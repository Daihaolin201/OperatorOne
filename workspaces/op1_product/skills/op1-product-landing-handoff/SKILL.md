---
name: op1-product-landing-handoff
description: Create landing-page-ready product handoff using Mode-C contract gates (opportunity selection, scope boundary, evidence traceability) and write output for marketing consumption.
---

# Landing Handoff Builder (Mode C)

Use this skill when the request is to produce a **landing-ready handoff** from Stage1/2/3 artifacts with explicit quality gates.

## Inputs
- Required: `research/stage1_opportunity_records.json`
- Optional: `research/stage2_decision_log.json`, `research/stage3_project_blueprint.json`
- Optional existing spec: `research/build_deploy_v1/project_spec.json`

## Execution
Preferred one-command path:

```bash
./scripts/run_create_landing_pages_v1.sh
```

This will:
1. Resolve/select opportunity (use stage2 if available, synthesize if missing).
2. Resolve MVP scope boundary (use stage3 if available, synthesize if missing).
3. Generate landing package + build inputs (`project_spec` + `page_spec`).
4. Run landing contract test + landing semantic test.
5. Write marketing handoff to `../../handoffs/product_to_marketing.json`.

## Core artifacts
- `research/landing_v1/landing_package.json`
- `research/landing_v1/landing_contract_test.latest.json`
- `research/landing_v1/landing_semantic_test.latest.json`
- `research/landing_v1/build_inputs/project_spec.json`
- `research/landing_v1/build_inputs/page_spec.json`
- `../../handoffs/product_to_marketing.json`

## Quality bar (must pass)
- `page_mode=landing`.
- Single primary CTA.
- LP module whitelist (no demo-first modules).
- Message-match with entry intent.
- Scope consistency with MVP boundary.
- Claim-evidence traceability coverage = 100%.
- Scannable message hierarchy.
- Multi-device compatibility baseline + performance budget hooks + security header hooks.

## Guardrails
- Do not invent claims that cannot be traced to Stage1/2 evidence.
- Do not introduce copy that violates `out_of_scope` boundary.
- Do not change other agents’ scope or handoff contracts.
