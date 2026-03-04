# Stage1 计划（Marketing）— SEO Experiments 自动化（Shadow Mode, 1周）

## 0) 目标与约束
- **目标**：在 1 周黑客马拉松内，搭建可复用的 SEO 实验自动化系统（不是追真实流量结果）。
- **约束**：
  - 不做实盘发布/投放（`publish=false`）
  - 不提交索引（`index=false`）
  - 所有评估使用离线/模拟评分（Shadow Mode）

---

## 1) 输入（自动从 op1_product 拉取）
系统每天自动读取以下产物作为“商业项目语料库”：

1. `research/stage1_idea_discovery/opportunity_records.json`
2. `research/stage2_idea_screening/decision_log.json`
3. `research/stage3_mvp_scope/project_blueprint.json`
4. `research/live_examples.latest.json`
5. `research/build_deploy_v1/project_spec.invoice.json`
6. `research/build_deploy_v1/project_spec.chargeback.json`
7. `research/build_deploy_v1/project_spec.reporting.json`
8. `research/landing_v1/landing_package.json`

### 当前可用项目池（已验证可用）
- invoice-followup（应收催收）
- chargeback-response（拒付申诉）
- client-reporting（代理商月报）

> 本周资源配比建议：**invoice 60% / chargeback 30% / reporting 10%**

---

## 2) Stage1 自动化流水线（One-command 思路）

### Step A — Project Ingest
- 抽取字段：ICP、痛点、价值主张、FAQ、proof points、CTA、kill criteria。
- 产出：`research/stage1_marketing_seo/project_ingest.json`

### Step B — Keyword Graph Builder
- 基于模板生成关键词（不依赖外部 API）：
  - 问题型：`how to + pain`
  - 模板型：`pain + template/checklist`
  - 对比型：`manual vs automated + workflow`
  - 决策型：`best + tool/workflow + ICP`
- 自动做 intent 分类：TOFU/MOFU/BOFU。
- 产出：`research/stage1_marketing_seo/keyword_graph.csv`

### Step C — Experiment Generator
- 每个主题自动生成实验卡（标题变量、内容结构变量、CTA变量、证明变量）。
- 每张实验卡都包含：假设、变量、主指标、护栏指标、成功阈值、失败阈值、风险。
- 产出：
  - `research/stage1_marketing_seo/experiments.backlog.json`（>=12）
  - `research/stage1_marketing_seo/experiments.top3.json`

### Step D — Brief Composer
- 为 Top3 自动生成内容 brief（页面结构、H1/H2、FAQ、内链建议、CTA位置）。
- 产出：`research/stage1_marketing_seo/briefs/*.md`

### Step E — Shadow Evaluator
- 离线评分维度（0-100）：
  1) Intent Match
  2) Problem-Message Fit
  3) Differentiation（相对同类角度）
  4) Conversion Readiness（CTA清晰度）
  5) Execution Risk（反向分）
- 产出：
  - `research/stage1_marketing_seo/shadow_scoreboard.json`
  - `research/stage1_marketing_seo/decision_log.md`

---

## 3) 一周执行节奏（自动化优先）

### Day 1：语料接入 + 数据契约
- 固化 ingest schema；拉齐 3 个项目语料。
- 验收：`project_ingest.json` 完整无空字段关键项。

### Day 2：关键词图谱自动生成
- 跑模板扩展 + 去重 + intent 分类。
- 验收：关键词 >=120，且 BOFU 占比 >=25%。

### Day 3：实验卡批量生成
- 自动生成 >=12 张实验卡并打优先级（ICE）。
- 验收：Top3 已选出且都有清晰阈值。

### Day 4：Top3 内容 brief 自动生成
- 每个实验产出可直接给内容生产的 brief。
- 验收：3 份 brief 均包含 H1/H2/FAQ/CTA/风险。

### Day 5：Shadow 评分与排序
- 对 Top3 做离线评分，输出 Go/No-Go。
- 验收：至少 2 个实验达到“Ready for Publish（下周可实盘）”。

### Day 6：Dry-run（全链路演练）
- 全流程从 ingest 到 scoreboard 重跑一次。
- 验收：全链路可一键复现，失败点有日志。

### Day 7：Demo + 下周实盘切换方案
- 输出本周总结与下周上线优先级。
- 验收：形成明确执行队列（P0/P1/P2）和停损规则。

---

## 4) Stage1 Done 定义（必须全部满足）
1. 一键生成 SEO 实验资产（关键词图谱、实验卡、brief、评分板）
2. 至少 12 个候选实验 + 3 个高置信 Top 实验
3. 至少 2 个实验达到“下周可发布”状态
4. 每个实验都有明确 stop rule（不拍脑袋）
5. 所有产物可追溯到 op1_product 项目输入文件

---

## 5) 风险与控制
- 风险：无外部搜索 API 时，关键词覆盖可能偏窄。
  - 控制：先模板法跑通自动化，Stage2 再接 SERP API 扩展。
- 风险：多项目并行导致分散。
  - 控制：本周以 invoice 为主，其他项目仅做对照。
- 风险：Shadow 分数与真实流量偏差。
  - 控制：Stage2 引入真实发布 + 7 天窗口验证。

---

## 6) Stage2（下周）衔接（预告）
- 打开 `publish=true`，将 Top2 实验上线；
- 加入真实 Search Console/Analytics 反馈闭环；
- 执行 7 天滚动复盘（保留/放大/淘汰）。
