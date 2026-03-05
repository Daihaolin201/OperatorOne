# Stage3 data contracts

## Experiment contract

Source: `contracts/stage3_experiment_contract.v1.json`

Each experiment requires:
- `experiment_id`, `hypothesis_id`, `title`, `status`, `owner`, `priority_tier`
- `targeting`, `variant_plan`, `primary_metric`
- `guardrail_metrics`, `sample_target`, `minimum_runtime_days`
- `stop_rules`, `success_criteria`, `rollback_criteria`

## Decision policy

Source: `contracts/stage3_decision_policy.v1.json`

Decision precedence:
1. rollback
2. ship
3. iterate
4. park

## Required outputs

Under `workspaces/op1_operations/research/stage3_product_iteration`:
- `iteration_inputs.latest.json`
- `opportunity_solution_tree.latest.json`
- `hypothesis_registry.latest.jsonl`
- `experiment_backlog.latest.json`
- `experiment_contract_validation.latest.json`
- `iteration_portfolio.latest.json`
- `variant_specs.latest.json`
- `rollout_log.latest.json`
- `experiment_monitor.latest.json`
- `experiment_results.latest.json`
- `iteration_decision_log.latest.json`
- `learning_log.latest.md`
- `delivery_performance.latest.json`
- `iteration_alerts.latest.json`
- `stage3_iteration_scoreboard.latest.json`
- `stage3_iteration_scoreboard.latest.md`
- `weekly_iteration_snapshot.latest.md`
- `reproducibility_report.latest.json`

## Guardrail expectations

Default guardrails (config):
- unsubscribe_rate max delta pp = 0.01
- error_rate max delta pp = 0.03
- p95 latency max = 1200 ms
- data lag max = 24h
- SRM deviation max = 0.1
