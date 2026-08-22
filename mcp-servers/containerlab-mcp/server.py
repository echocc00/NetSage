"""Containerlab MCP Server（v2.0 开发计划九章 9.2）。

工具：deploy_topology / destroy_topology / inspect_topology / save_topology / exec_on_node
部署：开发态 sidecar（docker-compose），生产态 K8s Deployment（v2.0 26.3）。

需 Docker socket 或远程 containerlab_host（SSH 跳板机，v2.0 风险表）。
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from fastmcp import FastMCP

from netsage_mcp_shared import MCPError, log

mcp = FastMCP("containerlab-mcp")

CONTAINERLAB_HOST = os.getenv("CONTAINERLAB_HOST", "")  # 远程 SSH 模式（v2.0 风险表）
CLAB_BIN = os.getenv("CLAB_BIN", "containerlab")


async def _run(cmd: list[str]) -> tuple[int, str, str]:
    """异步执行命令，返回 (returncode, stdout, stderr)。"""
    log.info("clab_exec", cmd=" ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()


@mcp.tool()
async def deploy_topology(topo_yaml: str, name: str) -> dict:
    """部署 containerlab 拓扑，返回节点状态。

    Args:
        topo_yaml: containerlab 声明式 YAML 内容
        name: 拓扑名称（lab prefix）
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".clab.yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(topo_yaml)
        topo_path = f.name

    try:
        rc, out, err = await _run([CLAB_BIN, "deploy", "-t", topo_path])
        if rc != 0:
            raise MCPError("deploy_failed", f"containerlab deploy 失败: {err}", out)
        inspect = await _inspect(name)
        log.info("clab_deployed", name=name, nodes=len(inspect.get("nodes", [])))
        return {"name": name, "status": "deployed", **inspect}
    finally:
        Path(topo_path).unlink(missing_ok=True)


@mcp.tool()
async def destroy_topology(name: str) -> dict:
    """销毁指定拓扑。"""
    rc, out, err = await _run([CLAB_BIN, "destroy", "-c", "--label", f"clab-node-lab-name={name}"])
    if rc != 0 and "not found" not in err.lower():
        raise MCPError("destroy_failed", f"destroy 失败: {err}", out)
    log.info("clab_destroyed", name=name)
    return {"name": name, "status": "destroyed"}


@mcp.tool()
async def inspect_topology(name: str) -> dict:
    """查看拓扑节点与链路状态。"""
    return await _inspect(name)


async def _inspect(name: str) -> dict:
    rc, out, err = await _run([CLAB_BIN, "inspect", "-c", "--label", f"clab-node-lab-name={name}"])
    if rc != 0:
        return {"name": name, "nodes": [], "raw": err}
    # containerlab inspect 输出表格，简化解析
    lines = [l for l in out.splitlines() if l.strip() and not l.startswith("+-")][1:]
    nodes = []
    for line in lines:
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 4:
            nodes.append({"name": parts[0], "kind": parts[1] if len(parts) > 1 else "", "image": parts[2] if len(parts) > 2 else ""})
    return {"name": name, "nodes": nodes}


# 仿真内只读诊断命令白名单（审查 C3 修复：防 shell 注入）
ALLOWED_EXEC_PREFIXES = ("show ", "ping ", "traceroute ", "ip route ", "ip address ",
                         "display ", "dis ", "bgp ", "ospf ")
VALID_NAME_RE = r"^[a-zA-Z0-9_-]{1,64}$"


def _validate_exec_command(command: str) -> None:
    """校验仿真内执行命令：仅允许白名单前缀的只读诊断命令。

    不用 sh -c 拼 shell（防 `; rm -rf` 注入），直接数组传参给 docker exec。
    """
    import re

    stripped = command.strip()
    if not stripped.lower().startswith(ALLOWED_EXEC_PREFIXES):
        raise MCPError(
            "command_denied",
            f"命令不在白名单内（仅允许诊断命令：show/ping/traceroute/display/bgp/ospf）: {stripped[:80]}",
        )
    if any(ch in stripped for ch in (";", "|", "&&", "||", "`", "$(", ">", "<")):
        raise MCPError("command_denied", "命令含 shell 特殊字符，拒绝执行")


@mcp.tool()
async def exec_on_node(name: str, node: str, command: str) -> dict:
    """在仿真拓扑的指定节点上执行只读诊断命令（show/ping/traceroute）。

    安全：命令过白名单 + 禁 shell 特殊字符（审查 C3 修复）。
    """
    import re
    if not re.fullmatch(VALID_NAME_RE, name) or not re.fullmatch(VALID_NAME_RE, node):
        raise MCPError("invalid_name", "拓扑名/节点名仅允许字母数字、横线、下划线（≤64 字符）")
    _validate_exec_command(command)

    # 数组传参，不经过 shell 解释
    container = f"clab-{name}-{node}"
    cmd = command.strip().split()
    if not cmd:
        raise MCPError("command_empty", "命令为空")
    rc, out, err = await _run(["docker", "exec", container, *cmd])
    if rc != 0:
        raise MCPError("exec_failed", f"exec on {node} 失败: {err}", out)
    return {"node": node, "stdout": out, "stderr": err}


@mcp.tool()
async def save_topology(name: str, path: str) -> str:
    """保存当前拓扑为模板文件（仅允许写入指定导出目录）。"""
    import re

    if not re.fullmatch(VALID_NAME_RE, name):
        raise MCPError("invalid_name", "拓扑名仅允许字母数字、横线、下划线")
    # 审查 M4 修复：限定导出目录，防路径遍历
    export_root = Path(os.getenv("CLAB_EXPORT_DIR", "/tmp/clab-exports"))
    export_root.mkdir(parents=True, exist_ok=True)
    target = (export_root / path).resolve()
    if not target.is_relative_to(export_root.resolve()):
        raise MCPError("path_denied", "导出路径必须在导出目录内")

    rc, out, err = await _run([CLAB_BIN, "inspect", "-c", "--label", f"clab-node-lab-name={name}", "--format", "yaml"])
    if rc != 0:
        raise MCPError("save_failed", f"save 失败: {err}", out)
    target.write_text(out, encoding="utf-8")
    return str(target)


if __name__ == "__main__":
    mcp.run(transport="stdio")
