# OperatorOne Runbook

## First-Time Setup (per machine, Profile-B)

1. Clone repo to:
   - `~/.openclaw/workspace/OperatorOne`
2. Run safe one-command sync in dedicated profile (`operatorone`):
   - `bash openclaw/sync-operatorone-safe.sh`
3. Verify operatorone profile:
   - `openclaw --profile operatorone status`
   - `openclaw --profile operatorone agents list`
4. Open a fresh chat session (`/new` or `/reset`) before using new agents/skills.

Advanced:
- Config-only sync (no service actions): `bash openclaw/sync-openclaw.sh`
- Allow dual gateways (override default single-active policy): `bash openclaw/sync-operatorone-safe.sh --allow-dual-gateway`

## Web Visibility Rule

- Web UI / Web Chat displays agents from the active gateway profile only.
- If `op1_*` agents are not visible, check profile context first:
  - `openclaw config file`
  - `openclaw --profile operatorone config file`
  - `openclaw --profile operatorone agents list`

## If you previously synced OperatorOne into default profile

Run cleanup once (optional but recommended):

- `bash openclaw/cleanup-default-profile.sh`

This removes OperatorOne manifest agents (`op1_product`, `op1_marketing`, `op1_sales`, `op1_operations`) and OperatorOne shared skill path from the default profile only.

## Daily Work

- Work in your owned agent workspace.
- Agent-specific skills go in:
  - `workspaces/op1_product/skills/`
  - `workspaces/op1_marketing/skills/`
  - `workspaces/op1_sales/skills/`
  - `workspaces/op1_operations/skills/`
- Cross-agent reusable skills go in:
  - `shared/skills/`
- Commit locally as needed.
- Push only when ready (milestone/PR time).

## Safety

- `sync-openclaw.sh` is non-destructive by design:
  - Creates missing agents only
  - Does not overwrite conflicting workspace pointers
  - Replaces `skills.load.extraDirs` inside the **operatorone profile only**
  - Sets operatorone profile defaults (`agents.defaults.workspace`, `gateway.port`, `agents.defaults.model.primary`) from manifest
  - Best-effort auth seeding: copies default profile main auth into `op1_*` agentDirs only when target auth file is missing
  - Strips inherited `OPENCLAW_*` env vars before all CLI reads/writes to avoid profile drift
  - Never edits default-profile `channels.*`, `gateway.*`, `auth.*`

- `sync-operatorone-safe.sh` adds operational safety:
  - Runs sync + gateway install/restart in one entrypoint
  - Default single-active mode stops default-profile gateway to avoid dual-gateway confusion
  - Verifies config path alignment (CLI path == daemon path == operatorone config)

- `cleanup-default-profile.sh` targets default profile only:
  - Removes OperatorOne manifest agents from default profile (`op1_product`, `op1_marketing`, `op1_sales`, `op1_operations`)
  - Removes OperatorOne shared skill dir from default `skills.load.extraDirs`
  - Cleans `main.subagents.allowAgents` entries for those OperatorOne agents
  - Never touches `channels.*`, `gateway.*`, `auth.*`
