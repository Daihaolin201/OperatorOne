# Product Pipeline（开箱即用）

## Stage 1 — Opportunity Capture
- 输入：问题域、目标人群、数据源
- 输出：`research/stage1_idea_discovery/opportunity_records.json`
- 通过条件：Hard Gates 全部通过

## Stage 2 — Screening & Decision
- 输入：Stage 1 records
- 输出：
  - `research/stage2_idea_screening/scoring.csv`
  - `research/stage2_idea_screening/decision_log.json`
- 通过条件：
  - `weighted_score >= 3.8`
  - Pain / Pay / MVP Speed 不低于最低通过线

## Stage 3 — Project Blueprint
- 输入：Stage 2 top candidates
- 输出：`research/stage3_mvp_scope/project_blueprint.json`
- 通过条件：
  - 14 天实验可执行
  - 成功指标和停止条件明确

## Stage 2.8 / 3.2 — Create Landing Pages (Mode C, Contract v1.1)
- 输入（优先级）：
  1) `research/stage1_idea_discovery/opportunity_records.json`（必需）
  2) `research/stage2_idea_screening/decision_log.json`（优先；缺失时自动合成）
  3) `research/stage3_mvp_scope/project_blueprint.json`（优先；缺失时自动合成 scope）
- 输出：
  - `research/landing_v1/landing_package.json`
  - `research/landing_v1/landing_contract_test.latest.json`
  - `research/landing_v1/landing_semantic_test.latest.json`
  - `research/landing_v1/build_inputs/project_spec.json`
  - `research/landing_v1/build_inputs/page_spec.json`
  - `../../handoffs/product_to_marketing.json`
- 通过条件：
  - `page_mode=landing`
  - 单主 CTA
  - LP 模块白名单通过（无 demo-first 模块）
  - scope 一致性通过
  - claim traceability 覆盖率 100%
  - 多设备兼容基线通过（desktop/tablet/mobile）

## Stage 2.5 / 3.5 — Build & Deploy (v1.1)
- 输入（优先级）：
  1) `research/build_deploy_v1/project_spec.json`
  2) `research/landing_v1/build_inputs/project_spec.json` + `research/landing_v1/build_inputs/page_spec.json`
  3) Stage1/Stage2 自动生成 project spec
  4) `research/stage3_mvp_scope/project_blueprint.json`（legacy）
- 输出：
  - `research/stage2_web_product/run.latest.json`
  - `research/stage2_web_product/state.latest.json`
  - `research/build_deploy_v1/page_strategy.latest.json`
  - `research/build_deploy_v1/smoke_test.latest.json`
  - `research/build_deploy_v1/business_test.latest.json`
- 通过条件：
  - 公开 URL 可访问
  - smoke test 全通过
  - page-strategy test 全通过（模块存在、顺序、主 CTA 唯一、viewport/响应式基线、安全响应头基线）
  - business-rule test 全通过

## Stage 4 — Functional Handoff（可选）
- 默认不执行（当前主目标是三项能力闭环）。
- 仅当你明确要求时执行。
- 输入：Stage 3 blueprint
- 输出：
  - `../../handoffs/product_to_marketing.json`
  - 其他团队 handoff（按需）

## 约束
- 不跳步骤。
- 不允许用“感觉”替代证据。
- 每一步都必须产出结构化文件，供下一步直接读取。
