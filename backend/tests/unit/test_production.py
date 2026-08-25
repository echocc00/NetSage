"""Phase 4 M12 生产化测试：报表/DR/LLM 缓存/OpenAPI。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import CurrentUser, Role, encode_token
from app.main import app

client = TestClient(app)


def _auth(role: Role = Role.ADMIN) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_token(CurrentUser(id=1, name='test', role=role))}"}


# ===== 报表 =====


def test_reports_overview():
    r = client.get("/api/v1/reports/overview", headers=_auth())
    assert r.status_code == 200
    d = r.json()["data"]
    assert "devices" in d and "changes" in d and "compliance" in d


def test_reports_dashboard():
    r = client.get("/api/v1/reports/dashboard", headers=_auth())
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["summary"]["devices"] == 5
    assert d["device_health"]["healthy"] == 4


def test_reports_devices():
    r = client.get("/api/v1/reports/devices", headers=_auth())
    assert r.status_code == 200
    assert len(r.json()["data"]["by_vendor"]) == 4


def test_reports_changes():
    r = client.get("/api/v1/reports/changes", headers=_auth())
    assert r.status_code == 200
    assert r.json()["data"]["automation_rate"] == 0.83


def test_reports_compliance():
    r = client.get("/api/v1/reports/compliance", headers=_auth())
    assert r.status_code == 200
    assert r.json()["data"]["avg_score"] == 72


def test_reports_llm_usage():
    r = client.get("/api/v1/reports/llm-usage", headers=_auth())
    assert r.status_code == 200
    assert "usage" in r.json()["data"]


# ===== 健康检查（依赖探测）=====


def test_health_liveness():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_ready():
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    d = r.json()
    assert "deps" in d
    assert len(d["deps"]) == 4  # pg/redis/llm/ssot


# ===== LLM 缓存 =====


def test_llm_cache_key_deterministic():
    from app.services.llm_gateway import LLMGateway, TaskTier

    gw = LLMGateway()
    k1 = gw._cache_key([{"role": "user", "content": "hi"}], TaskTier.SIMPLE, {})
    k2 = gw._cache_key([{"role": "user", "content": "hi"}], TaskTier.SIMPLE, {})
    assert k1 == k2  # 相同输入 → 相同 key


def test_llm_usage_stats():
    from app.services.llm_gateway import _track_usage, get_llm_gateway

    _track_usage("test_model", 100)
    gw = get_llm_gateway()
    stats = gw.usage_stats()
    assert "test_model" in stats


# ===== OpenAPI =====


def test_openapi_has_tags():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert "tags" in spec
    tag_names = {t["name"] for t in spec["tags"]}
    assert "reports" in tag_names
    assert "compliance" in tag_names


def test_openapi_has_redoc():
    r = client.get("/redoc")
    assert r.status_code == 200


# ===== 评测 Runner =====


def test_bench_runner():
    import asyncio
    import sys
    sys.path.insert(0, "..")
    from eval.runner.run_all import run_bench

    r = asyncio.run(run_bench(limit=20))
    assert r["total"] == 20
    assert r["pass_rate"] >= 0
    assert "by_category" in r


# ===== DR 脚本存在 =====


def test_dr_scripts_exist():
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]  # backend/tests/unit → repo root
    assert (root / "scripts" / "backup.sh").exists()
    assert (root / "scripts" / "restore.sh").exists()
