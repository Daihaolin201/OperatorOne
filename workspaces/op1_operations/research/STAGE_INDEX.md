# Research Stage Index — op1_operations

Operations runs a 3-stage loop: **tracking → feedback → iteration**.

## Canonical stage paths

### Stage1 — Track traffic, signups, revenue

- `research/stage1_tracking/run_stage1.latest.json`
- `research/stage1_tracking/stage1_scoreboard.latest.json`
- `research/stage1_tracking/stage1_scoreboard.latest.md`
- `research/stage1_tracking/weekly_kpi_snapshot.latest.md`
- `research/stage1_tracking/reproducibility_report.latest.json`

Supporting artifacts:

- `research/stage1_tracking/raw_events.latest.jsonl`
- `research/stage1_tracking/funnel_daily.latest.json`
- `research/stage1_tracking/revenue_mrr_daily.latest.json`
- `research/stage1_tracking/channel_scoreboard.latest.json`

### Stage2 — Process feedback

- `research/stage2_feedback/run_stage2.latest.json`
- `research/stage2_feedback/stage2_feedback_scoreboard.latest.json`
- `research/stage2_feedback/stage2_feedback_scoreboard.latest.md`
- `research/stage2_feedback/weekly_feedback_snapshot.latest.md`
- `research/stage2_feedback/reproducibility_report.latest.json`

Supporting artifacts:

- `research/stage2_feedback/feedback_priority_queue.latest.json`
- `research/stage2_feedback/impact_model.latest.json`
- `research/stage2_feedback/feedback_loop_status.latest.json`
- `research/stage2_feedback/theme_clusters.latest.json`

Stage2 outbound handoffs:

- `../../handoffs/operations_to_product.json`
- `../../handoffs/operations_to_marketing.json`
- `../../handoffs/operations_to_sales.json`

### Stage3 — Iterate on product

- `research/stage3_product_iteration/run_stage3.latest.json`
- `research/stage3_product_iteration/stage3_iteration_scoreboard.latest.json`
- `research/stage3_product_iteration/stage3_iteration_scoreboard.latest.md`
- `research/stage3_product_iteration/weekly_iteration_snapshot.latest.md`
- `research/stage3_product_iteration/reproducibility_report.latest.json`

Supporting artifacts:

- `research/stage3_product_iteration/iteration_inputs.latest.json`
- `research/stage3_product_iteration/experiment_backlog.latest.json`
- `research/stage3_product_iteration/rollout_log.latest.json`
- `research/stage3_product_iteration/iteration_decision_log.latest.json`
- `research/stage3_product_iteration/delivery_performance.latest.json`

Stage3 outbound iteration handoffs:

- `../../handoffs/operations_to_product_iterate.json`
- `../../handoffs/operations_to_marketing_iterate.json`
- `../../handoffs/operations_to_sales_iterate.json`

## Notes

- `*.latest.*` files are canonical for automation and dashboard consumption.
- Timestamped `run_stage*.json` snapshots are historical traces for replay/debug.
- When pipeline output paths change, update this index + workspace README + docs/runbook in the same PR.