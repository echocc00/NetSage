"""合规审计 API（Phase 3 SecurityAuditor + ComplianceAgent）。

POST /compliance/scan          基线扫描（需 troubleshoot 权限）
POST /compliance/scan-acl      ACL 分析（需 troubleshoot 权限）
GET  /compliance/reports       报告列表
POST /compliance/report        生成合规报告（需 audit 权限）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, require_permission
from app.schemas.common import Envelope

router = APIRouter(prefix="/compliance", tags=["compliance"])


class ScanRequest(BaseModel):
    config: str = Field(..., description="running-config 文本")
    vendor: str = Field("huawei_vrp", examples=["huawei_vrp", "cisco_iosxe"])


class ScanResponse(BaseModel):
    vendor: str
    total: int
    passed: int
    failed: int
    score: int
    findings: list[dict]


@router.post("/scan", response_model=Envelope[ScanResponse])
async def scan_baseline(
    req: ScanRequest,
    user: CurrentUser = Depends(require_permission("troubleshoot")),
) -> Envelope[ScanResponse]:
    """基线扫描（SecurityAuditor，≥30 条规则）。"""
    from app.services.baseline_scanner import BaselineScanner

    scanner = BaselineScanner()
    result = await scanner.scan(req.config, req.vendor)
    return Envelope.ok(ScanResponse(
        vendor=result.vendor, total=result.total, passed=result.passed,
        failed=result.failed, score=result.score,
        findings=[
            {"rule_id": f.rule_id, "severity": f.severity, "description": f.description,
             "passed": f.passed, "remediation": f.remediation, "standard_ref": f.standard_ref}
            for f in result.findings
        ],
    ))


class ACLScanRequest(BaseModel):
    snapshot: str = Field(..., description="Batfish snapshot 名")
    vendor: str = Field("cisco_iosxe")


@router.post("/scan-acl", response_model=Envelope[dict])
async def scan_acl(
    req: ACLScanRequest,
    user: CurrentUser = Depends(require_permission("troubleshoot")),
) -> Envelope[dict]:
    """ACL 分析（Batfish reachability + shadowed + unused）。"""
    from app.services.acl_analyzer import ACLAnalyzer

    analyzer = ACLAnalyzer()
    report = await analyzer.analyze(req.snapshot, req.vendor)
    return Envelope.ok({
        "snapshot": req.snapshot,
        "vendor": req.vendor,
        "reachability": report.reachability,
        "shadowed": report.shadowed,
        "unused": report.unused,
        "vendor_notes": report.vendor_notes,
    })


class ReportRequest(BaseModel):
    config: str
    vendor: str = "huawei_vrp"
    snapshot: str = ""


@router.post("/report", response_model=Envelope[dict])
async def generate_report(
    req: ReportRequest,
    user: CurrentUser = Depends(require_permission("audit")),
) -> Envelope[dict]:
    """生成合规报告（ComplianceAgent，Markdown + CSV，需 audit 权限）。"""
    from app.services.acl_analyzer import ACLAnalyzer
    from app.services.baseline_scanner import BaselineScanner
    from app.services.compliance_reporter import ComplianceReporter

    scanner = BaselineScanner()
    baseline = await scanner.scan(req.config, req.vendor)
    acl = ACLAnalyzer().empty_report(req.vendor)
    if req.snapshot:
        acl = await ACLAnalyzer().analyze(req.snapshot, req.vendor)
    reporter = ComplianceReporter()
    report = await reporter.render(baseline, acl)
    return Envelope.ok({
        "score": report.score,
        "markdown": report.markdown,
        "csv": report.csv,
        "baseline_total": baseline.total,
        "baseline_failed": baseline.failed,
    })
