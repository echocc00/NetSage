"""MCP Server 工具注册测试（不依赖外部服务）。

验证三个 server 的工具清单与 v2.0 开发计划第九章对齐。
"""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

MCP_ROOT = Path(__file__).resolve().parents[3] / "mcp-servers"


def _load(server_name: str):
    """按文件路径加载 server 模块（避免模块缓存冲突）。"""
    path = MCP_ROOT / server_name / "server.py"
    spec = importlib.util.spec_from_file_location(f"{server_name}_srv", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(
    "server_name,expected_tools",
    [
        ("containerlab-mcp", {"deploy_topology", "destroy_topology", "inspect_topology", "exec_on_node", "save_topology"}),
        ("batfish-mcp", {"load_snapshot", "assert_reachability", "assert_acl", "assert_routing", "lint_config"}),
        ("napalm-mcp", {"get_facts", "get_config", "load_merge_candidate", "compare_config", "commit", "discard"}),
    ],
)
def test_mcp_server_tools_registered(server_name: str, expected_tools: set[str]) -> None:
    """每个 MCP server 注册的工具名与设计一致（v2.0 开发计划九章 9.2）。"""
    mod = _load(server_name)
    tools = asyncio.run(mod.mcp.list_tools())
    actual = {t.name for t in tools}
    assert actual == expected_tools, f"{server_name} 工具不匹配: 缺 {expected_tools - actual}, 多 {actual - expected_tools}"


def test_napalm_driver_map_covers_phase1_vendors() -> None:
    """napalm-mcp Phase 1 覆盖厂商（v2.0 三章 + 31.2）。"""
    mod = _load("napalm-mcp")
    required = {"cisco_iosxe", "huawei_vrp", "h3c_comware", "juniper_junos", "arista_eos"}
    assert required.issubset(mod.DRIVER_MAP.keys()), f"缺失厂商: {required - mod.DRIVER_MAP.keys()}"


def test_mcp_error_structure() -> None:
    """MCPError 携带 code/message/details（供客户端结构化处理）。"""
    from netsage_mcp_shared import MCPError

    err = MCPError("connect_failed", "连接超时", {"host": "1.2.3.4"})
    assert err.code == "connect_failed"
    assert err.details == {"host": "1.2.3.4"}
