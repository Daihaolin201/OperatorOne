# 给朋友的一键同步提示词（复制给 OpenClaw 即可）

请执行 **OperatorOne 安全增量同步**，严格遵守以下约束：

1) 仅在 `~/.openclaw/workspace/OperatorOne` 下工作，不改动其他项目文件。  
2) 先检查仓库是否存在：
   - 若不存在，提示我先 `git clone` 到 `~/.openclaw/workspace/OperatorOne`。
3) 运行：
   - `bash ~/.openclaw/workspace/OperatorOne/openclaw/sync-openclaw.sh`
4) 同步完成后执行：
   - `openclaw gateway restart`
5) 最后输出以下核对项：
   - 新增/存在 agents：`op1_product`, `op1_marketing`, `op1_sales`, `op1_operations`
   - `skills.load.extraDirs` 已包含：`~/.openclaw/workspace/OperatorOne/shared/skills` 对应绝对路径
6) 严格禁止：
   - 覆盖 `agents.defaults.workspace`
   - 改动 `channels.*`, `gateway.*`, `auth.*`
   - 删除已有 agents

如果发现冲突（如同名 agent 已指向不同 workspace），请只报告冲突，不做覆盖。
