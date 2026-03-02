# OperatorOne Runbook

## First-Time Setup (per machine, Profile-B)

1. Clone repo to:
   - `~/.openclaw/workspace/OperatorOne`
2. Run one-time sync in dedicated profile (`operatorone`):
   - `bash openclaw/sync-openclaw.sh`
3. Install/repoint gateway service to operatorone profile:
   - `openclaw --profile operatorone gateway install --force`
4. Restart operatorone gateway:
   - `openclaw --profile operatorone gateway restart`
5. Verify operatorone profile:
   - `openclaw --profile operatorone status`
   - `openclaw --profile operatorone agents list`
6. Open a fresh chat session (`/new` or `/reset`) before using new agents/skills.

## Web Visibility Rule

- Web UI / Web Chat displays agents from the active gateway profile only.
- If `op1_*` agents are not visible, check profile context first:
  - `openclaw config file`
  - `openclaw --profile operatorone config file`
  - `openclaw --profile operatorone agents list`

## If you previously synced OperatorOne into default profile

Run cleanup once (optional but recommended):

- `bash openclaw/cleanup-default-profile.sh`

This removes `op1_*` agents and OperatorOne shared skill path from the default profile only.

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
  - Never edits default-profile `channels.*`, `gateway.*`, `auth.*`
