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

## [2026-03-07] T4: Run Evidence Schema

### 新增文件
- `dashboard/run_evidence_schema.py` — Run 级 evidence index 定义模块
- `.sisyphus/evidence/run_evidence_schema.json` — JSON Schema Draft-07 规范文档
- `.sisyphus/evidence/task-4-evidence-index.json` — 完整 mock run evidence 示例
- `.sisyphus/evidence/task-4-missing-artifact.txt` — validate 函数演示文档

### RunEvidenceIndex Schema 核心字段
- `run_id`: 不可变运行标识 (run_<12char-hex>)
- `status`: queued | running | succeeded | failed | cancelled
- `mode`: simulation | live
- `started_at`, `finished_at`: ISO 8601 UTC 时间戳
- `stages[]`: 每个 stage 记录包含 {name, status, started_at, finished_at, error?}
  - stage.name: product, marketing, sales, operations
  - stage.status: queued | running | succeeded | failed
- `model_usage`: {provider, model, total_calls, total_tokens}
  - 与 T1 审计字段风格对齐（provider, model）
  - total_calls / total_tokens 聚合整个 run 的消费
- `artifacts[]`: 每项 {name, path, exists}
  - path: repo-relative，禁止绝对路径
  - exists: false 时 validate_evidence_index 会标记为 missing_artifact

### validate_evidence_index() 函数逻辑
```python
(valid: bool, missing_fields: List[str]) = validate_evidence_index(index_dict)
```
- 检查必填字段存在性（run_id, status, mode, started_at, finished_at）
- 检查字段类型正确性（str, int, bool, dict, list）
- 递归验证 stages[] / model_usage / artifacts[] 结构
- **核心功能**：检测 artifacts[i].exists=false，标记为 missing_artifact
- 返回 (valid, missing_fields_list)，失败时 missing_fields 非空

**不做**的验证（留给 JSON Schema）：
- 枚举值有效性（status="in_progress" 等）
- 时间戳格式与一致性
- artifact path 绝对化检查
- token 数值精度

### 与现有代码对齐
- model_usage 中 provider="z.ai", model="glm-4.5" 与 T1 审计一致
- stage 名称列表与 studio.py STAGE_ORDER 对齐（product, marketing, sales, operations）
- artifact 数据结构与 stage_runs.json "artifacts" 字段兼容
- JSON Schema 采用 Draft-07 标准，供评委参考

### 约束遵守
- 仅用 Python 标准库（dataclass, typing）
- 无外部依赖
- 所有 JSON 文件均人类可读
