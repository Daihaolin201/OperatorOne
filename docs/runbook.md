# OperatorOne Runbook

## First-Time Setup (per machine)

1. Clone repo to:
   - `~/.openclaw/workspace/OperatorOne`
2. Run one-time sync:
   - `bash openclaw/sync-openclaw.sh`
3. Restart gateway:
   - `openclaw gateway restart`
4. Open a fresh chat session (`/new` or `/reset`) before using new agents/skills.

## Daily Work

- Work in your owned agent workspace.
- Commit locally as needed.
- Push only when ready (milestone/PR time).

## Safety

- Script is additive and non-destructive by design:
  - Creates missing agents only
  - Appends shared skills dir only
  - Never rewrites channel/auth/gateway sections
