# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### v0.5.0 阶段1 · per-tenant IdP（波1）

- `Settings.oidc_tenants`（env JSON）：`{tenant_slug: {discovery_url, client_id, client_secret}}` 覆盖全局默认 IdP
- `/auth/oidc/login?tenant=<slug>` 按租户路由到各自 IdP；`/callback` 从 state 恢复租户后**用该租户凭据**做 token 交换 + 按租户 client_id/issuer/JWKS 验签（隔离）
- `/auth/oidc/idps` 暴露已启用 SSO 的租户列表（登录页租户选择用）
- 未匹配租户回退全局 `default` IdP（向后兼容，单测 16→21 全过，真实 Keycloak E2E 8 通过）

### v0.5.0 阶段1 · OIDC 去 🟡（Keycloak 真实 E2E）

- `infra/docker-compose.keycloak.yml`：Keycloak 22.x 实例（start-dev，端口 9090）
- `backend/scripts/provision_keycloak.py`：Admin REST 幂等 provision（realm=netsage / 5 角色组 / alice·bob·carol·dave 用户 / 机密 client netsage-web(PKCE S256 + 标准流 + 直连授权) / groups→claims['groups'] mapper）；client secret 因 Keycloak 22 只生成随机值，持久化到 gitignored 的 `.env.keycloak`
- `backend/tests/integration/test_keycloak_e2e.py`（8 测试，真实 provider）：真实 discovery / 真实 JWKS RS256 / **完整 Authorization Code + PKCE 全链路**（headless 完成 Keycloak 登录表单 → 回调验签（iss/aud/exp/nonce）→ 签发本地 JWT + groups→RBAC）/ state 单次使用防重放 / 错误 code 401 / 真实 id_token 签名独立验证 / provision 幂等
- CI 新增 `keycloak` job（起实例 → provision → E2E）
- `.env.example` 增 OIDC 变量块；README「多租户 + SSO」转 ✅（真实 Keycloak 22 已验证），已知限制同步；SECURITY.md OIDC 范围注明真实 E2E

### 计划 v0.4.2（已发布 2026-09-06，见下）

## [v0.4.2] - 2026-09-06

### 收尾补丁（按 v0.4.2 规划）

**CLI nsc 落地**
- 命令增强至 8 个：新增 `version` / `status`（--url）；`ask` 链式产出 Markdown 报告（配置意图含 diff + lint，后端不可用回退意图分类）；`simulate` 支持 `--change-id` 触发真实三道闸
- `cli/nsc/tests/` 新增 23 测试（respx mock httpx，不碰真实后端）；test.yml 新增 `cli` job 跑 CLI 测试；pyproject version 0.1.0→0.4.2 + `[test]` 依赖组
- README 能力表 CLI nsc 改 ✅（8 命令，23 测试）

**frontend Dockerfile + nginx**
- `frontend/Dockerfile`（multi-stage node:20-alpine → nginx:1.27-alpine）、`nginx.conf`（/api 反代 backend:8000 + SSE 关缓冲 + SPA fallback + gzip + 静态缓存）、`.dockerignore`
- prod compose 补 frontend 服务引用（此前引用缺失的 Dockerfile）；CI docker job 加 frontend 镜像 build
- 实测：镜像 70.4MB（目标 ≤80MB），容器 health=healthy，`/` 返回 `<title>NetSage`，`/health` 200
- 修一个真实缺陷：busybox wget 里 localhost 解析到 `::1` 会被拒，healthcheck 改用 `127.0.0.1`

**mypy 收敛严格真阻断**
- `disable_error_code = ["type-arg"]` 封顶纯机械泛型噪音；test.yml 删除 `continue-on-error: true`，PR 再引入类型错会红
- 修 133 个真实类型错误：安全关键模块（redact/gates）全类型零错；7 个 Agent DEFINITION 动态 schema 注解 `dict[str, Any]`；handler `llm=None` 参数注解；`r.json()`/`.get()` 返回值收窄；async generator Protocol 签名修正；多处被 mypy 揪出的真实问题（`_est_tokens` 浮点累加、`get_sentence_embedding_dimension()` 可空、`rdma.save_fabric` 缺 return、`_default_for` 缺返回类型）
- 结果：`mypy app` 0 错 / 88 文件；ruff 0 告警

**测试数三层口径透明化**
- `backend/tests/conftest.py::test_inventory()` + CHANGELOG 区分 292 functions / 501 cases / 18 e2e；eval/README 加"测试层级（统计口径）"章节

**AGENTS.md + CHANGELOG Unreleased**
- 新增 `AGENTS.md`（编码风格 / 测试要求 / 文档约定 / 安全红线 / 仓库策略 5 分类）；CHANGELOG 顶部加 [Unreleased]

**gitignore 收尾**
- `__pycache__/` 已覆盖；`doc/` 无跟踪中途文件；前瞻规划文档（v1.0.2/v2.0）按"仅本地保留"约束移出版本控制

**测试**：292 unit functions 展开 501 unit cases + 18 e2e scenarios + 23 cli 全部通过；ruff + mypy 双 0

## [v0.4.1] - 2026-09-06

### 第三方审计问题修复（P7-1 ~ P7-8）

**安全修复**
- **脱敏接入 LLM 网关（P0）**：`redact/` 模块此前无调用方，配置原文直发 LLM。现 `LLMGateway.complete()` 强制过 `RedactingInterceptor`——黑盒内容（running-config）抛 `BlackboxBlockError` 阻断，灰盒强制脱敏，缓存存脱敏态，响应按 `MappingTable` 还原
- **OIDC 补齐 OAuth 2.1 要求**：PKCE S256（RFC 7636）+ nonce 防重放（OIDC Core 3.1.3.7）+ JWKS 验签（此前未校验 id_token 签名）+ state TTL 600s 单次使用；角色映射默认最小权限 VIEWER

**Agent 代码深度（此前 README 声明与实现不符）**
- WirelessAgent 3→5 节点：新增射频规划（信道复用 + 层间偏移 + 功率）、漫游安全（802.11r/k/v + PMF + RADIUS），AP 定容改为容量/覆盖双约束
- RdmAgent 3→4 节点：新增 Fabric 设计（Spine-Leaf 规模 + buffer 预算 + RoCE underlay 选型 / IB 分区键 + VL 映射 + SM 配置）
- SecurityAuditor 4→6 节点：新增攻击面测绘（8 正向 + 4 反向探测）、加固优先级（按风险分降序）

**质量门禁**
- CI：`.github/workflows/test.yml`（ruff + mypy + 单元 + e2e + 513 题 schema + 86 模板渲染 + Docker 构建）、`security.yml`（CodeQL + 密钥扫描 + bandit）、`CODEOWNERS`
- E2E：`backend/tests/e2e/test_full_flow.py` 18 测试 / 8 场景，TestClient 跑真实 HTTP 链路（中间件 + RBAC + 审计）
- ruff 清零 193 项，其中修 3 个真实缺陷：重复 `run_troubleshooter` 路由（后者静默覆盖前者）、`update_device_status` 多余 GET、`_correlate_changes` 死变量

**可审计性**
- 513 道评测题补 `source` 溯源字段（manual 30 / template_derived 81 / auto_generated 402），schema 强校验；`eval/README.md` 按来源分层说明引用权重
- 24 个一次性生成脚本归档到 `scripts/_build_archive/`，仓库根 `scripts/` 只留运维脚本
- **RAG hit_rate 首次实测**：bge-m3 真实向量 + 本地构建 pgvector，全量 33.9%（174/513）、语料内 99.4%（174/175）。瓶颈为语料覆盖（3 份华为手册 54 chunks，上限 34.1%）而非检索算法。报告见 `eval/reports/hit_rate-v1.0.md`
- `SECURITY.md` 改为 NetSage 专用（此前为模板残留），README 能力表引入 ✅/🟡 分级 + "已知限制（诚实清单）"

**测试**：292 unit functions 展开 501 unit cases + 18 e2e scenarios 通过（`pytest tests/ --collect-only` 501+18），ruff + mypy 双 0 告警

## [v0.4.0] - 2026-08-26

### 生产化（Phase 4 M12）

**新增**
- 运营大屏：`/reports/{overview,devices,changes,compliance,dashboard,llm-usage}` + 前端大屏页（6 统计卡 + 设备健康 + 变更流水线 + RCA 命中率，30s 自动刷新）
- DR/备份：`scripts/backup.sh`（PG dump + 模板 + 评测题 + sha256 校验）、`scripts/restore.sh`、`doc/NetSage-DR-Runbook-v1.0.md`（RPO 24h / RTO 2h + 月/季/年演练计划）
- 健康检查强化：`/health/ready` 并行探测 PG / Redis / LLM / SSoT
- LLM 成本优化：sha256 响应缓存 + per-model 用量统计
- 生产部署：多阶段 Dockerfile（builder + runtime + healthcheck）、`infra/docker-compose.prod.yml`（资源限制 + 依赖健康门禁）
- OpenAPI：tags 分组 + description + Redoc
- NetAI-Bench Runner：`eval/runner/run_all.py`（513 题批量评测 + pass_rate 报告）

**测试**：447 单元测试通过

## [v0.3.0] - 2026-08-24

### WirelessAgent + 多租户 SSO + NetAI-Bench 发布（Phase 4 M10/M11/M12）

**新增**
- WirelessAgent（第 10 个 Agent）：AP 布放规划（面积/用户/楼层 → AP 数量）+ 信道轮转（2.4G 1/6/11，5G 36/40/44/48）+ 漫游域 + 安全策略 + 配置模板渲染
- `/wireless/plan` + `/wireless/templates` API + 前端无线专项页
- 多租户：Tenant model（slug / plan / quota / oidc 配置，alembic 0006）
- SSO：`/auth/oidc/{login,callback,config}` + `/auth/oidc/tenants`，未配置时降级 dev-token
- NetAI-Bench 对外发布：`eval/README.md`（benchmark 说明 + BibTeX 引用）+ `eval/reports/benchmark-v1.0.md`（513 题统计）

**测试**：433 单元测试通过（+12）

## [v0.2.0] - 2026-08-24

### RDMA 专项（Phase 4 M7-M9）

**新增**
- RdmAgent（第 9 个 Agent）：collect → diagnose → suggest_tuning
- RoCEDiagnoseEngine：PFC/ECN/buffer/MTU 规则库 + 概率排序
- OpenSM 容器化：`infra/docker-compose.opensm.yml`（官方 rdma-core 镜像，GPL 隔离三条红线）
- opensm-mcp：ibstat / ibdiscover / perfquery / ibnetdiscover / sminfo（mock 模式默认）
- RoCE 模板库：华为/Cisco/Arista × PFC/ECN（6 模板）
- Nautobot App v0.2：RdmaFabric model
- 前端 RDMA 专项页

## [v0.1.1] - 2026-08-23

### 模板库补齐

**新增**
- 模板库 10 → 86（5 厂商 × 7 协议：bgp / ospf / vxlan / vpn / interface / static_route / wireless）
- 新增 feature：bgp_ipv6_family / ospf_stub_area / static_route_policy_route / juniper+arista wireless

**修复**
- `template_loader.VALID_PROTOCOLS` 补 `interface` / `static_route`
- `render()` 对可选参数注入类型默认值（修 29 个模板 StrictUndefined 误报，必填仍严格校验）
- 3 个 IPsec 模板补 `remote_mask` / `nat_group` 到 input_schema

**测试**：225 单元测试通过（+188 模板用例）

## [v0.1.0] - 2026-08-23

### 首发（Phase 1 + 2 + 3）

**Phase 1（M1-M2）平台骨架**
- FastAPI 后端 + RBAC 五级（viewer / operator / engineer / admin / auditor，等保三权分立）
- 设备接入层：NAPALM / netmiko / scrapli 三适配器 + AdapterFactory
- Agent 编排层：agent_runtime + SequentialBackend + 6 Agent + 6×7 意图分类
- 三道闸引擎：Containerlab 仿真 → Batfish 校验 → 人工审批 + 快照回滚
- MCP Server ×3：containerlab / batfish / napalm
- 数据脱敏：Layer1 静态字典（8 类 PII）+ Layer3 决策路由（白/灰/黑盒）
- 审计：sha256 哈希链 + INSERT ONLY
- RAG 管线：ingest + 混合检索 + 重排序（pgvector）
- React 前端 + React Flow 拓扑 + CLI nsc

**Phase 2（M3-M4）多厂商 + 数据闭环**
- SourceOfTruth 接口 + NetBoxAdapter（v4 REST，v2 token `Bearer nbt_`）
- netbox-mcp + suzieq-mcp
- H3C Batfish 静态校验（Cisco parser loose validation）
- SUZIEQ Poller + ObserverAgent + Assert 框架
- DeployAgent：顺序下发 + checkpoint + 失败自动回滚
- RCA 引擎：26 条规则 + 概率排序 + 变更关联（≥3 候选根因）
- Troubleshooter Agent + 拓扑可视化（节点点击 Drawer + 健康高亮）

**Phase 3（M5-M6）Nautobot + 安全合规 + 自动化闭环**
- NautobotAdapter（mock 模式）+ 双适配器 factory
- 自研 Nautobot App v0.1：NetworkDesign 持久化（本地 PG + Django plugin 双轨）
- SecurityAuditor + 基线规则库 30 条（Cisco 15 + 华为 15，认证/管理/协议/ACL）
- ACL 分析：reachability / shadowed / unused（Cisco + 华为）
- ComplianceAgent + Markdown/CSV 报告导出
- 自动化闭环 Orchestrator：诊断→修复→验证→审批→下发→监控（自动化率 83%）
- audit 权限加入 admin / auditor

**验收**：Phase 2 12/12 · Phase 3 12/12
