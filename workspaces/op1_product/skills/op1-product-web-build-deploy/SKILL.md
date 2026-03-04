---
name: op1-product-web-build-deploy
description: Build and deploy simple web products with a robust, adapter-driven framework (project spec -> page spec -> scaffold -> deploy -> smoke/page-strategy/business tests). Use when implementing or operating `Build & deploy simple web products` for `op1_product`, especially when the same harness must support multiple business project types.
---

# Web Build & Deploy (v1.1)

## Core contract
- Primary contract: `framework/contracts/build_deploy_simple_web_products.v1.1.json`
- Project spec schema: `framework/contracts/build_deploy_project_spec.v1.schema.json`
- Page spec schema: `framework/contracts/build_deploy_page_spec.v1.schema.json`

## Default execution
Recommended sequence:

```bash
# 1) lock landing package (mode C preflight gates)
./scripts/run_create_landing_pages_v1.sh

# 2) build/deploy from landing build input
./scripts/run_build_deploy_v1.sh --project-spec research/landing_v1/build_inputs/project_spec.json --page-spec research/landing_v1/build_inputs/page_spec.json
```

This will:
1. Resolve/generate project spec.
2. Compile modular page spec (layout profile + module order).
3. Scaffold app from specs.
4. Deploy to Vercel.
5. Run smoke tests.
6. Run page-strategy tests.
7. Run business-rule tests.
8. Publish run artifacts.

## Inputs
- Preferred: `research/build_deploy_v1/project_spec.json`
- Optional autogen sources:
  - `research/stage1_idea_discovery/opportunity_records.json`
  - `research/stage2_idea_screening/decision_log.json`
- Legacy mode: stage3 blueprint via `--legacy-blueprint`

## Key scripts
- `scripts/create_landing_package.py`
- `scripts/compile_landing_page_spec.py`
- `scripts/landing_contract_test.py`
- `scripts/landing_semantic_test.py`
- `scripts/run_create_landing_pages_v1.sh`
- `scripts/init_project_spec.py`
- `scripts/compile_page_spec.py`
- `scripts/scaffold_web_product.py`
- `scripts/deploy_web_product.sh`
- `scripts/smoke_test_web_product.py`
- `scripts/page_strategy_test_web_product.py`
- `scripts/business_test_web_product.py`
- `scripts/build_generalization_matrix.py`
- `scripts/run_build_deploy_v1.sh`

## Output artifacts
- `research/landing_v1/landing_package.json`
- `research/landing_v1/landing_contract_test.latest.json`
- `research/landing_v1/landing_semantic_test.latest.json`
- `research/stage3_landing_launch/run.latest.json`
- `research/stage2_web_product/run.latest.json`
- `research/stage2_web_product/state.latest.json`
- `research/build_deploy_v1/page_strategy.latest.json`
- `research/build_deploy_v1/smoke_test.latest.json`
- `research/build_deploy_v1/business_test.latest.json`

## References
- `references/robust-workflow.md`
- `references/project-spec-and-adapters.md`
- `references/external-research-notes.md`
