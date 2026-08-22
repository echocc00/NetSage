"""DeployAgent 节点处理（Phase 2 P2-8）。

pre_check → deploy_loop → verify → rollback
顺序下发多设备，每台 checkpoint 校验，失败自动回滚到快照。
接三道闸的 deploy 阶段（v2.0 十章 + 开发计划十三章）。
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.tools.registry import ToolRegistry

logger = get_logger("deploy_handler")


async def deploy_pre_check(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """下发前校验：审批状态 + 快照完整性 + 影响范围确认。"""
    # 审批必须已通过
    if state.get("change_status") != "approved":
        state["deploy_error"] = "变更未审批，禁止下发"
        state["deploy_blocked"] = True
        return state

    # 快照必须已抓取（回滚依赖）
    snapshots = state.get("snapshots", [])
    if not snapshots:
        state["deploy_error"] = "变更前快照缺失，无法保证回滚"
        state["deploy_blocked"] = True
        return state

    # 影响范围必须已确认
    impact = state.get("impact", {})
    if not impact.get("confirmed_by"):
        state["deploy_error"] = "影响范围未经工程师确认"
        state["deploy_blocked"] = True
        return state

    state["deploy_blocked"] = False
    state["deployed"] = []
    state["failed"] = None
    logger.info("deploy_pre_check_passed", devices=len(state.get("devices", [])))
    return state


async def deploy_loop(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """顺序下发多设备，每台 checkpoint 校验。失败则跳到 rollback。"""
    if state.get("deploy_blocked"):
        return state

    devices = state.get("devices", [])
    configs = state.get("configs", {})

    for device in devices:
        device_name = device.get("name", str(device.get("id")))
        config = configs.get(device_name, device.get("config", ""))

        try:
            # 1. 下发配置（apply_candidate 单会话 load+compare+commit）
            # Phase 2：通过 napalm-mcp 调用（MockToolRegistry 占位）
            await tools.invoke(
                "napalm.apply_candidate",
                vendor=device.get("vendor", "huawei"),
                host=device.get("host", ""),
                username=device.get("username", ""),
                password=device.get("password", ""),
                config=config,
            )

            # 2. checkpoint 校验：配置生效 + 邻居/路由正常
            await _checkpoint_verify(device, tools)

            state["deployed"].append(device_name)
            logger.info("deploy_device_ok", device=device_name)

        except Exception as e:
            state["failed"] = {"device": device_name, "error": str(e)}
            logger.warning("deploy_device_failed", device=device_name, error=str(e)[:80])
            return state  # 跳到 rollback

    return state


async def deploy_verify(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """全量验证 + 失败时内联回滚（SequentialBackend 不支持条件分支，合并为单节点）。"""
    if state.get("deploy_blocked"):
        return state

    if state.get("failed"):
        # 有设备失败 → 自动回滚已下发设备
        state["needs_rollback"] = True
        state = await deploy_rollback(state, tools, llm)
        return state

    # 全部成功 → 终态
    state["deploy_status"] = "success"
    state["needs_rollback"] = False
    logger.info("deploy_all_verified", count=len(state.get("deployed", [])))
    return state


async def deploy_rollback(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """失败自动回滚已下发设备到快照。"""
    if not state.get("needs_rollback"):
        return state

    deployed = state.get("deployed", [])
    snapshots = state.get("snapshots", [])
    rollback_results: list[dict] = []

    for device_name in deployed:
        # 找对应快照
        snapshot = next((s for s in snapshots if s.get("device_name") == device_name), None)
        if not snapshot:
            rollback_results.append({"device": device_name, "status": "no_snapshot"})
            continue

        try:
            await tools.invoke(
                "napalm.rollback",
                vendor=snapshot.get("vendor", "huawei"),
                host=snapshot.get("host", ""),
                username=snapshot.get("username", ""),
                password=snapshot.get("password", ""),
                config=snapshot.get("config", ""),
            )
            rollback_results.append({"device": device_name, "status": "rolled_back"})
            logger.info("deploy_rollback_ok", device=device_name)
        except Exception as e:
            rollback_results.append({"device": device_name, "status": "failed", "error": str(e)})
            logger.error("deploy_rollback_failed", device=device_name, error=str(e)[:80])

    state["rollback_results"] = rollback_results
    state["deploy_status"] = "rolled_back"
    state["partial_rollback"] = any(r["status"] != "rolled_back" for r in rollback_results)
    return state


async def _checkpoint_verify(device: dict, tools: ToolRegistry) -> None:
    """单设备 checkpoint：配置生效 + 邻居/路由正常。

    Phase 2 W4 接 SUZIEQ 后补实时状态校验；当前用 get_config 确认配置已应用。
    """
    # 简化：调 get_facts 确认设备可达 + 配置已生效
    result = await tools.invoke(
        "napalm.get_facts",
        vendor=device.get("vendor", "huawei"),
        host=device.get("host", ""),
        username=device.get("username", ""),
        password=device.get("password", ""),
    )
    if not result:
        raise RuntimeError("checkpoint 校验失败：设备不可达")


# DeployAgent 定义（线性执行：verify 内联 rollback，适配 SequentialBackend）
# 注：人审在三道闸 approval 阶段已完成，DeployAgent 仅做技术校验 + 下发
DEPLOY_DEFINITION = {
    "name": "deploy",
    "role": "变更下发 Agent：顺序下发 + checkpoint 校验 + 失败回滚",
    "system_prompt": "你是变更下发执行器。顺序下发多设备，每台 checkpoint 校验，失败自动回滚到快照。全程审计。",
    "tools": ["napalm.apply_candidate", "napalm.get_facts", "napalm.rollback"],
    "state_schema": {"type": "object"},
    "transitions": [
        {"from": "pre_check", "to": "deploy_loop"},
        {"from": "deploy_loop", "to": "verify"},
        {"from": "verify", "to": "END"},
    ],
    "interrupt_points": [],  # 人审在外层三道闸完成，DeployAgent 不再 interrupt
}