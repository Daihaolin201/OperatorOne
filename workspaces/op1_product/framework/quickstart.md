# Quickstart — Product Capability Runbook

## 1) Run discovery + screening (Stage1/2)
```bash
./scripts/run_generate_startup_ideas.sh
```

This generates:
- `research/stage1_idea_discovery/opportunity_records.json`
- `research/stage2_idea_screening/scoring.csv`
- `research/stage2_idea_screening/decision_log.json`

## 2) Create landing pages package (Mode C only)
```bash
./scripts/run_create_landing_pages_v1.sh
```

Outputs:
- `research/landing_v1/landing_package.json`
- `research/landing_v1/landing_contract_test.latest.json`
- `research/landing_v1/landing_semantic_test.latest.json`
- `research/stage3_landing_launch/run.latest.json`
- `research/landing_v1/build_inputs/project_spec.json`
- `research/landing_v1/build_inputs/page_spec.json`
- `../../handoffs/product_to_marketing.json`

Optional controls:
```bash
./scripts/run_create_landing_pages_v1.sh --opp-id opp_001 --adapter invoice-followup
./scripts/run_create_landing_pages_v1.sh --page-profile landing-chargeback-response
```

## 3) Build & deploy from landing build inputs
```bash
./scripts/run_build_deploy_v1.sh \
  --project-spec research/landing_v1/build_inputs/project_spec.json \
  --page-spec research/landing_v1/build_inputs/page_spec.json
```

Outputs:
- `research/stage2_web_product/run.latest.json`
- `research/stage2_web_product/state.latest.json`
- `research/build_deploy_v1/page_strategy.latest.json`
- `research/build_deploy_v1/smoke_test.latest.json`
- `research/build_deploy_v1/business_test.latest.json`

## 4) Optional one-command landing + deploy
```bash
./scripts/run_create_landing_pages_v1.sh --with-deploy
```

## 5) Quality expectations
- page_mode is landing (not web-product mode)
- one primary CTA
- LP module whitelist/required sections enforced
- message match with selected opportunity intent
- scope consistency with MVP boundary
- 100% claim traceability to evidence
- multi-device compatibility baseline (desktop/tablet/mobile)
- performance budget hooks present (LCP/INP/CLS)
- security header baseline hooks present and validated in page-strategy test
