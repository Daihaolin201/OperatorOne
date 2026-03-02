# OperatorOne

Built by Dennis and Bennett.

OperatorOne is a 4-agent OpenClaw startup builder focused on going from idea -> launch -> first customers, targeting the first **$100 MRR** milestone.

## Agent Roles

- `op1_product`: startup ideas + MVP definition + landing brief
- `op1_marketing`: SEO/content/campaign experiments
- `op1_sales`: prospecting + outreach + early conversion
- `op1_operations`: KPI tracking + feedback loop + iteration

## Repository Layout

- `openclaw/` - safe sync tooling and machine setup docs
- `workspaces/` - isolated workspace context per agent
- `shared/` - shared skills/prompts/templates
- `handoffs/` - structured inter-agent transfer files
- `docs/` - architecture/collaboration/runbook

## Quick Start (local)

1. Clone into:
   - `~/.openclaw/workspace/OperatorOne`
2. Run one-time non-destructive sync:
   - `bash openclaw/sync-openclaw.sh`
3. Restart gateway:
   - `openclaw gateway restart`
4. Start a fresh chat session:
   - `/new`

## Collaboration

See:
- `docs/collaboration.md`
- `openclaw/FRIEND_SYNC_PROMPT.zh.md`
