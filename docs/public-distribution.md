# Public distribution

The public artifact is a clean source release. It contains Python source,
strict configuration, synthetic fixtures, tests, documentation, license files,
and collector pin metadata. It does not contain the collector binary, account
snapshots, local caches, credentials, or internal execution records.

## Release boundary

Before any repository or release action:

1. run the public test suite;
2. run `validate_public_manifest.py`;
3. run `scan_public_release.py`;
4. verify the synthetic collector archive;
5. freeze file hashes and the acceptance results;
6. obtain an independent review of that frozen evidence.

The source tree may contain local implementation records outside the public
manifest. They are not release inputs. Release tooling must package only the
allowlisted public paths and must not infer additional files from the working
tree.

Real network download, collector installation, repository creation, commit,
push, tags, visibility changes, and publication are separate actions. A source
release can be prepared and reviewed without performing any of them.
