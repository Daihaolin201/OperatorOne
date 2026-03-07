# OperatorOne Docs Index

This folder contains the **project-level source of truth** for architecture, collaboration, and operations.

## Core docs

- `architecture.md`  
  System design for control-plane + specialist execution-plane, handoff topology, and artifact conventions.

- `collaboration.md`  
  Ownership boundaries, branch conventions, and PR/merge rules.

- `runbook.md`  
  Setup, daily operation commands, health checks, and troubleshooting.

- `architecture_logic_audit_2026-03-07.md`  
  Strict architecture/logic audit with priority remediation list.

## Dashboard / studio docs

- `dashboard_v1_architecture.md`  
  Monitor/dashboard rationale and policy design.

- `studio_phase0_product_spec.md`  
  Product spec for Studio objects/state machine.

- `studio_usage_guide.md`  
  Practical guide for running Studio workflows.

- `studio_optimization_report.md`  
  Iterative optimization notes.

## How to keep docs coherent

When you change one of these, update related docs in the same PR:

1. **Handoff contract changes** (`handoffs/*.json` schema/keys)  
   - Update: `handoffs/README.md`, `docs/architecture.md`, relevant workspace README.

2. **Pipeline command or output path changes**  
   - Update: `docs/runbook.md` + the owning workspace README + stage index file.

3. **Agent topology changes** (add/remove workspace/agent)  
   - Update: root `README.md`, `docs/architecture.md`, `openclaw/agents.manifest.json` (if synced agent).

4. **Dashboard action/gate changes**  
   - Update: `dashboard/README.md` and `docs/dashboard_v1_architecture.md`.

5. **Handoff producer changes** (`product_to_marketing`, `marketing_to_sales`, etc.)
   - Run: `python3 scripts/validate_handoffs.py --repo-root .`
   - If legacy files miss metadata fields, run: `python3 scripts/upgrade_handoffs.py --repo-root .`

If docs and runtime drift, runtime wins temporarily—but docs must be fixed in the same development cycle.