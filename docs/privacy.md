# Privacy boundary

SMT Coach is a local read-only advisor. It receives normalized usage output
from the configured collector and prints a recommendation. It does not upload
usage data, inspect browser cookies, read API keys, or print OAuth tokens.

The child collector environment removes provider-home overrides, API-key
variables, proxy overrides, and alternate base URLs. The process uses the
current account's normal home directory and sets browser-cookie import off.

Explicit policy files are treated as untrusted local input. The engine checks
the final file component for symlinks, verifies regular-file ownership and
permissions, reads at most 1 MiB plus one byte, and hashes the same bytes that
are parsed. Errors do not echo paths, keys, values, or stack traces.

Fixture mode is the preferred way to test. Fixture data should be synthetic;
do not place account names, email addresses, quota receipts, or tokens in the
repository.
