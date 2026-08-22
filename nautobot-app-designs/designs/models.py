"""NetSage 自研 Nautobot App — NetworkDesign 持久化（v0.1）。

Phase 3 差异化：AI 设计方案落 Nautobot 自定义 model。
model 字段与 backend/app/models/design.py 对齐，便于本地↔Nautobot 迁移。
"""
from __future__ import annotations

from django.db import models


class NetworkDesign(models.Model):
    """AI 生成的网络设计方案（v2.0 差异化：自带 SSoT 持久化）。"""

    name = models.CharField(max_length=200)
    site = models.CharField(max_length=100, default="")
    scenario = models.CharField(max_length=50)  # bgp/ospf/vxlan/...
    vendor = models.CharField(max_length=50)
    hld = models.JSONField(default=dict)        # 高层设计（拓扑 + 选型）
    lld = models.JSONField(default=dict)        # 低层设计（配置参数）
    config_diff = models.TextField(default="")
    rollback_config = models.TextField(default="")
    lint_passed = models.BooleanField(default=False)
    created_by = models.CharField(max_length=50, default="ai")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "网络设计方案"
        verbose_name_plural = "网络设计方案"

    def __str__(self) -> str:
        return f"{self.name} [{self.vendor}/{self.scenario}]"
