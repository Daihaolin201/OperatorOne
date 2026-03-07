#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
PROFILE="operatorone"
SINGLE_ACTIVE=1

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--profile <name>] [--dry-run] [--allow-dual-gateway]

Default behavior:
  - Sync OperatorOne config into profile "operatorone"
  - Install/repoint + restart that profile's gateway
  - Enforce single-active mode by stopping default-profile gateway
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
    --allow-dual-gateway)
      SINGLE_ACTIVE=0
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$SCRIPT_DIR/agents.manifest.json"
SYNC_SCRIPT="$SCRIPT_DIR/sync-openclaw.sh"

for path in "$MANIFEST" "$SYNC_SCRIPT"; do
  if [[ ! -f "$path" ]]; then
    echo "[ERROR] Missing required file: $path" >&2
    exit 1
  fi
done

for cmd in openclaw python3 bash; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[ERROR] Required command not found in PATH: $cmd" >&2
    exit 1
  fi
done

# Guard against inherited OPENCLAW_* vars from unrelated sessions/gateways.
OPENCLAW_ENV_KEYS=()
OPENCLAW_ENV_UNSET_ARGS=()
while IFS='=' read -r k _; do
  if [[ "$k" == OPENCLAW_* ]]; then
    OPENCLAW_ENV_KEYS+=("$k")
    OPENCLAW_ENV_UNSET_ARGS+=("-u" "$k")
  fi
done < <(env)

if [[ "${#OPENCLAW_ENV_KEYS[@]}" -gt 0 ]]; then
  echo "[WARN] Detected inherited OPENCLAW_* env vars; safe-sync will ignore them:"
  for k in "${OPENCLAW_ENV_KEYS[@]}"; do
    echo "  - $k"
  done
fi

run_clean() {
  if [[ "${#OPENCLAW_ENV_UNSET_ARGS[@]}" -gt 0 ]]; then
    env "${OPENCLAW_ENV_UNSET_ARGS[@]}" "$@"
  else
    "$@"
  fi
}

oc() {
  run_clean openclaw "$@"
}

echo "[STEP 1/5] Sync OperatorOne config into profile '$PROFILE'"
if [[ "$DRY_RUN" == "1" ]]; then
  run_clean bash "$SYNC_SCRIPT" --profile "$PROFILE" --dry-run
  echo "[DONE] Dry-run finished (gateway actions skipped)."
  exit 0
fi

run_clean bash "$SYNC_SCRIPT" --profile "$PROFILE"

echo "[STEP 2/5] Install/repoint gateway service for profile '$PROFILE'"
oc --profile "$PROFILE" gateway install --force

echo "[STEP 3/5] Restart gateway for profile '$PROFILE'"
oc --profile "$PROFILE" gateway restart

if [[ "$SINGLE_ACTIVE" == "1" ]]; then
  echo "[STEP 4/5] Single-active policy: stop default-profile gateway"
  oc gateway stop >/dev/null || true
else
  echo "[STEP 4/5] Dual-gateway mode allowed: skip stopping default profile gateway"
fi

echo "[STEP 5/5] Verify profile integrity"
python3 - "$MANIFEST" "$REPO_ROOT" "$PROFILE" "$SINGLE_ACTIVE" <<'PY'
import json
import os
import subprocess
import sys

manifest_path, repo_root, profile, single_active_flag = sys.argv[1:5]
single_active = single_active_flag == "1"
clean_env = {k: v for k, v in os.environ.items() if not k.startswith("OPENCLAW_")}

with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

required_agent_ids = [a.get("id") for a in manifest.get("agents", []) if isinstance(a, dict) and a.get("id")]
if not required_agent_ids:
    raise SystemExit("[ERROR] manifest has no agents")


def _clean_cli_output(raw: str):
    lines = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    if not lines:
        return []

    cleaned = []
    for line in lines:
        lo = line.lower()
        if lo.startswith("config warnings"):
            continue
        if line[:1] in {"│", "◇", "╭", "╮", "╰", "╯", "├", "└"}:
            continue
        cleaned.append(line)
    return cleaned or lines


def _extract_json_obj(raw: str):
    text = raw or ""
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        depth = 0
        in_str = False
        esc = False
        for j in range(i, len(text)):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        val = json.loads(text[i:j+1])
                        if isinstance(val, dict):
                            return val
                    except Exception:
                        break
    return None


def run(args, profile_name=None):
    cmd = ["openclaw"]
    if profile_name:
        cmd += ["--profile", profile_name]
    cmd += args
    raw = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, env=clean_env)
    lines = _clean_cli_output(raw)
    return "\n".join(lines).strip()


def run_json(args, profile_name=None):
    out = run(args, profile_name=profile_name)
    try:
        return json.loads(out)
    except Exception:
        maybe = _extract_json_obj(out)
        if isinstance(maybe, dict):
            return maybe
        raise


def run_value(args, profile_name=None):
    out = run(args, profile_name=profile_name)
    if not out:
        return None
    try:
        return json.loads(out)
    except Exception:
        lines = [line for line in out.splitlines() if line.strip()]
        return (lines[-1] if lines else out)


errors = []
notes = []

cfg_path = os.path.abspath(os.path.expanduser(run(["config", "file"], profile_name=profile)))
notes.append(f"profile config file: {cfg_path}")

gw_status = run_json(["gateway", "status", "--json"], profile_name=profile)
cli_cfg = os.path.abspath(os.path.expanduser(str(gw_status.get("config", {}).get("cli", {}).get("path", ""))))
daemon_cfg = os.path.abspath(os.path.expanduser(str(gw_status.get("config", {}).get("daemon", {}).get("path", ""))))
notes.append(f"gateway cli config path: {cli_cfg}")
notes.append(f"gateway daemon config path: {daemon_cfg}")

if cli_cfg != cfg_path:
    errors.append(f"CLI config path mismatch: expected {cfg_path}, got {cli_cfg}")
if daemon_cfg != cfg_path:
    errors.append(f"Daemon config path mismatch: expected {cfg_path}, got {daemon_cfg}")

agents_list = run_value(["config", "get", "agents.list"], profile_name=profile)
if not isinstance(agents_list, list):
    errors.append("agents.list is not an array")
    current_agent_ids = set()
else:
    current_agent_ids = {a.get("id") for a in agents_list if isinstance(a, dict) and a.get("id")}

missing = [aid for aid in required_agent_ids if aid not in current_agent_ids]
if missing:
    errors.append(f"missing agents: {', '.join(missing)}")
else:
    notes.append(f"agents present: {', '.join(required_agent_ids)}")

extra_dirs = run_value(["config", "get", "skills.load.extraDirs"], profile_name=profile)
if extra_dirs is None:
    extra_dirs = []
elif not isinstance(extra_dirs, list):
    extra_dirs = [str(extra_dirs)]

desired_rel = manifest.get("skillsExtraDirs")
if not isinstance(desired_rel, list) or not desired_rel:
    desired_rel = [manifest.get("sharedSkillsDir", "shared/skills")]

desired_extra = [os.path.abspath(os.path.join(repo_root, p)) for p in desired_rel]
actual_extra = [os.path.abspath(os.path.expanduser(str(x))) for x in extra_dirs]

if actual_extra != desired_extra:
    errors.append(f"skills.load.extraDirs mismatch: expected {desired_extra}, got {actual_extra}")
else:
    notes.append(f"skills.load.extraDirs OK: {actual_extra}")

expected_port = manifest.get("gatewayPort")
actual_port = run_value(["config", "get", "gateway.port"], profile_name=profile)
if isinstance(expected_port, int) and actual_port != expected_port:
    errors.append(f"gateway.port mismatch: expected {expected_port}, got {actual_port}")
else:
    notes.append(f"gateway.port: {actual_port}")

expected_model = manifest.get("profileDefaultModel")
actual_model = run_value(["config", "get", "agents.defaults.model.primary"], profile_name=profile)
if isinstance(expected_model, str) and expected_model and actual_model != expected_model:
    errors.append(f"agents.defaults.model.primary mismatch: expected {expected_model}, got {actual_model}")
else:
    notes.append(f"agents.defaults.model.primary: {actual_model}")

expected_fallbacks = manifest.get("profileModelFallbacks")
if isinstance(expected_fallbacks, list):
    normalized_expected = [str(x).strip() for x in expected_fallbacks if str(x).strip()]
    actual_fallbacks = run_value(["config", "get", "agents.defaults.model.fallbacks"], profile_name=profile)
    if actual_fallbacks is None:
        actual_fallbacks = []
    elif not isinstance(actual_fallbacks, list):
        actual_fallbacks = [str(actual_fallbacks)]
    normalized_actual = [str(x).strip() for x in actual_fallbacks if str(x).strip()]
    if normalized_actual != normalized_expected:
        errors.append(
            f"agents.defaults.model.fallbacks mismatch: expected {normalized_expected}, got {normalized_actual}"
        )
    else:
        notes.append(f"agents.defaults.model.fallbacks: {normalized_actual}")

for item in manifest.get("agents", []):
    aid = item.get("id")
    ws_rel = item.get("workspace")
    if not aid or not ws_rel:
        continue
    skill_dir = os.path.join(repo_root, ws_rel, "skills")
    if not os.path.isdir(skill_dir):
        errors.append(f"missing skills directory: {skill_dir}")

seed_auth = bool(manifest.get("seedAuthFromDefaultProfile", False))
if seed_auth:
    src = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
    if os.path.isfile(src):
        state_dir = os.path.dirname(cfg_path)
        for aid in required_agent_ids:
            dst = os.path.join(state_dir, "agents", aid, "agent", "auth-profiles.json")
            if not os.path.isfile(dst):
                errors.append(f"auth seed missing for {aid}: {dst}")
        notes.append("auth seed check completed")
    else:
        notes.append("auth seed source absent in default profile; skipped")

if single_active:
    default_status = run_json(["gateway", "status", "--json"], profile_name=None)
    default_runtime = default_status.get("service", {}).get("runtime", {})
    default_running = str(default_runtime.get("status", "")).lower() == "running"
    if default_running:
        errors.append("single-active policy violated: default-profile gateway is still running")
    else:
        notes.append("single-active policy OK: default-profile gateway not running")

print("[VERIFY] Checklist")
for n in notes:
    print(f"  - {n}")

if errors:
    print("[VERIFY] FAILED")
    for e in errors:
        print(f"  - {e}")
    raise SystemExit(1)

print("[VERIFY] PASSED")
PY

echo "[DONE] OperatorOne safe sync complete for profile '$PROFILE'."
echo "[NEXT] openclaw --profile $PROFILE status"
