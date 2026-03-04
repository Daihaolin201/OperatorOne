# op1_product — Product Agent 能力说明

这是 OperatorOne 的 Product 专用 agent 文档，供团队快速了解“这个 agent 现在能做什么、怎么用、输出到哪里”。

> 面向客户/协作者的一键复现手册：`REPRODUCE.md`

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

### D. Build & deploy simple web products（v1.1，已实现）
- 采用 **Project Spec + Page Spec + Adapter** 框架，支持多个商业项目类型（不是单一 demo）
- 输入优先级：
  1) `research/build_deploy_v1/project_spec.json`（推荐）
  2) Stage1/2 自动生成 spec（可选）
  3) Stage3 blueprint（legacy 模式）
- 页面生成策略：按 adapter 选择 layout profile，并按模块顺序组装（Hero/CTA/Proof/Workflow 等）
- 默认部署到 Vercel 子域名（无需自有域名）
- 三层自动验证：
  - smoke test（可用性）
  - page-strategy test（结构策略正确性 + 多设备兼容基线 + 安全响应头基线）
  - business-rule test（业务规则正确性）
- 输出结构化运行报告和检查点：
  - `research/build_deploy_v1_run.json`
  - `research/build_deploy_v1_state.json`
  - `research/build_deploy_v1/page_strategy.latest.json`
  - `research/build_deploy_v1/smoke_test.latest.json`
  - `research/build_deploy_v1/business_test.latest.json`

### E. Create landing pages（v1，Mode C only，已实现）
- 单一路径：**Mode C only**（不暴露 A/B 多模式）
- 内置 preflight：
  1) opportunity gate（Stage2 优先，缺失时从 Stage1 自动筛选）
  2) scope gate（Stage3 优先，缺失时自动合成 in/out scope + kill criteria）
  3) evidence traceability gate（核心 claim 100% 可回溯）
- 产出：
  - `research/landing_v1/landing_package.json`
  - `research/landing_v1/landing_contract_test.latest.json`
  - `research/landing_v1/build_inputs/project_spec.json`
  - `research/landing_v1/build_inputs/page_spec.json`
  - `../../handoffs/product_to_marketing.json`

## 4) Stage-Gate 流程
1. Stage 1 — Opportunity Capture
   - 输出：`research/stage1_opportunity_records.json`
2. Stage 2 — Screening & Decision
   - 输出：`research/stage2_scoring.csv`
   - 输出：`research/stage2_decision_log.json`
3. Stage 3 — Project Blueprint
   - 输出：`research/stage3_project_blueprint.json`
4. Stage 2.8/3.2 — Create Landing Pages（v1, Mode C）
   - 输入：Stage1（必需）+ Stage2/Stage3（可选但优先）
   - 输出：`research/landing_v1/landing_package.json` + `landing_contract_test.latest.json`
5. Stage 2.5/3.5 — Build & Deploy（v1.1 capability）
   - 输入：`project_spec`（推荐）或 Stage1/2 自动生成 spec
   - 输出：`research/build_deploy_v1_run.json` + `page_strategy.latest.json`
6. Stage 4 — Functional Handoff（项目选定后）
   - 输出：`../../handoffs/product_to_marketing.json`

## 5) 一键运行（按能力）
```bash
# Step 1: Generate startup ideas
./scripts/run_generate_startup_ideas.sh

# Create landing pages (Mode C)
./scripts/run_create_landing_pages_v1.sh

# Build & deploy simple web products (v1.1)
./scripts/run_build_deploy_v1.sh

# Optional: force a specific opportunity/adapter for demo
./scripts/run_build_deploy_v1.sh --opp-id opp_001 --adapter invoice-followup
```

## 6) 关键文件索引
- 流程总览：`framework/pipeline.md`
- 筛选框架：`framework/product-selection-framework.md`
- 来源信任配置：`framework/config/source_trust_rank.json`
- 权重配置：`framework/config/scoring_weights.default.json`
- Landing 能力契约：`framework/contracts/create_landing_pages.v1.json`
- Landing Package Schema：`framework/contracts/create_landing_package.v1.schema.json`
- Build/Deploy 能力契约：`framework/contracts/build_deploy_simple_web_products.v1.1.json`
- Project Spec Schema：`framework/contracts/build_deploy_project_spec.v1.schema.json`
- Page Spec Schema：`framework/contracts/build_deploy_page_spec.v1.schema.json`
- Landing 主脚本：`scripts/create_landing_package.py`
- Landing 一键脚本：`scripts/run_create_landing_pages_v1.sh`
- Landing 契约测试：`scripts/landing_contract_test.py`
- Adapter 库：`framework/build_deploy/adapters/`
- Layout profiles：`framework/build_deploy/layout_profiles/`
- Module registry：`framework/build_deploy/page_modules/module_registry.v1.json`
- 快速上手：`framework/quickstart.md`
- 技能目录：`skills/`

## 7) 已安装 skills
- `op1-product-idea-discovery`
- `op1-product-idea-screening`
- `op1-product-mvp-scope`
- `op1-product-landing-handoff`
- `op1-product-web-build-deploy`

## 8) 当前限制（运行环境相关）
- `web_search` 需要 Brave API key（当前未配置）
- G2/Capterra、Indeed/LinkedIn 在当前环境受反爬/验证限制
- 因此目前“稳定可跑”主源为：Reddit + HN + Shopify

## 9) 使用建议
- 如果是“能力建设期”：先跑 Stage1/2，确认筛选逻辑和证据质量
- 如果是“项目执行期”：从 Stage2 的 `advance` 候选中选 1 个进入 Stage3
- 只有项目选定后再生成 marketing handoff，避免过早绑定单一商业项目
