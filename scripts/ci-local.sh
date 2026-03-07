#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0
SKIPPED=0

_green='\033[0;32m'
_red='\033[0;31m'
_yellow='\033[0;33m'
_bold='\033[1m'
_reset='\033[0m'

stage_pass() { echo -e "${_green}[PASS]${_reset} $1"; PASS=$((PASS + 1)); }
stage_fail() { echo -e "${_red}[FAIL]${_reset} $1"; FAIL=$((FAIL + 1)); }
stage_skip() { echo -e "${_yellow}[SKIP]${_reset} $1"; SKIPPED=$((SKIPPED + 1)); }

echo -e "${_bold}OperatorOne CI — local run${_reset}"
echo "Repo: ${REPO_ROOT}"
echo "Date: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "────────────────────────────────────────"

echo ""
echo -e "${_bold}Stage: lint${_reset}"
if [ -f "${REPO_ROOT}/pnpm-lock.yaml" ] && command -v pnpm &>/dev/null; then
  if pnpm ls --filter='*' 2>/dev/null | grep -q eslint; then
    if (cd "${REPO_ROOT}" && pnpm turbo run lint --affected 2>&1); then
      stage_pass "lint"
    else
      stage_fail "lint"
    fi
  else
    stage_skip "lint — ESLint not yet configured (placeholder until T8)"
  fi
else
  stage_skip "lint — pnpm workspace not yet bootstrapped (placeholder until T8)"
fi

echo ""
echo -e "${_bold}Stage: typecheck${_reset}"
if [ -f "${REPO_ROOT}/pnpm-lock.yaml" ] && command -v pnpm &>/dev/null; then
  if pnpm ls --filter='*' 2>/dev/null | grep -q typescript; then
    if (cd "${REPO_ROOT}" && pnpm turbo run typecheck --affected 2>&1); then
      stage_pass "typecheck"
    else
      stage_fail "typecheck"
    fi
  else
    stage_skip "typecheck — TypeScript not yet configured (placeholder until T8)"
  fi
else
  stage_skip "typecheck — pnpm workspace not yet bootstrapped (placeholder until T8)"
fi

echo ""
echo -e "${_bold}Stage: test${_reset}"
if [ -f "${REPO_ROOT}/pnpm-lock.yaml" ] && command -v pnpm &>/dev/null; then
  if pnpm ls --filter='*' 2>/dev/null | grep -q vitest; then
    if (cd "${REPO_ROOT}" && pnpm turbo run test --affected 2>&1); then
      stage_pass "test"
    else
      stage_fail "test"
    fi
  else
    stage_skip "test — Vitest not yet configured (placeholder until T9)"
  fi
else
  stage_skip "test — pnpm workspace not yet bootstrapped (placeholder until T9)"
fi

echo ""
echo -e "${_bold}Stage: contracts${_reset}"
if (cd "${REPO_ROOT}" && python3 scripts/validate_handoffs.py --repo-root . 2>&1); then
  stage_pass "contracts"
else
  stage_fail "contracts"
fi

echo ""
echo -e "${_bold}Stage: hygiene${_reset}"
STAGED_FILES=$(git -C "${REPO_ROOT}" diff --cached --name-only 2>/dev/null || true)
if [ -z "${STAGED_FILES}" ]; then
  stage_skip "hygiene — no staged files (pre-commit guard; run after git add)"
else
  if (cd "${REPO_ROOT}" && python3 scripts/change_hygiene_guard.py --staged 2>&1); then
    stage_pass "hygiene"
  else
    stage_fail "hygiene"
  fi
fi

echo ""
echo "────────────────────────────────────────"
echo -e "Results: ${_green}${PASS} passed${_reset}  ${_red}${FAIL} failed${_reset}  ${_yellow}${SKIPPED} skipped${_reset}"

if [ "${FAIL}" -gt 0 ]; then
  echo -e "${_red}CI FAILED${_reset} — ${FAIL} stage(s) failed"
  exit 1
else
  echo -e "${_green}CI PASSED${_reset}"
  exit 0
fi
