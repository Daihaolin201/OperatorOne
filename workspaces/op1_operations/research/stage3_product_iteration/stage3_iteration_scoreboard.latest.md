# Stage3 Iteration Scoreboard (Iterate on product)

Generated at: 2026-03-06T00:18:09+00:00
Mode: simulated_signals

## Inputs
- top_feedback_queue_items: 15
- opportunities: 7
- stage1_net_new_mrr_baseline: 49.0
- stage2_expected_mrr_delta_30d: 77.101

## Iteration flow
- experiments_planned: 15
- running_candidates: 3
- rollout_completed: 1
- rollout_rollback: 0
- monitor_breaches: 0

## Outcomes
- ship: 2
- iterate: 10
- rollback: 0
- park: 3
- observed_mrr_delta_30d: 15.6691

## Delivery performance
- deployment_frequency_30d: 10
- lead_time_hours_avg: 0.0063
- change_failure_rate: 0.2308
- restore_time_hours_avg: 3.366

## Top experiment outcomes

| Experiment | Decision | Lift (pp) | MRR Δ30d | Rollout |
|---|---|---:|---:|---|
| exp3_cc6418573e5369 | ship | 0.015696 | 8.4262 | completed |
| exp3_c3a320476dbf99 | iterate | 0.006327 | 4.0759 | held |
| exp3_59cab733ebc263 | ship | 0.004916 | 3.167 | held |
| exp3_05035039912c10 | iterate | 0.0 | 0.0 | planned |
| exp3_c6b83944f78cc7 | iterate | 0.0 | 0.0 | planned |
| exp3_aff51f279f27df | iterate | 0.0 | 0.0 | planned |
| exp3_72c353fd9fdd32 | iterate | 0.0 | 0.0 | planned |
| exp3_6560f49deb814a | park | 0.0 | 0.0 | planned |
| exp3_299c70c714d04e | iterate | 0.0 | 0.0 | planned |
| exp3_bd55e0ff614989 | iterate | 0.0 | 0.0 | planned |
| exp3_368bdcc2cc5f04 | iterate | 0.0 | 0.0 | planned |
| exp3_4d927033157cf9 | park | 0.0 | 0.0 | planned |

## Alerts
- none
