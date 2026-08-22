"""合规报告生成器（Phase 3 ComplianceAgent）。

聚合基线 + ACL → Markdown + CSV，落审计哈希链。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.acl_analyzer import ACLReport
from app.services.baseline_scanner import ScanResult


@dataclass
class ComplianceReport:
    score: int
    markdown: str
    csv: str


class ComplianceReporter:
    """合规报告生成器。"""

    async def render(self, baseline: ScanResult, acl: ACLReport) -> ComplianceReport:
        md = self._render_md(baseline, acl)
        csv = self._render_csv(baseline, acl)
        return ComplianceReport(markdown=md, csv=csv, score=baseline.score)

    def _render_md(self, baseline: ScanResult, acl: ACLReport) -> str:
        lines = [
            f"# 合规审计报告 - {baseline.vendor}",
            "",
            f"**合规得分**: {baseline.score}/100",
            f"**基线规则**: {baseline.total} 条（通过 {baseline.passed}，未通过 {baseline.failed}）",
            f"**ACL 分析**: 遮蔽 {len(acl.shadowed)}，未用 {len(acl.unused)}",
            "",
            "## 基线检查详情",
            "",
            "| 规则 ID | 严重度 | 描述 | 状态 | 整改建议 |",
            "|---|---|---|---|---|",
        ]
        for f in baseline.findings:
            status = "✓ 通过" if f.passed else "✗ 未通过"
            lines.append(f"| {f.rule_id} | {f.severity} | {f.description} | {status} | {f.remediation} |")
        lines.extend([
            "",
            "## ACL 分析",
            "",
            "### 被遮蔽规则",
        ])
        for s in acl.shadowed:
            lines.append(f"- {s['acl']}: `{s['rule']}` 被 `{s['shadowed_by']}` 遮蔽")
        lines.append("")
        lines.append("### 未用 ACL")
        for u in acl.unused:
            lines.append(f"- {u['acl']}: {u['reason']}")
        lines.append("")
        lines.append(f"**厂商说明**: {acl.vendor_notes}")
        return "\n".join(lines)

    def _render_csv(self, baseline: ScanResult, acl: ACLReport) -> str:
        lines = ["rule_id,vendor,severity,description,status,remediation,standard_ref"]
        for f in baseline.findings:
            status = "pass" if f.passed else "fail"
            desc = f.description.replace(",", " ")
            rem = f.remediation.replace(",", " ")
            lines.append(f"{f.rule_id},{baseline.vendor},{f.severity},{desc},{status},{rem},{f.standard_ref}")
        return "\n".join(lines)
