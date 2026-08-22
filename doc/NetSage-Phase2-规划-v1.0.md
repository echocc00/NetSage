# NetSage · Phase 2 规划与详细设计 v1.0

> 基线：`NetSage-最终技术方案-v2.0.md` + `NetSage-开发计划与详细设计-v1.0.md`
> 前置：Phase 1 已完成（10/10 任务，127 单元测试 + 4 集成测试全过，真实 MiniMax LLM 已接入，containerlab 2 节点 BGP 邻居 Established，前端登录闭环）
> 文档版本：v1.0 · 日期：2026-08-22
> 覆盖：Phase 2（M3-M4，8 周）目标、逐周里程碑、模块详细设计、依赖、风险

---

## 目录

- [一、Phase 2 目标与验收标准](#一phase-2-目标与验收标准)
- [二、Phase 1 基线盘点（Phase 2 起点）](#二phase-1-基线盘点phase-2-起点)
- [三、逐周里程碑（M3-M4）](#三逐周里程碑m3-m4)
- [四、模块详细设计](#四模块详细设计)
  - [4.1 SourceOfTruth 抽象 + NetBox 集成](#41-sourceoftruth-抽象--netbox-集成)
  - [4.2 SUZIEQ Poller + ObserverAgent](#42-suzieq-poller--observeragent)
  - [4.3 多厂商扩展（H3C/Juniper/Arista）](#43-多厂商扩展h3cjuniperarista)
  - [4.4 DeployAgent + 真实下发闭环](#44-deployagent--真实下发闭环)
  - [4.5 Troubleshooter + RCA 引擎](#45-troubleshooter--rca-引擎)
  - [4.6 RAG 扩展（500 题 + hit_rate 优化）](#46-rag-扩展500-题--hit_rate-优化)
  - [4.7 拓扑可视化完善](#47-拓扑可视化完善)
- [五、任务拆解与依赖](#五任务拆解与依赖)
- [六、风险与对策](#六风险与对策)

---

## 一、Phase 2 目标与验收标准

### 1.1 目标（v2.0 第十四章）

**多厂商 + 数据闭环**：从 Phase 1 的"单厂商配置生成 + 仿真验证"扩展到"多厂商 + 真实设备数据 + 排障闭环 + 监控反馈"。

### 1.2 验收标准（v2.0 十九章 19.2）

| # | 验收项 | 指标 | 验证方式 |
|---|---|---|---|
| 1 | 多厂商覆盖 | ≥3 厂商（华为 + Cisco + H3C/Juniper/Arista 之一） | 每厂商 ≥1 协议模板 + NAPALM driver 跑通 commit/rollback |
| 2 | 排障闭环 | ≥3 场景端到端（症状→根因→修复→验证） | BGP/OSPF/VXLAN 各 1 场景 |
| 3 | NetBox 集成 | SourceOfTruth 双适配器（NetBox 包装）跑通 | 设备/IPAM/拓扑读取 + 变更回写 |
| 4 | SUZIEQ 集成 | poller 采集 + 标准化状态查询 | ≥10 设备定时 poll，Assert 框架跑通 |
| 5 | RAG 扩展 | 评测集扩至 500 题，hit_rate ≥ 85% | 跑评测集统计召回率 |
| 6 | DeployAgent | 真实下发 + checkpoint + 自动回滚 | 仿真环境端到端变更闭环 |
| 7 | 端到端闭环 | 配置生成→验证→推送→监控 | 3 场景全链路 demo |

### 1.3 不做（Phase 3/4 范围）

- Nautobot 深度集成 + 自研 App（Phase 3）
- SecurityAuditor + Batfish ACL 全厂商（Phase 3）
- OpenSM/RdmAgent/WirelessAgent（Phase 4）
- 多租户 + SSO（Phase 4）

---

## 二、Phase 1 基线盘点（Phase 2 起点）

| 已有能力 | Phase 2 复用方式 |
|---|---|
| Agent 编排层（agent_runtime + 6×7 意图分类 + Planner/ConfigEngineer/Validator） | 新增 Troubleshooter/Deploy/Observer 三个 Agent 注册到同一 runner |
| MCP Server ×3（containerlab/batfish/napalm） | 新增 netbox-mcp / suzieq-mcp 两个 server |
| 设备接入层（napalm/netmiko/scrapli 三 adapter + 工厂） | 扩展 NAPALM driver 覆盖 H3C/Juniper/Arista |
| 三道闸引擎 + 变更审批（影响范围自动推演） | DeployAgent 接入三道闸的 deploy 阶段 |
| ConfigRenderer（LLM 提参 → 模板渲染） | 多厂商模板库扩展后直接复用 |
| 模板库骨架（华为 BGP/OSPF + loader + meta 校验） | 扩展至 ~80 模板（6 厂商 × 5 协议） |
| RAG 管线（ingest + 混合检索 + 重排） | 扩展语料（华为手册 + 案例）+ 500 题 |
| containerlab 仿真环境（WSL + 2 节点 BGP） | 排障场景用仿真验证修复 |
| 数据脱敏 Layer1/3 + 审计哈希链 | 新增模块默认接入 |
| React 前端（5 页面 + 登录 + React Flow） | 拓扑页接 NetBox 真实拓扑 |

---

## 三、逐周里程碑（M3-M4）

| 周次 | 里程碑 | 主负责 | 交付物 | 验收 |
|---|---|---|---|---|
| **W1** | SourceOfTruth 接口 + NetBoxAdapter | 后端 | `SourceOfTruth` Protocol + `NetBoxAdapter`（REST/GraphQL） + netbox-mcp | 设备/IPAM/拓扑读取跑通 |
| **W2** | NetBox 变更回写 + 多厂商启动 | 后端 + AI | 变更单回写 NetBox + H3C/Juniper NAPALM driver 验证 | 变更后 NetBox 状态更新 |
| **W3** | SUZIEQ Poller 嵌入 | 后端 + SRE | suzieq-mcp + poller 定时采集 + 标准化状态表 | ≥10 设备 poll 跑通 |
| **W4** | ObserverAgent + Assert 框架 | AI | ObserverAgent（定时 poll → 趋势分析）+ SUZIEQ Assert | 状态异常自动告警 |
| **W5** | DeployAgent + 真实下发 | 后端 | DeployAgent（顺序下发 + checkpoint + 回滚）接三道闸 | 仿真环境端到端变更闭环 |
| **W6** | Troubleshooter + RCA 引擎 | AI + Tech Lead | Troubleshooter Agent + RCA 引擎（多源关联 + 根因排序） | BGP 抖动场景根因排序 |
| **W7** | 排障闭环 3 场景 + 拓扑可视化 | AI + 前端 | BGP/OSPF/VXLAN 排障场景 + React Flow 接 NetBox | 3 场景端到端 + 拓扑页真实数据 |
| **W8** | RAG 500 题 + 端到端验收 | 全员 | 评测集扩至 500 题 + hit_rate ≥85% + 闭环 demo | 7/7 验收达标 |

**关键 gate**：
- W2 末：NetBox 集成必须跑通——后续 Deploy/排障都依赖 SourceOfTruth。
- W4 末：SUZIEQ poller 必须出数据——ObserverAgent 和排障依赖实时状态。
- W6 末：RCA 引擎跑通 BGP 场景——W7 排障闭环的前置。
- W8 末：7/7 验收——<5/7 启动 Phase 2.5 补救。

---

## 四、模块详细设计

### 4.1 SourceOfTruth 抽象 + NetBox 集成

#### 设计（v2.0 三章 + 开发计划十八章 18.1）

```python
# app/access/source_of_truth.py
class SourceOfTruth(Protocol):
    """网络资产/拓扑/IPAM 单一事实源（v2.0 三章）。"""
    # 读
    async def get_device(self, device_id: int) -> Device: ...
    async def list_devices(self, filter: dict) -> list[Device]: ...
    async def get_topology(self, scope: str) -> Topology: ...  # 节点 + 链路
    async def get_ipam(self, prefix: str) -> IPAM: ...  # IP 地址管理
    async def get_vrfs(self, project: str) -> list[VRF]: ...
    # 写（变更后回写）
    async def write_change_record(self, record: ChangeRecord) -> None: ...
    async def update_device_status(self, device_id: int, status: str) -> None: ...
```

#### NetBoxAdapter 实现

```python
# app/access/netbox_adapter.py
class NetBoxAdapter(SourceOfTruth):
    """NetBox REST/GraphQL 包装（v2.0 hermes-03 🟡 包装决策）。"""

    def __init__(self, base_url: str, token: str):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Token {token}"},
            timeout=30.0,
        )

    async def get_device(self, device_id: int) -> Device:
        r = await self.client.get(f"/api/dcim/devices/{device_id}/")
        r.raise_for_status()
        return self._map_device(r.json())

    async def get_topology(self, scope: str) -> Topology:
        # GraphQL 一次拉全拓扑（NetBox v4 GraphQL）
        query = """
        query($scope: String!) {
          devices(site: $scope) { id name device_type {model} primary_ip4 {address} ... }
          cables { a_terminations b_terminations }
        }
        """
        r = await self.client.post("/graphql/", json={"query": query, "variables": {"scope": scope}})
        return self._map_topology(r.json())
```

#### netbox-mcp（2-3 人天，官方 MCP 可用）

| 工具 | 输入 | 输出 |
|---|---|---|
| `get_device` | device_id | Device |
| `list_devices` | filter（site/role/vendor） | list[Device] |
| `get_topology` | scope（site） | Topology（节点+链路） |
| `get_ipam` | prefix | IPAM |
| `write_change_record` | record | ok |

#### 部署

- NetBox Docker 容器加入 `infra/docker-compose.dev.yml`（`netboxcommunity/netbox:latest`）。
- 锁 NetBox v4 API（v3 不兼容，v2.0 hermes-03 风险）。
- 初始数据：从 Phase 1 仿真设备导入 5-10 台测试设备。

#### 前端拓扑页对接

- `GET /api/v1/topology?scope=<site>` → 后端调 NetBoxAdapter → 返回 React Flow 节点/边格式。
- 替换 Phase 1 的静态 `INITIAL_NODES`。

---

### 4.2 SUZIEQ Poller + ObserverAgent

#### 设计（v2.0 三章 + 开发计划十八章 18.2）

```python
# app/observability/suzieq_service.py
class SuzieqService:
    """SUZIEQ poller 嵌入 + 标准化状态查询（v2.0 hermes-03 🟢 集成）。"""

    def __init__(self, config_path: str):
        self.config = config_path  # suzieq 配置（设备清单 + 凭证）

    async def poll_once(self) -> dict:
        """触发一次全量采集，返回标准化状态表。"""
        # suzieq poller 走 subprocess（sync 库，to_thread 包装）
        return await asyncio.to_thread(self._poll_sync)

    async def query(self, table: str, filter: dict) -> list[dict]:
        """查询标准化状态表（bgp/ospf/interface/routes/...）。"""
        # suzieq analyze 走 SQL-like
        ...

    async def assert_state(self, assertion: dict) -> AssertResult:
        """SUZIEQ Assert 框架：配置 vs 状态断言。"""
        ...
```

#### suzieq-mcp（6-8 人天）

| 工具 | 输入 | 输出 |
|---|---|---|
| `poll_once` | — | 采集结果摘要 |
| `query_state` | table, filter | 标准化状态行 |
| `assert_state` | assertion（如"所有 BGP 邻居 Established"） | pass/fail + 证据 |
| `get_path` | src, dst | 端到端路径（path tracing） |

#### ObserverAgent

```python
# app/agents/definitions/observer.yaml
name: observer
role: "网络可观测性 Agent：定时 poll + 趋势分析 + 异常告警"
tools: [suzieq.poll_once, suzieq.query_state, suzieq.assert_state, prometheus.query]
transitions:
  - {from: poll, to: analyze}
  - {from: analyze, to: alert_or_done}
  - {from: alert_or_done, to: END}
```

- **定时任务**：Celery beat 每 5 分钟 poll 全网 → 标准化数据 → LLM 趋势分析（可选）→ 异常告警。
- **凭证轮换**：SUZIEQ 需要 SSH 凭证访问设备，走 Vault 注入（v2.0 17.4 隐藏成本）。
- **资源**：千台设备需 4-8 vCPU 专属（v2.0 17.4），Phase 2 仿真环境 10 台够。

#### 部署

- SUZIEQ Docker 容器加入 `docker-compose.dev.yml`。
- 配置文件指向 Phase 1 的 containerlab 仿真设备（cXRd/FRR）。

---

### 4.3 多厂商扩展（H3C/Juniper/Arista）

#### NAPALM driver 扩展（v2.0 开发计划十八章 18.3）

Phase 1 的 `DRIVER_MAP` 已含 7 厂商映射，Phase 2 补 driver 实测：

| 厂商 | NAPALM driver | Phase 2 验证项 | 模板数目标 |
|---|---|---|---|
| 华为 VRP | `huawei`（napalm-huawei） | get_facts + commit + rollback | ~20（Phase 1 已 2） |
| Cisco IOS-XE | `iosxe` | 同上 | ~20 |
| H3C Comware | `h3c`（napalm-h3c） | 同上 | ~15 |
| Juniper Junos | `junos` | 同上 | ~15 |
| Arista EOS | `eos` | 同上 | ~10 |

#### 模板库扩展（v2.0 二十七章）

- 目标 ~80 模板（6 厂商 × 5 协议 × 1-2 feature）。
- 每厂商至少：OSPF area、BGP peering、VLAN、静态路由、接口配置。
- **你需要做**：每厂商 5-10 个模板的参数规则（我搭框架 + meta 校验，你填 j2 内容 + review）。
- CI 矩阵测试：每厂商 × 每版本（v2.0 hermes-03 风险）。

#### 厂商适配层验证

```python
# tests/integration/test_multi_vendor.py
@pytest.mark.parametrize("vendor", ["huawei", "cisco_iosxe", "h3c_comware", "juniper_junos", "arista_eos"])
async def test_commit_rollback_per_vendor(vendor):
    """每厂商跑通 load_merge + compare + commit + rollback（仿真或实机）。"""
    adapter = AdapterFactory().for_write(DeviceTarget(vendor=vendor, ...))
    await adapter.apply_candidate(target, config)
    # 验证配置生效
    facts = await adapter.get_facts(target)
    ...
```

---

### 4.4 DeployAgent + 真实下发闭环

#### 设计（v2.0 十章 + 开发计划十三章）

Phase 1 的三道闸引擎已实现 `deploy` 阶段，Phase 2 补 **DeployAgent** 编排 + checkpoint 校验：

```python
# app/agents/definitions/deploy.yaml
name: deploy
role: "变更下发 Agent：顺序下发 + checkpoint 校验 + 失败回滚"
tools: [napalm.apply_candidate, napalm.get_config, snapshot.capture, snapshot.rollback]
transitions:
  - {from: pre_check, to: deploy_loop}
  - {from: deploy_loop, to: verify}
  - {from: verify, to: END}       # 成功
  - {from: verify, to: rollback}  # 失败
  - {from: rollback, to: END}
interrupt_points: [pre_check]  # 下发前最后人审确认
```

#### DeployAgent 节点逻辑

```python
# app/agents/handlers.py
async def deploy_pre_check(state):
    """下发前校验：审批状态 + 快照完整性 + 影响范围确认。"""
    assert state["change_status"] == "approved"
    assert state["snapshots"]  # 变更前快照已抓
    return state

async def deploy_loop(state):
    """顺序下发多设备，每台 checkpoint 校验。"""
    for device in state["devices"]:
        try:
            diff = await adapter.apply_candidate(device, state["configs"][device["name"]])
            await verify_device(device, diff)  # checkpoint：配置生效 + 邻居/路由正常
            state["deployed"].append(device["name"])
        except Exception as e:
            state["failed"] = {"device": device["name"], "error": str(e)}
            return state  # 跳到 rollback
    return state

async def deploy_rollback(state):
    """失败自动回滚到快照。"""
    for device_name in state["deployed"]:
        await snapshot_service.rollback(device_name, ...)
    state["rollback_status"] = "completed"
```

#### 闭环验收

- 仿真环境：3 台设备顺序下发 BGP 配置 → checkpoint（邻居 Established）→ 1 台故意失败 → 自动回滚已下发的 2 台 → 全网恢复。
- 审计日志全程记录（哈希链）。

---

### 4.5 Troubleshooter + RCA 引擎

#### 设计（v2.0 五章 + codex 设计 RCA 引擎）

```python
# app/agents/definitions/troubleshooter.yaml
name: troubleshooter
role: "故障排查 Agent：多源数据关联 + 根因排序 + 验证步骤"
tools:
  - suzieq.query_state       # 实时状态
  - suzieq.assert_state      # 状态断言
  - napalm.get_config        # 配置
  - rag.search               # 历史案例 + 手册
  - batfish.assert_reachability  # 路径验证
transitions:
  - {from: collect, to: analyze}
  - {from: analyze, to: rank_causes}
  - {from: rank_causes, to: suggest_fixes}
  - {from: suggest_fixes, to: END}
```

#### RCA 引擎核心逻辑（v2.0 codex 设计 §4.3）

```python
# app/agents/rca_engine.py
class RCAEngine:
    """根因分析：多源关联 + 因果图推理。"""

    async def analyze(self, symptom: str, context: dict) -> list[RootCause]:
        # 1. 拓扑定位（受影响设备/链路）
        affected = await self._locate(symptom, context)
        # 2. 时间窗口变更事件关联
        changes = await self._recent_changes(affected, window="24h")
        # 3. 流量基线偏离检测
        anomalies = await self._detect_anomalies(affected)
        # 4. 协议状态机异常（BGP flap / OSPF LSA 风暴）
        proto_issues = await self._check_protocol_state(affected)
        # 5. RAG 检索同类历史案例
        cases = await self._search_cases(symptom)
        # 6. 因果图推理 + 概率排序
        return self._rank_causes(
            changes, anomalies, proto_issues, cases
        )
```

#### 3 排障场景（v2.0 19.2 验收 2）

| 场景 | 症状 | 根因候选 | 验证 |
|---|---|---|---|
| BGP 邻居抖动 | `BGP-5-ADJCHG: Neighbor Down` | hello 计时器不一致 / MTU / CRC / 路由策略 | SUZIEQ bgp 表 + 接口 CRC |
| OSPF 邻居震荡 | `OSPF-5-ADJCHG: Hello expired` | 网络类型不一致 / MD5 mismatch / MTU / CRC | SUZIEQ ospf 表 + 接口 |
| VXLAN EVPN Type-2 不通 | 跨 Leaf 通信异常 | BGP EVPN 邻居 / VNI / anycast-gateway / ARP suppress | SUZIEQ bgp evpn + 路由表 |

- 每场景：症状输入 → RCA 排序 3 候选根因 + 证据链 + 验证命令 + 修复方案 → 仿真验证修复有效。
- **你需要做**：每场景出 5-10 道评测题（Phase 1 评测集 schema 已就绪），我跑 RCA + 评分。

---

### 4.6 RAG 扩展（500 题 + hit_rate 优化）

#### 语料扩展

| 层级 | Phase 1 | Phase 2 目标 |
|---|---|---|
| L1 官方手册 | 0（骨架已就绪） | 华为 VRP 8.x 全量 + Cisco IOS-XE 17.x 全量 |
| L4 内部资产 | 0 | 50 条 Postmortem（脱敏后） |
| L5 实时状态 | 0 | SUZIEQ 标准化状态表（实时） |

- **你需要提供**：华为 VRP 8.x 手册原文（PDF/网页导出，放 `doc/vendor-manuals/huawei/`）。
- ingest 管线已就绪（Phase 1 `rag/ingest.py`），分块按"特性→场景→命令→注意事项"四级。

#### 评测集扩展

| 项 | Phase 1 | Phase 2 |
|---|---|---|
| 题目数 | 4 | 500 |
| 覆盖 | troubleshoot/config/audit 各 1 | 全 6 类 × 7 协议 |
| 来源 | 人工构造 | 内部 Postmortem 50 + 厂商 KB 300 + 人工构造 150 |

- **你需要做**：出题（schema 校验器已就绪，`eval/runner/schema.py`）。
- 我做：LLM-as-judge 评分管线 + 月度盲测。

#### hit_rate 优化（≥85%）

- 查询改写：网络同义词表扩展（OSPF Neighbor↔Adjacency↔Peer 等）。
- HyDE 多路召回调参。
- 重排序模型：bge-reranker-v2-m3。
- 反馈闭环：点赞/点踩 → 调 chunk 权重。

---

### 4.7 拓扑可视化完善

#### 前端

- React Flow 接 `/api/v1/topology?scope=<site>` → NetBox 真实拓扑。
- 节点点击：侧栏显示设备 facts + 配置 + SUZIEQ 实时状态。
- 链路点击：显示接口利用率 + CRC 错误（SUZIEQ interface 表）。
- 高亮：故障设备/链路红色（排障时）。

#### 后端

- `GET /api/v1/topology` → NetBoxAdapter.get_topology → React Flow 格式。
- `GET /api/v1/devices/{id}/state` → SUZIEQ 实时状态 + NAPALM facts 合并。

---

## 五、任务拆解与依赖

| # | 任务 | 周次 | 依赖 | 负责人 |
|---|---|---|---|---|
| P2-1 | SourceOfTruth 接口 + NetBoxAdapter | W1 | — | 后端 |
| P2-2 | netbox-mcp + Docker 部署 | W1 | P2-1 | 后端 |
| P2-3 | NetBox 变更回写 + 前端拓扑对接 | W2 | P2-1 | 后端+前端 |
| P2-4 | H3C/Juniper NAPALM driver 验证 | W2 | — | 后端 |
| P2-5 | 多厂商模板库扩展（~80） | W2-W4 | P2-4 | AI+Tech Lead |
| P2-6 | suzieq-mcp + Poller 嵌入 | W3 | — | 后端+SRE |
| P2-7 | ObserverAgent + Assert 框架 | W4 | P2-6 | AI |
| P2-8 | DeployAgent + checkpoint | W5 | P2-1 | 后端 |
| P2-9 | RCA 引擎 | W6 | P2-6 | AI+Tech Lead |
| P2-10 | Troubleshooter Agent | W6 | P2-9 | AI |
| P2-11 | 排障闭环 3 场景 | W7 | P2-10 | AI+Tech Lead |
| P2-12 | 拓扑可视化完善 | W7 | P2-3 | 前端 |
| P2-13 | RAG 500 题 + hit_rate 优化 | W7-W8 | 华为手册 | AI+产品 |
| P2-14 | 端到端验收 | W8 | 全部 | 全员 |

**可并行**：P2-5（模板）/ P2-6（SUZIEQ）/ P2-13（RAG）三条线独立推进。

**关键阻塞**：
- 华为手册（P2-13 前置，你提供）
- 评测题出题（P2-13 + P2-11，你出题）
- 模板内容（P2-5，你填参数 + review）

---

## 六、风险与对策

| 风险 | 等级 | 对策 |
|---|---|---|
| NetBox v4 API 与 v3 不兼容 | 高 | 锁 v4，Adapter 内做版本探测 |
| SUZIEQ 凭证轮换复杂 | 中 | Vault 注入 + 定期 rotate（v2.0 17.4） |
| NAPALM H3C driver 不成熟 | 中 | netmiko 兜底（AdapterFactory 已支持降级） |
| RCA 引擎根因准确率不足 | 高 | 知识图谱 + 历史 Case + 多源交叉验证；低置信度要求人工确认 |
| 多厂商模板工作量大（~80） | 中 | 优先 Top 3 厂商 + 用户共建（v2.0 风险表） |
| SUZIEQ poller 资源占用 | 中 | 仿真环境 10 台够；生产规格见 v2.0 17.4 |
| containerlab 前缀通告问题（Phase 1 backlog） | 低 | Phase 2 排障场景用 SR Linux 镜像替代 FRR |

---

## 附录：Phase 2 与 Phase 1 的代码复用清单

| Phase 1 模块 | Phase 2 复用方式 | 是否需改动 |
|---|---|---|
| `agent_runtime` + `SequentialBackend` | 新增 3 Agent 注册 | 否（零改） |
| `ToolRegistry` + `MCPClient` | 新增 2 MCP server 注册 | 否 |
| `AdapterFactory` | 扩展 driver map | 小改 |
| `GatePipeline` | DeployAgent 接入 deploy 阶段 | 小改 |
| `ConfigRenderer` | 多厂商模板扩展后直接用 | 否 |
| `template_loader` | 模板目录扩展 | 否 |
| `rag/` 管线 | 语料扩展 + 调参 | 小改 |
| 脱敏 + 审计 | 新模块默认接入 | 否 |
| React 前端 | 拓扑页接真实数据 | 小改 |

**复用率约 70%**——Phase 2 主要是新增模块（NetBox/SUZIEQ/RCA/Deploy），底层基础设施全部复用。

---

## 变更日志

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v1.0 | 2026-08-22 | Phase 2 规划首版（8 周 + 7 模块详细设计 + 14 任务拆解） | 架构组 |

---

> Phase 2 规划完结。与 Phase 1 开发计划配套使用。下一步：确认规划后启动 W1（SourceOfTruth + NetBox）。
