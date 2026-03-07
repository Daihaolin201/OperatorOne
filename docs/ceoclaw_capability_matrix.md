# Founder 能力映射与 CEOClaw Challenge 验收矩阵

本文档旨在映射 OperatorOne 项目中的 Founder 核心能力到具体的代码实现、触发方式及产物证据，并明确标注相对于基础 OpenClaw 的 CEOClaw 扩展点。

## 1. 能力映射矩阵

| Domain | 关键能力 | 实现位置 (文件:函数/行) | 触发方式 (Dashboard/CLI) | 证据路径 (Artifact/Data) | CEOClaw 扩展点 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Product** | **需求发现与机会筛选** | `op1_product/scripts/run_generate_startup_ideas.sh` | Dashboard: `Refresh Ideas` | `workspaces/op1_product/research/stage1_opportunity_records.json` | ✅ 自动化多维评分 (Feasibility/Weighted) |
| **Product** | **MVP 自动化构建与部署** | `op1_product/scripts/run_build_deploy_v1.sh` | Dashboard: `Run Product (Live)` | `workspaces/op1_product/research/build_deploy_v1/deploy_latest.json` | ✅ 支持 Vercel 自动化部署与项目名治理 |
| **Product** | **落地页与价值主张生成** | `op1_product/scripts/run_create_landing_pages_v1.sh` | Dashboard: `Run Product` | `workspaces/op1_product/research/landing_v1/landing_package.json` | ✅ 结构化价值主张 (Value Prop) 提取 |
| **Marketing** | **SEO 与关键词策略** | `op1_marketing/scripts/run_marketing_seo_stage1.py` | Dashboard: `Run SEO Analysis` | `workspaces/op1_marketing/research/stage1_marketing_seo/run.latest.json` | ✅ 关键词图谱 (Keyword Graph) 自动分析 |
| **Marketing** | **自动化内容创作与审核** | `op1_marketing/scripts/run_marketing_content_stage2.py` | Dashboard: `Run Content Pipeline` | `workspaces/op1_marketing/research/stage2_content_publish/publish.queue.latest.json` | ✅ 审核工作流 (Review Ready/Approved) |
| **Marketing** | **全渠道营销活动分发** | `op1_marketing/scripts/run_marketing_campaign_stage3.py` | Dashboard: `Run Campaign Launch` | `workspaces/op1_marketing/research/stage3_campaign_launch/campaigns.queue.latest.json` | ✅ 多渠道 readiness_score 评分 |
| **Sales** | **潜在客户开发 (Prospecting)** | `op1_sales/scripts/build_prospect_queue.py` | Dashboard: `Run Prospecting` | `workspaces/op1_sales/research/prospecting/prospect_queue.latest.json` | ✅ 基于 ICP 的分层 (Segmentation) 逻辑 |
| **Sales** | **外联计划与审批流程** | `op1_sales/scripts/build_outreach_stage2.py` | Dashboard: `Run Outreach Plan` | `workspaces/op1_sales/research/outreach/outreach_batch.ready.json` | ✅ 显式审批门禁 (Approval Gate) |
| **Sales** | **漏斗转化与成交追踪** | `op1_sales/scripts/run_convert_early_customers_stage3.py` | Dashboard: `Run Conversion` | `workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.json` | ✅ MRR 代理 (MRR Proxy) 计算 |
| **Operations** | **核心 KPI 监控 (L1)** | `op1_operations/scripts/run_stage1_tracking.sh` | Dashboard: `Run KPI Tracking` | `workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json` | ✅ 跨 Agent KPI 聚合看板 |
| **Operations** | **用户反馈闭环 (L2)** | `op1_operations/scripts/run_stage2_feedback.sh` | Dashboard: `Run Feedback Loop` | `workspaces/op1_operations/research/stage2_feedback/stage2_feedback_scoreboard.latest.json` | ✅ 自动主题聚类与优先级评分 |
| **Operations** | **产品迭代决策 (L3)** | `op1_operations/scripts/run_stage3_iteration.sh` | Dashboard: `Run Iteration Plan` | `workspaces/op1_operations/research/stage3_product_iteration/learning_log.latest.md` | ✅ 迭代回写 (Writeback) 机制 |

## 2. CEOClaw 核心扩展机制 (Over OpenClaw)

1. **CEO 编排器 (`op1_ceo`)**: 
   - 实现位置: `workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py`
   - 功能: 驱动 Product -> Marketing -> Sales -> Operations 的全局端到端 Loop，负责状态流转与门控执行。
2. **交付合约 (Handoffs)**:
   - 实现位置: `handoffs/*.json`
   - 功能: 定义了 9 类跨 Agent 交付标准，取代了 OpenClaw 基础的非结构化对话。
3. **Venture Studio Dashboard**:
   - 实现位置: `dashboard/studio.py`
   - 功能: 为评委提供一键式 `rehearsal_e2e` (彩排) 能力，并实时同步各阶段产物证据。
4. **审批策略 (Approval Policy)**:
   - 实现位置: `workspaces/op1_ceo/research/ceo_orchestration/approval.json`
   - 功能: 强制执行外部影响动作（如发邮件、部署）的“人工确认”机制。

## 3. 验收建议 (For Judges)

请打开 Dashboard (`python3 dashboard/server.py`)，点击 **"Run CEOClaw Demo"** 或执行 **"Rehearsal E2E"**。您将在右侧 Timeline 中实时看到上述所有能力被按序触发，并可在产物视图中直接访问对应的 JSON/Markdown 证据文件。
