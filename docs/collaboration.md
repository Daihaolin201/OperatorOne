# Collaboration Protocol (Dennis + Bennett)

## 1) Ownership boundaries

### Primary ownership

- Bennett:
  - `workspaces/op1_product/**`
  - `workspaces/op1_operations/**`
- Dennis:
  - `workspaces/op1_marketing/**`
  - `workspaces/op1_sales/**`

### Shared ownership

- `workspaces/op1_manager/**`
- `handoffs/**`
- `docs/**`
- `dashboard/**`
- `openclaw/**`
- `shared/**`

---

## 2) Branch conventions

- Default branch: `main`
- Feature branches:
  - `feat/product/<topic>`
  - `feat/marketing/<topic>`
  - `feat/sales/<topic>`
  - `feat/operations/<topic>`
  - `feat/manager/<topic>`
  - `feat/dashboard/<topic>`
  - `feat/integration/<topic>` (cross-agent orchestration / contract changes)

---

## 3) PR rules

### Single-domain PRs

- Modify one specialist workspace only (+ minimal related test/doc fix).

### Cross-domain PRs

Use `feat/integration/*` and include clear impact notes for:

- changed handoff contracts,
- changed output paths,
- changed stage run semantics.

### Mandatory dual review

Changes touching any of the following require both collaborators:

- `handoffs/*.json`
- `openclaw/agents.manifest.json`
- `openclaw/sync-*.sh`
- `docs/architecture.md`
- `docs/runbook.md`

---

## 4) Contract gate rule

For any PR touching handoff producers or `handoffs/*.json`:

- Run locally: `python3 scripts/validate_handoffs.py --repo-root .`
- Keep `contract_version/generated_at/generated_by` fields valid.
- CI workflow `handoff-contract-validation` must pass.

For any PR with broad execution output churn:

- Run: `python3 scripts/change_hygiene_guard.py --staged`
- Split source/config/docs changes and generated artifact refreshes into separate commits/PRs.
- CI workflow `change-hygiene` must pass on PRs (push runs are informational for snapshot branches).

## 5) Documentation parity rule

If a PR changes runtime behavior, update docs in the same PR.

- Command/path changes → workspace README + `docs/runbook.md`
- Contract key/schema changes → `handoffs/README.md` + `docs/architecture.md`
- Topology changes (agent/workspace add/remove) → root `README.md` + architecture + manifest (if synced)

No "docs later" for architecture/contract changes.

---

## 6) Runtime convention

Always run OperatorOne with dedicated profile:

- `openclaw --profile operatorone ...`

Avoid using default profile for OperatorOne operations.

---

## 7) Push policy

- Local commits are encouraged.
- Push/merge timing should be coordinated (batch by milestone when possible).
- Avoid pushing partially coherent contract changes across multiple agents.

---

## 8) Commit style

- `feat(product): ...`
- `feat(marketing): ...`
- `feat(sales): ...`
- `feat(operations): ...`
- `feat(manager): ...`
- `feat(integration): ...`
- `chore(openclaw): ...`
- `docs: ...`