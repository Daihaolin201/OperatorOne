# Research Stage Index — op1_sales

Sales runs a 3-stage loop: **prospecting → outreach → conversion**.

## Canonical stage paths

### Stage1 — Identify prospects

- `research/prospecting/prospect_queue.latest.json`
- `research/prospecting/prospect_queue.latest.csv`
- `research/prospecting/prospect_queue.latest.md`

Optional summary output:

- `research/prospecting/top1_20_outreach.latest.md`

### Stage2 — Send outreach (approval-gated)

- `research/outreach/outreach_queue.latest.json`
- `research/outreach/outreach_queue.resolved.latest.json`
- `research/outreach/outreach_dispatch_report.latest.json`
- `research/outreach/outreach_dispatch_report.latest.md`
- `research/outreach/reply_processing_report.latest.md`

State + control artifacts:

- `research/outreach/contact_registry.latest.json`
- `research/outreach/outreach_batch.ready.json`
- `research/outreach/outreach_batch.approved.json`
- `research/outreach/suppression_list.latest.json`
- `research/outreach/outreach_events.latest.jsonl`
- `research/outreach/outreach_send_requests.latest.json`

### Stage3 — Convert early customers

- `research/conversion/conversion_pipeline.latest.json`
- `research/conversion/conversion_scoreboard.latest.json`
- `research/conversion/conversion_scoreboard.latest.md`
- `research/conversion/close_motion.latest.md`
- `research/conversion/pilot_onboarding.latest.json`
- `research/conversion/objection_playbook.latest.md`
- `research/conversion/reproducibility_report.latest.json`

Supporting artifacts:

- `research/conversion/conversion_events.latest.jsonl`
- `research/conversion/conversion_signal_processing.latest.json`
- `research/conversion/conversion_signal_inbox.latest.json`

## Handoff contract

Primary outbound handoff:

- `../../handoffs/sales_to_operations.json`

This handoff is updated from reply processing + conversion scoreboard pipelines.

## Notes

- Stage2 and Stage3 scripts often support `--mode simulate|commit`; only `commit` should update contracts/state.
- `*.latest.*` paths are canonical for dashboard/automation reads.
- If output paths or status semantics change, update this index + workspace README + docs/runbook together.