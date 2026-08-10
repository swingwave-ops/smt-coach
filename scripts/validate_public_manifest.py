#!/usr/bin/env python3
"""Validate the allowlisted public release surface."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = (
    ".gitignore",
    "LICENSE",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "fit_coach.py",
    "smt_coach.py",
    "smt",
    "config/collector-sources.json",
    "config/smt-policy.json",
    "config/policy.schema.json",
    "config/presets/example-policy.json",
    "vendor/codexbar/LICENSE",
    "vendor/codexbar/PINNED.json",
    "scripts/manage_codexbar.py",
    "scripts/validate_public_manifest.py",
    "scripts/scan_public_release.py",
    "docs/input-schema.md",
    "docs/install-linux-x86_64.md",
    "docs/install-macos.md",
    "docs/privacy.md",
    "docs/threat-model.md",
    "docs/public-distribution.md",
    "docs/verification-handoff.md",
    "docs/release-checklist.md",
    "docs/provenance.md",
    "tests/fixtures/codex.synthetic.json",
    "tests/fixtures/claude.synthetic.json",
    "tests/fixtures/grok.synthetic.json",
    "tests/fixtures/codexbar.synthetic.tar.gz",
    "tests/fixtures/codexbar-v0430-standard.json",
    "tests/fixtures/codexbar-v0481-standard.json",
    "tests/fixtures/codexbar-v0481-details-only.json",
    "tests/fixtures/codexbar-v0481-error.json",
    "tests/test_policy_boundary.py",
    "tests/test_manage_codexbar.py",
    "tests/test_collector_compatibility.py",
    "tests/test_public_cli.py",
)


def _digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    missing = [relative for relative in PUBLIC_FILES if not (ROOT / relative).is_file()]
    forbidden = [
        relative
        for relative in PUBLIC_FILES
        if (ROOT / relative).is_symlink()
    ]
    binary = []
    for relative in PUBLIC_FILES:
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            binary.append(relative)
            continue
        if b"\0" in data and not relative.endswith(".tar.gz"):
            binary.append(relative)
    legacy = (ROOT / "config" / ("codexbar-" + "oauth-only.json")).exists()
    installed = list((ROOT / "vendor" / "codexbar").glob(f"{'*'}/CodexBarCLI"))
    if missing or forbidden or binary or legacy or installed:
        print(
            "manifest_fail "
            f"missing={len(missing)} symlink={len(forbidden)} binary={len(binary)} "
            f"legacy={int(legacy)} installed_binary={len(installed)}"
        )
        return 1
    paths = [ROOT / relative for relative in PUBLIC_FILES]
    print(f"manifest_exact_pass files={len(paths)} aggregate_sha256={_digest(paths)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
