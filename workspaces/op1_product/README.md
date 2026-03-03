# op1_product — Product Agent 能力说明

这是 OperatorOne 的 Product 专用 agent 文档，供团队快速了解“这个 agent 现在能做什么、怎么用、输出到哪里”。

## 1) 角色定位
- 负责：
  - Generate startup ideas（商业机会搜索、分析、筛选）
  - MVP 边界定义与验证路径设计
  - 向 Marketing 交接产品输入
- 不负责：
  - 直接执行外联营销
  - 销售 pipeline 决策
  - 流量/营收 tracking owner 职能

## 2) 当前工作模式
- **Framework-first setup mode**（先搭能力框架，再选具体项目）
- 目标：让客户开箱即用地跑完整 Product 决策链路

## 3) 已实现能力（当前可用）
### A. Step 1: Generate startup ideas（已实现）
- 多源机会搜索（当前稳定来源：Reddit + HN Algolia + Shopify App Store）
- 机会结构化记录（Stage 1）
- 评分与决策输出（Stage 2）
- 可重复一键执行（非一次性人工流程）

### B. 筛选与评分能力（已实现）
- v2 权重（默认）：
  - pain_intensity: 0.24
  - willingness_to_pay: 0.24
  - mvp_speed: 0.18
  - acquisition_reachability: 0.16
  - competitive_whitespace: 0.08
  - recurring_usage: 0.10
- 置信度乘数：
  - high = 1.0
  - medium = 0.8
  - low = 0.5
- 最终分：
  - `final_score = base_weighted_score * confidence_multiplier`

### C. 决策闸门（已实现）
在进入 advance 决策前，至少满足：
1. 跨源证据（min distinct sources）
2. 有损失信号（loss signal）
3. 有预算/意图信号（budget or intent signal）

## 4) Stage-Gate 流程
1. Stage 1 — Opportunity Capture
   - 输出：`research/stage1_opportunity_records.json`
2. Stage 2 — Screening & Decision
   - 输出：`research/stage2_scoring.csv`
   - 输出：`research/stage2_decision_log.json`
3. Stage 3 — Project Blueprint
   - 输出：`research/stage3_project_blueprint.json`
4. Stage 4 — Functional Handoff（项目选定后）
   - 输出：`../../handoffs/product_to_marketing.json`

## 5) 一键运行
```bash
./scripts/run_generate_startup_ideas.sh
```

## 6) 关键文件索引
- 流程总览：`framework/pipeline.md`
- 筛选框架：`framework/product-selection-framework.md`
- 来源信任配置：`framework/config/source_trust_rank.json`
- 权重配置：`framework/config/scoring_weights.default.json`
- 快速上手：`framework/quickstart.md`
- 技能目录：`skills/`

## 7) 已安装 skills
- `op1-product-idea-discovery`
- `op1-product-idea-screening`
- `op1-product-mvp-scope`
- `op1-product-landing-handoff`

## 8) 当前限制（运行环境相关）
- `web_search` 需要 Brave API key（当前未配置）
- G2/Capterra、Indeed/LinkedIn 在当前环境受反爬/验证限制
- 因此目前“稳定可跑”主源为：Reddit + HN + Shopify

## 9) 使用建议
- 如果是“能力建设期”：先跑 Stage1/2，确认筛选逻辑和证据质量
- 如果是“项目执行期”：从 Stage2 的 `advance` 候选中选 1 个进入 Stage3
- 只有项目选定后再生成 marketing handoff，避免过早绑定单一商业项目
