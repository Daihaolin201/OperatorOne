#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/../.." && pwd)"

MODE="shadow"
FORCE="no"
INCLUDE_HOLD="no"
MAX_ITEMS=12
MIN_SCORE=78
CONTINUOUS="no"
INTERVAL_SECONDS=300
MAX_LOOPS=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_marketing_content_stage2.sh [options]

Options:
  --mode <shadow|review>   Run mode (default: shadow)
  --force                  Force recompute even if no input delta
  --include-hold           Include Stage1 hold queue for candidate selection
  --max-items <n>          Max generated content items (default: 12)
  --min-score <v>          Minimum Stage1 score floor in quality gate (default: 78)
  --continuous             Run in continuous loop mode
  --interval <seconds>     Loop interval in seconds (default: 300)
  --max-loops <n>          Exit after n loops in continuous mode (default: 0 => infinite)
  --help                   Show help
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
    --include-hold)
      INCLUDE_HOLD="yes"
      shift
      ;;
    --max-items)
      MAX_ITEMS="$2"
      shift 2
      ;;
    --min-score)
      MIN_SCORE="$2"
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
    python3 "$ROOT_DIR/scripts/run_marketing_content_stage2.py"
    --root-dir "$ROOT_DIR"
    --mode "$MODE"
    --max-items "$MAX_ITEMS"
    --min-score "$MIN_SCORE"
    --print-summary
  )

  if [[ "$FORCE" == "yes" ]]; then
    cmd+=(--force)
  fi
  if [[ "$INCLUDE_HOLD" == "yes" ]]; then
    cmd+=(--include-hold)
  fi

  "${cmd[@]}"

  python3 "$REPO_ROOT/scripts/validate_handoffs.py" \
    --repo-root "$REPO_ROOT" \
    --contracts marketing_to_sales
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
