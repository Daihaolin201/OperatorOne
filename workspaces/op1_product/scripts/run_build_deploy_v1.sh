#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE1_PATH="$ROOT_DIR/research/stage1_opportunity_records.json"
STAGE2_PATH="$ROOT_DIR/research/stage2_decision_log.json"
PROJECT_SPEC_PATH="$ROOT_DIR/research/build_deploy_v1/project_spec.json"
LEGACY_BLUEPRINT_PATH=""
APP_DIR="$ROOT_DIR/runtime/web_product_v1_app"
ARTIFACT_DIR="$ROOT_DIR/research/build_deploy_v1"
STATE_FILE="$ROOT_DIR/research/build_deploy_v1_state.json"
RUN_REPORT="$ROOT_DIR/research/build_deploy_v1_run.json"

ALLOW_SPEC_AUTOGEN="no"
ROLLBACK_ON_FAIL="yes"
RUN_PAGE_STRATEGY_TEST="yes"
OPP_ID=""
ADAPTER_ID=""
PAGE_PROFILE=""
DEPLOY_URL=""
PAGE_SPEC_PATH=""

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_build_deploy_v1.sh [options]

Options:
  --project-spec <path>      Path to project spec JSON (preferred)
  --page-spec <path>         Use an existing compiled page spec (skip compile step)
  --legacy-blueprint <path>  Use stage3 blueprint input (legacy mode)
  --opp-id <opportunity_id>  Opportunity id to build spec from (when autogen)
  --adapter <adapter_id>     Force adapter id when autogenerating spec
  --allow-spec-autogen       Allow generating project spec from stage1+stage2 when missing (default: disabled)
  --page-profile <id>        Force page layout profile id during page-spec compile
  --skip-page-strategy-test  Skip page strategy test stage
  --no-rollback              Disable auto rollback attempt on post-deploy failure
  --app-dir <path>           Override scaffold output app directory
  --artifact-dir <path>      Override artifact output directory
  --help                     Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-spec)
      PROJECT_SPEC_PATH="$2"
      shift 2
      ;;
    --page-spec)
      PAGE_SPEC_PATH="$2"
      shift 2
      ;;
    --legacy-blueprint)
      LEGACY_BLUEPRINT_PATH="$2"
      shift 2
      ;;
    --opp-id)
      OPP_ID="$2"
      shift 2
      ;;
    --adapter)
      ADAPTER_ID="$2"
      shift 2
      ;;
    --allow-spec-autogen)
      ALLOW_SPEC_AUTOGEN="yes"
      shift
      ;;
    --page-profile)
      PAGE_PROFILE="$2"
      shift 2
      ;;
    --skip-page-strategy-test)
      RUN_PAGE_STRATEGY_TEST="no"
      shift
      ;;
    --no-rollback)
      ROLLBACK_ON_FAIL="no"
      shift
      ;;
    --app-dir)
      APP_DIR="$2"
      shift 2
      ;;
    --artifact-dir)
      ARTIFACT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$ARTIFACT_DIR"
RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
SCAFFOLD_SUMMARY="$ARTIFACT_DIR/scaffold_${RUN_ID}.json"
PAGE_SPEC_COMPILE_REPORT="$ARTIFACT_DIR/page_spec_compile_${RUN_ID}.jsonl"
DEFAULT_PAGE_SPEC_PATH="$ARTIFACT_DIR/page_spec_${RUN_ID}.json"
if [[ -z "$PAGE_SPEC_PATH" ]]; then
  PAGE_SPEC_PATH="$DEFAULT_PAGE_SPEC_PATH"
fi
SMOKE_REPORT="$ARTIFACT_DIR/smoke_${RUN_ID}.json"
PAGE_STRATEGY_REPORT="$ARTIFACT_DIR/page_strategy_${RUN_ID}.json"
BUSINESS_REPORT="$ARTIFACT_DIR/business_${RUN_ID}.json"

append_event() {
  local step="$1"
  local status="$2"
  local note="$3"
  python3 - "$STATE_FILE" "$RUN_ID" "$step" "$status" "$note" <<'PY'
import datetime as dt
import json
import pathlib
import sys

state_path = pathlib.Path(sys.argv[1])
run_id = sys.argv[2]
step = sys.argv[3]
status = sys.argv[4]
note = sys.argv[5]
now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

if state_path.exists():
    data = json.loads(state_path.read_text(encoding="utf-8"))
else:
    data = {"events": []}

data["run_id"] = run_id
data["updated_at"] = now
data["last_status"] = status
data.setdefault("events", []).append({"at": now, "step": step, "status": status, "note": note})
state_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
}

CURRENT_STEP="init"

on_error() {
  append_event "$CURRENT_STEP" "failed" "Unexpected error at step: $CURRENT_STEP"

  if [[ "$ROLLBACK_ON_FAIL" == "yes" && -n "$DEPLOY_URL" ]]; then
    append_event "rollback" "in_progress" "Attempting rollback for deployment: $DEPLOY_URL"

    set +e
    rollback_output="$(cd "$APP_DIR" && vercel rollback 2>&1)"
    rollback_code=$?

    if [[ $rollback_code -ne 0 ]]; then
      rollback_output_fallback="$(cd "$APP_DIR" && vercel rollback "$DEPLOY_URL" 2>&1)"
      rollback_code=$?
      rollback_output="$rollback_output\n--- fallback ---\n$rollback_output_fallback"
    fi
    set -e

    if [[ $rollback_code -eq 0 ]]; then
      append_event "rollback" "done" "Rollback command succeeded"
    else
      append_event "rollback" "failed" "Rollback command failed: $rollback_output"
    fi
  fi
}

trap 'on_error' ERR

append_event "run_start" "in_progress" "Build & deploy v1.1 pipeline started"

PROJECT_SPEC_PATH="$(python3 - "$PROJECT_SPEC_PATH" <<'PY'
import pathlib
import sys
print(pathlib.Path(sys.argv[1]).resolve())
PY
)"

PAGE_SPEC_PATH="$(python3 - "$PAGE_SPEC_PATH" <<'PY'
import pathlib
import sys
print(pathlib.Path(sys.argv[1]).resolve())
PY
)"

CURRENT_STEP="project_spec"
append_event "$CURRENT_STEP" "in_progress" "Resolving project spec"

if [[ -n "$LEGACY_BLUEPRINT_PATH" ]]; then
  append_event "$CURRENT_STEP" "done" "Legacy blueprint mode enabled"
else
  if [[ ! -f "$PROJECT_SPEC_PATH" ]]; then
    if [[ "$ALLOW_SPEC_AUTOGEN" != "yes" ]]; then
      echo "Project spec not found and autogen disabled: $PROJECT_SPEC_PATH" >&2
      exit 4
    fi

    SPEC_CMD=(
      python3 "$ROOT_DIR/scripts/init_project_spec.py"
      --stage1 "$STAGE1_PATH"
      --stage2 "$STAGE2_PATH"
      --out "$PROJECT_SPEC_PATH"
      --force
    )

    if [[ -n "$OPP_ID" ]]; then
      SPEC_CMD+=(--opp-id "$OPP_ID")
    fi
    if [[ -n "$ADAPTER_ID" ]]; then
      SPEC_CMD+=(--adapter "$ADAPTER_ID")
    fi

    "${SPEC_CMD[@]}" >"$ARTIFACT_DIR/project_spec_${RUN_ID}.jsonl"
    append_event "$CURRENT_STEP" "done" "Project spec autogenerated at $PROJECT_SPEC_PATH"
  else
    append_event "$CURRENT_STEP" "done" "Using existing project spec at $PROJECT_SPEC_PATH"
  fi
fi

if [[ -z "$LEGACY_BLUEPRINT_PATH" ]]; then
  CURRENT_STEP="page_spec"

  if [[ "$PAGE_SPEC_PATH" != "$DEFAULT_PAGE_SPEC_PATH" ]]; then
    append_event "$CURRENT_STEP" "in_progress" "Using provided page spec"
    if [[ ! -f "$PAGE_SPEC_PATH" ]]; then
      echo "Provided page spec not found: $PAGE_SPEC_PATH" >&2
      exit 5
    fi
    append_event "$CURRENT_STEP" "done" "Using provided page spec at $PAGE_SPEC_PATH"
  else
    append_event "$CURRENT_STEP" "in_progress" "Compiling modular page spec"

    PAGE_SPEC_CMD=(
      python3 "$ROOT_DIR/scripts/compile_page_spec.py"
      --project-spec "$PROJECT_SPEC_PATH"
      --out "$PAGE_SPEC_PATH"
      --force
    )

    if [[ -n "$PAGE_PROFILE" ]]; then
      PAGE_SPEC_CMD+=(--profile "$PAGE_PROFILE")
    fi

    "${PAGE_SPEC_CMD[@]}" >"$PAGE_SPEC_COMPILE_REPORT"
    append_event "$CURRENT_STEP" "done" "Page spec compiled at $PAGE_SPEC_PATH"
  fi
fi

CURRENT_STEP="scaffold"
append_event "$CURRENT_STEP" "in_progress" "Scaffolding app"

if [[ -n "$LEGACY_BLUEPRINT_PATH" ]]; then
  python3 "$ROOT_DIR/scripts/scaffold_web_product.py" \
    --blueprint "$LEGACY_BLUEPRINT_PATH" \
    --out-dir "$APP_DIR" \
    --summary-out "$SCAFFOLD_SUMMARY" \
    --force
else
  python3 "$ROOT_DIR/scripts/scaffold_web_product.py" \
    --project-spec "$PROJECT_SPEC_PATH" \
    --page-spec "$PAGE_SPEC_PATH" \
    --out-dir "$APP_DIR" \
    --summary-out "$SCAFFOLD_SUMMARY" \
    --force
fi
append_event "$CURRENT_STEP" "done" "App scaffolded at $APP_DIR"

if [[ -n "$LEGACY_BLUEPRINT_PATH" ]]; then
  PAGE_SPEC_PATH="$APP_DIR/page_spec.snapshot.json"
fi

CURRENT_STEP="deploy"
append_event "$CURRENT_STEP" "in_progress" "Deploying to Vercel"
DEPLOY_URL="$($ROOT_DIR/scripts/deploy_web_product.sh --app-dir "$APP_DIR" --log-dir "$ARTIFACT_DIR" --target production)"
append_event "$CURRENT_STEP" "done" "Deployment URL: $DEPLOY_URL"

CURRENT_STEP="deployment_health_gate"
append_event "$CURRENT_STEP" "in_progress" "Validating deployment health endpoint"
python3 - "$DEPLOY_URL" <<'PY'
import json
import sys
import time
import urllib.request

base = sys.argv[1].rstrip("/")
url = f"{base}/api/health"
last = None
for _ in range(8):
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            if int(resp.status) == 200 and data.get("status") == "ok":
                print("health_gate_pass")
                raise SystemExit(0)
            last = f"unexpected payload: status={resp.status}, body={body[:300]}"
    except Exception as exc:
        last = str(exc)
    time.sleep(2.5)

raise SystemExit(f"Health gate failed: {last}")
PY
append_event "$CURRENT_STEP" "done" "Deployment health gate passed"

CURRENT_STEP="smoke_test"
append_event "$CURRENT_STEP" "in_progress" "Running smoke tests"
python3 "$ROOT_DIR/scripts/smoke_test_web_product.py" --base-url "$DEPLOY_URL" --out "$SMOKE_REPORT" --page-spec "$PAGE_SPEC_PATH"
cp "$SMOKE_REPORT" "$ARTIFACT_DIR/smoke_test.latest.json"
append_event "$CURRENT_STEP" "done" "Smoke tests passed"

if [[ "$RUN_PAGE_STRATEGY_TEST" == "yes" ]]; then
  CURRENT_STEP="page_strategy_test"
  append_event "$CURRENT_STEP" "in_progress" "Running page strategy tests"
  python3 "$ROOT_DIR/scripts/page_strategy_test_web_product.py" \
    --base-url "$DEPLOY_URL" \
    --page-spec "$PAGE_SPEC_PATH" \
    --out "$PAGE_STRATEGY_REPORT"
  cp "$PAGE_STRATEGY_REPORT" "$ARTIFACT_DIR/page_strategy.latest.json"
  append_event "$CURRENT_STEP" "done" "Page strategy tests passed"
else
  cat >"$PAGE_STRATEGY_REPORT" <<JSON
{
  "generated_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "base_url": "$DEPLOY_URL",
  "status": "skipped",
  "reason": "skip_page_strategy_test_flag"
}
JSON
  cp "$PAGE_STRATEGY_REPORT" "$ARTIFACT_DIR/page_strategy.latest.json"
fi

CURRENT_STEP="business_test"
append_event "$CURRENT_STEP" "in_progress" "Running business-rule tests"
if [[ -n "$LEGACY_BLUEPRINT_PATH" ]]; then
  # Legacy mode has no dedicated project spec; use snapshot generated in scaffold output.
  python3 "$ROOT_DIR/scripts/business_test_web_product.py" \
    --base-url "$DEPLOY_URL" \
    --project-spec "$APP_DIR/project_spec.snapshot.json" \
    --out "$BUSINESS_REPORT"
else
  python3 "$ROOT_DIR/scripts/business_test_web_product.py" \
    --base-url "$DEPLOY_URL" \
    --project-spec "$PROJECT_SPEC_PATH" \
    --out "$BUSINESS_REPORT"
fi
cp "$BUSINESS_REPORT" "$ARTIFACT_DIR/business_test.latest.json"
append_event "$CURRENT_STEP" "done" "Business-rule tests passed"

CURRENT_STEP="report"
append_event "$CURRENT_STEP" "in_progress" "Writing run report"
python3 - "$RUN_REPORT" "$RUN_ID" "$PROJECT_SPEC_PATH" "$APP_DIR" "$ARTIFACT_DIR" "$DEPLOY_URL" "$SCAFFOLD_SUMMARY" "$SMOKE_REPORT" "$PAGE_STRATEGY_REPORT" "$BUSINESS_REPORT" "$LEGACY_BLUEPRINT_PATH" "$ROLLBACK_ON_FAIL" "$RUN_PAGE_STRATEGY_TEST" "$PAGE_SPEC_PATH" <<'PY'
import datetime as dt
import json
import pathlib
import sys

run_report = pathlib.Path(sys.argv[1])
run_id = sys.argv[2]
project_spec_path = pathlib.Path(sys.argv[3]).resolve()
app_dir = pathlib.Path(sys.argv[4]).resolve()
artifact_dir = pathlib.Path(sys.argv[5]).resolve()
deploy_url = sys.argv[6]
scaffold_summary_path = pathlib.Path(sys.argv[7]).resolve()
smoke_path = pathlib.Path(sys.argv[8]).resolve()
page_strategy_path = pathlib.Path(sys.argv[9]).resolve()
business_path = pathlib.Path(sys.argv[10]).resolve()
legacy_blueprint = sys.argv[11]
rollback_on_fail = sys.argv[12]
run_page_strategy_test = sys.argv[13]
page_spec_path = pathlib.Path(sys.argv[14]).resolve()

scaffold_summary = json.loads(scaffold_summary_path.read_text(encoding="utf-8"))
smoke_report = json.loads(smoke_path.read_text(encoding="utf-8"))
page_strategy_report = json.loads(page_strategy_path.read_text(encoding="utf-8"))
business_report = json.loads(business_path.read_text(encoding="utf-8"))

project_id = scaffold_summary.get("project_id")
adapter_name = scaffold_summary.get("adapter_name")
input_mode = scaffold_summary.get("mode")

status = "passed"
if smoke_report.get("status") != "passed" or business_report.get("status") != "passed":
    status = "failed"
if run_page_strategy_test == "yes" and page_strategy_report.get("status") != "passed":
    status = "failed"

report = {
    "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "run_id": run_id,
    "status": status,
    "capability": "build_deploy_simple_web_products_v1.1",
    "input": {
        "mode": input_mode,
        "legacy_blueprint_path": str(pathlib.Path(legacy_blueprint).resolve()) if legacy_blueprint else None,
        "project_spec_path": str(project_spec_path) if project_spec_path.exists() else None,
        "project_id": project_id,
        "from_opportunity_id": scaffold_summary.get("from_opportunity_id"),
        "adapter_name": adapter_name,
        "page_strategy_test_enabled": run_page_strategy_test,
    },
    "output": {
        "app_dir": str(app_dir),
        "deployed_url": deploy_url,
        "artifact_dir": str(artifact_dir),
        "scaffold_summary": str(scaffold_summary_path),
        "page_spec_path": str(page_spec_path) if page_spec_path.exists() else None,
        "smoke_test_report": str(smoke_path),
        "page_strategy_test_report": str(page_strategy_path),
        "business_test_report": str(business_path),
        "deploy_log_hint": str(artifact_dir / "deploy_latest.json"),
    },
    "checks": {
        "deployment_health_gate": "passed",
        "smoke_status": smoke_report.get("status"),
        "page_strategy_status": page_strategy_report.get("status"),
        "business_status": business_report.get("status"),
        "smoke_checks": smoke_report.get("checks", []),
        "page_strategy_checks": page_strategy_report.get("checks", []),
        "business_checks": business_report.get("checks", []),
    },
    "safety": {
        "rollback_on_fail": rollback_on_fail,
        "rollback_mode": "best_effort_vercel_cli"
    },
}

run_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
append_event "$CURRENT_STEP" "done" "Run report written"

CURRENT_STEP="complete"
append_event "$CURRENT_STEP" "passed" "Pipeline completed successfully"

echo "$DEPLOY_URL"
