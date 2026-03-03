# Product Agent Setup Plan（框架优先）

## Objective
把 agent 配置为“先建能力、后选项目”的模式，确保客户开箱即用。

## Installed capabilities
1. **op1-product-idea-discovery**
   - 产出 Stage 1 机会记录（含证据与硬门槛）
2. **op1-product-idea-screening**
   - 产出 Stage 2 评分与决策日志（含理由与风险）
3. **op1-product-mvp-scope**
   - 产出 Stage 3 可测试立项蓝图
4. **op1-product-landing-handoff**
   - 项目选定后再生成营销交接

## Tool strategy
- `web_fetch` / `web_search`: 外部信号收集
- `exec`: 批量清洗与评分计算
- `read` / `write` / `edit`: 结构化产物管理

## Output contract (stage-first)
- Stage 1: `research/stage1_opportunity_records.json`
- Stage 2: `research/stage2_scoring.csv`, `research/stage2_decision_log.json`
- Stage 3: `research/stage3_project_blueprint.json`
- Stage 4 (only after project selection): `../../handoffs/product_to_marketing.json`
