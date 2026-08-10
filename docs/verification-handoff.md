# Verification handoff

This document is a template for an independent review of a frozen public
source tree. It is not an approval by itself.

## Frozen inputs

```text
target_root=<absolute path recorded outside the public artifact>
target_aggregate_sha256=<64 lowercase hex>
public_manifest_sha256=<64 lowercase hex>
source_mutation=0
network_calls=0
credential_reads=0
```

## Required checks

- public tests and their count;
- manifest allowlist and no-binary result;
- privacy/path/credential scan;
- policy boundary and stable failure taxonomy;
- JSON/human/exit parity;
- synthetic archive traversal, hash, atomicity, and rollback checks;
- `automatic_launch=false` and `automatic_fallback=false` on success and HOLD;
- known limits and claims that were not tested.

The verifier must be independent of the implementation context. A test pass is
not permission to create a repository, push a commit, download a live release,
or change provider credentials.
