from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import fit_coach
import smt_coach


ROOT = Path(fit_coach.ROOT)


def _fixture_rows() -> dict[str, list[dict]]:
    now = fit_coach.utcnow()
    updated = now.isoformat().replace("+00:00", "Z")
    reset = (now + dt.timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    return {
        "codex": [{
            "provider": "codex", "source": "oauth",
            "usage": {"updatedAt": updated, "primary": {"usedPercent": 20, "windowMinutes": 10080, "resetsAt": reset}},
        }],
        "claude": [{
            "provider": "claude", "source": "oauth",
            "usage": {
                "updatedAt": updated,
                "primary": {"usedPercent": 10, "windowMinutes": 300, "resetsAt": reset},
                "secondary": {"usedPercent": 20, "windowMinutes": 10080, "resetsAt": reset},
            },
        }],
        "grok": [{
            "provider": "grok", "source": "web",
            "usage": {"updatedAt": updated, "primary": {"usedPercent": 5, "resetsAt": reset}},
        }],
    }


def _write_fixtures(directory: Path, rows: dict[str, list[dict]] | None = None) -> list[str]:
    rows = rows or _fixture_rows()
    specs: list[str] = []
    for provider, payload in rows.items():
        path = directory / f"{provider}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        specs.extend(["--file", f"{provider}={path}"])
    return specs


class PublicCliTests(unittest.TestCase):
    def _run(self, script: str, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
        command = [sys.executable, script, *args]
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=merged, check=False)

    def test_status_fixture_is_observe_and_has_public_trust_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            specs = _write_fixtures(Path(directory))
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(ROOT / "fit_coach.py"), "--role", "status", *specs],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr.decode())
            payload = json.loads(completed.stdout)
            self.assertEqual("OBSERVE", payload["decision"]["decision"])
            self.assertEqual("default", payload["policy_origin"])
            self.assertEqual(payload["runtime_trust"]["default_policy_sha256"], payload["selected_policy_sha256"])
            self.assertIsNone(payload["runtime_trust"]["collector_sha256"])
            self.assertFalse(payload["automatic_launch"])
            self.assertFalse(payload["automatic_fallback"])
            self.assertNotIn("pin_" + "status", completed.stdout.decode())

    def test_live_without_collector_holds_without_partial_provider_output(self):
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(ROOT / "fit_coach.py"), "--role", "status"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(20, completed.returncode)
        payload = json.loads(completed.stdout)
        self.assertEqual("collector_not_installed", payload["decision"]["reason"])
        self.assertEqual({}, payload["providers"])

    def test_default_action_is_policy_required(self):
        with tempfile.TemporaryDirectory() as directory:
            specs = _write_fixtures(Path(directory))
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(ROOT / "fit_coach.py"), "--role", "plan", *specs],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertEqual(20, completed.returncode)
        self.assertEqual("policy_required", json.loads(completed.stdout)["decision"]["reason"])

    def test_explicit_example_policy_can_advisory_allow(self):
        with tempfile.TemporaryDirectory() as directory:
            specs = _write_fixtures(Path(directory))
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(ROOT / "fit_coach.py"), "--role", "plan", "--policy", str(ROOT / "config/presets/example-policy.json"), *specs],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertEqual(0, completed.returncode, completed.stderr.decode())
        payload = json.loads(completed.stdout)
        self.assertEqual("ALLOW", payload["decision"]["decision"])
        self.assertEqual("explicit", payload["policy_origin"])

    def test_wrapper_json_matches_engine_volatile_free(self):
        with tempfile.TemporaryDirectory() as directory:
            specs = _write_fixtures(Path(directory))
            engine = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(ROOT / "fit_coach.py"), "--role", "status", *specs],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            wrapper = subprocess.run(
                [sys.executable, str(ROOT / "smt_coach.py"), "--json", "--role", "status", *specs],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertEqual(engine.returncode, wrapper.returncode)
        self.assertEqual(json.loads(engine.stdout)["decision"], json.loads(wrapper.stdout)["decision"])
        self.assertEqual(json.loads(engine.stdout)["providers"].keys(), json.loads(wrapper.stdout)["providers"].keys())

    def test_human_width_boundary_has_no_ansi_or_overflow(self):
        with tempfile.TemporaryDirectory() as directory:
            specs = _write_fixtures(Path(directory))
            for width in ("99", "100"):
                completed = self._run(str(ROOT / "smt_coach.py"), ["--role", "status", *specs], {"SMT_COACH_WIDTH": width})
                self.assertEqual(0, completed.returncode, completed.stderr.decode())
                text = completed.stdout.decode()
                self.assertNotIn("\033", text)
                self.assertIn("automatic_launch=false", text)
                for line in text.splitlines():
                    self.assertLessEqual(smt_coach.display_cell_width(line), int(width), repr(line))

    def test_launcher_isolated_json(self):
        with tempfile.TemporaryDirectory() as directory:
            specs = _write_fixtures(Path(directory))
            completed = subprocess.run(
                [str(ROOT / "smt"), "--json", "--role", "status", *specs],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertEqual(0, completed.returncode, completed.stderr.decode())
        self.assertEqual("OBSERVE", json.loads(completed.stdout)["decision"]["decision"])


if __name__ == "__main__":
    unittest.main()
