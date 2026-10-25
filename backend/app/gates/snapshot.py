"""配置快照与回滚服务（v2.0 十章 + 开发计划十三章 13.3）。

变更前：napalm.get_config(running) → 对象存储 + hash。
下发失败：napalm.apply_candidate(snapshot) → 校验 hash 一致。
快照保留 7 天。

v0.5.0 修复（审查 P1/M-1）：
- 快照原存 SnapshotService 实例内存 dict——uvicorn 多 worker 下
  /run 与 /deploy 落不同 worker 时快照必读空。现抽 SnapshotObjectStore
  协议，GatePipeline 可注入 ChangeStore 持久化后端（跨 worker 共享）。
- 回滚原为 load_merge_candidate + commit 两次独立工具调用——MCP server
  每次调用新建连接，candidate 会话必丢。现改用 server 侧原子复合工具
  napalm.apply_candidate（单连接 load+commit）。
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Protocol

from app.core.logging import get_logger
from app.tools.registry import ToolRegistry

logger = get_logger("snapshot")

_DEVICE_KEY = re.compile(r"device-(\d+)")


class SnapshotObjectStore(Protocol):
    """快照正文存储（内存 / ChangeStore 持久化）。"""

    async def put(self, key: str, content: str) -> None: ...

    async def get(self, key: str) -> str: ...


class MemoryObjectStore:
    """进程内快照存储（默认；单 worker 或测试环境）。"""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def put(self, key: str, content: str) -> None:
        self._data[key] = content

    async def get(self, key: str) -> str:
        return self._data.get(key, "")


def device_id_from_key(key: str) -> int:
    """从 object_key（snapshots/device-{id}/{hash}）解析设备 id。"""
    m = _DEVICE_KEY.search(key)
    return int(m.group(1)) if m else 0


class StoreBackedObjectStore:
    """ChangeStore 持久化快照存储（多 worker 共享，审查 M-1 修复）。"""

    def __init__(self, store: Any, change_id: int) -> None:
        self._store = store
        self._change_id = change_id

    async def put(self, key: str, content: str) -> None:
        await self._store.save_snapshot(
            change_id=self._change_id,
            device_id=device_id_from_key(key),
            object_key=key,
            config_hash=hashlib.sha256(content.encode()).hexdigest(),
            config=content,
        )

    async def get(self, key: str) -> str:
        return str(await self._store.load_snapshot(key))


class SnapshotService:
    """配置快照：变更前抓全量 running-config，失败时回滚。"""

    def __init__(self, tools: ToolRegistry, object_store: SnapshotObjectStore | None = None) -> None:
        self.tools = tools
        # None 时用进程内存（审查 M3：实例变量而非类变量）
        self.object_store: SnapshotObjectStore = object_store or MemoryObjectStore()

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

        await self.object_store.put(object_key, config)

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
        """从快照回滚：apply_candidate 原子下发快照配置 → 校验 hash。"""
        config = await self.object_store.get(object_key)
        if not config:
            return {"status": "failed", "error": "快照不存在或已过期"}

        # 原子复合工具：单连接内 load_merge_candidate + commit（审查 H2）
        await self.tools.invoke(
            "napalm.apply_candidate",
            vendor=vendor,
            host=host,
            username=username,
            password=password,
            config=config,
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
