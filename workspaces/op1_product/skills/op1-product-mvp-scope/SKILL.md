---
name: op1-product-mvp-scope
description: Convert a selected Stage-2 opportunity into a testable MVP blueprint with strict scope boundaries, pricing hypothesis, success metric, and kill criteria.
---

# MVP Scope Builder (Stage 3)

1. Select one `advance` opportunity from `research/stage2_idea_screening/decision_log.json` (prefer `selection_summary.selected_opportunity_id`).
2. Build blueprint from template:
   - `../../framework/templates/stage3_project_blueprint.template.json`
3. Fill mandatory hypothesis block:
   - `hypothesis.for_segment`
   - `hypothesis.problem`
   - `hypothesis.value_proposition`
4. Define strict MVP boundary:
   - `mvp_boundary.in_scope`
   - `mvp_boundary.out_of_scope`
5. Define 14-day test design:
   - `test_design_14d.experiment`
   - `test_design_14d.channel`
   - `test_design_14d.sample_target`
   - `test_design_14d.offer`
6. Define validation economics + decision rules:
   - `pricing_hypothesis`
   - `success_metric`
   - `kill_criteria`
7. Add downstream handoff-ready inputs:
   - `downstream_inputs.marketing`
   - `downstream_inputs.operations`
8. Write output to `research/stage3_mvp_scope/project_blueprint.json`.

## Quality bar
- Scope is buildable by a small team in <=14 days.
- Success metric is measurable and decision-useful.
- Kill criteria are explicit stop conditions (not vague quality language).
- `in_scope`/`out_of_scope` do not conflict.
- Blueprint can be consumed directly by landing/build pipelines without extra manual interpretation.
