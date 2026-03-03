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

## 3) Move to Stage 3 manually
- Choose one `advance` opportunity.
- Fill `research/stage3_project_blueprint.json` from template:
  - `framework/templates/stage3_project_blueprint.template.json`

## 4) Only after project selection
- Generate `../../handoffs/product_to_marketing.json`.
