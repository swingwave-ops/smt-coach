from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

import scripts.manage_codexbar as manager


def _archive(path: Path, member_name: str = "CodexBarCLI", content: bytes = b"synthetic collector\n") -> None:
    info = tarfile.TarInfo(member_name)
    info.size = len(content)
    info.mode = 0o755
    with tarfile.open(path, "w:gz") as archive:
        archive.addfile(info, io.BytesIO(content))


class CollectorManagerTests(unittest.TestCase):
    def test_fixture_archive_is_checked_without_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pin = json.loads((Path(manager.ROOT) / "vendor/codexbar/PINNED.json").read_text(encoding="utf-8"))
            pin_path = root / "PINNED.json"
            pin_path.write_text(json.dumps(pin), encoding="utf-8")
            archive = root / "fixture.tar.gz"
            _archive(archive)
            with mock.patch.object(manager, "PIN_PATH", pin_path):
                result = manager.verify_fixture(archive)
            self.assertTrue(result["ok"])
            self.assertEqual("CodexBarCLI", result["member"])

    def test_fixture_install_verify_and_remove_are_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = b"synthetic executable\n"
            archive = root / "fixture.tar.gz"
            _archive(archive, content=content)
            pin = json.loads((Path(manager.ROOT) / "vendor/codexbar/PINNED.json").read_text(encoding="utf-8"))
            pin["platforms"][manager.CURRENT_PLATFORM]["extracted_sha256"] = hashlib.sha256(content).hexdigest()
            pin_path = root / "PINNED.json"
            pin_path.write_text(json.dumps(pin), encoding="utf-8")
            managed = root / "vendor"
            version_dir = managed / "0.48.1-linux-x86_64"
            executable = version_dir / "CodexBarCLI"
            link = version_dir / "codexbar"
            version_file = version_dir / "VERSION"
            with mock.patch.object(manager, "MANAGED_ROOT", managed), mock.patch.object(manager, "PIN_PATH", pin_path), mock.patch.object(manager, "VERSION_DIR", version_dir), mock.patch.object(manager, "EXECUTABLE", executable), mock.patch.object(manager, "LINK", link), mock.patch.object(manager, "VERSION_FILE", version_file):
                installed = manager.install(archive=archive, fixture=True, allow_network=False)
                self.assertTrue(installed["ok"])
                self.assertEqual("0.48.1", version_file.read_text(encoding="utf-8").strip())
                verified = manager.verify_installed()
                self.assertTrue(verified["ok"])
                removed = manager.remove()
                self.assertTrue(removed["removed"])
                self.assertFalse(version_dir.exists())

    def test_traversal_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "bad.tar.gz"
            _archive(archive, member_name="../CodexBarCLI")
            pin_path = root / "PINNED.json"
            pin_path.write_text((Path(manager.ROOT) / "vendor/codexbar/PINNED.json").read_text(encoding="utf-8"), encoding="utf-8")
            with mock.patch.object(manager, "PIN_PATH", pin_path):
                with self.assertRaises(manager.ManagerFailure) as error:
                    manager.verify_fixture(archive)
            self.assertEqual("archive_path_traversal", error.exception.reason)


if __name__ == "__main__":
    unittest.main()
