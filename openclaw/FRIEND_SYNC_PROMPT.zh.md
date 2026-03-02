# 给朋友的一键同步提示词（复制给 OpenClaw 即可）

请执行 **OperatorOne Profile-B 安全隔离同步**，严格遵守以下约束：

1) 只在 `~/.openclaw/workspace/OperatorOne` 下工作，不改动其他项目文件。  
2) 目标 profile 固定为：`operatorone`。  
3) 运行：
   - `bash ~/.openclaw/workspace/OperatorOne/openclaw/sync-openclaw.sh`
4) 将 gateway 服务明确切换到该 profile：
   - `openclaw --profile operatorone gateway install --force`
5) 同步后重启该 profile 的 gateway：
   - `openclaw --profile operatorone gateway restart`
6) 最后输出核对项：
   - profile 配置文件路径（`openclaw --profile operatorone config file`）
   - agents 已包含：`op1_product`, `op1_marketing`, `op1_sales`, `op1_operations`
   - `skills.load.extraDirs` **仅**包含：`~/.openclaw/workspace/OperatorOne/shared/skills` 对应绝对路径
   - `gateway.port` 为 `30740`
   - `agents.defaults.model.primary` 为 `openai-codex/gpt-5.3-codex`
   - 4 个专属 skills 目录存在：
     - `workspaces/op1_product/skills/`
     - `workspaces/op1_marketing/skills/`
     - `workspaces/op1_sales/skills/`
     - `workspaces/op1_operations/skills/`
   - 若默认 profile 存在 `~/.openclaw/agents/main/agent/auth-profiles.json`，则已将其复制到 `~/.openclaw-operatorone/agents/op1_*/agent/auth-profiles.json`（仅在目标缺失时复制）

严格禁止：
- 覆盖默认 profile（不带 `--profile`）的 `channels.*`, `gateway.*`, `auth.*`
- 删除朋友已有的默认 profile agents
- 修改默认 profile 的 `skills.load.extraDirs`

如果发现同名 agent 冲突（在 operatorone profile 内），只报告冲突，不做覆盖。
