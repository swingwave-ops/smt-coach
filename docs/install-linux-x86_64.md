# Linux/WSL x86_64 installation

The supported Linux path is x86_64 with Python 3.11 or newer. This includes
Ubuntu under WSL. The Python code has no third-party package dependency.

WSL uses the Linux glibc CodexBar CLI asset. The platform manager detects WSL
as Linux and never attempts to use macOS `launchd` or a macOS binary.

## Local archive

For a hermetic or pre-downloaded installation, provide the archive explicitly:

```bash
python3 scripts/manage_codexbar.py install --archive ./CodexBarCLI.tar.gz
python3 scripts/manage_codexbar.py verify
```

Official CodexBar archives contain exactly `CodexBarCLI`, a `codexbar` symlink
to that executable, and a `VERSION` file. The manager rejects absolute paths,
parent-directory traversal, unexpected members, invalid links, oversized
members, archive version/hash mismatches, and extracted hash mismatches.
Existing verified installations are preserved.

## Pinned HTTPS download

The pin metadata contains the upstream HTTPS URL, archive SHA-256, extracted
SHA-256, release tag, and source commit. A network download is opt-in:

```bash
python3 scripts/manage_codexbar.py install --allow-network
```

The command verifies the downloaded archive before any managed path is changed.
No credential directory, provider CLI configuration, cookie store, or API-key
environment variable is read by the manager.

## Optional scheduling

The public core is a read-only CLI and does not install a scheduler. If a user
wants periodic status output under WSL, they may wire the CLI to their own
systemd user timer or cron policy; that is outside the release artifact.

## Removal

```bash
python3 scripts/manage_codexbar.py remove
```

Removal is limited to this repository's managed version directory and its
verified symlink. Other installations and account data are out of scope.
