# SMT Coach

[English README](README.md)

SMT Coach는 Codex, Claude, Grok의 사용량을 읽어 조언하는 읽기 전용 도구입니다.
정규화된 사용량 snapshot을 읽고 `OBSERVE`, `ALLOW`, 또는 안정적인 `HOLD` 사유를
반환합니다. 모델을 시작하거나 provider를 바꾸거나 hook을 설치하지 않으며 자동
fallback도 사용하지 않습니다.

기본 제공 policy는 상태 조회 전용입니다. 사용자가 `--policy`로 명시적인 policy
파일을 선택하기 전까지 action role은 비활성화되어 있습니다.

## 빠른 시작

```bash
python3 -I -S -B fit_coach.py --role status
python3 smt_coach.py --role status
./smt --role status
```

collector가 설치되어 있지 않으면 live mode는 불완전하거나 추정한 결과를 만들지
않고 `HOLD`로 종료합니다. 격리된 검사를 하려면 활성화된 각 provider에 fixture를
하나씩 지정합니다.

```bash
python3 -I -S -B fit_coach.py --role status \
  --file codex=tests/fixtures/codex.synthetic.json \
  --file claude=tests/fixtures/claude.synthetic.json \
  --file grok=tests/fixtures/grok.synthetic.json
```

정확한 engine JSON과 종료 코드가 필요하면 `smt_coach.py --json`을 사용합니다.
`HOLD`는 종료 코드 `20`, `OBSERVE`와 `ALLOW`는 `0`, 명령줄 오류는 `2`입니다.

## Policy와 입력

`config/smt-policy.json`은 기본 policy입니다. 세 공개 collector source를 활성화하지만
모든 action role은 비활성화합니다. 기본값이 아닌 policy는 반드시 명시적으로 선택해야
합니다.

```bash
python3 -I -S -B fit_coach.py --role plan \
  --policy ./config/presets/example-policy.json \
  --file codex=tests/fixtures/codex.synthetic.json \
  --file claude=tests/fixtures/claude.synthetic.json \
  --file grok=tests/fixtures/grok.synthetic.json
```

Policy 파일은 symlink를 따라가지 않는 경계에서 한 번 열고, 소유자·권한을 검사하며,
최대 1MiB+1바이트만 제한적으로 읽고, 유한한 JSON 숫자를 엄격히 검사합니다. 출력에는
선택된 경로와 원시 예외를 포함하지 않고 hash와 `default`/`explicit` 출처만 표시합니다.

Fixture는 각 provider에 대해 정확히 하나의 snapshot을 담은 JSON object 또는 array입니다.
snapshot에는 `provider`, `source`, `usage`, `updatedAt`, quota window가 들어갑니다.
자세한 형식은 [입력 스키마](docs/ko/input-schema.md)를 참고하세요.

## Collector

CodexBar `0.48.1`은 Linux/WSL x86_64, macOS Apple Silicon arm64, macOS Intel x86_64에
대해 pin되어 있습니다. 플랫폼별 release metadata와 추출 실행 파일 hash는
[`vendor/codexbar/PINNED.json`](vendor/codexbar/PINNED.json)에 기록되어 있습니다.
binary 자체는 Git에 저장하지 않습니다. manager는 플랫폼, 공식 archive 구조, hash,
member 경로, staging, 원자적 promotion, rollback을 검증합니다.

```bash
python3 scripts/manage_codexbar.py verify --fixture tests/fixtures/codexbar.synthetic.tar.gz
python3 scripts/manage_codexbar.py verify --archive ./download/CodexBarCLI.tar.gz --platform linux-x86_64
python3 scripts/manage_codexbar.py install --archive ./download/CodexBarCLI.tar.gz
python3 scripts/manage_codexbar.py verify
python3 scripts/manage_codexbar.py remove
```

[Linux/WSL 설치 문서](docs/ko/install-linux-x86_64.md)와 [macOS 설치 문서](docs/ko/install-macos.md)를
참고하세요. WSL은 Linux CLI 경로를 사용하며 macOS `launchd`를 사용하지 않습니다.
공개 core는 scheduler를 설치하거나 모델을 실행하지 않습니다.

첫 번째 명령은 hermetic 검사입니다. 실제 다운로드는 자동으로 일어나지 않으며,
pin된 release를 의도적으로 설치할 때만 `--allow-network`를 명시합니다. manager는
계정 파일, token, cookie, API key 또는 다른 설치를 읽거나 복사·삭제하지 않습니다.

공개 저장소에는 [macOS runtime workflow](.github/workflows/macos-runtime.yml)도 있습니다.
GitHub-hosted `macos-14`(Apple Silicon arm64)와 `macos-15-intel`(Intel)에서 pinned
archive, install/verify/version/remove lifecycle, hermetic test를 검증합니다.
OAuth credential이나 live provider 호출은 사용하지 않습니다.

## 안전 계약

- Codex와 Claude source는 OAuth, Grok source는 cookie/API key override를 끈 공개 web adapter로 고정합니다.
- stale·누락·malformed·신뢰할 수 없는 provider는 부분 성공으로 처리하지 않습니다.
- 모든 성공 및 `HOLD` payload에서 `automatic_launch=false`, `automatic_fallback=false`가 유지됩니다.
- 공개 core는 model CLI를 실행하거나 policy label을 명령줄 model identifier로 바꾸지 않습니다.
- 공개 release에는 collector binary, account snapshot, secret이 포함되지 않습니다.

## 검증

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests
python3 -B scripts/validate_public_manifest.py
python3 -B scripts/scan_public_release.py
python3 -B scripts/manage_codexbar.py verify --fixture tests/fixtures/codexbar.synthetic.tar.gz
```

검증 script는 release check이며 supply-chain 인증을 의미하지 않습니다. [release checklist](docs/ko/release-checklist.md)와
[verification handoff](docs/ko/verification-handoff.md)를 참고하세요.

## 라이선스

이 프로젝트는 MIT License입니다. collector도 upstream MIT License로 별도 고지하며
자세한 내용은 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)를 참고하세요.

