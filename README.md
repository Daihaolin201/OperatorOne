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

## Skills Layout

- Agent-specific skills:
  - `workspaces/op1_product/skills/`
  - `workspaces/op1_marketing/skills/`
  - `workspaces/op1_sales/skills/`
  - `workspaces/op1_operations/skills/`
- Shared reusable skills:
  - `shared/skills/`

## Quick Start (local, Profile-B isolation)

1. Clone into:
   - `~/.openclaw/workspace/OperatorOne`
2. Run the safe one-command sync (dedicated profile `operatorone`, default single-active gateway):
   - `bash openclaw/sync-operatorone-safe.sh`
3. Verify isolated profile:
   - `openclaw --profile operatorone status`
   - `openclaw --profile operatorone agents list`
4. Start a fresh chat session:
   - `/new`

Advanced:
- Config-only sync (no gateway restart): `bash openclaw/sync-openclaw.sh`
- Allow dual gateways temporarily: `bash openclaw/sync-operatorone-safe.sh --allow-dual-gateway`

## Web UI / Web Chat Visibility (Important)

- Web side only shows agents from the **currently running gateway profile**.
- If you are connected to default profile, you will not see `op1_*` agents.
- Always use `openclaw --profile operatorone ...` when operating OperatorOne.

## Dashboard / Venture Studio

OperatorOne now includes a local dashboard with two layers:
- Monitor: 4-agent capability monitoring (12 capabilities), handoff I/O visibility, readiness gates
- Studio: human-in-the-loop pipeline from startup idea selection to Product/Marketing/Sales/Operations iteration

Run:
- `python3 dashboard/server.py --host 127.0.0.1 --port 8765`
- Open: `http://127.0.0.1:8765`

See `dashboard/README.md` for details.

## Collaboration

See:
- `docs/collaboration.md`
- `openclaw/FRIEND_SYNC_PROMPT.zh.md`
