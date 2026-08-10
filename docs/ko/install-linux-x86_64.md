# Linux/WSL x86_64 설치

[English version](../install-linux-x86_64.md)

지원 Linux 경로는 Python 3.11 이상을 사용하는 x86_64입니다. WSL의 Ubuntu도 포함됩니다.
Python code에는 third-party package 의존성이 없습니다.

WSL은 Linux glibc CodexBar CLI asset을 사용합니다. platform manager는 WSL을 Linux로
감지하며 macOS `launchd`나 macOS binary를 사용하지 않습니다.

## 로컬 archive

격리 검사 또는 미리 다운로드한 설치에서는 archive를 명시적으로 지정합니다.

```bash
python3 scripts/manage_codexbar.py install --archive ./CodexBarCLI.tar.gz
python3 scripts/manage_codexbar.py verify
```

공식 CodexBar archive는 정확히 `CodexBarCLI`, 해당 실행 파일을 가리키는 `codexbar`
symlink, `VERSION` 파일을 포함합니다. manager는 절대 경로, parent-directory traversal,
예상 밖 member, 잘못된 link, 과도하게 큰 member, archive version/hash 불일치, 추출 hash
불일치를 거부합니다. 이미 검증된 설치는 보존합니다.

## Pin된 HTTPS 다운로드

pin metadata에는 upstream HTTPS URL, archive SHA-256, 추출 SHA-256, release tag, source
commit이 들어 있습니다. network 다운로드는 opt-in입니다.

```bash
python3 scripts/manage_codexbar.py install --allow-network
```

명령은 managed path를 바꾸기 전에 다운로드한 archive를 검증합니다. manager는 credential
directory, provider CLI 설정, cookie store, API key 환경 변수를 읽지 않습니다.

## 선택적 스케줄링

공개 core는 읽기 전용 CLI이며 scheduler를 설치하지 않습니다. WSL에서 주기적인 상태
출력이 필요하면 사용자가 직접 systemd user timer 또는 cron policy에 연결할 수 있습니다.
이는 release artifact 범위 밖입니다.

## 제거

```bash
python3 scripts/manage_codexbar.py remove
```

제거 범위는 이 repository가 관리하는 version directory와 검증된 symlink로 한정됩니다.
다른 설치와 account data는 범위 밖입니다.

