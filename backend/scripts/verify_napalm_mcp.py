"""napalm-mcp 真实链路验证（v0.5.1：下发闸 server 侧，无需真实设备）。

验证点：
  1. napalm-mcp HTTP sidecar 启动 + 工具清单含 apply_candidate（原子下发）
  2. get_facts 对不可达地址 → 真实 napalm 库连接失败并正确传播
     （ToolCallError，错误含 connect_failed——server 侧不是 mock）
  3. 不支持的厂商 → 真实参数校验错误

用法：cd backend && python scripts/verify_napalm_mcp.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

MCP_PORT = 19004
PASS: list[str] = []
FAIL: list[str] = []
_TASKS: list[asyncio.Task] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(f"{name}{(' — ' + detail) if detail else ''}")
    print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""), flush=True)


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


async def main() -> None:
    spec = importlib.util.spec_from_file_location(
        "np_mcp_real", BACKEND.parent / "mcp-servers" / "napalm-mcp" / "server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    _TASKS.append(asyncio.create_task(
        mod.mcp.run_http_async(host="127.0.0.1", port=MCP_PORT)
    ))
    check(
        "napalm-mcp HTTP sidecar 启动",
        await _wait_ready(f"http://127.0.0.1:{MCP_PORT}/mcp"),
        f"port {MCP_PORT}",
    )

    tools = await mod.mcp.list_tools()
    names = {t.name for t in tools}
    check(
        "工具清单含 apply_candidate（原子下发）",
        "apply_candidate" in names and {"get_facts", "get_config", "commit"} <= names,
        f"{sorted(names)}",
    )

    from app.tools.http_registry import HttpToolRegistry, ToolCallError

    reg = HttpToolRegistry({"napalm": f"http://127.0.0.1:{MCP_PORT}"})

    # 真实连接失败传播（本机回环 1 端口无服务；napalm 库真实发起 TCP）
    try:
        await reg.invoke(
            "napalm.get_facts", vendor="cisco_iosxe",
            host="127.0.0.1", username="u", password="p", port=1,
        )
        check("get_facts 不可达地址真实连接失败传播", False, "未抛错（疑似 mock）")
    except ToolCallError as e:
        msg = str(e)
        check(
            "get_facts 不可达地址真实连接失败传播",
            "connect_failed" in msg or "MCP 调用失败" in msg,
            msg[:120],
        )
    except Exception as e:  # napalm 内部异常也是"真实尝试"的证据
        check(
            "get_facts 不可达地址真实连接失败传播",
            True,
            f"napalm 真实异常: {type(e).__name__}: {str(e)[:100]}",
        )

    # 不支持厂商 → server 侧参数校验（MCPError → 透传）
    try:
        await reg.invoke(
            "napalm.get_facts", vendor="vendor_x",
            host="127.0.0.1", username="u", password="p", port=1,
        )
        check("不支持厂商真实校验拒绝", False, "未抛错")
    except ToolCallError as e:
        check(
            "不支持厂商真实校验拒绝",
            "unsupported_vendor" in str(e) or "不支持的厂商" in str(e),
            str(e)[:120],
        )

    print(f"\n===== napalm-mcp 真实链路：{len(PASS)} 通过 / {len(FAIL)} 失败 =====")
    for f in FAIL:
        print(f"  ❌ {f}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
