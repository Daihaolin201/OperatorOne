# Venture Studio 使用指南（快速版）

## 一句话

这个 Studio 不是“监控看板”，而是“人选项目 + agent 执行 + 人工把关 + 闭环迭代”的控制台。

---

## 3 分钟上手路径（建议）

1. **Idea Board**
   - 点击「刷新 startup ideas」
   - 在表格里挑一个项目，点「创建 Venture」
   - 确认该 Venture 已是 active

2. **Product Build**
   - 默认 `simulation` 模式
   - 点击「执行 Product（landing + build/deploy）」
   - 观察产物（preview path / deployment url）

3. **Marketing Studio**
   - 点击：SEO → Content → Campaign
   - 在 content 候选里勾选并「批准」
   - 在 campaign 候选里选一个推进到 Sales

4. **Sales Console**
   - 依次点击：Identify prospects → 规划 outreach → 批准外联
   - 优先跑 `simulate`，确认后才考虑 `commit(live)`

5. **Ops Loop**
   - 点击「Run Operations Full」
   - 点击「回写下一轮待办」
   - 最后点击「确认进入下一轮」

---

## simulation 与 live 的区别

- `simulation`：安全默认，不触发真实对外动作
- `live`：高风险，要求：
  - Manual Arm = ON
  - 对应动作确认（confirmLive）
  - Product live 还要求 Vercel 已安装并登录

---

## 为什么会感觉“慢”

长耗时主要来自执行真实脚本（如 Product build、Marketing/Sales pipeline），不是前端本身卡死。

优化后：
- 轻量快照与重监控拆分
- 按钮提交后立即进入 Job 队列反馈
- 自动轮询 Job 状态并刷新

---

## 常见问题

### Q1: 点按钮没立即看到产物？
看「Jobs」和「Stage Timeline」，任务完成后会自动回填结果。

### Q2: 可以直接全都 live 吗？
不建议。先 simulation 跑通，再单步切 live。

### Q3: 我不知道下一步做什么？
看页面上方「下一步推荐动作」，按顺序执行即可。
