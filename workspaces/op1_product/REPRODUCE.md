# REPRODUCE.md — op1_product Agent 能力复现手册

> 目的：给客户/协作者一份可执行、可更新、可验收的文档，说明当前 Product Agent 能力边界与复现方式。

## 文档元信息（每次验收后更新）
- doc_version: `1.2`
- owner_agent: `op1_product`
- workspace: `workspaces/op1_product`
- last_validated_at_utc: `2026-03-04T00:51:04Z`
- validation_scope: `Stage1+Stage2 + CreateLandingPages v1.1(mode-c, landing-only semantics) + Build&Deploy v1.1(optional external page_spec) + 3-opportunity deployment validation`
- push_status: `no-push (default)`

---

## 1) 当前能力（面向客户）

### A. Stage 1 — 机会发现（已可复现）
- 多源信号抓取（当前稳定：Reddit + HN + Shopify）
- 机会结构化输出到 `research/stage1_opportunity_records.json`

### B. Stage 2 — 机会筛选与决策（已可复现）
- 评分与闸门判定
- 输出：
  - `research/stage2_scoring.csv`
  - `research/stage2_decision_log.json`

### C. Create landing pages（v1.1, Mode C only，已可复现）
- 核心链路：`Stage1/2/3 -> Preflight Gates -> LandingPackage -> Contract Test -> Semantic Test -> Marketing Handoff`
- 四个内置 preflight gate：
  - opportunity gate（Stage2 优先，缺失时自动合成）
  - scope gate（Stage3 优先，缺失时自动合成）
  - evidence traceability gate（核心 claim 100% 回溯）
  - landing structure gate（LP 白名单 + 禁止 demo-first 模块）
- 输出可直接喂给 Build/Deploy：
  - `research/landing_v1/build_inputs/project_spec.json`
  - `research/landing_v1/build_inputs/page_spec.json`
  - `research/landing_v1/landing_semantic_test.latest.json`

### D. Build & deploy simple web products（v1.1，已可复现）
- 核心链路：`ProjectSpec -> (optional external PageSpec) -> Scaffold -> Deploy -> Smoke -> PageStrategy -> Business`
- 具备模块化页面策略（不是同壳换文案）：
  - 按 adapter/layout profile 与 module order 组合
  - 支持 web-product 模式与 landing 模式 page spec 输入
- Page-strategy 包含：
  - 多设备兼容基线检查（viewport + responsive markers + device profiles）
  - 安全响应头基线检查
  - landing 语义检查（mode marker、forbidden modules/terms）
- 默认部署到 Vercel 子域名
- 结构化产物可审计、可复跑

### E. 跨项目泛化验证（已通过）
已验证 3 类 adapter 全链路通过：
- invoice-followup
- chargeback-response
- client-reporting

矩阵产物：`research/build_deploy_v1/modular_matrix/generalization_matrix.json`

---

## 2) 前置环境要求
1. 在 `workspaces/op1_product` 目录执行
2. 可用命令：`python3`, `bash`
3. 已安装并登录 Vercel CLI：
   - `vercel --version`
   - `vercel whoami`
4. （可选）Brave API key：用于 `web_search` 增强研究，不影响核心复现

---

## 3) 最短复现路径（推荐）

### Step 1：生成 Stage1/2
```bash
./scripts/run_generate_startup_ideas.sh
```

### Step 2：生成 Landing Package（Mode C, v1.1）
```bash
./scripts/run_create_landing_pages_v1.sh --adapter invoice-followup
```

关键产物：
- `research/landing_v1/landing_package.json`
- `research/landing_v1/landing_contract_test.latest.json`
- `research/landing_v1/landing_semantic_test.latest.json`
- `research/landing_v1/build_inputs/project_spec.json`
- `research/landing_v1/build_inputs/page_spec.json`

### Step 3：一键构建部署 + 三层测试
```bash
./scripts/run_build_deploy_v1.sh \
  --project-spec research/landing_v1/build_inputs/project_spec.json \
  --page-spec research/landing_v1/build_inputs/page_spec.json
```

### Step 4：验收主报告
查看：
- `research/create_landing_pages_v1_run.json`
- `research/build_deploy_v1_run.json`
- 关键字段应为：
  - `create_landing_pages_v1.status != blocked`
  - `contract_test_status = passed`
  - `semantic_test_status = passed`
  - `checks.smoke_status = passed`
  - `checks.page_strategy_status = passed`
  - `checks.business_status = passed`

---

## 4) 泛化复现（3 项目矩阵）

### 4.1 生成三份 spec
```bash
python3 scripts/init_project_spec.py --stage1 research/stage1_opportunity_records.json --stage2 research/stage2_decision_log.json --out research/build_deploy_v1/project_spec.invoice.json --adapter invoice-followup --force
python3 scripts/init_project_spec.py --stage1 research/stage1_opportunity_records.json --stage2 research/stage2_decision_log.json --out research/build_deploy_v1/project_spec.chargeback.json --adapter chargeback-response --force
python3 scripts/init_project_spec.py --stage1 research/stage1_opportunity_records.json --stage2 research/stage2_decision_log.json --out research/build_deploy_v1/project_spec.reporting.json --adapter client-reporting --force
```

### 4.2 分别运行流水线
```bash
./scripts/run_build_deploy_v1.sh --project-spec research/build_deploy_v1/project_spec.invoice.json --app-dir runtime/web_product_modular_invoice --artifact-dir research/build_deploy_v1/modular_matrix/invoice
./scripts/run_build_deploy_v1.sh --project-spec research/build_deploy_v1/project_spec.chargeback.json --app-dir runtime/web_product_modular_chargeback --artifact-dir research/build_deploy_v1/modular_matrix/chargeback
./scripts/run_build_deploy_v1.sh --project-spec research/build_deploy_v1/project_spec.reporting.json --app-dir runtime/web_product_modular_reporting --artifact-dir research/build_deploy_v1/modular_matrix/reporting
```

### 4.3 生成矩阵总报告
```bash
./scripts/build_generalization_matrix.py \
  --base-dir research/build_deploy_v1/modular_matrix \
  --out research/build_deploy_v1/modular_matrix/generalization_matrix.json
```

通过标准：
- `all_passed = true`
- pairwise 对比 `same_order` 不应全部为 true（证明存在结构差异）

---

## 5) 产物地图（客户常看）
- Landing 主报告：`research/create_landing_pages_v1_run.json`
- Landing 契约测试：`research/landing_v1/landing_contract_test.latest.json`
- Landing 语义测试：`research/landing_v1/landing_semantic_test.latest.json`
- Stage3 验证总报告：`research/landing_v1_regression/stage3_capability_validation.latest.json`
- Landing 回归矩阵：`research/landing_v1_regression/regression_matrix.latest.json`
- Build/Deploy 主运行报告：`research/build_deploy_v1_run.json`
- 运行状态时间线：`research/build_deploy_v1_state.json`
- Smoke 报告：`research/build_deploy_v1/**/smoke_test.latest.json`
- Page Strategy 报告：`research/build_deploy_v1/**/page_strategy.latest.json`
- Business 报告：`research/build_deploy_v1/**/business_test.latest.json`

---

## 6) 安全与边界
- 默认不 push（除非明确授权）
- 仅在 `workspaces/op1_product` 内操作
- 失败时记录结构化状态并尝试 best-effort rollback
- 这是“可复用构建框架”，不是承诺自动产出最终商业成功

---

## 7) 文档更新规则（可持续维护）
每次能力变化后，至少同步更新：
1. 本文件 `REPRODUCE.md`
2. `README.md`
3. `framework/pipeline.md`
4. `framework/quickstart.md`
5. `skills/op1-product-create-landing-pages/SKILL.md`
6. `skills/op1-product-landing-handoff/SKILL.md`
7. `skills/op1-product-web-build-deploy/SKILL.md`
8. 对应 contract/schema（如有字段变化）

建议在本文件追加一条更新日志：
- 时间
- 变更内容
- 影响命令
- 影响产物

---

## 8) Stage 3 启动建议（你下一步要做）
当你准备进入 Stage 3（Project Blueprint）时，建议流程：
1. 从 `stage2_decision_log.json` 选定一个 `advance` 候选
2. 明确 14 天实验：渠道、样本、成功阈值、kill criteria
3. 固化到 `research/stage3_project_blueprint.json`
4. 再用 Build&Deploy 能力做验证站点与业务测试

> 这样可以把“选题正确性”与“执行可复现性”串成一条闭环。
