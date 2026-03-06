# OperatorOne Dashboard v1 - Architecture & Rationale

## Goal

Create a single operator dashboard that can:

1. Observe the 4-agent system end-to-end (Product/Marketing/Sales/Operations)
2. Show input/output chain (handoffs)
3. Decide if external contact is allowed (policy gate)
4. Provide controlled onboarding for social channels and API integrations

## Why this is reasonable

The repository already stores most critical state as structured artifacts (`run.latest.json`, `state.latest.json`, `handoffs/*.json`, reproducibility reports). This is enough to build a deterministic monitoring plane without waiting for additional infra.

## Industry patterns considered

- **LangSmith dashboards + automations**: prebuilt + custom monitoring and rule-driven actions
- **OpenTelemetry / Phoenix**: common telemetry language and low lock-in observability design
- **Grafana alerting & SRE dashboard practices**: decision-oriented dashboards, not vanity metrics
- **OPA (policy as code)**: explicit gate rules, auditable and evolvable
- **GitHub Environments (required reviewers)**: human approval gate for risky actions
- **Stripe idempotency pattern**: avoid duplicate external actions
- **Temporal/Prefect**: resilient workflow framing and retry mindset
- **OpenClaw security/secrets model**: avoid plaintext secret drift, rely on controlled secret lifecycle

## v1 scope

### A. Observation plane

- Unified snapshot API (`/api/snapshot`) built from:
  - 12 capability checks
  - handoff chain checks
  - OpenClaw runtime status/channels/secrets JSON endpoints
- Per-agent rollups and status cards

### B. Decision plane

- Policy file (`dashboard/config/readiness_policy.json`)
- Two-level gate:
  - **Demo Gate**: capability + core handoff completeness
  - **Live Gate**: demo + channels + secrets + security + manual arm
- Three-state output: `BLOCKED`, `REVIEW_REQUIRED`, `READY`

### C. Controlled action plane

- Allowlisted integration actions only:
  - channel connect/disconnect via `openclaw channels add/remove`
  - `secrets audit/reload`
- No arbitrary shell command endpoint
- Local audit log for sensitive actions (`dashboard/.runtime/audit.log.jsonl`)

### D. Integration registry

- API integration metadata registry (name, base URL, secretRef, owner agent, notes)
- Designed for governance/audit without storing plaintext secrets in dashboard state

## Security boundaries

- Dashboard is local-first (`127.0.0.1` default)
- Manual ARM switch required before moving to `READY` for live external contact
- Secrets are checked using OpenClaw CLI (`secrets audit`) rather than dashboard-local secret logic
- Commands are strictly allowlisted; no generic command runner

## Next upgrades (post-v1)

1. Reviewer-based approval workflow for high-risk actions
2. Idempotency keys and action replay protection for outbound actions
3. Event streaming (WebSocket) instead of polling snapshot API
4. Integration with `channels capabilities` for permission-intent diagnostics
5. Optional OPA/Rego policy backend for larger policy sets
