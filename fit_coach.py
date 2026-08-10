#!/usr/bin/env python3
"""Read-only public usage advisor.

The public engine has two input modes:

* fixture mode reads explicitly supplied JSON files and is hermetic;
* live mode invokes an installed, hash-pinned collector only after its local
  integrity checks pass.

This module never launches a model, changes a provider, installs credentials,
or falls back silently.  A malformed or untrusted input becomes a stable HOLD.
"""

from __future__ import annotations

import argparse
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import pwd
import stat
import subprocess
import sys
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
PRODUCT_NAME = "SMT Coach"
DEFAULT_POLICY = ROOT / "config" / "smt-policy.json"
COLLECTOR_CONFIG = ROOT / "config" / "collector-sources.json"
COLLECTOR_ROOT = ROOT / "vendor" / "codexbar"


def _collector_platform_id() -> str | None:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "linux-x86_64"
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "macos-arm64"
    if system == "darwin" and machine in {"x86_64", "amd64"}:
        return "macos-x86_64"
    return None


COLLECTOR_VERSION = "0.48.1"
COLLECTOR_PLATFORM = _collector_platform_id()
COLLECTOR_DIR = COLLECTOR_ROOT / f"{COLLECTOR_VERSION}-{COLLECTOR_PLATFORM or 'unsupported'}"
COLLECTOR_LINK = COLLECTOR_DIR / "codexbar"
COLLECTOR_REAL = COLLECTOR_DIR / "CodexBarCLI"
COLLECTOR_VERSION_FILE = COLLECTOR_DIR / "VERSION"

# The default-policy value is filled from the shipped bytes and is checked by
# the manifest/release tests.  The collector values come from the upstream pin.
EXPECTED_DEFAULT_POLICY_SHA256 = "60c7e64476739ca179852a47ca27848578d8710e170ecf3afe8c15bd55c68002"
EXPECTED_CONFIG_SHA256 = "8a250ab3112c6b44f2336272cfa4bd548f949eefd0f662df5642ff738b24e029"
EXPECTED_COLLECTOR_SHA256_BY_PLATFORM = {
    "linux-x86_64": "2a914798540109cabba2f600a3ae4f19d8c95096ff686b346eaf4851f3078b4d",
    "macos-arm64": "177f55dbaf056422f0e1cad41e07a80a3c3e3a15873af05524bd31548de94180",
    "macos-x86_64": "6f876b9f0d46d9f0920abed9720975e411bf124e74f0c32e94ab711bfa6d30cd",
}
EXPECTED_COLLECTOR_SHA256 = EXPECTED_COLLECTOR_SHA256_BY_PLATFORM.get(COLLECTOR_PLATFORM)

EXIT_HOLD = 20
DISPLAY_TZ = ZoneInfo("Asia/Seoul")
MAX_POLICY_BYTES = 1024 * 1024
SUPPORTED_PROVIDERS = ("codex", "claude", "grok")
ACTION_ROLES = ("plan", "implementation", "verification", "research", "secondary_audit")
WINDOW_NAMES = {300: "5h", 10080: "7d"}
REQUIRED_WINDOWS = {
    "codex": ("7d",),
    "claude": ("5h", "7d"),
    "grok": ("credits",),
}
EXPECTED_SOURCES = {
    "codex": ("oauth",),
    "claude": ("oauth",),
    "grok": ("grok-web",),
}
COLLECTOR_ERROR_REASONS = {
    "auth_expired",
    "network_unavailable",
    "app_server_closed_stdout",
    "schema_incompatible",
    "collector_error",
    "provider_usage_unavailable",
    "usage_invalid",
}
BLOCKED_CHILD_ENV = {
    "USAGE_COACH_CODEXBAR",
    "CODEX_HOME",
    "CLAUDE_CONFIG_DIR",
    "GROK_HOME",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "XAI_API_KEY",
    "GROK_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_BASE_URL",
    "XAI_BASE_URL",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "CURL_CA_BUNDLE",
    "REQUESTS_CA_BUNDLE",
}


class PublicFailure(Exception):
    """An expected failure represented by a public stable token."""

    def __init__(self, reason: str, *, selected_hash: str | None = None):
        self.reason = reason
        self.selected_hash = selected_hash
        super().__init__(reason)


class CollectorFailure(ValueError):
    """A collector failure with a stable public reason and safe metadata."""

    def __init__(self, reason: str, *, kind: str | None = None, code: int | None = None):
        self.reason = reason if reason in COLLECTOR_ERROR_REASONS else "collector_error"
        self.kind = kind if isinstance(kind, str) and len(kind) <= 64 else None
        self.code = code if isinstance(code, int) and not isinstance(code, bool) else None
        super().__init__(self.reason)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def utc_text(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def display_text(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(DISPLAY_TZ).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json(data: bytes) -> Any:
    def reject_constant(_value: str) -> None:
        raise ValueError("nonfinite_number")

    return json.loads(
        data.decode("utf-8"),
        parse_constant=reject_constant,
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _check_keys(value: Any, allowed: set[str]) -> None:
    if not isinstance(value, dict) or any(key not in allowed for key in value):
        raise PublicFailure("policy_schema_invalid")


def _check_pct(value: Any) -> None:
    if not _is_number(value) or not 0.0 <= float(value) <= 100.0:
        raise PublicFailure("policy_schema_invalid")


def _check_requires(value: Any) -> None:
    if not isinstance(value, list) or not value or len(set(value)) != len(value):
        raise PublicFailure("policy_schema_invalid")
    if any(item not in {"5h", "7d", "credits"} for item in value):
        raise PublicFailure("policy_schema_invalid")


def _check_candidate(value: Any) -> None:
    if not isinstance(value, dict):
        raise PublicFailure("policy_schema_invalid")
    _check_keys(value, {"provider", "model", "requires", "min_left_pct"})
    if not isinstance(value.get("provider"), str) or value["provider"] not in SUPPORTED_PROVIDERS:
        raise PublicFailure("policy_schema_invalid")
    if not isinstance(value.get("model"), str) or not value["model"].strip() or len(value["model"]) > 128:
        raise PublicFailure("policy_schema_invalid")
    _check_requires(value.get("requires"))
    if "min_left_pct" in value:
        _check_pct(value["min_left_pct"])


def _check_action_role(value: Any) -> None:
    if not isinstance(value, dict) or "enabled" not in value or not isinstance(value["enabled"], bool):
        raise PublicFailure("policy_schema_invalid")
    if not value["enabled"]:
        _check_keys(value, {"enabled", "disabled_reason"})
        if "disabled_reason" in value and value["disabled_reason"] != "policy_required":
            raise PublicFailure("policy_schema_invalid")
        return

    has_provider = "provider" in value
    has_candidates = "candidates" in value
    if has_provider == has_candidates:
        raise PublicFailure("policy_schema_invalid")
    if has_provider:
        _check_keys(value, {"enabled", "provider", "model", "requires", "min_left_pct"})
        if not isinstance(value.get("provider"), str) or value["provider"] not in SUPPORTED_PROVIDERS:
            raise PublicFailure("policy_schema_invalid")
        if not isinstance(value.get("model"), str) or not value["model"].strip() or len(value["model"]) > 128:
            raise PublicFailure("policy_schema_invalid")
        _check_requires(value.get("requires"))
        if "min_left_pct" in value:
            _check_pct(value["min_left_pct"])
        return

    _check_keys(value, {"enabled", "candidates", "switch_margin_pct"})
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise PublicFailure("policy_schema_invalid")
    for candidate in candidates:
        _check_candidate(candidate)
    if "switch_margin_pct" in value:
        _check_pct(value["switch_margin_pct"])


def validate_policy(policy: Any) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise PublicFailure("policy_schema_invalid")
    _check_keys(policy, {"schema_version", "stale_after_seconds", "providers", "roles"})
    if policy.get("schema_version") != 1:
        raise PublicFailure("policy_schema_invalid")
    stale = policy.get("stale_after_seconds")
    if not isinstance(stale, int) or isinstance(stale, bool) or not 60 <= stale <= 3600:
        raise PublicFailure("policy_schema_invalid")

    providers = policy.get("providers")
    if not isinstance(providers, dict):
        raise PublicFailure("policy_schema_invalid")
    for provider, block in providers.items():
        if provider not in SUPPORTED_PROVIDERS:
            raise PublicFailure("policy_schema_invalid")
        if not isinstance(block, dict):
            raise PublicFailure("policy_schema_invalid")
        _check_keys(block, {"enabled", "allowed_sources"})
        if not isinstance(block.get("enabled"), bool):
            raise PublicFailure("policy_schema_invalid")
        sources = block.get("allowed_sources")
        if not isinstance(sources, list) or not sources or any(not isinstance(item, str) for item in sources):
            raise PublicFailure("policy_schema_invalid")
        if set(sources) != set(EXPECTED_SOURCES[provider]):
            raise PublicFailure("policy_schema_invalid")

    roles = policy.get("roles")
    if not isinstance(roles, dict):
        raise PublicFailure("policy_schema_invalid")
    for role, value in roles.items():
        if role not in ACTION_ROLES:
            raise PublicFailure("policy_schema_invalid")
        _check_action_role(value)
    return policy


def _enabled_providers(policy: dict[str, Any]) -> set[str]:
    return {
        provider
        for provider, block in policy["providers"].items()
        if block.get("enabled") is True
    }


def _validate_role_references(policy: dict[str, Any], enabled: set[str]) -> None:
    for role in ACTION_ROLES:
        config = policy["roles"].get(role)
        if not config or config.get("enabled") is not True:
            continue
        candidates = []
        if "provider" in config:
            candidates = [config]
        else:
            candidates = config.get("candidates", [])
        for candidate in candidates:
            if candidate.get("provider") not in enabled:
                raise PublicFailure("policy_role_provider_unavailable")


def _read_static_assets() -> tuple[bytes, bytes]:
    try:
        policy_bytes = DEFAULT_POLICY.read_bytes()
    except (OSError, ValueError):
        raise PublicFailure("default_policy_integrity_failed")
    try:
        config_bytes = COLLECTOR_CONFIG.read_bytes()
    except (OSError, ValueError):
        raise PublicFailure("collector_config_integrity_failed")
    if sha256_bytes(policy_bytes) != EXPECTED_DEFAULT_POLICY_SHA256:
        raise PublicFailure("default_policy_integrity_failed")
    if sha256_bytes(config_bytes) != EXPECTED_CONFIG_SHA256:
        raise PublicFailure("collector_config_integrity_failed")
    return policy_bytes, config_bytes


def _safe_policy_bytes(path: str) -> tuple[bytes, str]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    try:
        try:
            if Path(path).is_symlink():
                raise PublicFailure("policy_symlink_rejected")
        except OSError:
            raise PublicFailure("policy_unreadable")
        try:
            fd = os.open(path, flags)
        except OSError as exc:
            if getattr(exc, "errno", None) == 40:  # ELOOP on Linux
                raise PublicFailure("policy_symlink_rejected")
            raise PublicFailure("policy_unreadable")
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PublicFailure("policy_not_regular")
        if info.st_uid != os.getuid():
            raise PublicFailure("policy_unsafe_owner")
        if info.st_mode & 0o022:
            raise PublicFailure("policy_unsafe_permissions")
        if info.st_size > MAX_POLICY_BYTES:
            raise PublicFailure("policy_too_large")
        data = os.read(fd, MAX_POLICY_BYTES + 1)
        if len(data) > MAX_POLICY_BYTES:
            raise PublicFailure("policy_too_large")
        return data, sha256_bytes(data)
    except PublicFailure:
        raise
    except (OSError, ValueError):
        raise PublicFailure("policy_unreadable")
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass


def _collector_integrity(*, required: bool) -> str | None:
    if not required:
        return None
    if COLLECTOR_PLATFORM not in EXPECTED_COLLECTOR_SHA256_BY_PLATFORM or EXPECTED_COLLECTOR_SHA256 is None:
        raise PublicFailure("collector_unsupported_platform")
    if not COLLECTOR_DIR.exists():
        raise PublicFailure("collector_not_installed")
    if not COLLECTOR_LINK.exists():
        raise PublicFailure("collector_not_installed")
    if not COLLECTOR_LINK.is_symlink():
        raise PublicFailure("collector_symlink_invalid")
    try:
        if COLLECTOR_LINK.resolve(strict=True) != COLLECTOR_REAL.resolve(strict=True):
            raise PublicFailure("collector_symlink_invalid")
    except FileNotFoundError:
        raise PublicFailure("collector_not_installed")
    if not COLLECTOR_REAL.is_file():
        raise PublicFailure("collector_not_installed")
    if COLLECTOR_VERSION_FILE.is_symlink() or not COLLECTOR_VERSION_FILE.is_file():
        raise PublicFailure("collector_integrity_failed")
    try:
        if COLLECTOR_VERSION_FILE.read_text(encoding="utf-8").strip() != COLLECTOR_VERSION:
            raise PublicFailure("collector_integrity_failed")
    except (OSError, UnicodeError):
        raise PublicFailure("collector_integrity_failed")
    if not os.access(COLLECTOR_REAL, os.X_OK):
        raise PublicFailure("collector_not_executable")
    try:
        digest = sha256_file(COLLECTOR_REAL)
    except OSError:
        raise PublicFailure("collector_integrity_failed")
    if digest != EXPECTED_COLLECTOR_SHA256:
        raise PublicFailure("collector_integrity_failed")
    return digest


def collector_environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in BLOCKED_CHILD_ENV}
    env["HOME"] = pwd.getpwuid(os.getuid()).pw_dir
    env["CODEXBAR_ALLOW_BROWSER_COOKIE_IMPORT"] = "0"
    env["CODEXBAR_CONFIG"] = str(COLLECTOR_CONFIG)
    return env


def _collector_command(provider: str) -> list[str]:
    source = "web" if provider == "grok" else "oauth"
    return [
        str(COLLECTOR_LINK),
        "usage",
        "--provider",
        provider,
        "--source",
        source,
        "--format",
        "json",
        "--json-only",
    ]


def _classify_collector_text(value: str) -> str:
    text = value.lower()
    if "app-server closed stdout" in text or "app server closed stdout" in text:
        return "app_server_closed_stdout"
    if any(token in text for token in ("unauthorized", "forbidden", "401", "403", "expired", "login required", "not logged in")):
        return "auth_expired"
    if any(token in text for token in ("could not resolve host", "name or service not known", "network is unreachable", "timed out", "timeout", "connection refused", "dns")):
        return "network_unavailable"
    if any(token in text for token in ("invalid data", "invalid json", "schema", "decode", "malformed")):
        return "schema_incompatible"
    return "collector_error"


def _collector_error_from_payload(payload: Any) -> CollectorFailure | None:
    rows = payload if isinstance(payload, list) else [payload]
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("error"), dict):
            continue
        error = row["error"]
        message = error.get("message") if isinstance(error.get("message"), str) else ""
        raw_code = error.get("code")
        code = raw_code if isinstance(raw_code, int) and not isinstance(raw_code, bool) else None
        return CollectorFailure(
            _classify_collector_text(message),
            kind=error.get("kind"),
            code=code,
        )
    return None


def fetch(provider: str, timeout: int = 30) -> Any:
    try:
        completed = subprocess.run(
            _collector_command(provider),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
            env=collector_environment(),
        )
    except subprocess.TimeoutExpired:
        raise CollectorFailure("network_unavailable", kind="timeout")
    except OSError:
        raise CollectorFailure("provider_usage_unavailable", kind="process")

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    payload: Any | None = None
    if stdout:
        try:
            payload = _strict_json(stdout.encode("utf-8"))
        except (UnicodeError, ValueError, json.JSONDecodeError):
            payload = None

    if payload is not None:
        collector_error = _collector_error_from_payload(payload)
        if collector_error is not None:
            raise collector_error
        if completed.returncode != 0:
            raise CollectorFailure(
                _classify_collector_text(stderr),
                kind="process",
                code=completed.returncode,
            )
        return payload

    if completed.returncode != 0:
        raise CollectorFailure(
            _classify_collector_text(stderr),
            kind="process",
            code=completed.returncode,
        )
    raise CollectorFailure("schema_incompatible", kind="json")


def _one_snapshot(payload: Any, provider: str) -> dict[str, Any]:
    rows = payload if isinstance(payload, list) else [payload]
    matches = [row for row in rows if isinstance(row, dict) and row.get("provider") == provider]
    if len(matches) != 1:
        raise ValueError("usage_invalid")
    return matches[0]


def normalize(payload: Any, provider: str, policy: dict[str, Any], now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    snapshot = _one_snapshot(payload, provider)
    usage = snapshot.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("usage_invalid")
    updated = parse_time(usage.get("updatedAt") or snapshot.get("updatedAt"))
    raw_age = None if updated is None else round((now - updated).total_seconds())
    age = None if raw_age is None else max(0, raw_age)
    stale_after = int(policy["stale_after_seconds"])
    stale = updated is None or raw_age is None or raw_age < -60 or age > stale_after

    windows: dict[str, dict[str, Any]] = {}
    for key in ("primary", "secondary", "tertiary"):
        raw = usage.get(key)
        if not isinstance(raw, dict):
            continue
        used = raw.get("usedPercent")
        if not _is_number(used) or not 0.0 <= float(used) <= 100.0:
            continue
        reset = parse_time(raw.get("resetsAt"))
        reset_raw = raw.get("resetsAt")
        if reset_raw not in (None, "") and reset is None:
            continue
        window_minutes = raw.get("windowMinutes")
        if provider == "grok" and window_minutes is None:
            name, window_value = "credits", None
        elif isinstance(window_minutes, int) and not isinstance(window_minutes, bool) and window_minutes > 0:
            name, window_value = WINDOW_NAMES.get(window_minutes, f"{window_minutes}m"), window_minutes
        else:
            continue
        item = {
            "left_pct": round(100.0 - float(used), 2),
            "window_minutes": window_value,
            "resets_at": display_text(reset),
            "resets_at_utc": utc_text(reset),
        }
        previous = windows.get(name)
        if previous is None or item["left_pct"] < previous["left_pct"]:
            windows[name] = item

    raw_source = snapshot.get("source")
    source = "grok-web" if provider == "grok" and raw_source == "web" else raw_source
    allowed = source in EXPECTED_SOURCES[provider]
    confidence = "high" if updated and not stale and allowed and windows else "none"
    return {
        "provider": provider,
        "ok": confidence == "high",
        "source": source,
        "source_allowed": allowed,
        "updated_at": display_text(updated),
        "updated_at_utc": utc_text(updated),
        "age_seconds": age,
        "stale": stale,
        "confidence": confidence,
        "windows": windows,
        "input_provenance": "live",
    }


def unavailable(
    provider: str,
    reason: str,
    provenance: str,
    *,
    error_kind: str | None = None,
    error_code: int | None = None,
) -> dict[str, Any]:
    result = {
        "provider": provider,
        "ok": False,
        "source": None,
        "source_allowed": False,
        "updated_at": None,
        "updated_at_utc": None,
        "age_seconds": None,
        "stale": True,
        "confidence": "none",
        "windows": {},
        "error": reason if reason in COLLECTOR_ERROR_REASONS else "collector_error",
        "input_provenance": provenance,
    }
    if error_kind is not None:
        result["error_kind"] = error_kind
    if error_code is not None:
        result["error_code"] = error_code
    return result


def collect(policy: dict[str, Any], files: dict[str, Path], timeout: int = 30) -> dict[str, dict[str, Any]]:
    enabled = tuple(provider for provider in SUPPORTED_PROVIDERS if provider in _enabled_providers(policy))

    def one(provider: str) -> dict[str, Any]:
        provenance = "fixture" if provider in files else "live"
        try:
            payload = _strict_json(files[provider].read_bytes()) if provider in files else fetch(provider, timeout)
            result = normalize(payload, provider, policy)
            result["input_provenance"] = provenance
            return result
        except CollectorFailure as failure:
            return unavailable(
                provider,
                failure.reason,
                provenance,
                error_kind=failure.kind,
                error_code=failure.code,
            )
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            return unavailable(provider, "usage_invalid", provenance)

    with ThreadPoolExecutor(max_workers=max(1, len(enabled)), thread_name_prefix="smt-usage") as pool:
        futures = {provider: pool.submit(one, provider) for provider in enabled}
        return {provider: futures[provider].result() for provider in enabled}


def _candidate_result(candidate: dict[str, Any], statuses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    provider = candidate["provider"]
    status = statuses.get(provider)
    required = tuple(candidate["requires"])
    base: dict[str, Any] = {
        "provider": provider,
        "model": candidate["model"],
        "decision": "HOLD",
        "requires": list(required),
    }
    if not status or not status.get("ok"):
        base["reason"] = "provider_unavailable"
        return base
    windows = status.get("windows", {})
    if any(window not in windows for window in required):
        base["reason"] = "required_windows_missing"
        return base
    minimum = float(candidate.get("min_left_pct", 0.0))
    margins = [float(windows[window]["left_pct"]) - minimum for window in required]
    score = min(margins)
    base["safe_headroom_pct"] = round(score, 6)
    if score < 0:
        base["reason"] = "minimum_headroom_not_met"
        return base
    lowest = min(float(windows[window]["left_pct"]) for window in required)
    base["decision"] = "ALLOW"
    base["capacity"] = "large" if lowest >= 60 else "medium" if lowest >= 35 else "small"
    base["reason"] = "trusted_usage_above_policy_floor"
    return base


def recommend(role: str, statuses: dict[str, dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    if role == "status":
        if not statuses:
            return {"role": role, "decision": "HOLD", "provider": None, "model": None, "reason": "no_providers_enabled"}
        healthy = all(item.get("ok") is True for item in statuses.values())
        return {
            "role": role,
            "decision": "OBSERVE" if healthy else "HOLD",
            "provider": None,
            "model": None,
            "reason": "read_only_status" if healthy else "status_degraded",
        }

    config = policy["roles"].get(role)
    if not config or config.get("enabled") is not True:
        return {"role": role, "decision": "HOLD", "provider": None, "model": None, "reason": "policy_required"}
    if "provider" in config:
        candidates = [config]
    else:
        candidates = config["candidates"]
    evaluated = [_candidate_result(candidate, statuses) for candidate in candidates]
    allowed = [item for item in evaluated if item["decision"] == "ALLOW"]
    if not allowed:
        return {
            "role": role,
            "decision": "HOLD",
            "provider": None,
            "model": None,
            "reason": "no_eligible_candidate",
            "candidates": evaluated,
        }
    selected = max(allowed, key=lambda item: float(item.get("safe_headroom_pct", -1)))
    result = {
        "role": role,
        "decision": "ALLOW",
        "provider": selected["provider"],
        "model": selected["model"],
        "capacity": selected.get("capacity"),
        "reason": selected["reason"],
        "candidates": evaluated,
    }
    return result


def _parse_file_specs(specs: list[str]) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for spec in specs:
        if not isinstance(spec, str) or "=" not in spec:
            raise PublicFailure("fixture_spec_invalid")
        provider, raw_path = spec.split("=", 1)
        if provider not in SUPPORTED_PROVIDERS or not raw_path or provider in files:
            raise PublicFailure("fixture_spec_invalid")
        files[provider] = Path(raw_path)
    return files


def _verify_fixture_set(files: dict[str, Path], enabled: set[str]) -> None:
    if set(files) != enabled:
        raise PublicFailure("fixture_provider_set_mismatch")
    for path in files.values():
        try:
            if not path.is_file():
                raise PublicFailure("fixture_unreadable")
            _strict_json(path.read_bytes())
        except PublicFailure:
            raise
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            raise PublicFailure("fixture_not_json")


def _payload(
    *,
    role: str,
    decision: dict[str, Any],
    providers: dict[str, Any],
    input_mode: str,
    policy_origin: str,
    selected_hash: str | None,
    default_hash: str | None,
    config_hash: str | None,
    collector_hash: str | None,
) -> dict[str, Any]:
    return {
        "product": PRODUCT_NAME,
        "schema_version": 1,
        "display_timezone": "Asia/Seoul",
        "observed_at": display_text(utcnow()),
        "observed_at_utc": utc_text(utcnow()),
        "mode": "read_only_advisory",
        "input_mode": input_mode,
        "policy_origin": policy_origin,
        "selected_policy_sha256": selected_hash,
        "runtime_trust": {
            "verified": default_hash is not None and config_hash is not None and (input_mode == "fixture" or collector_hash is not None),
            "default_policy_sha256": default_hash,
            "config_sha256": config_hash,
            "collector_sha256": collector_hash,
        },
        "decision": decision,
        "providers": providers,
        "automatic_launch": False,
        "automatic_fallback": False,
    }


def _run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    files = _parse_file_specs(args.file_specs)
    input_mode = "fixture" if files else "live"
    policy_origin = "explicit" if args.policy else "default"
    default_hash: str | None = None
    config_hash: str | None = None
    collector_hash: str | None = None
    selected_hash: str | None = None
    try:
        default_bytes, config_bytes = _read_static_assets()
        default_hash = sha256_bytes(default_bytes)
        config_hash = sha256_bytes(config_bytes)
    except PublicFailure as failure:
        decision = {"role": args.role, "decision": "HOLD", "provider": None, "model": None, "reason": failure.reason}
        return _payload(
            role=args.role,
            decision=decision,
            providers={},
            input_mode=input_mode,
            policy_origin=policy_origin,
            selected_hash=None,
            default_hash=default_hash,
            config_hash=config_hash,
            collector_hash=None,
        ), EXIT_HOLD

    if args.policy:
        try:
            policy_bytes, selected_hash = _safe_policy_bytes(args.policy)
        except PublicFailure as failure:
            decision = {"role": args.role, "decision": "HOLD", "provider": None, "model": None, "reason": failure.reason}
            return _payload(
                role=args.role,
                decision=decision,
                providers={},
                input_mode=input_mode,
                policy_origin=policy_origin,
                selected_hash=failure.selected_hash,
                default_hash=default_hash,
                config_hash=config_hash,
                collector_hash=None,
            ), EXIT_HOLD
    else:
        policy_bytes = default_bytes
        selected_hash = default_hash

    try:
        parsed_policy = _strict_json(policy_bytes)
    except (UnicodeError, ValueError, json.JSONDecodeError):
        decision = {"role": args.role, "decision": "HOLD", "provider": None, "model": None, "reason": "policy_not_json"}
        return _payload(
            role=args.role,
            decision=decision,
            providers={},
            input_mode=input_mode,
            policy_origin=policy_origin,
            selected_hash=selected_hash,
            default_hash=default_hash,
            config_hash=config_hash,
            collector_hash=None,
        ), EXIT_HOLD
    try:
        policy = validate_policy(parsed_policy)
    except PublicFailure:
        decision = {"role": args.role, "decision": "HOLD", "provider": None, "model": None, "reason": "policy_schema_invalid"}
        return _payload(
            role=args.role,
            decision=decision,
            providers={},
            input_mode=input_mode,
            policy_origin=policy_origin,
            selected_hash=selected_hash,
            default_hash=default_hash,
            config_hash=config_hash,
            collector_hash=None,
        ), EXIT_HOLD

    enabled = _enabled_providers(policy)
    if not enabled:
        reason = "no_providers_enabled"
        decision = {"role": args.role, "decision": "HOLD", "provider": None, "model": None, "reason": reason}
        return _payload(
            role=args.role,
            decision=decision,
            providers={},
            input_mode=input_mode,
            policy_origin=policy_origin,
            selected_hash=selected_hash,
            default_hash=default_hash,
            config_hash=config_hash,
            collector_hash=None,
        ), EXIT_HOLD

    try:
        _validate_role_references(policy, enabled)
    except PublicFailure as failure:
        decision = {"role": args.role, "decision": "HOLD", "provider": None, "model": None, "reason": failure.reason}
        return _payload(
            role=args.role,
            decision=decision,
            providers={},
            input_mode=input_mode,
            policy_origin=policy_origin,
            selected_hash=selected_hash,
            default_hash=default_hash,
            config_hash=config_hash,
            collector_hash=None,
        ), EXIT_HOLD

    if args.role != "status" and (args.role not in policy["roles"] or policy["roles"][args.role].get("enabled") is not True):
        decision = {"role": args.role, "decision": "HOLD", "provider": None, "model": None, "reason": "policy_required"}
        return _payload(
            role=args.role,
            decision=decision,
            providers={},
            input_mode=input_mode,
            policy_origin=policy_origin,
            selected_hash=selected_hash,
            default_hash=default_hash,
            config_hash=config_hash,
            collector_hash=None,
        ), EXIT_HOLD

    try:
        if files:
            _verify_fixture_set(files, enabled)
        else:
            collector_hash = _collector_integrity(required=True)
    except PublicFailure as failure:
        decision = {"role": args.role, "decision": "HOLD", "provider": None, "model": None, "reason": failure.reason}
        return _payload(
            role=args.role,
            decision=decision,
            providers={},
            input_mode=input_mode,
            policy_origin=policy_origin,
            selected_hash=selected_hash,
            default_hash=default_hash,
            config_hash=config_hash,
            collector_hash=collector_hash,
        ), EXIT_HOLD

    statuses = collect(policy, files, max(1, int(args.timeout)))
    decision = recommend(args.role, statuses, policy)
    code = 0 if decision["decision"] in {"OBSERVE", "ALLOW"} else EXIT_HOLD
    return _payload(
        role=args.role,
        decision=decision,
        providers=statuses,
        input_mode=input_mode,
        policy_origin=policy_origin,
        selected_hash=selected_hash,
        default_hash=default_hash,
        config_hash=config_hash,
        collector_hash=collector_hash,
    ), code


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="smt-coach", description="Read-only usage status and advisory output")
    parser.add_argument("--role", choices=("status",) + ACTION_ROLES, required=True)
    parser.add_argument("--policy", help="explicit policy file; never auto-discovered")
    parser.add_argument("--file", dest="file_specs", action="append", default=[], metavar="PROVIDER=PATH")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _arg_parser().parse_args(argv)
    try:
        payload, code = _run(args)
    except PublicFailure as failure:
        payload = _payload(
            role=args.role,
            decision={"role": args.role, "decision": "HOLD", "provider": None, "model": None, "reason": failure.reason},
            providers={},
            input_mode="fixture" if args.file_specs else "live",
            policy_origin="explicit" if args.policy else "default",
            selected_hash=failure.selected_hash,
            default_hash=None,
            config_hash=None,
            collector_hash=None,
        )
        code = EXIT_HOLD
    except Exception:
        payload = _payload(
            role=args.role,
            decision={"role": args.role, "decision": "HOLD", "provider": None, "model": None, "reason": "internal_error"},
            providers={},
            input_mode="fixture" if args.file_specs else "live",
            policy_origin="explicit" if args.policy else "default",
            selected_hash=None,
            default_hash=None,
            config_hash=None,
            collector_hash=None,
        )
        code = EXIT_HOLD
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
