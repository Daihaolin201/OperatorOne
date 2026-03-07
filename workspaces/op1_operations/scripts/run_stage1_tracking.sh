#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OPS_DIR="$ROOT_DIR/workspaces/op1_operations"
OUT_DIR="$OPS_DIR/research/stage1_tracking"
RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
RUN_REPORT="$OUT_DIR/run_stage1_${RUN_ID}.json"
LATEST_RUN_REPORT="$OUT_DIR/run_stage1.latest.json"

mkdir -p "$OUT_DIR"

python3 "$OPS_DIR/scripts/ingest_stage1_events.py" \
  --repo-root "$ROOT_DIR" \
  --adapters-config "workspaces/op1_operations/config/source_adapters.v1.json" \
  --out-dir "workspaces/op1_operations/research/stage1_tracking"

python3 "$OPS_DIR/scripts/build_stage1_metrics.py" \
  --repo-root "$ROOT_DIR" \
  --adapters-config "workspaces/op1_operations/config/source_adapters.v1.json" \
  --in-dir "workspaces/op1_operations/research/stage1_tracking"

BASELINE_FILE="$OUT_DIR/reproducibility_baseline.json"
VERIFY_ARGS=(
  --repo-root "$ROOT_DIR"
  --in-dir "workspaces/op1_operations/research/stage1_tracking"
  --baseline-file "workspaces/op1_operations/research/stage1_tracking/reproducibility_baseline.json"
)

if [[ ! -f "$BASELINE_FILE" ]]; then
  VERIFY_ARGS+=(--update-baseline)
fi

python3 "$OPS_DIR/scripts/verify_stage1_reproducibility.py" "${VERIFY_ARGS[@]}"

python3 - "$RUN_REPORT" "$LATEST_RUN_REPORT" <<'PY'
import datetime as dt
import json
import pathlib
import sys

run_report = pathlib.Path(sys.argv[1])
latest_run = pathlib.Path(sys.argv[2])

now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
base = run_report.parent

score = json.loads((base / "stage1_scoreboard.latest.json").read_text(encoding="utf-8"))
repro = json.loads((base / "reproducibility_report.latest.json").read_text(encoding="utf-8"))

payload = {
    "generated_at": now,
    "status": "passed" if repro.get("status") == "passed" else "failed",
    "pipeline": "stage1_tracking",
    "outputs": {
        "scoreboard_json": str(base / "stage1_scoreboard.latest.json"),
        "scoreboard_md": str(base / "stage1_scoreboard.latest.md"),
        "weekly_snapshot_md": str(base / "weekly_kpi_snapshot.latest.md"),
        "reproducibility_json": str(base / "reproducibility_report.latest.json"),
    },
    "headline": {
        "sessions": score.get("summary", {}).get("traffic", {}).get("sessions"),
        "qualified_signups": score.get("summary", {}).get("signups", {}).get("qualified_signups"),
        "paid_customers": score.get("summary", {}).get("signups", {}).get("paid_customers"),
        "net_new_mrr": score.get("summary", {}).get("revenue", {}).get("net_new_mrr"),
    },
}

run_report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
latest_run.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

echo "$OUT_DIR/stage1_scoreboard.latest.md"
