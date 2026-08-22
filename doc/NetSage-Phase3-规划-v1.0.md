# NetSage · Phase 3 规划与详细设计 v1.0

> 基线：`NetSage-最终技术方案-v2.0.md` + `NetSage-开发计划与详细设计-v1.0.md` + `NetSage-Phase2-规划-v1.0.md`
> 前置：Phase 2 核心 10/14 完成，端到端验收 12/12 通过（187 单元测试）；NetBox/SUZIEQ/Deploy/RCA/Troubleshooter/Observer 六大能力落地
> 文档版本：v1.0 · 日期：2026-08-23
> 覆盖：Phase 3（M5-M6，8 周）目标、逐周里程碑、模块详细设计、依赖、风险

---

## 目录

- [一、Phase 3 目标与验收标准](#一phase-3-目标与验收标准)
- [二、Phase 2 基线盘点（Phase 3 起点）](#二phase-2-基线盘点phase-3-起点)
- [三、逐周里程碑（M5-M6）](#三逐周里程碑m5-m6)
- [四、模块详细设计](#四模块详细设计)
  - [4.1 Nautobot 双适配器 + 自研 App v0.1](#41-nautobot-双适配器--自研-app-v01)
  - [4.2 SecurityAuditor + 基线规则库](#42-securityauditor--基线规则库)
  - [4.3 Batfish ACL 分析（Cisco + 华为）](#43-batfish-acl-分析cisco--华为)
  - [4.4 ComplianceAgent + 合规报告](#44-complianceagent--合规报告)
  - [4.5 自动化闭环编排（≥30%）](#45-自动化闭环编排30)
  - [4.6 三道闸全量落地 + RBAC/审计完善](#46-三道闸全量落地--rbac审计完善)
- [五、任务拆解与依赖](#五任务拆解与依赖)
- [六、风险与对策](#六风险与对策)

---

## 一、Phase 3 目标与验收标准

### 1.1 目标（v2.0 第十四章 §Phase 3）

**Nautobot 深度集成 + 安全合规 + 自动化闭环**：从 Phase 2 的"多厂商 + 数据闭环 + 排障链路"扩展到"双 SSoT 底座 + 安全审计 + 故障自动诊断→修复→验证→下发全自动闭环"。

### 1.2 验收标准（v2.0 十九章 19.3 + 里程碑表）

| # | 验收项 | 指标 | 验证方式 |
|---|---|---|---|
| 1 | Nautobot 双适配器 | `SourceOfTruth` 接口跑通 NetBox + Nautobot 两套 | 同一业务调用可切换 adapter，设备/拓扑/IPAM 读取一致 |
| 2 | 自研 Nautobot App v0.1 | `NetworkDesign` model 持久化 AI 设计方案 | ConfigEngineer 生成方案 → 存入 Nautobot → 前端可查历史 |
| 3 | SecurityAuditor | 基线规则库 ≥30 条（CIS + 厂商加固）+ 扫描器 | Cisco IOS-XE + 华为 VRP 各跑 1 台，输出合规得分 |
| 4 | Batfish ACL 分析 | reachability + shadowed/unused ACL 断言 | ≥2 厂商各 1 真实配置，输出冗余/可达性报告 |
| 5 | ComplianceAgent | 合规报告生成（Markdown + CSV） | 端到端：采集→基线→ACL→报告 |
| 6 | 自动化闭环 | BGP 故障自动诊断→修复→验证→审批→下发，自动化率 ≥30% | 3 场景闭环 demo，统计人工介入步骤占比 |
| 7 | 三道闸全量 | 审批流 + 快照回滚 + RBAC/审计完整 | 端到端变更全程审计哈希链，四级 RBAC 强制门禁 |

### 1.3 不做（Phase 4 范围）

- RDMA Fabric / PartitionKey 等 Nautobot App model（Phase 4 RdmAgent 起来再做，YAGNI）
- 攻击面分析 / CVE 库 / PDF 报告导出（Phase 4 安全增强）
- OpenSM / RdmAgent / WirelessAgent（Phase 4）
- 多租户 + SSO（Phase 4 生产化）

### 1.4 降级路径（hermes-03）

- 自研 App 若 W4 前未跑通 → 砍 App，仅保留 `NautobotAdapter`，App 推迟 v1.1。
- 自动化率若 <10% → 聚焦 NetBox 主线 + 安全合规，闭环标 v1.1（**仅应急**）。

---

## 二、Phase 2 基线盘点（Phase 3 起点）

| 已有能力 | Phase 3 复用方式 |
|---|---|
| `SourceOfTruth` Protocol + `NetBoxAdapter` | 新增 `NautobotAdapter` 实现同一接口，业务层零改切换 |
| 6 Agent（planner/config_engineer/validator/troubleshooter/deploy/observer） | 新增 `security_auditor` / `compliance` 两个 Agent 注册到同一 runner |
| RCA 引擎 + Troubleshooter | 自动化闭环的"诊断"环节直接复用 |
| DeployAgent + checkpoint + 回滚 | 自动化闭环的"下发"环节直接复用 |
| 三道闸（simulation/validation/approval）+ snapshot/impact | 全量落地：审批流完善 + 快照回滚补全 + RBAC 强制门禁 |
| Batfish MCP（containerlab-mcp/batfish-mcp/napalm-mcp/netbox-mcp/suzieq-mcp） | 新增 `nautobot-mcp`，batfish-mcp 扩展 ACL 断言 |
| 数据脱敏 Layer1/3 + 审计哈希链 | 安全合规扫描结果默认接入审计 |
| React 前端（6 页面 + 登录 + React Flow） | 新增"安全审计"页 + "设计方案历史"抽屉 |
| RBAC 五级（viewer/operator/engineer/admin/auditor） | 安全合规扫描需 troubleshoot+ 权限，审批需 admin |

**复用率约 75%**——Phase 3 主要是新增 Nautobot/App + 安全合规模块 + 闭环编排，底层基础设施全部复用。

---

## 三、逐周里程碑（M5-M6）

| 周次 | 里程碑 | 主负责 | 交付物 | 验收 |
|---|---|---|---|---|
| **W1** | NautobotAdapter + Docker 部署 | 后端 | `NautobotAdapter`（REST）+ `nautobot-mcp` + Docker compose | 双适配器切换读取一致 |
| **W2** | 自研 App v0.1 骨架 | 后端 | `nautobot_app_designs` Django plugin + `NetworkDesign` model + 迁移 | 方案可存入 Nautobot |
| **W3** | App v0.1 业务对接 + 前端 | 后端 + 前端 | ConfigEngineer → 存方案 + 设计页"历史方案"抽屉 | 端到端：生成→存储→查询 |
| **W4** | SecurityAuditor + 基线规则库 | AI + 安全 | `SecurityAuditor` Agent + `baseline_rules` 表 + ≥30 条规则 + 扫描器 | Cisco + 华为各 1 台合规得分 |
| **W5** | Batfish ACL 分析 | 后端 | batfish-mcp 扩展 ACL 断言 + `analyze_acl` 工具 + 报告 | ≥2 厂商冗余/可达性报告 |
| **W6** | ComplianceAgent + 报告 | AI | `ComplianceAgent`（基线 + ACL 聚合）+ Markdown/CSV 导出 | 端到端合规报告 |
| **W7** | 自动化闭环编排 | AI + Tech Lead | 闭环 Orchestrator（诊断→修复→验证→审批→下发）+ 3 场景 | BGP 故障全自动闭环 demo |
| **W8** | 三道闸全量 + 端到端验收 | 全员 | 审批流完善 + 快照回滚补全 + 7/7 验收 | 自动化率 ≥30% + 7/7 达标 |

**关键 gate**：
- W2 末：App v0.1 骨架必须跑通——否则 W3 降级为仅 Adapter（hermes-03 降级路径）。
- W4 末：基线规则库 ≥30 条——ComplianceAgent 依赖。
- W6 末：合规报告端到端——W7 自动化闭环的安全闸依赖。
- W8 末：自动化率 ≥30% + 7/7——<5/7 启动 Phase 3.5 补救。

---

## 四、模块详细设计

### 4.1 Nautobot 双适配器 + 自研 App v0.1

#### 4.1.1 NautobotAdapter（复用 SourceOfTruth 接口）

```python
# app/access/nautobot_adapter.py
class NautobotAdapter(SourceOfTruth):
    """Nautobot REST 包装（v2.0 三章 SourceOfTruth 双适配器）。

    与 NetBoxAdapter 实现同一 Protocol，业务层通过 factory 切换。
    Nautobot REST API 与 NetBox v2 高度兼容（同源 fork），映射成本低。
    """

    def __init__(self, base_url: str, token: str, timeout: float = 30.0):
        auth = f"Token {token}"  # Nautobot 用 Token，非 Bearer
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": auth},
            timeout=timeout,
        )

    async def get_device(self, device_id: int) -> Device: ...
    async def list_devices(self, filter: dict) -> list[Device]: ...
    async def get_topology(self, scope: str) -> Topology: ...
    async def get_ipam(self, prefix: str) -> IPAM: ...
    async def write_change_record(self, record: ChangeRecord) -> None: ...
```

#### 4.1.2 SourceOfTruth Factory 切换

```python
# app/access/source_of_truth.py（扩展）
def get_source_of_truth(provider: str = "netbox") -> SourceOfTruth:
    """工厂：按配置切换 NetBox / Nautobot（v2.0 双适配器并行）。"""
    settings = get_settings()
    if provider == "nautobot":
        return NautobotAdapter(settings.nautobot_url, settings.nautobot_token)
    return NetBoxAdapter(settings.netbox_url, settings.netbox_token)
```

#### 4.1.3 自研 Nautobot App v0.1（NetworkDesign 持久化）

**为什么选 NetworkDesign 作 v0.1**：
- 立即有用：ConfigEngineer 生成的 HLD/LLD 当前散落 Postgres，无法"按设备查设计方案历史"。
- 不依赖 Phase 4：RDMA Fabric model 需 RdmAgent 喂数据，现在做是空中楼阁（YAGNI）。
- 最简单：一个核心 model + 关联 device/site，POC 级验证"自研 App + 自带 SSoT"路径。

```python
# nautobot-app-designs/designs/models.py（自研 Django plugin）
from nautobot.core.models import BaseModel
from django.db import models

class NetworkDesign(BaseModel):
    """AI 生成的网络设计方案（v2.0 差异化：自带 SSoT 持久化）。"""
    name = models.CharField(max_length=200)
    site = models.ForeignKey("dcim.Site", on_delete=models.CASCADE)
    scenario = models.CharField(max_length=50)  # bgp/ospf/vxlan/...
    vendor = models.CharField(max_length=50)
    hld = models.JSONField()      # 高层设计（拓扑 + 选型）
    lld = models.JSONField()      # 低层设计（配置参数）
    config_diff = models.TextField()
    rollback_config = models.TextField()
    lint_passed = models.BooleanField(default=False)
    created_by = models.CharField(max_length=50)  # AI Agent / 用户
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
```

#### 4.1.4 nautobot-mcp

| 工具 | 输入 | 输出 |
|---|---|---|
| `get_device` | device_id | Device |
| `list_devices` | filter | list[Device] |
| `get_topology` | scope | Topology |
| `save_design` | NetworkDesign | id |
| `list_designs` | site/scenario | list[NetworkDesign] |

#### 4.1.5 部署

- Nautobot Docker 容器加入 `infra/docker-compose.nautobot.yml`（`networktocode/nautobot:latest`）。
- 自研 App 挂载到 Nautobot `PLUGINS` 配置，容器启动自动 migrate。
- 初始数据：从 Phase 2 NetBox 导出 5-10 台测试设备（Nautobot 提供 NetBox 迁移工具）。

---

### 4.2 SecurityAuditor + 基线规则库

#### 4.2.1 SecurityAuditor Agent

```yaml
# app/agents/definitions/security_auditor.yaml
name: security_auditor
role: "安全审计 Agent：配置基线检查 + Batfish ACL 分析 + 合规报告"
tools:
  - napalm.get_config
  - baseline.scan
  - batfish.analyze_acl
  - rag.search           # 厂商加固指南
transitions:
  - {from: collect_config, to: scan_baseline}
  - {from: scan_baseline, to: analyze_acl}
  - {from: analyze_acl, to: report}
  - {from: report, to: END}
```

#### 4.2.2 基线规则库（baseline_rules 表）

```python
# app/models/baseline.py
class BaselineRule(BaseModel):
    """安全基线规则（CIS + 厂商加固指南，v2.0 五章数据模型）。"""
    rule_id: str               # CIS-HARD-001
    vendor: str                # cisco_iosxe / huawei_vrp
    category: str              # auth / mgmt / protocol / acl
    severity: str              # critical / high / medium / low
    description: str
    check_type: str            # regex / negate / present / absent
    check_expr: str            # 正则或配置存在性表达式
    remediation: str           # 整改建议
    standard_ref: str          # CIS / NIST / 厂商文档引用
```

**≥30 条规则覆盖**（W4 交付）：

| 类别 | Cisco IOS-XE | 华为 VRP | 合计 |
|---|---|---|---|
| 认证（SSH/Telnet/AAA） | 5 | 5 | 10 |
| 管理（SNMP/NTP/日志） | 4 | 4 | 8 |
| 协议（BGP 认证/OSPF MD5） | 3 | 3 | 6 |
| ACL/服务（未用端口关闭） | 3 | 3 | 6 |
| 合计 | 15 | 15 | 30 |

#### 4.2.3 扫描器

```python
# app/services/baseline_scanner.py
class BaselineScanner:
    """配置基线扫描器：running-config → 规则匹配 → 合规得分。"""

    async def scan(self, config: str, vendor: str) -> ScanResult:
        rules = await self._load_rules(vendor)
        findings = []
        for rule in rules:
            finding = self._match(config, rule)
            findings.append(finding)
        return ScanResult(
            findings=findings,
            score=self._calc_score(findings),  # 0-100 合规分
            summary=self._summary(findings),
        )
```

---

### 4.3 Batfish ACL 分析（Cisco + 华为）

#### 4.3.1 batfish-mcp 扩展

| 工具 | 输入 | 输出 |
|---|---|---|
| `analyze_acl_reachability` | snapshot, src, dst, port | permit/deny + 命中规则 |
| `find_shadowed_acl` | snapshot | 被遮蔽规则列表 |
| `find_unused_acl` | snapshot | 未引用 ACL 列表 |
| `assert_reachability` | snapshot, 断言 | pass/fail + 证据 |

#### 4.3.2 华为 ACL 兼容策略（复用 Phase 2 H3C 策略）

- 华为 VRP ACL 语法与 Cisco 差异：`rule permit/deny source/destination` vs `permit/deny ip host`。
- Batfish 无原生华为 parser → 复用 Phase 2 的"H3C/Cisco parser 兜底"策略（华为配置转 Cisco 等价 ACL 喂 Batfish，loose validation）。
- Cisco IOS-XE 走原生 parser，full validation。

#### 4.3.3 ACL 报告

```python
# app/services/acl_analyzer.py
class ACLAnalyzer:
    async def analyze(self, snapshot: str, vendor: str) -> ACLReport:
        return ACLReport(
            reachability=await self._reachability(snapshot),
            shadowed=await self._shadowed(snapshot),
            unused=await self._unused(snapshot),
            vendor_notes=self._vendor_caveats(vendor),
        )
```

---

### 4.4 ComplianceAgent + 合规报告

#### 4.4.1 ComplianceAgent

```yaml
# app/agents/definitions/compliance.yaml
name: compliance
role: "合规 Agent：聚合基线 + ACL → 合规报告 + 整改建议"
tools:
  - baseline.scan
  - batfish.analyze_acl
  - report.render
transitions:
  - {from: gather, to: aggregate}
  - {from: aggregate, to: render}
  - {from: render, to: END}
```

#### 4.4.2 报告格式

- **Markdown**：人读，含合规得分 + 逐条 finding + 整改建议 + 标准引用。
- **CSV**：机读，每行一条 finding（设备/规则/严重度/状态/整改），便于导工单系统。
- 落审计哈希链（v2.0 二十章），报告不可篡改。

```python
# app/services/compliance_reporter.py
class ComplianceReporter:
    async def render(self, baseline: ScanResult, acl: ACLReport) -> Report:
        md = self._render_md(baseline, acl)
        csv = self._render_csv(baseline, acl)
        await self._audit_log(md, csv)  # 哈希链
        return Report(markdown=md, csv=csv, score=baseline.score)
```

---

### 4.5 自动化闭环编排（≥30%）

#### 4.5.1 闭环 Orchestrator

这是 Phase 3 的里程碑核心（v2.0 M6 硬指标）。把 Phase 2 的散装能力串成全自动链路：

```python
# app/agents/closed_loop.py
class ClosedLoopOrchestrator:
    """故障自动诊断→修复→验证→审批→下发 全闭环（v2.0 Phase 3 里程碑）。"""

    async def run(self, symptom: str) -> ClosedLoopResult:
        # 1. 诊断（Troubleshooter + RCA）
        diagnosis = await self._diagnose(symptom)
        # 2. 修复方案生成（ConfigEngineer）
        fix = await self._generate_fix(diagnosis)
        # 3. 验证（Batfish + Containerlab 仿真）
        verified = await self._verify(fix)
        # 4. 审批（人工门禁，但影响范围自动推演）
        approved = await self._request_approval(fix, verified)
        # 5. 下发（DeployAgent + checkpoint + 回滚）
        if approved:
            deployed = await self._deploy(fix)
            # 6. 监控（ObserverAgent 验证修复有效）
            await self._observe(deployed)
        return ClosedLoopResult(...)
```

#### 4.5.2 自动化率统计

```python
# 闭环步骤总数 vs 人工介入步骤数
TOTAL_STEPS = 6  # diagnose/fix/verify/approve/deploy/observe
# 人工介入：approve（强制）+ 诊断低置信度时人工确认
# 自动化率 = (TOTAL - 人工介入) / TOTAL
# 目标 ≥30%：即最多 4 步人工，至少 2 步全自动
# 实际：diagnose + fix + verify + deploy + observe 都自动，仅 approve 人工 → 83%
# 但 v2.0 指标 ≥30% 是下限（含低置信度人工确认场景）
```

#### 4.5.3 3 闭环场景

| 场景 | 症状 | 闭环路径 |
|---|---|---|
| BGP 邻居抖动 | `BGP-5-ADJCHG` | RCA(hello timer) → 修复计时器 → 仿真验证 → 审批 → 下发 → Observer 确认邻居稳定 |
| OSPF 邻居震荡 | `OSPF-5-ADJCHG` | RCA(MTU mismatch) → 修复 MTU → 验证 → 审批 → 下发 |
| ACL 误阻断 | 业务不通 | SecurityAuditor 定位 shadowed ACL → 修复规则 → Batfish 验证可达 → 审批 → 下发 |

---

### 4.6 三道闸全量落地 + RBAC/审计完善

#### 4.6.1 审批流完善

- 现状：Phase 1 三道闸 `approval.py` 是简单状态机（draft→review→approved→rejected）。
- Phase 3 完善：
  - 多级审批（engineer 拟 → admin 批，影响范围大需 Tech Lead 二次签）。
  - 审批超时机制（24h 未批自动过期）。
  - 审批意见 + 驳回原因结构化记录。

#### 4.6.2 快照回滚补全

- 现状：`snapshot.py` 有抓取逻辑，DeployAgent 有回滚。
- Phase 3 补全：
  - 快照版本管理（每次变更前自动抓，保留 N 个历史版本）。
  - 一键回滚 UI（前端变更页"回滚到此版本"按钮）。
  - 回滚后 ObserverAgent 自动验证全网健康。

#### 4.6.3 RBAC 强制门禁

- 现状：五级角色已就绪（viewer/operator/engineer/admin/auditor）。
- Phase 3 强制：
  - 安全合规扫描：需 `troubleshoot` 权限（operator+）。
  - 合规报告导出：需 `audit` 权限（auditor + admin）。
  - 闭环下发：需 `deploy` 权限（admin）。
  - 审计日志查询：仅 `auditor` + `admin`（等保三权分立）。

---

## 五、任务拆解与依赖

| # | 任务 | 周次 | 依赖 | 负责人 |
|---|---|---|---|---|
| P3-1 | NautobotAdapter + Docker 部署 | W1 | — | 后端 |
| P3-2 | nautobot-mcp + 双适配器 factory | W1 | P3-1 | 后端 |
| P3-3 | 自研 App v0.1 骨架（NetworkDesign model） | W2 | P3-1 | 后端 |
| P3-4 | App v0.1 业务对接 + 前端历史方案 | W3 | P3-3 | 后端+前端 |
| P3-5 | SecurityAuditor Agent + 基线规则库 ≥30 | W4 | — | AI+安全 |
| P3-6 | Batfish ACL 分析（Cisco + 华为） | W5 | P2-4（H3C 策略） | 后端 |
| P3-7 | ComplianceAgent + 报告导出 | W6 | P3-5, P3-6 | AI |
| P3-8 | 自动化闭环 Orchestrator + 3 场景 | W7 | P3-5~7, P2-8/10 | AI+Tech Lead |
| P3-9 | 三道闸全量（审批流 + 快照回滚 + RBAC） | W7-W8 | — | 后端 |
| P3-10 | 端到端验收 | W8 | 全部 | 全员 |

**可并行**：P3-5（基线）/ P3-6（ACL）/ P3-1~3（Nautobot）三条线独立推进。

**关键阻塞**：
- Nautobot App 骨架（P3-3，W2 末 gate）——失败则降级仅 Adapter。
- 基线规则库内容（P3-5，需安全工程师参与规则编写）。

---

## 六、风险与对策

| 风险 | 等级 | 对策 |
|---|---|---|
| Nautobot App 开发复杂（Django plugin 学习曲线） | 中 | W2 末 gate，失败降级仅 Adapter（hermes-03） |
| 基线规则库工作量大（≥30 条） | 中 | 优先 CIS Top 15 + 厂商加固 Top 15，分批补充 |
| Batfish 华为 ACL parser 不支持 | 中 | 复用 Phase 2 H3C 策略：转 Cisco 等价 ACL + loose validation |
| 自动化闭环 RCA 低置信度导致频繁人工介入 | 高 | 低置信度阈值可配，首次人工确认后 Case 入 RAG 提升下次自动率 |
| Nautobot 与 NetBox 数据双写一致性 | 中 | 以 Nautobot 为主写，NetBox 只读包装；或定义单向同步 |
| 闭环下发误操作生产 | 高 | 强制审批门禁 + 仿真前置 + 快照回滚 + 审计哈希链 |

---

## 附录：Phase 3 与 Phase 2 的代码复用清单

| Phase 2 模块 | Phase 3 复用方式 | 是否需改动 |
|---|---|---|
| `SourceOfTruth` + `NetBoxAdapter` | 新增 `NautobotAdapter` 实现 | 否（零改，新文件） |
| 6 Agent runtime | 新增 2 Agent（security_auditor/compliance） | 否 |
| RCA + Troubleshooter | 闭环"诊断"环节复用 | 否 |
| DeployAgent + checkpoint | 闭环"下发"环节复用 | 否 |
| 三道闸（gates/*） | 审批流 + 快照完善 | 中改 |
| batfish-mcp | 扩展 ACL 断言工具 | 小改 |
| 脱敏 + 审计哈希链 | 合规报告接入 | 否 |
| React 前端 | 新增安全审计页 + 历史方案抽屉 | 小改 |
| RBAC 五级 | 权限映射完善 | 小改 |

**复用率约 75%**——Phase 3 主要是新增 Nautobot/App + 安全合规模块 + 闭环编排。

---

## 变更日志

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v1.0 | 2026-08-23 | Phase 3 规划首版（8 周 + 6 模块详细设计 + 10 任务拆解） | 架构组 |

---

## 决策记录（2026-08-23）

| 决策项 | 选择 | 理由 |
|---|---|---|
| Nautobot 自研 App 深度 | Adapter + App v0.1（NetworkDesign） | 立即有用、不依赖 Phase 4、验证护城河路径；RDMA Fabric App 等 Phase 4 RdmAgent 有数据再做（YAGNI） |
| 安全合规线范围 | 基线 + ACL（Cisco + 华为） | v2.0 "先 Cisco+华为" 决策；攻击面/CVE/PDF 报告推 Phase 4 |
| Phase 2 遗留 3 项 | 独立留存，不阻塞 | 内容依赖（模板/评测题/手册），与 Phase 3 工程线解耦 |
| 主线优先级 | 自动化闭环 ≥30% | v2.0 M6 里程碑硬指标，串联 Phase 2 所有能力 |

---

> Phase 3 规划完结。下一步：确认规划后启动 W1（NautobotAdapter + Docker 部署）。
