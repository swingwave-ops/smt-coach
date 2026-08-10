# 공개 배포

[English version](../public-distribution.md)

공개 artifact는 clean source release입니다. Python source, 엄격한 configuration, synthetic
fixture, tests, documentation, license file, collector pin metadata를 포함합니다. collector
binary, account snapshot, local cache, credential, 내부 실행 기록은 포함하지 않습니다.

## Release 경계

repository 또는 release action을 실행하기 전에:

1. public test suite를 실행합니다.
2. `validate_public_manifest.py`를 실행합니다.
3. `scan_public_release.py`를 실행합니다.
4. synthetic collector archive를 검증합니다.
5. file hash와 acceptance result를 freeze합니다.
6. freeze된 evidence에 대해 independent review를 받습니다.

source tree에는 public manifest 밖의 로컬 구현 기록이 있을 수 있습니다. 이는 release input이
아닙니다. release tooling은 allowlist된 public path만 package해야 하며 working tree에서 추가
파일을 추론해서는 안 됩니다.

실제 network download, collector installation, repository creation, commit, push, tag, visibility
변경, publication은 별도 action입니다. 이런 action을 하지 않고도 source release를 준비하고
검토할 수 있습니다.

