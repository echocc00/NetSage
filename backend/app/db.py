"""数据库引擎与 session（SQLAlchemy 2.0 async）。"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()

# dev 用 NullPool：测试/TestClient 各自独立 event loop，池化连接跨 loop 复用
# 会触发 "Event loop is closed"；dev 下每连接 ~1ms 成本换正确性。prod 保持池化。
_engine_kwargs: dict = {"echo": _settings.is_dev}
if _settings.is_dev:
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True})

engine = create_async_engine(_settings.database_url, **_engine_kwargs)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """每请求一个 session（v2.0 五章 5.5）。"""
    async with SessionLocal() as session:
        yield session
