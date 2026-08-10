# Input schema

Each provider fixture is a JSON object or an array with exactly one object for
that provider:

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

Supported provider identifiers are `codex`, `claude`, and `grok`.

- Codex and Claude use `source: "oauth"`.
- Grok accepts the collector adapter's `source: "web"` and normalizes it to
  `grok-web`; a fixture may use the normalized value directly.
- `usedPercent` is finite and must be between `0` and `100`.
- `windowMinutes` `300` becomes `5h`; `10080` becomes `7d`.
- A Grok usage row without `windowMinutes` becomes the `credits` window.
- An invalid timestamp, missing usage object, or invalid quota number makes the
  provider unavailable.
- A collector error is returned as a stable `error` reason. When CodexBar emits
  structured error JSON, `error_kind` and integer `error_code` are preserved;
  diagnostic stderr is never allowed to replace the structured provider error.

The `--file` argument is repeated as `PROVIDER=PATH`. Fixture mode requires an
exact set: one file for every configured and enabled provider, and no other
file. Fixture mode never invokes the collector.
