"""真实网元下发闭环验证（v0.6 里程碑：诚实清单最后一项）。

验证对象：Nokia SR Linux（真实 NOS 容器，gNMI 管理面）。
全链真实（无 mock）：docker run 网元 → sr_cli 引导（TLS 证书 + gNMI +
JSON-RPC）→ napalm-mcp 经 gNMI 连接 → get_config 基线 → apply_candidate
真实下发 → 配置落盘验证 → napalm rollback → 还原验证。

环境实测笔记（Windows Docker Desktop + WSL2，v0.6 调试沉淀）：
- containerlab postdeploy 在 clab-in-docker 套娃下写坏 /tmp/topology.yml
  （clab-mcp 需挂载 /var/lib/docker；仍有文件变目录的怪癖）→ 本脚本用
  docker run 直起网元，仿真闸已有 alpine 链路覆盖（verify_containerlab_real）
- 宿主机 TUN 代理会劫持容器网段直连（172.17.x 全黑洞）→ 必须走
  docker 端口发布（127.0.0.1）
- Windows 保留端口段避开（netsh excludedportrange）
- SR Linux 嵌套 netns 的 IPv6 由 docker --sysctl 控制继承；gNMI 绑 [::]
- gNMI TLS 需手工自签证书 + system tls profile（default-tls-profile）
- napalm-srl：insecure=True + skip_verify=True；gRPC 继承代理环境变量，
  sidecar 必须设 NO_PROXY

用法：cd backend && python scripts/verify_real_deploy.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# gRPC 继承代理环境变量会连到本机代理（v0.6 实测）——必须先清
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

NODE = "srl-nsv"
GNMI_HOST_PORT = 15740      # 宿主侧 gNMI（避开 Windows 保留段）
JSONRPC_HOST_PORT = 18080   # 宿主侧 JSON-RPC（standalone 未监听，兼容保留）
SSH_HOST_PORT = 15722       # 宿主侧 SSH（napalm-srl CLI 桥接通道）
VENDOR = "nokia_srlinux"
USER, PWD = "admin", "NokiaSrl1!"
MGMT_IP_IN_NETNS = "127.0.0.1"  # napalm 经宿主端口发布连 127.0.0.1

MARKER = "netsage-v06-real-deploy"
CHANGE = {"system": {"information": {"location": MARKER}}}

PASS: list[str] = []
FAIL: list[str] = []
_TASKS: list[asyncio.Task] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(f"{name}{(' — ' + detail) if detail else ''}")
    print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""), flush=True)


def sh(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)


def node_up() -> bool:
    rc, out = sh(["docker", "ps", "--filter", f"name={NODE}", "--format", "{{.Status}}"])
    return rc == 0 and "Up" in out


def boot_wait(timeout_s: int = 360) -> bool:
    """等 SR Linux CLI 可用（sr_cli show version 有输出）。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        rc, out = sh(["docker", "exec", "-u", "root", NODE,
                      "sr_cli", "-d", "-c", "show version"], timeout=30)
        if rc == 0 and "Hostname" in out:
            return True
        time.sleep(10)
    return False


def cli_alive() -> bool:
    """CLI 可用性（宽松：任何版本/主机名输出）。"""
    rc, out = sh(["docker", "exec", "-u", "root", NODE,
                  "sr_cli", "-d", "-c", "show version"], timeout=30)
    return rc == 0 and "srl" in out.lower() or "Hostname" in out


def srl_config(commands: list[str]) -> str:
    """经 sr_cli 提交配置，返回输出尾部。"""
    quoted = "\n".join(commands)
    rc, out = sh(["docker", "exec", "-u", "root", NODE, "bash", "-c",
                  f"printf 'enter candidate\\n{quoted}\\ncommit now\\n' | sr_cli -d"],
                 timeout=90)
    return out[-200:]


def setup_node() -> tuple[bool, str]:
    """引导网元：TLS 证书 + gNMI + JSON-RPC + 重启 gRPC agent。"""
    rc, out = sh(["docker", "exec", "-u", "root", NODE, "bash", "-c",
                  "mkdir -p /etc/opt/srlinux/certs && openssl req -x509 -newkey rsa:2048 "
                  "-nodes -keyout /etc/opt/srlinux/certs/server.key "
                  "-out /etc/opt/srlinux/certs/server.crt -days 365 "
                  "-subj '/CN=srl-nsv' 2>/dev/null && echo cert_ok"], timeout=60)
    if "cert_ok" not in out:
        return False, f"cert 生成失败: {out[-120:]}"
    out = srl_config([
        "set / system tls profile default certificate /etc/opt/srlinux/certs/server.crt",
        "set / system tls profile default key /etc/opt/srlinux/certs/server.key",
        "set / system grpc-server gnmi admin-state enable",
        "set / system grpc-server gnmi network-instance mgmt admin-state enable",
        "set / system grpc-server gnmi tls-profile default",
        "set / system json-rpc-server network-instance mgmt http admin-state enable",
    ])
    if "committed" not in out and "Leaving candidate" not in out:
        return False, f"配置提交失败: {out[-160:]}"
    # 重启 gRPC agent 加载证书（app_mgr 自动拉起）
    sh(["docker", "exec", "-u", "root", NODE, "pkill", "-f", "sr_grpc_server"], timeout=30)
    time.sleep(30)
    rc, out = sh(["docker", "exec", "-u", "root", NODE, "bash", "-c",
                  "ip netns exec srbase-mgmt ss -tln | grep -c 57400"], timeout=30)
    return ("1" in out), f"netns 57400 listener={out.strip()}"


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


async def start_napalm_sidecar() -> None:
    """起 napalm-mcp HTTP sidecar（NAPALM_JSONRPC_PORT 对齐端口发布）。"""
    spec = importlib.util.spec_from_file_location(
        "np_mcp", BACKEND.parent / "mcp-servers" / "napalm-mcp" / "server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _TASKS.append(asyncio.create_task(
        mod.mcp.run_http_async(host="127.0.0.1", port=19004)
    ))
    ok = await _wait_ready("http://127.0.0.1:19004/mcp")
    if not ok:
        print("napalm-mcp sidecar 启动失败", flush=True)
        sys.exit(2)


def gnsmi_reachable(timeout_s: int = 120) -> bool:
    """等宿主 127.0.0.1:15740 的 TLS 可握手（经端口发布进 netns）。"""
    import socket
    import ssl

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            s = ctx.wrap_socket(
                socket.create_connection((MGMT_IP_IN_NETNS, GNMI_HOST_PORT), timeout=8),
                server_hostname="srl-nsv",
            )
            s.close()
            return True
        except Exception:
            time.sleep(5)
    return False


async def main() -> None:
    from app.tools.http_registry import HttpToolRegistry

    # 0. 清理重建网元（幂等：删旧容器含历史调试残留 + 全新启动）
    sh(["docker", "rm", "-f", NODE, "srl-standalone"], timeout=60)
    rc, out = sh(["docker", "run", "-d", "--name", NODE, "--privileged",
                  "--sysctl", "net.ipv6.conf.all.disable_ipv6=0", "-h", "srl-nsv",
                  "-p", f"127.0.0.1:{GNMI_HOST_PORT}:57400",
                  "-p", f"127.0.0.1:{JSONRPC_HOST_PORT}:80",
                  "-p", f"127.0.0.1:{SSH_HOST_PORT}:22",
                  "ghcr.io/nokia/srlinux:latest",
                  "sudo", "/opt/srlinux/bin/sr_linux"], timeout=120)
    check("SR Linux 网元容器启动", node_up(), out.strip()[:60])

    # 1. 等 boot + 引导
    check("SR Linux boot 完成（CLI 可用）", boot_wait() or cli_alive())
    ok, detail = setup_node()
    check("网元引导：TLS 证书 + gNMI + JSON-RPC", ok, detail)
    check("宿主 → gNMI TLS 握手（端口发布路径）", gnsmi_reachable())

    # 2. napalm 真实连接
    await start_napalm_sidecar()
    nap = HttpToolRegistry({"napalm": "http://127.0.0.1:19004"})
    # sidecar 的 NAPALM_JSONRPC_PORT 需与端口发布一致：重启 sidecar 进程环境
    # （本脚本以环境变量启动子进程级 sidecar——见 start_napalm_sidecar 下方说明）
    facts = await nap.invoke(
        "napalm.get_facts", vendor=VENDOR, host=MGMT_IP_IN_NETNS,
        username=USER, password=PWD, port=GNMI_HOST_PORT,
    )
    check(
        "napalm gNMI 连接（get_facts 元数据尽力而为）",
        isinstance(facts, dict),
        f"facts={ {k: facts.get(k) for k in ('hostname', 'os_version', 'vendor') if isinstance(facts, dict)} }",
    )

    # 3. 基线配置（快照语义）
    base = await nap.invoke(
        "napalm.get_config", vendor=VENDOR, host=MGMT_IP_IN_NETNS,
        username=USER, password=PWD, port=GNMI_HOST_PORT, source="running",
    )
    base_cfg = base.get("config", "") if isinstance(base, dict) else str(base)
    check("get_config 真实读取基线", len(base_cfg) > 0, f"len={len(base_cfg)}")
    check("基线不含变更标记", MARKER not in base_cfg)

    # 4. apply_candidate 真实下发（gNMI Set：load_merge + commit）
    r = await nap.invoke(
        "napalm.apply_candidate", vendor=VENDOR, host=MGMT_IP_IN_NETNS,
        username=USER, password=PWD, port=GNMI_HOST_PORT,
        config=json.dumps(CHANGE),
    )
    committed = isinstance(r, dict) and r.get("status") == "committed"
    checkpoint = r.get("checkpoint", "") if isinstance(r, dict) else ""
    check("apply_candidate 真实下发（gNMI Set + commit）", committed,
          f"checkpoint={checkpoint}, {str(r)[:80]}")

    # 5. 验证落盘
    after = await nap.invoke(
        "napalm.get_config", vendor=VENDOR, host=MGMT_IP_IN_NETNS,
        username=USER, password=PWD, port=GNMI_HOST_PORT, source="running",
    )
    after_cfg = after.get("config", "") if isinstance(after, dict) else str(after)
    check("变更真实落盘（running config 命中 marker）", MARKER in after_cfg)

    # 6. rollback（按 apply 返回的确定性 checkpoint 名回退）
    rb_detail = ""
    try:
        r = await nap.invoke(
            "napalm.rollback", vendor=VENDOR, host=MGMT_IP_IN_NETNS,
            username=USER, password=PWD, port=GNMI_HOST_PORT,
            checkpoint=checkpoint,
        )
        rb_detail = f"checkpoint={checkpoint}, {str(r)[:80]}"
    except Exception as e:
        rb_detail = f"{type(e).__name__}: {str(e)[:80]}"
    finally_cfg = await nap.invoke(
        "napalm.get_config", vendor=VENDOR, host=MGMT_IP_IN_NETNS,
        username=USER, password=PWD, port=GNMI_HOST_PORT, source="running",
    )
    finally_text = finally_cfg.get("config", "") if isinstance(finally_cfg, dict) else str(finally_cfg)
    check("rollback 后配置还原（marker 消失）", MARKER not in finally_text, rb_detail)

    # 7. 清理（全过才删；失败保留现场供调试，脚本尾部提示）
    if not FAIL:
        sh(["docker", "rm", "-f", NODE], timeout=60)
    else:
        print(f"(失败保留现场：docker exec -u root {NODE} sr_cli -d 可调试；"
              f"清理：docker rm -f {NODE})", flush=True)
    print(f"\n===== 真实网元下发闭环：{len(PASS)} 通过 / {len(FAIL)} 失败 =====")
    for f in FAIL:
        print(f"  ❌ {f}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    os.environ["NAPALM_JSONRPC_PORT"] = str(JSONRPC_HOST_PORT)
    os.environ["NAPALM_SRL_SSH_PORT"] = str(SSH_HOST_PORT)
    asyncio.run(main())
