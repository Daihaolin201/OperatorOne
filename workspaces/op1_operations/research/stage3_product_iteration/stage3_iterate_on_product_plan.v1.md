# Stage3 能力设计（Iterate on product）

生成时间：2026-03-05
Owner：`op1_operations`

---

## 0) 目标定义（Stage3）

**Stage3 = 把 Stage1 的量化漏斗 + Stage2 的反馈洞察，转化为可持续、可复现、可审计的产品迭代系统。**

不是“做功能”，而是建立一条闭环：

`洞察 -> 假设 -> 方案 -> 实验 -> 发布 -> 评估 -> 决策 -> 下一轮`

核心目标：
1. 提高学习速度（learning velocity）
2. 提高迭代成功率（win rate）
3. 提高关键经营指标（visit->signup、signup->paid、net new MRR）
4. 控制变更风险（回滚、失败发布、指标污染）

---

## 1) 当前基线（来自已完成 Stage1/Stage2）

- Stage1（tracking）
  - sessions: `905.67`
  - qualified_signups: `13`
  - paid_customers: `1`
  - net_new_mrr: `$49`
  - milestone progress: `49%` to `$100 MRR`

- Stage2（feedback）
  - feedback_events_total: `31`
  - themes_total: `16`
  - top topics: onboarding / pricing / trust
  - expected_mrr_delta_30d（from queue model）: `$77.101`
  - alerts_count: `0`

这意味着 Stage3 已具备最关键前提：
- 有漏斗和收入基线（Stage1）
- 有结构化问题优先级（Stage2）

---

## 2) 业界领先方案的共性（搜索+分析结论）

在多源资料中，高绩效产品组织的共性不是某个工具，而是同一套机制：

1. **连续发现（Continuous Discovery）**
   - 机会树（Opportunity Solution Tree）驱动，避免直接跳“功能解”。
2. **双轨并行（Discovery + Delivery）**
   - 发现轨（验证问题与方案）与交付轨（稳定发布）并行。
3. **实验优先（Experiment-first）**
   - 先定义假设/指标/护栏，再开发。
4. **可信实验（Trustworthy Experimentation）**
   - 指标质量、样本分配异常（SRM）、告警与诊断机制必须内建。
5. **渐进发布（Progressive Rollout）**
   - feature flag + 分批放量 + kill switch，控制线上风险。
6. **交付性能治理（DORA/Four Keys）**
   - 发布频率、交付前置时间、变更失败率、恢复时间是迭代效率底盘。
7. **明确停手条件（Stop rules）**
   - 每轮迭代要有“继续/停止/回滚”客观阈值。

---

## 3) Stage3 全能力模型（完整能力清单）

## A. 输入治理能力（Inputs for iteration）
- 汇聚 Stage1 指标、Stage2 priority queue、Product build/deploy 结果
- 输出标准化迭代输入包
- 产物：`research/stage3_product_iteration/iteration_inputs.latest.json`

## B. 机会-方案树能力（OST）
- 从 top theme 自动生成 `opportunity -> solution options -> experiment` 树
- 产物：`opportunity_solution_tree.latest.json`

## C. 假设库能力（Hypothesis Registry）
- 每个迭代项必须有：
  - user segment
  - problem statement
  - expected behavioral change
  - metric delta target
  - invalidation condition
- 产物：`hypothesis_registry.latest.jsonl`

## D. 实验契约能力（Experiment Contract）
- 必填字段：experiment_id、variant、targeting、success metric、guardrails、sample rule、stop rule
- 产物：`contracts/stage3_experiment_contract.v1.json`

## E. 指标与护栏能力（Primary + Guardrail Metrics）
- 主指标：visit->signup, signup->paid, net_new_mrr
- 护栏指标：unsubscribe/complaint rate、error rate、latency、conversion异常波动
- 产物：`config/stage3_metric_guardrails.v1.yaml`

## F. 实验设计能力（Design & power heuristics）
- 支持 A/B、多变体、渐进发布实验
- 定义最小样本、最短观察窗、可提前停止条件
- 产物：`experiment_design.latest.json`

## G. 变体生成能力（Variant Builder）
- 基于现有 `op1_product` 模块化页面策略自动生成 v1/v2 变体 spec
- 产物：`variant_specs.latest.json`

## H. 发布控制能力（Release Safety）
- feature flag
- progressive rollout（1%→5%→20%→50%→100%）
- kill switch
- 产物：`rollout_log.latest.json`

## I. 在线监控能力（Live Monitor）
- 实验期间实时检查：
  - SRM（样本分配异常）
  - 数据延迟
  - 护栏指标越线
- 产物：`experiment_monitor.latest.json`

## J. 实验评估能力（Evaluation Engine）
- 评估输出：
  - observed lift
  - confidence/uncertainty
  - decision recommendation
- 产物：`experiment_results.latest.json`

## K. 决策引擎能力（Decision Policy）
- 统一规则：`ship / iterate / rollback / park`
- 产物：`iteration_decision_log.latest.json`

## L. 学习沉淀能力（Learning Repository）
- 记录每个实验的“做了什么、学到了什么、为何停手”
- 产物：`learning_log.latest.md`

## M. 迭代吞吐能力（Portfolio/WIP）
- 控制并行实验上限、避免上下文切换失控
- 产物：`iteration_portfolio.latest.json`

## N. 交付效率能力（DORA/Four Keys）
- 追踪 delivery 性能（发布频率、lead time、change failure、restore time）
- 产物：`delivery_performance.latest.json`

## O. 质量与可复算能力（Reproducibility）
- 固定 `STAGE3_AS_OF` 双跑一致
- strict baseline hash check
- 产物：`reproducibility_report.latest.json`

## P. Stage3 Scoreboard 能力
- 汇总：实验状态、成功率、净影响、风险、下轮建议
- 产物：
  - `stage3_iteration_scoreboard.latest.json`
  - `stage3_iteration_scoreboard.latest.md`
  - `weekly_iteration_snapshot.latest.md`

## Q. 跨团队 handoff 能力
- 输出给 product/marketing/sales/operations 的结构化变更建议
- 产物：
  - `handoffs/operations_to_product_iterate.json`
  - `handoffs/operations_to_marketing_iterate.json`
  - `handoffs/operations_to_sales_iterate.json`

---

## 4) Stage3 数据与文件设计（建议）

### 新增 contracts/config
- `contracts/stage3_experiment_contract.v1.json`
- `contracts/stage3_decision_policy.v1.json`
- `config/stage3_metric_guardrails.v1.yaml`
- `config/stage3_rollout_policy.v1.yaml`
- `config/stage3_iteration_weights.v1.yaml`

### 新增脚本（op1_operations）
- `scripts/stage3_iteration_common.py`
- `scripts/build_stage3_iteration_inputs.py`
- `scripts/build_opportunity_solution_tree.py`
- `scripts/build_stage3_experiment_backlog.py`
- `scripts/build_stage3_variant_specs.py`
- `scripts/run_stage3_rollouts.py`
- `scripts/evaluate_stage3_experiments.py`
- `scripts/build_stage3_iteration_scoreboard.py`
- `scripts/verify_stage3_reproducibility.py`
- `scripts/run_stage3_iteration.sh`

---

## 5) Stage3 KPI 框架（能力健康 + 业务结果）

### 能力健康 KPI
- experiment_throughput_per_week
- median_idea_to_release_days
- experiment_data_quality_pass_rate
- srm_alert_rate
- rollback_rate
- strict_repro_pass_rate

### 业务结果 KPI
- delta_visit_to_signup
- delta_signup_to_paid
- delta_net_new_mrr
- unresolved_high_impact_theme_count
- learning_velocity_index（每周被证伪/被验证假设数）

---

## 6) “完整具备 Stage3 能力”验收标准

只有以下全部满足，才算 Stage3 complete：

1. 从 Stage2 queue 自动生成可执行实验 backlog。
2. 每个实验有完整 contract（含 stop/guardrail）。
3. 发布有 flag+渐进放量+kill switch。
4. 实验评估输出可解释且可追溯。
5. 决策日志覆盖 ship/iterate/rollback/park。
6. Stage3 scoreboard + weekly snapshot 自动产出。
7. strict reproducibility 通过（固定 as-of 双跑一致）。
8. 跨团队 handoff 可直接消费。

---

## 7) 主要风险与控制

风险：
- 只追求“实验数量”而忽视质量
- 指标污染（口径漂移、采样偏差）
- 过度发布引发线上不稳定
- 反馈噪声反向驱动错误迭代

控制：
- experiment contract 必填+审计
- SRM/数据延迟/护栏监控
- progressive rollout + kill switch
- 决策政策强制包含“停止条件”

---

## 8) 结论

你当前系统已经完成 Stage1 + Stage2 的基础能力，Stage3 的最佳路径不是“多做功能”，而是建立**实验化产品迭代操作系统**。

该方案对标业界领先实践，同时与 OperatorOne 当前仓库结构高度兼容（尤其是 `op1_product` 的 build/deploy 能力和 `op1_operations` 的 tracking/feedback 能力）。
