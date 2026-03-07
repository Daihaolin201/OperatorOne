# Data Contracts

## Inputs
- `workspaces/op1_sales/research/outreach/outreach_queue.resolved.latest.json` (preferred) or `outreach_queue.latest.json`
- `workspaces/op1_sales/research/outreach/outreach_events.latest.jsonl`
- `workspaces/op1_sales/research/conversion/conversion_signal_inbox.latest.json`
- `workspaces/op1_product/research/stage3_mvp_scope/project_blueprint.json`
- `workspaces/op1_product/research/build_deploy_v1/project_spec*.json`

## Core state model
Each lead in conversion pipeline includes:
- `current_stage`, `stage_history[]`
- `conversion_readiness_score`
- `champion_confidence`
- `next_best_action`, `next_action_due_at`
- `objections_open[]`, `objections_resolved[]`
- `value_evidence[]`

## Output files
- `conversion_events.latest.jsonl`
- `conversion_pipeline.latest.json` + `.md`
- `close_motion.latest.json` + `.md`
- `pilot_onboarding.latest.json` + `.md`
- `conversion_scoreboard.latest.json` + `.md`
- `objection_playbook.latest.md`
- `conversion_signal_processing.latest.json` + `.md`

## Notes
- `conversion_events.latest.jsonl` is append-only and deduplicated by `source_key`.
- `sales_to_operations.json` is updated only in commit mode.
