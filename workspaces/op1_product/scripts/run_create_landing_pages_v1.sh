#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE1_PATH="$ROOT_DIR/research/stage1_idea_discovery/opportunity_records.json"
STAGE2_PATH="$ROOT_DIR/research/stage2_idea_screening/decision_log.json"
STAGE3_PATH="$ROOT_DIR/research/stage3_mvp_scope/project_blueprint.json"
PROJECT_SPEC_PATH=""
OUT_DIR="$ROOT_DIR/research/landing_v1"
HANDOFF_OUT="../../handoffs/product_to_marketing.json"

OPP_ID=""
ADAPTER_ID=""
PAGE_PROFILE=""
WITH_DEPLOY="no"
FORCE="yes"

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_create_landing_pages_v1.sh [options]

Options:
  --stage1 <path>         Stage1 records path
  --stage2 <path>         Stage2 decision path (optional)
  --stage3 <path>         Stage3 blueprint path (optional)
  --project-spec <path>   Existing project spec path (optional)
  --out-dir <path>        Output directory (default: research/landing_v1)
  --handoff-out <path>    Handoff path, relative to workspace (default: ../../handoffs/product_to_marketing.json)
  --opp-id <id>           Force opportunity id
  --adapter <id>          Force adapter when generating project spec
  --page-profile <id>     Force landing profile during page spec compile
  --with-deploy           Run build/deploy pipeline after landing package passes contract test
  --no-force              Keep existing out-dir (do not wipe)
  --help                  Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage1)
      STAGE1_PATH="$2"
      shift 2
      ;;
    --stage2)
      STAGE2_PATH="$2"
      shift 2
      ;;
    --stage3)
      STAGE3_PATH="$2"
      shift 2
      ;;
    --project-spec)
      PROJECT_SPEC_PATH="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --handoff-out)
      HANDOFF_OUT="$2"
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
    --page-profile)
      PAGE_PROFILE="$2"
      shift 2
      ;;
    --with-deploy)
      WITH_DEPLOY="yes"
      shift
      ;;
    --no-force)
      FORCE="no"
      shift
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

RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
RUN_REPORT="$ROOT_DIR/research/stage3_landing_launch/run.latest.json"
CONTRACT_TEST_OUT="$OUT_DIR/landing_contract_test_${RUN_ID}.json"
CONTRACT_TEST_LATEST="$OUT_DIR/landing_contract_test.latest.json"
SEMANTIC_TEST_OUT="$OUT_DIR/landing_semantic_test_${RUN_ID}.json"
SEMANTIC_TEST_LATEST="$OUT_DIR/landing_semantic_test.latest.json"
LANDING_PACKAGE_PATH="$OUT_DIR/landing_package.json"
PAGE_SPEC_PATH="$OUT_DIR/build_inputs/page_spec.json"

if [[ "$FORCE" == "yes" ]]; then
  FORCE_FLAG="--force"
else
  FORCE_FLAG=""
fi

mkdir -p "$OUT_DIR"
mkdir -p "$(dirname "$RUN_REPORT")"

CMD=(
  python3 "$ROOT_DIR/scripts/create_landing_package.py"
  --stage1 "$STAGE1_PATH"
  --stage2 "$STAGE2_PATH"
  --stage3 "$STAGE3_PATH"
  --out-dir "$OUT_DIR"
  --handoff-out "$HANDOFF_OUT"
)

if [[ -n "$FORCE_FLAG" ]]; then
  CMD+=("$FORCE_FLAG")
fi
if [[ -n "$OPP_ID" ]]; then
  CMD+=(--opp-id "$OPP_ID")
fi
if [[ -n "$ADAPTER_ID" ]]; then
  CMD+=(--adapter "$ADAPTER_ID")
fi
if [[ -n "$PROJECT_SPEC_PATH" ]]; then
  CMD+=(--project-spec "$PROJECT_SPEC_PATH")
fi
if [[ -n "$PAGE_PROFILE" ]]; then
  CMD+=(--page-profile "$PAGE_PROFILE")
fi

"${CMD[@]}"

python3 "$ROOT_DIR/scripts/landing_contract_test.py" \
  --landing-package "$LANDING_PACKAGE_PATH" \
  --out "$CONTRACT_TEST_OUT"
cp "$CONTRACT_TEST_OUT" "$CONTRACT_TEST_LATEST"

python3 "$ROOT_DIR/scripts/landing_semantic_test.py" \
  --landing-package "$LANDING_PACKAGE_PATH" \
  --page-spec "$PAGE_SPEC_PATH" \
  --out "$SEMANTIC_TEST_OUT"
cp "$SEMANTIC_TEST_OUT" "$SEMANTIC_TEST_LATEST"

STATUS="$(python3 - "$LANDING_PACKAGE_PATH" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
print(json.loads(p.read_text(encoding='utf-8')).get('status','unknown'))
PY
)"

DEPLOY_URL=""
DEPLOY_STATUS="skipped"

if [[ "$WITH_DEPLOY" == "yes" && "$STATUS" != "blocked" ]]; then
  DEPLOY_STATUS="running"
  PROJECT_SPEC_OUT="$OUT_DIR/build_inputs/project_spec.json"
  DEPLOY_ARTIFACT_DIR="$OUT_DIR/deploy_artifacts"

  DEPLOY_CMD=(
    "$ROOT_DIR/scripts/run_build_deploy_v1.sh"
    --project-spec "$PROJECT_SPEC_OUT"
    --page-spec "$PAGE_SPEC_PATH"
    --artifact-dir "$DEPLOY_ARTIFACT_DIR"
    --app-dir "$ROOT_DIR/runtime/web_product_landing_v1"
  )

  if [[ -n "$PAGE_PROFILE" ]]; then
    DEPLOY_CMD+=(--page-profile "$PAGE_PROFILE")
  fi

  DEPLOY_URL="$("${DEPLOY_CMD[@]}")"
  DEPLOY_STATUS="completed"
fi

python3 - "$RUN_REPORT" "$RUN_ID" "$LANDING_PACKAGE_PATH" "$CONTRACT_TEST_OUT" "$SEMANTIC_TEST_OUT" "$STATUS" "$WITH_DEPLOY" "$DEPLOY_STATUS" "$DEPLOY_URL" <<'PY'
import datetime as dt
import json
import pathlib
import sys

run_report = pathlib.Path(sys.argv[1])
run_id = sys.argv[2]
landing_path = pathlib.Path(sys.argv[3]).resolve()
contract_path = pathlib.Path(sys.argv[4]).resolve()
semantic_path = pathlib.Path(sys.argv[5]).resolve()
status = sys.argv[6]
with_deploy = sys.argv[7]
deploy_status = sys.argv[8]
deploy_url = sys.argv[9]

landing = json.loads(landing_path.read_text(encoding='utf-8'))
contract = json.loads(contract_path.read_text(encoding='utf-8'))
semantic = json.loads(semantic_path.read_text(encoding='utf-8'))

payload = {
    "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "run_id": run_id,
    "capability": "create_landing_pages_v1",
    "contract_version": "1.1",
    "mode": "mode_c_only",
    "page_mode": "landing",
    "status": status,
    "selected_opportunity": landing.get("selected_opportunity", {}).get("opportunity_id"),
    "artifacts": {
        "landing_package": str(landing_path),
        "landing_contract_test": str(contract_path),
        "landing_semantic_test": str(semantic_path),
        "project_spec": landing.get("build_inputs", {}).get("project_spec_path"),
        "page_spec": landing.get("build_inputs", {}).get("page_spec_path"),
        "marketing_handoff": landing.get("marketing_handoff_path"),
    },
    "checks": {
        "contract_test_status": contract.get("status"),
        "semantic_test_status": semantic.get("status"),
        "quality_gate_failures": [
            g for g in landing.get("quality_gates", [])
            if isinstance(g, dict) and g.get("status") == "fail"
        ],
    },
    "deploy": {
        "requested": with_deploy == "yes",
        "status": deploy_status,
        "url": deploy_url or None,
    },
}

run_report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"run_report": str(run_report), "status": status, "deploy_url": deploy_url or None}, ensure_ascii=False))
PY

python3 "$ROOT_DIR/scripts/update_live_examples_index.py" >/dev/null 2>&1 || true
