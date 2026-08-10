# Threat model

## Assets

- provider usage snapshots;
- local policy files;
- the managed collector executable;
- the recommendation and its provenance hashes.

## Threats and controls

| Threat | Control |
|---|---|
| A policy symlink or writable policy is substituted | no-follow open, owner check, mode check, bounded single read |
| A malformed number changes an advisory result | strict finite JSON and range validation |
| A stale or missing provider is treated as healthy | all configured providers must be healthy for `OBSERVE`; action candidates require their windows |
| An archive writes outside the managed directory | exact official member set, traversal checks, safe symlink target, manual bytes read, staging |
| A corrupted executable is used | archive and extracted SHA-256 pins plus exact symlink target |
| A user credential is accidentally copied | no credential paths are read by the manager; child overrides are removed |
| An advisory silently becomes execution | no launch/fallback code; invariant output flags remain false |
| A public release contains local material | manifest and text/privacy scans run before release |

## Residual limits

The supported path validates the final policy component and its opened inode;
parent-directory symlink resolution is a documented platform limit. The
collector's provider-side authentication and upstream release process remain
outside this project. Passing tests is not a security audit or a supply-chain
attestation.
