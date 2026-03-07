# OperatorOne Venture Studio Dashboard (v1.1)

这个 dashboard 现在有两层能力：

1. **Monitor**：4-agent 状态、12 能力、handoff 链路、外联门禁
2. **Studio**：从 startup idea 选择项目，并逐阶段执行 Product → Marketing → Sales → Operations → Iterate

---

## 启动

在仓库根目录执行：

```bash
python3 dashboard/server.py --host 127.0.0.1 --port 8765
```

浏览器打开：

- <http://127.0.0.1:8765>

---

## Phase 0-4 对应落地

### Phase 0（产品化设计稿）

- `docs/studio_phase0_product_spec.md`
- `dashboard/config/studio_phase0.json`

包含：核心对象（venture / stage_run / decision_gate / artifact / kpi_snapshot）、状态机、自动与人工动作边界。

### Phase 1（Studio 界面）

5 个主 tab：

- Idea Board
- Product Build
- Marketing Studio
- Sales Console
- Ops Loop

### Phase 2（执行引擎）

`dashboard/studio.py` 提供：

- venture 生命周期管理
- stage action 调度（复用现有脚本）
- 异步 job 执行 + 重复提交防抖（同 action/venture 复用进行中任务）
- stage timeline 记录
- artifact 快照（按 venture_id）
- venture context 同步（`venture_context.v1`）
- 子 Agent relay 的 provider/model 可观测性（默认要求 `zai + glm-*`）

### Phase 3（外联与部署）

- 默认 simulation（安全）
- live 模式需要 `manual arm ON` + `confirmLive=true`
- Product live 部署需要 Vercel 已安装并登录
- Product 部署支持 deterministic `--vercel-project` 命名治理
- Sales commit 动作同样有 live 门禁

### Phase 4（闭环自动化 + 鲁棒性）

- Operations 执行后可回写 loop todos 到 Product/Marketing/Sales
- 进入下一轮先创建迁移申请（`confirm_iterate`），再显式确认迁移
- 新增 `stage_preflight`（合同/可复现性预检查 + `zai_core_profile` 核查）
- 新增 `rehearsal_e2e`（simulation 一键彩排）
- 新增 `confirm_stage_transition`：阶段迁移统一显式确认，禁止隐式自动跳步

### v1.3 交互升级（Prompt-first + 显式门禁）

- Judge Focus 四块信息：当前项目 / 当前阶段 / 产物入口 / 下一步唯一动作
- 新增 **Prompt-first Copilot（问我）**：
  - 用户可输入问题（如“现在到哪一步了？”“下一步做什么？”“能不能开 live？”）
  - 提示词窗口优先走 LLM Copilot，失败时自动回退规则引擎
  - 面板展示当前阶段进度、待用户决策问题、最近问答记录
  - 支持直接从问题卡片触发建议动作
  - 内置“推荐项目 / 分析活动 / 新手计划”快捷问题
- 阶段产物卡片化：Product/Marketing/Sales/Ops 均提供可点击入口
- 操作状态机：idle → queued → running → succeeded/failed（按钮旁状态 + 全局运行条 + toast）
- `messagePack` 联动：Landing 价值主张 + 广告文案 + Sales 开场并排预览，自动生成 UTM 链接
- Product 部署治理：
  - deterministic 项目名 `op1-<opp>-<venture>`
  - 部署注册表新增 `env / commit / runId`
  - live 默认 preview，production 需 `confirmProduction=true`
- Vercel 两段治理：
  - `vercel_audit` 只读审计
  - `vercel_cleanup_apply` 支持 `strategy=archive|delete`（默认 archive，delete 需二次确认）
- `rehearsal_e2e` 生成可回放彩排报告（replay JSON）

---

## 核心 API

### Studio

- `GET /api/studio/fast-snapshot`（推荐，轻量）
- `GET /api/studio/snapshot?includeMonitor=1`（需要时拉全）
- `GET /api/studio/artifact?path=<repo-relative-path>`（读取产物）
- `POST /api/studio/action`
- `GET /api/studio/jobs`
- `GET /api/studio/jobs/<job_id>`

### Monitor + Integration（兼容）

- `GET /api/monitor/cached-snapshot`（缓存监控快照）
- `GET /api/snapshot`（兼容接口，cache-backed）
- `POST /api/runtime-flags/manual-arm`
- `POST /api/integrations/channel/connect`
- `POST /api/integrations/channel/disconnect`
- `POST /api/integrations/secrets/audit`
- `POST /api/integrations/secrets/reload`

---

## 关键运行态文件

- `dashboard/.runtime/studio/state.json`
- `dashboard/.runtime/studio/ventures.json`
- `dashboard/.runtime/studio/stage_runs.json`
- `dashboard/.runtime/studio/decision_gates.json`
- `dashboard/.runtime/studio/loop_todos.json`
- `dashboard/.runtime/studio/deployments.json`
- `dashboard/.runtime/studio/contexts/<venture>.json`
- `dashboard/.runtime/studio/artifacts/...`

---

## 使用与优化文档

- 使用指南：`docs/studio_usage_guide.md`
- 优化报告：`docs/studio_optimization_report.md`

## 安全边界

- 默认仅本机访问（127.0.0.1）
- live 高风险动作需 manual arm + 显式确认
- 无任意 shell 执行端点，动作仅白名单
- 仍建议在真实对外场景下接入额外审批与幂等保护
