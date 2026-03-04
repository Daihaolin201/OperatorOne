# Stage3 Plan（Marketing）— Launch Campaigns 能力建设（Shadow/Review）

## 目标（能力导向）
把 Stage2 已审核内容资产转化为“可执行 campaign launch packet”，并形成可追踪、可复盘的投放决策队列。

> 当前阶段不做外部自动投放（auto launch disabled）。

---

## 输入契约
必收输入：
- `research/stage2_content_publish/run.latest.json`
- `research/stage2_content_publish/content.backlog.latest.json`
- `research/stage2_content_publish/publish.queue.latest.json`
- `research/stage2_content_publish/qa.latest.json`
- `../../handoffs/marketing_to_sales.json`
- `../../handoffs/product_to_marketing.json`

输入层产物：
- `research/stage3_campaign_launch/input/stage2_snapshot.latest.json`
- `research/stage3_campaign_launch/input/delta.latest.json`
- `research/stage3_campaign_launch/input/mirror.latest/`

---

## 核心流水线
1. **Input Sync**：检查 Stage2 与 handoff 完整性，记录快照与delta。
2. **Asset Selection**：优先 Stage2 `approved`（可选纳入 `review_ready`）。
3. **Campaign Orchestration**：生成目标、渠道配比、预算分配、节奏与实验方案。
4. **Attribution Design**：生成 UTM 追踪参数与 `attribution.map.latest.csv`。
5. **Queueing**：按 readiness score 进入 `launch_ready` / `watchlist` / `hold`。
6. **Sales Handoff Sync**：更新 `../../handoffs/marketing_to_sales.json` 的 campaign_launch 视图。

---

## 输出契约
统一输出到 `research/stage3_campaign_launch/`：
- `run.latest.json`
- `state.latest.json`
- `campaigns.backlog.latest.json`
- `campaigns.queue.latest.json`
- `experiments.latest.json`
- `attribution.map.latest.csv`
- `decision_log.latest.md`
- `packets/`

---

## 状态机（Stage3）
`candidate -> orchestrated -> measured_plan -> launch_ready | watchlist | hold`

当前阶段终点：`launch_ready`（代表“可执行”，不代表“已自动投放”）。

---

## 验收标准（能力是否具备）
1. 可从 Stage2 自动生成 campaign packets 与实验卡。
2. 每个 campaign 都有完整追踪参数（UTM map）。
3. 队列分流规则可复算、可解释（readiness + risk flags）。
4. 自动投放保持关闭。
5. 成功运行后自动更新 `marketing_to_sales.json`。
6. 合约校验脚本可通过：`python3 scripts/verify_marketing_campaign_stage3.py`。

---

## 运行命令
```bash
# 单轮
./scripts/run_marketing_campaign_stage3.sh

# 强制重算
./scripts/run_marketing_campaign_stage3.sh --force

# 扩展候选（纳入 review_ready）
./scripts/run_marketing_campaign_stage3.sh --force --include-review-ready

# 输出契约校验
python3 ./scripts/verify_marketing_campaign_stage3.py
```
