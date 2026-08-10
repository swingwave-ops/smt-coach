#!/usr/bin/env python3
"""Human display wrapper for the isolated public JSON engine."""

from __future__ import annotations

# Keep the bootstrap deliberately tiny.  A direct public invocation re-execs
# before importing modules that could be shadowed by the current directory.
import os
import sys


def _running_isolated() -> bool:
    flags = sys.flags
    return bool(flags.isolated and flags.no_site and flags.dont_write_bytecode)


def _reexec_isolated() -> None:
    target = os.path.abspath(__file__)
    os.execv(sys.executable, [sys.executable, "-I", "-S", "-B", target, *sys.argv[1:]])


if __name__ == "__main__" and not _running_isolated():
    _reexec_isolated()
    raise SystemExit("isolated re-exec failed")


import json
import re
import shutil
import subprocess
import unicodedata
from typing import Any


ROOT = os.path.dirname(os.path.abspath(__file__))
FIT_COACH = os.path.join(ROOT, "fit_coach.py")
PRODUCT_NAME = "SMT Coach"
PROVIDER_ORDER = ("codex", "claude", "grok")
PROVIDER_LABELS = {"codex": "Codex", "claude": "Claude", "grok": "Grok"}
WINDOW_ORDER = ("5h", "7d", "credits")
HORIZONTAL_MIN_WIDTH = 100
EXIT_HOLD = 20
RESET_RE = re.compile(r"^\d{4}-(\d{2})-(\d{2})T(\d{2}):(\d{2})")


def fit_coach_argv(forwarded: list[str]) -> list[str]:
    return ["-I", "-S", "-B", FIT_COACH, *forwarded]


def fit_coach_command(forwarded: list[str]) -> list[str]:
    return [sys.executable, *fit_coach_argv(forwarded)]


def strip_json_flag(argv: list[str]) -> tuple[list[str], bool]:
    forwarded: list[str] = []
    requested = False
    for arg in argv:
        if arg == "--json":
            requested = True
        else:
            forwarded.append(arg)
    return forwarded, requested


def terminal_width() -> int:
    try:
        return int(shutil.get_terminal_size(fallback=(80, 24)).columns)
    except (OSError, TypeError, ValueError):
        return 80


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if number == int(number):
        return f"{int(number)}%"
    return f"{number:.2f}".rstrip("0").rstrip(".") + "%"


def _fmt_reset(value: Any) -> str:
    return "-" if value in (None, "") else str(value)


def _fmt_reset_short(value: Any) -> str:
    if value in (None, ""):
        return "-"
    text = str(value)
    match = RESET_RE.match(text)
    if match:
        return f"{match.group(1)}-{match.group(2)} {match.group(3)}:{match.group(4)}"
    return text if len(text) <= 11 else text[:11]


def freshness_text(status: dict[str, Any] | None) -> str:
    if not status:
        return "unavailable"
    if status.get("error"):
        return f"error:{status['error']}"
    if status.get("stale"):
        age = status.get("age_seconds")
        return "stale" if age is None else f"stale ({age}s)"
    if not status.get("ok"):
        return "unavailable"
    age = status.get("age_seconds")
    return "fresh" if age is None else f"fresh ({age}s)"


def _ordered_providers(providers: dict[str, Any] | None) -> list[str]:
    if not isinstance(providers, dict):
        return []
    return [name for name in PROVIDER_ORDER if name in providers]


def _window_cells(status: dict[str, Any] | None, short_reset: bool = False) -> dict[str, tuple[str, str]]:
    windows = (status or {}).get("windows") or {}
    reset_format = _fmt_reset_short if short_reset else _fmt_reset
    result: dict[str, tuple[str, str]] = {}
    for name in WINDOW_ORDER:
        row = windows.get(name)
        if isinstance(row, dict):
            result[name] = (_fmt_pct(row.get("left_pct")), reset_format(row.get("resets_at")))
        else:
            result[name] = ("-", "-")
    return result


def render_header(payload: dict[str, Any]) -> list[str]:
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    role = decision.get("role") or "-"
    verdict = decision.get("decision") or "-"
    provider = decision.get("provider")
    model = decision.get("model")
    capacity = decision.get("capacity")
    recommendation = " / ".join(str(item) for item in (provider, model) if item)
    if capacity:
        recommendation = f"{recommendation} / capacity={capacity}" if recommendation else f"capacity={capacity}"
    if not recommendation:
        recommendation = "(none)"
    return [
        f"{PRODUCT_NAME}  |  관측 {payload.get('observed_at') or '-'} KST  |  역할={role}  |  판정={verdict}",
        f"권고: {recommendation}  |  사유={decision.get('reason') or '-'}",
    ]


def render_vertical(providers: dict[str, Any] | None) -> list[str]:
    lines: list[str] = []
    ordered = _ordered_providers(providers)
    if not ordered:
        return ["providers: (empty / preflight)"]
    for name in ordered:
        status = providers.get(name) if providers else None
        lines.append(f"[{PROVIDER_LABELS.get(name, name)}]")
        if not isinstance(status, dict):
            lines.append("  freshness: unavailable")
            continue
        lines.append(f"  source: {status.get('source') or '-'}")
        lines.append(f"  freshness: {freshness_text(status)}")
        if status.get("error"):
            lines.append(f"  error: {status['error']}")
        for window in WINDOW_ORDER:
            remaining, reset = _window_cells(status)[window]
            if remaining == "-" and reset == "-":
                lines.append(f"  {window}: (missing)")
            else:
                lines.append(f"  {window}: 잔량 {remaining}, 리셋 {reset}")
    return lines


def render_horizontal(providers: dict[str, Any] | None) -> list[str]:
    headers = (
        f"{'Provider':<8} {'5h%':>5} {'5h KST':<11} "
        f"{'7d%':>5} {'7d KST':<11} {'cr%':>5} {'cr KST':<11} "
        f"{'source':<8} {'freshness'}"
    )
    lines = [headers, "-" * min(len(headers), 100)]
    ordered = _ordered_providers(providers)
    if not ordered:
        lines.append("(no providers — preflight or empty payload)")
        return lines
    for name in ordered:
        status = providers.get(name) if providers else None
        cells = _window_cells(status if isinstance(status, dict) else None, short_reset=True)
        source = status.get("source") if isinstance(status, dict) else None
        lines.append(
            f"{PROVIDER_LABELS.get(name, name):<8} "
            f"{cells['5h'][0]:>5} {cells['5h'][1]:<11} "
            f"{cells['7d'][0]:>5} {cells['7d'][1]:<11} "
            f"{cells['credits'][0]:>5} {cells['credits'][1]:<11} "
            f"{(source or '-'):<8} {freshness_text(status if isinstance(status, dict) else None)}"
        )
    return lines


def _character_cell_width(character: str) -> int:
    category = unicodedata.category(character)
    if unicodedata.combining(character) or category in {"Mn", "Me", "Cf", "Cc"}:
        return 0
    return 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1


def display_cell_width(text: str) -> int:
    cells = 0
    for character in str(text):
        if character == "\t":
            cells += 8 - cells % 8
        else:
            cells += _character_cell_width(character)
    return cells


def _expand_tabs(text: str) -> str:
    result: list[str] = []
    cells = 0
    for character in text:
        if character == "\t":
            count = 8 - cells % 8
            result.append(" " * count)
            cells += count
        else:
            result.append(character)
            cells += _character_cell_width(character)
    return "".join(result)


def _prefix_for_cells(text: str, limit: int) -> int:
    cells = 0
    for index, character in enumerate(text):
        width = _character_cell_width(character)
        if cells + width > limit:
            return index
        cells += width
    return len(text)


def _wrap_line(line: str, width: int) -> list[str]:
    line = _expand_tabs(line)
    if display_cell_width(line) <= width:
        return [line]
    remaining = line
    output: list[str] = []
    first = True
    indent = " " * min(len(line) - len(line.lstrip(" ")) + 2, max(0, width - 1))
    while remaining:
        prefix = "" if first else indent
        cut = _prefix_for_cells(remaining, max(1, width - display_cell_width(prefix)))
        if cut <= 0:
            output.append(prefix + "?")
            remaining = remaining[1:]
            first = False
            continue
        if cut == len(remaining):
            output.append(prefix + remaining.rstrip())
            break
        chunk = remaining[:cut]
        split = max((match.start() for match in re.finditer(r"\s+", chunk) if match.start() > 0), default=None)
        if split is None:
            output.append(prefix + chunk.rstrip())
            remaining = remaining[cut:].lstrip()
        else:
            output.append(prefix + chunk[:split].rstrip())
            remaining = remaining[split:].lstrip()
        first = False
    return output


def _wrap_lines(lines: list[str], width: int) -> list[str]:
    output: list[str] = []
    for line in lines:
        for logical in str(line).splitlines() or [""]:
            output.extend(_wrap_line(logical, max(1, width)))
    return output


def render_human(payload: dict[str, Any], width: int | None = None) -> str:
    width = terminal_width() if width is None else int(width)
    lines = render_header(payload if isinstance(payload, dict) else {})
    lines.append("")
    providers = payload.get("providers") if isinstance(payload, dict) else {}
    lines.extend(render_horizontal(providers if isinstance(providers, dict) else {}) if width >= HORIZONTAL_MIN_WIDTH else render_vertical(providers if isinstance(providers, dict) else {}))
    lines.append("")
    lines.append(f"automatic_launch={str(bool(payload.get('automatic_launch', False))).lower()}")
    lines.append(f"automatic_fallback={str(bool(payload.get('automatic_fallback', False))).lower()}")
    return "\n".join(_wrap_lines(lines, width)).replace("\033", "") + "\n"


def run_json_passthrough(forwarded: list[str]) -> int:
    os.execv(sys.executable, fit_coach_command(forwarded))
    return 1


def run_human(forwarded: list[str], width: int | None = None) -> int:
    try:
        completed = subprocess.run(
            fit_coach_command(forwarded),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        sys.stderr.write("smt-coach: engine unavailable\n")
        return EXIT_HOLD
    if completed.stderr:
        sys.stderr.buffer.write(completed.stderr)
    if completed.returncode == 2:
        if completed.stdout:
            sys.stdout.buffer.write(completed.stdout)
        return 2
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        sys.stderr.write("smt-coach: invalid engine output\n")
        return EXIT_HOLD if completed.returncode == 0 else completed.returncode
    if not isinstance(payload, dict):
        sys.stderr.write("smt-coach: invalid engine payload\n")
        return EXIT_HOLD if completed.returncode == 0 else completed.returncode
    sys.stdout.write(render_human(payload, width))
    return int(completed.returncode)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    forwarded, wants_json = strip_json_flag(raw)
    if wants_json:
        return run_json_passthrough(forwarded)
    width = None
    raw_width = os.environ.get("SMT_COACH_WIDTH")
    if raw_width:
        try:
            width = int(raw_width)
        except ValueError:
            width = None
    return run_human(forwarded, width)


if __name__ == "__main__":
    sys.exit(main())
