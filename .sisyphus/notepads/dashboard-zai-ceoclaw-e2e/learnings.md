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

## [2026-03-07] T3: Dashboard CTA骨架

### 新增前端组件
- `dashboard/web/index.html`：新增 CTA section (button + badge + error banner)
- `dashboard/web/styles.css`：新增 `.run-demo-btn`, `.run-id-badge`, `.run-error-banner` 样式
- `dashboard/web/app.js`：新增事件监听与 API 调用逻辑

### 关键决策
- **Mock优先**：考虑到 `/api/runs` 后端尚未就绪，前端实现自动 fallback (404/500 -> generate local ID)
- **非侵入式布局**：将 CTA 放置在 main 顶部，作为独立 section，不破坏现有 grid/card 结构
- **交互反馈**：点击即 disable，防止重复提交；成功显示 run_id，失败显示错误条
- **纯原生实现**：不引入 React/Vue 等框架，保持与现有 vanilla JS/CSS 一致

### 约束严守
- 未修改 `dashboard/server.py`（后端留给 T7）
- 保持 `judge` 和 `builder` 模式可见性（放在通用区域）
- 样式复用现有 CSS 变量 (`--btn`, `--card`, `--ok`, `--fail`)

## Task 10 - OpenClaw Agent Direct Invocation (2026-03-07)

### Gateway State
- Gateway confirmed running at `ws://127.0.0.1:30740` (pid 12880, state active)
- OpenClaw version: 2026.3.2
- Model: gpt-5.3-codex (200k context)

### All 5 Agents Respond Successfully
- `op1_product`: Stage 1 (idea discovery/screening), Stage 2 (build & deploy web MVPs), Stage 3 (landing page creation/handoff)
- `op1_marketing`: Stage1 (SEO experiments), Stage2 (content publishing), Stage3 (campaign launch)
- `op1_sales`: Stage 1 (prospect identification), Stage 2 (outreach/follow-ups), Stage 3 (early customer conversion to paid)
- `op1_operations`: Stage 1 (traffic/signups/revenue), Stage 2 (feedback processing), Stage 3 (iteration and rollout decisions)
- `op1_ceo`: Cross-agent orchestrator — translates goals into plans, gates external actions, audits venture state

### CLI Invocation Pattern (macOS)
- macOS has no native `timeout` command. Use perl wrapper:
  ```bash
  perl -e 'alarm(120); exec @ARGV' openclaw --profile operatorone agent --agent <id> --message "..." --json 2>&1
  ```
- `gtimeout` (coreutils) not installed by default either
- `exit_code=-1` from perl wrapper does not indicate failure — check JSON `status` field instead

### Safety Pattern
- `grep -ri "deliver|telegram|whatsapp|discord|slack" test_results/task-10-openclaw-*.json` → 0 matches ✅
- Never use `--deliver` flag — sends to external channels
- Safe test message: "What is your role and what stages do you handle? Reply briefly."

### Response Sizes
- All agents return ~10k chars of JSON (mostly system prompt metadata)
- Actual agent response text is in `.result.payloads[0].text`

## Task 11 - Capability Matrix Consolidation (2026-03-07)

### Data Consolidation Pattern
- Matrix compilation should anchor on canonical JSON summaries first (`test_results/*_results.json`), then use evidence `.txt` files only for command-level notes.
- When source files are missing (for this run: `test_results/handoff_validation_report.json`, `test_results/file_inventory.json`), fall back to validated canonical artifact paths already referenced by earlier evidence (`handoffs/_meta/validation_report.latest.json`, backup/inventory evidence txt files).

### Matrix Schema Discipline
- Keep agent stage status values normalized to `pass|fail|skip` even if upstream files use `PASS` or `ok`.
- Include explicit `scripts_run` and `outputs_verified` arrays for every stage block to avoid implicit claims.
- Record openclaw success using response-level evidence (`status=ok`, `has_valid_json=true`, `response_length`) rather than wrapper exit code alone.

### Quality Gates That Caught Issues
- JSON structure validation plus strict key assertions (`5 agents`, required top-level sections) provides fast integrity checks.
- Markdown table-density checks (`wc -l`, pipe count, agent mention count, pass/fail/skip keyword count) are practical for report quality enforcement.
- Capability-point counting script is useful for objective coverage tracking; this run totals `35` points.

## [2026-03-07] T7: Dashboard API /runs

### 文件改动
- `dashboard/server.py`：升级 `_handle_post_runs`，新增 4 个 helper + 3 个 handler

### 新增方法（server.py DashboardHandler）
- `_build_run_object(payload)` — 从请求 payload 构建 API run 对象，run_type="api" 区分 studio stage runs
- `_find_active_api_run()` — 查找 status 为 queued/running 的 API run（幂等控制）
- `_get_api_run_by_id(run_id)` — 按 run_id 查找 API run
- `_upsert_api_run(run)` — 写入/更新 runs.json，bounded 到 500 条
- `_handle_get_run(run_id)` — GET /api/runs/<id>
- `_handle_get_run_events(run_id)` — GET /api/runs/<id>/events（JSON poll，非 SSE）
- `_handle_post_run_cancel(run_id)` — POST /api/runs/<id>/cancel（T11 骨架）

### 路由注册
- do_GET：`/api/runs/<id>` → `_handle_get_run`；`/api/runs/<id>/events` → `_handle_get_run_events`
- do_POST：`/api/runs` → `_handle_post_runs`；`/api/runs/<id>/cancel` → `_handle_post_run_cancel`

### 关键决策
- `run_type: "api"` 字段区分 API runs 与 studio stage runs（共用 `stage_runs.json` / `_load_runs/_save_runs`）
- 幂等策略：存在 queued/running API run 时直接返回 `{reused: true}`（200），不创建新 run
- cancel 只允许 queued/running 状态，已完成/失败/已取消返回 409
- `_upsert_api_run` 加 `STUDIO.store_lock` 锁，与 studio.py 的并发安全模式一致
- run 对象字段：`run_id, run_type, status, current_step, started_at, finished_at, mode, model_provider, model_name, steps[], events[]`
- 默认值：`mode=simulation, model_provider=z.ai, model_name=glm-5`

### 证据
- `.sisyphus/evidence/task-7-runs-api-happy.json` — 真实 curl 响应 (POST→GET→GET events)
- `.sisyphus/evidence/task-7-runs-api-idempotent.json` — 幂等复用测试（reused=true）

### 约束遵守
- 未修改 `studio.py`
- 未删除现有逻辑，仅升级 `_handle_post_runs`
- 无 API key 出现在证据文件中
- 现有 `/api/studio/*` 接口未受影响
