# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [v1.0.0] - 2026-08-26

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
