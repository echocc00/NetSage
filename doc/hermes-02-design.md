# "NetAI Copilot" 企业级方案设计

> 目标：基于调研结果，构建 **企业级网络 AI 平台**，覆盖规划/仿真/配置/排障/合规/安全全链路，能力域全覆盖（OSPF/BGP/VXLAN/VPN/无线 + RDMA/RoCE）。  
> 定位对标：Forward Networks + Cisco Nexus Dashboard + Selector AI + 部分 Itential 的能力并集。  
> 部署：私有化为主，云端 SaaS 可选。  
> LLM：云端 API（Claude Sonnet/Opus、GPT-5、Gemini 路由式调用）。

---

## 一、整体架构（5 层 + 1 横切）

```
┌──────────────────────────────────────────────────────────────────┐
│  L5  应用层  Web Console / VSCode-Cursor 插件 / Slack-Bot / API   │
├──────────────────────────────────────────────────────────────────┤
│  L4  Agent 编排层  LangGraph / CrewAI / AutoGen 多 Agent 协同     │
│     • Planner Agent（拆解用户任务）                               │
│     • ConfigGen Agent / Troubleshoot Agent / RDMA Agent 等        │
│     • ToolRouter（按能力路由到 MCP server）                       │
├──────────────────────────────────────────────────────────────────┤
│  L3  能力网关  MCP Gateway + LLM Gateway                          │
│     • MCP: 统一协议适配所有下游工具                                │
│     • LLM: 多模型路由 / Token 计费 / Prompt 模板管理 / 审计       │
│     • RAG: 向量库 + 文档/配置/RFC 检索                           │
├──────────────────────────────────────────────────────────────────┤
│  L2  工具层（每个工具一个 MCP Server，全部基于调研选型）          │
│     Containerlab-MCP / Batfish-MCP / NetBox-MCP / Ansible-MCP    │
│     SUZIEQ-MCP / NAPALM-MCP / Scrapli-MCP / FRR-MCP              │
│     rdma-core-MCP / OpenSM-MCP / Hubble-MCP / NetEval-Bench      │
├──────────────────────────────────────────────────────────────────┤
│  L1  数据底座  PostgreSQL+TimescaleDB / Neo4j / S3 / Vector DB    │
│     • NetBox（资产/意图）                                         │
│     • SUZIEQ poller（实时状态）                                   │
│     • Batfish snapshot（配置历史）                                │
│     • Vector DB（设备手册/RFC/内部 runbook）                      │
├──────────────────────────────────────────────────────────────────┤
│  L0  网络基础设施  多厂商设备 / IB 子网 / K8s+Cilium / 监控系统  │
└──────────────────────────────────────────────────────────────────┘

横切：IAM (Keycloak/Authentik) + Audit + Observability (OTel) + Secrets (Vault)
```

---

## 二、能力域 → Agent → 工具映射

| 能力域 | 核心 Agent | 工具（来自调研） |
|---|---|---|
| **规划 / 仿真** | Planner / TopologyAgent | Containerlab + FRR/SONiC + OVS |
| **配置生成** | ConfigGenAgent | NAPALM + NTC Templates + Genieparser |
| **配置验证** | ValidatorAgent | Batfish（pybatfish API） |
| **意图翻译** | IntentAgent | OpenConfig YANG + 自定义 DSL |
| **推送执行** | DeployAgent | Ansible + Nornir + NAPALM commit/rollback |
| **实时可观测** | ObserverAgent | SUZIEQ + Cilium/Hubble + Prometheus |
| **故障排障** | TroubleshootAgent（SADE 思路） | SUZIEQ + scrapli + Batfish diff |
| **安全合规** | ComplianceAgent | Batfish ACL 分析 + 自定义策略库 |
| **RDMA/IB 运维** | RdmAgent | rdma-core + opensm + perftest + NIXT（待移植） |
| **无线** | WirelessAgent | 厂商 WLC API + CAPWAP 分析 |

---

## 三、核心技术选型矩阵

| 类别 | 选型 | 理由 |
|---|---|---|
| **LLM** | Claude Sonnet/Opus + GPT-5 路由 | 网络运维推理任务首选 Claude；GPT-5 兜底 |
| **Agent 框架** | LangGraph（首选） | 状态机可控、可中断、可人审 |
| **MCP 实现** | 官方 mcp-python-sdk | 每个工具一个独立 MCP server |
| **LLM Gateway** | LiteLLM + 自研 token 计费 | 多模型路由、灰度、降级 |
| **RAG** | Qdrant / pgvector | 文档/配置/RFC/历史工单 |
| **Workflow 持久化** | Postgres + Temporal | 长时间任务可恢复 |
| **任务队列** | Redis + Celery / Arq | 工具调用异步化 |
| **前端** | React + TipTap（编辑器）+ React Flow（拓扑） | 拓扑可视化必备 |
| **容器化** | Docker + Kubernetes（k3s 自带） | 仿真环境用 k3s |
| **可观测** | OTel + Grafana + Loki + Prometheus | 自监控 |
| **审计** | Postgres + OpenSearch | 所有变更、prompt、工具调用全留痕 |

---

## 四、核心数据流（3 条主线）

### 1. 配置生成闭环（最核心、最易出 demo）

```
用户："为上海-广州专线新建一条 BGP peering，AS 私有号 65001"
   ↓ PlannerAgent 拆解
   ↓ ConfigGenAgent 调 NAPALM-MCP 读设备能力
   ↓ ValidatorAgent 调 Batfish-MCP 跑 reachability/ACL 断言
   ↓ DeployAgent 调 Ansible-MCP 推配置（先推 Containerlab 仿真）
   ↓ ObserverAgent 调 SUZIEQ-MCP 确认 BGP session up
   ↓ 反馈给用户 + 写 NetBox 审计
```

### 2. 故障排障闭环（SADE 思路）

```
告警：CE1-CE2 BGP session down
   ↓ TroubleshootAgent 症状分类（"邻居 down"）
   ↓ 调 scrapli-MCP 抓设备 show bgp summary/log
   ↓ 调 Batfish-MCP 对比 last-good vs current 配置
   ↓ 根因推断：MD5 密码不一致
   ↓ 生成修复方案 + 影响评估 → 人工审批 → Ansible-MCP 推修复
```

### 3. RDMA 运维闭环（差异化亮点）

```
告警：HPC 集群 GPU 通信延迟 P99 > 8us（阈值 5us）
   ↓ RdmAgent 调 rdma-core-MCP 抓 PFC/ECN 计数器
   ↓ 调 perftest-MCP 跑 ib_write_bw 压测隔离问题链路
   ↓ 调 opensm-MCP 看子网拓扑 + 丢包
   ↓ 根因：某 leaf 交换机 PFC 阈值配置错误
   ↓ 调 Ansible-MCP 修复 → 重新跑 perftest 验证
```

---

## 五、MVP 路径（4 阶段、约 6 个月）

### Phase 1（M0-M1.5）：单工具 MCP + 单 Agent demo
- 交付：Containerlab-MCP + Batfish-MCP + 一个 ConfigGen Agent（Claude）
- demo 场景：用户输入需求 → 仿真拉起 → 生成配置 → Batfish 验证 → 报告
- 投入：1 后端 + 1 AI 工程师 + 1 网络顾问

### Phase 2（M1.5-M3）：闭环 + 多厂商
- 加上：NetBox-MCP + Ansible-MCP + SUZIEQ-MCP
- 加上：ConfigGen / Validator / Deploy / Observer 四个 Agent
- demo 场景：端到端"配置生成→验证→推送→监控"
- 投入：+1 前端 + 1 测试

### Phase 3（M3-M4.5）：排障 + 安全合规
- 加上：scrapli-MCP + Batfish ACL 分析 + Troubleshoot Agent
- demo 场景：BGP session 故障自动诊断修复

### Phase 4（M4.5-M6）：RDMA + 无线 + 多租户
- 加上：rdma-core-MCP + OpenSM-MCP + Wireless Agent
- 加上：IAM 多租户 + 审计 + 完整 Web Console
- 目标：可对外演示的 v1.0

---

## 六、风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| LLM 生成错误配置直接推到生产 | **致命** | 强制三道闸：Containerlab 仿真 → Batfish 验证 → 人审；任何跳过都不允许 |
| LLM 上下文窗口不够吃全网状态 | 高 | SUZIEQ 标准化输出 + 按需检索；引入 state summary 而非全量 |
| 厂商命令私有/不全公开 | 中 | NAPALM 多厂商抽象 + 兜底 scrapli raw + 厂商 SDK 适配 |
| MCP server 数量爆炸难维护 | 中 | 统一 mcp-hub 网关 + 公共 SDK（异常处理/重试/审计） |
| 数据出境合规（云端 LLM） | **高** | 默认脱敏（IP/MAC/AS 号哈希）；敏感场景接本地模型 fallback |
| 仿真环境与生产差异 | 中 | Containerlab 用真实 NOS 镜像（FRR/SONiC/SR Linux/cRPD）；逐步接入 cEOS/C8000v |

---

## 七、差异化卖点（相对 Forward Networks / Selector AI / Cisco）

1. **RDMA/InfiniBand 全栈支持**——竞品完全缺失
2. **MCP-First 架构**——工程师在 Cursor/Claude 里就能用，零学习曲线
3. **多 Agent 协同**——不是单一 chat，是 Planner→多个 Expert Agent 流水线
4. **仿真内置**——所有变更必过 Containerlab + Batfish 双验证
5. **国产化 LLM 路由就绪**——同一架构可切换 Qwen/DeepSeek/GLM
6. **开源底座透明**——客户可控可审计，避免 vendor lock-in

---

## 八、组织与开源策略建议

- **核心代码闭源 + 工具层开源**：MCP server 和 Containerlab 拓扑模板开源，做社区；编排 + Agent 逻辑 + UI 闭源做商业化
- **社区运营**：Awesome 列表 / 教程 / benchmark 数据集，复用您之前的 AI 安全 benchmark 调研模式
- **benchmark 自建**：参照 NetAgentBench / CTBench 思路做 NetAI-Bench，作为产品基线和营销素材
- **首发 demo 场景建议**：RDMA 集群 AI 优化（差异化）+ 数据中心 VXLAN fabric 规划（刚需）

---

方案完成。需要我下一步：
1. 把方案落成可执行的 **Gantt + 任务拆解**？
2. 先把 **Phase 1 的 Containerlab-MCP + Batfish-MCP + ConfigGen Agent** 起代码骨架？
3. 还是再深入某个模块（比如 RDMA Agent 的工具调用详细设计）？

请告诉我从哪一步开始。
