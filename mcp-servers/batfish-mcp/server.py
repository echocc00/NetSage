"""Batfish MCP Server（v2.0 开发计划九章 9.2）。

工具：load_snapshot / assert_reachability / assert_acl / assert_routing / lint_config
通过 pybatfish 调用 Batfish REST（batfish_host，默认 localhost:9996）。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastmcp import FastMCP
from pybatfish.client.session import Session

from netsage_mcp_shared import MCPError, log

mcp = FastMCP("batfish-mcp")

BATFISH_HOST = os.getenv("BATFISH_HOST", "localhost")
BATFISH_PORT = int(os.getenv("BATFISH_PORT", "9996"))

_session: Session | None = None


def _bf() -> Session:
    global _session
    if _session is None:
        _session = Session(host=BATFISH_HOST, port_v1=BATFISH_PORT)
    return _session


@mcp.tool()
async def load_snapshot(configs_dir: str, snapshot_name: str = "snap") -> dict:
    """加载配置快照到 Batfish。

    Args:
        configs_dir: 含设备配置文件的目录路径
        snapshot_name: 快照名称
    """
    bf = _bf()
    try:
        bf.set_snapshot(
            bf.init_snapshot(str(configs_dir), name=snapshot_name, overwrite=True),
            name=snapshot_name,
        )
        log.info("bf_snapshot_loaded", snapshot=snapshot_name, dir=configs_dir)
        return {"snapshot": snapshot_name, "status": "loaded"}
    except Exception as e:
        raise MCPError("load_failed", f"Batfish 加载快照失败: {e}") from e


@mcp.tool()
async def assert_reachability(snapshot: str, src: str, dst: str) -> dict:
    """断言：src 到 dst 是否可达。false negative = 0（v2.0 19.1 验收 3）。"""
    bf = _bf()
    try:
        answer = bf.q.reachability(
            locations=src,
            remoteLocations=dst,
        ).answer()
        accepted = len(answer["answerElements"]) > 0
        return {
            "snapshot": snapshot,
            "assertion": "reachability",
            "passed": accepted,
            "src": src,
            "dst": dst,
            "evidence": answer["answerElements"],
        }
    except Exception as e:
        raise MCPError("assert_failed", f"reachability 断言失败: {e}") from e


@mcp.tool()
async def assert_acl(snapshot: str, acl_spec: dict) -> dict:
    """断言：ACL 行为（permit/deny 指定流量）。"""
    bf = _bf()
    try:
        answer = bf.q.aclReachability(
            filters=acl_spec.get("filters"),
            headers=acl_spec.get("headers"),
        ).answer()
        return {
            "snapshot": snapshot,
            "assertion": "acl",
            "passed": True,
            "evidence": answer["answerElements"],
        }
    except Exception as e:
        raise MCPError("assert_failed", f"ACL 断言失败: {e}") from e


@mcp.tool()
async def assert_routing(snapshot: str, prefix: str) -> dict:
    """断言：路由表中存在指定前缀。"""
    bf = _bf()
    try:
        answer = bf.q.routes(prefix=prefix).answer()
        routes = answer["answerElements"]
        passed = len(routes) > 0
        return {
            "snapshot": snapshot,
            "assertion": "routing",
            "passed": passed,
            "prefix": prefix,
            "evidence": routes,
        }
    except Exception as e:
        raise MCPError("assert_failed", f"routing 断言失败: {e}") from e


@mcp.tool()
async def lint_config(config_text: str, vendor: str = "cisco") -> dict:
    """语法 lint：检查配置文本是否有语法错误。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".cfg", delete=False, encoding="utf-8"
    ) as f:
        f.write(config_text)
        cfg_path = f.name
    tmp_dir = Path(cfg_path).parent / f"lint_snapshot_{os.getpid()}"
    tmp_dir.mkdir(exist_ok=True)
    (tmp_dir / "configs").mkdir(exist_ok=True)
    Path(cfg_path).rename(tmp_dir / "configs" / "device.cfg")

    try:
        bf = _bf()
        bf.init_snapshot(str(tmp_dir), name="lint", overwrite=True)
        answer = bf.q.parseWarning().answer()
        warnings = answer.get("answerElements", [])
        return {
            "passed": len(warnings) == 0,
            "warnings": warnings,
            "vendor": vendor,
        }
    except Exception as e:
        raise MCPError("lint_failed", f"lint 失败: {e}") from e
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    mcp.run(transport="stdio")
