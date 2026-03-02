#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$SCRIPT_DIR/agents.manifest.json"
TARGET_SKILL_DIR="$(cd "$REPO_ROOT/shared/skills" && pwd)"

if [[ ! -f "$MANIFEST" ]]; then
  echo "[ERROR] Missing manifest: $MANIFEST" >&2
  exit 1
fi

for cmd in openclaw python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[ERROR] Required command not found in PATH: $cmd" >&2
    exit 1
  fi
done

# Guard against inherited OPENCLAW_* vars (this script must target default profile only).
OPENCLAW_ENV_KEYS=()
OPENCLAW_ENV_UNSET_ARGS=()
while IFS='=' read -r k _; do
  if [[ "$k" == OPENCLAW_* ]]; then
    OPENCLAW_ENV_KEYS+=("$k")
    OPENCLAW_ENV_UNSET_ARGS+=("-u" "$k")
  fi
done < <(env)

if [[ "${#OPENCLAW_ENV_KEYS[@]}" -gt 0 ]]; then
  echo "[WARN] Detected inherited OPENCLAW_* env vars; cleanup will ignore them and target default profile only:"
  for k in "${OPENCLAW_ENV_KEYS[@]}"; do
    echo "  - $k"
  done
fi

oc_default() {
  if [[ "${#OPENCLAW_ENV_UNSET_ARGS[@]}" -gt 0 ]]; then
    env "${OPENCLAW_ENV_UNSET_ARGS[@]}" openclaw "$@"
  else
    openclaw "$@"
  fi
}

CONFIG_PATH="$(oc_default config file | tr -d '\r')"
CONFIG_PATH="${CONFIG_PATH/#\~/$HOME}"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "[ERROR] Default profile config not found: $CONFIG_PATH" >&2
  exit 1
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_PATH="$CONFIG_PATH.bak.operatorone-clean.$TIMESTAMP"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "[INFO] Dry-run: skip backup write (would create $BACKUP_PATH)"
else
  cp "$CONFIG_PATH" "$BACKUP_PATH"
  echo "[INFO] Backup created: $BACKUP_PATH"
fi

TMP_JSON="$(mktemp)"
python3 - "$TARGET_SKILL_DIR" "$MANIFEST" > "$TMP_JSON" <<'PY'
import json
import os
import subprocess
import sys

target_skill_dir, manifest_path = sys.argv[1:3]
clean_env = {k: v for k, v in os.environ.items() if not k.startswith("OPENCLAW_")}

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)
remove_ids = {
    a.get("id")
    for a in manifest.get("agents", [])
    if isinstance(a, dict) and isinstance(a.get("id"), str)
}

def cfg_get(path, default):
    try:
        out = subprocess.check_output(["openclaw", "config", "get", path], stderr=subprocess.STDOUT, text=True, env=clean_env)
    except subprocess.CalledProcessError as e:
        msg = (e.output or "").strip().lower()
        if "config path not found" in msg or "path not found" in msg:
            return default
        raise
    out = out.strip()
    if not out:
        return default
    return json.loads(out)

agents = cfg_get("agents.list", [])
if not isinstance(agents, list):
    raise SystemExit("[ERROR] agents.list is not an array")

next_agents = []
removed = []
for a in agents:
    if not isinstance(a, dict):
        next_agents.append(a)
        continue
    aid = a.get("id")
    if isinstance(aid, str) and aid in remove_ids:
        removed.append(aid)
        continue
    # also clean main allowlist from op1_* ids
    if aid == "main" and isinstance(a.get("subagents"), dict):
        allow = a["subagents"].get("allowAgents")
        if isinstance(allow, list):
            a = dict(a)
            sub = dict(a["subagents"])
            sub["allowAgents"] = [x for x in allow if not (isinstance(x, str) and x in remove_ids)]
            a["subagents"] = sub
    next_agents.append(a)

extra = cfg_get("skills.load.extraDirs", [])
if extra is None:
    extra = []
elif not isinstance(extra, list):
    extra = [str(extra)]

next_extra = [x for x in extra if x != target_skill_dir]

print(json.dumps({
    "removed_agents": removed,
    "agents_list": next_agents,
    "extra_dirs": next_extra,
    "changed_agents": agents != next_agents,
    "changed_extra": extra != next_extra,
}, ensure_ascii=False))
PY

python3 - "$TMP_JSON" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    plan = json.load(f)
print('[INFO] Planned cleanup:')
if plan['removed_agents']:
    for aid in plan['removed_agents']:
        print('  - remove agent', aid)
else:
    print('  - no OperatorOne manifest agents to remove')
if plan['changed_extra']:
    print('  - remove OperatorOne shared skills dir from default profile extraDirs')
else:
    print('  - no OperatorOne shared skills dir in default profile extraDirs')
PY

if [[ "$DRY_RUN" == "1" ]]; then
  rm -f "$TMP_JSON"
  echo "[INFO] Dry-run mode: no config changes written"
  echo "[DONE] Dry-run completed."
  exit 0
fi

python3 - "$TMP_JSON" <<'PY'
import json, os, subprocess, sys
clean_env = {k: v for k, v in os.environ.items() if not k.startswith("OPENCLAW_")}
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    plan = json.load(f)

if plan.get('changed_agents'):
    subprocess.check_call([
        'openclaw', 'config', 'set', 'agents.list',
        json.dumps(plan['agents_list'], ensure_ascii=False), '--strict-json'
    ], env=clean_env)
if plan.get('changed_extra'):
    subprocess.check_call([
        'openclaw', 'config', 'set', 'skills.load.extraDirs',
        json.dumps(plan['extra_dirs'], ensure_ascii=False), '--strict-json'
    ], env=clean_env)
PY

rm -f "$TMP_JSON"

echo "[DONE] Default-profile cleanup completed."
echo "[NEXT] (Optional) restart default profile gateway: openclaw gateway restart"
