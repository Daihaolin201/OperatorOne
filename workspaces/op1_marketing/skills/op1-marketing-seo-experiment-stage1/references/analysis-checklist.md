# Analysis Checklist (1/2/3 Rounds)

Use this checklist after `run_rounds_123.py`.

## Round-level sanity
- All rounds return `status = passed`.
- Round2 has context/keyword/experiment counts greater than or equal to Round1.
- Round3 returns to Round1 counts after restoring the handoff baseline.

## Determinism checks
- `R1 vs R3 queue counts` are equal.
- `R1 vs R3 scoreboard summary` is equal.
- `R1 vs R3 keyword_graph hash` is equal.
- `R1 vs R3 queue hash` is equal.

## Sensitivity checks
- `R2 vs R1 queue hash` differs.
- New contexts/experiments in Round2 can be traced to the injected handoff context.

## Reporting format
Report at minimum:
- Queue split per round (Ready/Hold/Drop)
- Average overall score per round
- Determinism and sensitivity check booleans
- Path to the generated report bundle under `research/stage1_marketing_seo/rounds/<timestamp>/`
