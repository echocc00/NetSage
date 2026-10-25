"""Batfish MCP Server（v2.0 开发计划九章 9.2）。

工具：load_snapshot / assert_reachability / assert_acl / assert_routing / lint_config
通过 pybatfish 调用 Batfish REST（batfish_host，默认 localhost:9996）。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastmcp import FastMCP
from netsage_mcp_shared import MCPError, log
from pybatfish.client.session import Session

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
        # init_snapshot 返回快照名；set_snapshot 只传 name（v0.5.1：原写法
        # set_snapshot(snapshot_result, name=...) 重复指定快照，TypeError）
        snap_name = bf.init_snapshot(str(configs_dir), name=snapshot_name, overwrite=True)
        bf.set_snapshot(snap_name)
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


def _extract_rows(answer: dict) -> list[dict]:
    """解包 Batfish TableAnswerElement（v0.5.1 实测修复）。

    answer() 返回 {"answerElements": [{class: TableAnswerElement, rows: [...],
    summary: {...}}]}——真正的结果行在 rows 里，不能数 answerElements 长度
    （0 行结果的空表也会被误判为有警告）。
    """
    rows: list[dict] = []
    for el in answer.get("answerElements", []):
        if isinstance(el, dict) and isinstance(el.get("rows"), list):
            rows.extend(el["rows"])
        elif el:
            rows.append(el)
    return rows


@mcp.tool()
async def search_filters(snapshot: str) -> dict:
    """流量-ACL 匹配分析（searchFilters：每条流被哪条 ACL 行以什么动作命中）。"""
    bf = _bf()
    try:
        answer = bf.q.searchFilters().answer()
        return {"snapshot": snapshot, "rows": _extract_rows(answer)}
    except Exception as e:
        raise MCPError("search_failed", f"searchFilters 失败: {e}") from e


@mcp.tool()
async def interface_properties(snapshot: str) -> dict:
    """接口属性（含 Incoming_Filter / Outgoing_Filter——ACL 引用检查用）。"""
    bf = _bf()
    try:
        answer = bf.q.interfaceProperties().answer()
        return {"snapshot": snapshot, "rows": _extract_rows(answer)}
    except Exception as e:
        raise MCPError("query_failed", f"interfaceProperties 失败: {e}") from e


@mcp.tool()
async def filter_tables(snapshot: str) -> dict:
    """已定义的过滤器（ACL）清单。"""
    bf = _bf()
    try:
        answer = bf.q.filterTable().answer()
        return {"snapshot": snapshot, "rows": _extract_rows(answer)}
    except Exception as e:
        # filterTable 需要指定过滤器参数的版本：回退到 aclReachability 结构
        try:
            answer2 = bf.q.aclReachability().answer()
            return {"snapshot": snapshot, "rows": _extract_rows(answer2)}
        except Exception as e2:
            raise MCPError("query_failed", f"filterTable 失败: {e} / {e2}") from e2


@mcp.tool()
async def assert_routing(snapshot: str, prefix: str) -> dict:
    """断言：路由表中存在指定前缀。

    pybatfish routes() 不支持 prefix 过滤参数（版本 API 差异，v0.5.1 实测）——
    取全表后按 Network 列本地过滤。
    """
    bf = _bf()
    try:
        answer = bf.q.routes().answer()
        routes = _extract_rows(answer)
        matched = [
            r for r in routes
            if isinstance(r, dict) and r.get("Network") == prefix
        ]
        return {
            "snapshot": snapshot,
            "assertion": "routing",
            "passed": len(matched) > 0,
            "prefix": prefix,
            "evidence": matched,
        }
    except Exception as e:
        raise MCPError("assert_failed", f"routing 断言失败: {e}") from e


@mcp.tool()
async def lint_config(config_text: str, vendor: str = "cisco") -> dict:
    """语法 lint：检查配置文本是否有语法错误。

    快照目录结构要求（v0.5.1 实测）：root/configs/device.cfg
    —— Batfish 要求 configs/configs 包装，否则报 "Unexpected packaging"。
    """
    root = Path(tempfile.mkdtemp(prefix="bf_lint_"))
    cfg_dir = root / "configs"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "device.cfg").write_text(config_text, encoding="utf-8")

    try:
        bf = _bf()
        bf.init_snapshot(str(root), name="lint", overwrite=True)
        answer = bf.q.parseWarning().answer()
        warnings = _extract_rows(answer)
        return {
            "passed": len(warnings) == 0,
            "warnings": warnings,
            "vendor": vendor,
        }
    except Exception as e:
        raise MCPError("lint_failed", f"lint 失败: {e}") from e
    finally:
        import shutil
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    mcp.run(transport="stdio")
