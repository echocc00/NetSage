# NetSage · v0.1.1-v0.1.3 内容交付规范

> 本文档说明 v0.1.0 三个遗留 TODO 需要哪些内容、用途、来源、格式。
> 你按此文档准备内容，我负责 ingest / 校验 / 评测 / 并入发布。
> 文档版本：v1.0 · 日期：2026-08-23

---

## 总览

| 版本 | 任务 | 内容类型 | 工作量预估 | 阻塞点 |
|---|---|---|---|---|
| v0.1.1 | P2-5 多厂商模板库扩展 ~80 | Jinja2 模板 + meta.yaml | 你出参数规则，我渲染 | 无 |
| v0.1.2 | P2-11 排障闭环 3 场景 | YAML 评测题 | 你出 3 场景题 | 无 |
| v0.1.3 | P2-13 RAG 500 题 + hit_rate≥85% | 厂商手册原文 + 评测题 | 你提供手册 + 出题 | 手册授权 |

**分工原则**：你提供领域内容（网络专业知识），我负责工程化（模板渲染/题库校验/RAG ingest/评测打分）。

---

## v0.1.1 — 多厂商模板库扩展（~80 模板）

### 1.1 用途

ConfigEngineer Agent 生成配置时调用模板渲染（而非 LLM 裸生成命令，v2.0 安全边界）。
当前 10 模板（5 厂商 × 2 协议 BGP/OSPF），目标 ~80（5 厂商 × 5 协议 × 1-2 feature）。

### 1.2 当前状态

已有 10 模板骨架（`backend/templates/<vendor>/<protocol>/<feature>.j2` + `.meta.yaml`）：

```
backend/templates/
├── huawei_vrp/    bgp/peering.j2 + ospf/area_config.j2
├── cisco_iosxe/   bgp/peering.j2 + ospf/area_config.j2
├── h3c_comware/   bgp/peering.j2 + ospf/area_config.j2
├── juniper_junos/ bgp/peering.j2 + ospf/area_config.j2
└── arista_eos/    bgp/peering.j2 + ospf/area_config.j2
```

### 1.3 需要扩展的协议矩阵

每厂商补齐这 5 个协议（现有 BGP/OSPF 已就绪，补 VXLAN/VPN/接口/静态路由）：

| # | 协议 | feature | 优先级 | 模板数 |
|---|---|---|---|---|
| 1 | bgp | peering / rr（Route Reflector） | 已有 peering，补 rr | +5 |
| 2 | ospf | area_config / interface | 已有 area，补 interface | +5 |
| 3 | vxlan | evpn_l2vpn / anycast_gateway | **新增** | +10 |
| 4 | vpn | ipsec_site2site / ssl_remote | **新增** | +10 |
| 5 | 接口 | vlan / trunk / 静态路由 | **新增** | +15 |
| 6 | wireless | ssid / roaming（仅 Cisco/H3C/Huawei） | **新增** | +3 |

**目标总数**：~80（现有 10 + 新增 ~70）

### 1.4 内容格式（你需提供）

每个模板 = 2 个文件，放同一目录：

#### 文件 1：`<feature>.j2`（Jinja2 模板）

```jinja2
bgp {{ local_asn }}
{% if router_id is defined and router_id %}
  router-id {{ router_id }}
{% endif %}
{% for peer in peers %}
  peer {{ peer.address }} as-number {{ peer.remote_asn }}
{% if peer.description is defined and peer.description %}
  peer {{ peer.address }} description {{ peer.description }}
{% endif %}
{% endfor %}
{% if ebgp_multihop is defined and ebgp_multihop %}
  peer {{ peers[0].address }} ebgp-max-hop {{ ebgp_multihop }}
{% endif %}
```

#### 文件 2：`<feature>.j2.meta.yaml`（元数据）

```yaml
template_id: huawei_vrp_bgp_peering        # 唯一 ID：<vendor>_<protocol>_<feature>
vendor: huawei                              # huawei/cisco/h3c/juniper/arista
os: vrp                                     # vrp/iosxe/comware/junos/eos
version_min: "8.0"                          # 适用版本下限
version_max: "8.999"                        # 适用版本上限
protocol: bgp                               # bgp/ospf/vxlan/vpn/wireless/roce
feature: peering                            # 功能名
input_schema:                               # Jinja2 入参（JSON Schema 风格）
  - { name: local_asn, type: int, required: true }
  - { name: router_id, type: string, required: true }
  - { name: peers, type: array, required: true,
      items: { address: string, remote_asn: int, description: string } }
  - { name: ebgp_multihop, type: int, required: false }
  - { name: import_strategy, type: string, required: false,
      enum: [static, connected, ospf] }
output_format: cli                          # cli / netconf / json
validated_against: []                       # 仿真验证过的版本（我填）
author: ""                                  # 你填姓名/工号
reviewers: []                               # review 人（我 + 你）
last_reviewed: ""                           # 我填
```

### 1.5 你需要做什么

**对每个模板提供**：
1. **该厂商该协议的真实配置语法**（华为 VRP / Cisco IOS-XE / H3C Comware / Juniper Junos / Arista EOS 各自语法不同）
2. **入参 schema**（哪些字段是变量，类型，是否必填，枚举值）
3. **版本适用范围**（如华为 VRP 8.x 与 5.x 语法差异）

**你不用写 Jinja2**——你给我"配置示例 + 参数说明"，我转成 `.j2 + .meta.yaml`。

### 1.6 提供形式（推荐 3 选 1）

| 形式 | 优点 | 示例 |
|---|---|---|
| **A. Markdown 表格**（推荐） | 结构清晰，我易转码 | 见下方模板 |
| B. 直接写 .j2 + .meta.yaml | 最精确，但需你懂 Jinja2 | 见 1.4 |
| C. 厂商配置示例贴出来 | 最省事，我反推参数 | 贴一段真实 running-config |

#### 推荐形式 A 的填写模板

```markdown
## 模板：huawei_vrp_vxlan_evpn_l2vpn

**配置示例**（目标输出）：
```
bridge-domain 10
  vxlan vni 10010
evpn
  vpls-advertise-local
interface Vlanif10
  ip address 10.1.1.1 24
```

**参数**：
| 参数名 | 类型 | 必填 | 说明 | 示例值 |
|---|---|---|---|---|
| bd_id | int | 是 | bridge-domain ID | 10 |
| vni | int | 是 | VXLAN VNI | 10010 |
| vlanif_ip | string | 是 | VLAN 接口 IP/掩码 | 10.1.1.1/24 |

**版本**：VRP 8.0 - 8.999
```

### 1.7 内容来源

- **厂商官方配置指南**（华为信息大厦 / Cisco Docs / H3C 官网 / Juniper TechLibrary / Arista EOS Manual）
- 你已有的配置基线 / 项目模板
- 内部 Postmortem 中的配置片段（脱敏后）

### 1.8 交付节奏

建议分批，每批 10-15 个模板：
- 第 1 批：VXLAN EVPN（5 厂商 × 2 feature = 10）
- 第 2 批：IPsec VPN（5 厂商 × 2 feature = 10）
- 第 3 批：接口/VLAN/静态路由（5 厂商 × 3 feature = 15）
- ... 依此类推

每批交付后我跑渲染测试 + Batfish 校验，通过的标 `validated_against`。

---

## v0.1.2 — 排障闭环 3 场景评测题

### 2.1 用途

验收 RCA 引擎 + Troubleshooter Agent 在 3 个典型场景的端到端能力（v2.0 19.2 验收 2）。
当前评测集仅 10 题（骨架），需补 3 个完整场景题。

### 2.2 需要的 3 个场景

| # | 场景 | 协议 | 症状 | 根因候选（≥3） |
|---|---|---|---|---|
| 1 | BGP 邻居抖动 | bgp | `BGP-5-ADJCHG: Neighbor Down` | hello 计时器 / MTU / CRC / 路由策略 |
| 2 | OSPF 邻居震荡 | ospf | `OSPF-5-ADJCHG: Hello expired` | 网络类型 / MD5 mismatch / MTU / CRC |
| 3 | VXLAN EVPN Type-2 不通 | vxlan | 跨 Leaf 通信异常 | BGP EVPN 邻居 / VNI / anycast-gateway / ARP suppress |

### 2.3 内容格式（YAML，单文件单题）

文件名：`eval/dataset/NSG-Q-XXXX.yaml`（XXXX 顺延 0011 起）

```yaml
id: NSG-Q-0011
title: "BGP 邻居抖动（华为 VRP-8.180，hello 计时器不一致）"
category: troubleshoot              # troubleshoot/config/design/audit/perf
vendor: huawei                       # huawei/cisco/h3c/juniper/arista/mellanox/cross
version: VRP-8.180
difficulty: 3                        # 1-5
tags: [bgp, hello, timer, flap]

input:
  symptom: "BGP-5-ADJCHG: Neighbor 10.1.1.2 Down, Hello expired"
  device_info:
    model: CE12800
    version: VRP-8.180
    interfaces: [10GE1/0/1]
  evidence:
    - config_snippet: |
        bgp 65001
          peer 10.1.1.2 as-number 65002
          peer 10.1.1.2 timer 10 30    # 本端
    - log_lines:
        - "BGP-5-ADJCHG: Neighbor 10.1.1.2 Down, Hello expired"
        - "对端配置：peer 10.1.1.1 timer 20 60"
  question: "给出根因假设 + 验证步骤 + 修复方案"

expected_output:
  root_causes:                        # ≥3 个，按概率排序
    - rank: 1
      cause: "BGP hello/hold 计时器两端不一致"
      probability: 0.7
      evidence: ["本端 timer 10 30 vs 对端 20 60"]
      verify: "display bgp peer 10.1.1.2 | include Timer"
      fix: "对齐两端 neighbor timer（建议 10 30）"
    - rank: 2
      cause: "MTU 不一致导致大包丢失"
      probability: 0.2
      verify: "display interface 10GE1/0/1 | include MTU"
      fix: "对齐两端 MTU"
    - rank: 3
      cause: "CRC 错误导致 hello 丢包"
      probability: 0.1
      verify: "display interface 10GE1/0/1 | include CRC"
      fix: "更换光模块/线缆"
  references:
    - type: vendor_doc
      url: https://support.huawei.com/vrp-bgp
      version: VRP-8.180

anti_examples:                       # 反例：必须识别的错误回答
  - "诊断为配置错误，请删除 BGP 进程"
  - "请重启设备"

grading_rubric:
  must_have:      ["≥1 候选根因", "≥1 验证命令", "≥1 修复命令"]
  nice_to_have:   ["引用 RAG 文档", "≥3 候选根因", "含回滚命令"]
  penalty:        ["推荐重启设备", "删除进程", "无证据瞎猜"]
```

### 2.4 你需要做什么

**每个场景提供**：
1. **症状描述**（真实日志/告警格式，如 `BGP-5-ADJCHG` / `OSPF-5-ADJCHG`）
2. **设备信息**（型号、版本、涉及接口）
3. **证据**（配置片段 + 日志行，**已脱敏**——IP 用 10.x，主机名用 spine01）
4. **≥3 候选根因**（按概率排序，含验证命令 + 修复方案）
5. **反例**（常见错误诊断）
6. **评分标准**（must_have / nice_to_have / penalty）

### 2.5 校验规则（我跑 schema.py 校验）

| 字段 | 规则 |
|---|---|
| category | troubleshoot（这 3 题都是） |
| vendor | huawei/cisco/h3c/juniper/arista/cross |
| difficulty | 1-5 整数 |
| input.symptom | 必填 |
| input.question | 必填 |
| expected_output.root_causes | ≥3 个 |
| 每个 root_cause | 必须含 verify + fix |

### 2.6 内容来源

- 你处理过的真实故障 Case（脱敏后，IP/主机名/拓扑替换）
- 厂商 KB / TAC 案例
- 网络经典故障案例集（如 Cisco/Huawei community）

### 2.7 提供形式

直接按 2.3 格式写 YAML 文件给我（3 个文件），或先用 Markdown 写内容我转 YAML。

---

## v0.1.3 — RAG 500 题 + hit_rate ≥85%

### 3.1 用途

RAG 知识库语料 + 评测题，让 Agent 检索厂商手册准确率 ≥85%（v2.0 19.2 验收 5）。
当前语料 0（骨架已就绪），评测题 10。

### 3.2 需要的两部分内容

#### Part A：厂商手册语料（你提供原文，我 ingest）

| 厂商 | 手册 | 格式 | 预估量 |
|---|---|---|---|
| 华为 VRP 8.x | 配置指南（BGP/OSPF/VXLAN/VPN/接口） | PDF / 网页导出 Markdown | ~2000 chunk |
| Cisco IOS-XE 17.x | Configuration Guides | PDF / HTML | ~1500 chunk |
| H3C Comware 7 | 配置指导 | PDF / CHM | ~1000 chunk |

**ingest 管线已就绪**（`backend/app/rag/ingest.py`），四级分块：特性→场景→命令→注意事项，每块 ≤1500 token。

#### Part B：评测题 500 道（你出题，我跑 hit_rate）

500 题分布：

| 类别 | 数量 | 协议覆盖 |
|---|---|---|
| troubleshoot | 150 | BGP/OSPF/VXLAN/VPN 各 ~30 |
| config | 150 | 5 厂商 × 5 协议 |
| design | 80 | 拓扑规划/选型/BOM |
| audit | 80 | 安全基线/ACL/合规 |
| perf | 40 | RDMA/RoCE/性能调优 |

### 3.3 Part A 手册格式（你提供）

#### 推荐格式：Markdown（最佳）

```
doc/vendor-manuals/
├── huawei/
│   ├── vrp-8.180-bgp-配置指南.md
│   ├── vrp-8.180-ospf-配置指南.md
│   ├── vrp-8.180-vxlan-配置指南.md
│   └── ...
├── cisco/
│   └── iosxe-17-config-bgp.md
└── h3c/
    └── comware-7-ospf.md
```

**Markdown 结构要求**（让 chunker 正确分块）：

```markdown
# BGP 配置

## 1.1 BGP 基本配置

### 建立邻居

命令：
```
bgp { as-number-plain | as-number-dot }
  peer { ipv4-address | group-name } as-number { as-number-plain | as-number-dot }
```

**参数说明**：
- as-number-plain：AS 号（整数格式）
- ipv4-address：对端 IP

**注意事项**：
- 两端 AS 号必须匹配
- 建议配置 BGP 认证（password）
```

#### 也接受

- **PDF**：我用 pdfplumber 转 Markdown（但表格/图会丢失，建议关键章节手动导出 MD）
- **HTML**：网页 `Ctrl+S` 保存后我清洗
- **CHM**：先转 HTML 再处理

### 3.4 Part B 评测题格式

与 v0.1.2 相同的 YAML schema（见 2.3），但 500 题量大，建议分批：

| 批次 | 数量 | 类别 |
|---|---|---|
| 1 | 50 | troubleshoot（复用 v0.1.2 的 3 场景扩展） |
| 2 | 100 | config（对应 v0.1.1 的 80 模板） |
| 3 | 100 | troubleshoot + design |
| 4 | 150 | audit + perf + 补齐 |

### 3.5 hit_rate 评测流程（我负责）

```
你出题 → 我 ingest 手册 → 跑每题 RAG 检索 → 检查 top-K 是否命中预期 references
→ 统计 hit_rate = 命中题数 / 总题数 → <85% 我调参（同义词/HyDE/重排序）
```

### 3.6 你需要做什么

**Part A（手册）**：
1. 确认手册授权（华为/Cisco 官方手册是否可内部使用——通常可，但不可公开再分发）
2. 导出 Markdown（华为信息大厦 → 配置指南 → 导出；Cisco Docs → Print → 保存）
3. 放 `doc/vendor-manuals/<vendor>/` 目录

**Part B（出题）**：
1. 按批次出题（每题一个 YAML 文件）
2. 每题标 `references.url` 指向手册章节（hit_rate 评测锚点）

### 3.7 内容来源

| 内容 | 来源 |
|---|---|
| 华为手册 | https://support.huawei.com/enterprise/（需华为账号） |
| Cisco 手册 | https://www.cisco.com/c/en/us/support/index.html |
| H3C 手册 | https://www.h3c.com/cn/Service/Document_Center/ |
| 出题素材 | 内部 Postmortem（脱敏）/ 厂商 KB / 项目实战经验 |

### 3.8 授权注意

- 厂商手册**版权属厂商**：NetSage 仓库**不提交手册原文**（.gitignore 已排除 `doc/vendor-manuals/`）
- 仅 ingest 到本地 pgvector，RAG 检索结果供 Agent 内部使用
- 评测题**不引用手册原文段落**，只标 URL 锚点

---

## 交付节奏建议

| 时间 | 交付 | 版本 |
|---|---|---|
| 第 1 周 | v0.1.1 第 1 批模板（VXLAN 10 个） | v0.1.1-alpha |
| 第 2 周 | v0.1.1 第 2-3 批 + v0.1.2 3 场景题 | v0.1.1 + v0.1.2 |
| 第 3 周 | v0.1.3 Part A 手册（华为首发） | v0.1.3-alpha |
| 第 4-5 周 | v0.1.3 Part B 出题（分批）+ hit_rate 调参 | v0.1.3 |

**最小可行交付**：v0.1.1（VXLAN+VPN 20 模板）+ v0.1.2（3 场景题）即可发 v0.1.1 版本，v0.1.3 可独立迭代。

---

## 联系方式

内容准备好后：
1. 放对应目录（模板 `backend/templates/`、题库 `eval/dataset/`、手册 `doc/vendor-manuals/`）
2. 告知我，我跑校验 + 评测 + 并入发布
3. 不确定格式时，先给 1 个样本我确认后再批量

---

## 变更日志

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-08-23 | 首版交付规范 |
