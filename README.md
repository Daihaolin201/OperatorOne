# OperatorOne

Built by Dennis and Bennett.

OperatorOne is a multi-agent OpenClaw system for running a full startup execution loop:

**idea discovery → landing + demand generation → outreach + conversion → feedback-driven iteration**

Current north-star KPI: first **$100 MRR**.

---

## Agent topology

OperatorOne has **4 specialist execution agents** plus a **manager control-plane workspace**.

| Workspace | Role | In `openclaw/agents.manifest.json` | Primary responsibility |
|---|---|---:|---|
| `workspaces/op1_product` | Product | ✅ | Idea discovery, web product build/deploy, landing handoff |
| `workspaces/op1_marketing` | Marketing | ✅ | SEO/content/campaign pipeline |
| `workspaces/op1_sales` | Sales | ✅ | Prospecting, outreach, conversion |
| `workspaces/op1_operations` | Operations | ✅ | KPI tracking, feedback processing, iteration loop |
| `workspaces/op1_manager` | Manager (control plane) | ❌ | Cross-agent orchestration, audits, documentation hygiene |

> Sync scripts register the 4 specialist agents by default. `op1_manager` is intentionally kept as a local control-plane workspace.

---

## End-to-end flow

Primary chain:

1. `op1_product` writes `handoffs/product_to_marketing.json`
2. `op1_marketing` writes `handoffs/marketing_to_sales.json`
3. `op1_sales` writes `handoffs/sales_to_operations.json`
4. `op1_operations` writes:
   - `handoffs/operations_to_product.json`
   - `handoffs/operations_to_marketing.json`
   - `handoffs/operations_to_sales.json`

Iteration loop (Stage3 Ops):

- `handoffs/operations_to_product_iterate.json`
- `handoffs/operations_to_marketing_iterate.json`
- `handoffs/operations_to_sales_iterate.json`

See `handoffs/README.md` for contract details.

---

## Repository layout

- `openclaw/` — profile sync + safety scripts (`operatorone` profile)
- `workspaces/` — isolated agent workspaces and stage artifacts
- `handoffs/` — inter-agent JSON contracts
- `dashboard/` — local monitor + venture studio web app
- `official-site/` — OperatorOne official project introduction page (landing/login-style entry page)
- `shared/` — shared prompts/skills/templates
- `docs/` — architecture, collaboration protocol, runbook

---

## Quick start (local, profile isolation)

1. Clone into:
   - `~/.openclaw/workspace/OperatorOne`
2. Run safe sync:
   - `bash openclaw/sync-operatorone-safe.sh`
3. Verify profile and agents:
   - `openclaw --profile operatorone status`
   - `openclaw --profile operatorone agents list`
4. Start a fresh chat session (`/new`)

Advanced:

- Config-only sync (no service action): `bash openclaw/sync-openclaw.sh`
- Temporary dual-gateway mode: `bash openclaw/sync-operatorone-safe.sh --allow-dual-gateway`

---

## Z.AI (GLM) core integration

OperatorOne is configured to use **Z.AI GLM as the default core model path**:

- Primary: `zai/glm-4.6`
- Fallback: `openai-codex/gpt-5.3-codex` (safety fallback only)

### Secure setup (local only, never commit API keys)

```bash
export ZAI_API_KEY='YOUR_ZAI_KEY'
bash scripts/setup_zai_core.sh --profile operatorone --probe-all-agents
```

What this does:

1. Stores `ZAI_API_KEY` in the local `operatorone` profile config (outside repo runtime)
2. Sets default model to `zai/glm-4.6`
3. Syncs fallback list from `openclaw/agents.manifest.json`
4. Generates an integration verification report:
   - `docs/evidence/zai/core_integration_report.latest.json`

Manual verification (without probes):

```bash
python3 scripts/verify_zai_core_integration.py --repo-root . --profile operatorone
```

Strict runtime probe (temporarily disables fallbacks, then restores):

```bash
python3 scripts/verify_zai_core_integration.py \
  --repo-root . \
  --profile operatorone \
  --probe-all-agents \
  --probe-without-fallback
```

Troubleshooting:

- If you don’t see successful Z.AI completions in the Z.AI console, check probe reports for plan/limit errors (for example: `429 ... does not yet include access to GLM-5`).
- In that case, keep `zai/glm-4.6` as primary (or switch to another available GLM tier in your plan).
- The system will fall back to the safety model unless fallbacks are temporarily disabled for strict verification.

---

## Dashboard

Run local dashboard:

```bash
python3 dashboard/server.py --host 127.0.0.1 --port 8765
```

Open:

- <http://127.0.0.1:8765>

Details:

- `dashboard/README.md`
- `docs/studio_usage_guide.md`

---

## Official project introduction page

OperatorOne includes an official intro page in `official-site/`.

Purpose:
- Introduce the project clearly to collaborators, prospects, and new team members.
- Explain multi-agent capabilities, handoff loop, and value proposition on one page.

Local preview:

```bash
cd official-site
python3 -m http.server 4173
```

Open:
- <http://127.0.0.1:4173>

Current live URL:
- <https://official-site-theta.vercel.app>

---

## Workspace docs

- Product: `workspaces/op1_product/README.md`
- Marketing: `workspaces/op1_marketing/README.md`
- Sales: `workspaces/op1_sales/README.md`
- Operations: `workspaces/op1_operations/README.md`
- Manager: `workspaces/op1_manager/README.md`

---

## Project docs map

- Architecture: `docs/architecture.md`
- Collaboration protocol: `docs/collaboration.md`
- Ops runbook: `docs/runbook.md`
- Full doc index: `docs/README.md`

Contract validation helpers:

- `python3 scripts/validate_handoffs.py --repo-root .`
- `python3 scripts/upgrade_handoffs.py --repo-root .`

Change hygiene helpers:

- `python3 scripts/change_hygiene_guard.py --staged` (check staged set for mixed source+generated churn)
- `python3 scripts/reset_generated_artifacts.py` (dry-run noisy generated deltas)
- `python3 scripts/reset_generated_artifacts.py --apply` (restore noisy generated deltas)

---

## Note on generated artifacts

`workspaces/*/research/**` contains many `*.latest.*` and run snapshots that are intentionally machine-updated. When reviewing diffs, separate **code/docs/contract changes** from **pipeline output refreshes**.