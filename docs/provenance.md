# Provenance

[한국어판](ko/provenance.md)

The public project is a clean-room source export. The release set is defined
by its manifest, not by the contents of a developer working directory or by a
Git history.

The collector pin records its upstream release tag, source commit, per-platform
archive hashes, extracted executable hashes, and license path. The current
platform set is Linux/WSL x86_64, macOS arm64, and macOS x86_64. The public
policy and collector configuration are separately hashed at runtime. A
selected explicit policy hash identifies the bytes used for one run; it is not
a security certification or a public approval.

Synthetic fixtures are test inputs only. They do not represent a provider
account, a real quota window, or a live service result.
