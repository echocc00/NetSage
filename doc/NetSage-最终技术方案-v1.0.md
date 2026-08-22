# NetSage · AI 网络工程师智能平台 — 最终技术方案 v1.0

> 综合来源（去重合并）：hermes-01-survey（开源生态调研）· hermes-02-design（NetAI Copilot 架构）· hermes-03-decision-matrix（集成决策矩阵）· codex-NetSage-Design-v0.1（详细设计）· AI 网络架构师助手（Network Intent Model 等补充点）
> 文档版本：v1.0 · 日期：2026-08-20
> 设计原则：**做整套解决方案，不在实施中降级**；**不重复造轮子，成熟开源组件直接集成（MCP-First）**；**模型策略兼容多厂商，以 DeepSeek 为主、云端 API 优先**；**一切 AI 输出过"仿真+校验+审批"三道闸**。

---

## 目录

- [一、项目定位与北极星指标](#一项目定位与北极星指标)
- [二、整体架构（五层 + 横切）](#二整体架构五层--横切)
- [三、工具底座集成选型（采纳 hermes-03 决策矩阵）](#三工具底座集成选型)
- [四、能力矩阵与成熟度分级](#四能力矩阵与成熟度分级)
- [五、AI Agent 编排层](#五ai-agent-编排层)
- [六、模型与 LLM 网关策略（DeepSeek 为主）](#六模型与-llm-网关策略)
- [七、知识库与 RAG 体系](#七知识库与-rag-体系)
- [八、核心数据模型（Network Intent Model）](#八核心数据模型)
- [九、关键场景工作流](#九关键场景工作流)
- [十、变更下发与审批模型（三道闸）](#十变更下发与审批模型)
- [十一、安全与合规](#十一安全与合规)
- [十二、用户体验与交互](#十二用户体验与交互)
- [十三、部署与运维](#十三部署与运维)
- [十四、研发路线图](#十四研发路线图)
- [十五、风险与缓解](#十五风险与缓解)
- [十六、差异化卖点与开源策略](#十六差异化卖点与开源策略)

---

## 一、项目定位与北极星指标

### 1.1 三句话定位
1. **资深网络工程师的"AI 结对伙伴"**：1 个 NetSage ≈ 1 个随时在线、熟读所有厂商手册、记住每条历史变更的 L4/L5 工程师。
2. **业务驱动的网络架构师**：从业务 SLO（延迟、吞吐、合规、容灾）反推网络拓扑、协议选型、容量与安全策略。
3. **可执行、可审计、可回滚**：输出不是"建议"，而是带命令、带配置、带变更单、在仿真里验证过的"可交付件"。

### 1.2 北极星指标
| 维度 | 指标 | 目标 |
|---|---|---|
| 效率 | P1 故障 MTTR 缩短 | ≤ -50% |
| 效率 | 架构设计/方案输出时间 | ≤ -70% |
| 质量 | 配置变更首次通过率 | ≥ 95% |
| 覆盖 | 主流厂商协议覆盖 | OSPF/BGP/VXLAN-VPN/IPSec/RoCE ≥ 90% 场景 |
| 信任 | 幻觉率（事实性错误） | ≤ 2%，可引用 |
| 闭环 | 故障场景端到端闭环 | ≥ 80% |

---

## 二、整体架构（五层 + 横切）

```
┌──────────────────────────────────────────────────────────────────────┐
│  交互层 (L5)                                                          │
│  Web Console（Monaco 编辑器 + React Flow 拓扑 + 终端面板）            │
│  CLI (nsc) · VS Code Plugin · 飞书/钉钉/WX Bot · ITSM · API Gateway   │
├──────────────────────────────────────────────────────────────────────┤
│  Agent 编排层 (L4) — LangGraph StateGraph                             │
│  路由/规划器 Planner → 6 领域 Agent + ToolRouter（能力→MCP server）    │
│  模式：Plan-and-Execute / ReAct / Multi-Agent Debate / HITL 强制点    │
├──────────────────────────────────────────────────────────────────────┤
│  能力网关 (L3)                                                        │
│  MCP Gateway（统一协议适配所有下游工具）                              │
│  LLM Gateway（LiteLLM：多模型路由 / Token 计费 / Prompt 管理 / 审计） │
│  RAG 服务（向量检索 / 混合召回 / 重排序 / 引用溯源）                  │
├──────────────────────────────────────────────────────────────────────┤
│  工具层 (L2) — 每个工具一个 MCP Server（基于 hermes-03 集成决策）     │
│  Containerlab-MCP · Batfish-MCP · NAPALM/Netmiko/Scrapli-MCP          │
│  NetBox-MCP · Nautobot-MCP · SUZIEQ-MCP · OpenSM-MCP                  │
│  UFM-API(可选) · Prometheus/ELK-MCP · Hubble-MCP · NetEval-Bench      │
├──────────────────────────────────────────────────────────────────────┤
│  数据层 (L1)                                                          │
│  PostgreSQL+pgvector（业务/向量） · Redis（会话/缓存/队列）           │
│  NetBox/Nautobot（Source of Truth） · SUZIEQ Poller（实时状态）       │
│  Batfish Snapshot（配置历史） · MinIO（配置/抓包/审计）               │
├──────────────────────────────────────────────────────────────────────┤
│  基础设施层 (L0)                                                      │
│  多厂商设备 / IB 子网(OpenSM) / K8s+Cilium / 监控系统 / 跳板机(Bastion) │
└──────────────────────────────────────────────────────────────────────┘
横切：IAM(Keycloak) + Audit(Postgres/OpenSearch) + Observability(OTel/Grafana) + Secrets(Vault)
```

### 一次请求旅程（示例：用户问"两台 Spine 间 BGP 邻居反复抖动？"）
1. 交互层 Web Console 接收提问，附带上下文（当前设备/VRF/最近告警）。
2. 规划器识别意图="故障排查"+场景="BGP"+优先级="高" → 拉起 Troubleshooter。
3. Troubleshooter 并行：拉 NETCONF 状态、最近 24h BGP syslog/NetFlow、RAG 检索 BGP 抖动权威条目、拓扑路径图 + 链路光模块/CRC 历史。
4. 反思器生成 3 个候选根因 + 证据链 + 验证步骤。
5. 输出结构化报告 + 跳转 NetBox 设备页 + 一键生成变更工单（进审批流）。

---

## 三、工具底座集成选型

> 原则：**不重复造轮子**。已有成熟开源组件一律直接集成，本产品只做**编排层 + 差异化模块**（RDMA 管理等竞品没有的部分）。License 与成熟度依据 hermes-03（GitHub API 实时数据 2026-08）。

| # | 项目 | License | 决策 | 集成方式 | 优先级 |
|---|---|---|---|---|---:|
| 1 | **Containerlab** | BSD-3 | 🟢 集成 | 仿真底座，CLI+REST+MCP；**安全闸 1** | P0 |
| 2 | **Batfish** | Apache-2.0 | 🟢 集成 | pybatfish API + 自建 MCP；**安全闸 2** | P0 |
| 3 | **NAPALM + Netmiko + Scrapli** | Apache-2.0 | 🟢 集成 | 多厂商统一抽象（厂商翻译器） | P0 |
| 4 | **NetBox** | Apache-2.0 | 🟡 包装 | REST/GraphQL + 官方 NetBox MCP（外部 SSoT） | P0 |
| 5 | **Nautobot** | Apache-2.0 | 🟢 集成 | 核心数据模型 + 插件（差异化 SSoT 底座） | P1 |
| 6 | **SUZIEQ** | Apache-2.0 | 🟢 集成 | python client + poller 嵌入（可观测） | P0 |
| 7 | **OpenSM (rdma-core)** | GPL-2.0 | 🟢 集成 | 容器化 + CLI 包装 + 自研 REST 适配（进程外调用不传染） | P2 |
| 8 | **UFM (NVIDIA)** | 商业闭源 | ⚪ 参考 | 仅做可选 REST API 客户端，不自己部署 | P3 |
| 9 | **LangGraph** | MIT | 🟢 集成 | Agent 编排核心引擎 | P0 |
| 10 | **Awesome Network Automation** | — | ⚪ 参考 | 自家 awesome-list 种子 | — |

**架构决策（关键）**：
- **Source of Truth 抽象**：定义统一的 `SourceOfTruth` 接口，NetBox（包装）与 Nautobot（集成）双适配器并行——覆盖 100% 客户场景。
- **Nautobot 定位**：本产品差异化核心模块（RDMA Fabric Manager 等）写成 Nautobot App，形成"网络 AI 平台 + 自带 SSoT"一体化方案。
- **MCP-First**：每个底座工具一个独立 MCP Server，统一走 mcp-hub 网关，对接 Claude/DeepSeek/Cursor 等客户端即用。
- **每个变更必须先过**：Containerlab 仿真 → Batfish 静态校验 → 人工审批，三步缺一不可（见第十节）。

---

## 四、能力矩阵与成熟度分级

按"使用场景 × 协议栈"，每格标注成熟度 L1-L5（L1 问答 / L2 解释 / L3 生成 / L4 验证 / L5 自治）。
**L5 自治仅允许**"写权限明确开通且经过实验室验证的场景"；默认 L3/L4 + 人工审批。

| 场景 \ 协议 | OSPF | BGP | VXLAN/EVPN | MPLS VPN | IPsec/SSL | 无线 | RoCE/IB | 安全 |
|---|---|---|---|---|---|---|---|---|
| 架构设计 | L4 | L4 | L4 | L3 | L4 | L3 | L3 | L4 |
| 配置生成 | L4 | L4 | L4 | L3 | L4 | L3 | L3 | L4 |
| 配置审计 | L4 | L4 | L4 | L3 | L4 | L3 | L3 | L5 |
| 故障排查 | L4 | L4 | L4 | L3 | L4 | L3 | L3 | L4 |
| 容量规划 | L3 | L3 | L3 | L3 | L3 | L3 | L3 | L3 |
| 性能优化 | L3 | L3 | L3 | L3 | L3 | L3 | L4 | L3 |
| 知识问答 | L5 | L5 | L5 | L4 | L5 | L4 | L4 | L5 |

---

## 五、AI Agent 编排层

### 5.1 专家 Agent 矩阵
| Agent | 输入 | 输出 | 工具（来自底座） |
|---|---|---|---|
| **Planner/Architect** | 业务需求/容量/SLO/合规 | HLD + 拓扑图 + 协议选型 + 风险清单 | topology_planner、impact_analysis、capacity_planner |
| **ConfigEngineer** | 设计意图+设备型号+版本 | 完整配置 diff + 变更说明 + 回滚 | NAPALM driver、Jinja2 模板库、YANG 模型、命令生成器 |
| **Validator** | 生成的配置 | 语法/可达性/ACL/路由断言结果 | **Batfish**、**Containerlab** |
| **Troubleshooter** | 现象/日志/指标/配置 | 根因假设 + 证据链 + 验证 + 修复 | **SUZIEQ**、NAPALM、日志/NetFlow、rca_engine、path_analyzer |
| **PerfAnalyst** | 流量/计数器/丢包/延迟 | 瓶颈定位 + 优化 + 容量预测 | Prometheus、RoCE 计数器、Telemetry |
| **SecurityAuditor** | 配置+拓扑+威胁模型 | 漏洞清单 + 加固方案 + 合规对照 | Batfish ACL 分析、CVE 库、策略检查、attack_surface_mapper |
| **RdmAgent**（差异化） | IB/RoCE 需求/性能问题 | IB/无损网络设计 + 调优 + 诊断 | **OpenSM**、rdma-core、perftest、ibdiagnet |
| **WirelessAgent** | 无线需求 | AP 布放/信道/漫游域/安全策略 | 厂商 WLC API、CAPWAP 分析 |
| **DeployAgent** | 获批变更 | 顺序下发 + checkpoint + 回滚 | NAPALM commit/rollback、Ansible |
| **DocWriter** | 工程产出物 | HLD/LLD/Runbook/Postmortem/SOP | 文档模板、图表生成 |

### 5.2 编排模式
- **Plan-and-Execute**：复杂任务先出计划 → 用户批准 → 执行（规划器构建有向无环图 DAG 调度子 Agent）。
- **ReAct**：轻量排查循环（Thought → Action → Observation）。
- **Multi-Agent Debate**：架构/配置/安全三方对同一方案互评。
- **HITL 强制点**：所有"写"操作（配置下发、变更单提交）用 `interrupt_before` 节点强制人工确认。

### 5.3 网络意图模型（NIM）——跨 Agent 共享上下文
用统一的结构化模型承载所有 Agent 的读写，避免多 Agent 间信息丢失：
```yaml
intent:
  business_requirements:      # 业务 SLO：延迟/吞吐/容灾/合规
    - service: ai_training
      scale: 1024_gpu
      bandwidth_per_node: 200Gbps
      latency_requirement: <2us   # (注：IB 场景 us 级；RoCE 以太网 ×场景 5μs 级)
  topology:
    underlay: { type: spine_leaf, spines: 4, leaves: 32, protocol: ebgp }
    overlay:  { type: evpn_vxlan, vni_range: [10000, 20000] }
    rdma:     { plane: ib, topology: fat_tree, tier: 2 }
  addressing:
    underlay_loopbacks: 10.255.0.0/24
    vtep_loopbacks: 10.255.1.0/24
    ib_subnet: 172.16.0.0/16
  routing:    { underlay_asn_range: [65000,65100], overlay_evpn: true }
  security:   { zero_trust: true, microsegmentation: per_rack }
  devices:
    - { role: spine, model: nvidia_spectrum_x, count: 4 }
    - { role: leaf,  model: nvidia_spectrum_x, count: 32 }
```
所有 Agent 读写同一模型，最终输出为模型实例化 + 配置包。

---

## 六、模型与 LLM 网关策略

> **设计决策（用户确认）**：模型策略兼容各厂商，**以 DeepSeek 为主，接入方式优先云端 API**（走 LLM 云 API，不部署本地推理集群）。

- **LLM 网关**：LiteLLM 做统一多模型路由——DeepSeek-V3/R1（默认主模型）、Claude Sonnet/Opus（复杂推理/代码）、通义千问 Qwen（中文/国产化场景）、GPT 系（兜底）。按任务难度/成本自动路由，支持灰度与降级。
- **主路径（默认）**：DeepSeek 云端 API（deepseek 官方 / OpenRouter 等聚合入口）。
- **北向兼容**：由于走 LiteLLM 统一网关，底层换任何厂商（DeepSeek/Qwen/Claude/GPT）**对上层 Agent 完全透明**，满足"兼容各厂商"要求。
- **Embedding**：bge-m3（多语言，RAG 检索）— 可本地部署，不涉云。
- **成本控制**：难度路由（简单问答走小模型省钱）+ 缓存 + 小模型兜底。
- **数据合规**：所有发给 LLM 的内容经**脱敏过滤器**（IP/MAC/ASN/密码/主机名哈希替换），展示时还原；高敏感场景可切换已私有化部署的兼容模型（网关同一接口，方案保留该能力但非 Phase 1 必备）。

---

## 七、知识库与 RAG 体系

### 7.1 知识分层
| 层级 | 内容 | 来源 | 检索权重 |
|---|---|---|---|
| L1 官方手册 | 华为 VRP / Cisco IOS-XE/NX-OS / H3C Comware / Juniper Junos / Arista EOS / Nokia SR OS / Mellanox Onyx | 厂商官网/产品包 | ★★★★★ |
| L2 标准协议 | RFC 2328/4271/7348/8365/9136·IEEE 802.11ax/be·IBTA RoCE v1/v2·IBTA Vol1/2 | IETF/IEEE/IBTA | ★★★★★ |
| L3 最佳实践 | Cisco CVD / Juniper VDX / NVIDIA OFED / RF 草案 / Tech Field Day | 厂商白皮书/社区 | ★★★★ |
| L4 内部资产 | HLD/LLD/变更单/Postmortem/巡检报告/模板库（NIM 实例） | 内部 Git | ★★★★★ |
| L5 实时状态 | running-config / NetBox/Nautobot 拓扑 / 实时日志指标 | 内部系统 | ★★★★ |

### 7.2 检索策略
- **混合检索**：向量语义（bge-m3）+ BM25（精确命令/错误码）+ 知识图谱关系。
- **查询改写**：网络同义词表（OSPF Neighbor↔Adjacency↔Peer）。
- **多路召回**：原始 query + 改写 + 假设答案（HyDE）。
- **重排序**：Cross-Encoder / bge-reranker。
- **引用溯源**：每段事实带回来源 URL + 版本 + 抓取时间（满足"信息溯源"偏好）。
- **反馈闭环**：点赞/点踩 → 调 chunk 权重 + 微调集。

### 7.3 文档分块
- 手册按"特性→场景→命令→注意事项"四级，每块 ≤1500 token，保留章节路径元数据。
- Postmortem 按"症状→排查→根因→修复→教训"分块、标签化。
- 拓扑/协议/互联图走多模态嵌入（CLIP+OCR），支持"画一张这个"指令。

### 7.4 知识保鲜
- 厂商 Release Notes 每周 cron 抓取 → diff → 告警"3 个特性已废弃"。
- 内部 Postmortem 入库前 PII 脱敏 + 摘要。
- 模板库 GitOps 管理，PR 审核入库。

---

## 八、核心数据模型

PostgreSQL（业务 + pgvector 向量）核心表：
- `devices` / `projects` / `network_intents`（NIM JSON）
- `config_templates`（Jinja2 模板 + 版本）
- `change_requests` / `change_steps` / `approvals`
- `config_snapshots`（变更前自动快照，回滚用）
- `audit_logs`（不可篡改）
- `diagnosis_cases`（排障案例 → RAG）
- `baseline_rules`（安全基线）
- `credentials`（Vault 引用，不落明文）

Source of Truth（资产/拓扑/IPAM/VRF）：NetBox（包装）与 Nautobot（集成）双适配器，通过统一 `SourceOfTruth` 接口接入。

---

## 九、关键场景工作流（6 条精选）

### 9.1 业务驱动架构设计（含 RDMA）
输入"西安新建 1000 节点 AI 训练集群，跨域北京，RDMA 延迟 <5μs" → Planner 提取 SLO → RAG 检索 RoCEv2+PFC/ECN/DCQCN+跨域 DCI → impact_analysis 评估承载力 → 输出 HLD（Spine-Leaf 100G/400G、AI 独立 Pod、Underlay OSPF/ECMP + Overlay EVPN-VXLAN + 跨域 BGP-EVPN、PFC+ECN+DCQCN 调参、微分段+MACsec）→ ConfigEngineer 生成模板 → SecurityAuditor 合规 → DocWriter 整合。

### 9.2 MPLS L3VPN 跨域配置生成
CE1-PE1-P-CE2(Option A) → 识别厂商(华为 NE40E)+版本(VRP8.x) → RAG 命中手册章节 → 生成 PE/CE 配置（MPLS LDP / sham-link / MP-BGP vpnv4 / VRF+RD / OSPF 双向重发布）→ SecAudit(MD5/TTL/控制面保护) → Containerlab 4 节点仿真验证邻居/路由/连通性。

### 9.3 OSPF Neighbor 反复震荡
抓两端 Hello/Dead/Pacing/Network type/Auth + 端口 CRC/光模块 + 丢包/stp/QoS → 排序候选根因（网络类型不一致→MD5 mismatch→MTU 不一致 DD 重传→CRC 异常）→ 每假设给"验证一步 + 修复命令" → 一键生成含回滚的变更单。

### 9.4 VXLAN EVPN Type-2/3 路由不通
查 BGP EVPN 邻居/VNI/本地 ARP/远端 MAC → query_flows 抓 VXLAN 封装路径 → RAG 命中 Type-2 通告抑制/anycast-gateway 冲突/ARP flood suppress → 修复建议。

### 9.5 RoCE v2 性能不达标（差异化）
P99 18μs > SLO 5μs → PerfAnalyst 抓 PFC/ECN 计数器、CNP 包、DCQCN 状态、队列长度 → 识别 PFC storm / ECN 阈值不合理 / LLR/DCQCN 未启 → 调优清单（PFC 优先级映射、ECN 水线、buffer 分配、QoS 模板）→ 仿真验证。

### 9.6 变更前安全审计
解析 200 台设备 BGP 配置 diff → 检查 peer 鉴权(MD5/AH)、GTSM、最大前缀数、路由黑洞、管理面加固、VRF 隔离 → 输出风险清单 + 阻断式门禁（Critical 阻断 / Warning 警示）。

---

## 十、变更下发与审批模型（三道闸）

```
AI 产出变更
  └─ ① Containerlab 仿真验证（安全闸 1）——必过
  └─ ② Batfish 静态校验（安全闸 2：reachability/ACL/routing 断言）——必过
  └─ ③ 人工逐条审批（工程师确认 diff、回滚预案、变更窗口、影响范围）——必过
        ↓ 获批
  DeployAgent 按顺序下发（NAPALM commit + checkpoint 校验）
        ↓ 失败 → 自动回滚到审批时保存的配置快照（rollback）
全程审计日志（谁/何时/什么命令/结果）落 PostgreSQL，不可篡改
```

- **强制门禁**：读通道宽松、写通道严格。写命令只允许经模板引擎渲染 + 审批通过的对象，**不允许 LLM 裸发任意命令**（"IR 只作翻译不作裸推理"原则）。
- **权限分级**：viewer / operator（可读）/ engineer（可拟变更+发起审批）/ admin（审批+回滚）。
- **配置快照**：每次变更前自动拉全量 running-config 存快照，支持一键回滚，校验成功后保留 7 天。

---

## 十一、安全与合规

### 11.1 核心原则
- **最小权限**：默认只读，敏感操作走审批。
- **零信任**：API + mTLS + OIDC。
- **全审计**：所有动作带 user/device/command/before-after/timestamp。
- **数据脱敏**：密码、SNMP community、真实 IP/ASN 写入日志前自动 mask（LLM 前置过滤器）。
- **数据不出域**：核心 topology/config 保留本地，外部 LLM 仅传最少必要片段。

### 11.2 合规对照
- 等保 2.0：三权分立（系统管理员/安全管理员/审计管理员）。
- 数据安全法/个保法：操作日志保留 ≥ 6 个月。
- 行业：金融"两地三中心"、运营商"关基"。

---

## 十二、用户体验与交互

三种形态：**Web Console**（Monaco 编辑器 + React Flow 拓扑 + 终端面板 + 侧栏 AI，日常）；**CLI nsc**（`nsc ask "为什么 OSPF 邻居起不来"`、`nsc run simulate cml-topo.yaml`，应急）；**IM Bot**（告警自动@，@NetSage 直接排障）。
- 可解释 > 不可解释：结论带"为什么"。
- 可干预 > 自治：所有动作可暂停/修改/跳过。
- 可回放 > 一次性：会话可重放，便于复盘与培训。
- 结果可移植：导出 Markdown/Word/Confluence。
- 培训场景：陪练模式（AI 扮演现场，学员排查）、新协议速通（VXLAN/EVPN 4 周路径 + 检验题）。

---

## 十三、部署与运维

- **部署形态**：云端 LLM API + 本地平台，混合模型；高敏感场景可切换私有化兼容模型（网关同一接口）。
- **关键 SLO**：API P99 <2s（问答）/ <8s（生成类）；可用性 99.9%；推理成功率 >99.5%。
- **观测**：指标（调用量/token/工具失败率/Agent 步骤/反馈）+ 结构化 JSON 日志（trace_id 全链路）+ OTel/Grafana。
- **自愈**：工具调用失败 → 自动重试 → 切备用工具 → 失败后人工介入。

---

## 十四、研发路线图

> **不降级原则**：四阶段全量交付整套解决方案，计划里程碑不因时间压缩削减能力；集成项（hermes-03）按接口直接接入，不重复造轮子。

### Phase 1（M1-M2）— 最小闭环 + 核心底座集成
- 交付：Containerlab + Batfish + NAPALM/Netmiko/Scrapli + LangGraph 集成；Planner/ConfigGen/Validator 三个 Agent。
- 知识库：DeepSeek 网关 + 基础 RAG（L1 手册 + L4 内部案例）。
- 能力：知识问答 + 单厂商配置生成 + 配置审计。
- Web Console MVP（Chat + 设备管理 + 简易拓扑）。
- 里程碑：DAG 完整跑通"需求→配置生成→Batfish 校验→仿真→报告"。

### Phase 2（M3-M4）— 多厂商 + 数据闭环
- 交付：NetBox（包装）+ SUZIEQ（poller）集成；ConfigGen/Validator/Deploy/Observer 四 Agent。
- 多厂商：H3C/Juniper/Arista；拓扑可视化完善。
- 排障链路：SUZIEQ 实时观察 + 排障 Agent + 日志/NetFlow 分析 + 案例 RAG。
- 里程碑：端到端"配置生成→验证→推送→监控"闭环。

### Phase 3（M5-M6）— Nautobot 深度集成 + 排障/安全
- 交付：Nautobot（SourceOfTruth 双适配器）+ 自研 Nautobot App。
- TroubleshootAgent + ComplianceAgent + SecurityAuditor；Batfish ACL 分析。
- 三道闸全量落地 + 审批流 + 快照回滚 + 完整 RBAC/审计。
- 里程碑：BGP session 故障自动诊断→修复→验证全自动闭环（含审批）。

### Phase 4（M7-M12）— RDMA + 无线 + 生产化
- 交付：OpenSM 容器化 + 自研 **RdmAgent**（差异化护城河）+ WirelessAgent。
- 自研 benchmark:参照 NetAgentBench/CTBench 思路做 NetAI-Bench 作为基线与营销素材。
- 多租户 + SSO + 完整审计 + 报表/大屏。
- 里程碑：可对外演示的 v1.0，支持生产测试环境辅助真实变更。

---

## 十五、风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| LLM 幻觉导致错误配置 | **高** | 强制三道闸（仿真+Batfish+审批），禁止自由生成裸命令 |
| 厂商配置覆盖不全 | 高 | NAPALM 多厂商抽象 + Containerlab 仿真 + 用户共建模板 |
| 内部敏感数据外泄 | 高 | 前置脱敏过滤器 + LLM 网关 + 权限分级 + DLP 审计 |
| 工具执行不可控 | 中 | 沙箱 + 审批 + 灰度 + 自动回滚快照 |
| 检索召回不足 | 中 | 混合检索 + 重排序 + 反馈闭环 + 持续抓取 |
| LangGraph API 频繁变更 | 高 | 封装 `agent_runtime` 适配层，便于升级 |
| Batfish Java 后端资源占用 | 中 | 容器隔离（1vCPU/2GB 起步） |
| Containerlab 需 Docker socket | 中 | 提供"远程 containerlab"模式（SSH 跳板机） |
| OpenSM GPL 边界 | 低 | 仅进程外 REST/CLI 调用不传染，留法务 memo |
| NetBox/Nautobot 并行维护 | 中 | 抽象 `SourceOfTruth` 接口，两套适配器 |
| 模型成本失控 | 中 | 难度路由 + 缓存 + 小模型兜底 |
| 团队能力（懂网络+懂 AI）稀缺 | 中 | 网络专家深度结对 + AI 工程师从基础协议学起 |

---

## 十六、差异化卖点与开源策略

### 差异化卖点（相对 Forward Networks / Selector AI / Cisco / 华为 NCE）
1. **RDMA/InfiniBand 全栈支持（OpenSM+perftest）**——竞品完全缺失，最大护城河。
2. **MCP-First 架构**——工程师在 Claude/DeepSeek/Cursor 里即用，零学习曲线。
3. **多 Agent 协同（LangGraph 状态机）**，非单一 chat。
4. **仿真内置**——所有变更必过 Containerlab + Batfish 双验证。
5. **Model-agnostic LLM 网关**——DeepSeek/Qwen/Claude/GPT 随时切换，国产化就绪。
6. **自带 SSoT（Nautobot App）**——开源底座透明，避免 vendor lock-in。

### 开源与社区策略
- 核心编排 + Agent + UI 闭源做商业化；**MCP server + Containerlab 拓扑模板开源**做社区。
- 同步启动 `awesome-network-ai` 索引 + NetAI-Bench 数据集。
- 首发 demo：RDMA 集群 AI 优化（差异化）+ 数据中心 VXLAN fabric 规划（刚需）。

---

## 附录：与核心岗位能力对齐
资深网络工程师（你）的角色不是被替代而是被放大：
- **你定义"对"**：建评测集、审核模板、标注 Postmortem。
- **你承担"险"**：自治动作最终批准人、高风险场景兜底。
- **你驱动"迭代"**：每月从实战抽新场景喂给 NetSage，让它越用越懂你的网络。

> 目标：让 **1 个专家 = 1 个团队**。
