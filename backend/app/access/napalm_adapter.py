"""NAPALM Adapter（主路径，v2.0 开发计划十章 10.2）。

多厂商统一 API，优先用 napalm driver。
commit/rollback/diff 最成熟，作为主路径。

审查修复：
- 所有 sync 调用经 asyncio.to_thread 包装，避免阻塞事件循环（python C2）
- load+compare+commit 复合方法解决 candidate 会话生命周期（python H2）
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.access.base import (
    AdapterError,
    DeviceAdapter,
    DeviceFacts,
    DeviceTarget,
)
from app.core.logging import get_logger

logger = get_logger("access_napalm")


class NapalmAdapter(DeviceAdapter):
    """NAPALM 多厂商适配器。"""

    def _connect_sync(self, target: DeviceTarget) -> Any:
        from napalm import get_network_driver

        try:
            driver = get_network_driver(target.napalm_driver)
            device = driver(
                hostname=target.host,
                username=target.username,
                password=target.password,
                optional_args={"port": target.port},
            )
            device.open()
            return device
        except Exception as e:
            raise AdapterError("connect_failed", f"NAPALM 连接 {target.host} 失败: {e}") from e

    async def _connect(self, target: DeviceTarget) -> Any:
        """sync 连接在线程池执行，不阻塞 event loop。"""
        return await asyncio.to_thread(self._connect_sync, target)

    async def get_facts(self, target: DeviceTarget) -> DeviceFacts:
        device = await self._connect(target)
        try:
            facts = await asyncio.to_thread(device.get_facts)
            logger.info("napalm_facts", host=target.host, vendor=facts.get("vendor"))
            return DeviceFacts(
                vendor=facts.get("vendor", target.vendor),
                model=facts.get("model", ""),
                os_version=facts.get("os_version", ""),
                hostname=facts.get("hostname", target.name),
                serial=facts.get("serial_number"),
                interface_list=facts.get("interface_list", []),
            )
        finally:
            await asyncio.to_thread(device.close)

    async def get_config(self, target: DeviceTarget, source: str = "running") -> str:
        device = await self._connect(target)
        try:
            config = await asyncio.to_thread(device.get_config, retrieve=source)
            return config.get(source, "")
        finally:
            await asyncio.to_thread(device.close)

    async def load_merge_candidate(self, target: DeviceTarget, config: str) -> None:
        """加载候选（连接关闭后 candidate 会话丢失——审查 H2 修复）。

        ⚠️ 独立调用此方法后 candidate 不保留。
        必须用 apply_candidate 复合方法在单会话内完成 load+compare+commit。
        """
        device = await self._connect(target)
        try:
            await asyncio.to_thread(device.load_merge_candidate, config=config)
            logger.info("napalm_candidate_loaded", host=target.host)
        finally:
            await asyncio.to_thread(device.close)

    async def apply_candidate(self, target: DeviceTarget, config: str) -> str:
        """复合操作：单个 SSH 会话内 load + compare + commit（审查 H2 修复）。

        避免 candidate 跨连接丢失。返回 diff。
        """
        device = await self._connect(target)
        try:
            await asyncio.to_thread(device.load_merge_candidate, config=config)
            diff = await asyncio.to_thread(device.compare_config)
            await asyncio.to_thread(device.commit_config)
            logger.info("napalm_applied", host=target.host, diff_len=len(diff))
            return diff
        except Exception as e:
            await asyncio.to_thread(device.discard_config)
            raise AdapterError("apply_failed", f"候选应用失败: {e}") from e
        finally:
            await asyncio.to_thread(device.close)

    async def compare_config(self, target: DeviceTarget) -> str:
        device = await self._connect(target)
        try:
            return await asyncio.to_thread(device.compare_config)
        finally:
            await asyncio.to_thread(device.close)

    async def commit(self, target: DeviceTarget) -> None:
        """写操作：必须经三道闸 + 审批（v2.0 十章）。"""
        device = await self._connect(target)
        try:
            await asyncio.to_thread(device.commit_config)
            logger.info("napalm_committed", host=target.host)
        except Exception as e:
            raise AdapterError("commit_failed", f"commit 失败: {e}") from e
        finally:
            await asyncio.to_thread(device.close)

    async def discard(self, target: DeviceTarget) -> None:
        device = await self._connect(target)
        try:
            await asyncio.to_thread(device.discard_config)
        finally:
            await asyncio.to_thread(device.close)

    async def rollback(self, target: DeviceTarget, snapshot_config: str) -> None:
        """回滚：加载快照配置作为 merge candidate + commit（单会话）。"""
        device = await self._connect(target)
        try:
            await asyncio.to_thread(device.load_merge_candidate, config=snapshot_config)
            await asyncio.to_thread(device.commit_config)
            logger.info("napalm_rollback", host=target.host)
        finally:
            await asyncio.to_thread(device.close)
