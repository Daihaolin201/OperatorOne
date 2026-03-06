# Studio 优化复核报告（性能 + 交互）

## 背景

用户反馈：
1. Studio 页面加载慢
2. 点击按钮后反馈慢
3. 不清楚如何使用整个流程

---

## 已实施优化

### A. 接口拆分与缓存

- 新增 `GET /api/studio/fast-snapshot`
  - 仅返回 Studio 运行所需的轻量数据
- 新增 `GET /api/monitor/cached-snapshot`
  - 监控重快照走缓存（TTL 默认 45s）
- 保留 `/api/snapshot` 兼容，但改为 cache-backed
- 后台异步预热 monitor cache，避免首屏阻塞

### B. 减载与响应优化

- `studio.snapshot()` 不再每次实时调用 `collect_snapshot()`
- `recentRuns` 改为摘要模式（默认不返回长日志）
- `jobs` 列表改为摘要模式，详情走 `GET /api/studio/jobs/<id>`
- active context 改为结构化摘要（只保留 UI 必要字段）

### C. 操作反馈优化

- 按钮动作提交后立即显示“已入队/复用任务”
- 增加 jobs 高频轮询（2s）
- 任务状态变更后自动刷新 fast snapshot
- 增加重复提交防抖（同 venture + 同 action 复用运行中的 job）

### D. 可用性与引导

- 新增“怎么使用（3分钟）”引导区
- 新增“下一步推荐动作”区（基于当前阶段）
- 新增“阶段流程（演示视角）”与“阶段产物”可视化
- 新增 artifact 查看器（可直接读取阶段输出文件）

### E. Product 部署治理

- Product live 部署支持 deterministic `vercel_project` 命名
- 新增部署注册表 `deployments.json`（时间、mode、project、url/preview）
- 把部署结果回写到 venture links 与 stage summary，方便评委演示

### F. 鲁棒性加强（P4）

- 新增 `stage_preflight`（合同与可复现性预检查）
- 新增 `rehearsal_e2e`（simulation 一键彩排）
- 新增 action 重复提交防抖（复用 running/queued job）
- 新增 `venture_context.v1` 统一上下文快照
- 保留 5-tab 结构并补强跨阶段决策提示

---

## 实测结果（本机）

### 优化前

- `/api/studio/snapshot` ≈ 8.5s
- `/api/snapshot` ≈ 7.8s

### 优化后

- `/api/studio/fast-snapshot` ≈ 0.8~1.2s
- `/api/monitor/cached-snapshot` ≈ 0.001~0.003s

> 说明：长任务本身仍需要执行时间（脚本运行），但 UI 已改为“快速回执 + 异步进度”。

---

## 仍建议的下一步（可选）

1. WebSocket 推送 job 状态（替代轮询）
2. 动作级 SLA 面板（P95 duration）
3. live 动作增加确认短语（文本二次确认）
4. 更细权限矩阵（agent × action × channel/account）
