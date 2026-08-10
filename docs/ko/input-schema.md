# 입력 스키마

[English version](../input-schema.md)

각 provider fixture는 해당 provider에 대한 object 하나 또는 object 하나만 담은 array입니다.

```json
[
  {
    "provider": "codex",
    "source": "oauth",
    "usage": {
      "updatedAt": "2030-01-01T00:00:00Z",
      "primary": {
        "usedPercent": 20,
        "windowMinutes": 10080,
        "resetsAt": "2030-01-08T00:00:00Z"
      }
    }
  }
]
```

지원 provider 식별자는 `codex`, `claude`, `grok`입니다.

- Codex와 Claude는 `source: "oauth"`를 사용합니다.
- Grok은 collector adapter의 `source: "web"`를 받고 `grok-web`으로 정규화합니다. fixture에서 정규화된 값을 직접 써도 됩니다.
- `usedPercent`는 유한한 숫자이며 `0` 이상 `100` 이하여야 합니다.
- `windowMinutes` `300`은 `5h`, `10080`은 `7d`가 됩니다.
- `windowMinutes`가 없는 Grok usage row는 `credits` window가 됩니다.
- 잘못된 timestamp, 누락된 usage object, 잘못된 quota 숫자는 해당 provider를 unavailable로 만듭니다.
- collector 오류는 안정적인 `error` 사유로 반환됩니다. CodexBar가 구조화 오류 JSON을 내보내면 `error_kind`와 정수 `error_code`를 보존하며, diagnostic stderr가 구조화 provider 오류를 덮어쓰지 못합니다.

`--file` 인자는 `PROVIDER=PATH` 형식으로 반복 지정합니다. fixture mode는 설정되고
활성화된 모든 provider에 대해 파일을 정확히 하나씩 요구하며 다른 파일은 허용하지 않습니다.
fixture mode에서는 collector를 호출하지 않습니다.

