#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

HOST="${1:-127.0.0.1}"
PORT="${2:-8765}"
PROFILE="${OPENCLAW_PROFILE:-operatorone}"

printf "[1/3] Ensuring OpenClaw gateway is running (profile=%s) ...\n" "$PROFILE"
openclaw --profile "$PROFILE" gateway start >/dev/null || true

printf "[2/3] Gateway status:\n"
openclaw --profile "$PROFILE" gateway status | sed -n '1,20p'

printf "[3/3] Starting OperatorOne dashboard on http://%s:%s ...\n" "$HOST" "$PORT"
exec python3 dashboard/server.py --host "$HOST" --port "$PORT"
