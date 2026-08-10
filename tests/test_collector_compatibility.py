from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

import fit_coach
import scripts.manage_codexbar as manager


ROOT = Path(fit_coach.ROOT)
FIXTURES = ROOT / "tests" / "fixtures"


class CollectorCompatibilityTests(unittest.TestCase):
    def test_pin_contains_the_three_release_platforms(self):
        pin = json.loads((ROOT / "vendor/codexbar/PINNED.json").read_text(encoding="utf-8"))
        self.assertEqual("0.48.1", pin["version"])
        self.assertEqual(
            {"linux-x86_64", "macos-arm64", "macos-x86_64"},
            set(pin["platforms"]),
        )
        self.assertEqual(
            set(pin["platforms"]),
            set(fit_coach.EXPECTED_COLLECTOR_SHA256_BY_PLATFORM),
        )
        for platform_id, platform_pin in pin["platforms"].items():
            self.assertEqual(platform_pin["extracted_sha256"], fit_coach.EXPECTED_COLLECTOR_SHA256_BY_PLATFORM[platform_id])

    def test_platform_detection_covers_wsl_and_both_mac_architectures(self):
        self.assertEqual("linux-x86_64", manager._platform_id("Linux", "x86_64"))
        self.assertEqual("linux-x86_64", manager._platform_id("Linux", "amd64"))
        self.assertEqual("macos-arm64", manager._platform_id("Darwin", "arm64"))
        self.assertEqual("macos-x86_64", manager._platform_id("Darwin", "x86_64"))
        self.assertIsNone(manager._platform_id("Windows", "AMD64"))

    def test_official_archive_shape_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "official-shape.tar.gz"
            content = b"official-shaped executable\n"
            with tarfile.open(archive_path, "w:gz") as archive:
                executable = tarfile.TarInfo("CodexBarCLI")
                executable.size = len(content)
                executable.mode = 0o755
                archive.addfile(executable, io.BytesIO(content))
                link = tarfile.TarInfo("codexbar")
                link.type = tarfile.SYMTYPE
                link.linkname = "CodexBarCLI"
                archive.addfile(link)
                version = tarfile.TarInfo("VERSION")
                version_content = b"0.48.1\n"
                version.size = len(version_content)
                archive.addfile(version, io.BytesIO(version_content))

            extracted, digest = manager._read_archive(archive_path, expected_version="0.48.1")
            self.assertEqual(content, extracted)
            self.assertEqual(hashlib.sha256(content).hexdigest(), digest)

    def test_standard_windows_remain_compatible_across_pins(self):
        policy = {"stale_after_seconds": 3600}
        now = dt.datetime.fromisoformat("2026-08-10T01:30:00+00:00")
        for filename in ("codexbar-v0430-standard.json", "codexbar-v0481-standard.json"):
            payload = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
            normalized = fit_coach.normalize(payload, "codex", policy, now=now)
            self.assertTrue(normalized["ok"], filename)
            self.assertEqual(("7d",), tuple(normalized["windows"]))

    def test_details_only_payload_is_not_used_as_a_rate_window(self):
        payload = json.loads((FIXTURES / "codexbar-v0481-details-only.json").read_text(encoding="utf-8"))
        normalized = fit_coach.normalize(
            payload,
            "codex",
            {"stale_after_seconds": 3600},
            now=dt.datetime.fromisoformat("2026-08-10T01:30:00+00:00"),
        )
        self.assertFalse(normalized["ok"])
        self.assertEqual({}, normalized["windows"])

    def test_json_provider_error_wins_over_stderr_warning(self):
        payload = (FIXTURES / "codexbar-v0481-error.json").read_text(encoding="utf-8")
        completed = mock.Mock(returncode=1, stdout=payload, stderr="Could not create wakeup socket pair for CFSocket!!!")
        with mock.patch.object(fit_coach.subprocess, "run", return_value=completed):
            with self.assertRaises(fit_coach.CollectorFailure) as error:
                fit_coach.fetch("codex")
        self.assertEqual("app_server_closed_stdout", error.exception.reason)
        self.assertEqual("provider", error.exception.kind)
        self.assertEqual(1, error.exception.code)


if __name__ == "__main__":
    unittest.main()
