# Quickstart — Generate Startup Ideas

## 1) Run full discovery + analysis pipeline
```bash
./scripts/run_generate_startup_ideas.sh
```

This will produce:
- `research/reddit_signals.json`
- `research/signal_summary.json`
- `research/secondary_signals.json` (HN + Shopify App Store)
- `research/stage1_opportunity_records.json`
- `research/stage2_scoring.csv`
- `research/stage2_decision_log.json`

## 2) Inspect top candidates
- Open `research/stage2_scoring.csv` and review rows with decision=`advance`.
- Cross-check reasons/risks in `research/stage2_decision_log.json`.

## 3) Build deploy-ready project spec (recommended)
```bash
python3 scripts/init_project_spec.py \
  --stage1 research/stage1_opportunity_records.json \
  --stage2 research/stage2_decision_log.json \
  --out research/build_deploy_v1/project_spec.json \
  --opp-id opp_001 --force
```

(可选) 也可以继续使用 Stage3 blueprint 作为 legacy 输入。

## 4) Build & deploy simple web products (v1.1)
```bash
./scripts/run_build_deploy_v1.sh
```

(可选) 强制页面策略 profile：
```bash
./scripts/run_build_deploy_v1.sh --page-profile chargeback-response
```

Outputs:
- `research/build_deploy_v1_run.json`
- `research/build_deploy_v1_state.json`
- `research/build_deploy_v1/page_strategy.latest.json`
- `research/build_deploy_v1/smoke_test.latest.json`
- `research/build_deploy_v1/business_test.latest.json`

## 5) Only after project selection
- Generate `../../handoffs/product_to_marketing.json`.
