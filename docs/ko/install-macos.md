# macOS 설치

[English version](../install-macos.md)

SMT Coach는 pin된 CodexBar CLI asset으로 macOS 14 이상을 지원합니다. Apple Silicon
(`macos-arm64`)과 Intel (`macos-x86_64`)을 모두 지원하며, platform manager는 맞는
asset을 선택하고 promotion 전에 archive SHA-256과 추출된 `CodexBarCLI` SHA-256을 검증합니다.

## 로컬 archive

Mac에서 맞는 pre-downloaded archive를 명시합니다.

```bash
python3 scripts/manage_codexbar.py install --archive ./CodexBarCLI.tar.gz
python3 scripts/manage_codexbar.py verify
```

다른 platform에서도 설치 없이 archive를 검증할 수 있습니다.

```bash
python3 scripts/manage_codexbar.py verify \
  --archive ./CodexBarCLI-v0.48.1-macos-arm64.tar.gz \
  --platform macos-arm64
```

공식 archive는 정확히 `CodexBarCLI`, 이를 가리키는 `codexbar`, `0.48.1`과 일치하는
`VERSION`을 포함해야 합니다. manager는 credential directory, browser cookie store,
API-key 환경 변수, 다른 CodexBar 설치를 읽지 않습니다.

## Pin된 HTTPS 다운로드

network 다운로드는 명시적으로만 허용됩니다.

```bash
python3 scripts/manage_codexbar.py install --allow-network
```

manager는 managed installation을 변경하기 전에 선택된 macOS archive를 검증합니다.
macOS Keychain/browser 권한은 CodexBar의 책임이며 SMT Coach가 요청하거나 설정하지 않습니다.

## Hosted runtime 검증

두 CLI architecture를 검증하기 위해 Mac을 직접 가지고 있을 필요는 없습니다. 공개 저장소는
GitHub-hosted `macos-14`(Apple Silicon arm64)와 `macos-15-intel`(Intel x86_64)에서
`.github/workflows/macos-runtime.yml`을 실행합니다. workflow는 pinned archive SHA/VERSION,
managed lifecycle, hermetic test suite를 검사하며 OAuth credential이나 live provider collection을
사용하지 않습니다.

## 선택적 스케줄링

공개 core는 LaunchAgent를 설치하거나 model을 실행하지 않습니다. 주기적인 statusline 또는
dashboard scheduling은 사용자가 소유하는 선택적 통합입니다.

