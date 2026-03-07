# Learnings — dashboard-zai-ceoclaw-e2e

## [2026-03-07] Atlas初始化

### 项目结构要点
- 工作目录：`Code/OperatorOne/`
- dashboard入口：`dashboard/server.py` (HTTP), `dashboard/studio.py` (action dispatch), `dashboard/web/` (frontend)
- 现有API路由风格：`/api/studio/*`，handler在server.py
- 关键运行态文件：`dashboard/.runtime/studio/`
- 默认模型：`openai-codex/gpt-5.3-codex`（在openclaw/agents.manifest.json）
- Z.AI 凭据：环境变量 `ZAI_API_KEY`，目标模型 `glm-4.5`

### 现有能力（可复用）
- `dashboard/studio.py`：已有 `rehearsal_e2e`、stage action调度、job管理
- `dashboard/server.py`：已有 `/api/studio/action`、`/api/studio/jobs`、`/api/studio/fast-snapshot`
- `dashboard/web/app.js`：已有Judge视图、动作触发、状态轮询

### 关键已知问题
- `detect_deploy_url()` 不读取 `output.deployed_url`，导致 `go_to_landing` gate 失败
- 仓库内无显式 Z.AI GLM 调用模块（需新增）
- boulder.json 指向旧计划 `ceoclaw-submission.md`（需更新）

### 约束
- 不破坏既有 `/api/studio/*` 接口
- 默认 simulation-first，不做真实外联
- GLM失败不得静默fallback
- 不做大规模UI重构，只做最小增量

## [2026-03-07] T1: GLM前置门禁

### 新增文件
- `dashboard/zai_preflight.py` — Z.AI GLM预检门禁模块
- `dashboard/zai_preflight_contract.md` — 门禁契约文档（含JSON Schema）
- `.sisyphus/evidence/task-1-glm-preflight-pass.json` — 预检通过 mock 证据
- `.sisyphus/evidence/task-1-glm-preflight-fail.json` — 预检失败 mock 证据

### 关键决策
- 凭据检查仅做 `os.environ.get(ZAI_API_KEY_ENV)` 存在性检查，**不做真实API调用**，避免 key 泄露
- `ZAIPreflightError` 继承 `RuntimeError`，携带 `field` 和 `reason` 属性，消息包含明确诊断信息
- 审计字段 schema：`{provider, model, step, latency_ms, token_usage, request_id}`，符合 JSON Schema Draft-07
- `token_usage` 在预检阶段永远为 `null`（无网络调用）
- `request_id` 是 UUID4 hex（32位小写十六进制）

### 约束严守
- 不修改 `server.py` / `studio.py`
- 不打印明文 key
- 失败路径不静默 fallback，`ZAIPreflightError` 必须传播到调用方
- `provider="z.ai"`, `model="glm-4.5"` 是常量，不允许调用方覆盖

### 与现有代码的对齐
- 异常风格对齐 `StudioError(RuntimeError)`（`studio.py` 第191行）
- 常量命名风格对齐 `COPILOT_TIMEOUT_SECONDS`、`COPILOT_TO`（`studio.py`）
- section 分隔符 `# ---` 风格与 `studio.py` 保持一致
