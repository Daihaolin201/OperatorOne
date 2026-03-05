---
name: process-feedback-stage2
description: Implement and operate Stage2 Process feedback capability for OperatorOne. Use when asked to build, run, audit, or deliver feedback processing from ingestion through prioritization and closed-loop tracking; generate Stage2 feedback scoreboards/alerts/weekly snapshots; create operations_to_product/marketing/sales handoffs; enforce strict reproducibility; or migrate from simulated feedback adapters to live sources.
---

# Process Feedback Stage2

Run a deterministic Stage2 pipeline that turns raw feedback signals into prioritized actions and auditable outputs.

## Execute

1. Bootstrap defaults (run once per workspace or when resetting contracts/config):
   - `python3 workspaces/op1_operations/skills/process-feedback-stage2/scripts/bootstrap_stage2_feedback_contracts.py --repo-root /path/to/OperatorOne`
2. Run pipeline:
   - `python3 workspaces/op1_operations/skills/process-feedback-stage2/scripts/run_stage2_feedback.py --repo-root /path/to/OperatorOne`
3. Confirm required outputs exist under `workspaces/op1_operations/research/stage2_feedback`:
   - `stage2_feedback_scoreboard.latest.json`
   - `stage2_feedback_scoreboard.latest.md`
   - `weekly_feedback_snapshot.latest.md`
   - `reproducibility_report.latest.json`
   - `run_stage2.latest.json`

If repo auto-detection fails, pass `--repo-root` explicitly.

## Strict reproducibility

When reliability or delivery audit is required:

1. Set fixed timestamp:
   - `export STAGE2_AS_OF="2026-03-05T12:00:00Z"`
2. Run strict mode:
   - `python3 workspaces/op1_operations/skills/process-feedback-stage2/scripts/run_stage2_feedback.py --repo-root /path/to/OperatorOne --strict-repro`
3. Require all of:
   - `reproducibility_report.latest.json.status == "passed"`
   - `reproducibility_report.latest.json.strict_mode == true`
   - `reproducibility_report.latest.json.changed_files_vs_baseline` is empty

## Return format

When reporting status to user, include:

1. Pipeline status (`passed`/`failed`)
2. Headline metrics (`feedback_events_total`, `feedback_items_total`, `themes_total`, `expected_mrr_delta_30d`)
3. Alert status (count + top alert codes)
4. Closed-loop status (`triaged_rate`, `p0_untriaged`, `p0_unowned`)
5. Reproducibility status
6. Mode note (`simulated_signals` vs live adapters)

## Quality bar

- Keep contract alignment with `contracts/feedback_contract.v1.json`.
- Keep taxonomy alignment with `contracts/feedback_taxonomy.v1.yaml`.
- Keep weight logic alignment with `config/feedback_priority_weights.v1.yaml`.
- Treat missing required outputs or failed reproducibility as failed delivery.
- Treat unresolved critical alert as delivery risk.

## References

- Read `references/workflow.md` for full run sequence.
- Read `references/data-contracts.md` when validating schemas/outputs.
- Read `references/feedback_tagging_guide.md` when improving topic/subtopic coverage.
- Read `references/live-migration.md` when replacing simulated adapters with live sources.
