# 출처와 provenance

[English version](../provenance.md)

공개 project는 clean-room source export입니다. release set은 developer working directory나
Git history의 내용이 아니라 manifest로 정의됩니다.

## 의존성 경계

SMT Coach의 policy engine이 프로젝트 코드입니다. CodexBar CLI `v0.48.1`은 live
사용량 수집에만 필요한 외부 runtime dependency입니다. Fixture/JSON mode에는 설치된
collector가 필요하지 않습니다. CodexBar는 이 저장소에 번들된 SMT Coach skill이나
plugin이 아니라 제3자 CLI collector입니다.

collector pin에는 upstream release tag, source commit, platform별 archive hash, 추출 실행
파일 hash, license path가 기록됩니다. 현재 platform은 Linux/WSL x86_64, macOS arm64,
macOS x86_64입니다. 공개 policy와 collector configuration은 runtime에서 별도로 hash합니다.
명시적으로 선택한 policy hash는 한 번의 실행에 사용한 bytes를 식별하지만 security certification이나
public approval을 의미하지 않습니다.

Synthetic fixture는 테스트 입력일 뿐입니다. provider account, 실제 quota window, live service
결과를 나타내지 않습니다.

