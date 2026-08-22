# NetSage · 最终技术方案 v1.1 — 增量补全

> 文档版本：v1.1（增量） · 日期：2026-08-21
> 基线：`NetSage-最终技术方案-v1.0.md`（2026-08-20）
> 性质：**增量补全，不改动 v1.0 的架构与能力范围**。本章接续 v1.0 第十六节之后，新增第十七至第三十一章 + 附录。
> 设计原则延续：**不降级**（四大模块全做、多厂商全覆盖、RDMA/无线/多租户不砍）；**MCP-First**；**三道闸**；**DeepSeek 为主 + 云端 API 优先**。
> 评审来源：客观分析 `NetSage-Review-v1.0.md` 与 `04-review.md` 两份报告，采纳"做加法"类建议（预算/团队/验收/脱敏/法务/评测/商业化/韧性），拒绝"做减法"类建议（砍能力/砍厂商/砍 scope）。

---

## 目录（增量章节）

- [十七、预算与 TCO 估算](#十七预算与-tco-估算)
- [十八、团队规模与角色定义](#十八团队规模与角色定义)
- [十九、阶段验收标准与 Kill Criteria](#十九阶段验收标准与-kill-criteria)
- [二十、数据脱敏分层模型](#二十数据脱敏分层模型)
- [二十一、OpenSM GPL 法务隔离与 Memo](#二十一opensm-gpl-法务隔离与-memo)
- [二十二、NetAI-Bench 评测体系](#二十二netai-bench-评测体系)
- [二十三、核心指标字典](#二十三核心指标字典)
- [二十四、测试覆盖策略](#二十四测试覆盖策略)
- [二十五、DR / 备份 / RPO / RTO](#二十五dr--备份--rpoto)
- [二十六、MCP Server 自研工作量与部署模式](#二十六mcp-server-自研工作量与部署模式)
- [二十七、配置模板沉淀机制](#二十七配置模板沉淀机制)
- [二十八、商业化路线图](#二十八商业化路线图)
- [二十九、LLM 多模型路由与降级策略](#二十九llm-多模型路由与降级策略)
- [三十、Agent 运行时适配层](#三十agent-运行时适配层)
- [三十一、功能优先级矩阵与交付节奏（不降级版）](#三十一功能优先级矩阵与交付节奏不降级版)
- [附录：事实修正与引用补证](#附录事实修正与引用补证)

---

## 十七、预算与 TCO 估算

> 补 v1.0 缺失：原方案无任何预算数字，无法当合同执行。本节给出 12 个月 TCO + 运行态隐藏成本，所有数字基于公开市场价 + 假设，按季度刷新。

### 17.1 核心假设

- 团队 4.5 FTE（详见第十八章）
- LLM 调用量：Phase 1 约 200 请求/天，Phase 4 约 2000 请求/天
- 部署形态：云端 LLM API + 本地平台混合（v1.0 全云 API，无私域推理集群）
- 硬件：自有服务器 + 云混合
- PoC 客户：建议付费 30-50 万分摊开发成本

### 17.2 开发态人力成本（12 个月）

| 角色 | FTE | 平均月薪（万元） | 12 个月（万元） |
|---|:---:|:---:|:---:|
| Tech Lead / 架构师（你本人） | 1.0 | 5.0 | 60 |
| AI / Agent 工程师 | 1.0 | 4.0 | 48 |
| 后端 / 数据工程师 | 1.0 | 3.0 | 36 |
| 前端 / 全栈工程师 | 0.5 | 2.5 | 15 |
| SRE / 平台运维 | 0.5 | 2.0 | 12 |
| 产品 / 评测集标注 | 0.5 | 1.5 | 9 |
| **人力小计** | **4.5** | — | **180** |

### 17.3 云服务成本（12 个月）

| 项目 | 月均（万元） | 12 个月（万元） | 备注 |
|---|:---:|:---:|---|
| DeepSeek 主模型 | 0.5 | 6 | 2000 请求/天 × ≈0.5 元 |
| Claude 兜底（重度推理） | 1.5 | 18 | 200 请求/天 × ≈30 元 |
| GPT 系兜底（少数场景） | 0.5 | 6 | 备用 |
| Embedding（bge-m3 本地部署） | 0 | 0 | 不涉云 |
| 云 K8s 集群 | 1.0 | 12 | 8 vCPU / 32GB 中等规模 |
| 对象存储（MinIO 自建替代云对象） | 0.3 | 4 | 配置快照 |
| DB / Redis / 搜索 | 0.5 | 6 | RDS |
| 监控 / 日志 / 告警 | 0.3 | 4 | Prometheus + Loki 自建 |
| **云服务小计** | — | **56** | — |

### 17.4 运行态隐藏成本（评审指出，v1.0 低估 2-3 倍）

> 这部分是部署到客户环境后才会显化的支出，必须单列，不能混进开发态。

| 项目 | v1.0 表述 | 现实规格 | 12 个月增量（万元） |
|---|---|---|---|
| **Batfish 部署** | "1vCPU/2GB 起步" | 生产 ≥ **8GB RAM** + JVM 调优；并发多拓扑建议 16GB+ | 3-5（含 JVM 调优人力） |
| **Containerlab 仿真** | "Docker socket" | 每拓扑 4-15 容器，镜像 5-20GB/个；并发 3 拓扑需 60GB 磁盘 | 4-6（存储 + 内存扩容） |
| **RAG 数据采集** | "每周 cron 抓" | 首次 6 厂商 × 1000+ 文档，人工清洗标注 200+ 工时 | 6-8（标注人力） |
| **SUZIEQ poller** | "嵌入" | 千台设备需 4-8 vCPU 专属 + SSH 凭证轮换 | 3-5（凭证管理 + 资源） |
| **LLM Token 成本（Phase 2 后）** | "难度路由省钱" | 单次复杂任务 5-15k token；月跑 1 万次 ≈ 3-8 万/月 | 36-96（随规模线性增长） |
| **隐藏成本小计** | — | — | **52-120** |

**关键提醒**：LLM Token 是**随客户规模线性增长**的变量成本，不是一次性。Phase 4 多客户上线后此项可能超过人力成本，必须进入产品定价模型（见第二十八章）。

### 17.5 硬件与基础设施

| 项目 | 一次性（万元） | 12 个月摊销（万元） |
|---|:---:|:---:|
| 服务器 × 4 台（自建） | 32 | 4（8 年折旧） |
| 网络 / 防火墙 | 10 | 1.5 |
| 办公设备 | 15 | 2.5 |
| 笔记本 / 开发机 | 10 | 1.5 |
| **硬件小计** | — | **9.5** |

### 17.6 软件 / 服务 / 杂项

| 项目 | 12 个月（万元） |
|---|:---:|
| 商用工具（可选：商业版 Containerlab / Batfish 支持） | 0-15 |
| 法律 / 合规咨询（OpenSM GPL、隐私协议） | 5 |
| 安全审计（外部白盒测试） | 5 |
| 培训 / 认证 | 5 |
| 差旅 / 客户拜访 | 10 |
| 杂项 / 应急 | 10 |
| **软件小计** | **35-50** |

### 17.7 12 个月 TCO 汇总

| 类别 | 金额（万元） |
|---|---:|
| 人力 | 180 |
| 云服务 | 56 |
| 运行态隐藏成本（保守取下限） | 52 |
| 硬件摊销 | 9.5 |
| 软件 / 服务 | 35-50 |
| **合计（保守）** | **约 332-347** |
| **合计（含 Token 规模化上限）** | **约 376-441** |

### 17.8 敏感性分析

- 砍掉 0.5 FTE 产品 + 0.5 FTE SRE → 节省 25 万，但 Phase 1 验收有 Web Console / 指标字典不达标风险（不推荐，违背不降级）。
- LLM 调用量翻倍 → 年成本 +28 万（Claude + DeepSeek）。
- 加 1 个 PoC 客户定制 → 额外 30-50 万（1 FTE 兼职 3 个月）。
- 国产化私有部署（合规要求） → 硬件 +60 万、运维 +0.5 FTE。

### 17.9 TCO 刷新机制

- 每季度刷新一次（DeepSeek/Claude/GPT 价格、SLA、团队薪资均动态变化）。
- 每次客户签约后重算该客户的运行态成本，进入定价模型。

---

## 十八、团队规模与角色定义

> 补 v1.0 缺失："网络专家深度结对 + AI 工程师从基础协议学起"太抽象。低于 4 人 Phase 1 必然延期。

### 18.1 Phase 1 最少 4.5 FTE

| 角色 | FTE | 关键职责 | Phase 1 占比 | Phase 2-3 占比 |
|---|:---:|---|:---:|:---:|
| **Tech Lead / 架构师**（你本人） | 1.0 | 架构决策、网络知识库标注、Phase 验收、对外 PoC | 60% | 40% |
| **AI / Agent 工程师** | 1.0 | LangGraph StateGraph、Agent 编排、Prompt 工程、工具 schema | 100% | 100% |
| **后端 / 数据工程师** | 1.0 | MCP server 包装、LiteLLM 网关、Postgres+pgvector、Batfish 集成 | 100% | 100% |
| **前端 / 全栈工程师** | 0.5 | Web Console（Monaco + React Flow）、CLI nsc、API | 100% | 50% |
| **SRE / 平台运维** | 0.5 | Containerlab/Batfish 容器化、CI/CD、监控、节点管理 | 100% | 100% |
| **产品 / 评测集标注** | 0.5 | 评测集题目、Postmortem 录入、用户反馈收集 | 100% | 100% |
| **合计** | **4.5** | — | — | — |

### 18.2 关键约束（不可破）

- **Phase 1 必须有 1 个 FTE 网络工程师**（你本人或同级别）常驻 ≥60% 时间——AI 工程师做不了协议细节判断。
- **AI 工程师需 ≥6 个月 LangGraph 经验**或同等水平——不找 0 经验的人学。
- **SRE 角色不能合并到后端**——Containerlab/Batfish 容器化有自己的运维知识曲线。
- **产品 / 评测集可兼职**——前期 0.5 FTE 足够。

### 18.3 Phase 2-4 人力演进

| 阶段 | 新增角色 | 累计 FTE |
|---|---|---|
| Phase 2 | +1 Nautobot/NetBox 集成工程师 | 5.5 |
| Phase 3 | +1 安全合规工程师（兼职 0.5） | 6.0 |
| Phase 4 | +1 RDMA/IB 专项工程师（核心护城河，必须专职） | 7.0 |

---

## 十九、阶段验收标准与 Kill Criteria

> 补 v1.0 缺失：原路线图只有"里程碑"没有"验收条件"，易假进展。每阶段 12 条可验证 pass/fail 指标。

### 19.1 Phase 1 验收标准（12 条）

| # | 验收项 | 验收指标 | 验证方式 |
|---|---|---|---|
| 1 | 端到端 DAG 跑通 | 需求→Planner→ConfigGen→Validator→Containerlab 仿真→报告，**P95 < 30s** | 3 个真实场景盲测，3/3 跑通 |
| 2 | Containerlab 集成 | ≥2 拓扑跑通（4 节点 BGP + 4 节点 OSPF），节点启动 <60s | deploy + inspect + destroy 全流程 |
| 3 | Batfish 集成 | ≥2 类断言跑通（reachability + ACL），**false negative = 0** | 10 个 TRUE/FALSE 断言集 |
| 4 | NAPALM/Netmiko 集成 | ≥1 厂商（Cisco IOS-XE 或华为 VRP）跑通 load_merge_candidate + compare + commit + discard | 实机或虚拟设备完整 commit/rollback |
| 5 | LangGraph 编排 | Planner→ConfigGen→Validator 跑通 Plan-and-Execute，支持 interrupt_before 强制审批 | 演示 1 个 interrupt 场景 |
| 6 | MCP Gateway | ≥3 个 MCP server（Containerlab + Batfish + NAPALM），多 Agent 可调用 | 每个 server 文档化 tool/schema/示例 |
| 7 | LLM 网关 | LiteLLM 跑通 DeepSeek 主 + Claude 兜底，**难度路由工作** | 同一问题双模型结果，路由日志可查 |
| 8 | 知识 RAG MVP | ≥1 厂商手册入索引，**100 题评测集 hit_rate ≥ 80%** | 跑评测集统计召回率 |
| 9 | 数据脱敏过滤器 | ≥6 类 PII 自动 mask（IP/MAC/ASN/密码/SNMP community/邮箱），**fuzz 1000 条无泄漏** | Fuzz 工具注入样本，输出不含原始信息 |
| 10 | Web Console MVP | 登录→发起请求→看 DAG 执行→看 Config diff→看 Batfish 报告→看仿真结果 | 5 分钟 demo 视频，3 人独立复现 |
| 11 | 配置快照 | 变更前自动拉全量 running-config 存 MinIO，**1 周内快照可一键回滚** | 模拟变更 + 回滚，hash 比对一致 |
| 12 | 审计日志 | 所有读+写动作落 audit_logs，**不可篡改**（append-only + 哈希链） | 100 条操作导出验证完整性 |

**判定规则**：12/12 PASS = Phase 1 完结；9-11/12 = 补 30 天再判定；<9/12 = 启动 Phase 1.5。

### 19.2 Phase 2-4 验收标准

| 阶段 | 关键验收项 | 指标 |
|---|---|---|
| **Phase 2** (M4) | 多厂商覆盖 | ≥3 厂商（华为 + Cisco + H3C/Juniper/Arista 之一） |
| | 排障闭环 | ≥3 场景端到端（症状→根因→修复→验证） |
| | NetBox + SUZIEQ 集成 | 拓扑读取 + 实时状态查询跑通 |
| | RAG 扩展 | 评测集扩至 500 题，hit_rate ≥ 85% |
| **Phase 3** (M6) | Nautobot 集成 + 自研 App v1.0 | SourceOfTruth 双适配器跑通 |
| | SecurityAuditor + Batfish ACL | ≥2 厂商合规扫描 |
| | 三道闸全量 + 审批流 + 快照回滚 | 端到端变更闭环 demo |
| | RBAC + SSO | 四级权限 + OIDC 跑通 |
| | 自动化率 | ≥30%（获批变更自动下发） |
| **Phase 4** (M9 内部 Gate) | OpenSM 容器化 | IB 子网管理可用 |
| | RdmAgent POC | RoCE 诊断 + 调优清单跑通 1 场景 |
| **Phase 4** (M12) | WirelessAgent | 无线设计 + 漫游策略跑通 |
| | 多租户 + SSO | per-tenant 隔离 + 计费 |
| | NetAI-Bench | 评测集对外可引用（论文/博客） |

### 19.3 Kill Criteria（应急，非正常路径）

> **保留为安全网，正常路径按不降级交付。** 每次降级必须写"降级影响"，Kill 决策需 Tech Lead + 1 Senior + 1 Stakeholder 三人同意。

| 阶段 | Pass | Degrade（降级继续） | Kill（停止/转向） |
|---|---|---|---|
| Phase 1 (M2) | 12/12 PASS | 9-11/12：补 30 天 | <9/12：启动 Phase 1.5 |
| Phase 1.5 (M3) | 12/12 PASS | 9-11/12：再补 30 天 | <9/12：砍 Web Console 聚焦 API（应急） |
| Phase 2 (M4) | ≥3 厂商 + 排障闭环 ≥3 | 2 厂商 + 部分闭环：补 30 天 | <2 厂商：聚焦华为+Cisco（**仅应急，不从 scope 删除**） |
| Phase 3 (M6) | Nautobot + 自研 App + 自动化 ≥30% | 自研 App 推迟 v1.1 | 自动化 <10%：聚焦 NetBox（**仅应急**） |
| Phase 4 (M9 Gate) | OpenSM + RdmAgent POC | 仅 OpenSM 容器化 + RdmAgent 调研 | OpenSM 失败：砍 Phase 4 后半进 v1.1 |
| Phase 4 (M12) | 多租户 + SSO + NetAI-Bench | 仅多租户 + SSO | NetAI-Bench 没做成：不影响发布，标 v1.1 |

**原则**：Kill 表里的"砍"是**应急触发项**，不写入 v1.0 验收标准。多厂商、RDMA、无线仍属 v1.0 承诺 scope，只是 Phase 内部排序可调。

---

## 二十、数据脱敏分层模型

> 解决 v1.0 最大矛盾点：**"数据不出域" vs "DeepSeek 云端 API"**。原方案只说"前置脱敏过滤器"一句，本节给出可落地的四层模型。

### 20.1 四层脱敏架构

```
Layer 1: 静态字典脱敏（确定性）        — Phase 1 必做
  正则 + 字典 → 占位符替换（[IPV4_1], [PASS_1]）

Layer 2: 上下文感知脱敏（半确定性）    — Phase 2 引入
  语法树 + 协议语义 → 整段/嵌套字段替换

Layer 3: 决策路由（白/灰/黑盒）        — Phase 1 必做
  敏感度标签 → 允许的目标 LLM（本地/兜底云/主云）

Layer 4: 对抗性测试（持续）            — Phase 2 起
  fuzz 样本 → 发现新泄漏模式 → 喂回 Layer 1/2
```

### 20.2 Layer 1 — 静态字典规则（Phase 1 就有）

| 类别 | 正则 / 字典 | 替换为 |
|---|---|---|
| IPv4 | `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` | `[IPV4_<n>]` |
| IPv6 | `\b([0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b` | `[IPV6_<n>]` |
| MAC | `\b[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}\b` | `[MAC_<n>]` |
| ASN | `\bAS\s?\d{2,6}\b` | `[ASN_<n>]` |
| 密码 | `password\s+\S+` | `password [REDACTED]` |
| SNMP community | `community\s+\S+` | `community [REDACTED]` |
| 邮箱 | `\b[\w.]+@[\w.]+\b` | `[EMAIL_<n>]` |
| 内部主机名 | `\b[\w-]+\.(corp|internal|local)\b` | `[HOST_<n>]` |

### 20.3 Layer 2 — 上下文感知（Phase 2）

- 嵌套字段：`interface GigabitEthernet0/0/1\n  ip address 10.1.1.1 255.255.255.0` → 整段替换为 `[INTERFACE_BLOCK_<n>]`。
- 厂商私有字段：华为 `authentication-mode md5 1 Yk7...` → 整段替换。
- prefix-list：保留 prefix，mask 替换为 `[MASK_<n>]`。

### 20.4 Layer 3 — 决策路由

| 内容类型 | 允许的 LLM | 禁止的 LLM |
|---|---|---|
| **白盒（可发云）** | 通用知识问答、公开 RFC 查询、Prompt 模板查询 | — |
| **灰盒（本地/脱敏后发云）** | 内部 Postmortem 摘要、脱敏配置模板、拓扑抽象 | 任何外部 LLM（未脱敏时） |
| **黑盒（绝对本地）** | 完整 running-config、用户密码、真实 IP/ASN | **任何外部 LLM** |

**实现**：Agent 编排层拦截器（PreToolCall / PreLLMCall）过敏感度标签；标签来源 = 内容类型 + DB 敏感字段标记；路由决策落 audit_logs，**违反路由规则立即阻断**。

### 20.5 Layer 4 — 对抗测试

- 每月生成 1000 条对抗样本（边界、嵌套、协议嵌套）。
- 靶子：脱敏过滤器 + LLM Gateway。
- 发现 1 条泄漏 = 测试失败，必须修；新模式喂回 Layer 1 字典。

### 20.6 工程约束

- **可逆性**：占位符必须可逆（保存映射表），展示时还原——否则审计链断。
- **性能**：脱敏在 LLM 调用前，P99 < 50ms。
- **审计**：脱敏动作记日志（前长度、后长度、规则名）。
- **目标**：99.5% 可靠，剩余 0.5% 由 Layer 3 黑盒兜底。
- **客户信任**：需第三方安全审计（白盒测试），详见合规章节。

---

## 二十一、OpenSM GPL 法务隔离与 Memo

> **"GPL 进程外调用不传染"是法律判断不是技术判断。** v1.0 写在方案里不算合规，需法务 memo。

### 21.1 法律事实摘要

- OpenSM 是 **GPL-2.0**（rdma-core 项目下）。
- GPL-2.0 **mere aggregation** 原则：本产品不与 OpenSM 一起分发 + 进程外调用（REST/CLI/socket）→ 不传染。
- GPL FAQ 明确："mere aggregation of another work not based on the Program with the Program... does not bring the other work under the scope of this License."

### 21.2 隔离方案

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
│  │  OpenSM wrapper（自研，进程外）       │  │
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

### 21.3 三条红线（不可破）

- **不链接**：不 import OpenSM 库（无 C 头文件 / .so 动态链接）。
- **不分发**：不发布含 OpenSM 二进制的 Docker 镜像 / Helm Chart（容器化但内部调用）。
- **不修改**：用原版 OpenSM + 自研 wrapper，不 fork OpenSM 本身。

### 21.4 法务需出具的内容

1. 法律意见：本隔离方案是否符合 GPL-2.0 mere aggregation 原则？
2. 风险等级：被误解时的法律风险？
3. 替代方案：若风险高，是否走 UFM 商业许可替代？
4. 合规审计：每季度审查 wrapper 是否"无意中"链接/分发 OpenSM。

**节奏**：M2 末法务签字后再启动 OpenSM 集成开发（Phase 4 才编码，但 memo 在 Phase 1 就启动）。

---

## 二十二、NetAI-Bench 评测体系

> 补 v1.0 最大空头指标："幻觉率 ≤ 2%"无评测集就是空话。原方案 Phase 4 才提，**前置到 Phase 1**。

### 22.1 评测集来源（三类）

| 来源 | 数量目标 | 抓取方式 | 难度 |
|---|---|---|---|
| 内部 Postmortem 摘要 | 50 条 | 内部 Git / 工程师录入 | 中（需脱敏） |
| 公开厂商 KB / TAC 案例 | 100 条 | 厂商官网 + GitHub 公开 issue | 低 |
| 人工构造（含跨厂商对比） | 50 条 | 资深工程师出题 | 高 |

**节奏**：Phase 1 首批 50 题；Phase 2 扩至 500 题；Phase 4 对外发布 NetAI-Bench。

### 22.2 题目结构（每条必填字段）

```yaml
id: NSG-Q-0042
title: "ME60 上 OSPF neighbor 反复震荡，疑似 hello 包丢失"
category: troubleshoot  # / config / design / audit / perf
vendor: huawei          # / cisco / h3c / juniper / arista / mellanox / cross
version: VRP-8.180
difficulty: 3           # 1-5
tags: [ospf, hello, crc, optical]

input:
  symptom: "OSPF-5-ADJCHG: Neighbor 1.1.1.2 Down, Hello expired"
  device_info: { model: ME60-X8, version: VRP-8.180, interfaces: [GigabitEthernet0/2/0] }
  evidence:
    - { config_snippet: "[已脱敏]" }
    - { log_lines: ["OSPF-5-ADJCHG ...", "IFNET-4-LINKFAULT ..."] }
  question: "请给出根因假设 + 验证步骤 + 修复方案"

expected_output:
  root_causes:  # ≥3 个，按概率排序
    - { rank: 1, cause: "光模块 CRC 错误导致 hello 丢失", probability: 0.7,
        evidence: ["IFNET-4-LINKFAULT"], verify: "display interface ... | include CRC",
        fix: "更换光模块" }
    - { rank: 2, cause: "hello/dead 计时器不一致", probability: 0.2, ... }
  references:
    - { type: vendor_doc, url: "...", version: "VRP-8.180" }
    - { type: postmortem, id: "PM-2024-117" }

anti_examples:  # 反例：必须识别的错误回答
  - "诊断为配置错误，请删除 OSPF 进程"
  - "请重启设备"

grading_rubric:
  must_have:      [≥1 候选根因, ≥1 验证命令, ≥1 修复命令]
  nice_to_have:   [引用 RAG 文档, ≥3 候选根因, 含回滚命令]
  penalty:        [推荐重启设备, 删除进程, 无证据瞎猜]
```

### 22.3 标注流程

1. 出题（资深工程师 / 你本人）→ 2. 标注（AI 工程师细化 rubric）→ 3. 审校（SRE 验证 verify 步骤可跑）→ 4. 仲裁（不一致第 4 人）→ 5. 入库（标记版本号）。

### 22.4 自动化评测

- **不用 BLEU/ROUGE**（答案不唯一）。
- **LLM-as-judge**：独立 model 按 grading_rubric 逐项打分。
- **盲测**：每月 10 道新题跑 Eval Pipeline，统计 hit_rate / 首过率 / 引用率。
- **月度报告**：标注改进/退化，存档。

### 22.5 对标公开基准

- **NetConfEval**（2025）：LLM 网络配置修复基准，用 Batfish 做 ground truth。
- **NetAgentBench**（2026，State-centric）：状态转换视角评估 agent。
- **CTBench**（Xingyu Yan 2026）：电信级排障基准。
- NetAI-Bench 差异化：**加入 RDMA/IB 场景 + 中文厂商（华为/H3C）+ 三道闸闭环评估**——公开基准都不覆盖。

---

## 二十三、核心指标字典

> 补 v1.0："OTel/Grafana"写了但无指标定义。MVP 先抓 10 个核心。

### 23.1 L1 业务层

| # | 指标 | 含义 | 阈值 | 告警 |
|:--:|---|---|---|---|
| 1 | dag_e2e_p95 | 端到端请求 P95 | <30s | >60s |
| 2 | dag_e2e_success_rate | 端到端成功率 | >95% | <90% |
| 3 | daily_active_users | 日活 | — | 趋势 |
| 4 | user_feedback_score | 点赞率 | >80% | <70% |

### 23.2 L2 Agent 层

| # | 指标 | 含义 | 阈值 | 告警 |
|:--:|---|---|---|---|
| 5 | agent_tool_failure_rate | 工具失败率 | <5% | >10% |
| 6 | agent_interrupt_rate | 人工打断率 | <30% | >50% |
| 7 | agent_token_per_request | 单请求 token | <20k | >50k |
| 8 | agent_self_consistency_passes | Self-Consistency 通过率 | >90% | <80% |

### 23.3 L3 工具层

| # | 指标 | 含义 | 阈值 | 告警 |
|:--:|---|---|---|---|
| 9 | rag_hit_rate | 检索命中率 | >85% | <70% |
| 10 | rag_retrieval_p95 | RAG 检索 P95 | <1.5s | >3s |
| 11 | containerlab_deploy_p95 | 仿真启动 P95 | <60s | >120s |
| 12 | batfish_assert_p95 | Batfish 断言 P95 | <30s | >90s |
| 13 | mcp_server_uptime | MCP 健康 | >99.5% | <99% |

### 23.4 L4 基础设施层

| # | 指标 | 含义 | 阈值 | 告警 |
|:--:|---|---|---|---|
| 14 | k8s_pod_restart_rate | Pod 重启率 | <1/h | >5/h |
| 15 | db_connection_pool | DB 连接池使用率 | <80% | >90% |
| 16 | minio_storage_used | 存储使用率 | <70% | >85% |
| 17 | queue_depth | 任务队列深度 | <100 | >500 |
| 18 | error_budget_burn_rate | 错误预算燃烧率 | <1x | >2x |

### 23.5 仪表盘分组

- **业务大盘**：1-4
- **Agent 视角**：5-10
- **运维大盘**：11-18
- **SRE on-call**：所有超阈值实时视图

**节奏**：MVP 先抓 10 个（1-5、8、9、10、14、17），其余 Phase 2 补。阈值 Phase 1 末按实际数据微调。

---

## 二十四、测试覆盖策略

> 补 v1.0：无测试策略 = 无 SLA。

### 24.1 测试金字塔

```
                     ┌─────────┐
                     │  E2E    │  5%  真实场景
                    /└─────────┘\
                   / ┌─────────┐ \
                  /  │ 集成测试 │  \  25% MCP server、Agent 链路
                 /   └─────────┘   \
                /   ┌───────────┐    \
               /    │  单元测试  │     \  70% 纯函数、工具、schema
              └─────└───────────┘──────┘
```

### 24.2 各层覆盖基线

| 层级 | 目标覆盖率 | 工具 | 强制 |
|---|:---:|---|:---:|
| 单元测试 | ≥80% | pytest / vitest | CI 阻断 |
| 集成测试 | ≥60% | pytest + docker-compose | CI 阻断 |
| E2E 场景 | 100% 关键场景 | pytest + Containerlab | CI 阻断 |
| 契约测试 | 100% MCP schema | schemathesis | CI 阻断 |
| 性能测试 | 关键路径 | k6 / locust | 周跑 |
| 混沌测试 | 每月 1 次 | chaos-mesh | 月跑 |
| 安全测试 | 每月 1 次 | OWASP ZAP + SQLMap | 月跑 |

### 24.3 Phase 1 E2E 关键场景（100% 覆盖）

| 场景 | 入口 | 期望输出 |
|---|---|---|
| BGP 邻居反复震荡 | 症状 + 设备上下文 | 3 候选根因 + Batfish 验证 + 修复命令 |
| OSPF 区域错误 | 升级 OSPF 区域 | Config diff + 仿真 + 部署 |
| VLAN 创建 | 添加 VLAN 100 | 生成 + 仿真 + 审批 + 部署 |
| VXLAN VNI 添加 | 添加 VNI 50000 | 生成 + 仿真 + 审批 + 部署 |
| 静态路由变更 | 修改 next-hop | diff + 仿真 + 审批 + 部署 |
| IPSec 隧道配置 | 描述场景 | 完整 IPSec 配置 + 仿真 + 验证 |
| 配置回滚 | 任意变更 | 7 天内快照回滚成功 |
| 权限拒绝 | operator 越权 | 403 + 审计日志 |

### 24.4 性能基线

- DAG 端到端：P95 <30s, P99 <60s
- RAG 检索：P95 <1.5s
- Batfish 断言（4 节点）：P95 <30s
- Containerlab 启动（4 节点）：P95 <60s
- 并发：50 并发不下降

---

## 二十五、DR / 备份 / RPO / RTO

> 补 v1.0：平台自身高可用完全没写。

### 25.1 备份策略

| 数据 | 频率 | 保留 | 存储 | 加密 |
|---|---|---|---|---|
| PostgreSQL 主库 | 实时 WAL + 每日全量 | 30 天全量 + 7 天 WAL | 异地 OSS | AES-256 |
| Redis | AOF 每秒 | 1 天 | 同机房 | — |
| MinIO（配置快照） | 实时写入 | 7 天在线 + 30 天归档 | 异地 OSS | AES-256 |
| Batfish snapshot | 每次变更 | 90 天 | 同上 | AES-256 |
| pgvector 向量 | 每周全量 | 4 周 | 同上 | AES-256 |
| Git（模板、Prompt） | 实时推送 | 永久 | GitHub / 内部 GitLab | — |

### 25.2 RPO / RTO 目标

| 场景 | RPO | RTO |
|---|:---:|:---:|
| 数据库故障 | <5 min | <30 min |
| 整个 K8s 集群宕 | <15 min | <2 h |
| 整个机房不可用 | <1 h | <8 h |
| 对象存储丢失 | <5 min | <30 min |
| LLM 推理不可用 | N/A（可降级） | <5 min（路由切换） |

**节奏**：Phase 1 可宽松到 RPO 1h / RTO 4h，Phase 2 收紧到上表。

### 25.3 DR 演练

- 每月 1 次：单实例故障切换（kill -9 后自动恢复）。
- 每季度 1 次：机房级故障切换（异地恢复）。
- 每年 1 次：真实断网/断电演练。

### 25.4 备份验证

- 每周自动：随机抽 1 个备份恢复到沙箱，跑完整数据校验。
- 每月人工：资深工程师恢复 1 个变更快照，确认可回滚。

---

## 二十六、MCP Server 自研工作量与部署模式

> 补 v1.0：MCP-First 但没估算自研量，且没说部署模式。

### 26.1 工作量估算

| MCP Server | 官方 MCP? | 复杂度 | 人天 | 阻塞依赖 |
|---|---|:---:|:---:|---|
| Containerlab-MCP | 否 | 中 | 8-10 | Containerlab Python SDK |
| Batfish-MCP | 否（pybatfish 间接） | 中 | 8-10 | pybatfish 文档薄 |
| NAPALM-MCP | 否 | 中 | 6-8 | 多厂商 driver |
| NetBox-MCP | 是（官方） | 低 | 2-3 | 官方 SDK 成熟 |
| Nautobot-MCP | 否 | 中 | 6-8 | Nautobot 文档厚 |
| SUZIEQ-MCP | 否 | 中 | 6-8 | SUZIEQ 文档散 |
| OpenSM-MCP | 否 | 高 | 10-15 | GPL 边界（Phase 4） |
| Prometheus-MCP | 否 | 低 | 3-4 | PromQL 简单 |
| ELK-MCP | 否 | 中 | 5-6 | ES API |
| **Phase 1 合计** | — | — | **28-35** | 2 人 × 2 周 |

### 26.2 单个 MCP Server 工作量分解

- 调研 1-2 天 → Schema 设计 1 天 → Adapter 实现 3-5 天 → 测试 1-2 天 → 文档 0.5-1 天 = **6-10 天/个**。

### 26.3 部署模式（两种必须都支持）

- **sidecar 模式**：与主进程同生命周期，单元测试友好（开发态）。
- **独立部署模式**：K8s Deployment + Service，生产级，独立扩缩容、独立监控（生产态）。

### 26.4 MCP 自身运维

- 每个 MCP server 独立健康检查（纳入第 23 章 mcp_server_uptime 指标）。
- 内存泄漏监控：单 server RSS 超 512MB 告警。
- 版本管理：每个 server 独立版本号 + 兼容性矩阵。
- 凭证：通过 Vault 注入，不落明文。

---

## 二十七、配置模板沉淀机制

> 补 v1.0："Jinja2 模板库"一笔带过，但 6 厂商 × 5 协议 × 3-5 版本 = **150+ 模板**是真正的脏活和商业壁垒。

### 27.1 模板组织结构

```
templates/
├── cisco_iosxe/
│   ├── ospf/
│   ├── bgp/
│   ├── vxlan_evpn/
│   ├── ipsec/
│   └── wireless/
├── huawei_vrp/
│   ├── ospf/
│   ├── bgp/
│   └── ...
├── h3c_comware/
├── juniper_junos/
├── arista_eos/
└── nokia_sros/
```

每层目录下按版本分：`huawei_vrp/ospf/VRP-8.x/area_config.j2`。

### 27.2 模板元数据（每个模板必带）

```yaml
# ospf_area_config.j2.meta.yaml
template_id: huawei_vrp_ospf_area_vrp8
vendor: huawei
os: vrp
version_min: "8.0"
version_max: "8.999"
protocol: ospf
feature: area_config
input_schema:        # Jinja2 入参 JSON Schema
  - { name: area_id, type: int, required: true }
  - { name: interfaces, type: array, required: true }
output_format: cli   # / yang / json
validated_against:   # 验证过的版本
  - VRP-8.180
  - VRP-8.210
author: "你本人"
reviewers: ["AI 工程师", "SRE"]
last_reviewed: 2026-08-21
```

### 27.3 沉淀流程（GitOps）

1. **出题**：工程师从真实项目抽需求 → 写 input + 期望 output。
2. **写模板**：按元数据规范写 .j2 + .meta.yaml。
3. **自测**：本地渲染 + Batfish lint + Containerlab 仿真验证。
4. **PR review**：1 网络工程师 + 1 AI 工程师 + 1 SRE 三方签字。
5. **入库**：合并到 templates 仓库，打版本 tag。
6. **回归**：每次模板改动自动跑全量回归测试（Batfish + Containerlab）。

### 27.4 模板覆盖率目标

| 阶段 | 厂商 | 协议覆盖 | 模板数 |
|---|---|---|---|
| Phase 1 | Cisco IOS-XE + 华为 VRP | OSPF/BGP | ~30 |
| Phase 2 | + H3C/Juniper/Arista | + VXLAN-EVPN/VPN | ~80 |
| Phase 3 | 全 6 厂商 | + 无线/IPSec | ~150 |
| Phase 4 | + Mellanox Onyx | + RoCE/IB | ~200 |

### 27.5 模板与 RAG 的关系

- 模板库本身是 RAG L4 内部资产的核心语料。
- ConfigGen Agent 生成时：RAG 检索匹配模板 → 渲染 → Batfish 校验。
- **模板是"标准答案"，Agent 是"翻译器"**——符合"AI 翻译不作裸推理"原则。

---

## 二十八、商业化路线图

> 补 v1.0 最大战略盲区：原方案是"给工程师看的文档"，不是给 CEO/投资人/销售看的。

### 28.1 客户为什么买 NetSage

| 对比 | Forward Networks | Selector AI | Cisco DNA | 华为 NCE | **NetSage** |
|---|---|---|---|---|---|
| RDMA/IB 支持 | ❌ | ❌ | 部分 | ❌ | ✅（护城河） |
| 仿真强制门禁 | ❌ | ❌ | ❌ | ❌ | ✅ 三道闸 |
| 国产化 LLM | ❌ | ❌ | ❌ | 部分 | ✅ DeepSeek/Qwen |
| MCP-First | ❌ | ❌ | ❌ | ❌ | ✅ |
| 多 Agent 协同 | 部分 | 部分 | 部分 | 部分 | ✅ LangGraph |
| 中文厂商深度 | 弱 | 弱 | 中 | 强 | ✅ 强 |
| 开源底座透明 | ❌ | ❌ | ❌ | ❌ | ✅ Nautobot App |

### 28.2 目标客户分层

| 层级 | 客户画像 | 痛点 | 优先级 |
|---|---|---|---|
| **T1 AI 训练集群** | 大模型/智算中心 | RDMA 调优、无损网络 | P0（差异化最强） |
| **T2 金融/运营商** | 两地三中心、关基 | 合规、审计、变更安全 | P1 |
| **T3 互联网 DC** | 大规模数据中心 | VXLAN fabric、多厂商 | P1 |
| **T4 政府国产化** | 信创要求 | 国产 LLM、私有化 | P2 |
| **T5 企业园区** | 中小规模 | 无线、VPN | P3 |

### 28.3 定价模型（三档）

| 档位 | 形态 | 定价 | 适用 |
|---|---|---|---|
| **社区版** | 开源 MCP server + 拓扑模板 | 免费 | 社区引流、生态占位 |
| **专业版** | 闭源平台 + 单租户 | 按设备数：¥500-2000/设备/年 | T3/T5 |
| **企业版** | 多租户 + SSO + RDMA + 私有化 | 按场景：30-100 万/年 | T1/T2/T4 |

**LLM Token 成本**：企业版按租户计费，专业版含基础额度超额自付（与第十七章运行态成本对齐）。

### 28.4 销售周期与售前 demo

- 销售周期：T1/T2 约 3-6 个月，T3/T5 约 1-3 个月。
- 售前 demo 必备三场景：
  1. RDMA 集群 AI 优化（差异化）
  2. 数据中心 VXLAN fabric 规划（刚需）
  3. BGP 故障自动诊断→修复→验证闭环（三道闸）

### 28.5 客户成功指标（商业北极星）

| 指标 | 目标 |
|---|---|
| 续约率 | ≥85% |
| NPS | ≥40 |
| PoC 转化率 | ≥30% |
| 单客户 LTV / CAC | ≥3 |

### 28.6 开源与社区策略（与 v1.0 第十六章对齐）

- 核心编排 + Agent + UI 闭源；MCP server + Containerlab 拓扑模板开源。
- v1.0 发布同期启动 `awesome-network-ai` 索引 + NetAI-Bench 数据集。

---

## 二十九、LLM 多模型路由与降级策略

> 补 v1.0：DeepSeek 为主但没说主备切换、降级路径。把"主模型"改为"默认模型"。

### 29.1 模型分层路由

| 任务难度 | 默认模型 | 兜底 | 场景 |
|---|---|---|---|
| 简单问答/命令查询 | DeepSeek-V3 | Qwen | 成本最低 |
| 复杂推理/架构设计 | DeepSeek-R1 | Claude Sonnet | 推理强 |
| 代码/配置生成 | DeepSeek-V3 | Claude Sonnet | 代码能力 |
| 报告/文档生成 | DeepSeek-V3 | GPT 系 | 长文本 |
| 中文国产化场景 | Qwen | DeepSeek | 合规 |

### 29.2 降级路径

```
DeepSeek 主路径
   │ 超时/限流/降级
   ▼
LiteLLM 网关自动切换（<5s）
   │
   ├──→ Claude 兜底（重度推理）
   ├──→ GPT 兜底（少数场景）
   └──→ Qwen 兜底（国产化）
```

### 29.3 API 配额合约（Plan B）

- **必须签 2-3 家 API 配额合约**，避免单一厂商限流/涨价卡脖子。
- DeepSeek 官方 + OpenRouter 聚合 + Claude 直签 + GPT 直签，四入口。
- 每家配额阈值监控，超 70% 用量告警。

### 29.4 成本控制

- 难度路由：简单问答走小模型省钱。
- 缓存：相同 query + 上下文 hash 命中缓存（Redis）。
- Token 预算：单请求超 50k token 告警（第 23 章指标 7）。

### 29.5 高敏感场景私有化

- 网关同一接口，保留切换私有化兼容模型能力（Qwen2.5 本地部署）。
- **Phase 1 不做私域部署**，但架构预留接口——高敏感客户走黑盒路由（第二十章 Layer 3）。

---

## 三十、Agent 运行时适配层

> 补 v1.0 风险表已提"封装 agent_runtime 适配层"，但没说怎么评估替代品。保留 LangGraph 可替换性，不锁死单框架。

### 30.1 适配层设计

```
┌─────────────────────────────────────┐
│  Agent 定义（可移植中间格式）         │
│  - role / system_prompt / tools      │
│  - state_schema (JSON Schema)        │
│  - transitions (DAG 描述)             │
│  - interrupt_points                  │
└──────────────────┬──────────────────┘
                   │
         ┌─────────▼─────────┐
         │  agent_runtime     │  ← 适配层
         │  (LangGraph 后端)  │
         └─────────┬─────────┘
                   │
            ┌──────▼──────┐
            │  LangGraph   │  当前实现
            └─────────────┘
                   │ 未来可替换
            ┌──────▼──────┐
            │  CrewAI /    │
            │  AutoGen /   │
            │  自研 SG      │
            └─────────────┘
```

### 30.2 可移植中间格式

所有 Agent 定义写成框架无关的 JSON/YAML：
- `role` / `system_prompt` / `tools`（工具名引用，不绑定框架 Tool 类）
- `state_schema`（JSON Schema 描述状态结构）
- `transitions`（DAG：节点 → 节点 + 条件）
- `interrupt_points`（HITL 强制点）

### 30.3 替代品评估矩阵

| 框架 | 优势 | 劣势 | 何时评估 |
|---|---|---|---|
| LangGraph（当前） | 状态机成熟、MIT、生态稳 | v0.x→v1.0 breaking change 风险 | 现状保持 |
| CrewAI | 角色协作直观 | 状态管理弱 | Phase 2 末 |
| AutoGen | 多 Agent 对话强 | 微软主导、许可证风险 | Phase 3 |
| 自研 StateGraph | 完全可控 | 工作量大 | 仅作最后兜底 |

**评估触发**：LangGraph 出重大 breaking change，或 agent_runtime 适配层成本 > 自研。

### 30.4 隔离原则

- Agent 业务逻辑只依赖 `agent_runtime` 接口，**不直接 import LangGraph API**。
- LangGraph 特有功能（如 interrupt_before）在适配层封装为通用 `interrupt(point)` 调用。
- 单元测试针对中间格式，集成测试才跑具体后端。

---

## 三十一、功能优先级矩阵与交付节奏（不降级版）

> **替代 v1.0 "不降级原则"的模糊表述**。不是"什么能砍"，而是"什么必须保留 + Phase 内部如何排序"。所有能力仍属 v1.0 scope，不删除。

### 31.1 优先级三档定义

- **核心**：该 Phase 结束前没完成 → Phase 不算通过。
- **重要**：可推迟到下一 Phase，但本 Phase 必须有"启动迹象"。
- **延后**：v1.0 之后（v1.1/v1.2），**不写入 v1.0 验收标准**。

### 31.2 矩阵

| 能力 | P1 | P2 | P3 | P4 | v1.1+ |
|---|:---:|:---:|:---:|:---:|:---:|
| MCP Gateway + 3 server | 核心 | 继承 | 继承 | 继承 | — |
| 三道闸（仿真+校验+审批） | 核心 | 继承 | 继承 | 继承 | — |
| LLM 网关 + DeepSeek + 兜底 | 核心 | 继承 | 继承 | 继承 | — |
| 数据脱敏过滤器 | 核心 | 继承 | 继承 | 继承 | — |
| 审计日志 + 不可篡改 | 核心 | 继承 | 继承 | 继承 | — |
| Web Console MVP | 核心 | 继承 | 继承 | 继承 | — |
| RAG 知识库（1 厂商） | 核心 | 继承 | 继承 | 继承 | — |
| NetAI-Bench 评测集（50题） | 核心 | 扩500 | 继承 | 对外发布 | — |
| NetBox 集成（包装） | — | 核心 | 继承 | 继承 | — |
| SUZIEQ 集成 | — | 核心 | 继承 | 继承 | — |
| 多厂商（H3C/Juniper/Arista） | — | 重要 | 核心 | 继承 | — |
| Troubleshooter 完整闭环 | — | 重要 | 核心 | 继承 | — |
| Nautobot 集成 + 自研 App | — | — | 核心 | 继承 | — |
| SecurityAuditor + Batfish ACL | — | — | 核心 | 继承 | — |
| 全量 RBAC + SSO | — | — | 重要 | 核心 | — |
| Helm/Operator 化部署 | — | 重要 | 重要 | 核心 | — |
| OpenSM 容器化 | — | — | — | 核心 | — |
| RdmAgent（自研，护城河） | — | — | — | 核心 | — |
| WirelessAgent | — | — | — | 重要 | 延后 |
| 多租户 SaaS | — | — | — | 重要 | 延后 |
| 商业化路线图落地 | — | — | — | 核心 | — |

### 31.3 Phase 1 内部交付节奏（M1-M2）

> 采纳 04-review "超最小演示"建议作为 Phase 1 第一个里程碑，**不替代 Phase 1，而是 Phase 1 的前 2 周**。

| 周次 | 里程碑 | 产出 |
|---|---|---|
| W1-W2 | **超最小演示**（能跑 > 好看） | CLI nsc + 1 ConfigGen Agent + Batfish 校验 + Containerlab 2 节点 BGP 仿真 + report.md |
| W3-W4 | MCP Gateway + 脱敏过滤器 | 3 MCP server + Layer1/3 脱敏 |
| W5-M1末 | LangGraph 编排 + 评测集首批 | Planner→ConfigGen→Validator DAG + 50 题评测集 |
| M2 | Web Console MVP + 审批流 + 快照 | 12/12 验收达标 |

### 31.4 与 v1.0 路线图的对齐

v1.0 第十四章的 Phase 1-4 里程碑**全部保留**，本节只补充：
- 每 Phase 内部增加"超最小演示"前置里程碑（2 周）。
- 每 Phase 末按第十九章 12 条验收标准判定。
- Kill Criteria 作为应急安全网，正常路径不触发。

---

## 附录：事实修正与引用补证

### A.1 NetAgentBench / CTBench 引用补证

> 修正 NetSage-Review-v1.0 P1-5 的"未找到公开资料"误判。

| 项目 | 来源（hermes-01-survey.md 第 73-80 行已引用） |
|---|---|
| **NetAgentBench** | "NetAgentBench: A State-Centric Benchmark for Evaluating Agentic Network Configuration", 2026，State-centric 评估 agent |
| **CTBench** | Xingyu Yan, 2026，"CTBench: Evaluating Troubleshooting Capabilities of AI Agents in Realistic Telecom Networks" |
| **NetConfEval** | 2025，"NetConfEval: Benchmarking LLM-Driven Network Configuration Repair"，用 Batfish 做 ground truth |

**结论**：三个基准均可核实，v1.0 引用合规。NetAI-Bench 差异化见第二十二章 22.5。

### A.2 Batfish 规格修正

> 修正 04-review 把"1vCPU/2GB 起步"误判为生产规格。

- v1.0 原文："容器隔离（1vCPU/2GB 起步）"——**起步规格**，非生产规格。
- 生产规格明确：**≥8GB RAM + JVM 调优**，并发多拓扑建议 16GB+（见第十七章 17.4）。

### A.3 "竞品完全缺失 RDMA"表述修正

> 04-review 指出 Forward Networks 不做 ≠ 没有（华三 iMC 部分场景支持）。

- v1.0 第十六章表述"竞品完全缺失"略绝对。
- 修正为：**"主流竞品（Forward/Selector/Cisco DNA/华为 NCE）均无完整 RDMA/IB 全栈管理能力"**——Cisco Nexus Dashboard 有部分无损网络监控，但不覆盖 OpenSM/IB 子网管理。

### A.4 DeepSeek SLA 表述修正

> 04-review 称"DeepSeek 2025 多次降级"未核实。

- 表述修正为：**"DeepSeek 作为默认模型，SLA 低于 Claude/GPT；通过多模型降级路径（第二十九章）兜底"**，不引用未核实的降级次数。

---

## 变更日志

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v1.0 | 2026-08-20 | 合并 5 份文档的最终技术方案 | 架构组 |
| v1.1 | 2026-08-21 | 增量补全 15 章（第十七至三十一）+ 附录：预算/团队/验收/脱敏/法务/评测/指标/测试/DR/MCP工作量/模板沉淀/商业化/LLM降级/agent_runtime/优先级矩阵/事实修正 | 架构组 |

---

> v1.1 增量文档完结。与 v1.0 合并即为可执行的完整技术方案。
