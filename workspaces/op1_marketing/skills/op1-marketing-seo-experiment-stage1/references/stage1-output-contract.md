# Stage1 Output Contract (op1_marketing)

## Canonical outputs
- `research/stage1_marketing_seo/run.latest.json`
- `research/stage1_marketing_seo/state.latest.json`
- `research/stage1_marketing_seo/context_index.latest.json`
- `research/stage1_marketing_seo/keyword_graph.latest.csv`
- `research/stage1_marketing_seo/experiments.backlog.latest.json`
- `research/stage1_marketing_seo/experiments.queue.latest.json`
- `research/stage1_marketing_seo/scoreboard.latest.json`
- `research/stage1_marketing_seo/decision_log.latest.md`
- `research/stage1_marketing_seo/briefs/`

## Queue semantics
Decision logic in Stage1 scoring:
- `ready`: `overall_score >= 75` and `execution_risk_penalty <= 70`
- `hold`: `overall_score >= 58` and not ready
- `drop`: otherwise

Lifecycle note:
- `ready` entries with `overall_score >= 82` are marked `shadow_validated`.

## Gate condition
If any required input is missing, Stage1 writes blocked outputs and sets status:
- `blocked_input_incomplete`

Required input completeness is reported in:
- `run.latest.json.input_sync.completeness`
