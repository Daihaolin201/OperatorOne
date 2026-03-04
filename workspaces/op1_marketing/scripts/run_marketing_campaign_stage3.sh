#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="shadow"
FORCE="no"
INCLUDE_REVIEW_READY="no"
MAX_CAMPAIGNS=8
MIN_READINESS=78
DEFAULT_BUDGET=1200
DURATION_DAYS=14
BASE_DOMAIN="https://operatorone.ai"
CONTINUOUS="no"
INTERVAL_SECONDS=300
MAX_LOOPS=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_marketing_campaign_stage3.sh [options]

Options:
  --mode <shadow|review>          Run mode (default: shadow)
  --force                         Force recompute even if no input delta
  --include-review-ready          Include Stage2 review_ready items as watch candidates
  --max-campaigns <n>             Max campaign plans (default: 8)
  --min-readiness <v>             Readiness threshold for launch_ready (default: 78)
  --default-budget <v>            Fallback budget if handoff budget is unset (default: 1200)
  --duration-days <n>             Default campaign duration days (default: 14)
  --base-domain <url>             Base domain for landing URL fallback (default: https://operatorone.ai)
  --continuous                    Run continuously
  --interval <seconds>            Continuous interval seconds (default: 300)
  --max-loops <n>                 Exit after n loops in continuous mode (0=infinite)
  --help                          Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --force)
      FORCE="yes"
      shift
      ;;
    --include-review-ready)
      INCLUDE_REVIEW_READY="yes"
      shift
      ;;
    --max-campaigns)
      MAX_CAMPAIGNS="$2"
      shift 2
      ;;
    --min-readiness)
      MIN_READINESS="$2"
      shift 2
      ;;
    --default-budget)
      DEFAULT_BUDGET="$2"
      shift 2
      ;;
    --duration-days)
      DURATION_DAYS="$2"
      shift 2
      ;;
    --base-domain)
      BASE_DOMAIN="$2"
      shift 2
      ;;
    --continuous)
      CONTINUOUS="yes"
      shift
      ;;
    --interval)
      INTERVAL_SECONDS="$2"
      shift 2
      ;;
    --max-loops)
      MAX_LOOPS="$2"
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

run_once() {
  local cmd=(
    python3 "$ROOT_DIR/scripts/run_marketing_campaign_stage3.py"
    --root-dir "$ROOT_DIR"
    --mode "$MODE"
    --max-campaigns "$MAX_CAMPAIGNS"
    --min-readiness "$MIN_READINESS"
    --default-budget "$DEFAULT_BUDGET"
    --duration-days "$DURATION_DAYS"
    --base-domain "$BASE_DOMAIN"
    --print-summary
  )

  if [[ "$FORCE" == "yes" ]]; then
    cmd+=(--force)
  fi
  if [[ "$INCLUDE_REVIEW_READY" == "yes" ]]; then
    cmd+=(--include-review-ready)
  fi

  "${cmd[@]}"
}

if [[ "$CONTINUOUS" == "yes" ]]; then
  loop=0
  while true; do
    run_once
    loop=$((loop + 1))

    if [[ "$MAX_LOOPS" -gt 0 && "$loop" -ge "$MAX_LOOPS" ]]; then
      break
    fi

    sleep "$INTERVAL_SECONDS"
  done
else
  run_once
fi
