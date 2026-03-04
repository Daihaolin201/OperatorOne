# Stage1 计划（Marketing）— SEO Experiments 能力建设（Continuous Shadow Mode）

## 0) 目标（能力导向，不绑定单一项目）
建立一个**可连续运行**的 SEO 实验系统能力，而不是做某个业务项目的一次性计划。

该能力需要满足：
- 自动吸收 `op1_product` 产出的任意商业上下文；
- 自动生成并维护 SEO 实验队列；
- 自动完成 Shadow 评估与优先级调整；
- 在 `publish=false` 下稳定循环运行（黑客马拉松阶段先不上线实盘）。

---

## 1) 运行模式（Continuous Loop）
- `mode=shadow`
- `publish=false`
- `index=false`
- `continuous=true`

### 触发条件
1. 发现新的/变更的产品产物（如新的 project spec、landing package、blueprint）。
2. 手动触发一次全量重跑。
3. 定时触发增量重算（仅更新受影响主题与实验）。

---

## 2) 输入契约（Project-agnostic）
系统不写死某个业务名，而是统一读取“可营销化上下文对象（context objects）”。

### 上游来源（自动发现）
- `research/stage1_idea_discovery/opportunity_records.json`
- `research/stage2_idea_screening/decision_log.json`
- `research/stage3_mvp_scope/project_blueprint.json`
- `research/landing_v1/landing_package.json`
- `research/build_deploy_v1/project_spec*.json`
- `research/live_examples.latest.json`

### 统一上下文字段（最小必需）
- `context_id`
- `icp`
- `problem_statement`
- `value_proposition`
- `proof_points[]`
- `faq[]`
- `cta`
- `risk_if_wrong[]`
- `kill_criteria[]`

只要满足最小字段，即可进入 SEO 实验循环。

---

## 3) 输出契约（能力产物）
统一输出到：`research/stage1_marketing_seo/`

1. `run.latest.json` — 最新一次执行摘要（状态、耗时、输入版本）
2. `state.latest.json` — 连续运行状态（队列、指针、失败重试状态）
3. `context_index.latest.json` — 当前可用上下文索引
4. `keyword_graph.latest.csv` — 跨上下文关键词图谱
5. `experiments.backlog.latest.json` — 全量实验池
6. `experiments.queue.latest.json` — 当前优先队列（Ready 集合）
7. `briefs/` — 可直接用于内容生产的实验 brief
8. `scoreboard.latest.json` — Shadow 评分与决策
9. `decision_log.latest.md` — Go/No-Go 与淘汰原因

---

## 4) 核心能力流水线（持续循环）

### A. Context Harvester
- 自动发现并解析上游产物。
- 将异构结构标准化为统一 context objects。

### B. Keyword Graph Engine
- 基于 context 自动扩展关键词：问题型/模板型/对比型/决策型。
- 自动分类 intent（TOFU/MOFU/BOFU）并去重。

### C. Experiment Synthesizer
- 自动生成实验卡：
  - 标题变量
  - 内容结构变量
  - CTA 变量
  - 证据呈现变量
- 每张实验卡必须包含：
  - `hypothesis`
  - `change`
  - `primary_metric`
  - `guardrail_metrics`
  - `success_rule`
  - `stop_rule`

### D. Shadow Evaluator
- 对实验做离线评分（不依赖实盘流量）：
  1) Intent Match
  2) Problem-Message Fit
  3) Differentiation
  4) Conversion Readiness
  5) Execution Risk（反向）
- 输出分数 + 置信度 + 风险说明。

### E. Queue Manager
- 依据评分和风险自动排序，维护 `Ready / Hold / Drop` 三态。
- 当上游上下文变化时，仅局部重算受影响实验（增量更新）。

---

## 5) 状态机（实验生命周期）
`candidate -> drafted -> scored -> ready -> shadow_validated -> promoted | dropped`

### 自动迁移规则（示例）
- `scored >= threshold && risk <= limit` -> `ready`
- 连续两轮 shadow 评分下降且低于阈值 -> `dropped`
- 上游 context 发生结构变化 -> 回退到 `drafted` 重新生成

---

## 6) Stage1 验收（能力是否具备）
以下全部满足才算 Stage1 完成：

1. **连续性**：可重复运行，不依赖“Day1/Day2”人工节奏。  
2. **通用性**：接入新业务上下文无需改代码（仅新增输入文件）。  
3. **自动化**：一条命令/一次触发即可生成完整 SEO 实验资产。  
4. **可追溯**：每个实验都能反向追溯到来源 context。  
5. **可决策**：系统自动产出 `Ready/Hold/Drop` 队列与原因。  
6. **可切换实盘**：保留 `publish` 开关，Stage2 可无缝切到真实发布。  

---

## 7) 风险与控制
- **风险：上游字段不完整导致实验质量波动**  
  - 控制：字段校验 + 缺失字段降权，不阻塞全局循环。
- **风险：Shadow 与真实表现偏差**  
  - 控制：Stage2 接入实盘指标后做校准，不在 Stage1 过拟合评分器。
- **风险：实验池爆炸导致噪音**  
  - 控制：队列上限 + 低分自动淘汰 + 增量重算。

---

## 8) Stage1 与后续的边界
- Stage1 只交付“**连续 SEO 实验能力**”。
- 不要求真实流量结果，不要求上线投放，不要求内容发布执行。
- Stage2 才开启 `publish=true` 并接入真实反馈闭环。
