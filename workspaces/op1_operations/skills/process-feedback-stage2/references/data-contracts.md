# Data contracts (Stage2)

## Canonical feedback event fields

Required fields:
- `feedback_id`
- `feedback_time`
- `source_adapter`
- `source_system`
- `feedback_origin`
- `actor_id`
- `feedback_type`
- `topic`
- `subtopic`
- `journey_stage`
- `raw_text`
- `severity`
- `urgency`
- `sentiment`
- `sentiment_score`
- `evidence_weight`
- `confidence`

Enumerations:
- `feedback_type`: `bug|feature_request|objection|praise|confusion|churn_risk|pricing|other`
- `journey_stage`: `problem_discovery|signup_to_paid|post_purchase|unknown`

## Priority queue contract

Each queue row includes:
- `feedback_item_id`, `theme_id`, `topic`, `subtopic`
- `priority_tier`, `priority_score`
- `owner`, `owner_team`, `status`, `due_at`
- impact estimates (`expected_signup_delta_30d`, `expected_paid_delta_30d`, `expected_mrr_delta_30d`)

## Closed-loop status flow

`new -> triaged -> accepted -> planned -> shipped -> verified -> notified`

## Required output files

`workspaces/op1_operations/research/stage2_feedback/`:
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
- `stage2_feedback_scoreboard.latest.json`
- `stage2_feedback_scoreboard.latest.md`
- `weekly_feedback_snapshot.latest.md`
- `reproducibility_report.latest.json`
