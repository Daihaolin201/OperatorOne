#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${1:-127.0.0.1}"
PORT="${2:-8765}"

exec python3 dashboard/server.py --host "$HOST" --port "$PORT"
