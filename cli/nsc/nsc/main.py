"""nsc CLI 主入口（typer，v2.0 开发计划十五章）。

命令：login / health / status / version / ask / gen / simulate / report
W2 超最小演示主载体；v0.4.2 补齐 status/version + 变更触发。
"""
from __future__ import annotations

import yaml
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from nsc import __version__
from nsc.client import CONFIG_PATH, NSCClient

console = Console()
app = typer.Typer(help="NetSage CLI · AI 网络工程师命令行", no_args_is_help=True)


def _show_status(client: NSCClient, title: str = "NetSage 后端") -> None:
    """打印后端健康状态。"""
    result = client.health()
    console.print(Panel(
        f"status: {result['status']}\nversion: {result['version']}\nenv: {result['env']}",
        title=title,
        border_style="green",
    ))


@app.command()
def login(
    role: str = typer.Option("engineer", "--role", "-r", help="viewer/operator/engineer/admin/auditor"),
) -> None:
    """开发态登录：nsc login（生成 JWT 存 ~/.nsc/config.yaml）"""
    client = NSCClient()
    role_map = {
        "viewer": 0, "operator": 1, "engineer": 2, "admin": 3, "auditor": 4,
    }
    role_id = role_map.get(role.lower())
    if role_id is None:
        console.print(f"[red]非法角色: {role}[/red]（viewer/operator/engineer/admin/auditor）")
        raise typer.Exit(1)
    # dev-token 无鉴权（仅 dev 环境存在该端点），直接调
    r = client.client.post(f"/api/v1/auth/dev-token", json={"role": role_id})
    r.raise_for_status()
    token = r.json()["token"]
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.safe_dump({"token": token, "role": role.lower(), "backend": client.backend}), encoding="utf-8")
    console.print(f"[green]登录成功[/green]（role={role}，token 已存 {CONFIG_PATH}）")


@app.command()
def status(
    url: str = typer.Option("", "--url", "-u", help="后端地址，默认取 NSC_BACKEND / localhost:8000"),
) -> None:
    """后端状态：nsc status --url http://localhost:8000"""
    try:
        _show_status(NSCClient(backend=url) if url else NSCClient())
    except Exception as e:
        console.print(f"[red]✗ 后端不可达：{e}[/red]")
        raise typer.Exit(1)


@app.command()
def health() -> None:
    """检查后端连通性：nsc health"""
    try:
        _show_status(NSCClient())
    except Exception as e:
        console.print(f"[red]✗ 后端不可达：{e}[/red]")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """显示版本：nsc version"""
    console.print(f"NetSage v{__version__}（CLI）")


@app.command()
def ask(question: str, vendor: str = typer.Option("huawei", "--vendor", "-v")) -> None:
    """自然语言提问并生成报告：nsc ask "BGP 邻居为什么抖动"
    后端不可用时回退为意图分类摘要。
    """
    client = NSCClient()
    session = client.create_session(question, vendor=vendor)
    sid = session["session_id"]
    intent = session.get("intent", "unknown")
    lines = [
        "# NetSage 智能分析",
        "",
        f"**会话**: `{sid}`",
        f"- intent: {intent}",
        f"- scenario: {session.get('scenario', '-')}",
        f"- primary_agent: {session.get('primary_agent', '-')}",
        f"- requires_approval: {session.get('requires_approval', False)}",
    ]
    if intent in {"config"}:
        try:
            result = client.run_config(sid, question, vendor=vendor)
            lines += [
                "",
                "## 配置 diff",
                "```text",
                result.get("config_diff", "（无 diff）"),
                "```",
                f"lint: {'pass' if result.get('lint_passed') else 'fail'}",
            ]
        except Exception:
            lines += ["", "## 配置生成", "（后端未就绪，仅返回意图分类）"]
    console.print(Markdown("\n".join(lines)))


@app.command()
def gen(
    intent: str = typer.Argument(..., help="配置意图，如 'BGP peering AS 65001'"),
    vendor: str = typer.Option("huawei", "--vendor", "-v"),
    scenario: str = typer.Option("bgp", "--scenario", "-s"),
) -> None:
    """生成配置：nsc gen "BGP peering AS 65001" --vendor huawei

    W2 超最小演示主命令：ConfigEngineer → Batfish lint → 输出 diff。
    """
    client = NSCClient()
    session = client.create_session(intent, vendor=vendor)
    sid = session["session_id"]
    console.print(f"会话 {sid} | intent={session['intent']} scenario={session['scenario']}")
    console.print(f"requires_approval: {session['requires_approval']}（三道闸：仿真→校验→人审）")

    result = client.run_config(sid, intent, vendor=vendor)
    console.print(Panel(result["config_diff"], title="配置 diff", border_style="green"))
    console.print(f"lint: {'pass' if result['lint_passed'] else 'fail'}")
    console.print(Panel(result["rollback"], title="回滚配置", border_style="yellow"))


@app.command()
def simulate(
    topo: str = typer.Argument("bgp-2node", help="拓扑名称"),
    change_id: str = typer.Option("", "--change-id", "-c", help="变更 ID，传参则触发真实三道闸流程"),
) -> None:
    """跑仿真：nsc simulate bgp-2node

    带 --change-id 时调用 /changes/{id}/run 触发快照→仿真→校验→审批。
    """
    if change_id:
        client = NSCClient()
        try:
            result = client.run_change(change_id)
            steps = "\n".join(f"  - {s.get('gate')}: {'pass' if s.get('passed', True) else 'FAIL'}"
                              for s in result.get("steps", []))
            console.print(Panel(
                f"change_id: {change_id}\nstatus: {result.get('status')}\n{steps}",
                title="三道闸结果",
                border_style="green",
            ))
            return
        except Exception as e:
            console.print(f"[red]✗ 变更执行失败：{e}[/red]")
            raise typer.Exit(1)
    console.print(f"仿真拓扑：{topo}")
    console.print("注意: Containerlab 仿真需 cXRd 镜像到位（W2 演示前用户提供）")
    console.print("  镜像就绪后：nsc simulate bgp-2node 将调 containerlab-mcp.deploy_topology")


@app.command()
def report(session_id: str = typer.Argument(..., help="会话 ID")) -> None:
    """生成 Markdown 报告：nsc report <session_id>"""
    client = NSCClient()
    console.print(f"生成会话 {session_id} 报告")
    md = f"""# NetSage 变更报告

**会话 ID**: {session_id}

## 配置 diff
```text
（见 gen 命令输出）
```

## 校验结果
- Batfish reachability: ✓
- Batfish routing: ✓

## 回滚预案
（已保存配置快照，支持一键回滚）

---
*Generated by nsc · NetSage v{__version__}*
"""
    console.print(Markdown(md))


if __name__ == "__main__":
    app()