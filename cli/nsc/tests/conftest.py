"""nsc CLI 测试夹具：隔离 HOME 配置 + 固定后端地址，供 respx 拦截。"""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

import nsc.client
import nsc.main as main

TEST_BACKEND = "http://testserver"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """隔离配置路径 + 固定后端，避免碰真实 ~/.nsc。"""
    monkeypatch.setattr(nsc.client, "DEFAULT_BACKEND", TEST_BACKEND)
    cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(nsc.client, "CONFIG_PATH", cfg)
    monkeypatch.setattr(main, "CONFIG_PATH", cfg)
    yield cfg


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()