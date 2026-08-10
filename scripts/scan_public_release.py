#!/usr/bin/env python3
"""Scan the public manifest for local, credential, and private policy traces."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MANIFEST = ROOT / "scripts" / "validate_public_manifest.py"

# Keep the scanner's own source free of contiguous marker strings by composing
# values here.  The scanner reports only a relative path and marker category.
FORBIDDEN = (
    "/home/" + "chino",
    "Drop" + "box",
    "C:/" + "Users",
    "C:\\" + "Users",
    "/opt/" + "data",
    "BALANCED_" + "HARDENED",
    "pin_" + "status",
    "usage-" + "coach-" + "fit",
    "Luna" + " High",
    "Terra" + " Medium",
    "Spark" + " High",
    "grok-" + "4.5",
    "codexbar-" + "oauth-only.json",
)


def _manifest() -> list[Path]:
    namespace: dict[str, object] = {}
    source = PUBLIC_MANIFEST.read_text(encoding="utf-8")
    # The manifest is a literal tuple; using a tiny parser avoids importing a
    # script that may be run under an isolated interpreter.
    prefix = "PUBLIC_FILES = ("
    start = source.index(prefix) + len(prefix)
    end = source.index(")\n\n\ndef _digest", start)
    for line in source[start:end].splitlines():
        line = line.strip().rstrip(",")
        if line.startswith('"') and line.endswith('"'):
            namespace.setdefault("paths", []).append(line[1:-1])  # type: ignore[union-attr]
    return [ROOT / item for item in namespace.get("paths", [])]  # type: ignore[arg-type]


def main() -> int:
    findings: list[tuple[str, str]] = []
    for path in _manifest():
        if path.name.endswith(".tar.gz"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            findings.append((str(path.relative_to(ROOT)), "non_text_or_unreadable"))
            continue
        if text and not text.endswith("\n"):
            findings.append((str(path.relative_to(ROOT)), "missing_final_newline"))
        if any(line.rstrip("\r\n").rstrip(" \t") != line.rstrip("\r\n") for line in text.splitlines(True)):
            findings.append((str(path.relative_to(ROOT)), "trailing_whitespace"))
        for marker in FORBIDDEN:
            if marker in text:
                findings.append((str(path.relative_to(ROOT)), "private_marker"))
                break
        if "\x1b" in text:
            findings.append((str(path.relative_to(ROOT)), "ansi"))
    if findings:
        print(f"privacy_scan_fail findings={len(findings)}")
        return 1
    print(f"privacy_scan_pass files={len(_manifest())} markers=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
