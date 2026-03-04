---
name: op1-product-mvp-scope
description: Convert a selected Stage-2 opportunity into a testable MVP blueprint with strict scope boundaries, pricing hypothesis, success metric, and kill criteria.
---

# MVP Scope Builder (Stage 3)

1. Select one `advance` opportunity from `research/stage2_decision_log.json` (prefer top-ranked selection summary).
2. Build a 14-day blueprint using:
   - `../../framework/templates/stage3_project_blueprint.template.json`
3. Define strict scope boundaries:
   - `in_scope`
   - `out_of_scope`
4. Define paid-validation setup:
   - channel
   - target sample
   - offer
5. Define success metric and kill criteria before execution.
6. Write output to `research/stage3_project_blueprint.json`.

## Quality bar
- Scope is buildable by a small team in <=14 days.
- Success metric is measurable and decision-useful.
- Kill criteria are explicit stop conditions (not vague quality language).
