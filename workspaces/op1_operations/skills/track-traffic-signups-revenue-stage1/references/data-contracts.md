# Data contracts

## Canonical event model

Every event in `raw_events.latest.jsonl` includes these required fields:

- `event_id`
- `event_name`
- `event_time`
- `event_count`
- `source_adapter`
- `distinct_id`

Recommended attribution fields:

- `first_user_source`
- `first_user_medium`
- `session_source`
- `session_medium`
- `event_source`
- `event_medium`
- `campaign_id`

Revenue fields:

- `revenue_delta_mrr`
- `mrr_movement_type` (`new_business|expansion|contraction|churn|reactivation`)

## Core metric contracts

- `sessions = SUM(event_count WHERE event_name=session_observed)`
- `qualified_signups = DISTINCT lead_id WHERE event_name=signup_qualified`
- `paid_customers = DISTINCT lead_id WHERE event_name=paid_started`
- `visit_to_signup_rate = qualified_signups / sessions`
- `signup_to_paid_rate = paid_customers / qualified_signups`
- `new_mrr = SUM(revenue_delta_mrr WHERE movement_type=new_business)`
- `net_new_mrr = new + expansion + reactivation - contraction - churn`

Canonical source of truth is `contracts/metric_dictionary.v1.yaml`.

## Output contracts

Pipeline output directory: `workspaces/op1_operations/research/stage1_tracking`

Required output files:

- `raw_events.latest.jsonl`
- `identity_map.latest.json`
- `attribution_facts.latest.json`
- `funnel_daily.latest.json`
- `revenue_mrr_daily.latest.json`
- `channel_scoreboard.latest.json`
- `traffic_quality_report.latest.json`
- `signup_quality_daily.latest.json`
- `data_quality_report.latest.json`
- `alerts.latest.json`
- `stage1_scoreboard.latest.json`
- `stage1_scoreboard.latest.md`
- `weekly_kpi_snapshot.latest.md`
- `reproducibility_report.latest.json`

## Quality thresholds (default)

From `config/source_adapters.v1.json`:

- `max_duplicate_rate = 0.01`
- `max_unattributed_traffic_rate = 0.05`
- `max_data_lag_hours = 48`
- `min_visit_to_signup_rate = 0.005`
- `min_signup_to_paid_rate = 0.03`
