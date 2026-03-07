# Reproducibility Guide

## Why reproducibility matters
This skill is designed to be rerun with stable outputs for audits and demos.

## Determinism controls
- Fixed timestamp support via environment variable `STAGE3_AS_OF`.
- Orchestrator option `--as-of` sets this automatically.
- In simulate mode, conversion events are not appended, which preserves event state.

## Reproducibility verification
Run:

```bash
python3 workspaces/op1_sales/skills/convert-early-customers-stage3/scripts/verify_reproducibility_stage3.py \
  --repo-root <repo_root> \
  --as-of 2026-03-05T00:00:00+00:00
```

The verifier:
1. Executes two fixed-time simulate runs.
2. Hash-compares core output artifacts.
3. Checks DoD subset constraints (traceability, next actions, onboarding fields, scoreboard completeness).
4. Writes:
   - `workspaces/op1_sales/research/conversion/reproducibility_report.latest.json`
   - `workspaces/op1_sales/research/conversion/reproducibility_report.latest.md`

## Practical rule
- For production progression use `--mode commit` (real state updates).
- For repeatable analysis and demonstrations use `--mode simulate --as-of <fixed-ts>`.
