"""RdmAgent handlers（Phase 4 RDMA 专项，v2.0 5.1 差异化护城河）。

collect → diagnose → suggest_tuning → design_fabric
- collect：IB 状态（ibstat/perfquery/sminfo）+ RoCE 计数器 + 配置
- diagnose：RoCEDiagnoseEngine 规则+概率定位瓶颈
- suggest_tuning：PFC/ECN/DCQCN 参数（按诊断类别 + 链路速率自适应）+ 模板渲染
- design_fabric：无损网络 Fabric 设计（拓扑/buffer 预算/IB 分区/VL 映射）
"""
from __future__ import annotations

from typing import Any

RDMA_AGENT_DEFINITION: dict[str, Any] = {
    "name": "rdm_agent",
    "role": "RDMA/IB 专项 Agent：无损网络设计 + RoCE 调优 + 配置诊断 + IB 子网规划",
    "system_prompt": (
        "你是 RDMA/InfiniBand 专家。诊断 RoCE 丢包/延迟，输出 PFC/ECN/DCQCN 调优方案；"
        "设计无损网络 Fabric（buffer 预算 / IB 分区 / VL 映射）。"
    ),
    "tools": ["opensm.ibstat", "opensm.ibdiscover", "opensm.perfquery",
              "opensm.sminfo", "napalm.get_config", "rag.search", "template.render"],
    "state_schema": {"type": "object"},
    "transitions": [
        {"from": "collect", "to": "diagnose"},
        {"from": "diagnose", "to": "suggest_tuning"},
        {"from": "suggest_tuning", "to": "design_fabric"},
        {"from": "design_fabric", "to": "END"},
    ],
    "interrupt_points": [],
}

_VENDOR_KEYS = {
    "huawei": "huawei_vrp",
    "cisco": "cisco_iosxe",
    "arista": "arista_eos",
    "h3c": "h3c_comware",
}

# 诊断类别 → 调优参数覆盖（自适应，非固定常量）
_TUNING_BY_CATEGORY: dict[str, dict] = {
    "pfc": {"pfc_headroom": "16KB", "watchdog_interval": 100},
    "ecn": {"ecn_threshold": "100KB", "ecn_ce_threshold": "150KB"},
    "buffer": {"pfc_headroom": "24KB", "buffer_mode": "shared"},
    "mtu": {"mtu": 9216},
    "physical": {"fec_mode": "rs-fec"},
}


def _vendor_key(vendor: str) -> str:
    for prefix, key in _VENDOR_KEYS.items():
        if vendor.startswith(prefix):
            return key
    return "huawei_vrp"


async def rdma_collect(state: dict, tools: Any) -> dict:
    """采集：IB 状态 + 性能计数器 + SM 信息 + 配置。"""
    ibstat = state.get("ibstat", {})
    perf = state.get("perf", {})
    sminfo = state.get("sminfo", {})
    config = state.get("config", "")
    if tools and not ibstat:
        try:
            ibstat = await tools.call("opensm.ibstat")
        except Exception:
            ibstat = {}
    if tools and not perf:
        try:
            perf = await tools.call("opensm.perfquery", lid=state.get("lid", 1))
        except Exception:
            perf = {}
    if tools and not sminfo:
        try:
            sminfo = await tools.call("opensm.sminfo")
        except Exception:
            sminfo = {}
    return {**state, "ibstat": ibstat, "perf": perf, "sminfo": sminfo, "config": config}


async def rdma_diagnose(state: dict, tools: Any) -> dict:
    """诊断：瓶颈定位（PFC/ECN/buffer/MTU/物理层）。"""
    from app.agents.rdma_engine import RoCEDiagnoseEngine

    engine = RoCEDiagnoseEngine()
    result = engine.analyze(state)
    return {**state, "diagnosis": result}


async def rdma_suggest_tuning(state: dict, tools: Any) -> dict:
    """调优建议：按诊断类别 + 链路速率自适应 PFC/ECN/DCQCN 参数 + 模板渲染。"""
    from app.services.template_loader import TemplateError, render

    diag = state.get("diagnosis", {})
    category = diag.get("category", "")
    vendor = state.get("vendor", "huawei")
    interface = state.get("interface", "10GE1/0/1")
    link_speed = int(state.get("link_speed_gbps", 100))

    # headroom 随链路速率缩放（100G 需更大 buffer 吸收 PFC 反应延迟）
    headroom_kb = max(10, link_speed // 10)
    tuning: dict[str, Any] = {
        "pfc_priority": state.get("pfc_priority", 3),
        "pfc_headroom": f"{headroom_kb}KB",
        "ecn_threshold": f"{link_speed + 50}KB",
        "ecn_ce_threshold": f"{link_speed * 2}KB",
        "dcqcn_params": {"alpha": 0.5, "k_min": 1, "k_max": 100, "timer": 10},
        "mtu": 9100,
        "watchdog_interval": 100,
        "buffer_mode": "shared",
    }
    tuning.update(_TUNING_BY_CATEGORY.get(category, {}))

    vendor_key = _vendor_key(vendor)
    template_id = f"{vendor_key}_roce_ecn" if category == "ecn" else f"{vendor_key}_roce_pfc"

    config = ""
    try:
        config = render(template_id, {
            "interface": interface,
            "pfc_priority": tuning["pfc_priority"],
            "pfc_headroom": tuning["pfc_headroom"],
            "ecn_threshold": tuning["ecn_threshold"],
            "ecn_ce_threshold": tuning["ecn_ce_threshold"],
            "watchdog_interval": tuning["watchdog_interval"],
        })
    except TemplateError:
        config = ""

    return {
        **state,
        "tuning": tuning,
        "config": config,
        "template_used": template_id,
        "verify_commands": [c["verify"] for c in diag.get("causes", []) if c.get("verify")],
    }


async def rdma_design_fabric(state: dict, tools: Any) -> dict:
    """无损网络 Fabric 设计：拓扑 + buffer 预算 + IB 分区 + VL 映射。

    输入：gpu_count / link_speed_gbps / oversubscription / fabric_type(roce|ib)
    未给 gpu_count 时跳过（纯诊断场景）。
    """
    gpu_count = int(state.get("gpu_count", 0))
    if gpu_count <= 0:
        return {**state, "fabric_design": None}

    link_speed = int(state.get("link_speed_gbps", 100))
    oversub = float(state.get("oversubscription", 1.0))  # 1.0 = 无收敛
    fabric_type = state.get("fabric_type", "roce")
    ports_per_leaf = int(state.get("ports_per_leaf", 32))

    # 端口分配：access:uplink = oversub:1 → access = ports/(1+1/oversub)
    access_per_leaf = max(1, int(ports_per_leaf / (1 + 1 / oversub)))
    leaf_count = -(-gpu_count // access_per_leaf)  # ceil
    uplinks_per_leaf = ports_per_leaf - access_per_leaf
    spine_count = max(2, min(uplinks_per_leaf, 8))  # 冗余 ≥2

    # buffer 预算：headroom ≈ 链路速率 × RTT(5μs) × 无损优先级数
    lossless_priorities = int(state.get("lossless_priorities", 2))
    headroom_per_port_kb = int(link_speed * 0.625 * lossless_priorities)
    total_buffer_mb = round(headroom_per_port_kb * ports_per_leaf / 1024, 1)

    design: dict[str, Any] = {
        "fabric_type": fabric_type,
        "topology": f"Spine-Leaf {spine_count}+{leaf_count}",
        "spine_count": spine_count,
        "leaf_count": leaf_count,
        "access_ports_per_leaf": access_per_leaf,
        "uplinks_per_leaf": uplinks_per_leaf,
        "oversubscription": f"1:{oversub:.1f}",
        "link_speed_gbps": link_speed,
        "buffer_budget": {
            "headroom_per_port_kb": headroom_per_port_kb,
            "lossless_priorities": lossless_priorities,
            "total_per_leaf_mb": total_buffer_mb,
        },
        "capacity": {"gpu_count": gpu_count, "max_gpus": leaf_count * access_per_leaf},
    }

    if fabric_type == "ib":
        # IB 子网管理（v2.0 5.1 RdmAgent：LID/GID/VL/分区表）
        design["ib_subnet"] = {
            "partition_keys": [
                {"pkey": "0x7fff", "name": "default", "membership": "full"},
                {"pkey": "0x0001", "name": "compute", "membership": "full"},
                {"pkey": "0x0002", "name": "storage", "membership": "limited"},
            ],
            "vl_mapping": {"compute": "VL0-VL3", "storage": "VL4-VL6", "management": "VL15"},
            "sm_config": {
                "routing_engine": "updn" if leaf_count > 4 else "minhop",
                "lmc": 0,
                "sm_priority": 15,
                "subnet_prefix": "0xfe80000000000000",
            },
            "mtu": 4096,  # IB MTU 最大 4096 byte
        }
    else:
        design["roce_config"] = {
            "pfc_priority": 3,
            "ecn_enabled": True,
            "dcqcn_enabled": True,
            "mtu": 9100,
            "underlay": "eBGP unnumbered" if leaf_count > 8 else "OSPF",
        }

    return {**state, "fabric_design": design}
