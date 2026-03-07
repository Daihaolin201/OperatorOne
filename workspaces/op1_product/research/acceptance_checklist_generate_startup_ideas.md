# 验收清单：是否具备 Generate startup ideas 能力

生成时间：2026-03-02 22:22 GMT

## 既定目标（本轮）
让 agent 具备“商业项目搜索 + 分析 + 可交接输出”的能力，而不是一次性手工执行。

---

## A. 能力与配置验收

| 项目 | 验收标准 | 结果 | 证据 |
|---|---|---|---|
| A1 Skills 持久化安装 | 存在 discovery/screening/mvp-scope/handoff 四个技能 | ✅ 通过 | `skills/op1-product-idea-*/SKILL.md` |
| A2 Tools 工作流固定 | 明确使用搜索、抓取、批处理、读写工具链 | ✅ 通过 | `framework/quickstart.md`, `research/skills_tools_plan.md` |
| A3 一键可重复执行 | 能通过单命令重跑完整流程 | ✅ 通过 | `scripts/run_generate_startup_ideas.sh` + 本轮执行日志 |
| A4 配置可调 | 评分权重可配置，不写死 | ✅ 通过 | `framework/config/scoring_weights.default.json` |

---

## B. 搜索能力验收（Discovery）

| 项目 | 验收标准 | 结果 | 证据 |
|---|---|---|---|
| B1 覆盖查询规模 | 多主题查询，非单点检索 | ✅ 通过 | `research/signal_summary.json`（32 queries） |
| B2 数据规模 | 具备可用样本池 | ✅ 通过 | `raw_posts=551`, `filtered_posts=547` |
| B3 运行稳定性 | 报错可控/无阻断 | ✅ 通过 | `errors=[]` |
| B4 多源广度 | 不仅限单一社区来源 | ⚠️ 部分通过 | 当前主源为 Reddit，尚未扩展 G2/论坛/招聘等 |

---

## C. 分析能力验收（Screening）

| 项目 | 验收标准 | 结果 | 证据 |
|---|---|---|---|
| C1 Stage1 结构化记录 | 每个机会字段完整且可机读 | ✅ 通过 | `research/stage1_idea_discovery/opportunity_records.json`（6 opportunities） |
| C2 Stage1 证据数量 | 每个机会 >=3 条证据 | ✅ 通过 | 本轮检查：6/6 均为 3 条 |
| C3 Stage2 可解释评分 | 每维度有 score + reason + risk_if_wrong | ✅ 通过 | `research/stage2_idea_screening/decision_log.json` |
| C4 自动排序与决策 | 输出 advance/hold/reject | ✅ 通过 | `research/stage2_idea_screening/scoring.csv` |
| C5 追溯性 | 决策可追溯到 source_url | ✅ 通过 | Stage1 `pain_evidence.source_url` |
| C6 语义精度 | 证据与主题高度匹配 | ⚠️ 部分通过 | 已加关键词过滤，但仍需人工抽检提升准确度 |

---

## D. 下游可用性验收（可交接）

| 项目 | 验收标准 | 结果 | 证据 |
|---|---|---|---|
| D1 Stage-Gate 连贯 | Stage1 -> Stage2 -> Stage3 模板齐备 | ✅ 通过 | `framework/templates/*`, `framework/pipeline.md` |
| D2 项目蓝图承接 | 可从 `advance` 候选进入 Stage3 立项 | ✅ 通过 | `research/stage3_mvp_scope/project_blueprint.json`（待选项目） |
| D3 营销交接控制 | 未选项目前不强行输出商业交付 | ✅ 通过 | `../../handoffs/product_to_marketing.json` 为 pending 模板 |

---

## 结论：是否达成既定目标？

**结论：已达成“能力版 MVP 目标”（可搜索、可分析、可重跑、可交接）。**

- 你要求的核心能力（Generate startup ideas）已从“单次执行”升级为“可复用流水线”。
- 目前状态适合内部试运行与客户演示（开箱可用）。

**但尚未完全达成“生产级目标”**，主要差距：
1. 数据源广度仍偏单一（Reddit-first）；
2. 评分仍是启发式默认分，需引入访谈/真实转化反馈闭环；
3. 证据语义精度需再做自动质量控制（减少噪声样本）。

---

## 建议的下一步（不改权重前）
1. 增加第二、第三数据源适配（如 G2 评论、行业论坛、招聘 JD 痛点）。
2. 增加 `evidence_quality_score` 自动质检列（标题/正文关键词一致性、噪声过滤）。
3. 跑一轮“人工复核 20 条样本”的校准，形成 scoring calibration 规则。
