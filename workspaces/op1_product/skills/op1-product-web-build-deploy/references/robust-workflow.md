# Robust Workflow (v1.1)

## Goal
Build a **generalizable** build/deploy loop that works across multiple opportunity types via adapter-driven **project spec + page spec**.

## Pipeline
0. (Recommended) Run `create_landing_pages_v1` to lock opportunity, scope, and evidence-traceable landing package.
1. Resolve `project_spec.json` (or autogenerate from Stage1/Stage2).
2. Compile modular `page_spec` (layout profile + module order + multi-device/performance test hooks).
3. Scaffold app from project spec + page spec.
4. Deploy to Vercel.
5. Run deployment health gate.
6. Run smoke tests (reachability + core endpoints).
7. Run page-strategy tests (module presence/order + CTA uniqueness + viewport/responsive baseline + legacy label guardrail).
8. Run business-rule tests (domain behavior assertions).
9. Emit run report and checkpoint state.

## Safety constraints
- Operate only inside `workspaces/op1_product`.
- Do not push by default.
- Keep secrets out of code/reports.
- Fail fast on missing required fields.
- Attempt best-effort rollback on post-deploy failures.

## Core files
- `scripts/init_project_spec.py`
- `scripts/compile_page_spec.py`
- `scripts/scaffold_web_product.py`
- `scripts/deploy_web_product.sh`
- `scripts/smoke_test_web_product.py`
- `scripts/page_strategy_test_web_product.py`
- `scripts/business_test_web_product.py`
- `scripts/run_build_deploy_v1.sh`
- `scripts/build_generalization_matrix.py`

## Output artifacts
- `research/build_deploy_v1_run.json`
- `research/build_deploy_v1_state.json`
- `research/build_deploy_v1/page_strategy.latest.json`
- `research/build_deploy_v1/smoke_test.latest.json`
- `research/build_deploy_v1/business_test.latest.json`
- `research/build_deploy_v1/modular_matrix/generalization_matrix.json`
