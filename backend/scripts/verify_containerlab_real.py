"""containerlab 真实拓扑部署验证（v0.5.0 阶段2 收尾：诚实清单最后一项）。

前置（一次性环境搭建，见 CHANGELOG「containerlab 容器化 sidecar」）：
  docker run -d --name clab-mcp -p 19002:9001 -v //var/run/docker.sock:/var/run/docker.sock \
    debian:bookworm-slim sleep infinity
  容器内安装：docker.io + python3-pip + containerlab(.deb) + fastmcp/structlog，
  docker cp mcp-sources，PYTHONPATH 起 containerlab-mcp/run_http.py（0.0.0.0:9001）

验证链（宿主机执行）：
  HttpToolRegistry → 容器内 containerlab-mcp → 真实 containerlab：
  1. deploy_topology：真实创建 2 节点 alpine 拓扑（clab-nsv-* 容器落在宿主 Docker）
  2. inspect_topology：返回真实节点清单
  3. exec_on_node：真实 docker exec 进节点跑 ping（白名单只读命令）
  4. destroy_topology：真实销毁清理
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

PASS: list[str] = []
FAIL: list[str] = []

TOPO = """name: nsv-verify
topology:
  nodes:
    n1:
      kind: linux
      image: alpine:3.19
      cmd: sleep infinity
    n2:
      kind: linux
      image: alpine:3.19
      cmd: sleep infinity
  links:
    - endpoints: [n1:eth1, n2:eth1]
"""

LAB = "nsv-verify"


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(f"{name}{(' — ' + detail) if detail else ''}")
    print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""), flush=True)


async def main() -> None:
    from app.tools.http_registry import HttpToolRegistry

    reg = HttpToolRegistry({"containerlab": "http://localhost:19002"})

    # 先清理可能的残留（幂等）
    try:
        await reg.invoke("containerlab.destroy_topology", name=LAB)
        print("(已清理残留拓扑)")
    except Exception:
        pass

    # 1. 真实部署
    r = await reg.invoke("containerlab.deploy_topology", topo_yaml=TOPO, name=LAB)
    nodes = r.get("nodes", []) if isinstance(r, dict) else []
    check(
        "deploy_topology 真实部署 2 节点",
        isinstance(r, dict) and r.get("status") == "deployed" and len(nodes) >= 2,
        f"status={r.get('status') if isinstance(r, dict) else r}, nodes={[n.get('name') for n in nodes]}",
    )

    # 宿主侧独立佐证：clab 容器真实存在
    import subprocess

    proc = subprocess.run(
        ["docker", "ps", "--filter", f"name=clab-{LAB}", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=30,
    )
    docker_names = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    check(
        "宿主 Docker 中容器真实存在",
        len(docker_names) >= 2,
        f"docker ps: {docker_names}",
    )

    # 2. inspect
    r = await reg.invoke("containerlab.inspect_topology", name=LAB)
    check(
        "inspect_topology 返回真实节点",
        isinstance(r, dict) and len(r.get("nodes", [])) >= 1,
        f"nodes={r.get('nodes') if isinstance(r, dict) else r}",
    )

    # 3. 节点内真实执行（白名单只读命令）
    r = await reg.invoke(
        "containerlab.exec_on_node", name=LAB, node="n1", command="ping -c 1 127.0.0.1"
    )
    stdout = r.get("stdout", "") if isinstance(r, dict) else ""
    check(
        "exec_on_node 节点内真实执行 ping",
        "1 packets received" in stdout or "1 received" in stdout or "0% packet loss" in stdout,
        f"stdout={stdout.strip()[:80]!r}",
    )

    # 4. 销毁清理
    r = await reg.invoke("containerlab.destroy_topology", name=LAB)
    check(
        "destroy_topology 真实销毁",
        isinstance(r, dict) and r.get("status") == "destroyed",
        str(r)[:100],
    )
    proc = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name=clab-{LAB}", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=30,
    )
    leftover = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    check("销毁后无残留容器", len(leftover) == 0, f"leftover={leftover}")

    print(f"\n===== containerlab 真实链路：{len(PASS)} 通过 / {len(FAIL)} 失败 =====")
    for f in FAIL:
        print(f"  ❌ {f}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
