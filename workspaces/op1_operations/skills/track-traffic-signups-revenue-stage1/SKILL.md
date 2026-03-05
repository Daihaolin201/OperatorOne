---
name: track-traffic-signups-revenue-stage1
description: Implement and operate Stage1 tracking for OperatorOne operations (traffic, signups, revenue). Use when asked to build, run, audit, or deliver this capability; bootstrap contracts/adapters; generate Stage1 scoreboards and weekly KPI snapshots; enforce data quality and reproducibility; or migrate from simulated signals to live analytics/billing sources.
---

# Track Traffic Signups Revenue Stage1

Run a deterministic Stage1 pipeline that produces auditable traffic/signup/revenue outputs.

## Execute

1. Locate OperatorOne repo root.
2. Bootstrap defaults (run at least once per workspace):
   - `python3 workspaces/op1_operations/skills/track-traffic-signups-revenue-stage1/scripts/bootstrap_stage1_contracts.py --repo-root /path/to/OperatorOne`
3. Run pipeline:
   - `python3 workspaces/op1_operations/skills/track-traffic-signups-revenue-stage1/scripts/run_stage1_tracking.py --repo-root /path/to/OperatorOne`
4. Confirm required outputs exist under `workspaces/op1_operations/research/stage1_tracking`:
   - `stage1_scoreboard.latest.json`
   - `stage1_scoreboard.latest.md`
   - `weekly_kpi_snapshot.latest.md`
   - `reproducibility_report.latest.json`
   - `run_stage1.latest.json`

If repo auto-detection fails, always pass `--repo-root` explicitly.

## Strict reproducibility

When reliability/audit is requested:

1. Set fixed time:
   - `export STAGE1_AS_OF="2026-03-05T12:00:00Z"`
2. Run strict mode:
   - `python3 workspaces/op1_operations/skills/track-traffic-signups-revenue-stage1/scripts/run_stage1_tracking.py --repo-root /path/to/OperatorOne --strict-repro`
3. Require all of:
   - `reproducibility_report.latest.json.status == "passed"`
   - `reproducibility_report.latest.json.strict_mode == true`
   - `reproducibility_report.latest.json.changed_files_vs_baseline` is empty

## Return format

When user asks for capability status, report:

1. Pipeline status (`passed`/`failed`)
2. Headline KPIs (`sessions`, `qualified_signups`, `paid_customers`, `net_new_mrr`)
3. Alerts count and top alerts
4. Reproducibility status
5. Explicit mode note: simulated vs live adapters

## Quality bar

- Keep metric formulas aligned to `contracts/metric_dictionary.v1.yaml`.
- Keep event schema aligned to `contracts/tracking_plan.v1.json`.
- Keep revenue movement logic aligned to `contracts/revenue_rules.v1.yaml`.
- Avoid silent source drift: update `config/source_adapters.v1.json` intentionally.
- Treat missing required outputs or failed reproducibility as failed delivery.

## References

- Read `references/workflow.md` for end-to-end run sequence.
- Read `references/data-contracts.md` when validating event/metric contracts.
- Read `references/live-migration.md` when replacing simulated adapters with live systems.
