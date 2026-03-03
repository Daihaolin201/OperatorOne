# Product Pipeline（开箱即用）

## Stage 1 — Opportunity Capture
- 输入：问题域、目标人群、数据源
- 输出：`research/stage1_opportunity_records.json`
- 通过条件：Hard Gates 全部通过

## Stage 2 — Screening & Decision
- 输入：Stage 1 records
- 输出：
  - `research/stage2_scoring.csv`
  - `research/stage2_decision_log.json`
- 通过条件：
  - `weighted_score >= 3.8`
  - Pain / Pay / MVP Speed 不低于最低通过线

## Stage 3 — Project Blueprint
- 输入：Stage 2 top candidates
- 输出：`research/stage3_project_blueprint.json`
- 通过条件：
  - 14 天实验可执行
  - 成功指标和停止条件明确

## Stage 4 — Functional Handoff
- 输入：Stage 3 blueprint
- 输出：
  - `../../handoffs/product_to_marketing.json`
  - 其他团队 handoff（按需）

## 约束
- 不跳步骤。
- 不允许用“感觉”替代证据。
- 每一步都必须产出结构化文件，供下一步直接读取。
