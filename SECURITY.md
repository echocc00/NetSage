# Security Policy

## Supported Versions

| Version | Supported | 说明 |
|---|---|---|
| v1.0.0 | ✅ | Latest release（生产化完成） |
| v0.3.0 | ✅ | WirelessAgent + 多租户 SSO + NetAI-Bench |
| v0.2.0 | ✅ | RDMA 专项（OpenSM + RdmAgent） |
| < v0.2.0 | ❌ | 不再接收安全补丁，请升级到最新 release |

## Reporting a Vulnerability

如果你在 NetSage 中发现安全漏洞，**请不要**通过公开 Issue / Discussion / Pull Request 报告。

### 通过以下渠道私下报告

1. **GitHub Private Vulnerability Reporting**（推荐）
   - 仓库首页 → **Security** tab → **Advisories** → **Report a vulnerability**
   - 或访问 https://github.com/echocc00/NetSage/security/advisories/new
2. **Email**：`security@echocc00.dev` *(邮箱未启用占位 — 启用前请使用 GitHub 渠道)*

### 报告应包含

- 受影响版本
- 漏洞描述（攻击场景、影响范围）
- 复现步骤（尽量给出 PoC）
- 影响评估（CVSS 估算 / OWASP Top 10 类别）
- 是否已公开 / 是否被利用
- 你的联系方式（可选）

## Response Timeline

| 阶段 | 承诺时间 |
|---|---|
| 首次响应 | 收到报告后 **48 小时内** |
| 严重度评估 | 首次响应后 **3 个工作日内** |
| 修复发布 | 关键/高危 **≤ 14 天**；中危 **≤ 30 天**；低危 **≤ 90 天** |
| 公开披露 | 修复发布后 **90 天**或经与报告者协商 |

## Scope

### 在范围内

- NetSage 核心代码（backend / frontend / mcp-servers / cli）
- Docker / docker-compose 部署配置（含 docker-compose.prod.yml）
- 暴露端口与默认凭据问题
- **写通道安全边界**：三道闸绕过、审批门禁绕过、LLM 裸发命令
- **数据脱敏**：黑盒内容（running-config / 凭据 / 原始日志）泄漏到 LLM
- **审计完整性**：哈希链篡改、审计日志绕过
- RBAC 权限提升（viewer → engineer/admin）
- OIDC/SSO 流程漏洞（state/nonce/PKCE 绕过）
- RAG / LLM 注入 / 提示词越权
- 与上游集成的安全（NetBox / Nautobot / Batfish / Containerlab / SUZIEQ / OpenSM）

### 不在范围内

- 上游开源项目本身的漏洞（请直接报告给上游）
- 已知的、被 CVE 数据库收录的依赖漏洞
- 社工攻击 / 物理攻击
- 需要用户主动安装恶意软件的攻击
- mock 模式下的行为（OpenSM/Nautobot mock 仅开发用，非生产路径）

## Recognition

负责任的漏洞报告者将在：
- CHANGELOG.md 中致谢
- SECURITY Hall of Fame（如未来设立）

不接受金钱奖励，但可获：
- 优先获得新功能/补丁的提前体验
- 公开致谢（如希望匿名也可）

## Security Best Practices for Users

部署 NetSage 时建议：

1. **使用最新 release**（v1.0.0）
2. **生产必填密钥**：`JWT_SECRET` / `POSTGRES_PASSWORD` 不可用默认值（启动会拒绝）
3. **保持脱敏开启**：不要设置 `REDACT_BLACKBOX_LOCAL_ONLY=false`（会允许 running-config 外发）
4. **GPL 隔离**：OpenSM 走进程外调用，不链接不分发（见 doc/NetSage-最终技术方案-v2.0.md 二十一章）
5. **网络分段**：生产部署在独立网段，避免暴露公网
6. **启用审计**：所有变更落审计哈希链，DB 层 REVOKE UPDATE/DELETE
7. **CORS 收窄**：`CORS_ORIGINS` 填具体域名，不用通配符
8. **及时更新依赖**：`pip install --upgrade` / `npm update`

## License

本项目采用 Apache-2.0 License。Security Policy 是 License 的补充，不构成额外法律承诺。

---

<sub>Last updated: 2026-09-05 · Maintained by [@echocc00](https://github.com/echocc00)</sub>
