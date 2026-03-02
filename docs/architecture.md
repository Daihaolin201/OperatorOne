# OperatorOne Architecture (v1)

OperatorOne uses **4 specialist OpenClaw agents**:

1. **op1_product**
   - Generate startup ideas
   - Define MVP scope
   - Produce landing-page requirements
2. **op1_marketing**
   - Run SEO/content/campaign experiments
3. **op1_sales**
   - Build prospect list
   - Run outreach
   - Convert early customers
4. **op1_operations**
   - Track traffic/signup/revenue
   - Process feedback
   - Drive iteration loop

## Isolation Rules

- Each agent has an independent OpenClaw workspace under `workspaces/op1_*`.
- Each agent has an independent OpenClaw `agentDir` under `~/.openclaw/agents/op1_*/agent`.
- Shared, reusable capability lives in `shared/` and is loaded via one extra skills path:
  - `shared/skills`

## Workflow Contract

- Product -> Marketing -> Sales -> Operations
- Handoffs are structured JSON files in `handoffs/`.
- Cross-agent edits are only allowed in integration/release tasks.
