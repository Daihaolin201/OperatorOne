# Convert Early Customers（Stage3）完整实现计划 v2（详细版）

生成时间：2026-03-04
负责人：op1_sales
目标：在**一次集成交付**中把“Convert early customers”从可分析状态升级为可执行、可回写、可复盘的完整能力。

---

## 1) 先说结论：什么叫“完整实现”

这次不做半成品。完整实现定义为：

1. 能把 Stage2 线索自动推进到 Stage3 转化状态机。
2. 能为每个活跃机会产出可执行成交动作（不是泛文案）。
3. 能跟踪试点 onboarding 与首个价值点（TTFV）。
4. 能识别“已承诺/已付费/已丢单”并沉淀原因。
5. 能把结果自动回写到运营交接文件与周报板。
6. 能从真实异议中自动刷新成交打法。

只要这 6 条全满足，才算完成。

---

## 2) 搜索与分析后的事实基线（内部 + 外部）

## 内部（OperatorOne）

- Stage1/Stage2 已完成并可跑通（识别、外联、回复处理、指标回写）。
- 产品 Stage3 蓝图已给出明确转化目标：
  - 14天 pilot；20 个目标用户；
  - 目标：>=6 qualified pilot signup，且 >=2 paid starts（或签署付费承诺）。
- 价格假设已存在（invoice/chargeback/reporting 等）。
- 当前指标（样例数据）已出现：1 booked、1 converted、1 budget objection。

关键风险（已发现）：
- 当前队列文件可被“重建覆盖”，状态可能回退；因此 Stage3 必须以 **events 流**为主真相源（source of truth），而不是只读最新队列快照。

## 外部（web_fetch）

- 成交实践：明确 close ask + 异议处理闭环（先确认、再回应、再确认）。
- Onboarding 实践：首价值交付速度直接影响 trial/pilot 转付费。
- 指标实践：必须追踪转化漏斗和收入指标，不追 vanity。
- 合规/投递：CAN-SPAM、Gmail sender guidelines 必须前置。

运行环境约束：
- `web_search` 当前不可用（缺 Brave API key），所以外部研究基于 `web_fetch`。
- 运行时通道未配置，真实外发依赖环境配置；但 Stage3 能力本身可完整实现（文件化/事件化闭环）。

---

## 3) 一次集成交付的总体方案（不拆 Phase，直接一体化）

## 总体设计原则

- 一个总入口脚本（one-command orchestration）。
- 多个可复用子模块（便于调试），但对操作者是一条命令。
- 事件优先：所有状态变化都落事件日志，保证可追溯。

## 一次交付的脚本清单（新增）

1. `workspaces/op1_sales/scripts/build_conversion_pipeline_stage3.py`
2. `workspaces/op1_sales/scripts/build_close_motion_stage3.py`
3. `workspaces/op1_sales/scripts/track_pilot_onboarding_stage3.py`
4. `workspaces/op1_sales/scripts/process_conversion_events_stage3.py`
5. `workspaces/op1_sales/scripts/render_conversion_scoreboard_stage3.py`
6. `workspaces/op1_sales/scripts/run_convert_early_customers_stage3.py`  ← 总入口

> 操作体验：只需运行第 6 个脚本；其余由总入口按顺序调度。

---

## 4) 统一数据模型（确保“完整能力”可验证）

## 核心状态机（lead/customer lifecycle）

- `qualified_interest`
- `discovery_scheduled`
- `discovery_completed`
- `pilot_offered`
- `pilot_active`
- `pilot_value_confirmed`
- `commercial_terms_sent`
- `commitment_received`
- `paid_started`
- `closed_lost`

## 每条机会记录必填字段

- `lead_id`, `opportunity_id`, `segment_name`
- `current_stage`, `stage_entered_at`, `stage_history[]`
- `conversion_readiness_score`（0-100）
- `objections_open[]`, `objections_resolved[]`
- `pilot_plan`（目标、范围、成功判定）
- `next_best_action`, `next_action_due_at`, `owner`
- `evidence`（reply/event/url）

## 转化事件（JSONL）

文件：`research/conversion/conversion_events.latest.jsonl`

事件类型：
- `conversion_stage_changed`
- `discovery_booked`
- `pilot_started`
- `pilot_value_confirmed`
- `terms_sent`
- `commitment_received`
- `paid_started`
- `closed_lost`
- `objection_logged`
- `objection_resolved`

---

## 5) “一步达成”执行流程（总入口内部实际做的事）

`run_convert_early_customers_stage3.py` 内部固定执行以下动作：

1. 读取 Stage2 事件与队列，构建统一 LeadIndex。
2. 根据事件推进状态机，生成 `conversion_pipeline.latest.json`。
3. 按每条机会生成 close motion（成交动作包）。
4. 基于产品蓝图生成 pilot onboarding checklist，写入 onboarding 追踪文件。
5. 解析最新回复/notes 中的承诺信号（commitment/paid/lost），更新状态与事件。
6. 重算转化看板，产出 scoreboard，并回写 `handoffs/sales_to_operations.json`。
7. 从异议事件生成最新版 objection playbook（可直接给外联/成交使用）。

---

## 6) 计划产物（一次运行后应全部出现）

- `workspaces/op1_sales/research/conversion/conversion_pipeline.latest.json`
- `workspaces/op1_sales/research/conversion/close_motion.latest.md`
- `workspaces/op1_sales/research/conversion/pilot_onboarding.latest.json`
- `workspaces/op1_sales/research/conversion/conversion_events.latest.jsonl`
- `workspaces/op1_sales/research/conversion/objection_playbook.latest.md`
- `workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.md`

并更新：
- `handoffs/sales_to_operations.json`

---

## 7) 成交动作包（close motion）标准模板

每条活跃机会必须包含：

1. **价值回顾**：问题基线 + 预计收益（时间/现金流/风险）。
2. **证据链**：对应 reply/event/pain 信号。
3. **本次明确请求（single ask）**：
   - `启动14天pilot` / `签付费承诺` / `直接付费启动` 三选一。
4. **异议处理卡**：
   - budget / integration / trust / timing 的短回应。
5. **下一动作与截止时间**：
   - 24h / 48h / 72h SLA。

---

## 8) Onboarding + TTFV 机制（防止“答应了但不转化”）

每个 `pilot_active` 机会自动生成 onboarding 任务：

- 数据准备完成
- 首次动作执行
- 首个可见结果记录（TTFV）
- 每周复盘记录

触发规则：
- 超过 72 小时无 TTFV → 自动标记 `onboarding_at_risk` 并生成救援动作。

---

## 9) 计分与看板（严格反 vanity）

## 主要指标
- `qualified_interest_to_pilot_rate`
- `pilot_to_commitment_rate`
- `commitment_to_paid_start_rate`
- `median_time_to_first_value`
- `median_time_to_paid_start`

## 收入与质量指标
- `new_customers_converted`
- `new_business_mrr_proxy`
- `asp_proxy`
- `objection_resolution_rate`
- `closed_lost_reason_mix`

## 护栏指标
- `opt_out_rate`
- `onboarding_stall_rate`
- `no_response_after_terms_rate`

---

## 10) 质量门禁（DoD 验收清单）

只有全部通过才算“完整实现完成”：

1. 总入口脚本可一键运行成功。
2. 六个 conversion 产物文件全部生成。
3. 状态机可从事件正确推进并可追溯。
4. 每个活跃机会都有 next action + due date。
5. onboarding 文件包含 TTFV 字段与风险标记。
6. commitment/paid/lost 信号能被识别并写事件。
7. objection playbook 自动按最新事件刷新。
8. scoreboard 可计算完整漏斗转化率。
9. `sales_to_operations.json` 自动回写关键指标。
10. 对无真实通道/无真实联系人场景可降级运行（不崩）。

---

## 11) 你关心的“能不能完整做成”——可达成性判断

结论：**可完整达成**。

原因：
- 现有 Stage2 已具备事件流、状态更新、审批和回写能力；
- Stage3 只需在此基础上补“成交状态机 + onboarding + commitment + scoreboard”；
- 不依赖新增外部 API 才能完成能力本体。

仅有前置依赖（影响“真实外部成交执行”，不影响能力完整性）：
- 真实联系人数据
- 通道配置（若要自动化真实发送）

---

## 12) 执行后你会拿到什么

一次运行后，你将直接拿到：

- 谁最可能近7天转化（按 readiness 排名）
- 每个机会今天该做什么（带截止时间）
- 哪些 pilot 在卡住（含救援动作）
- 本周转化率与丢单原因（可直接管理复盘）

这就是“Convert early customers”从能力角度的完整闭环。
