"""健康端点单元测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["env"]


def test_openapi_available() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200


def test_trace_id_propagated() -> None:
    """服务端生成 trace_id 并透传响应头（审查 M6 修复：不信任客户端 ID）。"""
    response = client.get("/api/v1/health", headers={"X-Trace-Id": "client-hint-123"})
    # 主 ID 由服务端生成，与客户端 hint 不同
    assert response.headers["X-Trace-Id"]
    assert response.headers["X-Trace-Id"] != "client-hint-123"
