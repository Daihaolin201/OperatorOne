---
name: convert-early-customers-stage3
description: End-to-end Stage3 conversion execution for op1_sales. Use when asked to convert early customers, move leads from interest/discovery into pilot and paid start, generate close-motion playbooks, track pilot onboarding and TTFV, process conversion signals (commitment/paid/lost), produce conversion scoreboards, or run reproducible conversion audits.
---

# Convert Early Customers Stage3

Run a one-command Stage3 conversion workflow with reproducibility support.

## Primary run

Use commit mode for real state updates:

```bash
python3 workspaces/op1_sales/skills/convert-early-customers-stage3/scripts/run_convert_early_customers_stage3.py \
  --repo-root <repo_root> \
  --mode commit
```

## Reproducible run

Use a fixed timestamp for deterministic outputs:

```bash
python3 workspaces/op1_sales/skills/convert-early-customers-stage3/scripts/run_convert_early_customers_stage3.py \
  --repo-root <repo_root> \
  --mode simulate \
  --as-of 2026-03-05T00:00:00+00:00
```

## Reproducibility verification

```bash
python3 workspaces/op1_sales/skills/convert-early-customers-stage3/scripts/verify_reproducibility_stage3.py \
  --repo-root <repo_root> \
  --as-of 2026-03-05T00:00:00+00:00
```

## Quality rules

- Treat `conversion_events.latest.jsonl` as the primary state progression source.
- Require explicit stage history and next actions for every active lead.
- Keep objection handling evidence-based and update objection playbook from event data.
- Update `handoffs/sales_to_operations.json` only through commit-mode scoreboard rendering.
- Use simulate + fixed as-of timestamp for demos, audits, and reproducibility checks.

## References

- Read `references/workflow.md` for execution order and expected artifacts.
- Read `references/data-contracts.md` for input/output schema expectations.
- Read `references/reproducibility.md` before deterministic test/audit runs.
