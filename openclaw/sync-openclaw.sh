#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
PROFILE="operatorone"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--profile <name>] [--dry-run]

Default profile: operatorone
This script performs non-destructive OperatorOne sync into the selected profile.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --profile)
      PROFILE="${2:-}"
      if [[ -z "$PROFILE" ]]; then
        echo "[ERROR] --profile requires a value" >&2
        exit 1
      fi
      shift 2
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

oc() {
  openclaw --profile "$PROFILE" "$@"
}

expand_tilde() {
  local p="$1"
  echo "${p/#\~/$HOME}"
}

CONFIG_PATH="$(oc config file | tr -d '\r')"
CONFIG_PATH="$(expand_tilde "$CONFIG_PATH")"
STATE_DIR="$(dirname "$CONFIG_PATH")"

echo "[INFO] Profile: $PROFILE"
echo "[INFO] Config: $CONFIG_PATH"
echo "[INFO] State dir: $STATE_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_PATH="$CONFIG_PATH.bak.operatorone.$TIMESTAMP"
if [[ "$DRY_RUN" == "1" ]]; then
  if [[ -f "$CONFIG_PATH" ]]; then
    echo "[INFO] Dry-run: skip backup write (would create $BACKUP_PATH)"
  else
    echo "[INFO] Dry-run: profile config does not exist yet; would create a new config at $CONFIG_PATH"
  fi
else
  if [[ -f "$CONFIG_PATH" ]]; then
    cp "$CONFIG_PATH" "$BACKUP_PATH"
    echo "[INFO] Backup created: $BACKUP_PATH"
  else
    echo "[INFO] Profile config does not exist yet; it will be created by config set commands"
  fi
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
    os.makedirs(os.path.join(ws, 'skills'), exist_ok=True)
print('[INFO] Workspace and per-agent skills directories ensured')
PY

TMP_MERGE_JSON="$(mktemp)"

python3 - "$MANIFEST" "$REPO_ROOT" "$PROFILE" "$STATE_DIR" > "$TMP_MERGE_JSON" <<'PY'
import json
import os
import subprocess
import sys

manifest_path, repo_root, profile, state_dir = sys.argv[1:5]

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

def oc_get(path, default):
    try:
        out = subprocess.check_output([
            "openclaw", "--profile", profile, "config", "get", path
        ], stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        msg = (e.output or "").strip().lower()
        if "config path not found" in msg or "path not found" in msg:
            return default
        raise
    out = out.strip()
    if not out:
        return default
    try:
        return json.loads(out)
    except Exception:
        return out

agents_list = oc_get("agents.list", [])
if not isinstance(agents_list, list):
    raise SystemExit("[ERROR] config agents.list is not an array")

by_id = {a.get("id"): a for a in agents_list if isinstance(a, dict) and a.get("id")}
changes = []
warnings = []

for item in manifest.get("agents", []):
    aid = item["id"]
    ws_abs = os.path.abspath(os.path.join(repo_root, item["workspace"]))
    ad_abs = os.path.join(state_dir, "agents", aid, "agent")

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

# Dedicated-profile skill isolation: replace extraDirs by manifest-defined dirs.
mode = str(manifest.get("skillsExtraDirsMode", "replace")).lower()
rel_dirs = manifest.get("skillsExtraDirs")
if not isinstance(rel_dirs, list) or not rel_dirs:
    fallback = manifest.get("sharedSkillsDir", "shared/skills")
    rel_dirs = [fallback]

desired_extra_dirs = [os.path.abspath(os.path.join(repo_root, p)) for p in rel_dirs]

current_extra = oc_get("skills.load.extraDirs", [])
if current_extra is None:
    current_extra = []
elif not isinstance(current_extra, list):
    current_extra = [str(current_extra)]

if mode == "append":
    merged = list(current_extra)
    for d in desired_extra_dirs:
        if d not in merged:
            merged.append(d)
    next_extra = merged
else:
    next_extra = desired_extra_dirs

if current_extra != next_extra:
    changes.append(f"set skills.load.extraDirs ({mode})")

# Optional profile defaults
profile_ws = manifest.get("profileDefaultWorkspace")
current_default_ws = oc_get("agents.defaults.workspace", None)
next_default_ws = None
if profile_ws:
    next_default_ws = os.path.expanduser(str(profile_ws))
    if current_default_ws != next_default_ws:
        changes.append("set agents.defaults.workspace for profile")

gateway_port = manifest.get("gatewayPort")
current_port = oc_get("gateway.port", None)
next_port = None
if isinstance(gateway_port, int):
    next_port = gateway_port
    if current_port != next_port:
        changes.append("set gateway.port for profile")

profile_model = manifest.get("profileDefaultModel")
current_model = oc_get("agents.defaults.model.primary", None)
next_model = None
if isinstance(profile_model, str) and profile_model.strip():
    next_model = profile_model.strip()
    if current_model != next_model:
        changes.append("set agents.defaults.model.primary for profile")

print(json.dumps({
    "agents_list": agents_list,
    "extra_dirs": next_extra,
    "profile_workspace": next_default_ws,
    "gateway_port": next_port,
    "profile_model": next_model,
    "seed_auth": bool(manifest.get("seedAuthFromDefaultProfile", False)),
    "agent_ids": [a.get("id") for a in manifest.get("agents", []) if isinstance(a, dict) and a.get("id")],
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

python3 - "$TMP_MERGE_JSON" "$PROFILE" <<'PY'
import json, subprocess, sys
path, profile = sys.argv[1], sys.argv[2]
with open(path, 'r', encoding='utf-8') as f:
    merged = json.load(f)

agents_json = json.dumps(merged['agents_list'], ensure_ascii=False)
extra_json = json.dumps(merged['extra_dirs'], ensure_ascii=False)

subprocess.check_call(["openclaw", "--profile", profile, "config", "set", "agents.list", agents_json, "--strict-json"])
subprocess.check_call(["openclaw", "--profile", profile, "config", "set", "skills.load.extraDirs", extra_json, "--strict-json"])

if merged.get('profile_workspace'):
    subprocess.check_call([
        "openclaw", "--profile", profile, "config", "set", "agents.defaults.workspace",
        json.dumps(merged['profile_workspace'], ensure_ascii=False), "--strict-json"
    ])

if isinstance(merged.get('gateway_port'), int):
    subprocess.check_call([
        "openclaw", "--profile", profile, "config", "set", "gateway.port",
        str(merged['gateway_port']), "--strict-json"
    ])

if isinstance(merged.get('profile_model'), str) and merged['profile_model']:
    subprocess.check_call([
        "openclaw", "--profile", profile, "config", "set", "agents.defaults.model.primary",
        json.dumps(merged['profile_model'], ensure_ascii=False), "--strict-json"
    ])
PY

# Seed auth profiles from default profile into operatorone agents (best-effort, non-destructive).
if [[ "$DRY_RUN" != "1" ]]; then
  python3 - "$TMP_MERGE_JSON" "$STATE_DIR" <<'PY'
import json
import os
import shutil
import sys

merge_path, state_dir = sys.argv[1], sys.argv[2]
with open(merge_path, 'r', encoding='utf-8') as f:
    merged = json.load(f)

if not merged.get('seed_auth'):
    print('[INFO] Auth seeding disabled by manifest')
    raise SystemExit(0)

src = os.path.expanduser('~/.openclaw/agents/main/agent/auth-profiles.json')
if not os.path.isfile(src):
    print(f'[WARN] Default-profile auth source not found: {src}')
    raise SystemExit(0)

seeded = 0
skipped = 0
for aid in merged.get('agent_ids', []):
    if not aid:
        continue
    target_dir = os.path.join(state_dir, 'agents', aid, 'agent')
    os.makedirs(target_dir, exist_ok=True)
    dst = os.path.join(target_dir, 'auth-profiles.json')
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        skipped += 1
        continue
    shutil.copy2(src, dst)
    seeded += 1

print(f'[INFO] Auth seeding result: seeded={seeded}, skipped_existing={skipped}')
PY
fi

rm -f "$TMP_MERGE_JSON"

echo "[DONE] Sync completed for profile '$PROFILE'."
echo "[NEXT] Restart gateway: openclaw --profile $PROFILE gateway restart"
echo "[NEXT] Verify: openclaw --profile $PROFILE status"
echo "[NEXT] Start a fresh chat session: /new"
