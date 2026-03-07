# op1_product — Product Agent 能力说明

这是 OperatorOne 的 Product 专用 agent 文档，供团队快速了解“这个 agent 现在能做什么、怎么用、输出到哪里”。

> 面向客户/协作者的一键复现手册：`REPRODUCE.md`

## 0) Live Examples（在线示例入口）
- **人看入口（统一索引）**：`research/LIVE_EXAMPLES.md`
- 索引自动刷新脚本：`scripts/update_live_examples_index.py`（已接入 `run_create_landing_pages_v1.sh` / `run_build_deploy_v1.sh`）
- **机器真源（Stage2）**：
  - `research/stage2_web_product/run.latest.json`
  - `research/stage2_web_product/artifacts/modular_matrix/generalization_matrix.json`
- **机器真源（Stage3）**：
  - `research/stage3_landing_launch/run.latest.json`
  - `research/stage3_landing_launch/regression/stage3_capability_validation.latest.json`
- 当前常用在线示例：
  - Stage2: https://webproductmodularinvoice.vercel.app
  - Stage2: https://webproductmodularchargeback.vercel.app
  - Stage2: https://webproductmodularreporting.vercel.app
  - Stage3: https://webproductlandingstage3validation.vercel.app
  - Stage3: https://webproductlandingstage3opp002.vercel.app
  - Stage3: https://webproductlandingstage3opp003.vercel.app

## 1) 角色定位
- 负责（当前三项主能力）：
  - Generate startup ideas（商业机会搜索、分析、筛选）
  - Build & deploy simple web products（可复用构建部署流水线）
  - Create landing pages（Mode C，转化页语义与门禁）
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
  - `research/stage2_web_product/run.latest.json`
  - `research/stage2_web_product/state.latest.json`
  - `research/build_deploy_v1/page_strategy.latest.json`
  - `research/build_deploy_v1/smoke_test.latest.json`
  - `research/build_deploy_v1/business_test.latest.json`

### E. Create landing pages（v1.1，Mode C only，已实现）
- 单一路径：**Mode C only**（不暴露 A/B 多模式）
- 与 Build/Deploy 分层：Landing 负责转化叙事与门禁，Build/Deploy 负责部署执行。
- 内置 preflight：
  1) opportunity gate（Stage2 优先，缺失时从 Stage1 自动筛选）
  2) scope gate（Stage3 优先，缺失时自动合成 in/out scope + kill criteria）
  3) evidence traceability gate（核心 claim 100% 可回溯）
  4) landing structure gate（LP 白名单模块 + 禁止 demo-first 模块）
- 产出：
  - `research/landing_v1/landing_package.json`
  - `research/landing_v1/landing_contract_test.latest.json`
  - `research/landing_v1/landing_semantic_test.latest.json`
  - `research/landing_v1/build_inputs/project_spec.json`
  - `research/landing_v1/build_inputs/page_spec.json`
  - `../../handoffs/product_to_marketing.json`

## 4) 当前执行流程（按三项主任务）
1. Stage 1 — Generate startup ideas
   - 核心输出：
     - `research/stage1_idea_discovery/opportunity_records.json`
     - `research/stage2_idea_screening/scoring.csv`
     - `research/stage2_idea_screening/decision_log.json`

2. Stage 2 — Build & deploy simple web products
   - 核心输出：
     - `research/stage2_web_product/run.latest.json`
     - `research/stage2_web_product/state.latest.json`
     - `research/stage2_web_product/artifacts/`（build/deploy 详细产物）

3. Stage 3 — Create landing pages
   - 核心输出：
     - `research/landing_v1/landing_package.json`
     - `research/landing_v1/landing_contract_test.latest.json`
     - `research/landing_v1/landing_semantic_test.latest.json`
     - `research/stage3_landing_launch/run.latest.json`
     - `research/stage3_landing_launch/regression/stage3_capability_validation.latest.json`

> 注：Stage4 handoff 不是当前默认目标；当前版本优先保证以上三项能力可重复、可审计。
## 5) 一键运行（按能力）
```bash
# Step 1: Generate startup ideas
./scripts/run_generate_startup_ideas.sh

# Create landing pages (Mode C)
./scripts/run_create_landing_pages_v1.sh

# Build & deploy simple web products (v1.1)
./scripts/run_build_deploy_v1.sh --project-spec research/landing_v1/build_inputs/project_spec.json --page-spec research/landing_v1/build_inputs/page_spec.json

# Optional: force a specific opportunity/adapter for demo
./scripts/run_build_deploy_v1.sh --opp-id opp_001 --adapter invoice-followup
```

## 6) 关键文件索引
- 产物目录索引（新）：`research/STAGE_INDEX.md`
- 流程总览：`framework/pipeline.md`
- 筛选框架：`framework/product-selection-framework.md`
- 来源信任配置：`framework/config/source_trust_rank.json`
- 权重配置：`framework/config/scoring_weights.default.json`
- Product 能力边界：`framework/contracts/product_capability_boundaries.v1.json`
- Landing 能力契约：`framework/contracts/create_landing_pages.v1.1.json`
- Landing Package Schema：`framework/contracts/create_landing_package.v1.1.schema.json`
- Build/Deploy 能力契约：`framework/contracts/build_deploy_simple_web_products.v1.1.json`
- Project Spec Schema：`framework/contracts/build_deploy_project_spec.v1.schema.json`
- Page Spec Schema：`framework/contracts/build_deploy_page_spec.v1.schema.json`
- Landing 主脚本：`scripts/create_landing_package.py`
- Landing page-spec 编译：`scripts/compile_landing_page_spec.py`
- Landing 一键脚本：`scripts/run_create_landing_pages_v1.sh`
- Landing 契约测试：`scripts/landing_contract_test.py`
- Landing 语义测试：`scripts/landing_semantic_test.py`
- Landing 回归矩阵：`scripts/landing_regression_matrix.py`
- Adapter 库：`framework/build_deploy/adapters/`
- Layout profiles：`framework/build_deploy/layout_profiles/`
- Module registry：`framework/build_deploy/page_modules/module_registry.v1.json`
- 快速上手：`framework/quickstart.md`
- 技能目录：`skills/`

## 7) 已安装 skills
- `op1-product-idea-discovery`
- `op1-product-idea-screening`
- `op1-product-create-landing-pages`
- `op1-product-landing-handoff`
- `op1-product-web-build-deploy`

## 8) 当前限制（运行环境相关）
- `web_search` 需要 Brave API key（当前未配置）
- G2/Capterra、Indeed/LinkedIn 在当前环境受反爬/验证限制
- 因此目前“稳定可跑”主源为：Reddit + HN + Shopify

## 9) 使用建议
- 如果是“能力建设期”：先跑 Stage1，确认筛选逻辑和证据质量
- 如果是“执行验证期”：先跑 Stage3（landing），再跑 Stage2（build/deploy）做闭环验证
- 优先使用 `research/STAGE_INDEX.md` 给出的 canonical 路径，legacy 路径仅用于兼容历史脚本
