# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [v0.5.1] - 2026-10-25

### 校验闸真实化 + ACL 去示例化 + 审计物理只读（三闸真实化收尾）

> 本版完成后：三道闸中仿真闸（containerlab）与校验闸（batfish）均有真实链路实测；
> 审计记录 owner 也无法改写（物理只读）；全部包版本对齐 0.5.1。

**Batfish 校验闸真实链路（`backend/scripts/verify_batfish_real.py` 8/8）**
- 直连 pybatfish 5 项 + 经 batfish-mcp 3 项：真实 lint（合法配置 0 warning / 错误配置检出 2）/ 真实路由表查询 / 失败传播（不存在前缀 → 空）/ MCP load_snapshot / MCP lint+routing
- 真实调试修复 batfish-mcp 三个 bug：① `set_snapshot` 重复传参 TypeError；② `routes()` 不支持 prefix 参数（版本 API 差异）→ 全表+本地过滤；③ **TableAnswerElement 解包错误**——`answerElements` 是表格包装（0 行结果也会被数成 1 条警告，恒 fail），真结果在 `rows` 里
- 快照目录结构实测：Batfish 要求 `root/configs/device.cfg` 包装（"Unexpected packaging" 报错指引）
- 新增 3 个真实查询工具：`search_filters` / `interface_properties` / `filter_tables`（ACL 分析用）

**ACL 分析去示例化（评审 P1 收尾）**
- `acl_analyzer.py` 硬编码示例数据（编造 shadowed/unused 结论）移除——改走 ToolRegistry 真实断言（searchFilters 流量匹配 + 接口引用检查找 unused ACL）；Batfish 不可达时如实返回 `error` 说明，不编造

**审计物理只读（migration 0008，等保 INSERT ONLY 最后防线）**
- `BEFORE UPDATE/DELETE` trigger 强制抛异常——此前 REVOKE 对表 owner 无效的缺口补上（实测 owner UPDATE/DELETE 均被拒）
- DB 集成测试同步：篡改模拟改为 trigger 拒绝断言（防线一），哈希重算检测保留在内存链测试（防线二）

**napalm-mcp 真实化（`backend/scripts/verify_napalm_mcp.py` 4/4）**
- 真实调试修复 driver 映射 bug：`cisco_iosxe` 原映射 `"iosxe"` 不是有效 napalm driver（Cannot import 报错）——正确为 `"ios"`
- 验证 server 侧真实连接失败传播（不可达地址 → napalm 库真实 TCP 尝试）+ 不支持厂商校验拒绝
- 新增 `napalm-mcp/run_http.py`（streamable-http sidecar 入口，与 containerlab/batfish 同配方）

**其他**
- JWT decode 强制校验 iss/aud（encode 侧此前已带、decode 不验）
- pyproject 新增 `[batfish]` 可选依赖组（pybatfish）
- `GET /changes` 的 `count` 修正为全库真实总数（原取 len(items) 被 limit 截断）
- 包版本对齐 0.5.1（backend / cli / frontend / settings.version）
- 测试口径：316 unit functions / 534 unit cases / 18 e2e；ruff + mypy strict 双 0

## [Unreleased]

### v0.5.0 阶段2 补充 2 · containerlab 仿真闸真实链路打通 + CI DB 门禁

**containerlab 真实拓扑部署实测（诚实清单最后一项：仿真闸真实链路）**
- `backend/scripts/verify_containerlab_real.py` **6/6 通过**：真实部署 2 节点 alpine 拓扑
  （宿主 Docker 独立佐证容器存在）→ inspect 返回真实节点（含管理网 IP）→
  `exec_on_node` 节点内真实 ping（busybox 输出）→ destroy 真实销毁且无残留
- **containerlab-mcp 适配 containerlab 0.82 CLI**（真实调试发现）：`destroy --label` /
  `inspect -c --label` 旗标已在 0.6x+ 移除——改用 `destroy --name` 与
  `inspect --all --format json`（顺带把脆弱的表格文本解析换成 JSON 解析）
- 新增 `mcp-servers/containerlab-mcp/run_http.py`：streamable-http 启动入口
  （sidecar 部署，v2.0 二十六章 26.3 落地）
- **clab-in-docker sidecar 配方**（Windows Docker Desktop 实测）：
  `docker run -d --privileged --pid=host -v //var/run/docker.sock:/var/run/docker.sock
  -p 19002:9001 debian:bookworm-slim` + 容器内安装 docker.io/python3-pip +
  containerlab(.deb) + fastmcp/structlog，docker cp 源码后
  `PYTHONPATH=shared:containerlab-mcp python3 run_http.py`。
  关键点：`--privileged`（写 /proc/sys rp_filter）与 `--pid=host`（访问节点 netns）
  缺一不可；`--pid=host` 缺失时 deploy 报 "namespace path not available"

**CI 新增 db-integration job（PG 模式进门禁防回归）**
- `.github/workflows/test.yml`：pgvector/pg16 service + `alembic upgrade head` +
  `tests/integration/test_db_mode.py` + `test_rag_integration.py`——DB 模式
  （变更落库/审计链/快照共享/RAG）从"仅本地手跑"升级为 CI 阻断门禁

### v0.5.0 阶段2 · 系统评审修复（三道闸接线 / 审计落库 / 报表去编造）

> 修复第三方评审认定的三项核心差距（P0）：三道闸生产路由 mock 硬编码、
> 审计哈希链零调用、运营报表编造数字；以及一批 P1/P2（auto_approve 可跳审批、
> 变更单内存态、快照多 worker 失效、脱敏可绕过、SSE 路由 404 等）。

**三道闸真实工具链（P0）**
- 新增 `HttpToolRegistry`（`app/tools/http_registry.py`）：按 `<server>.<tool>` 前缀经 fastmcp 客户端调真实 MCP server；`app/tools/wiring.py` 双模式装配——`TOOLS_BACKEND=mcp` 走真实 server，默认 mock（演示预设必过，启动 WARNING + API 响应 `tools_mode` 字段明示）
- `changes.py` 三道闸/下发路由不再就地 `new MockToolRegistry()`，改用 main.py lifespan 装配的全局注册表（`configure_tools` 此前零调用）
- napalm-mcp 新增 `apply_candidate` 原子复合工具（单连接 load+compare+commit，修复 per-call 连接下 candidate 会话必丢的 H2 bug）；`GatePipeline.deploy`/`SnapshotService.rollback` 改用
- 工具名对齐：pipeline 此前调 `napalm.apply_candidate` 但 server 侧不存在——现已实现闭环

**审计哈希链接线（P0）**
- `AuditService` 此前全库零调用：现 `DbAuditSink`/`MemoryAuditSink` 双实现 + 启动 DB 探测装配；变更单 create/run_gates/approve/deploy 与闭环运行写入审计链（**fail-closed：审计写失败操作 503 中止**）
- `verify_chain` 重算 sha256（此前只比对链式相等，改写记录内容不被发现）；payload 补 ts（改时间戳不影响哈希的漏洞）；migration 0007 加 `audit_logs.prev_hash` 唯一约束 + IntegrityError 重试（并发分叉链防护）

**运营报表去编造（P0）**
- `reports.py` 5 端点硬编码演示数字（devices=5 / automation_rate=0.83 / rca_hit_rate=0.75）全部移除：变更统计来自 ChangeStore 实时计数、设备来自 SSoT（不可达如实标注 `unreachable`）、无历史数据的指标显式 `null + no_data` 说明，`meta.demo=false` 标注数据源

**安全修复（P0/P1）**
- `auto_approve` 服务端强制：非 dev 环境恒为 False（此前为纯请求参数，任何人传 true 跳过人工审批直达下发）+ 生产强制日志
- agents deploy 路由：生产必须携带 `change_id` 且对应变更单状态为 approved（此前路由自写 `change_status="approved"` 绕过审批校验）
- 脱敏内容自动分级（`redact/detector.py`）：声明白盒但内容含 running-config/日志特征时 tier 只升不降（配置强特征→黑盒阻断，片段→灰盒强制脱敏），不再信任调用方字符串
- 脱敏正则加固：`secret 5 $1$salt$hash` 整行值清除（此前真实哈希外发）、主机名后缀扩充（.lan/.localdomain/.priv/.home）、IPv4 严格 0-255 段、去魔法索引
- 模板参数消毒（`validate_param_values`）：参数值含换行/控制字符拒绝渲染（LLM 生成值注入任意配置行的通路封死）

**数据层落地（P1）**
- migration 0007：补齐 models 定义但从未迁移的 7 张表（projects/credentials/devices/change_requests/change_steps/approvals/config_snapshots）
- 变更单从进程内 dict 改为 `ChangeStore` 双实现（DB 落库 / 内存回退，启动探测自动选择 + 日志明示）；`GET /changes` 列表路由（前端审批页此前 405）
- 快照正文经 `SnapshotObjectStore` 落 config_snapshots 表（多 worker 下 /run 与 /deploy 落不同 worker 快照读空的问题修复）
- napalm/netmiko/scrapli 适配层依赖声明（pyproject optional `[vendors]`）

**前端/CLI 断链修复**
- `GET /agents/sessions/{id}/stream` SSE 路由落地（此前 docstring 宣称但未实现，前端 EventSource 404）；一次性 ticket 鉴权（120s TTL 单次使用，避免 JWT 进 URL）
- 前端 changes/devices/dashboard/troubleshoot 四页接真实 API（审批/驳回按钮、SSE ticket、报表 null 健壮渲染、移除死按钮与死依赖）
- CLI `report` 改调真实 `GET /reports/overview`（此前本地硬编码字符串拼接假报告）

**基础设施**
- backend Dockerfile：修 builder 阶段 editable 空壳 bug（源码未拷入先 install -e）、新增 `.dockerignore`（.venv/tests 不再打进镜像）、非 root 用户运行
- prod compose：`NAUTOBOT_MOCK`/backend 端口绑定改环境变量驱动（默认 `127.0.0.1:8000`，`.env.example` 补说明）
- backup/restore 脚本：恢复提示指向真实产物、SHA256SUMS 落盘且 restore 前校验、venv 路径自动探测（Windows/Linux）

**质量护栏**
- `test_inventory` 从无断言硬编码（且作为 conftest 函数根本不被 pytest 收集）改为收集钩子精确计数 + 按目录域强校验（`tests/unit/test_inventory_sync.py`）：测试数漂移即红
- baseline_scanner `absent/present` 行级否定语义修复（`no ip http server` 不再被误判违规）
- 测试口径更新：314 unit functions / 532 unit cases / 18 e2e（+25 项 v0.5.0 修复回归测试 + 快照失败防护）；ruff + mypy strict 双 0

### v0.5.0 阶段2 补充 · Docker 环境实测（DB 模式 + MCP 真实链路）

> 前置：docker compose dev（PG/pgvector）。此前所有验证均在无 DB/无 MCP server 环境下进行。

**DB 模式实测（真实 PostgreSQL，`alembic upgrade head` 0001→0007 全链执行成功）**
- `tests/integration/test_db_mode.py` 4 测试全过：DbChangeStore 全流程（CRUD/审批/快照/统计落 PG）；**审计链篡改检测**（owner UPDATE 记录后 verify_chain=False，还原后 True——重算哈希防线生效）；跨存储实例快照共享（多 worker 场景）；HTTP 生命周期落库（change_requests status=done + 审计 ≥4 条 + 快照正文落库 + 全链 verify 通过）
- 此前一直 skip 的 PG 相关测试随 PG 在线全部执行通过（unit 531 → 全绿）

**MCP 真实链路实测（`backend/scripts/verify_mcp_chain.py`，6/6 通过）**
- HttpToolRegistry → fastmcp streamable-http 真实协议调用（initialize/tools/call/DELETE 完整会话）
- `TOOLS_BACKEND=mcp` + 真实 uvicorn：三道闸四闸（快照/仿真/校验/审批）结果全部来自真实 MCP HTTP 响应（非 mock stub），下发经 `apply_candidate` → done
- **真实失败传播**：切真实 containerlab-mcp（宿主机无 containerlab CLI）→ 仿真闸 sim_failed，错误为真实 `[WinError 2]`——闸门不再无条件放行
- 遗留：真实 containerlab 拓扑的**成功路径**（部署真节点跑仿真检查）需 Linux 容器环境，未验证

**实测暴露并修复的问题**
- 快照抓取失败裸穿 500 → 状态机新增 `snapshot_failed`（SIM_PENDING 可达，可重试），优雅失败 + 单测
- dev 环境 SQLAlchemy engine 改 NullPool：修复 asyncpg 池化连接跨 event loop 复用（TestClient/多 loop）触发的 "Event loop is closed"
- `DbChangeStore.load_snapshot` 同 object_key 多版本（变更重跑）取最新一条

### v0.5.0 阶段1 · RAG 语料覆盖分析 + RFC 补语料管线（波2）

- **覆盖缺口量化**：513 题按 references 分三类——175 题已被现有 huawei 手册覆盖、**338 题缺语料**、其中 **50 题纯引公开 RFC（NDA-free）**、~160 题引 cisco/h3c/juniper/arista 厂商 URL（需版权/NDA）
- `backend/scripts/ingest_rfcs.py`：从 rfc-editor 拉取 16 个去重 RFC 到 gitignored `doc/rfcs/`，幂等入库（断点续跑）。实测 16 RFC 全量入库 1134 chunks
- **实测决定性结论（波2 核心发现）**：补 RFC 语料几乎不抬 hit_rate——
  ① BM25 oracle：50 纯 RFC 题 **0/50** 能召回预期 RFC（中文 query 与英文 RFC 零词重叠）
  ② 向量召回：NSG-Q-0039（预期 rfc2545）top-10 只有 rfc4271（0.59），rfc2545 不在——query 语义中心是故障/协议名，天然偏向被广泛引用的主规范，而非"具体被引那个 RFC"
  → 根因是**判定要求检索到具体被引用文档，而 query 语义偏向通用协议文档**。这是评测判定口径问题，非单纯语料覆盖可解
- 全量 hit_rate 维持 33.9%（语料内 99.4%）；1200 chunks 语料（huawei+RFC）作为资产保留，供换判定口径/有 GPU 环境复测

### v0.5.0 阶段1 · 评测集复审工具 + 首轮报告（波1）

- `eval/runner/review_dataset.py`：schema 之上叠深度质量扫描（root_causes 数量/概率越界/verify·fix 缺失、perf 缺 bottleneck、title 模板味、占位/乱码残留、疑似重复区分**编号系列变体** vs 真重复、vendor×category 覆盖矩阵），输出分层报告 `eval/reports/question-review-v1.md`；schema 失败或真重复 → 非零退出（CI 门禁）
- 首轮 513 题：schema 0 失败、**0 真重复**、200 对编号系列变体（设计规模梯度，属有意）、106 题 troubleshoot 仅 2 根因
- **106 题 root_causes 补齐到 3**（`scripts/_build_archive/bump_root_causes.py`，一次性）：为各题补真实互补第三候选（低概率 0.05-0.15，避开已有两条），513/513 schema 通过，复审命中 root_causes<3 **109→0**
- CI eval-dataset job 增 quality-review step

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
