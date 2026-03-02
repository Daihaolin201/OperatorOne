# 给朋友的一键同步提示词（复制给 OpenClaw 即可）

请执行 **OperatorOne Profile-B 安全隔离同步（默认单开）**，严格遵守以下约束：

1) 只在 `~/.openclaw/workspace/OperatorOne` 下工作，不改动其他项目文件。  
2) 目标 profile 固定为：`operatorone`。  
3) 仅运行单一入口脚本：
   - `bash ~/.openclaw/workspace/OperatorOne/openclaw/sync-operatorone-safe.sh`
4) 如果我明确要求允许双网关并行，再改用：
   - `bash ~/.openclaw/workspace/OperatorOne/openclaw/sync-operatorone-safe.sh --allow-dual-gateway`
5) 执行完成后输出核对项（脚本会自动校验并打印）：
   - profile 配置文件路径（`openclaw --profile operatorone config file`）
   - gateway 的 CLI config path 与 daemon config path 一致，且都指向 operatorone
   - agents 已包含：`op1_product`, `op1_marketing`, `op1_sales`, `op1_operations`
   - `skills.load.extraDirs` **仅**包含：`~/.openclaw/workspace/OperatorOne/shared/skills` 对应绝对路径
   - `gateway.port` 为 `30740`
   - `agents.defaults.model.primary` 为 `openai-codex/gpt-5.3-codex`
   - 4 个专属 skills 目录存在：
     - `workspaces/op1_product/skills/`
     - `workspaces/op1_marketing/skills/`
     - `workspaces/op1_sales/skills/`
     - `workspaces/op1_operations/skills/`
   - 若默认 profile 存在 `~/.openclaw/agents/main/agent/auth-profiles.json`，则 `~/.openclaw-operatorone/agents/op1_*/agent/auth-profiles.json` 已存在
   - 默认 profile gateway 已停止（默认单开策略）

严格禁止：
- 覆盖默认 profile（不带 `--profile`）的 `channels.*`, `gateway.*`, `auth.*`
- 删除朋友已有的默认 profile agents（除非我明确要求执行 cleanup 脚本）
- 修改默认 profile 的 `skills.load.extraDirs`

如果发现同名 agent 冲突（在 operatorone profile 内），只报告冲突，不做覆盖。
