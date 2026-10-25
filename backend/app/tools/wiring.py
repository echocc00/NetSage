"""启动装配：工具注册表 mock / mcp 双模式（审查 P0 修复）。

- mock 模式（默认）：MockToolRegistry + 演示预设 stub——闸门必过、
  下发必成功。仅供本地联调/测试，/health 与启动日志显式暴露
  tools_mode=mock，API 响应不再伪装成真实校验结果。
- mcp 模式（TOOLS_BACKEND=mcp）：HttpToolRegistry 经 MCP 协议调
  真实 server（containerlab/batfish/napalm/…），闸门结果来自真实
  仿真与静态分析。
"""
from __future__ import annotations

from app.core.config import Settings
from app.core.logging import get_logger
from app.tools.registry import MockToolRegistry, ToolRegistry

logger = get_logger("tools_wiring")

MOCK_MODE = "mock"
MCP_MODE = "mcp"


def install_demo_stubs(registry: MockToolRegistry) -> None:
    """mock 模式演示预设（闸门必过、下发必成功——不代表真实校验，仅供联调）。"""
    registry.stub("napalm.get_config", lambda **kw: {"config": "running-config-mock"})
    registry.stub("napalm.apply_candidate", lambda **kw: {"status": "committed"})
    registry.stub("napalm.load_merge_candidate", lambda **kw: {"status": "candidate_loaded"})
    registry.stub("napalm.commit", lambda **kw: {"status": "committed"})
    registry.stub("containerlab.deploy_topology", lambda **kw: {"status": "deployed"})
    registry.stub("containerlab.exec_on_node", lambda **kw: {"stdout": "Up"})
    registry.stub("batfish.lint_config", lambda **kw: {"passed": True, "warnings": []})
    registry.stub("batfish.assert_reachability", lambda **kw: {"passed": True})
    registry.stub("batfish.assert_routing", lambda **kw: {"passed": True})
    registry.stub("batfish.assert_acl", lambda **kw: {"passed": True})


def build_registry(settings: Settings) -> tuple[ToolRegistry, str]:
    """按配置构造工具注册表，返回 (registry, mode)。"""
    if settings.tools_backend == MCP_MODE:
        from app.tools.http_registry import HttpToolRegistry

        urls = {
            "containerlab": settings.mcp_containerlab_url,
            "batfish": settings.mcp_batfish_url,
            "napalm": settings.mcp_napalm_url,
            "netbox": settings.mcp_netbox_url,
            "suzieq": settings.mcp_suzieq_url,
            "nautobot": settings.mcp_nautobot_url,
            "opensm": settings.mcp_opensm_url,
        }
        urls = {k: v for k, v in urls.items() if v}
        registry: ToolRegistry = HttpToolRegistry(urls)
        logger.info("tools_configured", mode=MCP_MODE, servers=sorted(urls))
        return registry, MCP_MODE

    registry = MockToolRegistry()
    install_demo_stubs(registry)
    logger.warning(
        "tools_mock_mode",
        hint="所有工具返回演示预设（闸门必过）；设 TOOLS_BACKEND=mcp 接真实 MCP server",
    )
    return registry, MOCK_MODE
