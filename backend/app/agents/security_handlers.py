"""SecurityAuditor + Compliance Agent handlers（Phase 3）。"""
from __future__ import annotations

from typing import Any

SECURITY_AUDITOR_DEFINITION = {
    "name": "security_auditor",
    "role": "安全审计 Agent：配置基线检查 + Batfish ACL 分析 + 合规报告",
    "system_prompt": "你是网络安全审计员。对照 CIS/厂商加固基线检查配置，分析 ACL，输出合规报告。",
    "tools": ["napalm.get_config", "baseline.scan", "batfish.analyze_acl", "rag.search"],
    "state_schema": {"type": "object"},
    "transitions": [
        {"from": "collect_config", "to": "scan_baseline"},
        {"from": "scan_baseline", "to": "analyze_acl"},
        {"from": "analyze_acl", "to": "report"},
        {"from": "report", "to": "END"},
    ],
    "interrupt_points": [],
}

COMPLIANCE_DEFINITION = {
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


async def sec_report(state: dict, tools: Any) -> dict:
    """生成合规报告。"""
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
    return {
        **state,
        "report": {
            "score": report.score, "markdown": report.markdown, "csv": report.csv,
        },
    }


async def compliance_gather(state: dict, tools: Any) -> dict:
    """聚合输入。"""
    return state


async def compliance_aggregate(state: dict, tools: Any) -> dict:
    """聚合基线 + ACL（复用 security_auditor 逻辑）。"""
    state = await sec_scan_baseline(state, tools)
    state = await sec_analyze_acl(state, tools)
    return state


async def compliance_render(state: dict, tools: Any) -> dict:
    """渲染报告。"""
    state = await sec_report(state, tools)
    return state
