# macOS installation

SMT Coach supports macOS 14+ through the pinned CodexBar CLI assets for both
Apple Silicon (`macos-arm64`) and Intel (`macos-x86_64`). The platform manager
selects the matching asset and validates its archive SHA-256 and extracted
`CodexBarCLI` SHA-256 before promotion.

## Local archive

On a Mac, provide the matching pre-downloaded archive explicitly:

```bash
python3 scripts/manage_codexbar.py install --archive ./CodexBarCLI.tar.gz
python3 scripts/manage_codexbar.py verify
```

An archive can be verified from another platform without installing it:

```bash
python3 scripts/manage_codexbar.py verify \
  --archive ./CodexBarCLI-v0.48.1-macos-arm64.tar.gz \
  --platform macos-arm64
```

The official archive must contain exactly `CodexBarCLI`, `codexbar` pointing to
`CodexBarCLI`, and `VERSION` matching `0.48.1`. No credential directory,
browser cookie store, API-key environment variable, or other CodexBar install
is read by the manager.

## Pinned HTTPS download

Network download remains explicit:

```bash
python3 scripts/manage_codexbar.py install --allow-network
```

The manager verifies the selected macOS archive before changing the managed
installation. macOS Keychain/browser permissions belong to CodexBar and are
not requested or configured by SMT Coach.

## Hosted runtime verification

You do not need a Mac to verify the two CLI architectures. The public repository
runs `.github/workflows/macos-runtime.yml` on GitHub-hosted `macos-14` (Apple
Silicon arm64) and `macos-15-intel` (Intel x86_64) runners. The workflow checks
the pinned archive SHA/VERSION, executes the managed lifecycle, and runs the
hermetic test suite. It intentionally does not use OAuth credentials or perform
live provider collection.

## Optional scheduling

The public core does not install a LaunchAgent or launch a model. Periodic
statusline or dashboard scheduling is an optional user-owned integration.
