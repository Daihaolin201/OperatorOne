# Stage1 workflow (traffic / signups / revenue)

## 1) Bootstrap contracts and adapter config

Run once per workspace, or whenever you need to reset to known-good defaults.

```bash
python3 workspaces/op1_operations/skills/track-traffic-signups-revenue-stage1/scripts/bootstrap_stage1_contracts.py --repo-root /path/to/OperatorOne
```

Use `--force` to overwrite existing files.

## 2) Run Stage1 pipeline

```bash
python3 workspaces/op1_operations/skills/track-traffic-signups-revenue-stage1/scripts/run_stage1_tracking.py --repo-root /path/to/OperatorOne
```

The runner executes in order:

1. `ingest_stage1_events.py`
2. `build_stage1_metrics.py`
3. `verify_stage1_reproducibility.py`
4. writes `run_stage1.latest.json`

## 3) Validate completion

Check these files:

- `workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json`
- `workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.md`
- `workspaces/op1_operations/research/stage1_tracking/weekly_kpi_snapshot.latest.md`
- `workspaces/op1_operations/research/stage1_tracking/reproducibility_report.latest.json`

A run is considered successful when:

- `run_stage1.latest.json.status == passed`
- `reproducibility_report.latest.json.status == passed`
- `stage1_scoreboard.latest.json.alerts_count` is reviewed (0 is ideal)

## 4) Deterministic rerun (strict reproducibility)

Use a fixed as-of timestamp and strict mode:

```bash
export STAGE1_AS_OF="2026-03-05T12:00:00Z"
python3 workspaces/op1_operations/skills/track-traffic-signups-revenue-stage1/scripts/run_stage1_tracking.py \
  --repo-root /path/to/OperatorOne \
  --strict-repro
```

If `changed_files_vs_baseline` is non-empty under strict mode, treat as reproducibility regression.

## 5) Input expectations

Default adapters read from:

- `workspaces/op1_marketing/research/stage3_campaign_launch/campaigns.queue.latest.json`
- `workspaces/op1_sales/research/outreach/outreach_events.latest.jsonl`
- `workspaces/op1_sales/research/conversion/conversion_events.latest.jsonl`
- `workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.json`

The default profile supports simulated/shadow signals and is migration-ready for live adapters.
