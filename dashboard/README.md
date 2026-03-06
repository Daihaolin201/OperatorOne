# OperatorOne Dashboard (v1)

一个本地可运行的 Dashboard，用于：

1. 监控四个 agent（Product / Marketing / Sales / Operations）的运行状态
2. 展示输入输出链路（handoffs）
3. 给出“是否允许和外界联系”的门禁判定（BLOCKED / REVIEW_REQUIRED / READY）
4. 提供受控接入能力（社交渠道接入 + API 集成登记 + secrets 审计）

---

## 快速启动

在仓库根目录执行：

```bash
python3 dashboard/server.py --host 127.0.0.1 --port 8765
```

打开：

- <http://127.0.0.1:8765>

---

## 数据来源

### Agent 能力与产物

- `workspaces/op1_product/research/...`
- `workspaces/op1_marketing/research/...`
- `workspaces/op1_sales/research/...`
- `workspaces/op1_operations/research/...`
- `handoffs/*.json`

### OpenClaw 运行时

通过 CLI JSON 输出读取：

- `openclaw --profile operatorone status --all --json`
- `openclaw --profile operatorone channels status --json`
- `openclaw --profile operatorone channels list --json`
- `openclaw --profile operatorone secrets audit --json`

---

## 门禁策略（Policy-as-Code）

配置文件：

- `dashboard/config/readiness_policy.json`

核心规则：

- **Demo Gate**：能力与核心 handoff 是否完整
- **Live Gate**：在 Demo 基础上，要求渠道已连接、secrets 审计干净、人工 arm 开关开启、安全审计无 critical

状态含义：

- `BLOCKED`：禁止外联（基础条件不足）
- `REVIEW_REQUIRED`：具备部分条件，但需人工确认
- `READY`：可进入外联执行

---

## 社交渠道接入（受控）

Dashboard 内提供受控动作（白名单命令）：

- `channels add`
- `channels remove`
- `secrets audit`
- `secrets reload`

目前支持接入字段：

- telegram / discord：`token`
- slack：`botToken` + `appToken`
- googlechat：`webhookUrl` 或 `audience`
- whatsapp：可先创建 account（后续按 OpenClaw 流程完成登录）

> 为安全起见，Dashboard 不提供任意 shell 执行。

---

## API 集成登记

Dashboard 支持登记 API 连接元信息（名称、baseUrl、secretRef、ownerAgent、备注），
用于审计与可视化，不强制保存明文密钥。

本地保存路径：

- `dashboard/.runtime/api_connectors.json`

---

## 文件结构

```text
/dashboard
  collector.py                 # 快照采集与能力评估
  server.py                    # HTTP API + 静态页面服务
  /config
    readiness_policy.json      # 门禁规则
    industry_patterns.json     # 行业方案映射
  /web
    index.html
    app.js
    styles.css
  /.runtime                    # 运行态数据（gitignore）
```

---

## 行业方案映射（已纳入）

- LangSmith：预置/自定义看板 + 自动化规则
- OPA：策略与执行解耦（Policy-as-Code）
- Grafana / SRE 实践：统一告警与面向决策的看板
- GitHub Environments：高风险动作先审批
- Stripe Idempotency：预留幂等动作设计位
- OpenClaw Secrets：凭据审计与安全重载

---

## 当前边界

v1 重点在“监控 + 门禁 + 受控接入”。

后续可扩展：

- 外联动作审批流（多人 reviewer）
- 幂等键与动作重放保护
- 实时流式事件（WebSocket）
- 更细粒度的渠道/账号权限矩阵
