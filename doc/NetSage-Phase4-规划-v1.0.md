# NetSage · Phase 4 规划与详细设计 v1.0 — RDMA 专项

> 基线：`NetSage-最终技术方案-v2.0.md`（十四/十九/二十一/五章 5.1）+ Phase 1-3 已完成（34/34 任务，400 单元测试，v0.1.0 已发布）
> 文档版本：v1.0 · 日期：2026-08-24
> 覆盖：Phase 4 第一阶段（M7-M9，v0.2.0）— OpenSM 容器化 + RdmAgent 配置诊断
> 决策（2026-08-24）：RDMA 专项优先 / OpenSM + RdmAgent 配置诊断 / 先写规划文档

---

## 目录

- [一、Phase 4 目标与验收标准](#一phase-4-目标与验收标准)
- [二、Phase 3 基线盘点（Phase 4 起点）](#二phase-3-基线盘点phase-4-起点)
- [三、逐周里程碑（M7-M9）](#三逐周里程碑m7-m9)
- [四、模块详细设计](#四模块详细设计)
  - [4.1 OpenSM 容器化 + GPL 法务隔离](#41-opensm-容器化--gpl-法务隔离)
  - [4.2 RdmAgent — 配置诊断](#42-rdmagent--配置诊断)
  - [4.3 RoCE 模板库扩展](#43-roce-模板库扩展)
  - [4.4 opensm-mcp](#44-opensm-mcp)
- [五、任务拆解与依赖](#五任务拆解与依赖)
- [六、风险与对策](#六风险与对策)
- [七、Phase 4 后续阶段（M10-M12 预览）](#七phase-4-后续阶段m10-m12-预览)

---

## 一、Phase 4 目标与验收标准

### 1.1 目标（v2.0 十四章 Phase 4 + M9 内部 Gate）

**RDMA/IB 全栈支持（差异化护城河）**——主流竞品均无完整 RDMA/IB 全栈管理能力（Cisco Nexus Dashboard 仅有部分无损网络监控，不覆盖 OpenSM/IB 子网管理），NetSage 最大护城河。

本阶段（v0.2.0，M7-M9）聚焦：
- OpenSM 容器化（法务隔离方案落地，v2.0 二十一章）
- RdmAgent 自研（配置诊断：PFC/ECN/DCQCN 调优 + 无损网络设计）
- RoCE 模板库扩展（华为/Cisco/Arista RoCE 配置模板）
- opensm-mcp（OpenSM REST 包装，进程外调用）

### 1.2 验收标准（v2.0 十九章 19.2 M9 Gate）

| # | 验收项 | 指标 | 验证方式 |
|---|---|---|---|
| 1 | OpenSM 容器化 | 容器内 OpenSM 可启动 + IB 子网管理可用 | `docker compose up opensm` + `ibstat` 可查 |
| 2 | GPL 法务隔离 | 三条红线满足（不链接/不分发/不修改） | 法务 memo + wrapper 代码审查 |
| 3 | RdmAgent 配置诊断 | RoCE 诊断 + 调优清单跑通 1 场景 | PFC/ECN/DCQCN 调优输出 |
| 4 | RoCE 模板库 | ≥3 厂商 RoCE 配置模板 | 华为/Cisco/Arista 各 ≥2 |
| 5 | opensm-mcp | 工具可调（ibstat/ibdiscover/perfquery） | MCP 工具调用跑通 |
| 6 | Agent 注册 | 9 Agent（+RdmAgent） | build_runner 验证 |
| 7 | 端到端 | RoCE 丢包场景 → 诊断 → 调优方案 | 1 场景闭环 demo |

### 1.3 不做（M10-M12 范围）

- IB 子网管理（LID/GID/VL/分区表 partition）—— M10+ 需 IB 硬件
- perftest 性能验证 —— 需真实硬件测试床
- WirelessAgent —— M10
- 多租户 + SSO —— M11
- NetAI-Bench 对外发布 —— M12

---

## 二、Phase 3 基线盘点（Phase 4 起点）

| 已有能力 | Phase 4 复用方式 |
|---|---|
| Agent 编排层（8 Agent + SequentialBackend） | 新增 RdmAgent 注册到同一 runner |
| MCP Server ×6 | 新增 opensm-mcp |
| 三道闸引擎 + 审批 | RdmAgent 生成调优配置走三道闸 |
| ConfigRenderer（LLM 提参 → 模板渲染） | RoCE 模板扩展后直接复用 |
| 模板库 80（5 厂商 × 7 协议） | 扩展 roce 协议模板（已占位 VALID_PROTOCOLS） |
| RAG 管线（ingest + 检索） | ingest RoCE/IB 手册 |
| Nautobot App v0.1（NetworkDesign） | v0.2 扩展 RdmaFabric model |
| 评测集 513 题 | 含 40 题 perf 类（RoCE/PFC/ECN）预热 |
| 数据脱敏 + 审计 | RdmAgent 默认接入 |

---

## 三、逐周里程碑（M7-M9）

| 周次 | 里程碑 | 交付物 | 验收 |
|---|---|---|---|
| **W1** | OpenSM 容器化 + 法务 memo | `infra/docker-compose.opensm.yml` + OpenSM 容器 + wrapper 骨架 | `docker compose up` + `ibstat` 可查 |
| **W2** | opensm-mcp + 工具封装 | opensm-mcp（ibstat/ibdiscover/perfquery/ibnetdiscover） | MCP 工具调用跑通 |
| **W3** | RoCE 模板库扩展 | 华为/Cisco/Arista RoCE 模板 ×2（PFC + ECN） | 模板渲染 + 校验通过 |
| **W4** | RdmAgent 配置诊断 | RdmAgent（collect → diagnose → suggest_tuning） | RoCE 丢包场景诊断输出 |
| **W5** | RdmAgent 调优清单 + 设计 | 无损网络设计模板 + DCQCN 调优清单 | 设计 1 RoCE Fabric |
| **W6** | Nautobot RdmaFabric model | App v0.2 扩展 RdmaFabric + 前端 RoCE 页 | 方案持久化 |
| **W7** | RAG RoCE 语料 + 评测 | ingest RoCE 手册 + 40 题 perf 评测 | hit_rate 统计 |
| **W8** | 端到端验收 | RoCE 丢包 → 诊断 → 调优闭环 demo | 7/7 验收达标 |

**关键 gate**：
- W1 末：OpenSM 容器可启动——后续 RdmAgent 依赖。
- W4 末：RdmAgent 诊断跑通 1 场景——M9 Gate 硬指标。
- W8 末：7/7 验收——<5/7 启动降级（仅 OpenSM 容器化 + RdmAgent 调研）。

---

## 四、模块详细设计

### 4.1 OpenSM 容器化 + GPL 法务隔离

#### 法务隔离方案（v2.0 二十一章，三条红线）

```
┌─────────────────────────────────────────────┐
│  NetSage（Apache-2.0，闭源商业版可选）       │
│  ┌─────────────────────────────────────┐  │
│  │  RdmAgent                            │  │
│  │    └─ HTTP POST opensm-mcp /api/ib   │  │
│  └─────────────────────────────────────┘  │
│              │ HTTP（进程外）               │
│              ▼                              │
│  ┌─────────────────────────────────────┐  │
│  │  opensm-mcp（自研 wrapper，Apache）   │  │
│  │    - subprocess.call('opensm ...')   │  │
│  │    - 仅本机调用，不分发 OpenSM 二进制 │  │
│  └─────────────────────────────────────┘  │
│              │ subprocess / CLI            │
│              ▼                              │
│  ┌─────────────────────────────────────┐  │
│  │  OpenSM 原生二进制（GPL-2.0）         │  │
│  │  来自 rdma-core 官方包（容器内）      │  │
│  └─────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

**三条红线**：
1. **不链接**：不 import OpenSM 库（无 C 头文件/.so 动态链接），仅 subprocess/HTTP 调用
2. **不分发**：不发布含 OpenSM 二进制的 Docker 镜像（compose 用官方 rdma-core 镜像，用户本机拉取）
3. **不修改**：用原版 OpenSM + 自研 wrapper，不 fork OpenSM

#### Docker 部署

```yaml
# infra/docker-compose.opensm.yml
services:
  opensm:
    image: ghcr.io/rdma-core/opensm:latest   # 官方镜像，用户本机拉取
    container_name: netsage-opensm
    network_mode: host                        # IB 设备访问需 host 网络
    volumes:
      - /dev/infiniband:/dev/infiniband       # IB 设备直通（有硬件时）
    command: ["opensm", "-B"]                 # 后台运行
    restart: unless-stopped

  opensm-mcp:
    build: ./mcp-servers/opensm-mcp
    container_name: netsage-opensm-mcp
    depends_on: [opensm]
    ports: ["9006:9006"]
    environment:
      OPENSM_HOST: localhost
```

**无 IB 硬件时**：mock 模式（opensm-mcp 返回种子数据），不依赖真实 OpenSM。

#### 法务 memo（需法务出具，v2.0 21.4）

| 项 | 内容 | 状态 |
|---|---|---|
| 法律意见 | 隔离方案是否符合 GPL-2.0 mere aggregation | ⏳ 待法务 |
| 风险等级 | 被误解时的法律风险 | ⏳ 待法务 |
| 替代方案 | 若风险高，走 UFM 商业许可 | ⏳ 待法务 |
| 合规审计 | 每季度审查 wrapper 是否链接/分发 | ⏳ 流程 |

> **工程决策**：法务 memo 待出具期间，先做 wrapper + mock 模式（不触碰 OpenSM 二进制），memo 签字后接入真实 OpenSM。

---

### 4.2 RdmAgent — 配置诊断

#### Agent 定义

```python
# app/agents/rdma_handlers.py
RDMA_AGENT_DEFINITION = {
    "name": "rdm_agent",
    "role": "RDMA/IB 专项 Agent：无损网络设计 + RoCE 调优 + 配置诊断",
    "system_prompt": "你是 RDMA/InfiniBand 专家。诊断 RoCE 丢包/延迟，输出 PFC/ECN/DCQCN 调优方案。",
    "tools": ["opensm.ibstat", "opensm.ibdiscover", "opensm.perfquery",
              "napalm.get_config", "rag.search", "template.render"],
    "transitions": [
        {"from": "collect", "to": "diagnose"},
        {"from": "diagnose", "to": "suggest_tuning"},
        {"from": "suggest_tuning", "to": "END"},
    ],
    "interrupt_points": [],
}
```

#### 节点逻辑

```python
async def rdma_collect(state, tools):
    """采集：IB 状态 + RoCE 计数器 + 配置。"""
    # 1. IB 状态（opensm-mcp，mock 时返回种子）
    ibstat = await tools.call("opensm.ibstat") if tools else {}
    # 2. RoCE 计数器（NAPALM get_config 或 SUZIEQ）
    config = state.get("config", "")
    # 3. 性能计数器（perfquery）
    perf = await tools.call("opensm.perfquery", lid=state.get("lid", 1)) if tools else {}
    return {**state, "ibstat": ibstat, "config": config, "perf": perf}


async def rdma_diagnose(state, tools):
    """诊断：瓶颈定位（PFC/ECN/buffer/MTU）。"""
    engine = RoCEDiagnoseEngine()
    result = engine.analyze(state)
    return {**state, "diagnosis": result}


async def rdma_suggest_tuning(state, tools):
    """调优建议：PFC/ECN/DCQCN 参数 + 配置模板。"""
    diag = state.get("diagnosis", {})
    tuning = {
        "pfc_priority": 3,
        "pfc_headroom": "10KB",
        "ecn_threshold": diag.get("ecn_threshold", "150KB"),
        "dcqcn_params": {"alpha": 0.5, "k_min": 1, "k_max": 100},
        "mtu": 9100,
    }
    # 渲染 RoCE 配置模板
    config = render("huawei_vrp_roce_pfc", tuning) if state.get("vendor") == "huawei" else ""
    return {**state, "tuning": tuning, "config": config}
```

#### RoCEDiagnoseEngine（规则 + 概率，复用 RCA 模式）

```python
# app/agents/rdma_engine.py
class RoCEDiagnoseEngine:
    """RoCE 诊断引擎：PFC/ECN/buffer/MTU 规则库。"""

    RULES = [
        {"id": "pfc_watchdog_disabled", "keywords": ["pfc", "drop", "pause"],
         "cause": "PFC watchdog 未启用导致暂停风暴", "probability": 0.3,
         "verify": "display dcb pfc", "fix": "启用 PFC watchdog"},
        {"id": "ecn_missing", "keywords": ["congestion", "latency"],
         "cause": "ECN 未启用导致拥塞无反馈", "probability": 0.25,
         "verify": "display roce ecn", "fix": "配置 ECN 阈值"},
        {"id": "mtu_mismatch", "keywords": ["fragment", "drop"],
         "cause": "MTU 不一致导致分片丢包", "probability": 0.2,
         "verify": "display interface | include MTU", "fix": "对齐 MTU 9100"},
        # ... 更多规则
    ]

    def analyze(self, state: dict) -> dict:
        symptom = state.get("symptom", "").lower()
        causes = []
        for rule in self.RULES:
            if any(kw in symptom for kw in rule["keywords"]):
                causes.append(rule)
        return {
            "bottleneck": causes[0]["cause"] if causes else "未知",
            "causes": causes[:3],
            "confidence": causes[0]["probability"] if causes else 0,
        }
```

---

### 4.3 RoCE 模板库扩展

#### 目标模板（≥6，3 厂商 × 2 feature）

| 模板 ID | 厂商 | feature | 内容 |
|---|---|---|---|
| huawei_vrp_roce_pfc | huawei | pfc | PFC 优先级流控 + headroom |
| huawei_vrp_roce_ecn | huawei | ecn | ECN 阈值 + DCQCN |
| cisco_iosxe_roce_pfc | cisco | pfc | priority-flow-control |
| cisco_iosxe_roce_ecn | cisco | ecn | ECN + WRED |
| arista_eos_roce_pfc | arista | pfc | pfc priority |
| arista_eos_roce_ecn | arista | ecn | ecn + tx-queue |

#### 模板示例（华为 PFC）

```jinja2
dcb pfc
  priority 3
    headroom {{ pfc_headroom }}
    watchdog enable
    watchdog interval {{ watchdog_interval | default(100) }}
interface 10GE1/0/1
  pfc enable 3
  qos buffer headroom {{ pfc_headroom }} bytes
```

```yaml
# meta.yaml
template_id: huawei_vrp_roce_pfc
vendor: huawei
os: vrp
protocol: roce
feature: pfc
input_schema:
  - { name: pfc_priority, type: int, required: true, enum: [0, 1, 2, 3] }
  - { name: pfc_headroom, type: string, required: true, desc: "headroom 大小" }
  - { name: watchdog_interval, type: int, required: false }
```

---

### 4.4 opensm-mcp

#### 工具集

| 工具 | 输入 | 输出 | 说明 |
|---|---|---|---|
| `ibstat` | — | IB 端口状态 | HCA 端口 state/rate/LID |
| `ibdiscover` | — | 拓扑发现 | 节点 + 链路 |
| `perfquery` | lid | 性能计数器 | 丢包/CRC/延迟 |
| `ibnetdiscover` | — | 网络拓扑 | 完整拓扑图 |
| `sminfo` | — | SM 信息 | 子网管理器状态 |

#### mock 模式（无 IB 硬件时）

```python
# mcp-servers/opensm-mcp/server.py
OPENSM_MOCK = os.getenv("OPENSM_MOCK", "true").lower() == "true"

_MOCK_IBSTAT = {
    "ports": [
        {"port": 1, "state": "Active", "rate": "100 Gb/s", "lid": 1, "guid": "0x..."},
        {"port": 2, "state": "Active", "rate": "100 Gb/s", "lid": 2, "guid": "0x..."},
    ]
}

@mcp.tool()
async def ibstat() -> dict:
    """查询 IB 端口状态。"""
    if OPENSM_MOCK:
        return _MOCK_IBSTAT
    # 真实模式：subprocess.call('ibstat --json')
    return await _run_opensm_cli("ibstat", "--json")
```

---

## 五、任务拆解与依赖

| # | 任务 | 周次 | 依赖 |
|---|---|---|---|
| P4-1 | OpenSM 容器化 + docker-compose | W1 | — |
| P4-2 | opensm-mcp（wrapper + mock） | W2 | P4-1 |
| P4-3 | RoCE 模板库扩展（6 模板） | W3 | — |
| P4-4 | RdmAgent 配置诊断 | W4 | P4-2, P4-3 |
| P4-5 | RoCEDiagnoseEngine + 调优清单 | W4 | P4-4 |
| P4-6 | 无损网络设计模板 | W5 | P4-3 |
| P4-7 | Nautobot RdmaFabric model + 前端 | W6 | P4-4 |
| P4-8 | RAG RoCE 语料 ingest + 评测 | W7 | 手册 |
| P4-9 | 端到端验收 | W8 | 全部 |

**关键阻塞**：
- IB 硬件（P4-1 真实模式需要，mock 模式可绕过）
- RoCE 手册（P4-8，你提供华为/Cisco RoCE 配置指南）

---

## 六、风险与对策

| 风险 | 等级 | 对策 |
|---|---|---|
| OpenSM GPL 法务风险 | 中 | 三条红线 + 法务 memo（memo 待出期间用 mock） |
| 无 IB 硬件无法验证 | 高 | mock 模式先行，真实硬件验证标 TODO |
| RoCE 配置语法厂商差异大 | 中 | 3 厂商各出 2 模板，优先华为（主力） |
| RdmAgent 诊断准确率 | 中 | 规则库 + RAG + 低置信度人工确认 |
| OpenSM 容器化复杂 | 中 | 用官方 rdma-core 镜像，不自建 |

---

## 七、Phase 4 后续阶段（M10-M12 预览）

| 阶段 | 内容 | 版本 |
|---|---|---|
| M10 | IB 子网管理（LID/GID/VL/分区表）+ perftest 集成 | v0.3.0 |
| M10 | WirelessAgent（AP 布放/信道/漫游） | v0.3.0 |
| M11 | 多租户 + SSO（Keycloak/OIDC） | v0.4.0 |
| M12 | NetAI-Bench 对外发布 + 报表/大屏 + v1.0 | v1.0.0 |

---

## 变更日志

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-08-24 | Phase 4 规划首版（RDMA 专项 M7-M9，9 任务拆解） |
