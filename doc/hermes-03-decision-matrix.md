# 10 个候选项目决策矩阵

> 数据来源：GitHub REST API（实时抓取 2026-08-19） + Awesome Network Automation 索引 + 网络工程社区共识。  
> 决策维度：**集成深度**（直接复用代码/二进制 / 仅做 API 包装 / 仅作思路参考 / 不集成）+ **集成成本**（人月）+ **风险**。  
> 标注规则：
> - 🟢 **集成**：fork 或直接 pip install，深度耦合到您产品代码
> - 🟡 **包装**：通过 MCP/API 网关调用，本产品仅做编排层
> - ⚪ **参考**：仅借鉴架构/思路，不引入依赖
> - 🔴 **不集成**：有更优替代或与产品定位冲突

---

## 一、决策矩阵（速览表）

| # | 项目 | � | License | 决策 | 集成方式 | 优先级 |
|---|---|---:|---|---|---|---:|
| 1 | Containerlab | 2,746 | BSD-3 | 🟢 **集成** | 仿真底座，CLI 调用 + MCP | **P0** |
| 2 | Batfish | 1,454 | Apache-2.0 | 🟢 **集成** | pybatfish API + MCP | **P0** |
| 3 | NAPALM | 2,487 | Apache-2.0 | 🟢 **集成** | get_facts/config_replace + MCP | **P0** |
| 4 | NetBox | 21,329 | Apache-2.0 | 🟡 **包装** | REST/GraphQL + NetBox MCP | **P0** |
| 5 | Nautobot | 1,577 | Apache-2.0 | 🟢 **集成** | GraphQL + 插件开发 + MCP | **P1** |
| 6 | SUZIEQ | 894 | Apache-2.0 | 🟢 **集成** | suzieq python client + poller 嵌入 | **P0** |
| 7 | OpenSM | (kernel 子模块) | GPL-2.0 | 🟢 **集成** | 容器化 + CLI 包装 | **P2** |
| 8 | UFM (Mellanox/NVIDIA) | **不开源** | 商业 | ⚪ **参考** | 仅做 REST API 客户端（非必需） | P3 |
| 9 | LangGraph | 40,029 | MIT | 🟢 **集成** | 直接 pip 安装作为核心引擎 | **P0** |
| 10 | Awesome Network Automation | 2,826 | NOASSERTION | ⚪ **参考** | 不入代码库，作为项目自身 awesome 列表的种子 | — |

---

## 二、每个项目详细评估

### 1. Containerlab 🟢 P0 — 仿真底座

| 项 | 评估 |
|---|---|
| 仓库 | `srl-labs/containerlab` |
| 数据 | 2,746⭐ · 488 fork · BSD-3 · 最近 release v0.78.2 (2026-08-13) · 持续活跃 |
| 集成方式 | **通过 CLI 调用 + REST API + 官方 MCP server（已存在或即将发布）** |
| 为何集成 | • 覆盖 15+ NOS（Nokia SR Linux / Arista cEOS / Cisco XRd / SONiC / Juniper cRPD / FRR / VyOS / FD.io VPP）<br>• 声明式 YAML，AI 直接生成/修改拓扑最自然<br>• BSD-3 license 可商用<br>• 是您 5 层架构 L2 工具层核心 |
| 风险 | • BSD-3 要求保留版权（轻量义务，可接受）<br>• 仿真镜像需 Docker，部署到生产环境需考虑资源隔离 |
| **集成点** | • `TopologyAgent`：根据用户需求生成 containerlab YAML → `clab deploy` → 跑通后回写 NetBox<br>• 每个变更前先在 Containerlab 里跑一遍（**安全闸 1**） |

### 2. Batfish 🟢 P0 — 配置验证核心

| 项 | 评估 |
|---|---|
| 仓库 | `batfish/batfish` (Pybatfish 是 Python 客户端) |
| 数据 | 1,454⭐ · 285 fork · Apache-2.0 · 2026-08-17 仍活跃 |
| 集成方式 | **pybatfish Python API + 自建 MCP server 包装** |
| 为何集成 | • 业界唯一开源的"配置静态分析+意图验证"工具<br>• 支持 Cisco / Arista / Juniper / Palo Alto / Fortinet / FRR 等多厂商<br>• 学术圈 NetConfEval 等 benchmark 都用它做 ground truth<br>• Apache-2.0 可商用 |
| 风险 | • 服务端用 Java，需常驻 JVM（资源开销 1-2GB RAM）<br>• 部分新厂商支持滞后（需持续跟进） |
| **集成点** | • `ValidatorAgent`：每次生成配置后调 Batfish 跑 reachability / ACL / routing 断言<br>• **安全闸 2**：变更必须通过 Batfish 才能进入下一阶段 |

### 3. NAPALM 🟢 P0 — 多厂商抽象层

| 项 | 评估 |
|---|---|
| 仓库 | `napalm-automation/napalm` |
| 数据 | 2,487⭐ · 593 fork · Apache-2.0 · 活跃 |
| 集成方式 | **作为 Python 库直接依赖 + MCP server 包装** |
| 为何集成 | • 多厂商统一 API（get_facts / get_config / load_merge_candidate / commit / discard_config）<br>• 支持 Cisco IOS/IOS-XE/XR/NX-OS、Arista EOS、Juniper Junos、Nokia SR OS、Huawei VRP 等<br>• 与 Ansible 的 napalm-ios / napalm-junos 等模块共用一套数据模型<br>• 是 ConfigGen / DeployAgent 的"厂商语言翻译器" |
| 风险 | • 各厂商驱动版本兼容性问题（需锁版本）<br>• 部分小众厂商支持差 |
| **集成点** | • `ConfigGenAgent`：根据厂商和型号选择 NAPALM driver，生成 merge candidate<br>• `DeployAgent`：调 load_merge_candidate → diff 给人审 → commit / rollback |

### 4. NetBox 🟡 P0 — 包装而非集成

| 项 | 评估 |
|---|---|
| 仓库 | `netbox-community/netbox` |
| 数据 | 21,329⭐ · 3,104 fork · Apache-2.0 · 行业事实标准 |
| 集成方式 | **仅做 API 客户端 + NetBox MCP server**（已有官方 MCP） |
| 为何不深度集成 | • Django + PostgreSQL 重型应用，独立部署运维<br>• 您不应 fork NetBox，而应把它作为"外部 source of truth"，本产品只读写 |
| 风险 | • NetBox v4 API 与 v3 不兼容，需锁版本<br>• 插件生态混乱（NetBox Labs 商业化策略有变） |
| **集成点** | • 读：IPAM / 设备清单 / VLAN / VRF / 电路 / 线缆<br>• 写：变更工单 / 审计日志 / 配置快照<br>• **L1 数据底座核心**，但部署边界清晰 |

### 5. Nautobot 🟢 P1 — 比 NetBox 更适合自动化（用户判断）

| 项 | 评估 |
|---|---|
| 仓库 | `nautobot/nautobot` |
| 数据 | 1,577⭐ · 415 fork · Apache-2.0 · NetworkToCode 维护 |
| 集成方式 | **作为核心数据模型 + 大量自定义插件开发**（比 NetBox 更彻底的二次开发） |
| **核心优势对比 NetBox** | ① **插件架构更开放**：NetBox 插件受限于 Django/DRF 模板，Nautobot 是真正的可扩展 App<br>② **GraphQL 一等公民**：NetBox GraphQL 是第三方插件，Nautobot 原生支持<br>③ **Job 系统**：内置 Python Job 框架（类似 Ansible AWX 但更轻），可直接跑自定义运维任务<br>④ **计算字段与关系**：更适合做"动态派生数据"（如 BGP session 状态、链路利用率）<br>⑤ **从 NetBox 分叉**：2019 年 NetworkToCode 内部因可扩展性需求分叉，**专门面向自动化** |
| 风险 | • 社区比 NetBox 小（1.6k vs 21k），文档/插件少<br>• 部分 NetBox 生态插件无法直接迁移<br>• 与 NetBox 二选一时客户常倾向于 NetBox（更熟悉） |
| **建议** | • **P1 优先级，但战略上要重点投入**：作为您的"差异化底座"——本产品核心模块写成 Nautobot App，能形成"网络 AI 平台 + 自带 SSoT"的一体化方案，竞争对手难复制<br>• v1.0 同时支持 NetBox（包装）和 Nautobot（集成）两个 source of truth |
| **集成点** | • `RdmAgent`：IB 子网拓扑用 Nautobot App 实现（开源项目里第一个）<br>• `TopologyAgent`：fabric 拓扑存 Nautobot<br>• 自定义 Job 跑配置生成+验证流水线 |

### 6. SUZIEQ 🟢 P0 — 实时可观测性

| 项 | 评估 |
|---|---|
| 仓库 | `netenglabs/suzieq` |
| 数据 | 894⭐ · 118 fork · Apache-2.0 · 2026-08-16 仍活跃 |
| 集成方式 | **suzieq Python client + Poller 框架嵌入** |
| 为何集成 | • 多厂商标准化输出（同样的 `bgp` 表适用于 Cisco/Juniper/Nokia）<br>• 内置 Assert 框架做"配置 vs 状态"断言<br>• Poller 支持 syslog / SSH / NETCONF / gNMI 多采集方式 |
| 风险 | • 架构是客户端+服务端模式，服务端需独立部署<br>• 部分高级功能（path tracing）需要 gNMI，部署成本高 |
| **集成点** | • `ObserverAgent`：定时 poll 全网 → 标准化数据 → 喂给 LLM 做趋势分析<br>• `TroubleshootAgent`：故障时调 suzieq assert 看哪个表的状态变了<br>• 比 SUZIEQ 自己的 web UI 强在"自然语言查询" |

### 7. OpenSM 🟢 P2 — IB 子网管理器

| 项 | 评估 |
|---|---|
| 仓库 | `linux-rdma/rdma-core`（OpenSM 是其子模块） |
| License | **GPL-2.0**（与 rdma-core 主体同 license） |
| 集成方式 | **容器化（jumanjihouse/docker-opensm 有现成镜像 6⭐）+ CLI 包装 + 自研 REST API 适配层** |
| 为何集成 | • 您 ② 号需求（InfiniBand）核心<br>• 开源唯一可用方案（UFM 是商业闭源）<br>• GPL-2.0 仅要求"修改 OpenSM 本身要开源"，您通过 REST 包装不传染 |
| 风险 | • GPL-2.0 比 Apache/BSD 严，需法务确认<br>• OpenSM 只管 SM 平面，不做 telemetry/告警，需自己补 |
| **集成点** | • `RdmAgent`：调用 OpenSM CLI（`opensm` / `iblinkinfo` / `ibnetdiscover`）<br>• 把 IB 拓扑同步到 Nautobot/NetBox<br>• **您的差异化护城河**——竞品都不做 |

### 8. UFM (Mellanox/NVIDIA) � P3 — 仅做 API 客户端

| 项 | 评估 |
|---|---|
| 仓库 | **不在 GitHub 开源**——只有 stackhpc 社区维护的 docker 镜像 (3⭐) 和 ansible role (3⭐) |
| License | **商业闭源**（UFM Enterprise / UFM Telemetry / UFM Cyber / UFM SDT） |
| 决策 | **不集成**——但**保留可选客户端** |
| 原因 | • 客户若已有 UFM Enterprise，可通过其 REST API 接进来（您产品支持"外挂 IB 管理平台"模式）<br>• 不应自己部署 UFM（license 成本高）<br>• OpenSM 已覆盖 SMB 场景 |
| 风险 | 低 |
| **集成点** | • 可选：当用户填了 UFM endpoint 时，`RdmAgent` 自动切换到 UFM REST API 模式 |

### 9. LangGraph 🟢 P0 — Agent 编排核心

| 项 | 评估 |
|---|---|
| 仓库 | `langchain-ai/langgraph` |
| 数据 | 40,029⭐ · 6,741 fork · MIT · 最新 sdk==0.4.3 (2026-08-19) |
| 集成方式 | **作为产品核心依赖，直接 pip install** |
| 为何集成 | • 状态机范式最适合"长任务 + 人审 + 可中断"的网络运维场景<br>• 与 LangChain 生态打通（VectorStore / Tool / Retriever）<br>• MIT license 最自由<br>• LangChain 40k⭐ + LangGraph 同源，生态最稳 |
| 风险 | • LangChain 抽象层迭代快（v0.x → v1.0 重大重构），需锁版本<br>• 复杂工作流调试门槛高 |
| **集成点** | • 所有 Agent 都用 LangGraph StateGraph 定义<br>• `PlannerAgent`：根据用户输入构建有向无环图（DAG），调度子 Agent<br>• `Human-in-the-loop`：通过 `interrupt_before` 节点强制审批 |

### 10. Awesome Network Automation ⚪ 参考 — 工具索引

| 项 | 评估 |
|---|---|
| 仓库 | `networktocode/awesome-network-automation` |
| 数据 | 2,826⭐ · 498 fork · NOASSERTION license（CC BY-SA 类） |
| 决策 | **不集成**——本身是 markdown 索引，不入代码 |
| 价值 | • 您的项目自身也要出一个 awesome-list（`awesome-network-ai`），这个仓库是范本<br>• 持续维护中，可订阅 issue 跟踪网络自动化趋势 |
| 建议 | • 项目 v1.0 发布后，在 GitHub 出 `your-org/awesome-network-ai` 索引<br>• 营销素材之一 |

---

## 三、集成路线图（与原 02-design.md 对齐）

### Phase 1（M0-M1.5）— 最小可演示闭环
- � Containerlab + Batfish + NAPALM + LangGraph
- 一个 ConfigGen Agent demo：「为上海-广州专线新建 BGP peering」

### Phase 2（M1.5-M3）— 多厂商 + 数据闭环
- 🟡 NetBox（API + MCP）
- � SUZIEQ（嵌入式 poller）
- ConfigGen / Validator / Deploy / Observer 四个 Agent

### Phase 3（M3-M4.5）— Nautobot 深度集成
- 🟢 Nautobot 作为可选 source of truth（同时支持 NetBox）
- 自研 Nautobot App：RDMA Fabric Manager（**差异化亮点**）
- TroubleshootAgent + ComplianceAgent

### Phase 4（M4.5-M6）— RDMA + 无线
- � OpenSM 容器化 + 自研 RdmAgent
- ⚪ UFM 客户端（可选）
- WirelessAgent + 完整 Web Console

---

## 四、关键决策点（需要您确认）

### 决策 A：NetBox vs Nautobot 主选哪个？
- **选 NetBox**：用户基数大、文档全、易招人、易交付
- **选 Nautobot**：插件生态深、自动化原生、差异化强、但客户认知度低
- **两个都支持**：开发成本+30%，但覆盖 100% 客户场景（**推荐**）

### 决策 B：GPL-2.0 (rdma-core/OpenSM) 法务风险？
- 您的产品通过 REST/CLI 包装调用 OpenSM → **不传染 GPL**（业界共识：进程边界 + API 调用不构成 derivative work）
- 仍建议法务出一份 memo，留档

### 决策 C：是否启动 `awesome-network-ai` 索引项目？
- 立项成本：低（一个 PR 起步）
- 收益：长期 SEO + 社区品牌
- **建议**：v1.0 发布同期启动

---

## 五、风险与缓解（针对本批项目）

| 风险 | 等级 | 缓解 |
|---|---|---|
| Batfish Java 后端资源占用 | 中 | 用容器隔离，1 vCPU / 2GB RAM 起步 |
| Containerlab 需 Docker socket | 中 | 提供"远程 containerlab"模式（SSH 到跳板机） |
| NAPALM 厂商驱动版本冲突 | 低 | 锁版本 + CI 矩阵测试 |
| LangGraph API 频繁变更 | 高 | 封装一层 `agent_runtime` 适配层，便于升级 |
| OpenSM GPL 边界 | 低 | 仅进程外调用，留法务 memo |
| Nautobot 与 NetBox 并行维护 | 中 | 抽象 `SourceOfTruth` 接口，两套适配器 |

---

决策矩阵完成。请确认：
1. **NetBox + Nautobot 并行支持** 是否同意？
2. **OpenSM GPL 包装方案** 是否需要先法务确认？
3. 下一步直接出 **Phase 1 代码骨架**（Containerlab-MCP + Batfish-MCP + ConfigGen Agent），还是先做更深的某项调研？
