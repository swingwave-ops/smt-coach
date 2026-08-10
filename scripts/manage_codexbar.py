#!/usr/bin/env python3
"""Manage the pinned collector without touching credentials or other installs.

Normal installation requires an explicitly supplied local archive.  Network
download is an opt-in operation and is intentionally not used by the public
test suite.  Archive members are read into memory and written to a staging
directory; tarfile extraction is never used directly, so member paths cannot
escape the managed directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANAGED_ROOT = ROOT / "vendor" / "codexbar"
PIN_PATH = MANAGED_ROOT / "PINNED.json"
VERSION = "0.48.1"
SUPPORTED_PLATFORM_IDS = ("linux-x86_64", "macos-arm64", "macos-x86_64")


def _platform_id(system: str | None = None, machine: str | None = None) -> str | None:
    system_value = (system if system is not None else platform.system()).lower()
    machine_value = (machine if machine is not None else platform.machine()).lower()
    if system_value == "linux" and machine_value in {"x86_64", "amd64"}:
        return "linux-x86_64"
    if system_value == "darwin" and machine_value in {"arm64", "aarch64"}:
        return "macos-arm64"
    if system_value == "darwin" and machine_value in {"x86_64", "amd64"}:
        return "macos-x86_64"
    return None


CURRENT_PLATFORM = _platform_id() or "unsupported"
VERSION_DIR = MANAGED_ROOT / f"{VERSION}-{CURRENT_PLATFORM}"
EXECUTABLE = VERSION_DIR / "CodexBarCLI"
LINK = VERSION_DIR / "codexbar"
VERSION_FILE = VERSION_DIR / "VERSION"
# CodexBar v0.48.1's Linux glibc CLI is about 150 MiB.  Keep explicit
# bounded limits with room for release growth, rather than accepting an
# unbounded archive or member.
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 192 * 1024 * 1024
EXIT_HOLD = 20


class ManagerFailure(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_pin() -> dict[str, Any]:
    try:
        raw = PIN_PATH.read_bytes()
        pin = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise ManagerFailure("pin_invalid")
    if not isinstance(pin, dict):
        raise ManagerFailure("pin_invalid")
    required = {"version", "tag", "source_commit", "platforms", "license", "license_path", "upstream"}
    if set(pin) != required:
        raise ManagerFailure("pin_invalid")
    if pin.get("version") != VERSION or pin.get("tag") != f"v{VERSION}":
        raise ManagerFailure("pin_invalid")
    platforms = pin.get("platforms")
    if not isinstance(platforms, dict) or set(platforms) != set(SUPPORTED_PLATFORM_IDS):
        raise ManagerFailure("pin_invalid")
    source_commit = pin.get("source_commit")
    if not isinstance(source_commit, str) or len(source_commit) != 40 or any(char not in "0123456789abcdef" for char in source_commit):
        raise ManagerFailure("pin_invalid")
    for platform_id, platform_pin in platforms.items():
        if not isinstance(platform_pin, dict) or set(platform_pin) != {"asset", "url", "sha256", "extracted_sha256"}:
            raise ManagerFailure("pin_invalid")
        expected_asset = f"CodexBarCLI-v{VERSION}-{platform_id}.tar.gz"
        if platform_pin.get("asset") != expected_asset:
            raise ManagerFailure("pin_invalid")
        expected_url = f"https://github.com/steipete/CodexBar/releases/download/v{VERSION}/{expected_asset}"
        if platform_pin.get("url") != expected_url:
            raise ManagerFailure("pin_invalid")
        for key in ("sha256", "extracted_sha256"):
            value = platform_pin.get(key)
            if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ManagerFailure("pin_invalid")
    return pin


def _platform_ok() -> bool:
    return CURRENT_PLATFORM in SUPPORTED_PLATFORM_IDS


def _current_pin(pin: dict[str, Any]) -> dict[str, str]:
    return _pin_for_platform(pin, CURRENT_PLATFORM)


def _pin_for_platform(pin: dict[str, Any], platform_id: str) -> dict[str, str]:
    if platform_id not in SUPPORTED_PLATFORM_IDS:
        raise ManagerFailure("collector_unsupported_platform")
    platform_pin = pin["platforms"].get(platform_id)
    if not isinstance(platform_pin, dict):
        raise ManagerFailure("collector_unsupported_platform")
    return platform_pin


def _safe_member(archive: tarfile.TarFile, *, fixture: bool, expected_version: str | None) -> tarfile.TarInfo:
    members = archive.getmembers()
    names: list[str] = []
    by_name: dict[str, tarfile.TarInfo] = {}
    for member in members:
        name = member.name.replace("\\", "/")
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or name != path.as_posix() or name in by_name:
            raise ManagerFailure("archive_path_traversal")
        names.append(name)
        by_name[name] = member

    if fixture and set(names) == {"CodexBarCLI"}:
        member = by_name["CodexBarCLI"]
        if not member.isfile() or member.issym() or member.islnk():
            raise ManagerFailure("archive_member_invalid")
    elif set(names) == {"CodexBarCLI", "codexbar", "VERSION"} and len(names) == 3:
        member = by_name["CodexBarCLI"]
        link = by_name["codexbar"]
        version = by_name["VERSION"]
        if not member.isfile() or member.issym() or member.islnk():
            raise ManagerFailure("archive_member_invalid")
        if not link.issym() or link.linkname.replace("\\", "/") != "CodexBarCLI":
            raise ManagerFailure("archive_member_invalid")
        if not version.isfile() or version.issym() or version.islnk() or version.size > 64:
            raise ManagerFailure("archive_member_invalid")
        if expected_version is not None:
            handle = archive.extractfile(version)
            if handle is None or handle.read(65).decode("utf-8", errors="replace").strip() != expected_version:
                raise ManagerFailure("archive_version_invalid")
    else:
        raise ManagerFailure("archive_member_count_invalid")
    if member.name != "CodexBarCLI":
        raise ManagerFailure("archive_member_invalid")
    if member.size < 0 or member.size > MAX_MEMBER_BYTES:
        raise ManagerFailure("archive_member_too_large")
    return member


def _read_archive(path: Path, *, fixture: bool = False, expected_version: str | None = None) -> tuple[bytes, str]:
    try:
        if not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ManagerFailure("archive_unreadable")
        with tarfile.open(path, mode="r:gz") as archive:
            member = _safe_member(archive, fixture=fixture, expected_version=expected_version)
            handle = archive.extractfile(member)
            if handle is None:
                raise ManagerFailure("archive_member_invalid")
            content = handle.read(MAX_MEMBER_BYTES + 1)
            if len(content) > MAX_MEMBER_BYTES:
                raise ManagerFailure("archive_member_too_large")
    except ManagerFailure:
        raise
    except (OSError, tarfile.TarError):
        raise ManagerFailure("archive_unreadable")
    return content, _sha256(content)


def verify_fixture(path: Path) -> dict[str, Any]:
    pin = _read_pin()
    _current_pin(pin)
    content, digest = _read_archive(path, fixture=True)
    return {"ok": True, "mode": "fixture", "platform": CURRENT_PLATFORM, "member": "CodexBarCLI", "extracted_sha256": digest, "bytes": len(content)}


def verify_archive(path: Path, platform_id: str | None = None) -> dict[str, Any]:
    pin = _read_pin()
    selected_platform = platform_id or CURRENT_PLATFORM
    platform_pin = _pin_for_platform(pin, selected_platform)
    content, extracted_digest = _read_archive(path, expected_version=pin["version"])
    archive_digest = _sha256(path.read_bytes())
    if archive_digest != platform_pin["sha256"]:
        raise ManagerFailure("archive_hash_mismatch")
    if extracted_digest != platform_pin["extracted_sha256"]:
        raise ManagerFailure("extracted_hash_mismatch")
    return {
        "ok": True,
        "mode": "archive",
        "version": VERSION,
        "platform": selected_platform,
        "archive_sha256": archive_digest,
        "extracted_sha256": extracted_digest,
        "bytes": len(content),
    }


def _installed_status(pin: dict[str, Any]) -> tuple[bool, str, str | None]:
    platform_pin = _current_pin(pin)
    if not VERSION_DIR.exists():
        return False, "collector_not_installed", None
    if not LINK.exists():
        return False, "collector_not_installed", None
    if not LINK.is_symlink():
        return False, "collector_symlink_invalid", None
    try:
        if LINK.resolve(strict=True) != EXECUTABLE.resolve(strict=True):
            return False, "collector_symlink_invalid", None
    except FileNotFoundError:
        return False, "collector_not_installed", None
    if not EXECUTABLE.is_file():
        return False, "collector_not_installed", None
    if VERSION_FILE.is_symlink() or not VERSION_FILE.is_file():
        return False, "collector_integrity_failed", None
    try:
        if VERSION_FILE.read_text(encoding="utf-8").strip() != VERSION:
            return False, "collector_integrity_failed", None
    except (OSError, UnicodeError):
        return False, "collector_integrity_failed", None
    if not os.access(EXECUTABLE, os.X_OK):
        return False, "collector_not_executable", None
    try:
        digest = _sha256(EXECUTABLE.read_bytes())
    except OSError:
        return False, "collector_integrity_failed", None
    if digest != platform_pin["extracted_sha256"]:
        return False, "collector_integrity_failed", digest
    return True, "installed", digest


def verify_installed() -> dict[str, Any]:
    if not _platform_ok():
        raise ManagerFailure("collector_unsupported_platform")
    pin = _read_pin()
    _current_pin(pin)
    good, reason, digest = _installed_status(pin)
    if not good:
        raise ManagerFailure(reason)
    return {"ok": True, "mode": "installed", "version": VERSION, "platform": CURRENT_PLATFORM, "extracted_sha256": digest}


def _download_archive(platform_pin: dict[str, str]) -> Path:
    # Kept behind an explicit command-line opt-in.  The public tests and the
    # normal build never enter this function.
    import urllib.request

    target_fd, target_name = tempfile.mkstemp(prefix="codexbar-download-", suffix=".tar.gz")
    os.close(target_fd)
    target = Path(target_name)
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(platform_pin["url"], timeout=30) as response, target.open("wb") as handle:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise ManagerFailure("archive_too_large")
                handle.write(chunk)
        if _sha256(target.read_bytes()) != platform_pin["sha256"]:
            raise ManagerFailure("archive_hash_mismatch")
        return target
    except ManagerFailure:
        target.unlink(missing_ok=True)
        raise
    except Exception:
        target.unlink(missing_ok=True)
        raise ManagerFailure("download_failed")


def install(*, archive: Path | None, fixture: bool, allow_network: bool) -> dict[str, Any]:
    if not _platform_ok():
        raise ManagerFailure("collector_unsupported_platform")
    pin = _read_pin()
    platform_pin = _current_pin(pin)
    if VERSION_DIR.exists():
        good, reason, digest = _installed_status(pin)
        if good:
            return {"ok": True, "mode": "already_installed", "version": VERSION, "extracted_sha256": digest}
        if reason not in {"collector_not_installed", "collector_integrity_failed", "collector_symlink_invalid", "collector_not_executable"}:
            raise ManagerFailure(reason)

    temporary_download: Path | None = None
    if archive is None:
        if not allow_network:
            raise ManagerFailure("archive_required")
        temporary_download = _download_archive(platform_pin)
        archive = temporary_download
    try:
        content, extracted_digest = _read_archive(
            archive,
            fixture=fixture,
            expected_version=None if fixture else pin["version"],
        )
        if fixture:
            archive_digest = None
        else:
            archive_digest = _sha256(archive.read_bytes())
            if archive_digest != platform_pin["sha256"]:
                raise ManagerFailure("archive_hash_mismatch")
            if extracted_digest != platform_pin["extracted_sha256"]:
                raise ManagerFailure("extracted_hash_mismatch")

        MANAGED_ROOT.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=MANAGED_ROOT))
        backup: Path | None = None
        try:
            staged_version = staging / VERSION
            staged_version.mkdir()
            staged_binary = staged_version / "CodexBarCLI"
            staged_binary.write_bytes(content)
            os.chmod(staged_binary, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IXOTH)
            (staged_version / "codexbar").symlink_to("CodexBarCLI")
            (staged_version / "VERSION").write_text(f"{pin['version']}\n", encoding="utf-8")
            if VERSION_DIR.exists():
                backup = MANAGED_ROOT / f".backup-{VERSION}-{os.getpid()}"
                os.replace(VERSION_DIR, backup)
            os.replace(staged_version, VERSION_DIR)
            if backup is not None:
                shutil.rmtree(backup)
            return {
                "ok": True,
                "mode": "fixture_install" if fixture else "installed",
                "version": VERSION,
                "platform": CURRENT_PLATFORM,
                "archive_sha256": archive_digest,
                "extracted_sha256": extracted_digest,
            }
        except Exception:
            target = VERSION_DIR
            if target.exists() and target != staging:
                shutil.rmtree(target, ignore_errors=True)
            if backup is not None and backup.exists() and not VERSION_DIR.exists():
                os.replace(backup, VERSION_DIR)
            raise ManagerFailure("install_rollback")
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    finally:
        if temporary_download is not None:
            temporary_download.unlink(missing_ok=True)


def remove() -> dict[str, Any]:
    # Only the version directory created by this manager is in scope.
    if VERSION_DIR.is_symlink():
        VERSION_DIR.unlink()
        return {"ok": True, "removed": True, "version": VERSION, "platform": CURRENT_PLATFORM}
    if VERSION_DIR.exists():
        shutil.rmtree(VERSION_DIR)
        return {"ok": True, "removed": True, "version": VERSION, "platform": CURRENT_PLATFORM}
    return {"ok": True, "removed": False, "version": VERSION, "platform": CURRENT_PLATFORM}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="manage_codexbar")
    sub = parser.add_subparsers(dest="command", required=True)
    install_parser = sub.add_parser("install")
    install_parser.add_argument("--archive", type=Path)
    install_parser.add_argument("--fixture", action="store_true", help="allow a synthetic local archive for tests")
    install_parser.add_argument("--allow-network", action="store_true", help="explicitly permit the pinned HTTPS download")
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--fixture", type=Path)
    verify_parser.add_argument("--archive", type=Path)
    verify_parser.add_argument("--platform", choices=SUPPORTED_PLATFORM_IDS)
    sub.add_parser("remove")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "verify":
            if args.fixture is not None and args.archive is not None:
                raise ManagerFailure("verify_input_conflict")
            if args.archive is not None:
                result = verify_archive(args.archive, args.platform)
            elif args.fixture is not None:
                result = verify_fixture(args.fixture)
            else:
                result = verify_installed()
        elif args.command == "install":
            result = install(archive=args.archive, fixture=args.fixture, allow_network=args.allow_network)
        else:
            result = remove()
    except ManagerFailure as failure:
        print(json.dumps({"ok": False, "reason": failure.reason}, separators=(",", ":")))
        return EXIT_HOLD
    except Exception:
        print(json.dumps({"ok": False, "reason": "internal_error"}, separators=(",", ":")))
        return EXIT_HOLD
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
