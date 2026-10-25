"""DB 模式集成测试（v0.5.0 阶段2 验证：真实 PostgreSQL）。

前置：docker compose -f infra/docker-compose.dev.yml up -d postgres
跳过条件：PG 不可达（与 test_phase3 同模式）。

覆盖：
- DbChangeStore 全流程（CRUD/审批/快照/统计）
- DbAuditSink 哈希链写入 + verify 重算 + 篡改检测
- 跨实例快照共享（多 worker 场景：worker A 存、worker B 读）
- 完整 HTTP 生命周期在 DB 模式下落库（change_requests 状态流转 + audit_logs 4 条）
"""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

pg_available = False
try:
    import asyncpg

    asyncio.run(asyncio.wait_for(
        asyncpg.connect("postgresql://netsage:changeme_dev_only@localhost:5432/netsage"), 3
    )).close()
    pg_available = True
except Exception:
    pg_available = False

pytestmark = [
    pytest.mark.skipif(not pg_available, reason="Postgres 不可用（docker compose dev）"),
    pytest.mark.asyncio(loop_scope="session"),
]


@pytest_asyncio.fixture
async def store():
    from app.services.change_store import DbChangeStore

    s = DbChangeStore()
    yield s


async def test_db_change_store_full_lifecycle(store):
    """CRUD + 审批 + 快照 + 统计全流程（真实 PG）。"""
    rec = await store.create(
        title="IT-DB 变更", nim={"topology": {"underlay": {"protocol": "bgp"}}},
        devices=[{"id": 1, "name": "spine01"}], configs={"spine01": "router bgp 65001"},
        assertions=[], impact={"risk_level": "high"}, created_by=9,
    )
    assert rec.status == "draft" and rec.id > 0

    got = await store.get(rec.id)
    assert got is not None
    assert got.nim == {"topology": {"underlay": {"protocol": "bgp"}}}
    assert got.configs == {"spine01": "router bgp 65001"}

    updated = await store.update_status(rec.id, "approval", pipeline_result={"steps": [1, 2]})
    assert updated is not None and updated.status == "approval"
    assert updated.pipeline_result == {"steps": [1, 2]}

    await store.save_approval(rec.id, approver_id=3, decision="approved", comment="IT 审批")
    await store.update_status(rec.id, "approved")

    await store.save_snapshot(rec.id, 1, "snapshots/device-1/itdb01", "h" * 64, "running-config-IT")
    assert await store.load_snapshot("snapshots/device-1/itdb01") == "running-config-IT"

    stats = await store.stats()
    assert stats["by_status"].get("approved", 0) >= 1
    items = await store.list(limit=5)
    assert any(r.id == rec.id for r in items)


async def test_db_audit_chain_and_tamper_detect():
    """DB 审计链：写入 → verify 通过；owner 篡改被 trigger 物理阻止（v0.5.1）。

    防线一：BEFORE UPDATE/DELETE trigger（migration 0008）——owner 也被拒
    （此前 REVOKE 对 owner 无效的缺口已补）。
    防线二：verify_chain 重算哈希（内存链篡改检测见 test_v050_fixes.py）。
    """
    import asyncpg

    from app.audit.service import DbAuditSink

    sink = DbAuditSink()
    for i in range(3):
        assert await sink.append(
            user_id=1, action="change.create", resource_type="change_request", resource_id=str(i)
        )
    assert await sink.verify() is True

    conn = await asyncpg.connect("postgresql://netsage:changeme_dev_only@localhost:5432/netsage")
    try:
        # owner 直改/直删都被 trigger 拒绝（防线一生效）
        with pytest.raises(asyncpg.PostgresError, match="INSERT ONLY"):
            await conn.execute("UPDATE audit_logs SET action = 'change.deploy' WHERE id = 2")
        with pytest.raises(asyncpg.PostgresError, match="INSERT ONLY"):
            await conn.execute("DELETE FROM audit_logs WHERE id = 2")
        # 链未被破坏
        assert await sink.verify() is True
    finally:
        await conn.close()


async def test_snapshot_shared_across_store_instances(store):
    """多 worker 快照共享：实例 A 存 → 新实例 B（另一 worker）可读。"""
    from app.services.change_store import DbChangeStore

    rec = await store.create(title="IT-跨worker", nim={}, devices=[], configs={},
                             assertions=[], impact={}, created_by=1)
    await store.save_snapshot(rec.id, 5, "snapshots/device-5/xworker", "k" * 64, "config-X")
    worker_b = DbChangeStore()  # 模拟另一个 uvicorn worker 的存储实例
    assert await worker_b.load_snapshot("snapshots/device-5/xworker") == "config-X"


async def test_http_lifecycle_persists_to_db():
    """完整 HTTP 生命周期（DB 模式 lifespan）：变更单落库 + 审计 4 条 + 链有效。"""
    import asyncpg

    from app.core.security import CurrentUser, Role, encode_token
    from app.main import app

    admin_hdr = {"Authorization": f"Bearer {encode_token(CurrentUser(id=1, name='admin', role=Role.ADMIN))}"}
    eng_hdr = {"Authorization": f"Bearer {encode_token(CurrentUser(id=2, name='eng', role=Role.ENGINEER))}"}

    conn = await asyncpg.connect("postgresql://netsage:changeme_dev_only@localhost:5432/netsage")
    try:
        before_audit = await conn.fetchval("SELECT count(*) FROM audit_logs")

        with TestClient(app) as client:  # lifespan：DB 可达 → DbChangeStore/DbAuditSink
            r = client.post(
                "/api/v1/changes",
                json={"title": "IT-HTTP-DB", "nim": {}, "devices": [
                    {"id": 1, "name": "d1", "vendor": "huawei_vrp", "host": "1.2.3.4",
                     "username": "a", "password": "b"}],
                    "configs": {"d1": "router bgp 65001"}, "assertions": []},
                headers=eng_hdr,
            )
            assert r.status_code == 200, r.text
            cid = r.json()["data"]["id"]
            assert client.post(f"/api/v1/changes/{cid}/run", headers=eng_hdr).status_code == 200
            assert client.post(f"/api/v1/changes/{cid}/approve?decision=approved", headers=admin_hdr).status_code == 200
            assert client.post(f"/api/v1/changes/{cid}/deploy", headers=admin_hdr).status_code == 200

        # 变更单状态落库为 done（deploy 成功）；审计链新增 ≥4 条（create/run/approve/deploy）
        status = await conn.fetchval("SELECT status FROM change_requests WHERE id = $1", cid)
        assert status == "done", f"变更单未落库或状态异常: {status}"
        after_audit = await conn.fetchval("SELECT count(*) FROM audit_logs")
        assert after_audit - before_audit >= 4, "生命周期审计未落库"
        # 快照正文落库（deploy 前抓取）
        snaps = await conn.fetchval(
            "SELECT count(*) FROM config_snapshots WHERE change_request_id = $1", cid)
        assert snaps >= 1, "快照未落库"
    finally:
        await conn.close()

    from app.audit.service import DbAuditSink

    assert await DbAuditSink().verify() is True
