# Release checklist

[English version](../release-checklist.md)

## 로컬 후보

- [ ] public test가 통과하고 count가 기록되었는가;
- [ ] public manifest가 정확한가;
- [ ] binary, local path, credential, account data, 내부 기록이 release set에 없는가;
- [ ] policy schema 경계와 안정적인 failure precedence가 통과했는가;
- [ ] human, JSON, exit-code parity가 통과했는가;
- [ ] synthetic collector archive 검사가 통과했는가;
- [ ] 의존성 경계에 CodexBar가 live 수집에만 필요하고 fixture/JSON mode에는
      필요하지 않다고 명시되어 있는가;
- [ ] v0.48.1 Linux/WSL·macOS platform pin과 공식 archive 구조가 통과했는가;
- [ ] macOS hosted workflow가 arm64(`macos-14`)와 Intel(`macos-15-intel`)에서 통과했는가;
- [ ] 구조화 collector error fixture가 reason/kind/code를 보존하는가;
- [ ] source와 target hash가 freeze되었는가;
- [ ] independent verification이 기록되었는가.

## 외부 release

다음 항목은 로컬 후보 검사에서 수행하지 않습니다.

- [ ] 대표가 repository owner, name, visibility를 확인했는가;
- [ ] 해당 승인 뒤에만 repository와 remote를 만들었는가;
- [ ] first commit, push, tag, release가 명시적으로 승인되었는가;
- [ ] live download/install smoke가 별도 승인되었는가;
- [ ] published claim에서 source/test verification과 live provider collection을 구분했는가.

