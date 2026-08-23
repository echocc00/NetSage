"""Phase 4 端到端验收脚本（P4-6）。"""
from __future__ import annotations
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def check(name, coro_or_value) -> bool:
    import inspect
    try:
        if inspect.iscoroutine(coro_or_value): result = await coro_or_value
        else: result = coro_or_value
        ok = result if isinstance(result, bool) else True
        print(f"  {'✓' if ok else '✗'} {name}: {result if not isinstance(result,bool) else 'pass'}")
        return bool(ok)
    except Exception as e:
        print(f"  ✗ {name}: {str(e)[:100]}")
        return False


async def main():
    print("="*60); print("Phase 4 端到端验收（v2.0 M9 Gate）"); print("="*60)
    results: list[bool] = []

    print("\n[1] OpenSM 容器化 + opensm-mcp")
    import os; os.environ["OPENSM_MOCK"] = "true"
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mcp-servers" / "opensm-mcp"))
    import server as opensm
    ibstat = await opensm.ibstat.fn() if hasattr(opensm.ibstat,'fn') else opensm._MOCK_IBSTAT
    results.append(await check(f"opensm-mcp ibstat mock（{len(ibstat['ports'])} 端口）", len(ibstat['ports'])>=3))

    print("\n[2] RoCE 模板库 ≥6")
    from app.services.template_loader import list_by_vendor
    roce = sum(len([m for m in list_by_vendor(v) if m['protocol']=='roce']) for v in ['huawei','cisco','arista'])
    results.append(await check(f"RoCE 模板（{roce} 个）", roce>=6))

    print("\n[3] RdmAgent 配置诊断")
    from app.agents.registry import build_runner
    runner = build_runner()
    state = {"symptom":"RoCEv2 丢包 PFC pause 风暴","vendor":"huawei","interface":"10GE1/0/1","perf":{"counters":{"port_xmit_discards":50}}}
    result = await runner.run("rdm_agent", state, session_id="acc-rdma")
    diag = result.get("diagnosis",{})
    results.append(await check(f"诊断瓶颈: {diag.get('bottleneck','?')[:40]}", bool(diag.get("bottleneck"))))
    results.append(await check("调优参数生成", bool(result.get("tuning",{}).get("pfc_priority"))))
    results.append(await check("配置模板渲染", bool(result.get("template_used"))))

    print("\n[4] Agent 注册 9")
    agents = list(runner._compiled.keys())
    results.append(await check(f"Agent 注册（{len(agents)} 个）", len(agents)>=9 and "rdm_agent" in agents))

    print("\n[5] Nautobot RdmaFabric model")
    from app.models.design import RdmaFabric
    cols = [c.name for c in RdmaFabric.__table__.columns]
    results.append(await check(f"RdmaFabric model（{len(cols)} 列）", "pfc_priority" in cols and "ecn_enabled" in cols))

    print("\n[6] RdmaFabric 迁移")
    from pathlib import Path as P
    mig = P(__file__).resolve().parent.parent / "alembic" / "versions" / "0005_rdma_fabrics.py"
    results.append(await check("0005_rdma_fabrics.py 存在", mig.exists()))

    print("\n[7] RdmaFabric API")
    from app.api.v1 import rdma
    results.append(await check("rdma router 注册", hasattr(rdma, "router")))

    print("\n"+"="*60)
    passed = sum(results); total = len(results)
    print(f"验收结果：{passed}/{total} 通过")
    if passed == total: print("✓ Phase 4 v0.2.0 验收达标")
    elif passed >= total*0.8: print("⚠ Phase 4 基本达标")
    else: print("✗ Phase 4 未达标")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
