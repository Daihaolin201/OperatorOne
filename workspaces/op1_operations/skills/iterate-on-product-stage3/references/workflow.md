# Stage3 workflow (Iterate on product)

## 1) Bootstrap defaults

Run once per workspace or whenever contracts/config need reset.

```bash
python3 workspaces/op1_operations/skills/iterate-on-product-stage3/scripts/bootstrap_stage3_iteration_defaults.py --repo-root /path/to/OperatorOne
```

Use `--force` to overwrite existing files.

## 2) Run Stage3 pipeline

```bash
python3 workspaces/op1_operations/skills/iterate-on-product-stage3/scripts/run_stage3_iteration.py --repo-root /path/to/OperatorOne
```

Execution order:
1. build iteration inputs
2. build opportunity solution tree
3. build experiment backlog + hypothesis registry
4. build variant specs
5. run rollout planner + monitor
6. evaluate experiments + decisions + learnings
7. build Stage3 scoreboard + alerts + weekly snapshot
8. verify reproducibility + write run report

## 3) Validate completion

Required files under `workspaces/op1_operations/research/stage3_product_iteration`:
- `stage3_iteration_scoreboard.latest.json`
- `stage3_iteration_scoreboard.latest.md`
- `weekly_iteration_snapshot.latest.md`
- `reproducibility_report.latest.json`
- `run_stage3.latest.json`

Required handoffs:
- `handoffs/operations_to_product_iterate.json`
- `handoffs/operations_to_marketing_iterate.json`
- `handoffs/operations_to_sales_iterate.json`

## 4) Strict deterministic rerun

```bash
export STAGE3_AS_OF="2026-03-05T12:00:00Z"
python3 workspaces/op1_operations/skills/iterate-on-product-stage3/scripts/run_stage3_iteration.py \
  --repo-root /path/to/OperatorOne \
  --strict-repro
```

Require strict pass with empty `changed_files_vs_baseline`.
