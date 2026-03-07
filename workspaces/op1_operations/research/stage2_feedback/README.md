# Stage2 Feedback Capability (Process feedback)

This folder contains outputs for Stage2 feedback processing.

## Run

```bash
cd workspaces/op1_operations
./scripts/run_stage2_feedback.sh
```

## Core outputs

- `raw_feedback_events.latest.jsonl`
- `feedback_ingest_report.latest.json`
- `feedback_normalized.latest.jsonl`
- `feedback_dedup.latest.json`
- `theme_clusters.latest.json`
- `feedback_scored.latest.jsonl`
- `feedback_priority_queue.latest.json`
- `feedback_loop_status.latest.json`
- `impact_model.latest.json`
- `insight_briefs.latest.md`
- `feedback_data_quality.latest.json`
- `feedback_alerts.latest.json`
- `stage2_feedback_scoreboard.latest.json` + `.md`
- `weekly_feedback_snapshot.latest.md`
- `reproducibility_report.latest.json` + `.md`

## Notes

- Current default sources are simulated sales/pipeline signals.
- Live source migration is supported through `config/feedback_source_adapters.v1.json`.
