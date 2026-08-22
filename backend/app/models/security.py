"""安全基线规则 ORM（Phase 3，v2.0 五章 baseline_rules + SecurityAuditor）。"""
from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BaselineRule(Base, TimestampMixin):
    """安全基线规则（CIS + 厂商加固指南）。"""
    __tablename__ = "baseline_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), unique=True)   # CIS-HARD-001
    vendor: Mapped[str] = mapped_column(String(50))                 # cisco_iosxe / huawei_vrp
    category: Mapped[str] = mapped_column(String(50))               # auth/mgmt/protocol/acl
    severity: Mapped[str] = mapped_column(String(16))               # critical/high/medium/low
    description: Mapped[str] = mapped_column(Text)
    check_type: Mapped[str] = mapped_column(String(16))             # regex/negate/present/absent
    check_expr: Mapped[str] = mapped_column(Text)                   # 正则或配置存在性表达式
    remediation: Mapped[str] = mapped_column(Text, default="")
    standard_ref: Mapped[str] = mapped_column(String(128), default="")  # CIS / NIST 引用
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ComplianceReport(Base, TimestampMixin):
    """合规扫描报告（Phase 3 ComplianceAgent 输出）。"""
    __tablename__ = "compliance_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(default=0)
    vendor: Mapped[str] = mapped_column(String(50), default="")
    scan_result: Mapped[str] = mapped_column(Text, default="{}")     # BaselineScanResult JSON
    acl_report: Mapped[str] = mapped_column(Text, default="{}")      # ACLReport JSON
    score: Mapped[int] = mapped_column(default=0)                    # 合规分 0-100
    markdown: Mapped[str] = mapped_column(Text, default="")
    csv_text: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(50), default="ai")
