"""配置快照与回滚服务（v2.0 十章 + 开发计划十三章 13.3）。

变更前：napalm.get_config(running) → 存 MinIO + hash 存 DB。
下发失败：napalm.rollback(snapshot) → 校验 hash 一致。
快照保留 7 天。
"""
from __future__ import annotations

import hashlib
from typing import Any

from app.core.logging import get_logger
from app.tools.registry import ToolRegistry

logger = get_logger("snapshot")


class SnapshotService:
    """配置快照：变更前抓全量 running-config，失败时回滚。"""

    def __init__(self, tools: ToolRegistry, object_store: Any = None) -> None:
        self.tools = tools
        self.object_store = object_store  # MinIO client（Phase 2 接入，Phase 1 用内存 dict）
        # 审查 M3 修复：实例变量而非类变量，避免跨实例共享
        self._memory_store: dict[str, str] = {}

    async def capture(
        self,
        device_id: int,
        vendor: str,
        host: str,
        username: str,
        password: str,
        port: int = 22,
    ) -> dict:
        """抓取 running-config，计算 hash，存对象存储。返回快照元数据。"""
        result = await self.tools.invoke(
            "napalm.get_config",
            vendor=vendor,
            host=host,
            username=username,
            password=password,
            source="running",
            port=port,
        )
        config = result.get("config", "") if isinstance(result, dict) else str(result)
        config_hash = hashlib.sha256(config.encode()).hexdigest()
        object_key = f"snapshots/device-{device_id}/{config_hash[:12]}"

        # Phase 1：内存存储；Phase 2 换 MinIO
        if self.object_store is not None:
            self.object_store[object_key] = config
        else:
            self._memory_store[object_key] = config

        logger.info(
            "snapshot_captured",
            device_id=device_id,
            hash=config_hash[:12],
            config_len=len(config),
        )
        return {
            "device_id": device_id,
            "object_key": object_key,
            "config_hash": config_hash,
        }

    async def rollback(
        self,
        device_id: int,
        vendor: str,
        host: str,
        username: str,
        password: str,
        object_key: str,
        expected_hash: str,
        port: int = 22,
    ) -> dict:
        """从快照回滚：读取快照配置 → load_merge_candidate + commit → 校验 hash。"""
        config = self._memory_store.get(object_key, "")
        if not config:
            return {"status": "failed", "error": "快照不存在或已过期"}

        # 加载回滚配置作为 merge candidate（简化：实际应走 config replace）
        await self.tools.invoke(
            "napalm.load_merge_candidate",
            vendor=vendor,
            host=host,
            username=username,
            password=password,
            config=config,
            port=port,
        )
        await self.tools.invoke(
            "napalm.commit",
            vendor=vendor,
            host=host,
            username=username,
            password=password,
            port=port,
        )

        # 校验回滚后 hash
        verify = await self.tools.invoke(
            "napalm.get_config",
            vendor=vendor,
            host=host,
            username=username,
            password=password,
            source="running",
            port=port,
        )
        actual_hash = hashlib.sha256(
            (verify.get("config", "") if isinstance(verify, dict) else str(verify)).encode()
        ).hexdigest()

        ok = actual_hash == expected_hash
        logger.info("snapshot_rollback", device_id=device_id, hash_match=ok)
        return {
            "status": "ok" if ok else "hash_mismatch",
            "expected": expected_hash[:12],
            "actual": actual_hash[:12],
        }
