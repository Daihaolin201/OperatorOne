<div align="center">

<img src="docs/assets/logo.png" alt="OperatorOne" height="60">

# Build Details — OperatorOne

**Branch** `dennis/automation-framework` &nbsp;·&nbsp; **Latest commit** `f8b5922` &nbsp;·&nbsp; **Date** 2026-03-07

[![Branch](https://img.shields.io/badge/branch-dennis%2Fautomation--framework-blue?style=flat-square)](https://github.com/Daihaolin201/OperatorOne)
[![Model](https://img.shields.io/badge/model-GLM--5-purple?style=flat-square)](https://z.ai)
[![Tests](https://img.shields.io/badge/tests-5%20passed-brightgreen?style=flat-square)](#tests--quality-gates)
[![Contracts](https://img.shields.io/badge/handoffs-9%20valid-yellow?style=flat-square)](#handoff-contracts)
[![MRR](https://img.shields.io/badge/MRR-%2449-brightgreen?style=flat-square)](#current-venture-kpis)

</div>

---

<div align="center">
<img src="docs/assets/hero.png" alt="OperatorOne × CEOClaw" width="100%">
</div>

---

## Table of Contents

0. [Judge Verification Checklist](#judge-verification-checklist)
1. [Repository Structure](#repository-structure)
2. [Monorepo & Toolchain](#monorepo--toolchain)
3. [Applications](#applications)
4. [Shared Packages](#shared-packages)
5. [Agent Architecture](#agent-architecture)
6. [Handoff Contracts](#handoff-contracts)
7. [Dashboard & Venture Studio](#dashboard--venture-studio)
8. [Z.AI / GLM-5 Integration](#zai--glm-5-integration)
9. [Tests & Quality Gates](#tests--quality-gates)
10. [CI Pipeline](#ci-pipeline)
11. [Deployed Products](#deployed-products)
12. [What Makes This Different](#what-makes-this-different)
13. [Hackathon Bounties](#hackathon-bounties)
14. [Commit History](#commit-history)

---

## Judge Verification Checklist

Use this checklist to verify all claims in under five minutes.

| Step | Command | Expected result |
|---|---|---|
| 1. Clone & checkout | `git clone https://github.com/Daihaolin201/OperatorOne && cd OperatorOne && git checkout dennis/automation-framework` | Branch checked out cleanly |
| 2. Run CEO orchestrator | `python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run` | 4-agent loop completes, artifacts written |
| 3. Read venture state | `cat workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json` | MRR $49, stage OPERATIONS, 6 deployed URLs |
| 4. Run preflight tests | `python3 -m pytest dashboard/tests/ -q` | 5 passed, GLM-5 confirmed |
| 5. Validate contracts | `python3 scripts/validate_handoffs.py --repo-root .` | 9 contracts valid |
| 6. Start dashboard | `python3 dashboard/server.py --host 127.0.0.1 --port 8765` | Dashboard at http://127.0.0.1:8765 |
| 7. View live products | Open any URL from the Deployed Products table | Landing page loads |

**Key artifacts to inspect:**

```
workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json   KPI proof
workspaces/op1_ceo/research/ceo_orchestration/approval.json               approval gate state
handoffs/*.json                                                             9 typed inter-agent contracts
dashboard/zai_preflight.py                                                 Z.AI compliance gate
workspaces/op1_ceo/AGENTS.md                                               CEO persona definition
```

---

## Repository Structure

```
OperatorOne/
├── apps/
│   ├── portal/              @op1/portal  — Venture dashboard (Next.js 15, port 3000)
│   └── product/             @op1/product — Product landing pages (Next.js 15, port 3001)
├── packages/
│   ├── ui/                  @op1/ui            — Shared React components
│   ├── types/               @op1/types         — Shared TypeScript types
│   ├── i18n/                @op1/i18n          — EN / ZH translation strings
│   ├── api-client/          @op1/api-client    — API client utilities
│   ├── config/              @op1/config        — ESLint / Tailwind / TS base configs
│   └── vitest-config/       @op1/vitest-config — Shared Vitest configuration
├── workspaces/
│   ├── op1_ceo/             CEO orchestrator scripts + KPI state artifacts
│   ├── op1_product/         Product agent workspace + research artifacts
│   ├── op1_marketing/       Marketing agent workspace + stage pipelines
│   ├── op1_sales/           Sales agent workspace + outreach pipeline
│   ├── op1_operations/      Operations agent workspace + feedback loop
│   └── op1_manager/         Cross-agent audit (not registered in manifest)
├── handoffs/                9 typed JSON inter-agent contracts
├── dashboard/               Python venture studio & monitor server (port 8765)
├── openclaw/                agents.manifest.json + profile config
├── official-site/           Static intro site (Vercel)
├── shared/                  Shared skills, prompts, templates
├── scripts/                 Handoff validation, upgrade, hygiene utilities
├── docs/                    Architecture, runbook, studio spec, audit reports
└── .github/workflows/       CI workflow definitions
```

---

## Monorepo & Toolchain

| Item | Value |
|---|---|
| Package manager | pnpm 10.30.3 |
| Build system | Turborepo 2.4.4 |
| Node.js | >= 20.0.0 |
| TypeScript | 5.8.2 |
| Prettier | 3.5.3 |

### Turbo Pipeline

| Task | Depends on | Outputs | Cache |
|---|---|---|---|
| `build` | `^build` | `.next/**`, `dist/**` | yes |
| `dev` | — | — | no (persistent) |
| `lint` | `^lint` | — | yes |
| `typecheck` | `^typecheck` | — | yes |
| `test` | `^build` | `coverage/**`, `coverage.json` | yes |
| `clean` | — | — | no |

### Root Scripts

```bash
pnpm build          # turbo run build — all packages in dependency order
pnpm dev            # all apps in parallel
pnpm dev:portal     # @op1/portal only (port 3000)
pnpm dev:product    # @op1/product only (port 3001)
pnpm lint           # turbo run lint
pnpm typecheck      # turbo run typecheck
pnpm test           # turbo run test
pnpm clean          # clean all .next / dist + node_modules
pnpm format         # prettier --write **/*.{ts,tsx,md,json}
```

---

## Applications

### `@op1/portal` — Venture Dashboard

| Attribute | Value |
|---|---|
| Framework | Next.js 15.2.2 (App Router) |
| Dev port | 3000 |
| i18n | next-intl 4.1.0 (EN / ZH) |
| Styling | Tailwind CSS 4 |
| Build output | `.next/` |

**Routes**

```
/[locale]/dashboard    Agent status, KPI monitor, handoff chain
/[locale]/ventures     Venture studio — stage execution and artifact view
/[locale]/agents       Agent registry view
```

---

### `@op1/product` — Product Landing Pages

| Attribute | Value |
|---|---|
| Framework | Next.js 15.2.2 (App Router) |
| Dev port | 3001 |
| i18n | next-intl 4.1.0 (EN / ZH) |
| Styling | Tailwind CSS 4 |
| Build output | `.next/` |

**Routes**

```
/[locale]/             Landing page
/[locale]/about        About
/[locale]/pricing      Pricing
```

---

## Shared Packages

| Package | Version | Description |
|---|---|---|
| `@op1/ui` | 0.0.0 | Shared React 19 components; ESM + CJS exports |
| `@op1/types` | 0.0.0 | Shared TypeScript type definitions |
| `@op1/i18n` | 1.0.0 | EN/ZH translation strings |
| `@op1/api-client` | 1.0.0 | API client with separate `./types` export path |
| `@op1/config` | — | ESLint, Tailwind, TypeScript base configurations |
| `@op1/vitest-config` | 0.0.0 | Vitest base + UI configs; Vitest + React Testing Library |

All packages use workspace-local references (`workspace:*`) and export via `./src/index.ts`.

---

## Agent Architecture

<div align="center">
<img src="docs/assets/pipeline.png" alt="Agent Pipeline" width="100%">
</div>

### CEO Orchestrator

```
Script   workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py
Model    GLM-5  (Z.AI, 744B MoE, 40B active, MIT license)
Loop     while mrr < target_mrr and cycle < max_cycles (default 3)
Stages   Product -> Marketing -> Sales -> Operations -> (iterate)
Gate     workspaces/op1_ceo/research/ceo_orchestration/approval.json
```

**Output artifacts**

| File | Contents |
|---|---|
| `run.latest.json` | Full 4-agent execution log with simulation replies |
| `venture_state.latest.json` | KPI snapshot (MRR, prospects, deployed URLs, gates, cycle) |
| `orchestrator_summary.latest.json` | Operator-facing summary |

**Quick start**

```bash
git clone https://github.com/Daihaolin201/OperatorOne
cd OperatorOne
git checkout dennis/automation-framework

# Single dry-run cycle
python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run

# Multi-cycle until target (max 5 attempts)
python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run --max-cycles 5

# Read state
cat workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json
```

---

### Agent Roster

| ID | Role | Workspace | Owner | In Manifest |
|---|---|---|---|---|
| `op1_product` | Product | `workspaces/op1_product` | Bennett | yes |
| `op1_marketing` | Marketing | `workspaces/op1_marketing` | Dennis | yes |
| `op1_sales` | Sales | `workspaces/op1_sales` | Dennis | yes |
| `op1_operations` | Operations | `workspaces/op1_operations` | Bennett | yes |
| `op1_manager` | Manager | `workspaces/op1_manager` | — | no |

**OpenClaw profile config** (`openclaw/agents.manifest.json`, version 1.1.0)

```
profile              operatorone
profileDefaultModel  openai-codex/gpt-5.3-codex
gatewayPort          30740
skillsExtraDirs      shared/skills
```

---

### Current Venture KPIs

Source: `venture_state.latest.json` · generated 2026-03-07

| Metric | Value |
|---|---|
| Venture ID | `venture_20260307_231817` |
| Goal | Reach first $100 MRR |
| Current MRR | **$49** |
| Cycle | 1 of max 3 |
| Stage | OPERATIONS (completed) |
| Prospects contacted | 13 |
| Replies received | 6 |
| Customers converted | 1 |
| Deployed products | 6 live Vercel URLs |
| `go_to_marketing` gate | true |
| `go_to_sales` gate | true |
| `go_to_operations` gate | true |
| Budget constraint | $200 max |
| Time constraint | 14 days |

---

## Handoff Contracts

9 typed JSON contracts, all at `contract_version: 1.0.0`.

```
handoffs/
├── product_to_marketing.json              Product -> Marketing
├── marketing_to_sales.json                Marketing -> Sales
├── sales_to_operations.json               Sales -> Operations
├── operations_to_product.json             Operations -> Product  (feedback)
├── operations_to_marketing.json           Operations -> Marketing (feedback)
├── operations_to_sales.json               Operations -> Sales    (feedback)
├── operations_to_product_iterate.json     Operations -> Product  (iterate)
├── operations_to_marketing_iterate.json   Operations -> Marketing (iterate)
└── operations_to_sales_iterate.json       Operations -> Sales    (iterate)
```

Each contract carries `contract_version`, `generated_at`, and `generated_by` metadata for full traceability.

**Validation**

```bash
python3 scripts/validate_handoffs.py --repo-root .
python3 scripts/upgrade_handoffs.py --repo-root .    # backfill missing metadata
```

---

## Dashboard & Venture Studio

```bash
python3 dashboard/server.py --host 127.0.0.1 --port 8765
# open http://127.0.0.1:8765
```

### API Surface

| Endpoint | Method | Description |
|---|---|---|
| `/api/studio/fast-snapshot` | GET | Lightweight studio state (recommended) |
| `/api/studio/snapshot` | GET | Full snapshot; optional `?includeMonitor=1` |
| `/api/studio/artifact` | GET | Read artifact by repo-relative path |
| `/api/studio/action` | POST | Trigger a stage action |
| `/api/studio/jobs` | GET | List running jobs |
| `/api/studio/jobs/<id>` | GET | Single job status |
| `/api/monitor/cached-snapshot` | GET | Monitor-only cached state |
| `/api/snapshot` | GET | Compatibility alias (cache-backed) |
| `/api/runtime-flags/manual-arm` | POST | Arm live-mode for high-risk actions |
| `/api/integrations/channel/connect` | POST | Connect integration channel |
| `/api/integrations/channel/disconnect` | POST | Disconnect integration channel |
| `/api/integrations/secrets/audit` | POST | Audit configured secrets |
| `/api/integrations/secrets/reload` | POST | Reload secrets |

### Runtime State Files

Location: `dashboard/.runtime/studio/`

| File | Contents |
|---|---|
| `state.json` | Venture states |
| `ventures.json` | Venture registry |
| `stage_runs.json` | Stage execution log |
| `decision_gates.json` | Decision gate records |
| `loop_todos.json` | Ops feedback items fed back to agents |
| `deployments.json` | Vercel deployment registry |
| `contexts/<venture>.json` | Per-venture context snapshot |

### Safety Boundaries

- Accessible on localhost only (`127.0.0.1`) by default
- High-risk actions (email send, Vercel deploy) require manual arm + explicit confirmation
- No arbitrary shell execution; all actions are whitelisted
- Live mode disabled by default; opt-in per action with `confirmLive=true`

---

## Z.AI / GLM-5 Integration

### Environment Configuration

```bash
export ZAI_API_BASE="https://api.z.ai/api/paas/v4"
export ZAI_MODEL="glm-5"
export ZAI_API_KEY="<your-key>"
```

### Preflight Gate

File: `dashboard/zai_preflight.py`

Misconfiguration raises `ZAIPreflightError` and halts. No silent fallback to any other provider.

```python
ZAI_PROVIDER = "z.ai"
ZAI_MODEL    = "glm-5"

# Audit record shape
{
  "provider":    str,   # always "z.ai"
  "model":       str,   # always "glm-5"
  "step":        str,   # e.g. "env_check"
  "latency_ms":  int,
  "token_usage": None,  # None at preflight (no real API call)
  "request_id":  str    # UUID4 hex
}
```

### GLM-5 Specifications

| Attribute | Value |
|---|---|
| Released | February 2026 (Z.AI / Zhipu AI) |
| Codename | Pony Alpha |
| Architecture | 744B total params, 40B active (MoE) |
| Training tokens | 28.5T |
| Context window | 202K tokens |
| RL framework | "Slime" async RL |
| Attention | DeepSeek Sparse Attention (DSA) |
| License | MIT (open weights) |
| Input pricing | $0.80 / M tokens |
| Output pricing | $2.56 / M tokens |

### Benchmark Results

| Benchmark | Score | Delta vs GLM-4.7 |
|---|---|---|
| SWE-bench Verified | **77.8%** | open weights #1 |
| Terminal-Bench-2.0 | **61.1%** | +28.3% |
| BrowseComp | **75.9%** | +8.4% |
| HLE with Tools | **50.4%** | +7.6% |
| AA Intelligence Index | **50** | open weights leading |

### Per-Agent Model Routing

| Agent | Task type | Model | Reason |
|---|---|---|---|
| `op1_product` | Code gen, Vercel deploy | glm-5 | SWE-bench 77.8% — top open-weights coding |
| `op1_marketing` | Content, SEO copy | glm-5 | 202K context, ultra-low hallucination |
| `op1_sales` | Outreach, dialogue | glm-5 | Native agent mode + Slime RL planning |
| `op1_operations` | KPI analysis, JSON | glm-5 | Structured output, BrowseComp 75.9% |
| CEO Orchestrator | Planning, routing | glm-5 | Terminal-Bench +28.3% |

---

## Tests & Quality Gates

### Python Test Suite

```bash
python3 -m pytest dashboard/tests/ -q
# 5 passed in 0.02s
```

| File | Tests | What is covered |
|---|---|---|
| `test_zai_preflight.py` | 3 | Preflight gate: valid key, missing key, empty key |
| `test_run_evidence_schema.py` | 2 | Run artifact index schema validation |

### Local Validation Scripts

```bash
python3 scripts/validate_handoffs.py --repo-root .     # validate all JSON contracts
python3 scripts/upgrade_handoffs.py --repo-root .      # backfill missing metadata fields
python3 scripts/change_hygiene_guard.py --staged       # pre-commit mixed-change guard
python3 scripts/reset_generated_artifacts.py --apply   # reset pipeline output artifacts
bash scripts/ci-local.sh                               # local equivalent of CI jobs
```

---

## CI Pipeline

**Workflows** (`.github/workflows/`)

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yml` | push / PR to `main` | lint, typecheck, test, contracts, hygiene |
| `handoff-contract-validation.yml` | push / PR | validate handoff JSON contracts |
| `change-hygiene.yml` | PR | mixed-change guard (`--allow-mixed` on PR) |

### CI Jobs

| Job | Runner | Timeout | Command |
|---|---|---|---|
| `lint` | ubuntu-latest | 10 min | `pnpm turbo run lint --affected` |
| `typecheck` | ubuntu-latest | 10 min | `pnpm turbo run typecheck --affected` |
| `test` | ubuntu-latest | 15 min | `pnpm turbo run test --affected` |
| `contracts` | ubuntu-latest | 5 min | `python3 scripts/validate_handoffs.py` |
| `hygiene` | ubuntu-latest | 5 min | `change_hygiene_guard.py --allow-mixed` (PR only) |

All Node.js jobs use Node 22, pnpm 10, frozen lockfile install.

**Pipeline flow:**

```
git push / PR
    ├── lint
    ├── typecheck
    ├── test
    └── contracts
              └── (all pass) → hygiene guard  [PR only]
```

---

## Deployed Products

| URL | Product | Opportunity |
|---|---|---|
| https://webproductmodularinvoice.vercel.app | Invoice follow-up tool | opp_001 |
| https://webproductmodularchargeback.vercel.app | Chargeback response ops | opp_001 |
| https://webproductmodularreporting.vercel.app | Client reporting module | opp_001 |
| https://webproductlandingstage3validation.vercel.app | Validation landing page | validation |
| https://webproductlandingstage3opp002.vercel.app | opp_002 landing page | opp_002 |
| https://webproductlandingstage3opp003.vercel.app | opp_003 landing page | opp_003 |
| https://official-site-theta.vercel.app | Official intro site | — |

---

## What Makes This Different

Most hackathon submissions demonstrate agent *capability*. OperatorOne demonstrates agent *output*.

| Dimension | Typical submission | OperatorOne |
|---|---|---|
| Scope | Single agent or demo | 4-agent CEO orchestrator with feedback loop |
| Evidence | Screenshot or mock data | $49 live MRR, 1 paying customer, 6 deployed URLs |
| State management | In-memory or none | 9 typed JSON contracts with version metadata |
| Human oversight | None or ad hoc | Approval gate controls all external actions |
| Model compliance | OpenAI fallback | GLM-5 exclusive, hard preflight gate, audit fields |
| Iteration | One shot | Multi-cycle loop re-runs until MRR target reached |
| Reproducibility | Run once | `--dry-run` mode, validated contracts, reset scripts |

Built under a $200 cash budget over 14 days. Every number in this document is sourced directly from `venture_state.latest.json`.

---

## Hackathon Bounties

| Bounty | Evidence | Verify |
|---|---|---|
| **CEOClaw Challenge** (£1,000) | `venture_state.latest.json` — $49 MRR, 6 deploys, 13 prospects | `python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run` |
| **Z.AI Gold Bounty** | `dashboard/zai_preflight.py` — all 5 roles use glm-5, no fallback | `python3 -m pytest dashboard/tests/ -q` |
| **Animoca Brands** | `workspaces/op1_ceo/AGENTS.md` + 9 JSON contracts with persistent state | `ls handoffs/*.json` |
| **Human for Claw** | `dashboard/` on port 8765 + `approval.json` gate | `python3 dashboard/server.py` |

---

## Commit History

| Hash | Message |
|---|---|
| `f8b5922` | redesign README with AI-generated visuals and cleaner layout |
| `f2434d2` | add multi-cycle loop to CEO orchestrator |
| `2d41bdb` | fix MRR progress bar percentage in README |
| `fc1fa8f` | enhance BUILD.md and clean bounty_map.svg |
| `067a157` | docs: rewrite README bilingual, add Mermaid diagrams and bounty map |
| `1cf9560` | fix(test): update expected model in preflight test to glm-5 |
| `d3ccb32` | fix: repair SVG escape sequences and upgrade preflight model to glm-5 |
| `5ca7a97` | docs: add SVG diagrams, upgrade to GLM-5, polish bilingual README |
| `e2efbc7` | 优化 |
| `3d0ac39` | docs: enhance README with Mermaid diagrams, Z.AI bounty section, and bounty coverage map |
| `e04d719` | chore(evidence): define run artifact index schema |
| `7061ea8` | fix(op1-product): align deploy url reader/writer compatibility |
| `a47920f` | feat(zai): add glm preflight contract and audit fields |
| `7a7de8b` | docs: rewrite README with bilingual EN/ZH support, default English |
| `ab33423` | feat(ceo): add hackathon demo script, dorahacks submission, fix orchestrator simulation |
| `ead1e95` | feat(ceo): polish orchestrator simulation, add hackathon README and demo script |
| `e066f49` | feat(ui): add one-click startup, platform/product workspace modes, and zh-en switch |
| `2d62375` | feat(dashboard): add opencode-style CEO flow visualization tab |
| `bb54170` | feat(ceo): add multi-agent orchestrator mode and dashboard trigger |
| `8ced819` | feat(studio): add CEO autopilot action and register op1_ceo workspace |
| `c8d18b7` | feat(op1_product): add CEO state machine, approval gate, and stage2 fallback retries |
| `e45e981` | feat(op1_product): add CEO autopilot v1 orchestration contract and runner |
| `aa916dc` | feat(studio): implement venture studio workflow across phase 0-4 |
| `794861d` | feat(dashboard): add OperatorOne multi-agent control dashboard |
| `decfdfd` | feat(operations): implement stage1-3 ops capabilities and package skills |
| `c4ac562` | op1_sales: finalize Stage1-3 capabilities and package reproducible skills |
| `97057ff` | feat(marketing): implement Stage3 launch-campaign orchestration and skill |
| `30c38a2` | feat(product): complete stage3 landing capability and add dedicated skill |
| `0b1ba73` | feat(op1_product): add reusable startup-idea framework and pipeline |
| `323186a` | feat: scaffold OperatorOne multi-agent framework and safe OpenClaw sync |
| `f7408c1` | Initial commit |

---

*Source of truth: `git log`, `package.json`, `turbo.json`, `openclaw/agents.manifest.json`, `venture_state.latest.json` · 2026-03-07*
