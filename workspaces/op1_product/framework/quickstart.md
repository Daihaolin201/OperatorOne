# Quickstart — Product Capability Runbook

## 1) Run discovery + screening (Stage1/2)
```bash
./scripts/run_generate_startup_ideas.sh
```

This generates:
- `research/stage1_opportunity_records.json`
- `research/stage2_scoring.csv`
- `research/stage2_decision_log.json`

## 2) Create landing pages package (Mode C only)
```bash
./scripts/run_create_landing_pages_v1.sh
```

Outputs:
- `research/landing_v1/landing_package.json`
- `research/landing_v1/landing_contract_test.latest.json`
- `research/landing_v1/build_inputs/project_spec.json`
- `research/landing_v1/build_inputs/page_spec.json`
- `../../handoffs/product_to_marketing.json`

Optional controls:
```bash
./scripts/run_create_landing_pages_v1.sh --opp-id opp_001 --adapter invoice-followup
./scripts/run_create_landing_pages_v1.sh --page-profile chargeback-response
```

## 3) Build & deploy from landing build inputs
```bash
./scripts/run_build_deploy_v1.sh \
  --project-spec research/landing_v1/build_inputs/project_spec.json
```

Outputs:
- `research/build_deploy_v1_run.json`
- `research/build_deploy_v1_state.json`
- `research/build_deploy_v1/page_strategy.latest.json`
- `research/build_deploy_v1/smoke_test.latest.json`
- `research/build_deploy_v1/business_test.latest.json`

## 4) Optional one-command landing + deploy
```bash
./scripts/run_create_landing_pages_v1.sh --with-deploy
```

## 5) Quality expectations
- one primary CTA
- message match with selected opportunity intent
- scope consistency with MVP boundary
- 100% claim traceability to evidence
- multi-device compatibility baseline (desktop/tablet/mobile)
- performance budget hooks present (LCP/INP/CLS)
