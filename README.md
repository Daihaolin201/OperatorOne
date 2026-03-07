[English](#operatorone--ceoclaw) | [中文](#operatorone--ceoclaw-中文)

---

# OperatorOne × CEOClaw

> **UK AI Agent Hackathon EP4 × OpenClaw — CEOClaw Challenge submission**
> Team: Dennis & Bennett · Branch: `dennis/automation-framework`
> Repo: https://github.com/Daihaolin201/OperatorOne

**CEOClaw** is OperatorOne's multi-agent CEO orchestrator that autonomously coordinates four specialist agents — Product, Marketing, Sales, and Operations — to run an internet business from initial idea to first customers.

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

## Architecture

```
CEO Orchestrator (run_ceo_multi_agent_orchestrator_v1.py)
  │
  ├─▶ op1_product  ──[product_to_marketing.json]──▶  op1_marketing
  │                                                          │
  │                                              [marketing_to_sales.json]
  │                                                          │
  │                                                   op1_sales
  │                                                          │
  │                                             [sales_to_operations.json]
  │                                                          │
  └─────────────────────────────────────────────── op1_operations
                                                             │
                                          [operations_to_product/marketing/sales.json]
                                                             │
                                                    (iteration loop)

Outputs: run.latest.json · venture_state.latest.json · orchestrator_summary.latest.json
```

---

## Repository Layout

- `openclaw/`: profile sync and safety scripts (`operatorone` profile).
- `workspaces/`: isolated agent workspaces and stage artifacts.
- `handoffs/`: inter-agent JSON contracts (9 contracts).
- `dashboard/`: local monitor and venture studio web app.
- `official-site/`: OperatorOne official intro page.
- `shared/`: shared prompts, skills, and templates.
- `docs/`: architecture, collaboration protocol, and runbook.
- `apps/`: Next.js portal and product apps (monorepo).
- `packages/`: shared @op1/* packages (ui, i18n, types, config).

---

## Agent Topology

| Workspace | Role | In manifest | Primary responsibility |
|---|---|---|---|
| `workspaces/op1_product` | Product | ✅ | Idea discovery, web product build/deploy, landing handoff |
| `workspaces/op1_marketing` | Marketing | ✅ | SEO/content/campaign pipeline |
| `workspaces/op1_sales` | Sales | ✅ | Prospecting, outreach, conversion |
| `workspaces/op1_operations` | Operations | ✅ | KPI tracking, feedback processing, iteration loop |
| `workspaces/op1_manager` | Manager (control plane) | ❌ | Cross-agent orchestration, audits, documentation hygiene |

---

## End-to-End Flow

The primary handoff chain proceeds as follows:

1. `op1_product` writes `handoffs/product_to_marketing.json`
2. `op1_marketing` writes `handoffs/marketing_to_sales.json`
3. `op1_sales` writes `handoffs/sales_to_operations.json`
4. `op1_operations` writes:
   - `handoffs/operations_to_product.json`
   - `handoffs/operations_to_marketing.json`
   - `handoffs/operations_to_sales.json`

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

### Quick Start
Follow the commands in the CEOClaw Quick Start section to clone the repository and run the orchestrator.

### Workspace Documentation
Detailed information for each workspace can be found in their respective `README.md` files within `workspaces/`.

### Script Helpers
- `python3 scripts/validate_handoffs.py --repo-root .`
- `python3 scripts/upgrade_handoffs.py --repo-root .`
- `python3 scripts/change_hygiene_guard.py --staged`
- `python3 scripts/reset_generated_artifacts.py`
- `python3 scripts/reset_generated_artifacts.py --apply`

---

## Demo Video

Detailed walkthrough can be found at `docs/demo_video_script.md`.

---

## Note on Generated Artifacts

`workspaces/*/research/**` contains many `*.latest.*` and run snapshots that are intentionally machine-updated. When reviewing diffs, separate **code, docs, and contract changes** from **pipeline output refreshes**.

---

<a name="operatorone--ceoclaw-中文"></a>
# OperatorOne × CEOClaw（中文）

> **UK AI Agent Hackathon EP4 × OpenClaw — CEOClaw Challenge 提交项目**
> 团队：Dennis & Bennett · 分支：`dennis/automation-framework`
> 仓库：https://github.com/Daihaolin201/OperatorOne

**CEOClaw** 是 OperatorOne 的多智能体 CEO 编排器，能够自动协调四个专业智能体（op1_product, op1_marketing, op1_sales, op1_operations），实现从创意发现到获取首批客户的全流程互联网业务运营。

---

## 实际成果

本项目非演示原型，以下数据源自真实的流水线执行。

| 指标 | 数值 |
|---|---|
| 当前 MRR | **$49** (目标: $100) |
| 已联系潜在客户 | **13** |
| 收到回复 | **6** |
| 已转化客户 | **1** |
| 已部署产品 | **6 个 Vercel 实时链接** |
| 已准备活动 | **9** (3 个就绪, 5 个观察名单, 1 个已批准) |
| 内容资产 | **12** (3 个已批准, 9 个待审核) |
| 智能体交付物 | **9 个 JSON 合约** |

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
- `venture_state.latest.json`：项目 KPI 快照（包含 MRR、潜在客户、营销活动、部署链接）。
- `orchestrator_summary.latest.json`：面向操作员的执行摘要。

---

## 工作原理

- **阶段门控多智能体循环**：各专业智能体（Product, Marketing, Sales, Operations）通过 JSON 合约向下一阶段交付成果，而非孤立的智能体调用。
- **审批门控外部操作**：通过 `approval.json` 控制邮件发送或部署等外部操作的权限，确保系统完全可审计。
- **真实的业务执行**：流水线已完成端到端运行，成功在 Vercel 部署 6 个产品，联系 13 位潜在客户，并获得 $49 MRR（月经常性收入）。
- **交付合约架构**：9 个类型化的 JSON 合约包含 `contract_version`, `generated_at`, `generated_by` 等元数据，确保全流程可追溯。
- **迭代循环**：Operations 的反馈（10 个事项，已按 P2/P3 优先级排序）会反馈给 Product, Marketing 和 Sales，开启下一轮迭代。
- **CEO 编排脚本**：`run_ceo_multi_agent_orchestrator_v1.py` 执行完整的 4 智能体序列，生成 `venture_state.latest.json` 并强制执行审批策略。

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

## 系统架构

```
CEO Orchestrator (run_ceo_multi_agent_orchestrator_v1.py)
  │
  ├─▶ op1_product  ──[product_to_marketing.json]──▶  op1_marketing
  │                                                          │
  │                                              [marketing_to_sales.json]
  │                                                          │
  │                                                   op1_sales
  │                                                          │
  │                                             [sales_to_operations.json]
  │                                                          │
  └─────────────────────────────────────────────── op1_operations
                                                             │
                                          [operations_to_product/marketing/sales.json]
                                                             │
                                                    (迭代循环)

输出: run.latest.json · venture_state.latest.json · orchestrator_summary.latest.json
```

---

## 仓库布局

- `openclaw/`：配置文件同步与安全脚本（使用 `operatorone` 配置）。
- `workspaces/`：隔离的智能体工作区及阶段性产物。
- `handoffs/`：智能体间的 JSON 交付合约（共 9 个）。
- `dashboard/`：本地监控器及创业工作室 Web 应用。
- `official-site/`：OperatorOne 官方介绍页。
- `shared/`：共享的提示词、技能及模板。
- `docs/`：架构设计、协作协议及操作指南。
- `apps/`：Next.js 门户及产品应用（单仓管理）。
- `packages/`：共享的 @op1/* 软件包（UI, 多语言, 类型定义, 配置）。

---

## 智能体拓扑

| 工作区 | 角色 | 是否在 manifest 中 | 主要职责 |
|---|---|---|---|
| `workspaces/op1_product` | Product | ✅ | 创意发现、Web 产品构建与部署、落地页交付 |
| `workspaces/op1_marketing` | Marketing | ✅ | SEO、内容创作、营销活动流水线 |
| `workspaces/op1_sales` | Sales | ✅ | 客户开发、外联、转化 |
| `workspaces/op1_operations` | Operations | ✅ | KPI 追踪、反馈处理、迭代循环 |
| `workspaces/op1_manager` | Manager (控制层) | ❌ | 跨智能体编排、审计、文档维护 |

---

## 端到端流程

主要的交付链条如下：

1. `op1_product` 生成 `handoffs/product_to_marketing.json`
2. `op1_marketing` 生成 `handoffs/marketing_to_sales.json`
3. `op1_sales` 生成 `handoffs/sales_to_operations.json`
4. `op1_operations` 生成：
   - `handoffs/operations_to_product.json`
   - `handoffs/operations_to_marketing.json`
   - `handoffs/operations_to_sales.json`

---

## 控制面板 (Dashboard)

运行本地控制面板以监控创业工作室状态。

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

### 快速开始
请参考“CEOClaw 快速开始”章节中的命令来克隆仓库并运行编排器。

### 工作区文档
各工作区的详细文档位于 `workspaces/` 目录下的相应 `README.md` 文件中。

### 脚本辅助工具
- `python3 scripts/validate_handoffs.py --repo-root .`
- `python3 scripts/upgrade_handoffs.py --repo-root .`
- `python3 scripts/change_hygiene_guard.py --staged`
- `python3 scripts/reset_generated_artifacts.py`
- `python3 scripts/reset_generated_artifacts.py --apply`

---

## 演示视频

详细的项目演示可见 `docs/demo_video_script.md`。

---

## 关于生成产物的说明

`workspaces/*/research/**` 目录下包含许多由机器自动更新的 `*.latest.*` 文件及运行快照。在审查代码差异（diff）时，请将**代码、文档及合约变更**与**流水线输出更新**区分开来。
