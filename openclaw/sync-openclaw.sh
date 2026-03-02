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

if ! command -v openclaw >/dev/null 2>&1; then
  echo "[ERROR] openclaw CLI not found in PATH" >&2
  exit 1
fi

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

# Ensure workspace directories exist before writing config.
python3 - "$MANIFEST" "$REPO_ROOT" <<'PY'
import json, os, sys
manifest_path, repo_root = sys.argv[1], sys.argv[2]
with open(manifest_path, 'r', encoding='utf-8') as f:
    m = json.load(f)
for a in m.get('agents', []):
    rel = a['workspace']
    abs_ws = os.path.join(repo_root, rel)
    os.makedirs(abs_ws, exist_ok=True)
print('[INFO] Workspace directories ensured')
PY

TMP_PATH="${CONFIG_PATH}.operatorone.tmp"

python3 - "$CONFIG_PATH" "$TMP_PATH" "$MANIFEST" "$REPO_ROOT" "$DRY_RUN" <<'PY'
import json
import os
import sys
from copy import deepcopy

cfg_path, out_path, manifest_path, repo_root, dry_flag = sys.argv[1:6]
dry_run = dry_flag == "1"

with open(cfg_path, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

before = deepcopy(cfg)

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

agents_cfg = cfg.setdefault('agents', {})
agent_list = agents_cfg.setdefault('list', [])
if not isinstance(agent_list, list):
    raise SystemExit('[ERROR] config path agents.list is not an array')

by_id = {a.get('id'): a for a in agent_list if isinstance(a, dict) and a.get('id')}
changes = []
warnings = []

home = os.path.expanduser('~')

for item in manifest.get('agents', []):
    aid = item['id']
    ws_abs = os.path.abspath(os.path.join(repo_root, item['workspace']))
    ad_abs = os.path.join(home, '.openclaw', 'agents', aid, 'agent')

    if aid not in by_id:
        agent_list.append({
            'id': aid,
            'workspace': ws_abs,
            'agentDir': ad_abs
        })
        changes.append(f'add agent {aid}')
        by_id[aid] = agent_list[-1]
    else:
        existing = by_id[aid]
        existing_ws = existing.get('workspace')
        if existing_ws is None:
            existing['workspace'] = ws_abs
            changes.append(f'set workspace for existing agent {aid}')
        elif os.path.abspath(os.path.expanduser(str(existing_ws))) != ws_abs:
            warnings.append(f'skip workspace overwrite for {aid} (existing: {existing_ws})')

        existing_ad = existing.get('agentDir')
        if existing_ad is None:
            existing['agentDir'] = ad_abs
            changes.append(f'set agentDir for existing agent {aid}')

if manifest.get('syncMainAllowAgents', False):
    main = by_id.get('main')
    if isinstance(main, dict):
        sub = main.setdefault('subagents', {})
        allow = sub.setdefault('allowAgents', [])
        if isinstance(allow, list):
            for item in manifest.get('agents', []):
                aid = item['id']
                if aid not in allow:
                    allow.append(aid)
                    changes.append(f'append main.subagents.allowAgents += {aid}')
        else:
            warnings.append('main.subagents.allowAgents is not an array; skip append')

skills_cfg = cfg.setdefault('skills', {})
load_cfg = skills_cfg.setdefault('load', {})
extra = load_cfg.get('extraDirs')
shared_rel = manifest.get('sharedSkillsDir', 'shared/skills')
shared_abs = os.path.abspath(os.path.join(repo_root, shared_rel))

if extra is None:
    load_cfg['extraDirs'] = [shared_abs]
    changes.append('set skills.load.extraDirs with OperatorOne shared skills')
elif isinstance(extra, list):
    if shared_abs not in extra:
        extra.append(shared_abs)
        changes.append('append OperatorOne shared skills dir to skills.load.extraDirs')
else:
    normalized = [str(extra)]
    if shared_abs not in normalized:
        normalized.append(shared_abs)
    load_cfg['extraDirs'] = normalized
    changes.append('normalize skills.load.extraDirs to array and append OperatorOne path')

print('[INFO] Planned changes:')
if changes:
    for c in changes:
        print('  -', c)
else:
    print('  - (none)')

if warnings:
    print('[WARN] Non-destructive skips:')
    for w in warnings:
        print('  -', w)

if dry_run:
    print('[INFO] Dry-run mode: no config changes written')
    sys.exit(0)

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
    f.write('\n')

print('[INFO] Config written:', out_path)
PY

if [[ "$DRY_RUN" == "1" ]]; then
  rm -f "$TMP_PATH"
  echo "[DONE] Dry-run completed."
  exit 0
fi

mv "$TMP_PATH" "$CONFIG_PATH"
chmod 600 "$CONFIG_PATH" || true

echo "[DONE] Sync completed."
echo "[NEXT] Restart gateway: openclaw gateway restart"
echo "[NEXT] Start a fresh chat session: /new"
