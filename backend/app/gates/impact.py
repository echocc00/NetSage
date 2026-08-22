"""变更影响范围自动推演（用户决策 2026-08-21：自动推演 + 人工确认）。

从 NIM + 拓扑推演受影响设备/链路/业务流 + 风险等级。
工程师可在审批工作台修改确认。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger("impact_analyzer")


@dataclass
class ImpactReport:
    """变更影响范围报告（自动推演草稿，工程师可改）。"""
    affected_devices: list[str] = field(default_factory=list)
    affected_links: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    risk_level: str = "medium"          # low / medium / high / critical
    risk_reasons: list[str] = field(default_factory=list)
    suggested_window: str = "any"       # any / maintenance / emergency
    confirmed_by: str | None = None     # 工程师确认人

    def to_dict(self) -> dict:
        return {
            "affected_devices": self.affected_devices,
            "affected_links": self.affected_links,
            "affected_services": self.affected_services,
            "risk_level": self.risk_level,
            "risk_reasons": self.risk_reasons,
            "suggested_window": self.suggested_window,
            "confirmed_by": self.confirmed_by,
        }


# 风险等级判定规则
RISK_RULES: list[tuple[str, str, str]] = [
    # (条件, 风险等级, 原因)
    ("protocol==bgp", "high", "BGP 变更影响路由全局，可能导致大面积丢包"),
    ("protocol==ospf", "high", "OSPF 变更触发 LSA 泛洪，影响区域收敛"),
    ("protocol==vxlan", "medium", "VXLAN 变更影响租户隔离"),
    ("protocol==roce", "critical", "RDMA 变更影响 AI 训练任务，PFC 失误可致丢包"),
    ("device_role==spine", "critical", "Spine 变更影响整 fabric"),
    ("device_role==leaf", "medium", "Leaf 变更影响单 Pod"),
    ("device_role==pe", "high", "PE 变更影响 VPN 租户"),
    ("action==rollback", "high", "回滚操作本身有风险"),
]


class ImpactAnalyzer:
    """从 NIM 推演变更影响范围。"""

    def analyze(self, nim: dict, devices: list[dict], action: str = "config") -> ImpactReport:
        """分析变更影响。"""
        report = ImpactReport()

        # 受影响设备
        report.affected_devices = [d["name"] for d in devices]
        for d in devices:
            if d.get("role") == "spine":
                report.affected_links.append(f"{d['name']}-all-leaves")

        # 受影响业务流（从 NIM business_requirements 推演）
        for req in nim.get("business_requirements", []):
            service = req.get("service", "unknown")
            report.affected_services.append(service)

        # 风险等级判定
        protocol = nim.get("topology", {}).get("underlay", {}).get("protocol", "")
        device_roles = {d.get("role", "") for d in devices}

        for condition, level, reason in RISK_RULES:
            if self._match(condition, protocol, device_roles, action):
                if self._level_weight(level) > self._level_weight(report.risk_level):
                    report.risk_level = level
                report.risk_reasons.append(reason)

        # 变更窗口建议
        if report.risk_level in ("high", "critical"):
            report.suggested_window = "maintenance"
        if action == "emergency":
            report.suggested_window = "emergency"

        logger.info(
            "impact_analyzed",
            devices=len(report.affected_devices),
            risk=report.risk_level,
            reasons=len(report.risk_reasons),
        )
        return report

    @staticmethod
    def _match(condition: str, protocol: str, roles: set[str], action: str) -> bool:
        """简单条件匹配。"""
        if condition.startswith("protocol=="):
            return protocol == condition.split("==")[1]
        if condition.startswith("device_role=="):
            return condition.split("==")[1] in roles
        if condition.startswith("action=="):
            return action == condition.split("==")[1]
        return False

    @staticmethod
    def _level_weight(level: str) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(level, 1)
