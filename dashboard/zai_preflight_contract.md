# Z.AI GLM Preflight Gate Contract

Version: `1.0.0`  
Updated: `2026-03-07`  
Module: `dashboard/zai_preflight.py`

---

## 1. Purpose

This contract defines the mandatory pre-flight gate that MUST pass before any Z.AI GLM API call is made within the OperatorOne / CEOClaw system. The gate is a hard stop — failures raise an explicit exception and NEVER silently fall back to another model or provider.

---

## 2. Credential Injection

| Item | Detail |
|------|--------|
| Environment variable | `ZAI_API_KEY` |
| Injection method | Shell environment (e.g. `.env` file loaded before process start, or export in CI/CD) |
| Key format | Opaque string (provided by Z.AI platform) |
| Logging policy | **Key value MUST NOT appear in any log, stdout, or audit record** |

The preflight function checks for presence and non-emptiness only. It does NOT print, hash, truncate, or log the key value in any form.

---

## 3. Target Model & Provider

| Field | Value |
|-------|-------|
| `provider` | `z.ai` |
| `model` | `glm-4.5` |

These values are immutable constants in `zai_preflight.py`. They MUST NOT be overridden at call sites.

---

## 4. Failure Behaviour

- Failure mode: raise `ZAIPreflightError(field, reason)`
- **No silent fallback** — callers MUST NOT catch `ZAIPreflightError` and continue with `openai-codex/gpt-5.3-codex` or any other model
- Error message is diagnostic: it names the missing/invalid field and the reason
- Default model `openai-codex/gpt-5.3-codex` (from `openclaw/agents.manifest.json`) is for non-GLM paths only

Example error message:

```
ZAI preflight FAILED — field='ZAI_API_KEY': environment variable 'ZAI_API_KEY' is not set or is empty. MUST NOT silently fall back to another provider.
```

---

## 5. Preflight Steps

| Step name | Check performed | Real network call? |
|-----------|----------------|--------------------|
| `env_check` | `ZAI_API_KEY` present and non-empty | No |

Future steps (e.g. `connectivity_check`) may be added here and reflected in the audit schema.

---

## 6. Audit Record Schema

Each call to `check_zai_preflight()` returns one audit record. The schema (JSON Schema Draft-07):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ZAIPreflightAuditRecord",
  "type": "object",
  "required": ["provider", "model", "step", "latency_ms", "token_usage", "request_id"],
  "additionalProperties": false,
  "properties": {
    "provider": {
      "type": "string",
      "const": "z.ai",
      "description": "LLM provider identifier"
    },
    "model": {
      "type": "string",
      "const": "glm-4.5",
      "description": "Target model identifier"
    },
    "step": {
      "type": "string",
      "enum": ["env_check"],
      "description": "Preflight step that produced this record"
    },
    "latency_ms": {
      "type": "integer",
      "minimum": 0,
      "description": "Wall-clock duration of this preflight step in milliseconds"
    },
    "token_usage": {
      "type": ["null", "object"],
      "description": "Token usage statistics; null at preflight because no real API call is made"
    },
    "request_id": {
      "type": "string",
      "pattern": "^[0-9a-f]{32}$",
      "description": "UUID4 hex identifying this preflight invocation"
    }
  }
}
```

---

## 7. Integration Pattern

```python
from dashboard.zai_preflight import check_zai_preflight, ZAIPreflightError

audit = check_zai_preflight()
# store audit record in run log, then proceed with GLM call
```

Callers that need to gate a GLM step inside a stage action:

```python
try:
    audit = check_zai_preflight()
except ZAIPreflightError as exc:
    raise StudioError(f"GLM unavailable: {exc}") from exc
```

---

## 8. Invariants

1. `provider` is always `"z.ai"` — never changed at runtime.
2. `model` is always `"glm-4.5"` — never overridden.
3. `token_usage` is `null` during preflight (no network call).
4. `ZAIPreflightError` propagates unconditionally to the caller.
5. No key material appears in logs, stdout, audit records, or error messages.
