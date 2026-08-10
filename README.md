# SMT Coach

SMT Coach is a read-only usage advisor for Codex, Claude, and Grok. It reads
normalized usage snapshots and returns either `OBSERVE`, `ALLOW`, or a stable
`HOLD` reason. It never starts a model, changes a provider, installs a hook, or
uses an automatic fallback.

The shipped policy is status-only. Action roles are disabled until a user
selects an explicit policy file with `--policy`.

## Quick start

```bash
python3 -I -S -B fit_coach.py --role status
python3 smt_coach.py --role status
./smt --role status
```

Without an installed collector, live mode stops with `HOLD` rather than making
a partial or guessed report. For a hermetic check, provide one fixture for
each enabled provider:

```bash
python3 -I -S -B fit_coach.py --role status \
  --file codex=tests/fixtures/codex.synthetic.json \
  --file claude=tests/fixtures/claude.synthetic.json \
  --file grok=tests/fixtures/grok.synthetic.json
```

Use `smt_coach.py --json` when the exact engine JSON and exit code are needed.
`HOLD` is exit `20`; `OBSERVE` and `ALLOW` are exit `0`; command-line errors
are exit `2`.

## Policy and inputs

`config/smt-policy.json` is the built-in policy. It enables the three public
collector sources but leaves every action role disabled. A non-default policy
must be selected explicitly:

```bash
python3 -I -S -B fit_coach.py --role plan \
  --policy ./config/presets/example-policy.json \
  --file codex=tests/fixtures/codex.synthetic.json \
  --file claude=tests/fixtures/claude.synthetic.json \
  --file grok=tests/fixtures/grok.synthetic.json
```

Policy files are opened once with a no-symlink boundary, ownership and mode
checks, a 1 MiB limit, a bounded read, and strict finite-number JSON parsing.
The output reports hashes and a `default`/`explicit` origin, never the selected
path or raw exception.

The fixture format is a JSON object or array containing exactly one snapshot
for each provider. The snapshot carries `provider`, `source`, and a `usage`
object with `updatedAt` and quota windows. See
[`docs/input-schema.md`](docs/input-schema.md).

## Collector

CodexBar `0.48.1` is pinned for Linux/WSL x86_64, macOS Apple Silicon arm64,
and macOS Intel x86_64. Its per-platform release metadata and extracted
executable hashes are pinned in
[`vendor/codexbar/PINNED.json`](vendor/codexbar/PINNED.json). The binary is
intentionally not stored in Git. The manager validates platform selection,
official archive shape, hashes, member paths, staging, atomic promotion, and
rollback:

```bash
python3 scripts/manage_codexbar.py verify --fixture tests/fixtures/codexbar.synthetic.tar.gz
python3 scripts/manage_codexbar.py verify --archive ./download/CodexBarCLI.tar.gz --platform linux-x86_64
python3 scripts/manage_codexbar.py install --archive ./download/CodexBarCLI.tar.gz
python3 scripts/manage_codexbar.py verify
python3 scripts/manage_codexbar.py remove
```

See [`docs/install-linux-x86_64.md`](docs/install-linux-x86_64.md) for Linux
and WSL, and [`docs/install-macos.md`](docs/install-macos.md) for both Apple
Silicon and Intel Macs. WSL is treated as the Linux CLI path; it does not use
macOS `launchd`. The public core does not install a scheduler or launch a
model.

The first command is hermetic. A real download is never implicit; use the
explicit `--allow-network` option only when the pinned release is intentionally
being installed. The manager does not read, copy, or remove account files,
tokens, cookies, API keys, or other installations.

## Safety contract

- Provider sources are fixed to OAuth for Codex and Claude, and the public web
  adapter source for Grok with cookie and API-key overrides disabled.
- A stale, missing, malformed, or untrusted provider does not become a partial
  success.
- `automatic_launch=false` and `automatic_fallback=false` are invariant in
  every success and `HOLD` payload.
- The public core does not execute a model CLI or turn a policy label into a
  command-line model identifier.
- The public release contains no collector binary, account snapshot, or secret.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests
python3 -B scripts/validate_public_manifest.py
python3 -B scripts/scan_public_release.py
python3 -B scripts/manage_codexbar.py verify --fixture tests/fixtures/codexbar.synthetic.tar.gz
```

The validation scripts are release checks, not a supply-chain certification.
See [`docs/release-checklist.md`](docs/release-checklist.md) and
[`docs/verification-handoff.md`](docs/verification-handoff.md).

## License

This project is MIT licensed. The collector is separately attributed under its
upstream MIT license; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
