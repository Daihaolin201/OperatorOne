---
name: op1-product-idea-screening
description: Score and prioritize startup opportunities with an explicit weighted framework. Use when selecting which Stage-1 opportunities should advance into MVP design (Stage 3).
---

# Idea Screening (Stage 2)

1. Read Stage-1 input:
   - `research/stage1_opportunity_records.json`
2. Run scoring with explicit config:
   - `python3 scripts/score_stage2.py --input research/stage1_opportunity_records.json --weights framework/config/scoring_weights.default.json --trust-config framework/config/source_trust_rank.json --csv-out research/stage2_scoring.csv --json-out research/stage2_decision_log.json`
3. Review outputs:
   - `research/stage2_scoring.csv`
   - `research/stage2_decision_log.json`
4. Verify per-opportunity decision packet includes:
   - `hard_gate_pass`
   - `evidence_gate` (`stage1_pass`, `loss_signal_ok`, `budget_or_intent_ok`)
   - `confidence` (`level`, `multiplier`, `reason`)
   - per-dimension `score`, `reason`, `risk_if_wrong`
   - final `decision` and `decision_reason`
5. Verify ranking summary exists and is coherent:
   - `selection_summary.top_ranked_opportunity_id`
   - `selection_summary.runner_up_opportunity_id`
   - `selection_summary.score_gap_vs_runner_up`
   - `selection_summary.why_top_beats_runner_up`
6. If top-vs-runner gap is narrow, add manual review notes before advancing.

## Quality bar
- No generic comments; tie scores and decisions to evidence.
- Top-ranked idea must explicitly beat runner-up with auditable reasoning.
- Rejections/holds must include concrete rationale and risk notes.
