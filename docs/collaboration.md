# Collaboration Protocol (Dennis + Bennett)

## Ownership

- Bennett: `workspaces/op1_product/**`, `workspaces/op1_operations/**`
- Dennis: `workspaces/op1_marketing/**`, `workspaces/op1_sales/**`
- Shared ownership: `shared/**`, `handoffs/**`, `openclaw/**`, `docs/**`

## Branching

- Default branch: `main`
- Feature branches:
  - `feat/product/<topic>`
  - `feat/marketing/<topic>`
  - `feat/sales/<topic>`
  - `feat/operations/<topic>`
  - `feat/integration/<topic>` (only for cross-agent orchestration)

## Pull Request Rules

- Normal PR: modify only one `workspaces/op1_*` domain (+ tiny shared fix if required).
- Cross-domain PR: use `feat/integration/*` and request both reviewers.
- Changes to `openclaw/sync-openclaw.sh` or `openclaw/agents.manifest.json` require both reviewers.

## Push Policy

- Default: local commits are allowed; **no push by default**.
- Only push when both collaborators explicitly agree (or when release/merge window starts).
- During focused build windows (e.g. next 2 days), keep changes local and batch-push at merge time.

## Commit Style

- `feat(product): ...`
- `feat(marketing): ...`
- `feat(sales): ...`
- `feat(operations): ...`
- `chore(openclaw): ...`
- `docs: ...`
