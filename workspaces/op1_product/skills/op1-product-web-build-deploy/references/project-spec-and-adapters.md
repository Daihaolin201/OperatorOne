# Project Spec + Page Spec + Adapter Model

## Project Spec contract
Use `framework/contracts/build_deploy_project_spec.v1.schema.json` as canonical business structure.

Required high-level sections:
- source/opportunity metadata
- segment + problem + value proposition
- offer (headline + CTA)
- workflow rules + default response
- metrics + kill criteria
- pricing hypothesis
- adapter metadata
- business test cases
- page-strategy hints (`page_profile`, `proof_points`, `faq`, `operational_checklist`, optional CTA support text)

## Page Spec contract
Use `framework/contracts/build_deploy_page_spec.v1.schema.json` for rendering strategy.

Page spec controls:
- layout profile selection
- theme tokens
- module order
- module props payload
- strategy test expectations (`expected_modules`, primary CTA constraints)

## Adapter library
Location: `framework/build_deploy/adapters/*.json`

Current adapters:
- `invoice-followup`
- `chargeback-response`
- `client-reporting`
- `generic-operator`

Each adapter includes:
- keyword matcher hints
- workflow rule engine payload (`workflow.rules`)
- business test seeds
- page strategy defaults (`page_profile`, proof/FAQ/checklists)

## Selection strategy
- If adapter is forced: use forced adapter.
- Else: keyword-match against opportunity signals.
- If no reliable match: fallback to `generic-operator`.
- Then resolve page layout profile by explicit `page_profile` or adapter/profile fallback rules.

## Why this model improves robustness
- Decouples business logic from rendering strategy.
- Supports deterministic domain behavior via rules.
- Enables structural variation across project types (not just copy swaps).
- Makes smoke + page-strategy + business tests portable across project types.
