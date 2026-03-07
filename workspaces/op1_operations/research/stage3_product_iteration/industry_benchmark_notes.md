# Stage3 行业基准研究笔记（Iterate on product）

生成时间：2026-03-05

> 说明：web_search 在当前环境返回 `missing_brave_api_key`，因此使用了多轮定向 `web_fetch` + 仓库现状分析。

## 1) Continuous Discovery / Opportunity Mapping

### Product Talk — Opportunity Solution Tree
- URL: https://www.producttalk.org/opportunity-solution-tree/
- 要点：
  - 机会树把“结果目标 -> 机会 -> 方案 -> 实验”连起来。
  - 强调“先识别机会，再选方案”，防止直接跳功能。
- Stage3映射：
  - 增加 `opportunity_solution_tree.latest.json` 作为实验 backlog 上游。

### SVPG — Dual-Track Agile
- URL: https://www.svpg.com/dual-track-agile/
- 要点：
  - 发现轨（discovery）与交付轨（delivery）并行，避免“只开发不验证”。
- Stage3映射：
  - Stage3 设计成 discovery+delivery 双轨流水线，而非单线开发。

## 2) Prioritization & Product Bets

### Intercom RICE
- URL: https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/
- 要点：
  - Reach / Impact / Confidence / Effort 提供结构化排序。
- Stage3映射：
  - 实验优先级沿用 RICE 思路并叠加 Stage1/Stage2 影响数据。

### ProductPlan RICE/Kano
- URL: https://www.productplan.com/glossary/rice-scoring-model/
- URL: https://www.productplan.com/glossary/kano-model/
- 要点：
  - RICE 减少主观偏差；Kano 区分 basic/performance/delighter。
- Stage3映射：
  - backlog 同时保留价值优先级与体验类别标签。

### Amazon Working Backwards（方法综述）
- URL: https://www.productplan.com/glossary/working-backward-amazon-method/
- 要点：
  - 从用户价值叙事倒推产品方案，先写“发布叙事”验证可行性。
- Stage3映射：
  - 每个高优实验必须有清晰用户价值叙述（非技术描述）。

## 3) Experimentation & Measurement Trust

### Microsoft ExP 文章集（可信实验）
- SRM: https://www.microsoft.com/en-us/research/articles/diagnosing-sample-ratio-mismatch-in-a-b-testing/
- Pre-experiment patterns: https://www.microsoft.com/en-us/research/articles/patterns-of-trustworthy-experimentation-pre-experiment-stage/
- Data quality: https://www.microsoft.com/en-us/research/articles/data-quality-fundamental-building-blocks-for-trustworthy-a-b-testing-analysis/
- Alerting: https://www.microsoft.com/en-us/research/articles/alerting-in-microsofts-experimentation-platform-exp/
- Metric quality (STEDII): https://www.microsoft.com/en-us/research/articles/stedii-properties-of-a-good-metric/
- 要点：
  - 实验可信度来自前置质量门槛、样本健康、指标质量与实时告警。
- Stage3映射：
  - 增加 SRM 检查、metric guardrail、experiment alerting、decision policy。

### PostHog（事件+实验+特性开关）
- https://posthog.com/docs/experiments
- https://posthog.com/docs/feature-flags
- https://posthog.com/docs/data/events
- 要点：
  - 统一事件模型 + experiment + flags，便于落地增长实验闭环。
- Stage3映射：
  - Stage3 设计采用“事件优先 + flag 控制 + 实验评估”结构。

## 4) Release Safety / Delivery Performance

### LaunchDarkly（Progressive Rollouts）
- https://launchdarkly.com/docs/home/releases/feature-flags
- https://launchdarkly.com/docs/home/releases/progressive-rollouts
- 要点：
  - 用 feature flag + 渐进放量控制变更风险。
- Stage3映射：
  - 发布策略固定为 1%→5%→20%→50%→100%，并配 kill switch。

### Martin Fowler — Feature Toggles
- URL: https://martinfowler.com/articles/feature-toggles.html
- 要点：
  - 使用 toggle router 动态控制新旧逻辑共存，支持安全迭代。
- Stage3映射：
  - 实验和发布必须具备动态开关与回退能力。

### Trunk-Based Development
- URL: https://trunkbaseddevelopment.com/
- 要点：
  - 短分支+高频集成是持续交付基础。
- Stage3映射：
  - 迭代交付要求短周期小变更，提高部署频率并降低集成风险。

### DORA / Four Keys
- https://dora.dev/guides/dora-metrics-four-keys/
- https://cloud.google.com/architecture/devops/devops-tech-measuring-performance
- 要点：
  - 交付性能四指标（部署频率、前置时间、变更失败率、恢复时间）可量化迭代能力。
- Stage3映射：
  - Stage3 scoreboards 纳入交付指标，避免“只看增长不看稳定性”。

## 5) Iteration Cadence / Scope Control

### Basecamp Shape Up（章节）
- https://basecamp.com/shapeup/1.3-chapter-04
- https://basecamp.com/shapeup/3.4-chapter-13
- https://basecamp.com/shapeup/3.5-chapter-14
- https://basecamp.com/shapeup/3.6-chapter-15
- 要点：
  - 先明确边界和问题，再做粗粒度方案；
  - 管理未知而非只管理任务；
  - 到期时基于 baseline 做 scope cut；
  - 反馈进入下一轮“重新成型”，避免即时反应式开发。
- Stage3映射：
  - 迭代节奏采用 bet + cutoff + revisit，明确 stop rules。

## 6) Backlog/Execution Tooling

### GitHub Projects / Labels
- https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects
- https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels
- 要点：
  - 用自定义字段/视图/自动化/标签支持 backlog 与 roadmap 透明管理。
- Stage3映射：
  - Stage3 输出应具备可映射到 issue/project 的字段结构。

---

## 结论（对 Stage3 的启示）

业界领先并不是单点“做 A/B 测试”，而是：

1) 先有机会树与连续发现；
2) 再有可信实验与可控发布；
3) 最后用交付性能与业务指标共同评估。

因此 Stage3 设计必须是**产品迭代操作系统**，而不是“新功能列表”。
