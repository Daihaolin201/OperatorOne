# OperatorOne Agent Rules

## Project Boundary

- Active worktree: `/Users/dennisli/Developer/OperatorOne`
- OneDrive record folder: `/Users/dennisli/Library/CloudStorage/OneDrive-个人/文件管理/600_工作台/620_项目/20260301UK AI Agent Hackathon EP4 x OpenClaw/00_Project_Record`
- GitHub remote: `https://github.com/Daihaolin201/OperatorOne.git`
- Current collaboration branch: `dennis/automation-framework`

This GitHub repository is currently public. Do not commit real API keys, customer data, private credentials, personal exports, or unreleased private notes.

## Engineering Rules

- This is a pnpm/Turborepo plus Python dashboard/agent orchestration repo.
- `workspaces/op1_*` contain agent role logic and generated audit artifacts; preserve reproducibility snapshots when they are intentionally tracked.
- Runtime state, `.env*`, `node_modules`, `.venv`, dashboard runtime folders, `.sisyphus`, and local OpenClaw sync folders stay out of Git.
- External actions must remain gated. Never make email, deploy, or API-costing paths run silently without explicit approval/config.

## Checks

Minimum checks after relevant edits:

```bash
pnpm install --frozen-lockfile
pnpm turbo run lint --affected
pnpm turbo run typecheck --affected
pnpm turbo run test --affected
python3 scripts/validate_handoffs.py --repo-root .
python3 -m pytest dashboard/tests/ -q
```

If dependency install is skipped, record that explicitly in `PROJECT_LOG.md`.

## GitHub Actions Cost Control

- Routine workflows must stay Ubuntu-only and short-timeout.
- Do not add scheduled workflows without recording the business reason and expected cost.
- Every workflow should use `concurrency` with `cancel-in-progress: true`.
- PR checks should validate contracts and critical paths; heavy external/API workflows must stay manual or dry-run.
