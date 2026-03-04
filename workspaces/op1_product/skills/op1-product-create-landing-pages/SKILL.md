---
name: op1-product-create-landing-pages
description: "Execute full Stage-3 landing capability for op1_product (Mode C): resolve opportunity/scope/evidence gates, generate landing package + landing-specific page spec, run contract/semantic tests, and (optionally) deploy via build pipeline."
---

# Stage-3 Landing Capability (Mode C, v1.1)

Use this skill when the goal is to produce a **true conversion landing page package** (not a demo-first web-product page).

## Scope
- In scope:
  - Stage3 landing package generation from Stage1/2/3 inputs
  - landing-specific page spec compilation (`page_mode=landing`)
  - contract + semantic + deployment test chain
- Out of scope:
  - rewriting Stage1 discovery process
  - replacing Build&Deploy framework

## Inputs
- Required:
  - `research/stage1_idea_discovery/opportunity_records.json`
- Optional but preferred:
  - `research/stage2_idea_screening/decision_log.json`
  - `research/stage3_mvp_scope/project_blueprint.json`

## Core command (recommended)
```bash
./scripts/run_create_landing_pages_v1.sh
```

This runs:
1. opportunity gate (Stage2优先；缺失时自动合成)
2. scope gate (Stage3优先；缺失时自动合成)
3. evidence traceability gate
4. landing structure gate (LP whitelist + forbidden demo modules)
5. landing contract test
6. landing semantic test
7. marketing handoff write

## Optional deployment validation
```bash
./scripts/run_build_deploy_v1.sh \
  --project-spec research/landing_v1/build_inputs/project_spec.json \
  --page-spec research/landing_v1/build_inputs/page_spec.json
```

## Outputs
- `research/landing_v1/landing_package.json`
- `research/landing_v1/landing_contract_test.latest.json`
- `research/landing_v1/landing_semantic_test.latest.json`
- `research/landing_v1/build_inputs/project_spec.json`
- `research/landing_v1/build_inputs/page_spec.json`
- `../../handoffs/product_to_marketing.json`

## Quality gates (must pass)
- `landing_mode_enabled`
- `single_primary_cta`
- `landing_module_whitelist_and_structure`
- `message_match_with_entry_intent`
- `scope_consistency_with_mvp_boundary`
- `claim_evidence_traceability_100pct`
- `no_demo_first_positioning`
- `multi_device_compatibility_baseline`
- `performance_baseline_hooks_present`
- `security_headers_baseline_hooks_present`

## Guardrails
- 不允许把 landing 页面退化为 workflow demo page。
- 不允许出现无法映射回 Stage1/2 证据的核心 claim。
- 不允许越过 Stage3 scope 边界写文案。
