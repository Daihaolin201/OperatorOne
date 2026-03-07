# Stage1 Tracking Capability (Traffic / Signups / Revenue)

This directory contains the full Stage1 operations capability outputs.

## Run

```bash
cd workspaces/op1_operations
./scripts/run_stage1_tracking.sh
```

## Core outputs

- `raw_events.latest.jsonl` — canonical event log
- `identity_map.latest.json` — stitched identities
- `attribution_facts.latest.json` — attribution layer (opportunity/campaign/source)
- `funnel_daily.latest.json` — daily traffic/signup/paid funnel
- `revenue_mrr_daily.latest.json` — MRR movement rollup
- `channel_scoreboard.latest.json` — channel economics table
- `traffic_quality_report.latest.json`
- `signup_quality_daily.latest.json`
- `data_quality_report.latest.json`
- `alerts.latest.json`
- `stage1_scoreboard.latest.json` + `.md`
- `weekly_kpi_snapshot.latest.md`
- `reproducibility_report.latest.json` + `.md`

## Notes

- Current sales and traffic inputs are simulated/shadow signals.
- Adapters are externalized in `config/source_adapters.v1.json` for migration to live systems.
