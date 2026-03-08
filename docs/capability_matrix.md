# Founder Capability Mapping & Challenge Matrix

This document maps OperatorOne's Product, Marketing, Sales, and Operations actions to the CEOClaw challenge requirements. It serves as a guide for judges to verify the "Added Founder Capabilities" introduced in this project compared to the baseline OpenClaw.

## Baseline vs. OperatorOne

| Feature | Baseline OpenClaw | OperatorOne (New) |
|---|---|---|
| **Orchestration** | Single agent / Manual script calls | **Multi-Agent CEO Orchestrator** with 9 JSON handoff contracts |
| **Stage Gating** | Implicit / No formal stages | **Explicit Stage-Gating** (IDEA -> PRODUCT -> MARKETING -> SALES -> OPERATIONS) |
| **Memory** | Session-based / Ephemeral | **Persistent Handoff Layer** (`handoffs/*.json`) preserving state across agents |
| **Human-in-Loop** | CLI only | **Studio Dashboard** with integrated "Prompt-first Copilot" and Approval Gates |
| **Auditability** | Log files | **Z.AI Preflight Guard** + Immutable Handoff Contracts + Decision Gates |

---

## Capability Matrix

| Domain | Capability | NEW? | Implementation File | Trigger Action / Command | Evidence Path |
|---|---|---|---|---|---|
| **Product** | Idea Discovery & Screening | Yes | `dashboard/studio.py` | `refresh_ideas` | `workspaces/op1_product/research/stage1_idea_discovery/opportunity_records.json` |
| **Product** | Automated MVP Build & Deploy | Yes | `dashboard/studio.py` | `run_product` | `workspaces/op1_product/research/stage3_product_build/landing_package.json` |
| **Marketing** | SEO Experimentation | Yes | `dashboard/studio.py` | `run_marketing_seo` | `workspaces/op1_marketing/research/stage2_seo_research/seo_targets.json` |
| **Marketing** | Content & Campaign Generation | Yes | `dashboard/studio.py` | `run_marketing_campaign` | `handoffs/marketing_to_sales.json` |
| **Sales** | Automated Prospecting | Yes | `dashboard/studio.py` | `run_sales_prospecting` | `workspaces/op1_sales/research/stage1_prospecting/lead_signals.json` |
| **Sales** | Outreach & Conversion Pipeline | Yes | `dashboard/studio.py` | `run_sales_conversion` | `handoffs/sales_to_operations.json` |
| **Operations** | KPI Tracking & Feedback | Yes | `dashboard/studio.py` | `run_operations_full` | `workspaces/op1_operations/research/stage1_kpi_tracking/kpi_snapshot.json` |
| **Operations** | Feedback Loop & Iteration | Yes | `dashboard/studio.py` | `writeback_operations` | `handoffs/operations_to_product_iterate.json` |

---

## Detailed Capability Breakdown

### 1. Product (Idea to MVP)
*   **Discovery**: The `op1_product` agent crawls and synthesizes market pain points into `opportunity_records.json`.
*   **Trigger**: Dashboard "Refresh Ideas" or `python3 dashboard/studio.py` (internal call).
*   **New**: Baseline OpenClaw does not have a formal idea discovery and weighted screening stage (Phase 1-2).

### 2. Marketing (SEO to Campaign)
*   **SEO Strategy**: Generates keywords and content maps based on the Product ICP.
*   **Trigger**: Dashboard "Run Marketing SEO".
*   **New**: Automated mapping of Product ICP to Marketing SEO targets via `product_to_marketing.json`.

### 3. Sales (Prospecting to MRR)
*   **Outreach**: Executes outreach scripts (simulated or live) and tracks replies.
*   **Trigger**: Dashboard "Dispatch Sales Outreach".
*   **New**: Real-time KPI tracking ($49 MRR) stored in `sales_to_operations.json`.

### 4. Operations (Feedback to Iteration)
*   **Loop Closure**: Triage objections and feedback, creating "Iterate" contracts for the next cycle.
*   **Trigger**: Dashboard "Writeback Operations".
*   **New**: The iteration loop (`operations_to_*_iterate.json`) is the core "CEO" capability that ensures the venture improves over time.

---

## Verification Guide for Judges

1. **Verify CEO Orchestration**:
   ```bash
   python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run
   ```
   *Assert: `workspaces/op1_ceo/research/ceo_orchestration/run.latest.json` is generated.*

2. **Verify Handoff Persistence**:
   ```bash
   ls -l handoffs/*.json
   ```
   *Assert: All 9 contracts exist and follow the version 1.0.0 schema.*

3. **Verify Z.AI Preflight**:
   ```bash
   python3 -m pytest dashboard/tests/ -q
   ```
   *Assert: Preflight tests pass (verifying the Z.AI hard gate).*
