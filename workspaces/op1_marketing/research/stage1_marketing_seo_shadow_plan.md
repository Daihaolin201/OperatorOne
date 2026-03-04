# Stage1 计划（Marketing）— SEO Experiments 能力建设（Continuous Shadow Mode）

## 0) 目标（能力导向）
你说的方向是对的：**Marketing Stage1 必须先完整接入 Product 产物**，再做 SEO 实验。

因此 Stage1 的定义是：
- 先做 `op1_product` 全量产物同步（lossless），把 Product 当作唯一事实源；
- 再在同步后的完整输入上，连续运行 SEO 实验循环；
- 不绑定单一商业项目，不上线实盘（shadow only）。

---

## 1) 运行模式（Continuous Loop）
- `mode=shadow`
- `publish=false`
- `index=false`
- `continuous=true`

### 触发方式
1. 上游 Product 产物变更触发增量循环；
2. 手动触发全量重建；
3. 定时健康重算（校验状态一致性）。

---

## 2) 输入契约（完整 Product 产物输入，非抽样）

## 2.1 必收清单（Required）
以下路径作为 Stage1 的**完整输入集合**：

- `../op1_product/research/stage1_idea_discovery/opportunity_records.json`
- `../op1_product/research/stage2_idea_screening/scoring.csv`
- `../op1_product/research/stage2_idea_screening/decision_log.json`
- `../op1_product/research/stage3_mvp_scope/project_blueprint.json`
- `../op1_product/research/stage2_web_product/run.latest.json`
- `../op1_product/research/stage2_web_product/state.latest.json`
- `../op1_product/research/stage3_landing_launch/run.latest.json`
- `../op1_product/research/live_examples.latest.json`
- `../op1_product/research/build_deploy_v1/project_spec*.json`
- `../op1_product/research/landing_v1/landing_package.json`
- `../op1_product/research/landing_v1/landing_contract_test.latest.json`
- `../op1_product/research/landing_v1/landing_semantic_test.latest.json`
- `../../handoffs/product_to_marketing.json`

> 说明：`project_spec*.json` 代表全部 spec，不允许只取单个项目。

## 2.2 输入处理原则（必须遵守）
1. **先镜像后解析**：先把所有必收文件完整镜像，再做结构化提取。  
2. **禁止预筛选**：不能先人工挑“看起来有用”的片段。  
3. **缺失即阻塞**：任一 Required 文件缺失，状态标记为 `blocked_input_incomplete`。  
4. **可校验版本**：每个输入文件记录 hash/mtime/size，支持可追溯 diff。  

## 2.3 输入层产物
输出到 `research/stage1_marketing_seo/input/`：
- `product_snapshot.latest.json`（完整输入清单 + hash）
- `delta.latest.json`（本轮与上轮差异）
- `mirror.latest/`（完整镜像目录，供下游统一读取）

---

## 3) 输出契约（能力产物）
统一输出到：`research/stage1_marketing_seo/`

1. `run.latest.json` — 本轮执行摘要
2. `state.latest.json` — 连续状态（loop/queue/retry）
3. `context_index.latest.json` — 从完整镜像生成的上下文索引
4. `keyword_graph.latest.csv` — 跨上下文关键词图谱
5. `experiments.backlog.latest.json` — 全量实验池
6. `experiments.queue.latest.json` — 当前优先队列（Ready/Hold/Drop）
7. `briefs/` — 实验 brief 产物
8. `scoreboard.latest.json` — Shadow 评分结果
9. `decision_log.latest.md` — 决策与淘汰理由

---

## 4) 核心能力流水线（持续循环）

### A. Product Artifact Sync（新增首步）
- 扫描 Required 清单并镜像全部输入。
- 生成 snapshot + delta。
- 未通过完整性校验则不进入下游。

### B. Context Index Builder
- 从 `input/mirror.latest/` 构建统一上下文索引。
- 索引需保留 source pointer（可回溯到原文件与字段）。

### C. Keyword Graph Engine
- 基于上下文自动扩展关键词（问题型/模板型/对比型/决策型）。
- intent 分类（TOFU/MOFU/BOFU）+ 去重。

### D. Experiment Synthesizer
- 自动生成实验卡（标题/结构/CTA/证据变量）。
- 每卡必须具备：`hypothesis`, `change`, `primary_metric`, `guardrail_metrics`, `success_rule`, `stop_rule`。

### E. Shadow Evaluator
- 离线评分：Intent Match / Problem-Message Fit / Differentiation / Conversion Readiness / Execution Risk。
- 产出分数、置信度、风险说明。

### F. Queue Manager
- 维护 `Ready / Hold / Drop` 队列。
- 基于 `delta.latest.json` 只重算受影响实验（增量）。

---

## 5) 状态机（实验生命周期）
`candidate -> drafted -> scored -> ready -> shadow_validated -> promoted | dropped`

### 关键迁移
- `input_changed`：相关实验回退到 `drafted` 重算
- `scored >= threshold && risk <= limit`：进入 `ready`
- 连续两轮低于阈值：进入 `dropped`

---

## 6) Stage1 验收（能力是否具备）
以下全部满足才算完成：

1. **连续性**：可重复运行，不依赖人工日程。
2. **完整输入**：Required 清单完整接入率 100%。
3. **自动化**：一次触发可完成“同步→实验→评分→队列”。
4. **可追溯**：每个实验可反查到 Product 源文件字段。
5. **可决策**：系统自动输出 Ready/Hold/Drop 与理由。
6. **可切换实盘**：保留 publish 开关，Stage2 可直接开启实盘。

---

## 7) 风险与控制
- **风险：上游文件结构变更**  
  - 控制：schema version + 兼容解析层 + 变更告警。
- **风险：Shadow 与真实表现偏差**  
  - 控制：Stage2 引入实盘后校准评分器，不在 Stage1 过拟合。
- **风险：输入过大导致循环变慢**  
  - 控制：镜像全量、计算增量（delta 驱动重算）。

---

## 8) Stage1 与后续边界
- Stage1 仅交付“**完整输入 + 连续 SEO 实验能力**”。
- 不要求真实流量结果，不要求发布或投放。
- Stage2 才开启 `publish=true` 并接入真实反馈闭环。
