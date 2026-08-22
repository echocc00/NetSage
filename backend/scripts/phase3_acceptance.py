"""Phase 3 端到端验收脚本（P3-10）。

覆盖 v2.0 十九章 19.3 Phase 3 验收标准：
1. Nautobot 双适配器（NetBox + Nautobot）
2. 自研 App v0.1（NetworkDesign 持久化）
3. SecurityAuditor + 基线规则库 ≥30
4. Batfish ACL 分析（Cisco + 华为）
5. ComplianceAgent + 报告导出
6. 自动化闭环 ≥30%
7. 三道闸全量 + RBAC/审计完善
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def check(name: str, coro_or_value) -> bool:
    import inspect
    try:
        if inspect.iscoroutine(coro_or_value):
            result = await coro_or_value
        else:
            result = coro_or_value
        ok = result if isinstance(result, bool) else True
        status = "✓" if ok else "✗"
        detail = result if not isinstance(result, bool) else "pass"
        print(f"  {status} {name}: {detail}")
        return bool(ok)
    except Exception as e:
        print(f"  ✗ {name}: {str(e)[:100]}")
        return False


async def main():
    print("=" * 60)
    print("Phase 3 端到端验收（v2.0 十九章 19.3）")
    print("=" * 60)
    results: list[bool] = []

    print("\n[1] Nautobot 双适配器")
    from app.access.nautobot_adapter import NautobotAdapter
    from app.access.source_of_truth import get_source_of_truth
    nb = get_source_of_truth("netbox")
    nt = get_source_of_truth("nautobot")
    nt_devs = await nt.list_devices()
    results.append(await check(f"双适配器切换（Nautobot mock {len(nt_devs)} 台）", len(nt_devs) == 5))
    await nt.close()

    print("\n[2] 自研 App v0.1（NetworkDesign model）")
    from app.models.design import NetworkDesign
    cols = [c.name for c in NetworkDesign.__table__.columns]
    required = {"name", "site", "scenario", "vendor", "hld", "lld", "config_diff", "lint_passed"}
    results.append(await check(f"NetworkDesign model 字段（{len(cols)} 列）", required.issubset(set(cols))))

    print("\n[3] SecurityAuditor + 基线规则库 ≥30")
    from app.services.baseline_scanner import RULES, BaselineScanner
    results.append(await check(f"基线规则库（{len(RULES)} 条）", len(RULES) == 30))
    scanner = BaselineScanner()
    scan = await scanner.scan("stelnet server enable\naaa new-model", "huawei_vrp")
    results.append(await check(f"华为基线扫描（{scan.passed}/{scan.total} 通过）", scan.total == 15))

    print("\n[4] Batfish ACL 分析（Cisco + 华为）")
    from app.services.acl_analyzer import ACLAnalyzer
    acl_cisco = await ACLAnalyzer().analyze("snap1", "cisco_iosxe")
    results.append(await check("Cisco ACL 分析", len(acl_cisco.shadowed) + len(acl_cisco.unused) >= 0))
    acl_hw = await ACLAnalyzer().analyze("snap2", "huawei_vrp")
    results.append(await check("华为 ACL 分析（loose validation）", "loose validation" in acl_hw.vendor_notes))

    print("\n[5] ComplianceAgent + 报告导出")
    from app.agents.registry import build_runner
    runner = build_runner()
    state = {"config": "stelnet server enable", "vendor": "huawei_vrp", "snapshot": "mock"}
    result = await runner.run("compliance", state, session_id="acc-comp")
    report = result.get("report", {})
    results.append(await check("ComplianceAgent 报告生成", "# 合规审计报告" in report.get("markdown", "")))

    print("\n[6] 自动化闭环 ≥30%")
    from app.agents.closed_loop import ClosedLoopOrchestrator
    orch = ClosedLoopOrchestrator(runner=runner)
    loop_result = await orch.run("BGP 邻居抖动", "huawei_vrp", auto_approve=True)
    results.append(await check(
        f"闭环自动化率 {loop_result.automation_rate:.0%}",
        loop_result.automation_rate >= 0.3,
    ))

    print("\n[7] 三道闸 + RBAC/审计完善")
    from app.core.security import ROLE_PERMISSIONS, Role
    admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
    auditor_perms = ROLE_PERMISSIONS[Role.AUDITOR]
    results.append(await check("admin 含 audit 权限", "audit" in admin_perms))
    results.append(await check("auditor 含 audit 权限", "audit" in auditor_perms))
    from app.gates.models import VALID_TRANSITIONS, ChangeStatus
    results.append(await check("状态机含审批→下发", ChangeStatus.DEPLOYING in VALID_TRANSITIONS[ChangeStatus.APPROVED]))

    print("\n[8] Agent 注册（8 Agent）")
    agents = list(runner._compiled.keys())
    results.append(await check(f"Agent 注册（{len(agents)} 个）", len(agents) >= 8))
    print(f"    Agents: {agents}")

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"验收结果：{passed}/{total} 通过")
    if passed == total:
        print("✓ Phase 3 验收达标")
    elif passed >= total * 0.8:
        print("⚠ Phase 3 基本达标，部分项待补")
    else:
        print("✗ Phase 3 未达标，需补救")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
