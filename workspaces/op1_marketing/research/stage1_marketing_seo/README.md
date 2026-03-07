# Stage 1 — Marketing SEO Experiments (Continuous Shadow)

## Canonical outputs
- `run.latest.json`
- `state.latest.json`
- `context_index.latest.json`
- `keyword_graph.latest.csv`
- `experiments.backlog.latest.json`
- `experiments.queue.latest.json`
- `scoreboard.latest.json`
- `decision_log.latest.md`
- `briefs/`

## Canonical input artifacts
- `input/product_snapshot.latest.json`
- `input/delta.latest.json`
- `input/mirror.latest/`

## Required upstream inputs (full ingest, no pre-filter)
- `../op1_product/research/stage1_idea_discovery/opportunity_records.json`
- `../op1_product/research/stage2_idea_screening/scoring.csv`
- `../op1_product/research/stage2_idea_screening/decision_log.json`
- `../op1_product/research/stage3_mvp_scope/project_blueprint.json`
- `../op1_product/research/stage2_web_product/run.latest.json`
- `../op1_product/research/stage2_web_product/state.latest.json`
- `../op1_product/research/stage3_landing_launch/run.latest.json`
- `../op1_product/research/live_examples.latest.json`
- `../op1_product/research/build_deploy_v1/project_spec*.json`
- `../op1_product/research/landing_v1/landing_package.json`
- `../op1_product/research/landing_v1/landing_contract_test.latest.json`
- `../op1_product/research/landing_v1/landing_semantic_test.latest.json`
- `../../handoffs/product_to_marketing.json`

## Mode defaults
- `shadow` (default)
- `publish=false`
- `index=false`
- `continuous=true`

## Run
```bash
# single cycle
./scripts/run_marketing_seo_stage1.sh

# force recompute even if no input delta
./scripts/run_marketing_seo_stage1.sh --force

# continuous mode
./scripts/run_marketing_seo_stage1.sh --continuous --interval 300
```

## Capability contract
- Full-product ingestion first (lossless mirror), then SEO experiment computation.
- Any required input missing => `blocked_input_incomplete`.
- Continuous queue lifecycle: `candidate -> drafted -> scored -> ready -> shadow_validated -> promoted|dropped`.
- No hard binding to a single business project.
