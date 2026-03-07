# op1_operations — Operations Agent

Operations owns the measurement + feedback + iteration loop of OperatorOne.

Core mission:

1. Track traffic/signups/revenue (Stage1)
2. Process and prioritize feedback (Stage2)
3. Drive experiment-based iteration and rollout decisions (Stage3)

## Stage pipelines

### Stage1 — Track traffic, signups, revenue

```bash
bash workspaces/op1_operations/scripts/run_stage1_tracking.sh
```

Key outputs:

- `research/stage1_tracking/stage1_scoreboard.latest.json`
- `research/stage1_tracking/stage1_scoreboard.latest.md`
- `research/stage1_tracking/run_stage1.latest.json`
- `research/stage1_tracking/reproducibility_report.latest.json`

### Stage2 — Process feedback

```bash
bash workspaces/op1_operations/scripts/run_stage2_feedback.sh
```

Key outputs:

- `research/stage2_feedback/stage2_feedback_scoreboard.latest.json`
- `research/stage2_feedback/stage2_feedback_scoreboard.latest.md`
- `research/stage2_feedback/feedback_priority_queue.latest.json`
- `research/stage2_feedback/impact_model.latest.json`
- `research/stage2_feedback/run_stage2.latest.json`
- `research/stage2_feedback/reproducibility_report.latest.json`

Stage2 handoffs produced:

- `../../handoffs/operations_to_product.json`
- `../../handoffs/operations_to_marketing.json`
- `../../handoffs/operations_to_sales.json`

### Stage3 — Iterate on product

```bash
bash workspaces/op1_operations/scripts/run_stage3_iteration.sh
```

Key outputs:

- `research/stage3_product_iteration/stage3_iteration_scoreboard.latest.json`
- `research/stage3_product_iteration/stage3_iteration_scoreboard.latest.md`
- `research/stage3_product_iteration/experiment_backlog.latest.json`
- `research/stage3_product_iteration/iteration_decision_log.latest.json`
- `research/stage3_product_iteration/run_stage3.latest.json`
- `research/stage3_product_iteration/reproducibility_report.latest.json`

Stage3 iteration handoffs produced:

- `../../handoffs/operations_to_product_iterate.json`
- `../../handoffs/operations_to_marketing_iterate.json`
- `../../handoffs/operations_to_sales_iterate.json`

## Contracts and configs

- Contracts: `contracts/`
  - `feedback_contract.v1.json`
  - `stage3_decision_policy.v1.json`
  - `stage3_experiment_contract.v1.json`
  - `metric_dictionary.v1.yaml`

- Configs: `config/`
  - `feedback_priority_weights.v1.yaml`
  - `stage3_iteration_weights.v1.yaml`
  - `stage3_metric_guardrails.v1.yaml`
  - `stage3_rollout_policy.v1.yaml`

## References

- Stage path index: `research/STAGE_INDEX.md`
- Stage README files:
  - `research/stage1_tracking/README.md`
  - `research/stage2_feedback/README.md`
  - `research/stage3_product_iteration/README.md`