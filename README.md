# OperatorOne × CEOClaw

> **UK AI Agent Hackathon EP4 × OpenClaw — CEOClaw Challenge submission**
> Built by Dennis & Bennett · Branch: `dennis/automation-framework`

**CEOClaw** is OperatorOne's multi-agent CEO orchestrator that autonomously coordinates 4 specialist agents — Product → Marketing → Sales → Operations — to run an internet business from idea to first customers.

---

## Real Results (Not a Demo — Actual Pipeline Execution)

| Metric | Value |
|---|---|
| Current MRR | **$49** (target: $100) |
| Prospects contacted | **13** |
| Replies received | **6** |
| Customers converted | **1** |
| Products deployed | **6 live Vercel URLs** |
| Campaigns prepared | **9** (3 launch_ready, 5 watchlist, 1 approved) |
| Content assets | **12** (3 approved, 9 review_ready) |
| Agent handoffs | **9 JSON contracts** |

---

## CEOClaw Quick Start (Judges: run this)

```bash
# Clone and enter repo
git clone https://github.com/Daihaolin201/OperatorOne
cd OperatorOne
git checkout dennis/automation-framework

# Run the CEO multi-agent orchestrator (simulation mode — no API keys needed)
python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run

# Inspect outputs
cat workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json
cat workspaces/op1_ceo/research/ceo_orchestration/run.latest.json
```

Output artifacts:
- `run.latest.json` — full 4-agent execution log with realistic simulation replies
- `venture_state.latest.json` — venture KPI snapshot (MRR, prospects, campaigns, deployed URLs)
- `orchestrator_summary.latest.json` — operator-facing summary

---

## How OperatorOne Extends OpenClaw

- **Stage-gated multi-agent loop**: Each specialist (Product/Marketing/Sales/Operations) hands off a JSON contract to the next stage — not isolated agent calls
- **Approval-gated external actions**: `approval.json` controls whether external actions (emails, deployments) are permitted; fully auditable
- **Real business execution**: Pipeline has been run end-to-end — 6 products deployed to Vercel, 13 prospects contacted, $49 MRR earned
- **Handoff contract schema**: 9 typed JSON contracts with `contract_version`, `generated_at`, `generated_by` metadata for traceability and reproducibility
- **Iteration loop**: Operations feedback (10 items, P2/P3 prioritised) feeds back to Product/Marketing/Sales for the next cycle
- **CEO orchestrator script**: `run_ceo_multi_agent_orchestrator_v1.py` runs the full 4-agent sequence, writes `venture_state.latest.json`, and enforces approval policy

---

## Live Deployed Products

| URL | Product |
|---|---|
| https://webproductmodularinvoice.vercel.app | Invoice follow-up tool |
| https://webproductmodularchargeback.vercel.app | Chargeback response ops |
| https://webproductmodularreporting.vercel.app | Client reporting module |
| https://webproductlandingstage3validation.vercel.app | Validation landing page |
| https://webproductlandingstage3opp002.vercel.app | opp_002 landing page |
| https://webproductlandingstage3opp003.vercel.app | opp_003 landing page |

---

## Architecture

```
CEO Orchestrator (run_ceo_multi_agent_orchestrator_v1.py)
  │
  ├─▶ op1_product  ──[product_to_marketing.json]──▶  op1_marketing
  │                                                          │
  │                                              [marketing_to_sales.json]
  │                                                          │
  │                                                   op1_sales
  │                                                          │
  │                                             [sales_to_operations.json]
  │                                                          │
  └─────────────────────────────────────────────── op1_operations
                                                             │
                                          [operations_to_product/marketing/sales.json]
                                                             │
                                                    (iteration loop)

Outputs: run.latest.json · venture_state.latest.json · orchestrator_summary.latest.json
```

---

## Demo Video

See `docs/demo_video_script.md` for the 5-10 min recording walkthrough.

---

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
