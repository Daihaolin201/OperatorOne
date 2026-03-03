---
name: op1-product-idea-screening
description: Score and prioritize startup opportunities with an explicit weighted framework. Use when selecting which product idea should advance from discovery into MVP design.
---

# Idea Screening

1. Read stage-1 records from `research/stage1_opportunity_records.json`.
2. Load weights from `../../../framework/config/scoring_weights.default.json` (or custom file).
3. Run scoring script:
   - `python3 scripts/score_stage2.py`
4. Review generated outputs and adjust any heuristic scores with human judgment where needed:
   - `research/stage2_scoring.csv`
   - `research/stage2_decision_log.json`
5. Ensure each score dimension includes:
   - numeric score (1-5)
   - concrete reason
   - risk if wrong
6. Enforce gate check before scoring decision: `hard_gate_check.min_distinct_sources_met` must be true.
7. Set decision per opportunity: `advance | hold | reject`.

## Quality bar
- No generic comments like “seems good”; always tie to evidence.
- Always state why top-ranked idea beats runner-up.
- Always include rejection rationale for non-selected ideas.
