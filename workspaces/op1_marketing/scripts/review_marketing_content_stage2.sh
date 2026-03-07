#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APPROVE=()
REJECT=()
APPROVE_ALL="no"
REJECT_ALL="no"
REASON="manual_review_requested_changes"
NOTE=""

usage() {
  cat <<'USAGE'
Usage:
  scripts/review_marketing_content_stage2.sh [options]

Options:
  --approve <content_id[,content_id...]>     Approve one or more review_ready items
  --reject <content_id[,content_id...]>      Request revision for one or more review_ready items
  --approve-all                              Approve all current review_ready items
  --reject-all                               Request revision for all current review_ready items
  --reason <text>                            Rejection reason (default: manual_review_requested_changes)
  --note <text>                              Optional reviewer note
  --help                                     Show help

Examples:
  ./scripts/review_marketing_content_stage2.sh --approve-all --note "QA pass"
  ./scripts/review_marketing_content_stage2.sh --approve cnt_a,cnt_b --reject cnt_c --reason "tighten evidence"
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --approve)
      APPROVE+=("$2")
      shift 2
      ;;
    --reject)
      REJECT+=("$2")
      shift 2
      ;;
    --approve-all)
      APPROVE_ALL="yes"
      shift
      ;;
    --reject-all)
      REJECT_ALL="yes"
      shift
      ;;
    --reason)
      REASON="$2"
      shift 2
      ;;
    --note)
      NOTE="$2"
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

cmd=(
  python3 "$ROOT_DIR/scripts/review_marketing_content_stage2.py"
  --root-dir "$ROOT_DIR"
  --reason "$REASON"
  --note "$NOTE"
  --print-summary
)

if [[ "$APPROVE_ALL" == "yes" ]]; then
  cmd+=(--approve-all)
fi
if [[ "$REJECT_ALL" == "yes" ]]; then
  cmd+=(--reject-all)
fi

for id in "${APPROVE[@]:-}"; do
  [[ -n "$id" ]] && cmd+=(--approve "$id")
done
for id in "${REJECT[@]:-}"; do
  [[ -n "$id" ]] && cmd+=(--reject "$id")
done

"${cmd[@]}"
