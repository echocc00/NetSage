# 开源网络 AI 项目调研报告（2026-08）

> 数据来源：GitHub REST API + OpenAlex 学术数据库（实时抓取）  
> 截止时间：2026-08-19  
> 调研目标：梳理"AI 辅助网络规划/实施/运维"全链路开源生态，评估成熟度、可组合性、是否可直接作为底座或组件集成。

---

## 一、能力矩阵（按您 5 条核心需求对齐）

| 您的需求 | 主要开源能力域 | 代表项目（⭐=star数） | AI 化程度 |
|---|---|---|---|
| ① OSPF/BGP/VXLAN/VPN/无线配置与排障 | 多厂商配置抽象+配置分析+配置生成/校验 | NAPALM(2.5k) / Batfish(1.5k) / NetBox(21k) / pyATS(185+) / Containerlab(2.7k) / FRR(4.3k) / SONiC(2.9k) | 部分（LLM 化刚起步） |
| ② InfiniBand / RoCE v1/v2 运维 | RDMA 用户态内核+子网管理+性能测试 | linux-rdma/rdma-core(2.3k) / perftest / opensm | 极低（基本无 AI 化） |
| ③ 故障排查+系统性思维+业务反推 | 可观测性+数字孪生+LLM Agent | SUZIEQ(894) / Cilium+Hubble(25k+4.3k) / Containerlab | 中（前沿论文涌现） |
| ④ 大型网络交付+多厂商设备调试 | 配置管理+变更审计+推送回滚 | Ansible(70k) / Nornir(1.6k) / NAPALM / NetBox | 低（仍是人工编排） |
| ⑤ 网络安全：交换/路由/VPN/SDN/VXLAN+合规 | 策略验证+意图翻译+合规检查 | Batfish / OpenConfig(990) / OVS(4k) / TopoIntent(论文) | 中（NetConfEval 是标杆） |

---

## 二、五大类项目精选（按能力域组织）

### 1. 网络配置/自动化（您的④号需求核心）

| 项目 | � | 关键能力 | AI/Agent 化 |
|---|---:|---|---|
| **ansible/ansible** | 70,349 | 通用自动化之王，ansible.netcommon 覆盖 Cisco/Arista/Juniper/Nokia 等；网络社区模块 1500+ | 无原生 AI，但 playbook 可作为 LLM 的执行后端 |
| **napalm-automation/napalm** | 2,487 | **多厂商配置抽象层**（get_facts / get_config / load_merge_candidate）；统一 API 操作异构设备 | 无；可作为 LLM 工具调用层 |
| **nornir-automation/nornir** | 1,611 | Python 化、多线程、插件化的网络任务框架，比 Ansible 更适合做"网络 agent 工具集" | 无；和 NAPALM 互补 |
| **netbox-community/netbox** | 21,329 | **网络单一事实源（source of truth）**：IPAM / 设备机架 / 线缆 / VLAN / VRF / 电路 | NetBox MCP server 已现成 |
| **carlmontan/scrapli** | (已迁移/重写中) | 异步网络 CLI 抓取框架，比 Netmiko 快 10x | 无；新一代为 scrapli-community |
| **networktocode/ntc-templates** | 1,287 | TextFSM 模板库，覆盖 70+ 厂商 show 命令解析 | LLM 友好：解析后即结构化 |
| **CiscoTestAutomation/pyats + genieparser** | 185 / 279 | Cisco 官方测试+解析；Genie parsers 业内最准 | 无；可做 LLM 的事实抽取工具 |

### 2. 网络仿真/数字孪生（您做"测试/验证/演练"必备）

| 项目 | ⭐ | 关键能力 | 您的适配 |
|---|---:|---|---|
| **srl-labs/containerlab** | 2,745 | **容器化网络仿真之王**：FRR / SONiC / Nokia SR Linux / Cisco IOS XR / 瞻博 cRPD 一键拉起拓扑；声明式 YAML | ★★★★★ 强烈推荐做底座仿真 |
| **KatharaFramework/Kathara** | 631 | 比 Containerlab 更轻量，学术圈常用 | 备选 |
| **GNS3/gns3-gui** | 2,608 | 老牌 GUI 仿真，VM 为主，重 | 仅 GUI 演示场景 |
| **Mats2208/MCP-Packet-Tracer** | 131 | **AI+思科 Packet Tracer 通过 MCP**：自然语言驱动 | 思路参考，但能力窄 |

### 3. 网络验证/分析（您的①③⑤号需求核心，AI 化最前沿）

| 项目 | ⭐ | 关键能力 | AI 化 |
|---|---:|---|---|
| **batfish/batfish** | 1,454 | **配置静态分析**：建模路由表/ACL/转发，断言式检查"配置是否满足意图" | 是；Pybatfish Python API 是 LLM 工具的金标准 |
| **netenglabs/suzieq** | 894 | **多厂商可观测性**：状态表 + 跨厂商 BGP/OSPF/LLDP 标准化查询；Poller/Assert 框架 | 中；适合做 LLM 的"运行时观察工具" |
| **cilium/cilium** | 24,970 | **eBPF 网络+安全**：K8s CNI、Hubble 可观测、L7 策略 | 中；可做 LLM 的"东西向流量分析工具" |
| **openconfig/public** | 990 | 厂商中立的 YANG 模型（Google 主导） | 无；是 SONiC/Nokia/Arista 的事实标准 |

### 4. SDN / 数据中心 / 路由协议栈（您的①⑤号需求核心）

| 项目 | ⭐ | 关键能力 | 您的适配 |
|---|---:|---|---|
| **openvswitch/ovs** | 4,004 | 虚拟交换机之王；VXLAN/Geneve/OpenFlow；OVS-DPDK | 仿真必备 |
| **FRRouting/frr** | 4,255 | 全协议路由栈（OSPF/BGP/VXLAN/EVPN/IS-IS） | Containerlab 默认底座 |
| **sonic-net/SONiC** | 2,899 | 云厂商主流 NOS（微软Azure/阿里云）；SAI 抽象 | 仿真和真实硬件都支持 |
| **linux-rdma/rdma-core** | 2,344 | RDMA 内核+用户态主仓（ibverbs/libibumad/opensm 等） | 您的 ② 号需求 |

### 5. 前沿 AI/LLM + Network 项目（您要做的产品直接对标）

| 项目 | ⭐ | 类型 | 关键能力 |
|---|---:|---|---|
| **NetConfEval/NetConfEval** | 1 | Benchmark | **LLM 网络配置修复基准**：用 Batfish 评估 OSPF/BGP/ACL/路由策略生成正确率 |
| **Overlxrd-uwu/SADE-NetworkAgent** | 7 | Agent | **症状感知-诊断升级**：LLM 网络排障 agent（论文 SADE 对应） |
| **olasupo/bubbln_network-automation** | 38 | Agent | AI 驱动的网络自动化 CLI 工具 |
| **Mats2208/MCP-Packet-Tracer** | 131 | Agent | MCP + Packet Tracer 自然语言驱动 |
| **packetcoders/awesome-network-automation-ai** | 57 | 索引 | Awesome 列表，持续维护 |
| **zhihao1998/LLM4NetLab** | 12 | Benchmark | AI Agent 网络排障开放基准（容器化网络实验台） |

### 6. 学术前沿论文（2025-2026，与您项目最相关的 7 篇）

| 论文 | 一作 | 关键观点 |
|---|---|---|
| **A Comprehensive Survey on LLM-Based Network Management and Operations** | Jibum Hong (USENIX/IJnM 2025) | 综述，把 LLM4Net 分为"配置/排障/可观测/意图/安全"五域；13 引用，**必读** |
| **NetConfEval: Benchmarking LLM-Driven Network Configuration Repair** | 2025 | 用 Batfish 做 ground truth 评测 LLM 修复 BGP/OSPF 错误配置的能力 |
| **NetAgentBench: A State-Centric Benchmark for Evaluating Agentic Network Configuration** | 2026 | **State-centric** 评估 agent（状态转换视角），比单纯配置正确率更接近真实运维 |
| **CTBench: Evaluating Troubleshooting Capabilities of AI Agents in Realistic Telecom Networks** | Xingyu Yan 2026 | 电信级（RAN/核心网/传输）排障 benchmark |
| **TopoIntent: Compiling Security Intent into Executable, Compliance-Checked Network Topologies** | 2026 | **自然语言→合规网络拓扑**：直接对应您的 ⑤ 号需求 |
| **SADE: Symptom-Aware Diagnostic Escalation for LLM-Based Network Troubleshooting** | 2026 | 分级诊断策略：先症状分类→低级查→升级 |
| **Let AI Agents Translate Networks, Not Reason About Them** | 2026 | **重要观点**：让 LLM 做翻译（NL↔配置），不让它推理复杂网络行为——直接关系到您产品定位 |

### 7. RDMA/InfiniBand 工具链（②号需求）

| 工具 | 角色 |
|---|---|
| linux-rdma/rdma-core | 主仓：ibverbs / libibumad / opensm 子网管理器 / ipoib |
| linux-rdma/perftest | 性能压测：ib_send_bw / ib_write_bw / ib_read_bw |
| jumanjihouse/docker-opensm | opensm 容器化（轻量 SM 部署） |
| Mellanox/NVIDIA mlx5 驱动 | 实际生产环境的卡+驱动（不开源二进制） |
| NIXT (NVIDIA, 2026 论文) | NCCL 通信可观测性，RDMA 集群必备监控 |

> ⚠️ RDMA 领域的 AI 化基本空白，是您产品差异化最强的方向之一。

---

## 三、社区活跃度 / 商业生态扫描

| 维度 | 状态 |
|---|---|
| **网络+LLM 顶级社区** | NANOG（北美运营商）/ RIPE / APRICOT 2025 起有专门 track；USENIX NSDI/ATC 2025 出现多篇 |
| **商业产品对标** | Cisco Nexus Dashboard + AI Assistant、Huawei iMaster NCE + 盘古大模型、Juniper Mist AI、Nokia AVA + GenAI、Itential、Forward Networks、Graphiant、Selector AI |
| **MCP 生态** | NetBox MCP、Containerlab MCP（社区已有）、Ansible MCP、FRR MCP（部分）—— **MCP 已是事实标准，建议您的产品直接走 MCP 接口** |
| **大模型选择** | Claude Sonnet/Opus（推理强）、GPT-5（多模态）、Qwen3-Coder（开源可本地部署）—— 网络运维推理任务首选 Claude |

---

## 四、可直接作为产品底座的开源项目 TOP 5

按"复用价值/集成成本/AI 化基础"综合打分（10 分制）：

| 排名 | 项目 | 综合分 | 推荐用途 |
|---|---|---:|---|
| 1 | **Containerlab + FRR + SONiC** | 9.5 | 数字孪生底座，所有变更先在仿真里验证 |
| 2 | **Batfish** | 9.0 | 配置意图验证、错误配置检测（LLM 生成配置后必经此关） |
| 3 | **NetBox + NetBox MCP** | 9.0 | source of truth；所有操作都从 NetBox 读意图、写回审计 |
| 4 | **SUZIEQ** | 8.5 | 多厂商实时可观测、跨厂商标准化查询；LLM 排障的事实抽取层 |
| 5 | **Ansible (ansible.netcommon) + NAPALM** | 8.0 | 配置推送/回滚；LLM 通过工具调用生成 playbook 执行 |

---

## 五、产品差异化机会（基于调研发现的 5 个空白点）

1. **RDMA/InfiniBand + AI 完全空白**——目前没有任何 LLM agent 能管理 IB 子网；NIXT 类工具都没有 AI 层
2. **"翻译器"而非"推理器"定位**——SADE/NetConfEval 等论文都验证了"LLM 直接推理网络行为不可靠"，让 LLM 做 NL↔配置翻译，用 Batfish/FRR 验证——这是产业共识方向
3. **State-Centric Agent 框架**——NetAgentBench 提出"状态转换"评估，您可以用 Containerlab 仿真器作为 state simulator
4. **端到端闭环**——从 NetBox 读意图 → LLM 翻译 → Containerlab 验证 → Batfish 静态检查 → Ansible 推送 → SUZIEQ 监控，每一步都是开源组件，**没有产品把它们串起来**
5. **MCP-First 架构**——直接出 NetBox/Containerlab/Batfish/Ansible/SUZIEQ 的 MCP server，对接 Claude/Cursor/Cline 即用

---

调研完成。下一步我准备出 **完整的产品架构设计方案**，包含：分层架构、数据流、技术选型矩阵、MVP 路径、风险点和落地节奏。要我现在就出方案吗？
