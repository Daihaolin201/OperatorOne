# Stage3 Product Iteration Capability (Iterate on product)

This directory contains Stage3 outputs and run artifacts.

## Run

```bash
cd workspaces/op1_operations
./scripts/run_stage3_iteration.sh
```

For deterministic strict checks:

```bash
export STAGE3_AS_OF="2026-03-05T12:00:00Z"
./scripts/run_stage3_iteration.sh
```

## Core outputs

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
- `stage3_iteration_scoreboard.latest.json` + `.md`
- `weekly_iteration_snapshot.latest.md`
- `reproducibility_report.latest.json` + `.md`
- `run_stage3.latest.json`

## Notes

- Current operation mode uses Stage1/Stage2 simulated signals + product runtime artifacts.
- Live experiment integration can be added by wiring real feature flag/experiment adapters.
