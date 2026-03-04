# Stage2 Plan（Marketing）— Publish Content 能力建设（Shadow/Review）

## 目标（能力导向）
从 Stage1 的 SEO 实验队列（Ready/Hold）自动生成“可发布内容包”，并通过质量门禁进入人工评审队列。

> 当前阶段不做自动发布（auto publish disabled）。

---

## 输入契约
必收输入：
- `research/stage1_marketing_seo/run.latest.json`
- `research/stage1_marketing_seo/context_index.latest.json`
- `research/stage1_marketing_seo/experiments.backlog.latest.json`
- `research/stage1_marketing_seo/experiments.queue.latest.json`
- `research/stage1_marketing_seo/scoreboard.latest.json`
- `../../handoffs/product_to_marketing.json`

输入层产物：
- `research/stage2_content_publish/input/stage1_snapshot.latest.json`
- `research/stage2_content_publish/input/delta.latest.json`
- `research/stage2_content_publish/input/mirror.latest/`

---

## 核心流水线
1. **Input Sync**：检查输入完整性 + 记录快照与delta。
2. **Candidate Selection**：优先 Stage1 Ready（可选扩展 Hold），按分数、意图、置信度排序。
3. **Content Packaging**：生成一稿多用内容包（博客主稿 + 渠道片段）。
4. **QA Gate**：词数、证据深度、来源可追溯、关键词密度、政策风险、分数下限。
5. **Queueing**：进入 `approved` / `review_ready` / `needs_revision` 队列。
6. **Manual Review**：通过审批脚本将 `review_ready` 项目转为 `approved` 或 `needs_revision`。
7. **Sales Handoff Sync**：更新 `../../handoffs/marketing_to_sales.json`。

---

## 输出契约
统一输出到 `research/stage2_content_publish/`：
- `run.latest.json`
- `state.latest.json`
- `content.backlog.latest.json`
- `publish.queue.latest.json`
- `qa.latest.json`
- `decision_log.latest.md`
- `review_log.latest.json`
- `drafts/`

---

## 状态机（Stage2）
`candidate -> drafted -> qa_checked -> review_ready | needs_revision -> approved`

当前阶段终点：`approved`（仅代表通过人工审核，仍不触发自动发布）。

---

## 验收标准（能力是否具备）
1. 单次触发可完成“选题 -> 起草 -> 质检 -> 队列化”。
2. 人工审核可执行 approve / request-revision，并可写入审计日志。
3. 所有内容项可回溯到 Stage1 实验与源文件指针。
4. 输出含可读决策日志与质量报告。
5. 自动发布保持关闭。
6. 成功运行后自动更新 `marketing_to_sales.json`。

---

## 运行命令
```bash
# 单轮
./scripts/run_marketing_content_stage2.sh

# 强制重算 + 扩展Hold候选
./scripts/run_marketing_content_stage2.sh --force --include-hold

# 人工审核：全部通过
./scripts/review_marketing_content_stage2.sh --approve-all --note "editorial pass"

# 人工审核：部分通过 + 部分退回
./scripts/review_marketing_content_stage2.sh \
  --approve cnt_x,cnt_y \
  --reject cnt_z \
  --reason "tighten evidence"
```
