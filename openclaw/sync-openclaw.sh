#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$SCRIPT_DIR/agents.manifest.json"

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

CONFIG_PATH="$(openclaw config file | tr -d '\r')"
CONFIG_PATH="${CONFIG_PATH/#\~/$HOME}"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "[ERROR] OpenClaw config not found: $CONFIG_PATH" >&2
  exit 1
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_PATH="$CONFIG_PATH.bak.operatorone.$TIMESTAMP"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "[INFO] Dry-run: skip backup write (would create $BACKUP_PATH)"
else
  cp "$CONFIG_PATH" "$BACKUP_PATH"
  echo "[INFO] Backup created: $BACKUP_PATH"
fi

# Ensure workspace directories exist.
python3 - "$MANIFEST" "$REPO_ROOT" <<'PY'
import json, os, sys
manifest_path, repo_root = sys.argv[1], sys.argv[2]
with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)
for a in manifest.get('agents', []):
    ws = os.path.join(repo_root, a['workspace'])
    os.makedirs(ws, exist_ok=True)
print('[INFO] Workspace directories ensured')
PY

TMP_MERGE_JSON="$(mktemp)"

python3 - "$MANIFEST" "$REPO_ROOT" > "$TMP_MERGE_JSON" <<'PY'
import json
import os
import subprocess
import sys

manifest_path, repo_root = sys.argv[1], sys.argv[2]

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

def cfg_get(path, default):
    try:
        out = subprocess.check_output(["openclaw", "config", "get", path], stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        msg = (e.output or "").strip().lower()
        if "config path not found" in msg or "path not found" in msg:
            return default
        raise
    out = out.strip()
    if not out:
        return default
    return json.loads(out)

agents_list = cfg_get("agents.list", [])
if not isinstance(agents_list, list):
    raise SystemExit("[ERROR] config agents.list is not an array")

by_id = {a.get("id"): a for a in agents_list if isinstance(a, dict) and a.get("id")}
changes = []
warnings = []

home = os.path.expanduser("~")

for item in manifest.get("agents", []):
    aid = item["id"]
    ws_abs = os.path.abspath(os.path.join(repo_root, item["workspace"]))
    ad_abs = os.path.join(home, ".openclaw", "agents", aid, "agent")

    if aid not in by_id:
        new_agent = {
            "id": aid,
            "workspace": ws_abs,
            "agentDir": ad_abs,
        }
        agents_list.append(new_agent)
        by_id[aid] = new_agent
        changes.append(f"add agent {aid}")
    else:
        existing = by_id[aid]
        existing_ws = existing.get("workspace")
        if existing_ws is None:
            existing["workspace"] = ws_abs
            changes.append(f"set workspace for existing agent {aid}")
        elif os.path.abspath(os.path.expanduser(str(existing_ws))) != ws_abs:
            warnings.append(f"skip workspace overwrite for {aid} (existing: {existing_ws})")

        if existing.get("agentDir") is None:
            existing["agentDir"] = ad_abs
            changes.append(f"set agentDir for existing agent {aid}")

if manifest.get("syncMainAllowAgents", False):
    main = by_id.get("main")
    if isinstance(main, dict):
        sub = main.setdefault("subagents", {})
        allow = sub.setdefault("allowAgents", [])
        if isinstance(allow, list):
            for item in manifest.get("agents", []):
                aid = item["id"]
                if aid not in allow:
                    allow.append(aid)
                    changes.append(f"append main.subagents.allowAgents += {aid}")
        else:
            warnings.append("main.subagents.allowAgents is not an array; skip append")

extra_dirs = cfg_get("skills.load.extraDirs", [])
if extra_dirs is None:
    extra_dirs = []
elif not isinstance(extra_dirs, list):
    extra_dirs = [str(extra_dirs)]

shared_abs = os.path.abspath(os.path.join(repo_root, manifest.get("sharedSkillsDir", "shared/skills")))
if shared_abs not in extra_dirs:
    extra_dirs.append(shared_abs)
    changes.append("append OperatorOne shared skills dir to skills.load.extraDirs")

print(json.dumps({
    "agents_list": agents_list,
    "extra_dirs": extra_dirs,
    "changes": changes,
    "warnings": warnings,
}, ensure_ascii=False))
PY

python3 - "$TMP_MERGE_JSON" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    merged = json.load(f)
print('[INFO] Planned changes:')
if merged['changes']:
    for c in merged['changes']:
        print('  -', c)
else:
    print('  - (none)')
if merged['warnings']:
    print('[WARN] Non-destructive skips:')
    for w in merged['warnings']:
        print('  -', w)
PY

if [[ "$DRY_RUN" == "1" ]]; then
  rm -f "$TMP_MERGE_JSON"
  echo "[INFO] Dry-run mode: no config changes written"
  echo "[DONE] Dry-run completed."
  exit 0
fi

python3 - "$TMP_MERGE_JSON" <<'PY'
import json, subprocess, sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    merged = json.load(f)

agents_json = json.dumps(merged['agents_list'], ensure_ascii=False)
extra_json = json.dumps(merged['extra_dirs'], ensure_ascii=False)

subprocess.check_call(["openclaw", "config", "set", "agents.list", agents_json, "--strict-json"])
subprocess.check_call(["openclaw", "config", "set", "skills.load.extraDirs", extra_json, "--strict-json"])
PY

rm -f "$TMP_MERGE_JSON"

echo "[DONE] Sync completed."
echo "[NEXT] Restart gateway: openclaw gateway restart"
echo "[NEXT] Start a fresh chat session: /new"
