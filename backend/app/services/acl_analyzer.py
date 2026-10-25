"""Batfish ACL 分析器（v0.5.1 去示例化：接真实 batfish-mcp 断言）。

此前 analyze() 返回硬编码示例数据（评审 P1：编造 shadowed/unused 结论）。
现走全局 ToolRegistry 的 batfish.* 真实断言：
- reachability：searchFilters 真实流量匹配分析（按 ACL 命中动作聚合）
- unused：interfaceProperties 检查 ACL 是否被接口引用
Batfish 不可达/快照不存在时如实返回 error 字段，不编造结论。
华为/H3C 的 parser 限制仍如实写入 vendor_notes。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger("acl_analyzer")


@dataclass
class ACLReport:
    snapshot: str
    vendor: str
    reachability: list[dict] = field(default_factory=list)
    shadowed: list[dict] = field(default_factory=list)
    unused: list[dict] = field(default_factory=list)
    vendor_notes: str = ""
    error: str | None = None  # 真实分析不可用时的原因（不编造数据）


class ACLAnalyzer:
    """ACL 分析器：经 ToolRegistry 调真实 batfish-mcp 断言。"""

    async def analyze(self, snapshot: str, vendor: str) -> ACLReport:
        from app.agents.registry import get_tools

        tools = get_tools()
        report = ACLReport(snapshot=snapshot, vendor=vendor,
                           vendor_notes=self._vendor_caveats(vendor))

        try:
            report.reachability = await self._flow_matches(tools, snapshot)
            report.unused = await self._unreferenced_acls(tools, snapshot)
        except Exception as e:
            logger.error("acl_analyze_failed", snapshot=snapshot, error=str(e))
            report.error = (
                f"Batfish 真实分析不可用：{e}。"
                "需 batfish 服务在线（docker compose dev batfish）且快照已加载"
                "（POST /compliance/scan-acl 前先经 batfish-mcp load_snapshot）。"
            )
        return report

    async def _flow_matches(self, tools: Any, snapshot: str) -> list[dict]:
        """searchFilters 真实流量匹配：返回 ACL 命中动作聚合（前 50 条）。"""
        answer = await tools.invoke("batfish.search_filters", snapshot=snapshot)
        rows = _extract_rows(answer) if isinstance(answer, dict) else []
        flows: list[dict] = []
        for r in rows[:50]:
            if not isinstance(r, dict):
                continue
            flows.append({
                "src": r.get("Source", r.get("Src", "")),
                "dst": r.get("Destination", r.get("Dst", "")),
                "port": r.get("IP_Protocol", r.get("Port", "")),
                "action": r.get("Action", "").lower() or "unknown",
                "matched_rule": r.get("Line_Content", ""),
            })
        return flows

    async def _unreferenced_acls(self, tools: Any, snapshot: str) -> list[dict]:
        """接口引用检查：定义了但未被任何接口引用的 ACL（unused）。"""
        props = await tools.invoke("batfish.interface_properties", snapshot=snapshot)
        rows = _extract_rows(props) if isinstance(props, dict) else []
        referenced: set[str] = set()
        for r in rows:
            if isinstance(r, dict) and r.get("Incoming_Filter"):
                referenced.add(str(r["Incoming_Filter"]))
            if isinstance(r, dict) and r.get("Outgoing_Filter"):
                referenced.add(str(r["Outgoing_Filter"]))
        defined = await tools.invoke("batfish.filter_tables", snapshot=snapshot)
        drows = _extract_rows(defined) if isinstance(defined, dict) else []
        return [
            {"acl": r.get("Name", "?"), "reason": "未在任何接口引用"}
            for r in drows
            if isinstance(r, dict) and r.get("Name") and r["Name"] not in referenced
        ][:20]

    def empty_report(self, vendor: str) -> ACLReport:
        return ACLReport(snapshot="", vendor=vendor, vendor_notes=self._vendor_caveats(vendor))

    def _vendor_caveats(self, vendor: str) -> str:
        if vendor.startswith("huawei") or vendor.startswith("h3c"):
            return ("Batfish 无原生华为/H3C parser，已转 Cisco 等价 ACL（loose validation）。"
                    "USG 防火墙 ACL 语法部分不支持，建议人工复核。")
        return "Batfish 原生 parser，full validation。"


def _extract_rows(answer: dict) -> list[dict]:
    """解包 Batfish TableAnswerElement（与 batfish-mcp 同逻辑）。"""
    rows: list[dict] = []
    for el in answer.get("answerElements", []):
        if isinstance(el, dict) and isinstance(el.get("rows"), list):
            rows.extend(el["rows"])
        elif el:
            rows.append(el)
    return rows
