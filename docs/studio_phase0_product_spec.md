# OperatorOne Venture Studio - Phase 0 产品化设计稿

## 目标

把当前「监控型 dashboard」升级为「可选择、可执行、可审计、可闭环」的 Venture Studio。

用户路径：

1. 从 Product 的 startup ideas 中选项目
2. 触发 Product 产出（web product + landing）
3. 选择 Marketing 内容与 campaign
4. 执行 Sales 线索/外联/转化
5. 用 Operations 追踪并回写下一轮待办

---

## 设计原则（含行业方案映射）

1. **Human-in-the-loop**（AWS Step Functions / Prefect HITL 思路）
   - 关键外联与推进动作必须人工确认。
2. **Policy-as-code**（OPA 思路）
   - 可否外联由规则判定，而非临场主观判断。
3. **Decision-oriented dashboard**（SRE dashboard 原则）
   - 看板优先回答“下一步能不能做、为什么”。
4. **Feature flags / mode toggle**（Feature Toggle 实践）
   - simulation/live 两套执行模式可切换。
5. **Deployment safety gate**（GitHub environment protection 思路）
   - live 动作必须通过 gate（manual arm + confirm）。

---

## 核心对象

### 1) venture

单个商业项目实例，贯穿全流程。

- id
- opportunityId
- name
- stage（IDEA_POOL → ... → ITERATE）
- status
- decisions（内容选择/campaign选择/是否进入下一轮）
- outputs（各阶段产物索引）

### 2) stage_run

每次执行动作的一条可审计记录。

- action、stage、mode
- command（已脱敏）
- startedAt / endedAt / durationMs
- status / error
- artifacts（源文件与快照映射）

### 3) decision_gate

关键人工决策点。

- gateId
- stage
- decision（approved/rejected/pending）
- reason
- decidedAt

### 4) artifact

流程产物统一映射。

- sourcePath（仓库内真实路径）
- snapshotPath（venture 独立快照）
- type（json/md/html/url）

### 5) kpi_snapshot

运营指标快照。

- metrics（sessions/signups/mrr/feedback/iteration decisions）
- capturedAt

---

## 状态机

`IDEA_POOL -> SELECTED -> PRODUCT -> MARKETING -> SALES -> OPERATIONS -> ITERATE`

- `IDEA_POOL`：刷新 ideas、选中项目
- `SELECTED`：建立 venture 上下文
- `PRODUCT`：landing + build/deploy
- `MARKETING`：SEO/content/campaign + 人工选择
- `SALES`：prospect/outreach/conversion
- `OPERATIONS`：tracking/feedback/iteration
- `ITERATE`：回写后进入下一轮（需人工确认）

---

## 每阶段自动项与人工项

详见 `dashboard/config/studio_phase0.json`，核心规则：

- 自动项负责“生成候选、同步产物、形成待办”。
- 人工项负责“高风险确认、业务判断、最终推进”。

---

## 执行模式

### simulation（默认）

- 不触发真实外联
- Product 产出本地预览
- Marketing/Sales 默认 shadow/simulate

### live

- 需要 `manual arm ON`
- 需要 API 请求显式 `confirm_live=true`
- Product 可尝试 Vercel 部署（凭据存在时）
- Sales 才允许 commit 级外联动作

---

## 关键验收标准

1. 用户能从 startup ideas 中创建 venture 并选择执行。
2. 每个阶段都能看到输入、输出、候选、选择与执行结果。
3. 所有执行都有 stage_run 审计轨迹和产物快照。
4. 默认 simulation，live 动作必须双重确认。
5. Operations 回写待办后，必须人工确认才进入下一轮。
