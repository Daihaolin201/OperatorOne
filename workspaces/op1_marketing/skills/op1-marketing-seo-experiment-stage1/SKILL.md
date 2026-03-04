---
name: op1-marketing-seo-experiment-stage1
description: Run and audit OperatorOne Stage1 marketing SEO shadow experiments across input sync, context index, keyword graph, experiment synthesis, and Ready/Hold/Drop queueing. Use when asked to run SEO experiments, execute 1/2/3 validation rounds, verify reproducibility, or summarize queue and scoreboard outputs for op1_marketing.
---

# Stage1 SEO Experiment Runner (Shadow)

## Objective
Run the Stage1 SEO pipeline in shadow mode and produce auditable artifacts under `research/stage1_marketing_seo/`.

## Single-cycle run
From workspace root:

```bash
./scripts/run_marketing_seo_stage1.sh --mode shadow --force
```

Check:
- `research/stage1_marketing_seo/run.latest.json`
- `research/stage1_marketing_seo/experiments.queue.latest.json`
- `research/stage1_marketing_seo/scoreboard.latest.json`
- `research/stage1_marketing_seo/decision_log.latest.md`

## 1/2/3 validation run
Use the bundled helper:

```bash
python3 {baseDir}/scripts/run_rounds_123.py
```

This executes:
1. Round1 baseline
2. Round2 controlled handoff perturbation
3. Round3 baseline restore + rerun

Then it writes snapshot artifacts and validation checks to:
- `research/stage1_marketing_seo/rounds/<timestamp>/rounds_1_2_3.report.md`
- `research/stage1_marketing_seo/rounds/<timestamp>/rounds_1_2_3.report.json`

Expected checks:
- `R1 == R3` for queue/content reproducibility
- `R2 != R1` for input-sensitivity

## Guardrails
- Keep mode as `shadow` for Stage1 capability validation.
- Treat this as experiment generation/scoring/queueing only (not auto publish).
- If run status is `blocked_input_incomplete`, stop and report missing requirements from `run.latest.json.input_sync.completeness`.

## References
- `references/stage1-output-contract.md`
- `references/analysis-checklist.md`
