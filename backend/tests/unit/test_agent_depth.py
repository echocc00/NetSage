"""Agent 深度测试（P7-5）：WirelessAgent 射频/漫游/安全 + RdmAgent Fabric 设计。"""
from __future__ import annotations

import pytest

# ===== WirelessAgent：容量 vs 覆盖双约束 =====


@pytest.mark.asyncio
async def test_wireless_capacity_bound():
    """高用户密度 → 容量约束主导（不是面积）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    # 300m² 但 300 用户 → office profile 每 AP 40 用户 → 容量需 8 AP > 覆盖需 3 AP
    r = await runner.run("wireless_agent", {
        "area_sqm": 300, "users": 300, "floors": 1, "scenario": "office",
    }, session_id="w-cap")
    sizing = r["plan"]["sizing"]
    assert sizing["binding_constraint"] == "capacity"
    assert sizing["by_capacity"] > sizing["by_coverage"]
    assert r["plan"]["total_aps"] == sizing["by_capacity"]


@pytest.mark.asyncio
async def test_wireless_coverage_bound():
    """大面积少用户 → 覆盖约束主导。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("wireless_agent", {
        "area_sqm": 2000, "users": 40, "floors": 1, "scenario": "office",
    }, session_id="w-cov")
    assert r["plan"]["sizing"]["binding_constraint"] == "coverage"


@pytest.mark.asyncio
async def test_wireless_scenario_profiles_differ():
    """高密场景比办公场景需要更多 AP（每 AP 覆盖面积更小）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    office = await runner.run("wireless_agent",
                              {"area_sqm": 600, "users": 50, "scenario": "office"},
                              session_id="w-o")
    highd = await runner.run("wireless_agent",
                             {"area_sqm": 600, "users": 50, "scenario": "highdensity"},
                             session_id="w-h")
    assert highd["plan"]["total_aps"] > office["plan"]["total_aps"]
    # 高密降功率提复用
    assert highd["rf_plan"]["tx_power_percent"] < office["rf_plan"]["tx_power_percent"]


# ===== WirelessAgent：射频规划 =====


@pytest.mark.asyncio
async def test_wireless_channel_reuse_within_floor():
    """同层相邻 AP 信道错开（2.4G 1/6/11 轮转）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("wireless_agent",
                         {"area_sqm": 1200, "users": 100, "floors": 1},
                         session_id="w-ch")
    aps = r["plan"]["ap_plan"]
    floor1 = [a for a in aps if a["floor"] == 1]
    # 相邻 AP 不同频
    for a, b in zip(floor1, floor1[1:], strict=False):
        assert a["channel_2g"] != b["channel_2g"]


@pytest.mark.asyncio
async def test_wireless_floor_offset():
    """层间信道偏移：同序号 AP 跨层不同频（减垂直干扰）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("wireless_agent",
                         {"area_sqm": 360, "users": 60, "floors": 3, "scenario": "office"},
                         session_id="w-fl")
    aps = r["plan"]["ap_plan"]
    per_floor = r["plan"]["ap_per_floor"]
    first_of_floor = [a for a in aps if (a["ap_id"] - 1) % per_floor == 0]
    channels = [a["channel_2g"] for a in first_of_floor[:3]]
    assert len(set(channels)) > 1, "层间未做信道偏移"


@pytest.mark.asyncio
async def test_wireless_channel_width_selects_band():
    """80MHz 选 80MHz 主信道集，20MHz 选 20MHz 集。"""
    from app.agents.registry import build_runner
    from app.agents.wireless_handlers import CHANNELS_5G_20, CHANNELS_5G_80

    runner = build_runner()
    r80 = await runner.run("wireless_agent",
                           {"area_sqm": 300, "users": 50, "channel_width_mhz": 80},
                           session_id="w-80")
    assert r80["rf_plan"]["channels_5g"] == CHANNELS_5G_80
    r20 = await runner.run("wireless_agent",
                           {"area_sqm": 300, "users": 50, "channel_width_mhz": 20},
                           session_id="w-20")
    assert r20["rf_plan"]["channels_5g"] == CHANNELS_5G_20


# ===== WirelessAgent：漫游 + 安全 =====


@pytest.mark.asyncio
async def test_wireless_roaming_domain_split():
    """AP 超过 32 台时拆多个漫游域（避免大二层泛洪）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("wireless_agent",
                         {"area_sqm": 6000, "users": 2000, "floors": 1, "scenario": "office"},
                         session_id="w-dom")
    assert r["plan"]["total_aps"] > 32
    assert r["roaming"]["domain_count"] >= 2
    assert r["roaming"]["fast_transition"]["ft_over_ds"] is False  # 大规模用 over-the-air


@pytest.mark.asyncio
async def test_wireless_802_11_kvr_enabled():
    """802.11r/k/v 全开（快速漫游三件套）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("wireless_agent", {"area_sqm": 200, "users": 30},
                         session_id="w-ft")
    ft = r["roaming"]["fast_transition"]
    assert ft["802.11r"] and ft["802.11k"] and ft["802.11v"]
    assert r["roaming"]["pmk_caching"] is True


@pytest.mark.asyncio
async def test_wireless_wpa3_requires_pmf():
    """WPA3 强制 PMF（802.11w），WPA2-PSK 可选。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    wpa3 = await runner.run("wireless_agent",
                            {"area_sqm": 200, "users": 30, "security": "wpa3-sae"},
                            session_id="w-wpa3")
    assert wpa3["security_policy"]["pmf"] == "required"
    assert wpa3["security_policy"]["akm"] == "sae"

    wpa2 = await runner.run("wireless_agent",
                            {"area_sqm": 200, "users": 30, "security": "wpa2-psk"},
                            session_id="w-wpa2")
    assert wpa2["security_policy"]["pmf"] == "optional"


@pytest.mark.asyncio
async def test_wireless_dot1x_requires_radius():
    """802.1X 需 RADIUS，PSK 不需要。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("wireless_agent",
                         {"area_sqm": 200, "users": 30, "security": "wpa3-802.1x",
                          "radius_server": "10.9.9.9"},
                         session_id="w-1x")
    radius = r["security_policy"]["radius"]
    assert radius is not None
    assert radius["required"] is True
    assert radius["server"] == "10.9.9.9"
    assert r["security_policy"]["cipher"] == "gcmp256"  # WPA3-Enterprise
    assert r["roaming"]["okc"] is True

    psk = await runner.run("wireless_agent",
                           {"area_sqm": 200, "users": 30, "security": "wpa2-psk"},
                           session_id="w-psk")
    assert psk["security_policy"]["radius"] is None


@pytest.mark.asyncio
async def test_wireless_recommendations_cover_all_dimensions():
    """建议覆盖布放/射频/功率/漫游/安全 5 个维度。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("wireless_agent",
                         {"area_sqm": 500, "users": 100, "security": "wpa3-sae"},
                         session_id="w-rec")
    text = " ".join(r["recommendations"])
    for kw in ("AP", "射频", "功率", "漫游", "安全"):
        assert kw in text, f"建议缺少 {kw} 维度"


# ===== RdmAgent：Fabric 设计 =====


@pytest.mark.asyncio
async def test_rdma_fabric_skipped_without_gpu_count():
    """纯诊断场景（无 gpu_count）不产出 Fabric 设计。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("rdm_agent", {"symptom": "RoCE 丢包", "vendor": "huawei"},
                         session_id="r-nofab")
    assert r["fabric_design"] is None


@pytest.mark.asyncio
async def test_rdma_fabric_roce_design():
    """RoCE Fabric：Spine-Leaf 规模 + buffer 预算 + underlay 选型。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("rdm_agent", {
        "symptom": "新建 AI 训练集群", "vendor": "huawei",
        "gpu_count": 256, "link_speed_gbps": 400, "fabric_type": "roce",
        "ports_per_leaf": 32, "oversubscription": 1.0,
    }, session_id="r-roce")
    d = r["fabric_design"]
    assert d["fabric_type"] == "roce"
    assert d["spine_count"] >= 2  # 冗余
    assert d["leaf_count"] >= 16  # 256 GPU / 16 access
    assert d["capacity"]["max_gpus"] >= 256
    # buffer 随 400G 链路放大
    assert d["buffer_budget"]["headroom_per_port_kb"] > 400
    assert d["roce_config"]["ecn_enabled"] is True
    assert d["roce_config"]["underlay"] == "eBGP unnumbered"  # leaf > 8


@pytest.mark.asyncio
async def test_rdma_fabric_ib_subnet():
    """IB Fabric：分区键 + VL 映射 + SM 配置。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("rdm_agent", {
        "symptom": "IB 子网规划", "gpu_count": 64,
        "fabric_type": "ib", "link_speed_gbps": 200,
    }, session_id="r-ib")
    ib = r["fabric_design"]["ib_subnet"]
    assert len(ib["partition_keys"]) >= 3
    assert any(p["pkey"] == "0x7fff" for p in ib["partition_keys"])  # default pkey
    assert "VL15" in ib["vl_mapping"]["management"]  # VL15 保留给 SM
    assert ib["mtu"] == 4096
    assert ib["sm_config"]["sm_priority"] == 15


@pytest.mark.asyncio
async def test_rdma_oversubscription_affects_leaf_count():
    """收敛比越高，单 leaf 接入端口越多 → leaf 数越少。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    no_sub = await runner.run("rdm_agent", {
        "gpu_count": 128, "fabric_type": "roce", "oversubscription": 1.0,
        "ports_per_leaf": 32,
    }, session_id="r-1to1")
    sub3 = await runner.run("rdm_agent", {
        "gpu_count": 128, "fabric_type": "roce", "oversubscription": 3.0,
        "ports_per_leaf": 32,
    }, session_id="r-3to1")
    assert sub3["fabric_design"]["leaf_count"] < no_sub["fabric_design"]["leaf_count"]
    assert sub3["fabric_design"]["access_ports_per_leaf"] > \
        no_sub["fabric_design"]["access_ports_per_leaf"]


# ===== RdmAgent：自适应调优 =====


@pytest.mark.asyncio
async def test_rdma_tuning_scales_with_link_speed():
    """headroom 随链路速率缩放（400G 需比 25G 更大 buffer）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    fast = await runner.run("rdm_agent",
                            {"symptom": "拥塞延迟高", "link_speed_gbps": 400},
                            session_id="r-400")
    slow = await runner.run("rdm_agent",
                            {"symptom": "拥塞延迟高", "link_speed_gbps": 25},
                            session_id="r-25")
    fast_kb = int(fast["tuning"]["pfc_headroom"].rstrip("KB"))
    slow_kb = int(slow["tuning"]["pfc_headroom"].rstrip("KB"))
    assert fast_kb > slow_kb


@pytest.mark.asyncio
async def test_rdma_tuning_category_override():
    """诊断为 buffer 类问题 → headroom 覆盖为 24KB。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    # 只含 buffer 类关键词（egress/缓冲），避免 "drop" 同时命中 PFC 规则
    r = await runner.run("rdm_agent", {
        "symptom": "egress 缓冲耗尽",
        "vendor": "huawei", "link_speed_gbps": 100,
    }, session_id="r-buf")
    assert r["diagnosis"]["category"] == "buffer"
    assert r["tuning"]["pfc_headroom"] == "24KB"
    assert r["tuning"]["buffer_mode"] == "shared"


@pytest.mark.asyncio
async def test_rdma_ambiguous_symptom_prefers_higher_prior():
    """'drop' 同时命中 PFC 与 buffer 规则时，按先验概率 PFC 优先。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("rdm_agent",
                         {"symptom": "egress buffer 耗尽导致 drop", "vendor": "huawei"},
                         session_id="r-ambig")
    assert r["diagnosis"]["category"] == "pfc"
    # buffer 仍在候选列表中（不丢失次要根因）
    categories = [c["category"] for c in r["diagnosis"]["causes"]]
    assert "buffer" in categories


@pytest.mark.asyncio
async def test_rdma_verify_commands_from_diagnosis():
    """输出诊断对应的验证命令（可执行排查步骤）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("rdm_agent",
                         {"symptom": "PFC pause storm 导致 drop", "vendor": "huawei"},
                         session_id="r-verify")
    assert len(r["verify_commands"]) >= 1
    assert any("display" in c for c in r["verify_commands"])


# ===== Agent 步骤数（深度证明） =====


def test_agent_node_counts():
    """wireless 5 节点 / rdma 4 节点（此前各 3 节点）。"""
    from app.agents.rdma_handlers import RDMA_AGENT_DEFINITION
    from app.agents.wireless_handlers import WIRELESS_AGENT_DEFINITION

    assert len(WIRELESS_AGENT_DEFINITION["transitions"]) == 5
    assert len(RDMA_AGENT_DEFINITION["transitions"]) == 4


# ===== SecurityAuditor：攻击面测绘 + 加固优先级 =====


@pytest.mark.asyncio
async def test_security_attack_surface_detects_plaintext():
    """明文协议（Telnet/HTTP/FTP）识别为 critical/high 暴露。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("security_auditor", {
        "config": "telnet server enable\nhttp server enable\nftp server enable",
        "vendor": "huawei_vrp", "snapshot": "mock",
    }, session_id="s-plain")
    surface = r["attack_surface"]
    items = " ".join(e["item"] for e in surface["exposures"])
    assert "Telnet" in items
    assert "HTTP" in items
    assert surface["by_severity"]["critical"] >= 1
    assert surface["mgmt_plane_exposed"] is True


@pytest.mark.asyncio
async def test_security_attack_surface_detects_weak_snmp():
    """SNMP v1/v2c 社区串识别为 critical。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("security_auditor", {
        "config": "snmp-agent community read public",
        "vendor": "huawei_vrp", "snapshot": "mock",
    }, session_id="s-snmp")
    items = " ".join(e["item"] for e in r["attack_surface"]["exposures"])
    assert "SNMP" in items


@pytest.mark.asyncio
async def test_security_attack_surface_reverse_probe():
    """反向检查：缺 SSH / AAA / BGP 认证也算暴露。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("security_auditor", {
        "config": "interface GE0/0/1\n description uplink",  # 什么都没配
        "vendor": "huawei_vrp", "snapshot": "mock",
    }, session_id="s-rev")
    items = " ".join(e["item"] for e in r["attack_surface"]["exposures"])
    assert "SSH" in items         # 未启用 SSH
    assert "AAA" in items         # 无 AAA
    assert "BGP" in items         # BGP 无认证


@pytest.mark.asyncio
async def test_security_hardened_config_low_exposure():
    """加固过的配置暴露分明显低于裸配置。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    hardened = await runner.run("security_auditor", {
        "config": (
            "stelnet server enable\nundo telnet server enable\n"
            "authentication-scheme default\nacl 2000\n"
            "bgp 65001\n peer 10.1.1.2 password cipher xxx\n"
        ),
        "vendor": "huawei_vrp", "snapshot": "mock",
    }, session_id="s-hard")
    bare = await runner.run("security_auditor", {
        "config": "telnet server enable\nsnmp-agent community public",
        "vendor": "huawei_vrp", "snapshot": "mock",
    }, session_id="s-bare")
    assert hardened["attack_surface"]["exposure_score"] < \
        bare["attack_surface"]["exposure_score"]


@pytest.mark.asyncio
async def test_security_remediation_plan_sorted_by_risk():
    """加固优先级按风险分降序，critical 在前。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("security_auditor", {
        "config": "telnet server enable\nlldp enable",
        "vendor": "huawei_vrp", "snapshot": "mock",
    }, session_id="s-plan")
    plan = r["remediation_plan"]
    assert len(plan) >= 3
    scores = [p["risk_score"] for p in plan]
    assert scores == sorted(scores, reverse=True), "未按风险分降序"
    assert plan[0]["severity"] == "critical"


@pytest.mark.asyncio
async def test_security_remediation_has_actions():
    """每个整改项都有可执行动作。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("security_auditor", {
        "config": "telnet server enable", "vendor": "huawei_vrp", "snapshot": "mock",
    }, session_id="s-act")
    for item in r["remediation_plan"]:
        assert item["action"], f"整改项无动作: {item['item']}"


@pytest.mark.asyncio
async def test_security_report_includes_new_sections():
    """报告 Markdown 含攻击面 + 加固优先级章节。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("security_auditor", {
        "config": "telnet server enable", "vendor": "huawei_vrp", "snapshot": "mock",
    }, session_id="s-rpt")
    md = r["report"]["markdown"]
    assert "## 攻击面测绘" in md
    assert "## 加固优先级" in md
    assert "攻击面得分" in md
    assert r["report"]["risk_score"] > 0


@pytest.mark.asyncio
async def test_compliance_agent_full_pipeline():
    """ComplianceAgent 也走完整管线（基线+ACL+攻击面+优先级）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    r = await runner.run("compliance", {
        "config": "telnet server enable\nsnmp-agent community public",
        "vendor": "huawei_vrp", "snapshot": "mock",
    }, session_id="c-full")
    assert "attack_surface" in r
    assert "remediation_plan" in r
    assert "## 攻击面测绘" in r["report"]["markdown"]


def test_security_auditor_node_count():
    """security_auditor 6 节点（此前 4 节点）。"""
    from app.agents.security_handlers import SECURITY_AUDITOR_DEFINITION

    assert len(SECURITY_AUDITOR_DEFINITION["transitions"]) == 6
