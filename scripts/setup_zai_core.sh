#!/usr/bin/env bash
set -euo pipefail

PROFILE="operatorone"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO_ROOT/openclaw/agents.manifest.json"
VERIFY_SCRIPT="$REPO_ROOT/scripts/verify_zai_core_integration.py"
RESTART_GATEWAY=1
RUN_PROBES=0
ZAI_API_KEY_INPUT="${ZAI_API_KEY:-}"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  --profile <name>         OpenClaw profile (default: operatorone)
  --zai-api-key <key>      Z.AI API key (or set env ZAI_API_KEY)
  --skip-restart           Do not restart gateway after config changes
  --probe-all-agents       Run runtime probe for all 4 agents after setup
  -h, --help               Show help

This script configures OperatorOne to use Z.AI GLM as primary model,
with manifest-defined fallbacks.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="${2:-}"
      shift 2
      ;;
    --zai-api-key)
      ZAI_API_KEY_INPUT="${2:-}"
      shift 2
      ;;
    --skip-restart)
      RESTART_GATEWAY=0
      shift
      ;;
    --probe-all-agents)
      RUN_PROBES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$MANIFEST" ]]; then
  echo "[ERROR] Missing manifest: $MANIFEST" >&2
  exit 1
fi

if [[ ! -f "$VERIFY_SCRIPT" ]]; then
  echo "[ERROR] Missing verifier: $VERIFY_SCRIPT" >&2
  exit 1
fi

MODEL_INFO_RAW="$(python3 - "$MANIFEST" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    m = json.load(f)
primary = str(m.get('profileDefaultModel') or '').strip()
if not primary:
    raise SystemExit('manifest.profileDefaultModel is required')
print(primary)
for x in (m.get('profileModelFallbacks') or []):
    x = str(x).strip()
    if x:
        print(x)
PY
)"

PRIMARY_MODEL="$(printf '%s\n' "$MODEL_INFO_RAW" | sed -n '1p')"
FALLBACKS=()
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  FALLBACKS+=("$line")
done <<EOF
$(printf '%s\n' "$MODEL_INFO_RAW" | tail -n +2)
EOF

echo "[INFO] Profile: $PROFILE"
echo "[INFO] Primary model: $PRIMARY_MODEL"
if [[ ${#FALLBACKS[@]} -gt 0 ]]; then
  echo "[INFO] Fallbacks: ${FALLBACKS[*]}"
else
  echo "[INFO] Fallbacks: (none)"
fi

if [[ -n "$ZAI_API_KEY_INPUT" ]]; then
  KEY_JSON="$(python3 - <<'PY' "$ZAI_API_KEY_INPUT"
import json, sys
print(json.dumps(sys.argv[1]))
PY
)"
  echo "[STEP] Setting env.ZAI_API_KEY in profile config"
  openclaw --profile "$PROFILE" config set env.ZAI_API_KEY "$KEY_JSON" --strict-json
else
  echo "[WARN] ZAI_API_KEY not provided; skipping key injection"
fi

echo "[STEP] Setting primary model"
openclaw --profile "$PROFILE" models set "$PRIMARY_MODEL"

echo "[STEP] Syncing fallback model list"
openclaw --profile "$PROFILE" models fallbacks clear || true
for fb in "${FALLBACKS[@]}"; do
  [[ -z "$fb" ]] && continue
  openclaw --profile "$PROFILE" models fallbacks add "$fb"
done

if [[ "$RESTART_GATEWAY" == "1" ]]; then
  echo "[STEP] Restarting gateway"
  openclaw --profile "$PROFILE" gateway restart
fi

echo "[STEP] Verifying integration"
if [[ "$RUN_PROBES" == "1" ]]; then
  python3 "$VERIFY_SCRIPT" \
    --repo-root "$REPO_ROOT" \
    --profile "$PROFILE" \
    --probe-all-agents \
    --probe-without-fallback
else
  python3 "$VERIFY_SCRIPT" --repo-root "$REPO_ROOT" --profile "$PROFILE"
fi

echo "[DONE] Z.AI core setup complete for profile '$PROFILE'."
