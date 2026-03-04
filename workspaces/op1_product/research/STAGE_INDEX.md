# Research Stage Index (2026-03 cleanup)

目的：把 Stage1/2/3 关键输出集中到清晰目录，降低根目录噪音，同时保留 legacy 路径兼容。

## Canonical stage paths

- Stage 1 — Idea Discovery
  - `research/stage1_idea_discovery/opportunity_records.json`

- Stage 1 — Marketing SEO Experiments (continuous shadow)
  - `research/stage1_marketing_seo/run.latest.json`
  - `research/stage1_marketing_seo/state.latest.json`
  - `research/stage1_marketing_seo/context_index.latest.json`
  - `research/stage1_marketing_seo/keyword_graph.latest.csv`
  - `research/stage1_marketing_seo/experiments.backlog.latest.json`
  - `research/stage1_marketing_seo/experiments.queue.latest.json`
  - `research/stage1_marketing_seo/scoreboard.latest.json`

- Stage 2 — Idea Screening
  - `research/stage2_idea_screening/scoring.csv`
  - `research/stage2_idea_screening/decision_log.json`

- Stage 2 — Web Product Build/Deploy
  - `research/stage2_web_product/run.latest.json`
  - `research/stage2_web_product/state.latest.json`
  - `research/stage2_web_product/artifacts/` (alias -> `research/build_deploy_v1/`)

- Stage 3 — MVP Scope
  - `research/stage3_mvp_scope/project_blueprint.json`

- Stage 3 — Landing Launch
  - `research/stage3_landing_launch/run.latest.json`
  - `research/stage3_landing_launch/regression/` (alias -> `research/landing_v1_regression/`)

- Live examples index
  - Human index: `research/LIVE_EXAMPLES.md`
  - Machine index: `research/live_examples.latest.json`

## Legacy compatibility

以下旧路径仍可读写（符号链接），不会影响既有脚本：

- `research/stage1_opportunity_records.json`
- `research/stage2_scoring.csv`
- `research/stage2_decision_log.json`
- `research/stage3_project_blueprint.json`
- `research/build_deploy_v1_run.json`
- `research/build_deploy_v1_state.json`
- `research/create_landing_pages_v1_run.json`

建议：新开发统一使用 canonical stage paths。