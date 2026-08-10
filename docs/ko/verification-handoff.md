# Verification handoff

[English version](../verification-handoff.md)

이 문서는 freeze된 public source tree의 independent review를 위한 template입니다. 그 자체로
approval을 의미하지 않습니다.

## Freeze된 입력

```text
target_root=<public artifact 밖에 기록한 절대 경로>
target_aggregate_sha256=<64자리 소문자 hex>
public_manifest_sha256=<64자리 소문자 hex>
source_mutation=0
network_calls=0
credential_reads=0
```

## 필수 검사

- public test와 count;
- manifest allowlist와 no-binary 결과;
- privacy/path/credential scan;
- policy boundary와 안정적인 failure taxonomy;
- JSON/human/exit parity;
- synthetic archive traversal, hash, atomicity, rollback 검사;
- 성공 및 HOLD에서 `automatic_launch=false`, `automatic_fallback=false`;
- 알려진 한계와 테스트하지 않은 claim.

검증자는 implementation context와 독립적이어야 합니다. 테스트 통과는 repository 생성, commit
push, live release 다운로드, provider credential 변경의 permission이 아닙니다.

