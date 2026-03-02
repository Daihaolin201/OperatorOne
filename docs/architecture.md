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

- OperatorOne runs in dedicated profile: `operatorone` (Profile-B isolation).
- Each agent has an independent OpenClaw workspace under `workspaces/op1_*`.
- Each agent has an independent OpenClaw `agentDir` under `~/.openclaw-operatorone/agents/op1_*/agent`.
- Skill isolation model:
  - Agent-specific skills: `workspaces/op1_*/skills/*`
  - Cross-agent shared skills: `shared/skills/*`
- `skills.load.extraDirs` for `operatorone` profile is replaced to OperatorOne-only path(s) from manifest (default: `shared/skills`), preventing reuse of unrelated project skills.
- Default profile (without `--profile`) is not modified by normal OperatorOne sync.

## Workflow Contract

- Product -> Marketing -> Sales -> Operations
- Handoffs are structured JSON files in `handoffs/`.
- Cross-agent edits are only allowed in integration/release tasks.
