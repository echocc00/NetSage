"""SecurityAuditor + Compliance Agent handlers（Phase 3）。"""
from __future__ import annotations

from typing import Any

SECURITY_AUDITOR_DEFINITION: dict[str, Any] = {
    "name": "security_auditor",
    "role": "安全审计 Agent：配置基线 + ACL 分析 + 攻击面测绘 + 加固优先级 + 合规报告",
    "system_prompt": (
        "你是网络安全审计员。对照 CIS/厂商加固基线检查配置，分析 ACL，"
        "测绘攻击面（暴露服务/明文协议/默认凭据/管理面），按风险排序加固优先级。"
    ),
    "tools": ["napalm.get_config", "baseline.scan", "batfish.analyze_acl", "rag.search"],
    "state_schema": {"type": "object"},
    "transitions": [
        {"from": "collect_config", "to": "scan_baseline"},
        {"from": "scan_baseline", "to": "analyze_acl"},
        {"from": "analyze_acl", "to": "map_attack_surface"},
        {"from": "map_attack_surface", "to": "prioritize"},
        {"from": "prioritize", "to": "report"},
        {"from": "report", "to": "END"},
    ],
    "interrupt_points": [],
}

COMPLIANCE_DEFINITION: dict[str, Any] = {
    "name": "compliance",
    "role": "合规 Agent：聚合基线 + ACL → 合规报告 + 整改建议",
    "system_prompt": "你是合规审计官。聚合基线扫描与 ACL 分析结果，生成 Markdown + CSV 报告。",
    "tools": ["baseline.scan", "batfish.analyze_acl", "report.render"],
    "state_schema": {"type": "object"},
    "transitions": [
        {"from": "gather", "to": "aggregate"},
        {"from": "aggregate", "to": "render"},
        {"from": "render", "to": "END"},
    ],
    "interrupt_points": [],
}


async def sec_collect_config(state: dict, tools: Any) -> dict:
    """采集 running-config（通过 napalm.get_config 或 state 直接传入）。"""
    config = state.get("config", "")
    if not config and tools:
        try:
            result = await tools.call("napalm.get_config", device_id=state.get("device_id", 1))
            config = result.get("config", "") if isinstance(result, dict) else str(result)
        except Exception:
            config = ""
    return {**state, "config": config}


async def sec_scan_baseline(state: dict, tools: Any) -> dict:
    """基线扫描。"""
    from app.services.baseline_scanner import BaselineScanner

    scanner = BaselineScanner()
    vendor = state.get("vendor", "huawei_vrp")
    result = await scanner.scan(state.get("config", ""), vendor)
    return {
        **state,
        "baseline": {
            "total": result.total, "passed": result.passed, "failed": result.failed,
            "score": result.score,
            "findings": [
                {"rule_id": f.rule_id, "severity": f.severity, "description": f.description,
                 "passed": f.passed, "remediation": f.remediation}
                for f in result.findings
            ],
        },
    }


async def sec_analyze_acl(state: dict, tools: Any) -> dict:
    """ACL 分析。"""
    from app.services.acl_analyzer import ACLAnalyzer

    analyzer = ACLAnalyzer()
    snapshot = state.get("snapshot", "mock")
    vendor = state.get("vendor", "huawei_vrp")
    report = await analyzer.analyze(snapshot, vendor)
    return {
        **state,
        "acl": {
            "shadowed": report.shadowed, "unused": report.unused,
            "reachability": report.reachability, "vendor_notes": report.vendor_notes,
        },
    }


# ===== 攻击面测绘（v2.0 5.1 attack_surface_mapper）=====

# (类别, 严重度, 描述, 匹配的配置片段列表)
ATTACK_SURFACE_PROBES: list[tuple[str, str, str, list[str]]] = [
    ("明文协议", "critical", "Telnet 服务启用（凭据明文传输）",
     ["telnet server enable", "transport input telnet"]),
    ("明文协议", "high", "FTP/TFTP 服务启用（无加密文件传输）",
     ["ftp server enable", "tftp server enable"]),
    ("明文协议", "high", "HTTP 管理面启用（未加密 Web 管理）",
     ["ip http server", "http server enable"]),
    ("弱认证", "critical", "SNMP v1/v2c 社区串（明文 + 无认证）",
     ["snmp-agent community", "snmp-server community"]),
    ("弱认证", "high", "无 AAA 认证方案（本地账户直连）",
     []),  # 反向检查：见 _probe_missing
    ("管理面暴露", "high", "管理面未绑定 ACL（任意源可达）",
     []),  # 反向检查
    ("协议未加固", "medium", "BGP 邻居无认证（易受路由注入）",
     []),  # 反向检查
    ("发现协议", "low", "LLDP/CDP 全局启用（拓扑信息泄漏）",
     ["lldp enable", "cdp run"]),
]

# 反向检查：配置中"缺少"这些才算暴露
MISSING_PROBES: list[tuple[str, str, str, list[str]]] = [
    ("弱认证", "high", "无 AAA 认证方案", ["authentication-scheme", "aaa new-model"]),
    ("管理面暴露", "high", "vty/管理面无 ACL 限制", ["acl", "access-class"]),
    ("协议未加固", "medium", "BGP 邻居无认证", ["peer .* password", "neighbor .* password"]),
    ("传输加密", "critical", "未启用 SSH（无加密远程管理）",
     ["stelnet server enable", "ip ssh version 2"]),
]

SEVERITY_WEIGHT = {"critical": 40, "high": 20, "medium": 8, "low": 2}


async def sec_map_attack_surface(state: dict, tools: Any) -> dict:
    """攻击面测绘：暴露服务 / 明文协议 / 弱认证 / 管理面。"""
    import re

    config = state.get("config", "")
    config_lower = config.lower()
    exposures: list[dict] = []

    # 正向检查：出现即暴露
    for category, severity, item, patterns in ATTACK_SURFACE_PROBES:
        for pat in patterns:
            if pat.lower() in config_lower:
                exposures.append({
                    "category": category, "severity": severity,
                    "item": item, "evidence": pat,
                })
                break

    # 反向检查：缺少即暴露
    for category, severity, item, patterns in MISSING_PROBES:
        if not any(re.search(p, config, re.IGNORECASE) for p in patterns):
            exposures.append({
                "category": category, "severity": severity,
                "item": item, "evidence": f"未找到: {patterns[0]}",
            })

    score = min(100, sum(SEVERITY_WEIGHT.get(e["severity"], 0) for e in exposures))
    mgmt_exposed = any(e["category"] in ("管理面暴露", "明文协议") for e in exposures)

    return {
        **state,
        "attack_surface": {
            "exposures": exposures,
            "exposure_score": score,
            "mgmt_plane_exposed": mgmt_exposed,
            "by_severity": {
                sev: sum(1 for e in exposures if e["severity"] == sev)
                for sev in ("critical", "high", "medium", "low")
            },
        },
    }


async def sec_prioritize(state: dict, tools: Any) -> dict:
    """加固优先级：合并基线失败项 + 攻击面暴露，按风险 × 修复成本排序。"""
    baseline = state.get("baseline", {})
    surface = state.get("attack_surface", {})

    items: list[dict] = []
    # 基线失败项
    for f in baseline.get("findings", []):
        if f.get("passed"):
            continue
        items.append({
            "source": "baseline",
            "item": f.get("description", ""),
            "severity": f.get("severity", "medium"),
            "action": f.get("remediation", ""),
            "rule_id": f.get("rule_id", ""),
        })
    # 攻击面暴露
    for e in surface.get("exposures", []):
        items.append({
            "source": "attack_surface",
            "item": e["item"],
            "severity": e["severity"],
            "action": f"消除暴露：{e['evidence']}",
            "rule_id": "",
        })

    # 风险分 = 严重度权重（同分时 baseline 项优先，因有明确整改命令）
    for it in items:
        base = SEVERITY_WEIGHT.get(it["severity"], 0)
        it["risk_score"] = base + (2 if it["source"] == "baseline" else 0)

    items.sort(key=lambda x: x["risk_score"], reverse=True)
    # 去重（同一条目可能基线与攻击面都报）
    seen: set[str] = set()
    deduped: list[dict] = []
    for it in items:
        key = it["item"][:30]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)

    total_risk = sum(it["risk_score"] for it in deduped)
    return {
        **state,
        "remediation_plan": deduped[:15],  # Top 15 优先整改
        "risk_score": min(100, total_risk),
        "risk_summary": {
            "total_items": len(deduped),
            "critical": sum(1 for i in deduped if i["severity"] == "critical"),
            "high": sum(1 for i in deduped if i["severity"] == "high"),
        },
    }


async def sec_report(state: dict, tools: Any) -> dict:
    """生成合规报告（含攻击面 + 加固优先级）。"""
    from app.services.acl_analyzer import ACLReport
    from app.services.baseline_scanner import Finding, ScanResult
    from app.services.compliance_reporter import ComplianceReporter

    baseline_data = state.get("baseline", {})
    acl_data = state.get("acl", {})
    baseline = ScanResult(
        vendor=state.get("vendor", ""),
        total=baseline_data.get("total", 0),
        passed=baseline_data.get("passed", 0),
        failed=baseline_data.get("failed", 0),
        score=baseline_data.get("score", 0),
        findings=[Finding(**f) for f in baseline_data.get("findings", [])],
    )
    acl = ACLReport(
        snapshot=state.get("snapshot", ""),
        vendor=state.get("vendor", ""),
        reachability=acl_data.get("reachability", []),
        shadowed=acl_data.get("shadowed", []),
        unused=acl_data.get("unused", []),
        vendor_notes=acl_data.get("vendor_notes", ""),
    )
    reporter = ComplianceReporter()
    report = await reporter.render(baseline, acl)

    # 附加攻击面 + 加固优先级章节
    extra = _render_extra_sections(state)
    return {
        **state,
        "report": {
            "score": report.score,
            "markdown": report.markdown + extra,
            "csv": report.csv,
            "risk_score": state.get("risk_score", 0),
        },
    }


def _render_extra_sections(state: dict) -> str:
    """渲染攻击面 + 加固优先级 Markdown 章节。"""
    surface = state.get("attack_surface", {})
    plan = state.get("remediation_plan", [])
    if not surface and not plan:
        return ""

    lines = ["", "## 攻击面测绘", ""]
    exposures = surface.get("exposures", [])
    if exposures:
        lines.append("| 类别 | 严重度 | 暴露项 | 证据 |")
        lines.append("|---|---|---|---|")
        for e in exposures:
            lines.append(
                f"| {e['category']} | {e['severity']} | {e['item']} | `{e['evidence']}` |"
            )
    else:
        lines.append("未发现明显暴露面。")
    lines.extend([
        "",
        f"**攻击面得分**：{surface.get('exposure_score', 0)}/100（越低越安全）",
        f"**管理面暴露**：{'是' if surface.get('mgmt_plane_exposed') else '否'}",
        "",
        "## 加固优先级（按风险 × 修复成本排序）",
        "",
    ])
    if plan:
        lines.append("| 优先级 | 项 | 严重度 | 风险分 | 整改动作 |")
        lines.append("|---|---|---|---|---|")
        for i, item in enumerate(plan, 1):
            lines.append(
                f"| P{i} | {item['item']} | {item['severity']} | "
                f"{item['risk_score']} | {item['action']} |"
            )
    else:
        lines.append("无待整改项。")
    return "\n".join(lines) + "\n"


async def compliance_gather(state: dict, tools: Any) -> dict:
    """聚合输入：确保 config 就绪（可从 napalm 拉取）。"""
    return await sec_collect_config(state, tools)


async def compliance_aggregate(state: dict, tools: Any) -> dict:
    """聚合基线 + ACL + 攻击面 + 优先级（复用 security_auditor 逻辑）。"""
    state = await sec_scan_baseline(state, tools)
    state = await sec_analyze_acl(state, tools)
    state = await sec_map_attack_surface(state, tools)
    state = await sec_prioritize(state, tools)
    return state


async def compliance_render(state: dict, tools: Any) -> dict:
    """渲染报告（Markdown + CSV + 风险分）。"""
    return await sec_report(state, tools)
