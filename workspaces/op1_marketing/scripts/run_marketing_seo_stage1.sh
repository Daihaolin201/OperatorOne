#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="shadow"
PUBLISH="no"
INDEX_FLAG="no"
FORCE="no"
CONTINUOUS="no"
INTERVAL_SECONDS=300
MAX_LOOPS=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_marketing_seo_stage1.sh [options]

Options:
  --mode <shadow|live>   Run mode (default: shadow)
  --publish              Set publish=true (default false)
  --index                Set index=true (default false)
  --force                Force recompute even if no input delta
  --continuous           Run in continuous loop mode
  --interval <seconds>   Loop interval in seconds (default: 300)
  --max-loops <n>        Exit after n loops in continuous mode (default: 0 => infinite)
  --help                 Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --publish)
      PUBLISH="yes"
      shift
      ;;
    --index)
      INDEX_FLAG="yes"
      shift
      ;;
    --force)
      FORCE="yes"
      shift
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
    python3 "$ROOT_DIR/scripts/run_marketing_seo_stage1.py"
    --root-dir "$ROOT_DIR"
    --mode "$MODE"
    --print-summary
  )

  if [[ "$PUBLISH" == "yes" ]]; then
    cmd+=(--publish)
  fi
  if [[ "$INDEX_FLAG" == "yes" ]]; then
    cmd+=(--index)
  fi
  if [[ "$FORCE" == "yes" ]]; then
    cmd+=(--force)
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
