#!/usr/bin/env bash
set -euo pipefail

APP_DIR=""
LOG_DIR=""
TARGET="preview"
VERCEL_PROJECT=""
START_DIR="$(pwd)"

usage() {
  cat <<'USAGE'
Usage:
  scripts/deploy_web_product.sh --app-dir <path> [--log-dir <path>] [--target production|preview] [--vercel-project <name>]

Description:
  Deploys a scaffolded web product to Vercel and prints the deployment URL to stdout.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-dir)
      APP_DIR="$2"
      shift 2
      ;;
    --log-dir)
      LOG_DIR="$2"
      shift 2
      ;;
    --target)
      TARGET="$2"
      shift 2
      ;;
    --vercel-project)
      VERCEL_PROJECT="$2"
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

if [[ -z "$APP_DIR" ]]; then
  echo "Missing required argument: --app-dir" >&2
  exit 2
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "App directory does not exist: $APP_DIR" >&2
  exit 2
fi

if [[ "$TARGET" != "production" && "$TARGET" != "preview" ]]; then
  echo "Invalid --target: $TARGET (expected production|preview)" >&2
  exit 2
fi

APP_DIR="$(cd "$APP_DIR" && pwd)"

if [[ -z "$LOG_DIR" ]]; then
  LOG_DIR="$APP_DIR/../build_deploy_v1_logs"
elif [[ "$LOG_DIR" != /* ]]; then
  LOG_DIR="$START_DIR/$LOG_DIR"
fi
mkdir -p "$LOG_DIR"

if ! command -v vercel >/dev/null 2>&1; then
  echo "vercel CLI not found. Install with: npm i -g vercel" >&2
  exit 3
fi

if ! vercel whoami >/dev/null 2>&1; then
  echo "vercel auth missing. Run: vercel login" >&2
  exit 3
fi

timestamp="$(date -u +"%Y%m%dT%H%M%SZ")"
log_file="$LOG_DIR/deploy_${timestamp}.log"

pushd "$APP_DIR" >/dev/null

# Link project non-interactively. If deterministic project name is provided, enforce it.
if [[ -n "$VERCEL_PROJECT" ]]; then
  {
    echo "[info] Linking to Vercel project: $VERCEL_PROJECT"
    vercel link --yes --project "$VERCEL_PROJECT" || true
  } >>"$log_file" 2>&1
elif [[ ! -f ".vercel/project.json" ]]; then
  {
    echo "[info] Linking project non-interactively (default scope/settings)."
    vercel link --yes || true
  } >>"$log_file" 2>&1
fi

deploy_cmd=(vercel deploy --yes)
if [[ "$TARGET" == "production" ]]; then
  deploy_cmd+=(--prod)
fi

# Vercel CLI writes deploy URL to stdout; logs mostly to stderr.
set +e
deploy_stdout="$(${deploy_cmd[@]} 2>>"$log_file")"
exit_code=$?
set -e

echo "$deploy_stdout" >>"$log_file"

if [[ $exit_code -ne 0 ]]; then
  echo "Deployment failed. See log: $log_file" >&2
  popd >/dev/null
  exit $exit_code
fi

url="$(echo "$deploy_stdout" | tr -d '\r' | grep -Eo 'https://[^[:space:]]+' | tail -n 1 || true)"

if [[ -z "$url" ]]; then
  url="$(grep -Eo 'https://[^[:space:]]+\.vercel\.app[^[:space:]]*' "$log_file" | tail -n 1 || true)"
fi

if [[ -z "$url" ]]; then
  echo "Unable to parse deployment URL. See log: $log_file" >&2
  popd >/dev/null
  exit 4
fi

# Prefer a public production alias when available (some deployment URLs can be SSO-protected).
public_url="$url"
inspect_output="$(vercel inspect "$url" 2>&1 || true)"
echo "$inspect_output" >>"$log_file"
if [[ -n "$inspect_output" ]]; then
  while IFS= read -r candidate; do
    if [[ "$candidate" != "$url" ]]; then
      public_url="$candidate"
      break
    fi
  done < <(echo "$inspect_output" | grep -Eo 'https://[A-Za-z0-9.-]+\.vercel\.app' | awk '!seen[$0]++')

  if [[ "$public_url" == "$url" ]]; then
    project_name="$(echo "$inspect_output" | sed -n 's/^[[:space:]]*name[[:space:]]*\([^[:space:]]*\).*$/\1/p' | head -n1)"
    if [[ -n "$project_name" ]]; then
      canonical="$(echo "$project_name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]//g')"
      if [[ -n "$canonical" ]]; then
        candidate="https://${canonical}.vercel.app"
        code="$(curl -s -o /dev/null -w '%{http_code}' "$candidate" || true)"
        if [[ "$code" =~ ^(2|3) ]]; then
          public_url="$candidate"
        fi
      fi
    fi
  fi
fi

# Emit machine-readable helper JSON alongside log for downstream scripts.
cat >"$LOG_DIR/deploy_latest.json" <<JSON
{
  "deployed_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "target": "$TARGET",
  "vercel_project": "$VERCEL_PROJECT",
  "app_dir": "$(pwd)",
  "deployment_url": "$url",
  "public_url": "$public_url",
  "log_file": "$log_file"
}
JSON

popd >/dev/null

echo "$public_url"
