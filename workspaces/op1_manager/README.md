# op1_manager — Control-Plane Workspace

`op1_manager` is the cross-agent management workspace for OperatorOne.

Unlike specialist agents (`op1_product`, `op1_marketing`, `op1_sales`, `op1_operations`), this workspace focuses on:

- cross-workspace audits,
- documentation coherence,
- architecture/runbook updates,
- orchestration support and quality review.

## Position in system

- Not part of `openclaw/agents.manifest.json` by default.
- Used as local control plane for repo-level tasks.
- Should avoid taking ownership of specialist domain execution artifacts.

## Typical responsibilities

1. Audit handoff/data flow consistency across agents.
2. Identify stale/missing docs (README, STAGE_INDEX, runbook drift).
3. Prepare integration-level refactors (paths/contracts/docs).
4. Keep architecture and runbook aligned with actual scripts.

## Recommended workflow

From repo root:

```bash
git status --short
find workspaces -maxdepth 2 -name README.md | sort
find workspaces -maxdepth 3 -path "*/research/STAGE_INDEX.md" | sort
```

Then update:

- root `README.md`
- `docs/architecture.md`
- `docs/runbook.md`
- `handoffs/README.md`
- workspace README/STAGE_INDEX files as needed

## Guardrails

- Prefer docs/contracts/coordination changes over specialist artifact edits.
- If changing handoff schema, update all affected docs and consumers together.
- Keep commits narrowly scoped and reviewable (avoid mixing generated `.latest` artifacts with doc refactors).