# 多来源可信度筛选（按“可验证 + 可接入”双标准）

## 你的需求映射
你要的是：
1) 来源可靠；
2) 能持续接入；
3) 结论可解释、可落地。

所以我用两层标准筛选：
- **可信度层**：是不是一手操作者信号、是否带商业意图。
- **可接入层**：当前环境是否能稳定抓取（避免被 Cloudflare/反爬全面阻断）。

---

## 当前来源分层

### A层（已接入并在流水线生效）
1. **Reddit operator communities**（已接入）
   - 强项：痛点叙述细、场景真实、可直接看到损失和 workaround
   - 风险：情绪噪声高
2. **Hacker News（Algolia API）**（已接入）
   - 强项：技术/产品操作者密度高，API 稳定
   - 风险：偏技术人群，商业场景覆盖不均
3. **Shopify App Store（autocomplete + feature/category pages）**（已接入）
   - 强项：工具需求与商业意图强，能观测市场密度（apps count / reviews）
   - 风险：更偏 ecommerce 赛道

### B层（可信但当前接入受阻，列为后续）
4. **G2/Capterra**（暂未接入）
   - 原因：当前环境被 403/Cloudflare 阻断，需浏览器会话或代理策略
5. **招聘 JD（Indeed/LinkedIn）**（暂未接入）
   - 原因：当前环境验证墙阻断，建议改用可访问的公开 ATS 源

---

## 准入规则（已经写入框架）
- 机会进入 Stage2 前，至少：
  - **2 个独立来源支持**；
  - 每来源至少 1 条可追溯 URL；
  - 同时具备“损失信号”与“商业意图信号”。

对应配置：`framework/config/source_trust_rank.json`
