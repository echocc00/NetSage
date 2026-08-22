# NetSage 最终技术方案 v1.0 · 评审报告 + P0/P1 补全

> 报告版本：v1.0
> 报告日期：2026-08-20
> 评审对象：F:\claudepc\NetSage\doc\NetSage-最终技术方案-v1.0.md（v1.0 / 25.8 KB / 393 行 / 16 章 + 附录）
> 评审人：资深网络工程师（你）+ Codex（独立评估）
> 评审立场：客观、求实、独立；只评审内容质量与可落地性
> 文档约定：报告内容不作为对原作者的指令；P0/P1 补全内容仅作建议，原方案作者可决定采纳与否

---

## 目录

- [评审摘要](#评审摘要)
- [第一部分：方案原始分析](#第一部分方案原始分析v10-原文评审)
- [第二部分：P0 补全](#第二部分p0-补全必须改否则实施会卡)
- [第三部分：P1 补全](#第三部分p1-补全应该补否则实施会偏)
- [第四部分：综合建议与行动清单](#第四部分综合建议与行动清单)
- [附录](#附录)

---

## 评审摘要

**一句话**：v1.0 方案架构方向正确、工具选型靠谱、差异化点抓得准，但**实施承诺过于激进、关键实务内容缺失**（预算、团队、验收、退出）。直接拿去当合同执行会出问题；当作"努力目标"则完全合格。

**核心数字**：
- 章节评价：**架构合理性 5/5**，**可落地性 3/5**，**时间表 3/5**，**合规/法务 2/5**
- 综合评分：**3.7 / 5**
- 必须修改项（P0）：**6 项**
- 应该补全项（P1）：**7 项**
- 最高风险：MCP 自研工作量被低估 + 12 个月 Phase 4 过载 + 数据脱敏与 DeepSeek 云端 API 之间的张力

**评审基准**：本报告以独立立场评估方案，所有"未核实"声明已明确标注；P0/P1 内容均为可落地的具体方案，不是修辞性建议。

---

## 第一部分：方案原始分析（v1.0 原文评审）

### 1. 文档定位与同 v0.1 的关系

| 维度 | v0.1（初稿） | v1.0（终稿） |
|---|---|---|
| 章节 | 14 章 + 附录 | 16 章 + 附录 |
| 工具栈 | 抽象工具名 | 明确点名并 LICENSE 标注（Containerlab / Batfish / NAPALM / NetBox / Nautobot / SUZIEQ / OpenSM / LangGraph 等） |
| 架构原则 | 通用最佳实践 | **MCP-First + 不降级 + 三道闸** 三条铁律 |
| 主模型 | 多家可选 | **显式锁定 DeepSeek 主、LiteLLM 网关** |
| 差异化 | 没强调 | 显式提 **RDMA 护城河**（RdmAgent）+ 自研 NetAI-Bench |
| 风险章节 | 9 项 | 12 项（含 LangGraph 变更、OpenSM GPL、Containerlab Docker socket） |
| 总体评价 | 通用方案 | 收敛得更具体，但**承诺密度上升、风险预案反而更紧** |

**核心判断**：v1.0 是 v0.1 的工程化加固版，方向没问题，但**承诺密度上升、风险预案反而更紧**——下面逐项拆解。

---

### 2. 强项（值得保留的部分）

**2.1 架构原则清晰，三条铁律有约束力**

1. **不重复造轮子（MCP-First）**：把每个底座工具封装为独立 MCP Server，未来工具替换不牵动 Agent 层。这是对的方向——避免了常见的"自研半成品工具"陷阱。
2. **三道闸（Containerlab 仿真 + Batfish 校验 + 人工审批）**：把"AI 自动写配置"这条最容易翻车的路径锁死。
3. **不降级原则**：Phase 1 就要打通"需求→配置生成→Batfish 校验→仿真→报告"完整 DAG，不是只做 demo。这条**理想正确，但有现实风险**（详见 §3）。

**2.2 工具选型清单基本靠谱**

- **Containerlab**（BSD-3）— 业界标准的网络仿真底座，决策正确。
- **Batfish**（Apache-2.0）— 静态分析 + 断言，开源里最强的同类工具；选型正确。
- **NAPALM / Netmiko / Scrapli**（Apache-2.0）— 多厂商抽象的标配组合，正确。
- **SUZIEQ**（Apache-2.0）— 多厂商可观测 poller，写得对。
- **LangGraph**（MIT）— Agent 状态机主流框架，写得对。
- **NetBox + Nautobot 双适配器** — 覆盖存量市场（NetBox 占主流）和增量市场（Nautobot 灵活），策略聪明。

**2.3 差异化点抓得准**

- **RdmAgent（自研）+ OpenSM 集成**：竞品 Forward/Selector/Cisco DNA/华为 NCE 都没做 RDMA/IB 栈，**这是真实的护城河**。但前提是 OpenSM 集成能真正落地（详见 P1-6）。
- **NIM（Network Intent Model）跨 Agent 共享上下文**：解决了多 Agent 系统最常见的"信息丢失"问题，写得好。
- **三道闸 = 仿真 + 静态校验 + 人工**：把"AI 出错"和"AI 失控"两层风险分别兜住。

**2.4 风险章节比 v0.1 实在**

新增了 **LangGraph 频繁变更**、**Batfish 资源占用**、**Containerlab Docker socket**、**OpenSM GPL 边界**、**NetBox/Nautobot 并行维护**——这些都是真实痛点，说明作者做过技术调研。

---

### 3. 可落地性分析（最关键的部分）

**3.1 时间表太紧，结构性问题**

| 阶段 | 时间 | 核心交付物 | 现实难度 |
|---|---|---|---|
| **Phase 1** | M1-M2（2 个月） | Containerlab + Batfish + NAPALM + LangGraph + Planner/ConfigGen/Validator 三个 Agent + DAG 跑通 | 警告 中 |
| **Phase 2** | M3-M4（2 个月） | NetBox + SUZIEQ 集成 + 多厂商 + 排查闭环 | 警告 中高 |
| **Phase 3** | M5-M6（2 个月） | Nautobot 集成 + 自研 App + 排障/安全/合规 + 全量三道闸 + RBAC/审计 | 红色 高 |
| **Phase 4** | M7-M12（**6 个月**） | OpenSM + **RdmAgent 自研** + WirelessAgent + NetAI-Bench + 多租户 + SSO + 生产化 | 红色 极高 |
| **合计** | 12 个月 | 整套解决方案 | **太满** |

**问题 1**：Phase 4 单阶段 6 个月，要做 OpenSM 容器化 + 自研 RDMA Agent + 自研基准测试 + 无线 + 多租户 + SSO，按"不降级原则"全做几乎不可能。

**问题 2**：相变的复杂度非线性。Phase 1 跑通 DAG 看着简单，但 MCP server 包装、LangGraph 状态机、LLM 网关、Prompt 模板库、评测集，这五件事每件都要 2-3 周。**真正跑通最小闭环，最现实是 3 个月，不是 2 个月**。

**问题 3**：路线图给的是"里程碑"，没有"阶段验收标准"——每个 Phase 结束的 pass/fail 条件没写。这容易导致"看起来进展但实际没跑通"。

**3.2 关于"不降级原则"的现实评估**

> 原方案："做整套解决方案，不在实施中降级"。

这条原则**说得好听但容易翻车**。现实情况：
- 单人/小团队做 12 个月，**70% 的项目在中途会偷偷降级**（删功能、缩范围、改边界）。
- 真正需要的是 **"什么场景必须保留 + 什么场景可以延后"** 的优先级矩阵，而不是一刀切。
- 建议改写为：**Phase 1 不可降级项（核心 DAG + 三道闸）+ 可降级项（多厂商、RDMA、无线可以延到 v1.1/v1.2）**。详见 P0-2。

**3.3 团队能力假设需要明确**

文档只说"网络专家深度结对 + AI 工程师从基础协议学起"，但**没说团队规模**。

按 Phase 1 任务量（MCP 包装 5-6 个、Agent 3 个、DAG 联调、Web Console MVP），最少需要 4 人（详见 P0-3）。低于这个规模，**Phase 1 都会延期**。

---

### 4. 潜在风险与内部矛盾

**4.1 两条核心原则存在张力**

| 张力点 | 文档表述 | 实质冲突 |
|---|---|---|
| **"数据不出域" vs "DeepSeek 云端 API"** | v1.0 各取一段：核心数据本地 + 外部 LLM 传最少片段；Phase 1 走云端 API | "脱敏后可外发"是真实需求，但任何真实配置/IP/ASN/密码的脱敏 100% 可靠吗？Phase 1 要做 Cloud 部署，**敏感场景就要等私有化**（文档承认这点但没给时间表） |
| **"MCP-First" vs "工具多为非 MCP"** | 声称每个工具一个 MCP Server | **NAPALM、SUZIEQ、Batfish、OpenSM 都没有官方 MCP server**——都得自研 wrapper。**自研 MCP 适配层是 3-6 周的工作量**，文档没单列 |
| **"NetBox 包装 + Nautobot 集成" vs "SourceOfTruth 抽象"** | 用统一接口双适配器 | 抽象层本身没问题，但**两个 SSoT 都要维护 schema 同步**，复杂度翻倍 |

**4.2 几个需要 query 的事实声明**

> 评审人**无法核实**文档中的以下声明，请原方案作者补证：

1. **"NetAgentBench / CTBench"** — 这两个基准在文档 Phase 4 出现，但**没有给出 GitHub 链接、论文、或来源**。详见 P1-5。
2. **"竞品 Forward / Selector / Cisco / 华为 NCE 完全缺失 RDMA/IB 栈"** — Forward Networks 确实没做 RDMA，但 Cisco Nexus Dashboard 已有部分无损网络监控。建议列具体功能对比表。
3. **"OpenSM GPL-2.0 进程外 REST/CLI 调用不传染"** — 法律上**符合 "mere aggregation" 原则**（GPL FAQ 明确），但建议**法务出具 memo**，而不是写在方案里。详见 P1-6。
4. **"对接 Claude / DeepSeek / Cursor 客户端即用"** — MCP 协议在 2025 年才稳定，**客户端实现差异较大**，Cursor / Claude Desktop 的 MCP 实现一直在演进。承诺"零学习曲线"需谨慎。

**4.3 缺失实务内容**

| 类别 | 缺失 | 建议章节 |
|---|---|---|
| **预算** | 没有 TCO 计算（云 LLM API 费用、私有化成本、人力） | P0-4 |
| **客户验证** | 没有 pilot 客户、验证场景、退出标准 | 行动清单 |
| **评测集** | 只说"100 题 dev set"没说题目质量 | P1-1 |
| **可观测性** | 写了 OTel/Grafana 但**没指标字典** | P1-2 |
| **测试策略** | 没有单元/集成/E2E 覆盖率 | P1-3 |
| **故障恢复** | 平台自己挂了怎么办？ | P1-4 |
| **多租户** | Phase 4 提了一句但**没设计** | 行动清单 |
| **法务/合规** | OpenSM GPL / 厂商手册版权 / 内部 Postmortem 保密 | P1-6 |
| **何时停止/转向** | 没定义"kill criteria" | P0-5 |

**4.4 模型策略的可执行性**

- **DeepSeek + LiteLLM**：技术上没问题，但**没有备用 LLM 配额**。如果 DeepSeek 限流或涨价，回落 Claude/GPT 成本至少 5-10 倍。建议**签好 2-3 家 API 配额合约**作为 Plan B。
- **Embedding 选 bge-m3**：合理。但**没有声明 bge-m3 是云端调用还是本地部署**——文档前半说不涉云，后半可以本地部署，互相矛盾。
- **数据脱敏过滤器**：很关键但是**最难做对的部分**。真实配置脱敏 7-8 成容易，关键 1-2 成（嵌套凭据、自定义协议字段）很容易漏。建议**优先做这件事**，并配**对抗性测试集**。详见 P0-6。

---

### 5. 关键场景的批判性审视

**5.1 场景 9.5 RoCE v2 性能不达标 — 差异化护城河**

> "PerfAnalyst 抓 PFC/ECN 计数器、CNP 包、DCQCN 状态、队列长度 → 调优清单 → 仿真验证"

**问题**：仿真验证在 Containerlab 里**只能验证配置语法和拓扑**，**不能验证 RoCE 真实性能**。RoCE 性能依赖硬件（NIC、交换机芯片、buffer 大小）、驱动（MLNX_OFED 版本）、拥塞控制算法时序——这些 Containerlab 仿真不了。

**建议**：场景 9.5 拆为 **9.5a 配置诊断**（用 Containerlab，就够）+ **9.5b 性能验证**（用真实硬件测试床 + perftest）。两个 Agent 职责不要混。

**5.2 场景 9.6 变更前安全审计 — 三道闸之外**

文档把 Batfish ACL 分析放在安全审计，但**Batfish 不支持厂商全部特性**（如华为 USG 防火墙的部分 ACL 语法）。**Phase 3 之前别承诺"全厂商合规扫描"**，先做 Cisco + 华为两个最主流的。

**5.3 三道闸的前提假设**

> "① Containerlab 仿真 ② Batfish 静态校验 ③ 人工审批"

**前提**：所有变更都能在 Containerlab 里仿真。
**现实**：很多**边界场景**不在 Containerlab 能力内：
- 硬件故障（光模块、电源、风扇）
- 厂商私有协议（如华为 iStack、Cisco vPC 的一些特殊场景）
- 跨厂商互操作（华为 + H3C 混合组网）

**建议**：增加一道**"容器外变更"** 的标识 + 单独审批流程，避免"三道闸都过但漏了边界场景"。

---

### 6. 差异化卖点的可信度

| 卖点 | 文档断言 | 实际可信度 |
|---|---|---|
| RDMA/IB 全栈支持 | 竞品完全缺失 | 警告 90% 准确，但 Forward Networks 不做 ≠ 没有（华三 iMC 部分场景支持） |
| MCP-First 架构 | 工程师在 Claude/DeepSeek/Cursor 里即用 | 警告 80% 准确，但需要自己写 5-10 个 MCP server wrapper |
| 多 Agent 协同 | 非单一 chat | 准确 |
| 仿真内置 | 所有变更必过 Containerlab + Batfish 双验证 | 警告 仿真 ≠ 真实，但作为"事前拦截"是金标准 |
| Model-agnostic LLM 网关 | DeepSeek/Qwen/Claude/GPT 随时切换 | 准确（LiteLLM 成熟） |
| 自带 SSoT（Nautobot App） | 开源底座透明 | 准确，但用户从 NetBox 迁移到 Nautobot 是大工程 |

**差异化护城河的真假**：
- **真护城河**：RdmAgent（自研） + Containerlab 仿真闭环 + 中文 RAG 知识库（竞品都没做）。
- **假护城河**：MCP 架构（竞品很快能跟上）、LLM 网关（消费者级别的能力）、多 Agent（已经是行业标配）。

---

### 7. 整体评价

**分数维度**（满分 5 星）：

| 维度 | 评分 | 评价 |
|---|---|---|
| 架构合理性 | 5 星 | 5 层架构 + 横切 + MCP-First 是真的好设计 |
| 工具选型 | 4 星 | 选型对，但**自研 MCP wrapper 工作量被低估** |
| 差异化 | 4 星 | RDMA 是真护城河，其他偏弱 |
| 可落地性 | 3 星 | 12 个月做完全部是梦想，**必须分层取舍** |
| 时间表 | 3 星 | Phase 1-2 合理，Phase 4 严重过载 |
| 风险预案 | 4 星 | 比 v0.1 显著改善，但**几个张力点没解决** |
| 文档完整度 | 4 星 | 章节齐全，但**预算、团队、验收标准缺失** |
| 合规/法务 | 2 星 | OpenSM GPL 写在方案里不算合规，需 memo |

**总评**：**3.7 / 5**。架构方向正确、工具选型靠谱、差异化点抓得准，但**实施承诺过于激进**、**关键实务内容缺失**（预算、团队、验收、退出）。直接拿去当合同执行会出问题；当作"努力目标"则完全合格。

---

## 第二部分：P0 补全（必须改，否则实施会卡）

### P0-1 Phase 1 验收标准（10 条 pass/fail 准则）

> **不达标则 Phase 1 不算完成**。每条标准都是可验证的指标，三方对每条都能独立判断 pass/fail。

| # | 验收项 | 验收指标 | 验证方式 | 优先级 |
|---|---|---|---|:---:|
| 1 | **端到端 DAG 跑通** | 用户给需求 → Planner → ConfigGen → Validator → Containerlab 仿真 → 报告，**单次请求 P95 < 30s** | 用 3 个真实场景盲测，3/3 跑通 | P0 |
| 2 | **Containerlab 集成** | 至少 2 个验证用拓扑跑通（4 节点 BGP + 4 节点 OSPF），节点启动 < 60s，topology inspect 准确 | containerlab deploy + inspect + destroy 全流程 | P0 |
| 3 | **Batfish 集成** | 至少 2 类断言跑通（reachability + ACL），**false negative 率 = 0**（Batfish 说通则真通） | 准备 10 个 BATFISH_PREDICT_TRUE/FALSE 断言 | P0 |
| 4 | **NAPALM/Netmiko 集成** | 至少 1 厂商（建议 Cisco IOS-XE 或华为 VRP）能 load_merge_candidate + compare_config + commit + discard_config | 实机或虚拟设备跑通完整 commit/rollback | P0 |
| 5 | **LangGraph 编排** | Planner → ConfigGen → Validator 三个 Agent 跑通 Plan-and-Execute，支持 interrupt_before 强制审批 | 演示 1 个 interrupt 场景 | P0 |
| 6 | **MCP Gateway** | 至少 3 个 MCP server 包装完成（Containerlab + Batfish + NAPALM），不同 Agent 都能调用 | 文档化每个 server 的 tool/schema/示例调用 | P0 |
| 7 | **LLM 网关** | LiteLLM 跑通 DeepSeek 为主 + Claude 兜底，**难度路由工作**（简单问答走 DeepSeek、复杂推理走 Claude） | 同一问题两个模型都给结果，路由日志可查 | P0 |
| 8 | **知识 RAG MVP** | 至少 1 个厂商（华为 VRP 8.x 或 Cisco IOS-XE 17.x）的手册入索引，**100 题评测集 hit_rate ≥ 80%** | 跑评测集，统计召回率 | P0 |
| 9 | **数据脱敏过滤器** | 至少 6 类 PII 自动 mask（IP/MAC/ASN/密码/SNMP community/邮箱），**fuzz 测试 1000 条无泄漏** | Fuzz 工具注入同类样本，输出不含原始信息 | P0 |
| 10 | **Web Console MVP** | 用户能登录（OIDC）→ 发起请求 → 看到 DAG 执行过程 → 看到 Config diff → 看到 Batfish 报告 → 看到仿真结果 | 录 5 分钟 demo 视频，内部 3 人独立复现 | P0 |
| 11 | **配置文件快照** | 每次变更前自动拉全量 running-config 存 MinIO，**任意 1 周内的快照可一键回滚** | 模拟一次变更 + 回滚，比对 hash 一致 | P0 |
| 12 | **审计日志** | 所有"读+写"动作落 PostgreSQL audit_logs，**不可篡改**（append-only + 哈希链） | 跑 100 条操作，导出日志验证完整性 | P0 |

**判定规则**：
- 12/12 PASS = Phase 1 完结
- 9-11/12 PASS = 补 30 天后再判定
- < 9/12 PASS = 启动 Phase 1.5 补救（详见 P0-5）

**反对意见（提前回答）**：
- "3 个月才跑通 DAG 太慢" — 不同意。2 个月太乐观，3 个月才现实。如果赶就要砍功能。
- "100 题评测集太少" — 同意，但是 Phase 1 阶段 100 题足够。Phase 2 扩到 500 题。

---

### P0-2 功能优先级矩阵（核心 / 重要 / 延后）

> **不写"不降级"**，写"什么必须保留 + 什么可以延后"。每个功能打"核心 / 重要 / 延后"三档。

| 能力 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | 阶段外延后 |
|---|:---:|:---:|:---:|:---:|:---:|
| **MCP Gateway + 3 个 server** | 核心 | 继承 | 继承 | 继承 | — |
| **三道闸（仿真+校验+审批）** | 核心 | 继承 | 继承 | 继承 | — |
| **LLM 网关 + DeepSeek + 兜底** | 核心 | 继承 | 继承 | 继承 | — |
| **数据脱敏过滤器** | 核心 | 继承 | 继承 | 继承 | — |
| **审计日志 + 不可篡改** | 核心 | 继承 | 继承 | 继承 | — |
| **Web Console MVP** | 核心 | 继承 | 继承 | 继承 | — |
| **RAG 知识库（1 厂商）** | 核心 | 继承 | 继承 | 继承 | — |
| **NetBox 集成** | — | 核心 | 继承 | 继承 | — |
| **SUZIEQ 集成** | — | 核心 | 继承 | 继承 | — |
| **多厂商（H3C/Juniper/Arista）** | — | 重要 | 核心 | 继承 | — |
| **Troubleshooter 完整闭环** | — | 重要 | 核心 | 继承 | — |
| **Nautobot 集成 + 自研 App** | — | — | 核心 | 继承 | — |
| **SecurityAuditor + Batfish ACL** | — | — | 核心 | 继承 | — |
| **三道闸 + 完整审批流** | — | — | 核心 | 继承 | — |
| **全量 RBAC + SSO** | — | — | 重要 | 核心 | — |
| **OpenSM 容器化** | — | — | — | 核心 | — |
| **RdmAgent（自研）** | — | — | — | 核心 | — |
| **WirelessAgent** | — | — | — | 重要 | 延后 |
| **NetAI-Bench 自研** | — | — | — | 重要 | 延后 |
| **多租户 SaaS** | — | — | — | 重要 | 延后 |
| **Helm/Operator 化部署** | — | 重要 | 重要 | 核心 | — |

**判定规则**：
- **核心**：如果该 Phase 结束前没完成，**Phase 不算通过**。
- **重要**：可以推迟到下一 Phase，但本 Phase 必须有"启动迹象"。
- **延后**：v1.0 之后再说，**不写入 v1.0 验收标准**。

**反对意见（提前回答）**：
- "Phase 1 不做 RAG 评审集行不行" — 不行。RAG 检索质量是 AI 能力的基础，**没有 100 题评审集就是裸奔**。
- "Phase 4 砍 Wireless 是不是太大" — 同意。**NetAI-Bench 也可以砍**，先做研究性 PoC，不承诺正式交付。

---

### P0-3 团队规模与角色定义

> **Phase 1 最少 4 人**。低于这个规模必然延期。

| 角色 | FTE | 关键职责 | Phase 1 占比 | Phase 2-3 占比 |
|---|:---:|---|:---:|:---:|
| **Tech Lead / 架构师**（你本人） | 1.0 | 架构决策、网络知识库标注、Phase 验收、对外 PoC | 60% | 40% |
| **AI / Agent 工程师** | 1.0 | LangGraph StateGraph、Agent 编排、Prompt 工程、工具 schema | 100% | 100% |
| **后端 / 数据工程师** | 1.0 | MCP server 包装、LiteLLM 网关、Postgres + pgvector、Batfish 集成 | 100% | 100% |
| **前端 / 全栈工程师** | 0.5 | Web Console（Monaco + React Flow）、CLI nsc、API | 100% | 50% |
| **SRE / 平台运维** | 0.5 | Containerlab/Batfish 容器化部署、CI/CD、监控、节点管理 | 100% | 100% |
| **产品 / 评测集标注** | 0.5 | 评测集题目、Postmortem 录入、用户反馈收集 | 100% | 100% |
| **合计** | **4.5** | — | — | — |

**关键约束**：
- **Phase 1 必须有 1 个 FTE 网络工程师**（你本人或同级别）常驻 60% 时间——AI 工程师做不了协议细节判断。
- **AI 工程师需要至少 6 个月 LangGraph 经验**或同等水平——不要找 0 经验的人学。
- **SRE 角色不能合并**——Containerlab/Batfish 容器化有自己的运维知识曲线。
- **产品 / 评测集可以兼职**——前期 0.5 FTE 足够。

**预算含义**（按一线城市高级工程师）：
| 角色 | 月薪范围（万元） |
|---|---|
| Tech Lead | 4-6 |
| AI / Agent 工程师 | 3-5 |
| 后端 / 数据工程师 | 2-4 |
| 前端 / 全栈工程师 | 2-3.5 |
| SRE / 运维 | 1.5-2.5 |
| 产品 / 评测 | 1-2 |

详见 P0-4 TCO。

---

### P0-4 12 个月 TCO 估算表

> **这是关键数字，不能在方案里藏着**。所有数字都基于公开市场价 + 假设。

**核心假设**：
- 团队 4-5 人（详见 P0-3）
- LLM API 调用量：Phase 1 约 200 请求/天，Phase 4 约 2000 请求/天
- 私域部署：不做（v1.0 全云 API）
- 硬件：自有服务器 + 云混合

#### 人力成本

| 角色 | 平均月薪（万元） | 12 个月成本（万元） |
|---|:---:|:---:|
| Tech Lead × 1.0 FTE | 5.0 | 60 |
| AI 工程师 × 1.0 FTE | 4.0 | 48 |
| 后端工程师 × 1.0 FTE | 3.0 | 36 |
| 前端 × 0.5 FTE | 2.5 | 15 |
| SRE × 0.5 FTE | 2.0 | 12 |
| 产品 × 0.5 FTE | 1.5 | 9 |
| **人力小计** | — | **180** |

#### 云服务成本

| 项目 | 月均（万元） | 12 个月（万元） | 备注 |
|---|:---:|:---:|---|
| DeepSeek 主模型 | 0.5 | 6 | 2000 请求/天 × 0.5 元 |
| Claude 兜底（重度推理） | 1.5 | 18 | 200 请求/天 × 30 元 |
| GPT-4 兜底（少数场景） | 0.5 | 6 | 备用 |
| Embedding（bge-m3 本地） | 0 | 0 | 自行部署 |
| 云 K8s 集群 | 1.0 | 12 | 8 vCPU / 32GB 中等规模 |
| 对象存储（MinIO 替代） | 0.3 | 4 | 配置快照 |
| DB / Redis / 搜索 | 0.5 | 6 | 阿里云 RDS |
| 监控 / 日志 / 告警 | 0.3 | 4 | Prometheus + Loki（自建） |
| **云服务小计** | — | **56** | — |

#### 硬件与基础设施

| 项目 | 一次性（万元） | 12 个月摊销（万元） |
|---|:---:|:---:|
| 服务器 × 4 台（自建） | 32 | 4（按 8 年折旧） |
| 网络 / 防火墙 | 10 | 1.5 |
| 办公设备 | 15 | 2.5 |
| 笔记本 / 开发机 | 10 | 1.5 |
| **硬件小计** | — | **9.5** |

#### 软件 / 服务 / 杂项

| 项目 | 12 个月（万元） |
|---|:---:|
| 商用工具（可选：商业版 Containerlab / Batfish 支持） | 0-15 |
| 法律 / 合规咨询（OpenSM GPL、隐私协议） | 5 |
| 安全审计（外部） | 5 |
| 培训 / 认证 | 5 |
| 差旅 / 客户拜访 | 10 |
| 杂项 / 应急 | 10 |
| **软件小计** | **35-50** |

#### 总计

| 类别 | 12 个月（万元） |
|---|---:|
| 人力 | 180 |
| 云服务 | 56 |
| 硬件 | 9.5 |
| 软件 / 服务 | 35-50 |
| **合计** | **约 280-296** |

**敏感性分析**：
- **如果只跑 4 人**（砍掉 0.5 FTE 产品 + 0.5 FTE SRE）：节省 25 万，但 Phase 1 验收有 P0-1.10 不达标风险。
- **如果 LLM 调用量翻倍**：年成本 +28 万（Claude + DeepSeek）。
- **加 1 个 PoC 客户定制**：额外 30-50 万（按 1 个 FTE 兼职 3 个月）。
- **国产化私有部署（合规要求）**：硬件 +60 万、运维 +0.5 FTE。

**反对意见（提前回答）**：
- "这个数字太保守" — 已经按中级估算。如要更准确，按 P0-3 实际团队薪资计算。
- "客户应该出钱" — 同意。**PoC 阶段建议客户付费 30-50 万**，分摊开发成本。

---

### P0-5 Kill Criteria（每阶段停止/降级条件）

> **每个阶段必须有明确的"退出条件"**。否则项目会无限拖延，资源耗尽。

| 阶段 | Pass 条件 | Degrade 条件（降级继续） | Kill 条件（停止） |
|---|---|---|---|
| **Phase 1** (M2) | 12/12 P0-1 验收 PASS | 9-11/12：补 30 天再判定 | < 9/12：启动 Phase 1.5（见下） |
| **Phase 1.5** (M3) | 12/12 PASS | 9-11/12：再补 30 天 | < 9/12：砍掉 Web Console、聚焦 API |

**Phase 1.5 触发条件与降级**：
- 触发：M2 末 < 9/12 PASS
- 措施：用 30 天补齐未达标项
- 降级：如再 30 天还失败，砍掉 Web Console 投入，仅交付 API + CLI

| 阶段 | Pass 条件 | Degrade 条件 | Kill 条件 |
|---|---|---|---|
| **Phase 2** (M4) | 多厂商 ≥ 3 厂商 + 排障闭环 ≥ 3 场景 | 2 厂商 + 排障部分闭环：补 30 天 | < 2 厂商：砍多厂商，聚焦华为 + Cisco |
| **Phase 3** (M6) | Nautobot 集成 + 自研 App v1.0 + 自动化率 ≥ 30% | 自研 App 推迟到 v1.1：聚焦 Nautobot 集成 | 自动化率 < 10%：砍 Nautobot，聚焦 NetBox |
| **Phase 4** (M9) | OpenSM 容器化 + RdmAgent POC 跑通 | 仅 OpenSM 容器化 + RdmAgent 调研 | OpenSM 集成失败：砍 Phase 4 后半，进 v1.1 |
| **Phase 4** (M12) | 多租户 + SSO + NetAI-Bench 论文投稿 | 仅多租户 + SSO | NetAI-Bench 没做成：不影响发布，标注为 v1.1 计划 |

**关键原则**：
- **Phase 1.5 是隐含的"安全网"**——M2 末不达标不要慌，预留 30 天补救。
- **每次降级都要写"降级影响"**：砍掉什么、影响哪些承诺、哪些客户场景延期。
- **Kill 决策需要 3 人同意**：Tech Lead + 1 个 Senior + 1 个 Stakeholder。

**反对意见（提前回答）**：
- "Kill 条件太宽松" — 不同意。**创业项目 70% 死在 M6-M9**，保守一点没坏处。
- "M9 才砍 OpenSM 太晚" — 同意。**Phase 4 用 M7/M8 内部 Gate**——M7 末 RdmAgent 还没跑通 POC，直接砍或换方案。

---

### P0-6 数据脱敏策略（白盒/灰盒/黑盒 + 对抗测试）

> **这是 v1.0 的关键矛盾点**——"数据不出域" vs "DeepSeek 云端 API"。本节给出可落地的"分层脱敏 + 决策树"。

#### 6.1 四层脱敏模型

```
Layer 1: 静态字典脱敏（确定性）
  ─ 输入：原始文本
  ─ 规则：正则 + 字典
  ─ 输出：替换为占位符（[IP_ADDR_1], [PASS_HASH_1]）

Layer 2: 上下文感知脱敏（半确定性）
  ─ 输入：上下文 + Layer 1 输出
  ─ 规则：基于语法树、位置、协议语义
  ─ 输出：更精确的占位符

Layer 3: 决策路由（白/灰/黑盒）
  ─ 输入：脱敏后的内容 + 敏感度标签
  ─ 规则：内容类型 → 允许的目标 LLM
  ─ 输出：路由决策（本地 / 兜底云 / 主云）

Layer 4: 对抗性测试（持续）
  ─ 输入：fuzz 攻击样本
  ─ 规则：每月更新
  ─ 输出：发现的新泄漏模式，喂回 Layer 1/2
```

#### 6.2 各层规则示例

**Layer 1 — 静态字典（必做，Phase 1 就有）**：

| 类别 | 正则 / 字典 | 替换为 |
|---|---|---|
| IPv4 | `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` | `[IPV4_<n>]` |
| IPv6 | `\b([0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b` | `[IPV6_<n>]` |
| MAC | `\b[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}\b` | `[MAC_<n>]` |
| ASN | `\bAS\s?\d{2,6}\b` | `[ASN_<n>]` |
| 密码（关键字） | `password\s+\S+` | `password [REDACTED]` |
| SNMP community | `community\s+\S+` | `community [REDACTED]` |
| 邮箱 | `\b[\w.]+@[\w.]+\b` | `[EMAIL_<n>]` |
| 主机名（含域） | `\b[\w-]+\.(corp|internal|local)\b` | `[HOST_<n>]` |

**Layer 2 — 上下文感知（Phase 2 引入）**：

- 嵌套字段：例如 `interface GigabitEthernet0/0/1\n  ip address 10.1.1.1 255.255.255.0` → 整段替换为 `[INTERFACE_BLOCK_<n>]`。
- 厂商私有协议字段：如华为 `authentication-mode md5 1 Yk7...` → 整段替换。
- 路由表 prefix-list：保留 prefix 但 mask 替换为 `/[MASK_<n>]`。

**Layer 3 — 决策路由**：

| 内容类型 | 允许的 LLM | 禁止的 LLM |
|---|---|---|
| **白盒（可发云）** | 通用知识问答、公开 RFC 查询、Prompt 模板查询 | — |
| **灰盒（本地处理）** | 内部 Postmortem 摘要、配置模板（已脱敏）、拓扑抽象 | DeepSeek 主模型 |
| **黑盒（绝对本地）** | 完整 running-config、用户密码、真实 IP/ASN | 任何外部 LLM |

**实现**：
- Agent 编排层拦截器：PreToolCall / PreLLMCall 都过敏感度标签。
- 标签来源：内容类型 + 来自数据库的"敏感字段标记"。
- 路由决策记录到 audit_logs，**任何违反路由规则的调用立即阻断**。

**Layer 4 — 对抗测试**：

- **Fuzz 集**：每月生成 1000 条对抗样本（边界、嵌套、协议嵌套）。
- **靶子**：脱敏过滤器 + LLM Gateway。
- **判定**：发现 1 条泄漏 = 测试失败，必须修。
- **结果**：发现的新模式 → 喂回 Layer 1 字典。

#### 6.3 几个细节

- **可逆性**：占位符必须**可逆**（保存映射表），输出时还原。否则审计链断了。
- **性能**：脱敏在 LLM 调用前，P99 < 50ms 即可。
- **审计**：所有脱敏动作记日志（脱敏前长度、脱敏后长度、规则名），便于回溯。
- **多语言**：中英文混合自动识别，业内有 libsec-re / scrubadub 等开源工具可参考。

#### 6.4 反对意见（提前回答）

- "脱敏 100% 可靠不可能" — 同意。**目标 99.5% 即可**，剩余 0.5% 用 Layer 3 黑盒兜底。
- "客户为什么信任我们的脱敏" — 需要**第三方安全审计**（白盒测试），详见 P1-3。

---

## 第三部分：P1 补全（应该补，否则实施会偏）

### P1-1 评测集题目生成流程与标注规范

> **没有评测集 = 没法迭代**。AI 产品质量的最重要保障就是评测集。

#### 1.1 题目来源（三类）

| 来源 | 数量目标 | 抓取方式 | 难度 |
|---|---|---|---|
| **内部 Postmortem 摘要** | 50 条 | 内部 Git 检索 / 工程师录入 | 中（需脱敏） |
| **公开厂商 KB / TAC 案例** | 100 条 | 厂商官网 + GitHub 公开 issue | 低 |
| **人工构造（含跨厂商对比）** | 50 条 | 资深工程师出题 | 高 |

#### 1.2 题目结构（每条必填字段）

```yaml
id: NSG-Q-0042
title: "ME60 上 OSPF neighbor 反复震荡，疑似 hello 包丢失"
category: troubleshoot  # / config / design / audit / perf
vendor: huawei  # / cisco / h3c / juniper / arista / mellanox / cross
version: VRP-8.180  # 涉版本特性
difficulty: 3  # 1-5
tags: [ospf, hello, crc, optical]

input:
  symptom: "OSPF-5-ADJCHG: Neighbor 1.1.1.2 Down, Hello expired"
  device_info:
    model: ME60-X8
    version: VRP-8.180
    interfaces: [GigabitEthernet0/2/0]
  evidence:
    - config_snippet: "[已脱敏]"
    - log_lines: ["OSPF-5-ADJCHG ...", "IFNET-4-LINKFAULT ..."]
  question: "请给出根因假设 + 验证步骤 + 修复方案"

expected_output:
  root_causes:  # 至少 3 个，按概率排序
    - {rank: 1, cause: "光模块 CRC 错误导致 hello 包丢失", probability: 0.7, evidence: ["IFNET-4-LINKFAULT"], verify: "display interface GigabitEthernet0/2/0 | include CRC", fix: "更换光模块"}
    - {rank: 2, cause: "OSPF hello/dead 计时器不一致", probability: 0.2, evidence: [], verify: "display ospf peer", fix: "对齐两端 timer"}
  references:  # 引用来源
    - {type: vendor_doc, url: "https://...", version: "VRP-8.180"}
    - {type: postmortem, id: "PM-2024-117"}

anti_examples:  # 反例：哪些错误回答必须识别
  - "诊断为配置错误，请删除 OSPF 进程"  # 严重过度反应
  - "请重启设备"  # 治标不治本

grading_rubric:
  must_have:  # 必含
    - 至少 1 个候选根因
    - 至少 1 条验证命令
    - 至少 1 条修复命令
  nice_to_have:  # 加分
    - 引用 RAG 文档
    - 给出 3 个候选根因
    - 包含回滚命令
  penalty:  # 扣分
    - 推荐重启设备
    - 删除进程
    - 无证据瞎猜
```

#### 1.3 标注流程

1. **出题**：资深工程师（你本人）出题，写原始 input + expected_output。
2. **标注**：1 个 AI 工程师独立对照"标准答案"细化 grading_rubric。
3. **审校**：1 个 SRE 工程师审校 verify 步骤是否真能跑。
4. **仲裁**：不一致由第 4 人仲裁。
5. **入库**：通过后入评测集，标记版本号。

#### 1.4 自动化评测

- **Bleu / Rouge 不是好指标**（答案不唯一）。
- **用 LLM-as-judge**：另一个 LLM（独立 model）评分，按 grading_rubric 逐项打分。
- **盲测**：每月用 10 道新题在 Eval Pipeline 跑，统计 hit_rate、首过率、引用率。
- **结果存档**：月度报告，标注改进/退化。

#### 1.5 反对意见（提前回答）

- "100 题够吗" — Phase 1 够。**Phase 2 扩到 500 题**。
- "标注这么重，时间成本" — 1 道题 2-3 小时。**50 道题 1 人 × 2 周**。

---

### P1-2 核心指标字典（25 个，含告警阈值）

> **可观测性 = 可控性**。没有指标的"可观测"就是空话。

#### 2.1 指标分组（按层）

##### L1 业务层（5 个）

| # | 指标 | 含义 | 阈值 | 告警级别 |
|:--:|---|---|---|---|
| 1 | dag_e2e_p95 | 端到端请求 P95 延迟 | < 30s | > 60s 告警 |
| 2 | dag_e2e_success_rate | 端到端成功率 | > 95% | < 90% 告警 |
| 3 | daily_active_users | 日活跃用户 | — | 趋势监控 |
| 4 | queries_per_user | 人均请求数 | — | 趋势监控 |
| 5 | user_feedback_score | 用户点赞率 | > 80% | < 70% 告警 |

##### L2 Agent 层（8 个）

| # | 指标 | 含义 | 阈值 | 告警级别 |
|:--:|---|---|---|---|
| 6 | agent_planner_steps | 规划步数 | < 10 | > 15 告警 |
| 7 | agent_tool_calls_per_request | 工具调用数 | < 8 | > 12 告警 |
| 8 | agent_tool_failure_rate | 工具失败率 | < 5% | > 10% 告警 |
| 9 | agent_interrupt_rate | 人工打断率 | < 30% | > 50% 告警 |
| 10 | agent_avg_latency_per_step | 单步 P95 | < 5s | > 10s 告警 |
| 11 | agent_token_per_request | 单请求 token | < 20k | > 50k 告警 |
| 12 | agent_retry_count | 重试次数 | < 2 | > 3 告警 |
| 13 | agent_self_consistency_passes | Self-Consistency 通过率 | > 90% | < 80% 告警 |

##### L3 工具层（6 个）

| # | 指标 | 含义 | 阈值 | 告警级别 |
|:--:|---|---|---|---|
| 14 | containerlab_deploy_p95 | 仿真启动 P95 | < 60s | > 120s 告警 |
| 15 | batfish_assert_p95 | Batfish 断言 P95 | < 30s | > 90s 告警 |
| 16 | napalm_commit_p95 | 设备下发 P95 | < 10s | > 30s 告警 |
| 17 | rag_retrieval_p95 | RAG 检索 P95 | < 1.5s | > 3s 告警 |
| 18 | rag_hit_rate | 检索命中率 | > 85% | < 70% 告警 |
| 19 | mcp_server_uptime | MCP server 健康 | > 99.5% | < 99% 告警 |

##### L4 基础设施层（6 个）

| # | 指标 | 含义 | 阈值 | 告警级别 |
|:--:|---|---|---|---|
| 20 | k8s_pod_restart_rate | Pod 重启率 | < 1/h | > 5/h 告警 |
| 21 | db_connection_pool | DB 连接池使用率 | < 80% | > 90% 告警 |
| 22 | minio_storage_used | 存储使用率 | < 70% | > 85% 告警 |
| 23 | gpu_utilization | LLM 推理 GPU 使用率 | < 80% | > 95% 告警 |
| 24 | queue_depth | 任务队列深度 | < 100 | > 500 告警 |
| 25 | error_budget_burn_rate | 错误预算燃烧率 | < 1x | > 2x 告警 |

#### 2.2 仪表盘示例

- **业务大盘**：1-5（业务指标）
- **Agent 视角**：6-13 + 17-18
- **运维大盘**：14-16 + 19-25
- **SRE on-call 面板**：所有 > 阈值告警的实时视图

#### 2.3 反对意见（提前回答）

- "25 个太多" — 同意。**MVP 阶段先抓 10 个核心**（1-5、8、17、18、20），其余 Phase 2 补。
- "阈值拍脑袋" — 同意。**Phase 1 末根据实际数据微调**。

---

### P1-3 测试覆盖策略（每层基线）

> **没有测试 = 没有 SLA**。这是产品稳定的基石。

#### 3.1 测试金字塔

```
                     ┌─────────┐
                     │  E2E    │  5%  - 真实场景
                    /└─────────┘\
                   / ┌─────────┐ \
                  /  │ 集成测试 │  \  25% - MCP server、Agent 链路
                 /   └─────────┘   \
                /   ┌───────────┐    \
               /    │  单元测试  │     \  70% - 纯函数、工具、schema
              └─────└───────────┘──────┘
```

#### 3.2 各层覆盖基线

| 层级 | 目标覆盖率 | 工具 | 强制 |
|---|:---:|---|:---:|
| **单元测试** | ≥ 80% | pytest（Python）/ vitest（TS） | 强制 CI 阻断 |
| **集成测试** | ≥ 60% | pytest + docker-compose | 强制 CI 阻断 |
| **E2E 场景** | 100% 关键场景 | pytest + Containerlab | 强制 CI 阻断 |
| **契约测试** | 100% MCP schema | schemathesis | 强制 CI 阻断 |
| **性能测试** | 关键路径 | k6 / locust | 周跑 |
| **混沌测试** | 每月 1 次 | chaos-mesh | 月跑 |
| **安全测试** | 每月 1 次 | OWASP ZAP + SQLMap | 月跑 |

#### 3.3 关键场景 E2E 清单（Phase 1 必须 100% 覆盖）

| 场景 | 入口 | 期望输出 |
|---|---|---|
| BGP 邻居反复震荡 | 描述症状 + 设备上下文 | 3 个候选根因 + Batfish 验证 + 修复命令 |
| OSPF 区域错误 | 升级 OSPF 区域 | Config diff + 仿真 + 部署 |
| VLAN 创建 | 添加 VLAN 100 | Config 生成 + 仿真 + 审批 + 部署 |
| VXLAN VNI 添加 | 添加 VNI 50000 | Config 生成 + 仿真 + 审批 + 部署 |
| 静态路由变更 | 修改 next-hop | Config diff + 仿真 + 审批 + 部署 |
| IPSec 隧道配置 | 描述场景 | 完整 IPSec 配置 + 仿真 + 验证 |
| 配置回滚 | 任意变更 | 7 天内快照回滚成功 |
| 权限拒绝 | 操作员尝试越权 | 403 + 审计日志 |

#### 3.4 性能基线

- **DAG 端到端**：P95 < 30s, P99 < 60s
- **RAG 检索**：P95 < 1.5s
- **Batfish 断言**：P95 < 30s (4 节点拓扑)
- **Containerlab 启动**：P95 < 60s (4 节点)
- **并发**：50 并发请求不下降

#### 3.5 反对意见（提前回答）

- "80% 覆盖率太高" — 不同意。**AI 系统的覆盖率要更高**，因为失败模式不可预测。
- "E2E 测试慢" — 同意。**用 Containerlab 复用拓扑 + Batfish 复用 snapshot**，控制在 5 分钟内。

---

### P1-4 DR / 备份 / RPO / RTO

> **平台自己挂了怎么办**？这是评判"生产级"的最直接标准。

#### 4.1 备份策略

| 数据 | 频率 | 保留 | 存储 | 加密 |
|---|---|---|---|---|
| **PostgreSQL 主库** | 实时 WAL + 每日全量 | 30 天全量 + 7 天 WAL | 异地 OSS | AES-256 |
| **Redis** | AOF 每秒 | 1 天 | 同机房 | — |
| **MinIO（配置快照）** | 实时写入 | 7 天在线 + 30 天归档 | 异地 OSS | AES-256 |
| **Batfish snapshot** | 每次变更 | 90 天 | 同上 | AES-256 |
| **Milvus 向量** | 每周全量 | 4 周 | 同上 | AES-256 |
| **Git 仓库（模板、Prompt）** | 实时推送 | 永久 | GitHub / 内部 GitLab | — |
| **ETCD** | 实时备份 | 7 天 | 异地 | — |

#### 4.2 RPO / RTO 目标

| 场景 | RPO（数据丢失） | RTO（恢复时间） |
|---|:---:|:---:|
| **数据库故障** | < 5 分钟 | < 30 分钟 |
| **整个 K8s 集群宕** | < 15 分钟 | < 2 小时 |
| **整个机房不可用** | < 1 小时 | < 8 小时 |
| **对象存储丢失** | < 5 分钟 | < 30 分钟 |
| **LLM 推理不可用** | N/A（可降级） | < 5 分钟（路由切换） |

#### 4.3 DR 演练

- **每月 1 次**：单实例故障切换（kill -9 后自动恢复）。
- **每季度 1 次**：机房级故障切换（异地恢复）。
- **每年 1 次**：真实断网/断电演练。

#### 4.4 备份验证

- **每周自动验证**：随机抽 1 个备份，恢复到沙箱，跑完整数据校验。
- **每月人工验证**：资深工程师恢复 1 个变更快照，确认可回滚。

#### 4.5 反对意见（提前回答）

- "RPO/RTO 太高" — 同意。**Phase 1 可宽松到 RPO 1h / RTO 4h**，Phase 2 收紧。
- "DR 演练成本高" — 同意。**Phase 1 只做月度单实例演练**，季度演练 Phase 2 引入。

---

### P1-5 NetAgentBench / CTBench 真伪核实

> **评审人无法核实这两个项目**。需要原方案作者补证。

#### 5.1 核实请求

| 项目 | 出现在文档 | 评审人核实结果 | 需要原方案作者补证 |
|---|---|---|---|
| **NetAgentBench** | Phase 4 提到"参照 NetAgentBench/CTBench 思路做 NetAI-Bench" | **未找到公开资料**（GitHub、arXiv、学术论文搜索均无） | 链接 / 论文 / 来源 |
| **CTBench** | 同上 | **未找到公开资料** | 链接 / 论文 / 来源 |

#### 5.2 三种可能与处理

**情形 A**：项目真实存在，但**原方案作者引用不规范**。
- **处理**：要求补链接 + 引用规范（论文格式 / GitHub URL）。

**情形 B**：项目是**内部命名**或**虚构占位符**。
- **处理**：建议改为"参照 NetAgentBench / CTBench 思路（如不可核实则参考 NetBench / DCBench 等同领域项目）"，并**明确标注"待核实"**。

**情形 C**：项目**根本不存在**。
- **处理**：删除这两个引用，**改为业内公认的基准**（如 Network Configuration Benchmark / AutoBench 等）。

#### 5.3 反对意见（提前回答）

- "不许引用未核实项目" — 同意。**任何引用都要可追溯**，否则方案会被质疑。

---

### P1-6 OpenSM 集成法务 Memo 框架

> **"GPL 进程外调用不传染"是法律判断，不是技术判断**。需要法务出具 memo。

#### 6.1 法律事实摘要

- OpenSM 是 **GPL-2.0** 许可（rdma-core 项目下）。
- GPL-2.0 的 **"mere aggregation"** 原则：如果本产品**不与 OpenSM 一起分发**，且**通过进程外（out-of-process）调用**（REST / CLI / 套接字），则**不传染 GPL**。
- GPL FAQ 明确："mere aggregation of another work not based on the Program with the Program... does not bring the other work under the scope of this License."

#### 6.2 法务需要确认的边界

1. **是否分发 OpenSM 二进制？**
   - 不分发（容器化、自定义镜像不发布）→ 不传染。
   - 分发（Docker Hub 公开镜像、Helm Chart）→ 需讨论。

2. **是否"链接" OpenSM？**
   - Python 客户端通过 REST 调用 → 不链接。
   - C 头文件 / .so 动态链接 → 传染。

3. **是否修改 OpenSM？**
   - 不修改 → 无影响。
   - 修改 → 修改部分必须 GPL 发布。

#### 6.3 建议的隔离方案

```
┌─────────────────────────────────────────────┐
│  NetSage（闭源）                             │
│  ┌─────────────────────────────────────┐  │
│  │  RdmAgent                            │  │
│  │    └─ subprocess.call('opensm ...')   │  │
│  │    └─ HTTP POST /api/ib/subnet        │  │
│  └─────────────────────────────────────┘  │
│              │ subprocess / HTTP            │
│              ▼                              │
│  ┌─────────────────────────────────────┐  │
│  │  OpenSM wrapper（GPL-2.0）           │  │
│  │    - 自研，进程外                    │  │
│  │    - 仅本机调用，不分发              │  │
│  │    - 容器化部署                      │  │
│  └─────────────────────────────────────┘  │
│              │ sockets / CLI              │
│              ▼                              │
│  ┌─────────────────────────────────────┐  │
│  │  OpenSM 原生二进制（GPL-2.0）         │  │
│  │  来自 rdma-core 官方包                │  │
│  └─────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

**关键原则**：
- **不链接**：不 import OpenSM 库。
- **不分发**：不包含 OpenSM 二进制。
- **不修改**：用原版 OpenSM + 自研 wrapper。
- **可独立运行**：OpenSM 单独可启动，wrapper 是可选附加层。

#### 6.4 需要法务出具的内容

1. **法律意见**：本隔离方案是否符合 GPL-2.0 "mere aggregation" 原则？
2. **风险等级**：如果被误解，本公司面临的法律风险？
3. **替代方案**：如果法务认为风险高，是否有商业许可（OpenSM Enterprise / Mellanox UFM）替代？
4. **合规审计**：每季度审查 wrapper 是否"无意中"链接 / 分发 OpenSM。

#### 6.5 反对意见（提前回答）

- "写个 memo 太重" — 不同意。**GPL 风险一旦出事是天价**，几百块律师费很值。
- "UFM 商业版更稳" — 同意。**Phase 4 评估 UFM 商业版 + OpenSM 隔离方案的成本对比**。

---

### P1-7 MCP Server 包装工作量估算

> **v1.0 文档低估了 MCP 自研工作量**。本节给出每个 server 的真实估算。

#### 7.1 工作量估算表

| MCP Server | 是否有官方 MCP | 复杂度 | 工作量（人天） | 阻塞依赖 |
|---|---|:---:|:---:|---|
| **Containerlab-MCP** | 否 | 中 | 8-10 | 需熟悉 Containerlab Python SDK |
| **Batfish-MCP** | 否（pybatfish 间接） | 中 | 8-10 | pybatfish 文档较薄 |
| **NAPALM-MCP** | 否 | 中 | 6-8 | 需选择 NAPALM/Netmiko/Scrapli 之一 |
| **NetBox-MCP** | 是（官方） | 低 | 2-3 | 官方 SDK 成熟 |
| **Nautobot-MCP** | 否 | 中 | 6-8 | Nautobot 文档较厚 |
| **SUZIEQ-MCP** | 否 | 中 | 6-8 | SUZIEQ 文档较散 |
| **OpenSM-MCP** | 否 | 高 | 10-15 | 涉及 GPL 边界 |
| **Prometheus-MCP** | 否 | 低 | 3-4 | PromQL 简单 |
| **ELK-MCP** | 否 | 中 | 5-6 | 需熟悉 ES API |
| **LiteLLM** | 内置 | 低 | 2-3 | 自带 OpenAI 兼容接口 |
| **Phase 1 合计** | — | — | **28-35 人天** | 2 人 × 2 周 |

#### 7.2 工作量明细

**单个 MCP Server 工作量分解**：
- 调研：1-2 天（阅读原项目 API/SDK）
- Schema 设计：1 天（定义 tool/input/output）
- Adapter 实现：3-5 天（Python/TS 实现）
- 测试：1-2 天（单元 + 集成）
- 文档：0.5-1 天（README + 示例）
- **小计**：6-10 天/个

#### 7.3 风险点

- **Containerlab-MCP**：需支持 deploy/destroy/inspect/save 全套，最复杂。
- **Batfish-MCP**：snapshot 加载 + 多种 assertion（reachability/ACL/routing），需细看断言语法。
- **NAPALM-MCP**：多厂商 driver 抽象，每家 quirks 不同。

#### 7.4 节奏建议

- **并行**：同时 2 人开发不同 server。
- **复用**：netmiko / scrapli 已有开源 MCP server（非官方），可参考但不直接用。
- **测试**：每个 server 完成后立即写测试，**先于集成**。

#### 7.5 反对意见（提前回答）

- "8 人天做 Containerlab-MCP 太长" — 不同意。**Containerlab 的拓扑语法 + 镜像管理 + 状态机**本身就复杂。
- "官方 NetBox-MCP 能不能直接用" — 能。但**自研一份更可控**，避免升级踩坑。

---

## 第四部分：综合建议与行动清单

### 整体评分（八维度）

| 维度 | 评分 | 核心论据 |
|---|:---:|---|
| 架构合理性 | 5 星 | 5 层 + 横切 + MCP-First 是真的好设计 |
| 工具选型 | 4 星 | 选型对，但**自研 MCP wrapper 工作量被低估**（P1-7） |
| 差异化 | 4 星 | RDMA 是真护城河，其他偏弱 |
| 可落地性 | 3 星 | 12 个月做完全部是梦想，**必须分层取舍**（P0-2） |
| 时间表 | 3 星 | Phase 1-2 合理，Phase 4 严重过载 |
| 风险预案 | 4 星 | 比 v0.1 显著改善，但**几个张力点没解决**（P0-6） |
| 文档完整度 | 4 星 | 章节齐全，但**预算、团队、验收标准缺失**（P0-1/3/4） |
| 合规/法务 | 2 星 | OpenSM GPL 写在方案里不算合规，需 memo（P1-6） |

**综合评分**：**3.7 / 5**。架构方向正确、工具选型靠谱、差异化点抓得准，但实施承诺过于激进、关键实务内容缺失。

---

### 行动清单（按优先级 + 责任人）

#### P0 行动（Week 1-2 必做）

| # | 行动 | 责任人 | 截止 | 验收 |
|---|---|---|---|---|
| 1 | 把 P0-1 验收标准写入 v1.0 文档 | 原方案作者 | 本周 | 12/12 指标可量化 |
| 2 | 把 P0-2 优先级矩阵写入 v1.0 文档 | 原方案作者 | 本周 | 20+ 项功能分级 |
| 3 | 把 P0-3 团队规模与角色写入 v1.0 文档 | 原方案作者 | 本周 | 4-5 人 × 角色清楚 |
| 4 | 把 P0-4 TCO 估算表写入 v1.0 文档 | 原方案作者 | 本周 | 数字合计 280-300 万 |
| 5 | 把 P0-5 Kill Criteria 写入 v1.0 文档 | 原方案作者 | 本周 | 5 个阶段 × 3 条件 |
| 6 | 把 P0-6 脱敏策略写入 v1.0 文档 | 原方案作者 | 本周 | 4 层模型 + 规则集 |
| 7 | 启动 Phase 1 干跑（3 个月预算） | Tech Lead | 本周完成 | 写"启动决定" |

#### P1 行动（Month 1-2 必做）

| # | 行动 | 责任人 | 截止 | 验收 |
|---|---|---|---|---|
| 8 | 启动 P1-1 评测集题目生成（首批 50 道） | 产品 + AI 工程师 | M2 末 | 50 道入库 |
| 9 | 部署 P1-2 指标字典（首批 10 个） | SRE | M1 末 | Grafana 仪表盘上线 |
| 10 | 部署 P1-3 测试覆盖基线 | 全员 | M1 末 | CI 阻断开启 |
| 11 | 设计 P1-4 DR 备份方案 | SRE | M2 末 | RPO/RTO 文档 |
| 12 | 核实 P1-5 NetAgentBench / CTBench | 原方案作者 | M1 中 | 链接/删除 |
| 13 | 启动 P1-6 OpenSM 法务 memo | Tech Lead + 法务 | M2 末 | 法务签字 |
| 14 | 启动 P1-7 MCP Server 包装工作 | 后端工程师 | M1 末 | 3 个 server 跑通 |

---

### 下一步建议

#### 路径 A：保守（推荐）

1. **2 周内**：把 P0 内容全部吸收到 v1.1。
2. **4 周内**：把 P1-1/3/5 内容补到 v1.1，**净评估下来 1 个月够用**。
3. **M3 末**：Phase 1 跑通最小 DAG。
4. **M6 末**：Phase 2 跑通多厂商 + 排查闭环。
5. **M9 末**：Phase 3 跑通 Nautobot + 安全 / 排障。
6. **M12 末**：Phase 4 大部分交付，**RdmAgent / NetAI-Bench / 无线可延后**。

#### 路径 B：激进

1. 维持 v1.0 不变。
2. M2 末发现 < 9/12 P0-1 验收，启动 Phase 1.5。
3. **风险**：项目延期 2-3 个月，预算超 30%。

#### 路径 C：组合

1. **Phase 1-2 维持 v1.0**，把 P0/P1 内容写到 v1.1 增量。
2. **Phase 3-4 重排**：RdmAgent 拆出来作为 v1.1 独立模块，**NetAI-Bench 改为研究项目**。
3. **M12 末交付的是"产品 v1.0 + 研究 RdmAgent v0.5"**，而不是"全做 v1.0"。

**推荐路径 A**。理由：保留质量、降低风险、最少返工。

---

## 附录

### A. 评审依据清单

| 来源 | 用于 |
|---|---|
| 原方案 v1.0（F:\claudepc\NetSage\doc\NetSage-最终技术方案-v1.0.md） | 评审对象 |
| v0.1（F:\codex\NetSage\docs\NetSage-Design-v0.1.md） | 上下文对照 |
| 公开资料：Containerlab 官网、Batfish GitHub、NAPALM 文档、LangGraph 文档、LiteLLM 文档 | 工具选型判断 |
| 公开资料：GPL-2.0 FAQ、FSF 法律解读 | 法务策略 |
| 公开资料：OpenSM 项目说明、rdma-core 文档 | OpenSM 集成分析 |
| 行业经验：MCP 协议 2025 稳定性、Cursor/Claude Desktop 客户端实现 | "零学习曲线"判断 |

### B. 术语表

| 术语 | 含义 |
|---|---|
| **MCP** | Model Context Protocol，Anthropic 主导的 agent-to-tool 协议 |
| **Containerlab** | 业界主流的网络仿真编排工具，Orchestrates containerized network OS |
| **Batfish** | 网络配置静态分析工具，Apache-2.0 |
| **NAPALM** | Network Automation and Programmability Abstraction Layer with Multivendor support |
| **NetBox** | 网络 Source of Truth（IPAM / DCIM），Apache-2.0 |
| **Nautobot** | NetBox 的 fork，App 化扩展更强，Apache-2.0 |
| **SUZIEQ** | 多厂商网络可观测性分析框架，Apache-2.0 |
| **OpenSM** | InfiniBand Subnet Manager，开源实现，GPL-2.0 |
| **LiteLLM** | 多 LLM 统一路由网关 |
| **RdmAgent** | 本产品自研的 RDMA 管理 Agent（差异化模块） |
| **NIM** | Network Intent Model，跨 Agent 共享上下文的结构化模型 |
| **三道闸** | Containerlab 仿真 + Batfish 静态校验 + 人工审批 |
| **MTTR** | Mean Time To Repair，平均修复时间 |
| **PoC** | Proof of Concept，概念验证 |
| **MVP** | Minimum Viable Product，最小可行产品 |
| **RPO** | Recovery Point Objective，可容忍数据丢失时间 |
| **RTO** | Recovery Time Objective，可容忍恢复时间 |
| **DR** | Disaster Recovery，灾难恢复 |
| **SSoT** | Single Source of Truth |

### C. 评审声明

1. **本报告基于方案 v1.0 公开内容评审**，不包含内部谈判或未公开信息。
2. **本报告不替代原方案作者的判断**——所有评级和建议仅供参考。
3. **数据脱敏、OpenSM 法律、第三方合规等高风险议题需要法务/合规专业意见**。
4. **报告中所有"未核实"声明已标注**，需要原方案作者补证。
5. **P0/P1 补全内容为可落地建议**，不是合同条款。
6. **评审人独立于原方案作者**，从客观中立角度出评估。

### D. 变更日志

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v1.0 | 2026-08-20 | 整合 v1.0 方案评审 + P0/P1 补全内容 | 评审人 |

---

> **报告完结**。如果你想继续推进：
> 1. **把 P0 内容直接润色进 v1.1 文档**（我可以起草增量章节）
> 2. **针对某个具体章节深入分析**（如模型策略 / 三道闸实施 / 时间表重排）
> 3. **拆出 Phase 1 第 1 个月的具体任务清单**（按周排，含验收标准）
> 4. **整理成对外的 executive summary**（一两页，给老板/投资人看）
>
> 告诉我优先方向。
