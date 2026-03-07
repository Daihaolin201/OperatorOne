#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OPS_DIR="$ROOT_DIR/workspaces/op1_operations"
OUT_DIR="$OPS_DIR/research/stage3_product_iteration"
RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
RUN_REPORT="$OUT_DIR/run_stage3_${RUN_ID}.json"
LATEST_RUN_REPORT="$OUT_DIR/run_stage3.latest.json"

mkdir -p "$OUT_DIR"

python3 "$OPS_DIR/scripts/build_stage3_iteration_inputs.py" \
  --repo-root "$ROOT_DIR" \
  --out-dir "workspaces/op1_operations/research/stage3_product_iteration" \
  --stage1-scoreboard "workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json" \
  --stage2-scoreboard "workspaces/op1_operations/research/stage2_feedback/stage2_feedback_scoreboard.latest.json" \
  --stage2-priority "workspaces/op1_operations/research/stage2_feedback/feedback_priority_queue.latest.json" \
  --stage2-impact "workspaces/op1_operations/research/stage2_feedback/impact_model.latest.json" \
  --stage2-loop "workspaces/op1_operations/research/stage2_feedback/feedback_loop_status.latest.json"

python3 "$OPS_DIR/scripts/build_opportunity_solution_tree.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage3_product_iteration"

python3 "$OPS_DIR/scripts/build_stage3_experiment_backlog.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage3_product_iteration" \
  --weights "workspaces/op1_operations/config/stage3_iteration_weights.v1.yaml" \
  --guardrails "workspaces/op1_operations/config/stage3_metric_guardrails.v1.yaml" \
  --decision-policy "workspaces/op1_operations/contracts/stage3_decision_policy.v1.json" \
  --experiment-contract "workspaces/op1_operations/contracts/stage3_experiment_contract.v1.json"

python3 "$OPS_DIR/scripts/build_stage3_variant_specs.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage3_product_iteration" \
  --product-run "workspaces/op1_product/research/stage2_web_product/run.latest.json"

python3 "$OPS_DIR/scripts/run_stage3_rollouts.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage3_product_iteration" \
  --rollout-policy "workspaces/op1_operations/config/stage3_rollout_policy.v1.yaml" \
  --guardrails "workspaces/op1_operations/config/stage3_metric_guardrails.v1.yaml"

python3 "$OPS_DIR/scripts/evaluate_stage3_experiments.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage3_product_iteration" \
  --decision-policy "workspaces/op1_operations/contracts/stage3_decision_policy.v1.json" \
  --product-state "workspaces/op1_product/research/stage2_web_product/state.latest.json"

python3 "$OPS_DIR/scripts/build_stage3_iteration_scoreboard.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage3_product_iteration" \
  --guardrails "workspaces/op1_operations/config/stage3_metric_guardrails.v1.yaml" \
  --stage1-scoreboard "workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json" \
  --stage2-scoreboard "workspaces/op1_operations/research/stage2_feedback/stage2_feedback_scoreboard.latest.json"

BASELINE_FILE="$OUT_DIR/reproducibility_baseline.json"
VERIFY_ARGS=(
  --repo-root "$ROOT_DIR"
  --in-dir "workspaces/op1_operations/research/stage3_product_iteration"
  --baseline-file "workspaces/op1_operations/research/stage3_product_iteration/reproducibility_baseline.json"
)

if [[ ! -f "$BASELINE_FILE" ]]; then
  VERIFY_ARGS+=(--update-baseline)
fi

python3 "$OPS_DIR/scripts/verify_stage3_reproducibility.py" "${VERIFY_ARGS[@]}"

python3 "$ROOT_DIR/scripts/validate_handoffs.py" \
  --repo-root "$ROOT_DIR" \
  --contracts operations_to_product_iterate,operations_to_marketing_iterate,operations_to_sales_iterate

python3 - "$RUN_REPORT" "$LATEST_RUN_REPORT" <<'PY'
import datetime as dt
import json
import pathlib
import sys

run_report = pathlib.Path(sys.argv[1])
latest_run = pathlib.Path(sys.argv[2])
base = run_report.parent

now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
score = json.loads((base / "stage3_iteration_scoreboard.latest.json").read_text(encoding="utf-8"))
repro = json.loads((base / "reproducibility_report.latest.json").read_text(encoding="utf-8"))

payload = {
    "generated_at": now,
    "status": "passed" if repro.get("status") == "passed" else "failed",
    "pipeline": "stage3_iteration",
    "outputs": {
        "scoreboard_json": str(base / "stage3_iteration_scoreboard.latest.json"),
        "scoreboard_md": str(base / "stage3_iteration_scoreboard.latest.md"),
        "weekly_snapshot_md": str(base / "weekly_iteration_snapshot.latest.md"),
        "reproducibility_json": str(base / "reproducibility_report.latest.json"),
    },
    "headline": {
        "experiments_planned": (((score.get("summary") or {}).get("flow") or {}).get("experiments_planned")),
        "ship_count": (((score.get("summary") or {}).get("outcomes") or {}).get("ship_count")),
        "rollback_count": (((score.get("summary") or {}).get("outcomes") or {}).get("rollback_count")),
        "observed_mrr_delta_30d": (((score.get("summary") or {}).get("outcomes") or {}).get("observed_mrr_delta_30d")),
        "alerts_count": score.get("alerts_count"),
    },
}

run_report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
latest_run.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

echo "$OUT_DIR/stage3_iteration_scoreboard.latest.md"
