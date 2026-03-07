# OperatorOne Architecture (v1.1)

## 1) System intent

OperatorOne is a multi-agent startup execution system that turns structured market signals into iterative go-to-market execution, optimized for:

- reproducible stage pipelines,
- explicit handoff contracts,
- measurable progress toward **$100 MRR**.

---

## 2) Topology

### 2.1 Specialist execution plane (manifest-synced)

1. **op1_product**
   - idea discovery
   - web product build/deploy
   - landing package + Product→Marketing handoff
2. **op1_marketing**
   - SEO/content/campaign stage pipeline
   - Marketing→Sales handoff updates
3. **op1_sales**
   - prospecting + outreach prep/dispatch
   - conversion pipeline
   - Sales→Operations KPI rollup
4. **op1_operations**
   - traffic/signup/revenue tracking (Stage1)
   - feedback processing + prioritization (Stage2)
   - product/marketing/sales iteration loop (Stage3)

### 2.2 Control plane (local workspace)

- **op1_manager** (not manifest-synced by default)
  - cross-agent audits
  - documentation coherence
  - orchestration support / review support

### 2.3 Supporting planes

- **Contracts plane**: `handoffs/*.json`, `workspaces/op1_operations/contracts/*`
- **Observability plane**: `workspaces/*/research/**/*.latest.*`, reproducibility reports
- **Dashboard plane**: `dashboard/` (monitor + studio workflows)

---

## 3) Execution graph

Primary chain:

`Product -> Marketing -> Sales -> Operations`

Contract files:

- Product → Marketing: `handoffs/product_to_marketing.json`
- Marketing → Sales: `handoffs/marketing_to_sales.json`
- Sales → Operations: `handoffs/sales_to_operations.json`
- Operations → Product/Marketing/Sales:
  - `handoffs/operations_to_product.json`
  - `handoffs/operations_to_marketing.json`
  - `handoffs/operations_to_sales.json`

Iteration loop contracts (Ops Stage3):

- `handoffs/operations_to_product_iterate.json`
- `handoffs/operations_to_marketing_iterate.json`
- `handoffs/operations_to_sales_iterate.json`

---

## 4) Stage architecture by domain

### Product

- Stage1/2: opportunity discovery + screening
- Stage2 (build/deploy): `research/stage2_web_product/*.latest.json`
- Stage3 (landing): `research/stage3_landing_launch/run.latest.json`

### Marketing

- Stage1 SEO: `research/stage1_marketing_seo/*`
- Stage2 content: `research/stage2_content_publish/*`
- Stage3 campaign: `research/stage3_campaign_launch/*`

### Sales

- Stage1 prospecting: `research/prospecting/*`
- Stage2 outreach: `research/outreach/*`
- Stage3 conversion: `research/conversion/*`

### Operations

- Stage1 tracking: `research/stage1_tracking/*`
- Stage2 feedback: `research/stage2_feedback/*`
- Stage3 iteration: `research/stage3_product_iteration/*`

---

## 5) Artifact conventions

1. **`*.latest.*`** = canonical latest snapshot for automation and dashboard reads.
2. **timestamped run files** = replay/debug history.
3. **Markdown + JSON dual outputs** are expected for human + machine consumption.
4. **Reproducibility reports** are first-class stage outputs, not optional extras.

---

## 6) Isolation and safety model

- Dedicated OpenClaw profile: `operatorone`
- Dedicated workspaces per specialist agent under `workspaces/op1_*`
- Manifest sync only for specialist agents; manager workspace is local control-plane by design
- Shared skills loaded from `shared/skills` into the `operatorone` profile
- Default profile remains isolated from OperatorOne sync actions

---

## 7) Invariants (must stay true)

1. **Contract-first handoffs**: cross-agent transfer must go through `handoffs/*.json`.
2. **Owner-bound edits**: each specialist primarily edits its own workspace; cross-domain edits are integration work.
3. **Stage reproducibility**: each stage keeps a reproducibility check/report.
4. **Docs parity**: command/path/contract changes require same-cycle docs updates.

For collaboration/merge policy see `docs/collaboration.md`; for operations commands see `docs/runbook.md`.