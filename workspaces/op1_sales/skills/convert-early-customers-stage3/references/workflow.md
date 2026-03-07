# Stage3 Workflow (Convert Early Customers)

## Goal
Convert qualified early leads into paid starts with explicit evidence and repeatable operations.

## Single-command run

```bash
python3 workspaces/op1_sales/skills/convert-early-customers-stage3/scripts/run_convert_early_customers_stage3.py \
  --repo-root <repo_root> \
  --mode commit
```

## Reproducible simulate run (fixed time)

```bash
python3 workspaces/op1_sales/skills/convert-early-customers-stage3/scripts/run_convert_early_customers_stage3.py \
  --repo-root <repo_root> \
  --mode simulate \
  --as-of 2026-03-05T00:00:00+00:00
```

## Internal execution order
1. `process_conversion_events_stage3.py`
2. `build_conversion_pipeline_stage3.py`
3. `build_close_motion_stage3.py`
4. `track_pilot_onboarding_stage3.py`
5. `render_conversion_scoreboard_stage3.py`

## Expected outputs
- `workspaces/op1_sales/research/conversion/conversion_events.latest.jsonl`
- `workspaces/op1_sales/research/conversion/conversion_pipeline.latest.json`
- `workspaces/op1_sales/research/conversion/close_motion.latest.md`
- `workspaces/op1_sales/research/conversion/pilot_onboarding.latest.json`
- `workspaces/op1_sales/research/conversion/objection_playbook.latest.md`
- `workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.md`
- `handoffs/sales_to_operations.json` (commit mode)
