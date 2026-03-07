<div align="center">

[![English](https://img.shields.io/badge/lang-English-blue?style=flat-square)](#operatorone--ceoclaw) &nbsp;
[![中文](https://img.shields.io/badge/lang-中文-red?style=flat-square)](#operatorone--ceoclaw中文版)

</div>

---

# OperatorOne × CEOClaw

> **UK AI Agent Hackathon EP4 × OpenClaw — CEOClaw Challenge submission**
> Team: Dennis & Bennett · Branch: `dennis/automation-framework`
> Repo: https://github.com/Daihaolin201/OperatorOne

<div align="center">

![MIT License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![GLM-5](https://img.shields.io/badge/model-GLM--5-purple?style=flat-square)
![MRR](https://img.shields.io/badge/MRR-%2449-brightgreen?style=flat-square)
![Agents](https://img.shields.io/badge/agents-4-blue?style=flat-square)
![Bounties](https://img.shields.io/badge/bounties-4-yellow?style=flat-square)

</div>

**CEOClaw** is OperatorOne's multi-agent CEO orchestrator. It autonomously coordinates four specialist agents — Product, Marketing, Sales, and Operations — to run an internet business from initial idea to first customers.

---

## Real Results

This is not a demo. These numbers reflect actual pipeline execution.

| Metric | Value |
|---|---|
| Current MRR | **$49** (target: $100) |
| Prospects contacted | **13** |
| Replies received | **6** |
| Customers converted | **1** |
| Products deployed | **6 live Vercel URLs** |
| Campaigns prepared | **9** (3 launch_ready, 5 watchlist, 1 approved) |
| Content assets | **12** (3 approved, 9 review_ready) |
| Agent handoffs | **9 JSON contracts** |

---

## Architecture

<div align="center">
<img src="docs/assets/architecture.svg" alt="OperatorOne Multi-Agent Architecture" width="100%">
</div>

---

## CEOClaw Quick Start

Judges, use these commands to run the orchestrator in simulation mode.

```bash
git clone https://github.com/Daihaolin201/OperatorOne
cd OperatorOne
git checkout dennis/automation-framework
python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run
cat workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json
```

Output artifacts:
- `run.latest.json`: full 4-agent execution log with realistic simulation replies.
- `venture_state.latest.json`: venture KPI snapshot (MRR, prospects, campaigns, deployed URLs).
- `orchestrator_summary.latest.json`: operator-facing summary.

---

## How It Works

- **Stage-gated multi-agent loop**: Each specialist (Product, Marketing, Sales, Operations) hands off a JSON contract to the next stage rather than making isolated agent calls.
- **Approval-gated external actions**: `approval.json` controls whether external actions like emails or deployments are permitted. This ensures the system is fully auditable.
- **Real business execution**: The pipeline has been run end-to-end, resulting in 6 products deployed to Vercel, 13 prospects contacted, and $49 MRR earned.
- **Handoff contract schema**: 9 typed JSON contracts include `contract_version`, `generated_at`, and `generated_by` metadata for full traceability.
- **Iteration loop**: Operations feedback (10 items, P2/P3 prioritized) feeds back to Product, Marketing, and Sales for the next cycle.
- **CEO orchestrator script**: `run_ceo_multi_agent_orchestrator_v1.py` runs the full 4-agent sequence, writes `venture_state.latest.json`, and enforces approval policy.

---

## Live Products

| URL | Product |
|---|---|
| https://webproductmodularinvoice.vercel.app | Invoice follow-up tool |
| https://webproductmodularchargeback.vercel.app | Chargeback response ops |
| https://webproductmodularreporting.vercel.app | Client reporting module |
| https://webproductlandingstage3validation.vercel.app | Validation landing page |
| https://webproductlandingstage3opp002.vercel.app | opp_002 landing page |
| https://webproductlandingstage3opp003.vercel.app | opp_003 landing page |

---

## Z.AI & GLM-5 Integration

OperatorOne targets **GLM-5** as its primary intelligence engine. Released in February 2026, GLM-5 (formerly "Pony Alpha") is the new flagship model from Z.AI (Zhipu AI).

### Why GLM-5 for OperatorOne
GLM-5 provides the long-horizon planning and reliable tool use required for autonomous business operations.

- **744B MoE Architecture**: Massive capacity with 40B active parameters for efficient inference.
- **202K Context Window**: Enables analysis of extensive business logs and market research.
- **"Slime" Async RL**: A novel framework that significantly improves long-horizon agent behavior.
- **Superior Coding**: SWE-bench Verified score of **77.8%**, making it the top open-weights model for engineering.
- **High Cognition**: Terminal-Bench-2.0 score of **61.1%**, a 28.3% improvement over previous generations.

### API Configuration
The preflight gate (`dashboard/zai_preflight.py`) enforces Z.AI API compliance. Update your environment to point at the latest flagship.

```bash
# Configuration
export ZAI_API_BASE="https://api.z.ai/api/paas/v4"
export ZAI_MODEL="glm-5"
export ZAI_API_KEY="your-key-here"

# Verify preflight
python3 -m pytest dashboard/tests/ -q
```

### Per-Agent Model Routing

| Agent | Task Type | Model | Why GLM-5 |
|---|---|---|---|
| op1_product | Code gen, Vercel deploy | glm-5 | SWE-bench 77.8% — top open-weights coding model |
| op1_marketing | Content, SEO copy | glm-5 | Ultra-low hallucination, 202K context window |
| op1_sales | Outreach, dialogue | glm-5 | Native agent mode + "Slime" RL for planning |
| op1_operations | KPI analysis, JSON | glm-5 | Structured output, BrowseComp 75.9% |
| CEO Orchestrator | Planning, routing | glm-5 | Terminal-Bench +28.3% improvement |

### Preflight Gate
The system enforces a hard gate via `dashboard/zai_preflight.py`. If the Z.AI environment is misconfigured, the system raises a `ZAIPreflightError` and halts. There is no silent fallback, ensuring strict compliance with the Z.AI Gold Bounty requirements.

---

## Hackathon Bounties

### 🏆 CEOClaw Challenge (£1,000)
- **Evidence**: The CEO orchestrator successfully runs a 4-agent loop end-to-end. Real results include $49 MRR, 13 prospects contacted, and 6 Vercel products deployed.
- **Verification**: `python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run`

### ⚡ Z.AI Gold Bounty
- **Evidence**: GLM-5 is the featured model for all 5 roles. The preflight gate enforces correct `base_url` and model configuration without silent fallback.
- **Verification**: `python3 -m pytest dashboard/tests/ -q`

### 🎮 Animoca Brands
- **Identity**: The CEO has a persistent persona and execution logic defined in `workspaces/op1_ceo/AGENTS.md`.
- **Memory**: 9 inter-agent JSON contracts persist state and learnings across agent boundaries.
- **Cognition**: The Operations iteration loop feeds learned feedback back into the system for continuous improvement.

### 🤝 Human for Claw
- **Dashboard**: A dedicated stage view at `http://127.0.0.1:8765` provides human-readable status and artifact tracking.
- **Approval Gate**: `approval.json` gates every external action, keeping the human operator in control of deployments and communications.

---

## Bounty Coverage

<div align="center">
<img src="docs/assets/bounty_map.svg" alt="Hackathon Bounty Coverage" width="80%">
</div>

---

## Repository Layout

- `openclaw/`: profile sync and safety scripts.
- `workspaces/`: isolated agent workspaces and stage artifacts.
- `handoffs/`: inter-agent JSON contracts (9 contracts).
- `dashboard/`: local monitor and venture studio web app.
- `official-site/`: OperatorOne official intro page.
- `shared/`: shared prompts, skills, and templates.
- `docs/`: architecture, collaboration protocol, and runbook.
- `apps/`: Next.js portal and product apps (monorepo).
- `packages/`: shared @op1/* packages.

---

## Agent Topology

| Workspace | Role | In manifest | Primary responsibility |
|---|---|---|---|
| `workspaces/op1_product` | Product | ✅ | Idea discovery, web product build/deploy |
| `workspaces/op1_marketing` | Marketing | ✅ | SEO, content, and campaign pipeline |
| `workspaces/op1_sales` | Sales | ✅ | Prospecting, outreach, and conversion |
| `workspaces/op1_operations` | Operations | ✅ | KPI tracking and feedback loop |
| `workspaces/op1_manager` | Manager | ❌ | Cross-agent orchestration and audits |

---

## End-to-End Flow

The primary handoff chain proceeds as follows:

1. `op1_product` → `handoffs/product_to_marketing.json`
2. `op1_marketing` → `handoffs/marketing_to_sales.json`
3. `op1_sales` → `handoffs/sales_to_operations.json`
4. `op1_operations` → Feedback to Product, Marketing, and Sales.

---

## Dashboard

Run the local dashboard to monitor the venture studio.

```bash
python3 dashboard/server.py --host 127.0.0.1 --port 8765
```
Open: http://127.0.0.1:8765

---

## Official Site

Preview the official introduction page locally.

```bash
cd official-site
python3 -m http.server 4173
```
Open: http://127.0.0.1:4173
Live URL: https://official-site-theta.vercel.app

---

## Developer Reference

Detailed information for each workspace can be found in their respective `README.md` files within `workspaces/`.

### Script Helpers
- `python3 scripts/validate_handoffs.py --repo-root .`
- `python3 scripts/upgrade_handoffs.py --repo-root .`
- `python3 scripts/change_hygiene_guard.py --staged`
- `python3 scripts/reset_generated_artifacts.py --apply`

---

## Demo Video

Detailed walkthrough can be found at `docs/demo_video_script.md`.

---

## Note on Generated Artifacts

`workspaces/*/research/**` contains machine-updated run snapshots. When reviewing diffs, please separate code and contract changes from pipeline output refreshes.

---

<a name="operatorone--ceoclaw中文版"></a>

<div align="center">

[![English](https://img.shields.io/badge/lang-English-blue?style=flat-square)](#operatorone--ceoclaw) &nbsp;
[![中文](https://img.shields.io/badge/lang-中文-red?style=flat-square)](#operatorone--ceoclaw中文版)

</div>

---

# OperatorOne × CEOClaw（中文版）

> **UK AI Agent Hackathon EP4 × OpenClaw — CEOClaw Challenge 提交项目**
> 团队：Dennis & Bennett · 分支：`dennis/automation-framework`
> 仓库：https://github.com/Daihaolin201/OperatorOne

<div align="center">

![MIT License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![GLM-5](https://img.shields.io/badge/model-GLM--5-purple?style=flat-square)
![MRR](https://img.shields.io/badge/MRR-%2449-brightgreen?style=flat-square)
![Agents](https://img.shields.io/badge/agents-4-blue?style=flat-square)
![Bounties](https://img.shields.io/badge/bounties-4-yellow?style=flat-square)

</div>

**CEOClaw** 是 OperatorOne 的多智能体 CEO 编排器。它能够自动协调四个专业智能体（Product, Marketing, Sales, Operations），实现从最初创意到获取首批客户的全流程业务运营。

---

## 实际成果

本项目并非演示原型，以下数据源自真实的流水线执行。

| 指标 | 数值 |
|---|---|
| 当前 MRR | **$49** (目标: $100) |
| 已联系潜在客户 | **13** |
| 收到回复 | **6** |
| 已转化客户 | **1** |
| 已部署产品 | **6 个 Vercel 实时链接** |
| 已准备活动 | **9** (3 个就绪, 5 个观察名单, 1 个批准) |
| 内容资产 | **12** (3 个批准, 9 个待审核) |
| 智能体交付物 | **9 个 JSON 合约** |

---

## 系统架构

<div align="center">
<img src="docs/assets/architecture.svg" alt="OperatorOne Multi-Agent Architecture" width="100%">
</div>

---

## CEOClaw 快速开始

评委可以通过以下命令在模拟模式下运行编排器。

```bash
git clone https://github.com/Daihaolin201/OperatorOne
cd OperatorOne
git checkout dennis/automation-framework
python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run
cat workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json
```

输出产物：
- `run.latest.json`：包含真实模拟回复的 4 智能体执行完整日志。
- `venture_state.latest.json`：项目 KPI 快照（包含 MRR、潜在客户、活动、部署链接）。
- `orchestrator_summary.latest.json`：面向操作员的执行摘要。

---

## 工作原理

- **阶段门控多智能体循环**：各专业智能体（Product, Marketing, Sales, Operations）通过 JSON 合约向下一阶段交付成果，而非孤立调用。
- **审批门控外部操作**：通过 `approval.json` 控制邮件发送或部署等外部操作权限，确保系统完全可审计。
- **真实的业务执行**：流水线已完成端到端运行，成功部署 6 个 Vercel 产品，联系 13 位潜在客户，并获得 $49 MRR。
- **交付合约架构**：9 个类型化的 JSON 合约包含版本、生成时间和生成者等元数据，确保全流程可追溯。
- **迭代循环**：Operations 的反馈（10 个事项，已按优先级排序）会反馈给其他智能体，开启下一轮迭代。
- **CEO 编排脚本**：`run_ceo_multi_agent_orchestrator_v1.py` 执行完整的智能体序列，并强制执行审批策略。

---

## 线上产品

| 链接 | 产品 |
|---|---|
| https://webproductmodularinvoice.vercel.app | 发票跟进工具 |
| https://webproductmodularchargeback.vercel.app | 拒付申诉操作工具 |
| https://webproductmodularreporting.vercel.app | 客户报告模块 |
| https://webproductlandingstage3validation.vercel.app | 验证落地页 |
| https://webproductlandingstage3opp002.vercel.app | opp_002 落地页 |
| https://webproductlandingstage3opp003.vercel.app | opp_003 落地页 |

---

## Z.AI 与 GLM-5 集成

OperatorOne 采用 **GLM-5** 作为核心智能引擎。GLM-5（研发代号 "Pony Alpha"）由 Z.AI（智谱 AI）于 2026 年 2 月发布，是其最新的旗舰级模型。

### 为什么选择 GLM-5
GLM-5 为自主业务运营提供了长周期规划和可靠的工具调用能力。

- **744B MoE 架构**：超大规模参数量，40B 激活参数确保高效推理。
- **202K 上下文窗口**：支持分析超长业务日志和市场调研数据。
- **"Slime" 异步强化学习**：全新的 RL 框架显著提升了智能体的长周期行为表现。
- **卓越的代码能力**：SWE-bench Verified 评分 **77.8%**，是目前工程领域表现最好的开源模型。
- **高水平认知**：Terminal-Bench-2.0 评分 **61.1%**，较上一代提升 28.3%。

### API 配置
系统通过 `dashboard/zai_preflight.py` 强制执行 Z.AI API 预检查。请更新环境变量以指向最新的旗舰模型。

```bash
# 配置
export ZAI_API_BASE="https://api.z.ai/api/paas/v4"
export ZAI_MODEL="glm-5"
export ZAI_API_KEY="your-key-here"

# 运行测试验证
python3 -m pytest dashboard/tests/ -q
```

### 智能体模型路由

| 智能体 | 任务类型 | 模型 | 为什么选择 GLM-5 |
|---|---|---|---|
| op1_product | 代码生成、部署 | glm-5 | SWE-bench 77.8% — 开源模型第一 |
| op1_marketing | 内容创作、SEO | glm-5 | 极低幻觉率，202K 上下文支持 |
| op1_sales | 外联、对话 | glm-5 | 原生智能体模式 + "Slime" 规划 |
| op1_operations | KPI 分析、JSON | glm-5 | 结构化输出，BrowseComp 75.9% |
| CEO Orchestrator | 规划、路由 | glm-5 | Terminal-Bench 提升 28.3% |

### 预检查门控
系统通过 `dashboard/zai_preflight.py` 强制执行硬门控。如果环境配置不正确，系统将抛出 `ZAIPreflightError` 并停止运行。系统不会静默回退，确保严格符合 Z.AI 奖项要求。

---

## 黑客马拉松奖项

### 🏆 CEOClaw Challenge (£1,000)
- **证据**：CEO 编排器端到端运行 4 智能体循环；实现 $49 MRR 真实收入；部署 6 个 Vercel 产品。
- **验证方式**：`python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run`

### ⚡ Z.AI Gold Bounty
- **证据**：GLM-5 充当全部 5 个角色的核心模型。预检查门控强制执行正确的配置，且无静默回退。
- **验证方式**：`python3 -m pytest dashboard/tests/ -q`

### 🎮 Animoca Brands
- **身份**：CEO 拥有在 `workspaces/op1_ceo/AGENTS.md` 中定义的持久人格与逻辑。
- **记忆**：9 个 JSON 合约在智能体边界间持久化状态与学习成果。
- **认知**：Operations 迭代循环将反馈重新输入系统，实现持续改进。

### 🤝 Human for Claw
- **控制面板**：位于 `http://127.0.0.1:8765` 的专用视图提供直观的状态与产物追踪。
- **审批门控**：`approval.json` 门控所有外部操作，确保人类操作员保持最终控制权。

---

## 奖项覆盖矩阵

<div align="center">
<img src="docs/assets/bounty_map.svg" alt="Hackathon Bounty Coverage" width="80%">
</div>

---

## 仓库布局

- `openclaw/`：配置文件同步与安全脚本。
- `workspaces/`：隔离的智能体工作区及产物。
- `handoffs/`：智能体间的 JSON 交付合约（共 9 个）。
- `dashboard/`：本地监控器及创业工作室 Web 应用。
- `official-site/`：OperatorOne 官方介绍页。
- `shared/`：共享的提示词、技能及模板。
- `docs/`：架构设计、协议及指南。
- `apps/`：Next.js 门户及产品应用。
- `packages/`：共享的 @op1/* 软件包。

---

## 智能体拓扑

| 工作区 | 角色 | 是否在 manifest 中 | 主要职责 |
|---|---|---|---|
| `workspaces/op1_product` | Product | ✅ | 创意发现、Web 产品构建与部署 |
| `workspaces/op1_marketing` | Marketing | ✅ | SEO、内容创作与营销流水线 |
| `workspaces/op1_sales` | Sales | ✅ | 客户开发、外联与转化 |
| `workspaces/op1_operations` | Operations | ✅ | KPI 追踪与反馈循环 |
| `workspaces/op1_manager` | Manager | ❌ | 跨智能体编排与审计 |

---

## 端到端流程

主要的交付链条如下：

1. `op1_product` → `handoffs/product_to_marketing.json`
2. `op1_marketing` → `handoffs/marketing_to_sales.json`
3. `op1_sales` → `handoffs/sales_to_operations.json`
4. `op1_operations` → 反馈至 Product, Marketing 和 Sales。

---

## 控制面板

运行本地控制面板以监控项目状态。

```bash
python3 dashboard/server.py --host 127.0.0.1 --port 8765
```
访问地址：http://127.0.0.1:8765

---

## 官方网站

在本地预览官方介绍页面。

```bash
cd official-site
python3 -m http.server 4173
```
访问地址：http://127.0.0.1:4173
实时链接：https://official-site-theta.vercel.app

---

## 开发者参考

各工作区的详细文档位于 `workspaces/` 目录下的相应 `README.md` 文件中。

### 脚本辅助工具
- `python3 scripts/validate_handoffs.py --repo-root .`
- `python3 scripts/upgrade_handoffs.py --repo-root .`
- `python3 scripts/change_hygiene_guard.py --staged`
- `python3 scripts/reset_generated_artifacts.py --apply`

---

## 演示视频

详细的项目演示可见 `docs/demo_video_script.md`。

---

## 关于生成产物的说明

`workspaces/*/research/**` 目录下包含许多由机器自动更新的运行快照。在审查变更时，请将代码和合约变更与流水线输出更新区分开来。
