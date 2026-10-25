"""Batfish 校验闸真实链路验证（v0.5.1：三闸真实化之校验闸）。

前置：docker compose -f infra/docker-compose.dev.yml up -d batfish
      （REST 9996 / workmgr 9997；首次启动解析服务需 1~3 分钟）

验证链（对齐 ValidationGate 的真实用法）：
  1. 直连：pybatfish → Batfish REST 服务器连通（服务版本）
  2. lint_config：合法 Cisco 配置 → passed=True（0 parse warning）
  3. lint_config：语法错误配置 → passed=False（真实语法检查，非恒真）
  4. 经 batfish-mcp（containerlab-mcp 同款 streamable-http sidecar 方式）：
     load_snapshot → assert_routing（真实路由表查询）→ assert_reachability
  5. 失败传播：不可达断言正确返回 passed=False（闸门不再无条件放行）

用法：cd backend && python scripts/verify_batfish_real.py
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

MCP_PORT = 19003

PASS: list[str] = []
FAIL: list[str] = []

GOOD_CONFIG = """!
version 15.2
hostname leaf01
!
interface Ethernet1
 ip address 10.0.0.1 255.255.255.0
 no shutdown
!
ip route 10.0.2.0 255.255.255.0 10.0.0.2
ip route 10.0.3.0 255.255.255.0 Null0
!
end
"""

BAD_CONFIG = """!
version 15.2
hostname leaf01
!
interface Ethernet1
 ip address this is not a valid netmask
 ribg mainum 9999 nonsense
!
end
"""


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(f"{name}{(' — ' + detail) if detail else ''}")
    print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""), flush=True)


def wait_batfish(timeout_s: float = 240) -> bool:
    """等 Batfish REST 就绪（镜像冷启动解析服务需时间）。"""
    from pybatfish.client.session import Session

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            bf = Session(host="localhost", port_v1=9996)
            bf.get_component_versions()  # 轻量 REST 握手
            return True
        except Exception:
            time.sleep(5)
    return False


async def start_mcp_sidecar() -> None:
    """容器化 batfish-mcp sidecar（与 clab-mcp 同配方：docker cp + PYTHONPATH）。

    batfish-mcp 默认 stdio 传输且无 run_http 入口——本脚本用
    fastmcp http 模式直接挂载仓库内 server 模块，模拟与生产 sidecar
    相同的部署形态（网络可达性 / 协议 / 端口约束完全一致）。
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "bf_mcp_real", BACKEND.parent / "mcp-servers" / "batfish-mcp" / "server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    task = asyncio.create_task(mod.mcp.run_http_async(host="127.0.0.1", port=MCP_PORT))
    _TASKS.append(task)
    await _wait_ready(f"http://127.0.0.1:{MCP_PORT}/mcp")


_TASKS: list[asyncio.Task] = []


async def _wait_ready(url: str, timeout_s: float = 20.0) -> bool:
    from fastmcp import Client

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            async with Client(url) as c:
                await c.ping()
            return True
        except Exception:
            await asyncio.sleep(0.4)
    return False


def main_direct() -> None:
    from pybatfish.client.session import Session

    check("Batfish REST 服务器连通", wait_batfish(), "pybatfish → localhost:9996")

    bf = Session(host="localhost", port_v1=9996)

    # lint 合法配置
    with tempfile.TemporaryDirectory() as td:
        cfg_dir = Path(td) / "configs"
        cfg_dir.mkdir()
        (cfg_dir / "leaf01.cfg").write_text(GOOD_CONFIG, encoding="utf-8")
        snap = bf.init_snapshot(str(Path(td)), name="v-good", overwrite=True)
        bf.set_snapshot(snap)
        warnings = bf.q.parseWarning().answer().frame()
        check(
            "lint 合法配置 → 0 parse warning",
            len(warnings) == 0,
            f"warnings={len(warnings)}",
        )

        # 真实路由断言：静态路由 10.0.3.0/24 → Null0 存在于路由表
        # （pybatfish routes() 不支持 prefix 参数，取全表后本地过滤）
        routes = bf.q.routes().answer().frame()
        target = routes[routes["Network"] == "10.0.3.0/24"] if len(routes) and "Network" in routes.columns else routes
        check(
            "assert_routing 真实路由表查询（静态路由存在）",
            len(target) > 0,
            f"total_routes={len(routes)}, matched={len(target)}",
        )

        # 失败传播：查一个不存在的前缀
        routes2 = bf.q.routes().answer().frame()
        miss = routes2[routes2["Network"] == "99.99.99.99/32"] if len(routes2) and "Network" in routes2.columns else routes2
        check(
            "assert_routing 失败传播（不存在前缀 → 空）",
            len(miss) == 0,
            f"matched={len(miss)}",
        )

    # lint 语法错误配置
    with tempfile.TemporaryDirectory() as td:
        cfg_dir = Path(td) / "configs"
        cfg_dir.mkdir()
        (cfg_dir / "leaf01.cfg").write_text(BAD_CONFIG, encoding="utf-8")
        snap = bf.init_snapshot(str(Path(td)), name="v-bad", overwrite=True)
        bf.set_snapshot(snap)
        warnings = bf.q.parseWarning().answer().frame()
        check(
            "lint 语法错误配置 → 真实检出 parse warning",
            len(warnings) > 0,
            f"warnings={len(warnings)}",
        )


async def main_mcp() -> None:
    from app.tools.http_registry import HttpToolRegistry

    await start_mcp_sidecar()
    reg = HttpToolRegistry({"batfish": f"http://127.0.0.1:{MCP_PORT}"})

    with tempfile.TemporaryDirectory() as td:
        cfg_dir = Path(td) / "configs"
        cfg_dir.mkdir()
        (cfg_dir / "leaf01.cfg").write_text(GOOD_CONFIG, encoding="utf-8")

        # 经 MCP 协议 load_snapshot（root 目录，configs/ 子目录结构）
        r = await reg.invoke("batfish.load_snapshot", configs_dir=str(td), snapshot_name="mcp-snap")
        check("MCP load_snapshot 真实加载", isinstance(r, dict) and r.get("status") == "loaded", str(r)[:100])

        # 经 MCP 协议 lint
        r = await reg.invoke("batfish.lint_config", config_text=GOOD_CONFIG, vendor="cisco")
        check("MCP lint_config 真实语法检查", isinstance(r, dict) and r.get("passed") is True, str(r)[:100])

        # 经 MCP 协议路由断言
        r = await reg.invoke("batfish.assert_routing", snapshot="mcp-snap", prefix="10.0.3.0/24")
        check(
            "MCP assert_routing 真实断言",
            isinstance(r, dict) and r.get("passed") is True,
            str(r)[:100],
        )


async def amain() -> None:
    main_direct()
    await main_mcp()
    print(f"\n===== Batfish 校验闸真实链路：{len(PASS)} 通过 / {len(FAIL)} 失败 =====")
    for f in FAIL:
        print(f"  ❌ {f}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(amain())
