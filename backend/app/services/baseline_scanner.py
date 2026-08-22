"""配置基线扫描器（Phase 3 SecurityAuditor）。

running-config → 规则匹配 → 合规得分。
规则库 ≥30 条（Cisco 15 + 华为 15，覆盖认证/管理/协议/ACL 四类）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Finding:
    rule_id: str
    severity: str
    description: str
    passed: bool
    remediation: str = ""
    standard_ref: str = ""


@dataclass
class ScanResult:
    vendor: str
    total: int
    passed: int
    failed: int
    score: int
    findings: list[Finding] = field(default_factory=list)


# ===== 基线规则（CIS + 厂商加固，30 条）=====
# 格式: (rule_id, vendor, category, severity, description, check_type, check_expr, remediation, standard_ref)
# check_type: present(必须存在) / absent(必须不存在) / regex(正则匹配)
RULES: list[tuple] = [
    # ===== Cisco IOS-XE 15 条 =====
    # 认证（5）
    ("CISCO-AUTH-01", "cisco_iosxe", "auth", "critical",
     "启用 SSH v2（禁用 SSH v1）", "present", "ip ssh version 2",
     "配置 ip ssh version 2", "CIS Cisco IOS 7.2"),
    ("CISCO-AUTH-02", "cisco_iosxe", "auth", "critical",
     "禁用 Telnet", "absent", "transport input telnet",
     "vty 下 transport input ssh", "CIS Cisco IOS 7.1"),
    ("CISCO-AUTH-03", "cisco_iosxe", "auth", "high",
     "启用 AAA 认证", "present", "aaa new-model",
     "配置 aaa new-model", "CIS Cisco IOS 8.1"),
    ("CISCO-AUTH-04", "cisco_iosxe", "auth", "high",
     "启用本地账户 + enable secret", "present", "enable secret",
     "配置 enable secret <hash>", "CIS Cisco IOS 8.2"),
    ("CISCO-AUTH-05", "cisco_iosxe", "auth", "medium",
     "vty 配置登录认证", "present", "login authentication",
     "line vty 下 login authentication default", "CIS Cisco IOS 8.4"),
    # 管理（4）
    ("CISCO-MGMT-01", "cisco_iosxe", "mgmt", "high",
     "SNMP v3（禁用 v1/v2c 社区串）", "absent", "snmp-server community",
     "改用 snmp-server group/user v3", "CIS Cisco IOS 5.1"),
    ("CISCO-MGMT-02", "cisco_iosxe", "mgmt", "medium",
     "配置 NTP", "present", "ntp server",
     "配置 ntp server <addr>", "CIS Cisco IOS 6.1"),
    ("CISCO-MGMT-03", "cisco_iosxe", "mgmt", "high",
     "日志服务器", "present", "logging host",
     "配置 logging host <addr>", "CIS Cisco IOS 6.2"),
    ("CISCO-MGMT-04", "cisco_iosxe", "mgmt", "medium",
     "启用日志时间戳", "present", "service timestamps log datetime",
     "service timestamps log datetime msec", "CIS Cisco IOS 6.3"),
    # 协议（3）
    ("CISCO-PROTO-01", "cisco_iosxe", "protocol", "high",
     "BGP 邻居认证", "regex", r"neighbor\s+\S+\s+password",
     "BGP 邻居配置 password", "厂商加固 BGP"),
    ("CISCO-PROTO-02", "cisco_iosxe", "protocol", "medium",
     "OSPF MD5 认证", "regex", r"ip ospf message-digest-key|area\s+\S+\s+authentication message-digest",
     "OSPF 区域启用 MD5 认证", "厂商加固 OSPF"),
    ("CISCO-PROTO-03", "cisco_iosxe", "protocol", "medium",
     "CDP 按需关闭", "absent", "no cdp enable",
     "边缘接口 no cdp enable", "CIS Cisco IOS 4.1"),
    # ACL/服务（3）
    ("CISCO-ACL-01", "cisco_iosxe", "acl", "high",
     "禁用未用 HTTP 服务", "absent", "ip http server",
     "no ip http server", "CIS Cisco IOS 3.1"),
    ("CISCO-ACL-02", "cisco_iosxe", "acl", "high",
     "禁用 HTTPS（或改用更安全方式）", "absent", "ip http secure-server",
     "按需 no ip http secure-server", "CIS Cisco IOS 3.2"),
    ("CISCO-ACL-03", "cisco_iosxe", "acl", "medium",
     "禁用 finger/small-servers", "absent", "service finger|service small-servers",
     "no service finger / small-servers", "CIS Cisco IOS 3.3"),

    # ===== 华为 VRP 15 条 =====
    # 认证（5）
    ("HUAWEI-AUTH-01", "huawei_vrp", "auth", "critical",
     "启用 SSH（stelnet）", "present", "stelnet server enable",
     "配置 stelnet server enable", "华为 VRP 加固指南"),
    ("HUAWEI-AUTH-02", "huawei_vrp", "auth", "critical",
     "禁用 Telnet", "absent", "telnet server enable",
     "undo telnet server enable", "华为 VRP 加固指南"),
    ("HUAWEI-AUTH-03", "huawei_vrp", "auth", "high",
     "AAA 认证方案", "present", "authentication-scheme",
     "配置 AAA authentication-scheme", "华为 VRP 加固指南"),
    ("HUAWEI-AUTH-04", "huawei_vrp", "auth", "high",
     "本地用户 + 密码加密", "present", "password-policy",
     "配置 local-user + password-policy", "华为 VRP 加固指南"),
    ("HUAWEI-AUTH-05", "huawei_vrp", "auth", "medium",
     "vty 走 AAA", "present", "authentication-mode aaa",
     "vty 下 authentication-mode aaa", "华为 VRP 加固指南"),
    # 管理（4）
    ("HUAWEI-MGMT-01", "huawei_vrp", "mgmt", "high",
     "SNMP v3（禁用 v1/v2c）", "absent", "snmp-agent community",
     "改用 snmp-agent group/usm v3", "华为 VRP 加固指南"),
    ("HUAWEI-MGMT-02", "huawei_vrp", "mgmt", "medium",
     "配置 NTP", "present", "ntp-service unicast-peer|ntp-service unicast-server",
     "配置 ntp-service unicast-server <addr>", "华为 VRP 加固指南"),
    ("HUAWEI-MGMT-03", "huawei_vrp", "mgmt", "high",
     "日志服务器", "present", "info-center loghost",
     "配置 info-center loghost <addr>", "华为 VRP 加固指南"),
    ("HUAWEI-MGMT-04", "huawei_vrp", "mgmt", "medium",
     "日志时间戳", "present", "info-center timestamp log date",
     "info-center timestamp log date", "华为 VRP 加固指南"),
    # 协议（3）
    ("HUAWEI-PROTO-01", "huawei_vrp", "protocol", "high",
     "BGP 邻居认证", "regex", r"peer\s+\S+\s+password",
     "BGP peer 配置 password", "厂商加固 BGP"),
    ("HUAWEI-PROTO-02", "huawei_vrp", "protocol", "medium",
     "OSPF MD5 认证", "regex", r"authentication-mode md5|ospf authentication-mode",
     "OSPF 区域/接口启用 MD5", "厂商加固 OSPF"),
    ("HUAWEI-PROTO-03", "huawei_vrp", "protocol", "medium",
     "LLDP/CDP 按需关闭", "regex", r"undo lldp enable",
     "边缘接口 undo lldp enable", "华为 VRP 加固指南"),
    # ACL/服务（3）
    ("HUAWEI-ACL-01", "huawei_vrp", "acl", "high",
     "关闭 HTTP 服务", "absent", "http server enable",
     "undo http server enable", "华为 VRP 加固指南"),
    ("HUAWEI-ACL-02", "huawei_vrp", "acl", "medium",
     "关闭 HTTPS（按需）", "absent", "http secure-server enable",
     "undo http secure-server enable", "华为 VRP 加固指南"),
    ("HUAWEI-ACL-03", "huawei_vrp", "acl", "medium",
     "禁止 FTP/TFTP", "absent", "ftp server enable|tftp server enable",
     "undo ftp/tftp server enable", "华为 VRP 加固指南"),
]


class BaselineScanner:
    """配置基线扫描器。"""

    async def scan(self, config: str, vendor: str) -> ScanResult:
        rules = [r for r in RULES if r[1] == vendor]
        findings: list[Finding] = []
        for r in rules:
            rule_id, _v, _cat, sev, desc, ctype, expr, remed, ref = r
            passed = self._match(config, ctype, expr)
            findings.append(Finding(
                rule_id=rule_id, severity=sev, description=desc,
                passed=passed, remediation=remed, standard_ref=ref,
            ))
        passed_count = sum(1 for f in findings if f.passed)
        failed = len(findings) - passed_count
        score = int(passed_count / len(findings) * 100) if findings else 0
        return ScanResult(
            vendor=vendor, total=len(findings), passed=passed_count,
            failed=failed, score=score, findings=findings,
        )

    def _match(self, config: str, check_type: str, expr: str) -> bool:
        if check_type == "present":
            return expr in config
        if check_type == "absent":
            return expr not in config
        if check_type == "regex":
            return bool(re.search(expr, config))
        return False
