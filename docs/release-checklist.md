# Release checklist

## Local candidate

- [ ] public tests pass and the new count is recorded;
- [ ] public manifest is exact;
- [ ] no binary, local path, credential, account data, or internal record is in
  the release set;
- [ ] policy schema boundary and stable failure precedence pass;
- [ ] human, JSON, and exit-code parity pass;
- [ ] synthetic collector archive checks pass;
- [ ] v0.48.1 Linux/WSL and macOS platform pins and official archive shape pass;
- [ ] structured collector error fixtures preserve reason/kind/code;
- [ ] source and target hashes are frozen;
- [ ] independent verification is recorded.

## External release

These are not performed by the local candidate checks:

- [ ] representative confirms repository owner, name, and visibility;
- [ ] repository and remote are created only after that approval;
- [ ] first commit, push, tag, or release is explicitly authorized;
- [ ] any live download/install smoke is separately authorized;
- [ ] published claims distinguish source/test verification from live provider
  collection.
