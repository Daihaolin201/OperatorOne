---
name: iterate-on-product-stage3
description: Design, run, and audit Stage3 Iterate on product capability for OperatorOne. Use when asked to convert Stage1 metrics and Stage2 feedback priorities into experiment backlogs, rollout plans, policy-driven decisions (ship/iterate/rollback/park), learning logs, and cross-team iteration handoffs; or when asked to bootstrap Stage3 contracts/config, enforce guardrails, and verify strict reproducibility.
---

# Iterate on Product Stage3

Run a deterministic Stage3 product-iteration operating loop from opportunity mapping to decision outputs.

## Bootstrap defaults

Run bootstrap before first run in a workspace, or whenever Stage3 contracts/config must be reset.

```bash
python3 workspaces/op1_operations/skills/iterate-on-product-stage3/scripts/bootstrap_stage3_iteration_defaults.py --repo-root /path/to/OperatorOne
```

Use `--force` to overwrite existing files.

## Run full Stage3 pipeline

```bash
python3 workspaces/op1_operations/skills/iterate-on-product-stage3/scripts/run_stage3_iteration.py --repo-root /path/to/OperatorOne
```

Pipeline flow:
1. Build standardized iteration inputs from Stage1/Stage2/Product artifacts.
2. Build opportunity-solution tree.
3. Build hypothesis registry and experiment backlog.
4. Build variant specs and rollout plan.
5. Evaluate experiment outcomes and apply decision policy.
6. Build Stage3 scoreboard, alerts, weekly snapshot.
7. Verify reproducibility and write run report.

## Validate completion

Require all outputs:
- `workspaces/op1_operations/research/stage3_product_iteration/stage3_iteration_scoreboard.latest.json`
- `workspaces/op1_operations/research/stage3_product_iteration/stage3_iteration_scoreboard.latest.md`
- `workspaces/op1_operations/research/stage3_product_iteration/weekly_iteration_snapshot.latest.md`
- `workspaces/op1_operations/research/stage3_product_iteration/reproducibility_report.latest.json`
- `workspaces/op1_operations/research/stage3_product_iteration/run_stage3.latest.json`

Require handoff outputs:
- `handoffs/operations_to_product_iterate.json`
- `handoffs/operations_to_marketing_iterate.json`
- `handoffs/operations_to_sales_iterate.json`

Treat missing required output as failed delivery.

## Enforce strict reproducibility

Use deterministic mode for delivery-quality checks:

```bash
export STAGE3_AS_OF="2026-03-05T12:00:00Z"
python3 workspaces/op1_operations/skills/iterate-on-product-stage3/scripts/run_stage3_iteration.py \
  --repo-root /path/to/OperatorOne \
  --strict-repro
```

Require:
- `reproducibility_report.latest.json.status == "passed"`
- `reproducibility_report.latest.json.strict_mode == true`
- `changed_files_vs_baseline` empty

## Report status consistently

When reporting Stage3 status, include:
1. pipeline status (`passed`/`failed`)
2. headline metrics (`experiments_planned`, `ship_count`, `rollback_count`, `observed_mrr_delta_30d`)
3. alert status (count and highest-severity codes)
4. delivery metrics (`deployment_frequency_30d`, `lead_time_hours_avg`, `change_failure_rate`)
5. reproducibility status
6. mode note (`simulated_signals` vs live adapters)

## Maintain quality bar

- Keep experiment schema aligned with `contracts/stage3_experiment_contract.v1.json`.
- Keep decision precedence aligned with `contracts/stage3_decision_policy.v1.json`.
- Keep guardrail thresholds aligned with `config/stage3_metric_guardrails.v1.yaml`.
- Keep rollout steps aligned with `config/stage3_rollout_policy.v1.yaml`.
- Keep scoring/portfolio settings aligned with `config/stage3_iteration_weights.v1.yaml`.
- Avoid changing formulas and source adapters in the same change unless explicitly requested.

## Use references intentionally

- Read `references/workflow.md` for full execution sequence.
- Read `references/data-contracts.md` when validating schema/output completeness.
- Read `references/live-migration.md` when replacing simulated adapters with live experiment events.
- Read `references/benchmark-principles.md` when assessing process quality against leading iteration patterns.
