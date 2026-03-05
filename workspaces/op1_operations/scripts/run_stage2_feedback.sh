#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OPS_DIR="$ROOT_DIR/workspaces/op1_operations"
OUT_DIR="$OPS_DIR/research/stage2_feedback"
RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
RUN_REPORT="$OUT_DIR/run_stage2_${RUN_ID}.json"
LATEST_RUN_REPORT="$OUT_DIR/run_stage2.latest.json"

mkdir -p "$OUT_DIR"

python3 "$OPS_DIR/scripts/ingest_stage2_feedback.py" \
  --repo-root "$ROOT_DIR" \
  --adapters-config "workspaces/op1_operations/config/feedback_source_adapters.v1.json" \
  --out-dir "workspaces/op1_operations/research/stage2_feedback"

python3 "$OPS_DIR/scripts/normalize_stage2_feedback.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage2_feedback"

python3 "$OPS_DIR/scripts/cluster_stage2_feedback.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage2_feedback"

python3 "$OPS_DIR/scripts/score_stage2_feedback.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage2_feedback" \
  --weights "workspaces/op1_operations/config/feedback_priority_weights.v1.yaml" \
  --adapters-config "workspaces/op1_operations/config/feedback_source_adapters.v1.json"

python3 "$OPS_DIR/scripts/prioritize_stage2_feedback.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage2_feedback" \
  --weights "workspaces/op1_operations/config/feedback_priority_weights.v1.yaml" \
  --stage1-scoreboard "workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json" \
  --conversion-scoreboard "workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.json"

python3 "$OPS_DIR/scripts/build_stage2_feedback_scoreboard.py" \
  --repo-root "$ROOT_DIR" \
  --in-dir "workspaces/op1_operations/research/stage2_feedback" \
  --adapters-config "workspaces/op1_operations/config/feedback_source_adapters.v1.json" \
  --feedback-contract "workspaces/op1_operations/contracts/feedback_contract.v1.json" \
  --stage1-scoreboard "workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json"

BASELINE_FILE="$OUT_DIR/reproducibility_baseline.json"
VERIFY_ARGS=(
  --repo-root "$ROOT_DIR"
  --in-dir "workspaces/op1_operations/research/stage2_feedback"
  --baseline-file "workspaces/op1_operations/research/stage2_feedback/reproducibility_baseline.json"
)

if [[ ! -f "$BASELINE_FILE" ]]; then
  VERIFY_ARGS+=(--update-baseline)
fi

python3 "$OPS_DIR/scripts/verify_stage2_feedback_reproducibility.py" "${VERIFY_ARGS[@]}"

python3 - "$RUN_REPORT" "$LATEST_RUN_REPORT" <<'PY'
import datetime as dt
import json
import pathlib
import sys

run_report = pathlib.Path(sys.argv[1])
latest_run = pathlib.Path(sys.argv[2])
base = run_report.parent

now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
score = json.loads((base / "stage2_feedback_scoreboard.latest.json").read_text(encoding="utf-8"))
repro = json.loads((base / "reproducibility_report.latest.json").read_text(encoding="utf-8"))

payload = {
    "generated_at": now,
    "status": "passed" if repro.get("status") == "passed" else "failed",
    "pipeline": "stage2_feedback",
    "outputs": {
        "scoreboard_json": str(base / "stage2_feedback_scoreboard.latest.json"),
        "scoreboard_md": str(base / "stage2_feedback_scoreboard.latest.md"),
        "weekly_snapshot_md": str(base / "weekly_feedback_snapshot.latest.md"),
        "reproducibility_json": str(base / "reproducibility_report.latest.json"),
    },
    "headline": {
        "feedback_events_total": ((score.get("summary") or {}).get("feedback") or {}).get("feedback_events_total"),
        "feedback_items_total": ((score.get("summary") or {}).get("feedback") or {}).get("feedback_items_total"),
        "p0_count": ((score.get("summary") or {}).get("priority") or {}).get("p0_count"),
        "expected_mrr_delta_30d": ((score.get("summary") or {}).get("impact") or {}).get("expected_mrr_delta_30d"),
        "alerts_count": score.get("alerts_count"),
    },
}

run_report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
latest_run.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

echo "$OUT_DIR/stage2_feedback_scoreboard.latest.md"
