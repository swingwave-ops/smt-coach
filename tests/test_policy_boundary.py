from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest

import fit_coach


ROOT = Path(fit_coach.ROOT)


def _rows() -> dict[str, list[dict]]:
    now = fit_coach.utcnow()
    updated = now.isoformat().replace("+00:00", "Z")
    reset = (now + dt.timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    return {
        "codex": [{"provider": "codex", "source": "oauth", "usage": {"updatedAt": updated, "primary": {"usedPercent": 1, "windowMinutes": 10080, "resetsAt": reset}}}],
        "claude": [{"provider": "claude", "source": "oauth", "usage": {"updatedAt": updated, "primary": {"usedPercent": 1, "windowMinutes": 300, "resetsAt": reset}, "secondary": {"usedPercent": 1, "windowMinutes": 10080, "resetsAt": reset}}}],
        "grok": [{"provider": "grok", "source": "web", "usage": {"updatedAt": updated, "primary": {"usedPercent": 1, "resetsAt": reset}}}],
    }


def _files(directory: Path, providers: set[str] | None = None) -> list[str]:
    providers = providers or set(_rows())
    result: list[str] = []
    for provider, payload in _rows().items():
        if provider not in providers:
            continue
        path = directory / f"{provider}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        result.extend(["--file", f"{provider}={path}"])
    return result


def _invoke(args: list[str]) -> tuple[int, dict]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = fit_coach.main(args)
    return code, json.loads(output.getvalue())


class PolicyBoundaryTests(unittest.TestCase):
    def _policy(self, directory: Path, **changes) -> Path:
        policy = json.loads((ROOT / "config/smt-policy.json").read_text(encoding="utf-8"))
        for key, value in changes.items():
            policy[key] = value
        path = directory / "policy.json"
        path.write_text(json.dumps(policy), encoding="utf-8")
        path.chmod(0o600)
        return path

    def test_stale_after_bounds_are_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for value in (59, 3601):
                policy_path = self._policy(path, stale_after_seconds=value)
                code, payload = _invoke(["--role", "status", "--policy", str(policy_path), *_files(path)])
                self.assertEqual(20, code)
                self.assertEqual("policy_schema_invalid", payload["decision"]["reason"])

    def test_unknown_key_does_not_echo_path_or_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            policy_path = self._policy(path, unknown_private_key="do-not-print")
            code, payload = _invoke(["--role", "status", "--policy", str(policy_path), *_files(path)])
            raw = json.dumps(payload)
            self.assertEqual(20, code)
            self.assertEqual("policy_schema_invalid", payload["decision"]["reason"])
            self.assertNotIn(str(policy_path), raw)
            self.assertNotIn("unknown_private_key", raw)

    def test_symlink_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            target = path / "target.json"
            target.write_text((ROOT / "config/smt-policy.json").read_text(encoding="utf-8"), encoding="utf-8")
            link = path / "link.json"
            link.symlink_to(target)
            code, payload = _invoke(["--role", "status", "--policy", str(link), *_files(path)])
            self.assertEqual(20, code)
            self.assertEqual("policy_symlink_rejected", payload["decision"]["reason"])
            self.assertIsNone(payload["selected_policy_sha256"])

    def test_fixture_set_must_match_enabled_provider_set(self):
        with tempfile.TemporaryDirectory() as directory:
            code, payload = _invoke(["--role", "status", *_files(Path(directory), {"codex", "claude"})])
            self.assertEqual(20, code)
            self.assertEqual("fixture_provider_set_mismatch", payload["decision"]["reason"])

    def test_all_provider_failure_is_status_degraded(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = _rows()
            rows["grok"][0]["usage"]["updatedAt"] = "2000-01-01T00:00:00Z"
            for provider, payload in rows.items():
                path = Path(directory) / f"{provider}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
            args = ["--role", "status"]
            for provider in rows:
                args.extend(["--file", f"{provider}={Path(directory) / (provider + '.json')}"])
            code, payload = _invoke(args)
            self.assertEqual(20, code)
            self.assertEqual("status_degraded", payload["decision"]["reason"])


if __name__ == "__main__":
    unittest.main()
