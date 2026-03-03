# Product 项目筛选框架（可执行版）

## 0) 目标
在不预设具体项目的前提下，稳定筛出“可在短期内验证付费价值”的商业项目，并给出可解释理由。

---

## 1) Stage 1：机会记录（Opportunity Record）
每个机会必须包含以下字段（缺失即不入池）：
- `target_segment`（具体到角色与规模）
- `core_problem`（一句话，结果导向）
- `current_workaround`（用户现在怎么凑合）
- `pain_evidence`（至少 3 条独立证据，含来源标记）
- `source_coverage`（来源覆盖与跨源门槛结果）
- `budget_signal`（是否出现愿付费线索）
- `urgency_signal`（是否出现“现在就要解决”）
- `distribution_entry`（最小可行获客入口）
- `implementation_constraint`（合规、集成、数据等约束）

**进入 Stage 2 的硬门槛（Hard Gates）**
1. 有明确 buyer（不是“泛用户”）。
2. 有可验证痛点（不是功能想象）。
3. 有可触达渠道（能找到前 20 个访谈对象）。
4. 14 天内可做可测试 MVP。
5. 满足跨源证据门槛：至少 2 个独立来源支持同一机会（配置见 `framework/config/source_trust_rank.json`）。

---

## 2) Stage 2：评分与排序（Scoring）
评分范围 1-5，必须写明依据和风险。

| 维度 | 权重 | 为什么重要 | 最低通过线 |
|---|---:|---|---:|
| Pain Intensity（痛点强度） | 0.25 | 决定是否真的会行动 | 3.5 |
| Willingness to Pay（付费意愿） | 0.25 | 决定能否形成收入 | 3.5 |
| MVP Speed（MVP速度） | 0.20 | 决定验证周期和成本 | 3.0 |
| Acquisition Reachability（获客可达） | 0.15 | 决定首批用户是否可拿到 | 3.0 |
| Competitive Whitespace（竞争空位） | 0.10 | 决定差异化空间 | 2.5 |
| Recurring Usage（复用频率） | 0.05 | 决定留存与订阅稳定性 | 2.5 |

总分公式：
`weighted_score = Σ(score_i * weight_i)`

**排序规则**
- 先过硬门槛，再按 `weighted_score` 降序。
- 若分数相近（差值 < 0.15），优先选择：
  1) 验证成本更低；
  2) 访谈样本更容易拿到；
  3) 失败后可复用资产更多。

---

## 3) Stage 3：立项蓝图（Project Blueprint）
Top 项目必须输出：
- `hypothesis`（问题-人群-价值主张）
- `mvp_boundary`（做什么/不做什么）
- `test_design`（14天验证实验）
- `pricing_hypothesis`
- `success_metric`（如：首批付费转化）
- `kill_criteria`（什么结果下停止）

---

## 4) 可落地要求（必须满足）
1. 每个结论都能追溯到证据链接。
2. 每个评分维度都包含“理由 + 反例风险”。
3. Stage 1 结果必须可直接喂给 Stage 2（结构一致）。
4. Stage 3 结果必须可直接喂给营销/运营（无需二次解释）。
