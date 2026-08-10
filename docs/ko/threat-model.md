# Threat model

[English version](../threat-model.md)

## 보호 대상

- provider usage snapshot;
- 로컬 policy 파일;
- managed collector 실행 파일;
- recommendation과 provenance hash.

## 위협과 통제

| 위협 | 통제 |
|---|---|
| policy symlink 또는 writable policy가 대체됨 | no-follow open, owner check, mode check, bounded single read |
| malformed number가 advisory 결과를 바꿈 | strict finite JSON과 범위 검증 |
| stale 또는 누락 provider가 healthy로 처리됨 | `OBSERVE`에는 설정된 모든 provider가 healthy여야 하며 action candidate에는 window가 필요 |
| archive가 managed directory 밖에 씀 | 정확한 공식 member set, traversal 검사, 안전한 symlink target, 수동 bytes read, staging |
| 손상된 실행 파일이 사용됨 | archive와 추출 실행 파일의 SHA-256 pin 및 정확한 symlink target |
| 사용자 credential이 실수로 복사됨 | manager는 credential path를 읽지 않고 하위 환경 override를 제거 |
| advisory가 조용히 execution으로 바뀜 | launch/fallback code가 없고 invariant output flag가 false |
| 공개 release에 로컬 자료가 포함됨 | release 전에 manifest와 text/privacy scan 실행 |

## 잔여 한계

지원 경로는 최종 policy component와 열린 inode를 검증합니다. parent-directory symlink resolution은
문서화된 platform 한계입니다. provider 측 인증과 upstream release process는 이 project 밖에
있습니다. 테스트 통과는 security audit이나 supply-chain attestation이 아닙니다.

