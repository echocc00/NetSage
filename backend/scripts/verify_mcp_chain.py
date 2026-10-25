"""MCP 真实链路验证（v0.5.0 阶段2 收尾验证）。

验证三件事（需要 docker dev PG 在线；不需要 containerlab 二进制）：
1. HttpToolRegistry → fastmcp HTTP server 的真实 MCP 协议调用（正例：内联 server）。
2. TOOLS_BACKEND=mcp 下三道闸全链：create → run → approve → deploy，
   闸门结果来自真实 MCP HTTP 响应（非 mock stub）。
3. 真实 containerlab-mcp（无 containerlab CLI 的宿主机）→ 仿真闸真实失败传播：
   闸门不再"必过"，会把真实错误显式暴露（sim_failed）。

用法：cd backend && python scripts/verify_mcp_chain.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# 必须在导入 app 前 set env（Settings lru_cache + TOOLS_BACKEND 装配）
os.environ["TOOLS_BACKEND"] = "mcp"
os.environ["MCP_CONTAINERLAB_URL"] = "http://127.0.0.1:19001"
os.environ["MCP_BATFISH_URL"] = "http://127.0.0.1:19001"
os.environ["MCP_NAPALM_URL"] = "http://127.0.0.1:19001"

PASS: list[str] = []
FAIL: list[str] = []
# 强引用持有 server task（create_task 无引用会被 GC 静默杀死）
_SERVER_TASKS: list[asyncio.Task] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(f"{name}{(' — ' + detail) if detail else ''}")
    print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""), flush=True)


async def _wait_server_ready(url: str, timeout_s: float = 15.0) -> bool:
    """轮询 MCP server HTTP 就绪（避免固定 sleep 的竞态）。"""
    import time

    from fastmcp import Client

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            async with Client(url) as c:
                await c.ping()
            return True
        except Exception:
            await asyncio.sleep(0.5)
    return False


async def start_inline_server() -> None:
    """内联 MCP server：承载全部三道闸工具的正例响应（真实 HTTP 协议）。"""
    from fastmcp import FastMCP

    mcp = FastMCP("inline-echo")

    @mcp.tool()
    def deploy_topology(topo_yaml: str, name: str) -> dict:
        return {"status": "deployed", "nodes": [{"name": "n1"}]}

    @mcp.tool()
    def exec_on_node(name: str, node: str, command: str) -> dict:
        return {"stdout": "BGP neighbor is Up"}

    @mcp.tool()
    def lint_config(config_text: str, vendor: str) -> dict:
        return {"passed": True, "warnings": []}

    @mcp.tool()
    def assert_reachability(snapshot: str, src: str, dst: str) -> dict:
        return {"passed": True}

    @mcp.tool()
    def assert_routing(snapshot: str, prefix: str) -> dict:
        return {"passed": True}

    @mcp.tool()
    def get_config(vendor: str, host: str, username: str, password: str,
                   source: str = "running", port: int = 22) -> dict:
        return {"host": host, "source": source, "config": "interface GE0/0/1"}

    @mcp.tool()
    def apply_candidate(vendor: str, host: str, username: str, password: str,
                        config: str, port: int = 22) -> dict:
        return {"host": host, "status": "committed", "diff": ""}

    _SERVER_TASKS.append(asyncio.create_task(
        mcp.run_http_async(host="127.0.0.1", port=19001)
    ))
    ready = await _wait_server_ready("http://127.0.0.1:19001/mcp")
    if not ready:
        print("内联 MCP server 启动失败（端口 19001）", flush=True)
        sys.exit(2)


async def start_real_containerlab_server() -> None:
    """真实 containerlab-mcp（mcp-servers/ 源码）：本机无 containerlab CLI，
    工具调用应返回真实失败——用于验证闸门的真实失败传播。"""
    spec = importlib.util.spec_from_file_location(
        "cl_mcp_real", BACKEND.parent / "mcp-servers" / "containerlab-mcp" / "server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _SERVER_TASKS.append(asyncio.create_task(
        mod.mcp.run_http_async(host="127.0.0.1", port=19002)
    ))
    ready = await _wait_server_ready("http://127.0.0.1:19002/mcp")
    if not ready:
        check("真实 containerlab-mcp 启动", False, "端口 19002 未就绪")
        return


async def main() -> None:
    await start_inline_server()

    # ── 1. HttpToolRegistry 直接调用（真实 MCP HTTP 协议）──
    from app.tools.http_registry import HttpToolRegistry

    reg = HttpToolRegistry({"containerlab": "http://127.0.0.1:19001"})
    result = await reg.invoke("containerlab.deploy_topology", topo_yaml="name: t", name="t1")
    check("HttpToolRegistry → MCP HTTP 真实调用", result.get("status") == "deployed", str(result))

    # ── 2. TOOLS_BACKEND=mcp 三道闸全链（真实 uvicorn + httpx，非 TestClient：
    #       fastmcp 客户端在 TestClient portal loop 会触发 mcp 库跨 loop 冲突）──
    import httpx
    import uvicorn

    from app.core.security import CurrentUser, Role, encode_token

    admin = {"Authorization": f"Bearer {encode_token(CurrentUser(id=1, name='a', role=Role.ADMIN))}"}
    eng = {"Authorization": f"Bearer {encode_token(CurrentUser(id=2, name='e', role=Role.ENGINEER))}"}

    server = uvicorn.Server(uvicorn.Config(
        "app.main:app", host="127.0.0.1", port=8800, log_level="warning"
    ))
    _SERVER_TASKS.append(asyncio.create_task(server.serve()))
    for _ in range(40):  # 等 uvicorn 就绪
        try:
            async with httpx.AsyncClient() as probe:
                if (await probe.get("http://127.0.0.1:8800/api/v1/health")).status_code == 200:
                    break
        except Exception:
            await asyncio.sleep(0.5)

    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8800", timeout=httpx.Timeout(120.0)
    ) as client:
        from app.agents.registry import tools_mode

        check("启动装配为 mcp 模式", tools_mode() == "mcp", f"tools_mode={tools_mode()}")

        r = await client.post("/api/v1/changes", headers=eng, json={
            "title": "MCP-链路验证", "nim": {"sim_checks": [{"node": "n1", "command": "show bgp", "expect": "Up"}]},
            "devices": [{"id": 1, "name": "d1", "vendor": "huawei_vrp", "host": "1.1.1.1",
                         "username": "u", "password": "p"}],
            "configs": {"d1": "router bgp 65001"},
            "assertions": [{"type": "reachability", "src": "n1", "dst": "n2"}],
        })
        cid = r.json()["data"]["id"]
        check("变更单创建（DB 模式）", r.status_code == 200, f"id={cid}")

        r = await client.post(f"/api/v1/changes/{cid}/run", headers=eng)
        result = r.json()["data"]
        gates = [s["gate"] for s in result.get("steps", [])]
        check(
            "三道闸全链通过（结果来自真实 MCP 响应）",
            result.get("status") == "approval" and "simulation" in gates and result.get("tools_mode") == "mcp",
            f"status={result.get('status')}, gates={gates}",
        )

        await client.post(f"/api/v1/changes/{cid}/approve?decision=approved", headers=admin)
        r = await client.post(f"/api/v1/changes/{cid}/deploy", headers=admin)
        result = r.json()["data"]
        check(
            "下发经真实 apply_candidate → done",
            result.get("status") == "done" and result.get("tools_mode") == "mcp",
            f"status={result.get('status')}, steps={result.get('steps')}",
        )

        # ── 3. 真实 containerlab-mcp：无 CLI 的宿主机 → 仿真闸真实失败 ──
        await start_real_containerlab_server()
        from app.agents.registry import configure_tools
        from app.tools.http_registry import HttpToolRegistry

        real_urls = {
            "containerlab": "http://127.0.0.1:19002",
            "batfish": "http://127.0.0.1:19001",
            "napalm": "http://127.0.0.1:19001",
        }
        configure_tools(HttpToolRegistry(real_urls), "mcp")  # 模拟只把 containerlab 切到真实 server
        # 注意：uvicorn worker 内的全局 registry 无法从外部进程注入——本脚本
        # 单进程运行，configure_tools 直接生效于同一进程

        r2 = await client.post("/api/v1/changes", headers=eng, json={
            "title": "MCP-真实失败传播", "nim": {"sim_checks": []},
            "devices": [{"id": 9, "name": "d9", "vendor": "huawei_vrp", "host": "1.1.1.1",
                         "username": "u", "password": "p"}],
            "configs": {"d9": "router bgp 65001"}, "assertions": [],
        })
        cid2 = r2.json()["data"]["id"]
        r3 = await client.post(f"/api/v1/changes/{cid2}/run", headers=eng)
        result3 = r3.json()["data"]
        sim_error = str(result3.get("error", ""))
        check(
            "真实失败传播：无 containerlab CLI → 仿真闸 sim_failed（不再必过）",
            result3.get("status") == "sim_failed" and "仿真" in sim_error,
            f"status={result3.get('status')}, error={sim_error[:150]}",
        )

    server.should_exit = True
    await asyncio.sleep(1)

    # ── 汇总 ──
    print(f"\n===== MCP 链路验证：{len(PASS)} 通过 / {len(FAIL)} 失败 =====")
    for f in FAIL:
        print(f"  ❌ {f}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
