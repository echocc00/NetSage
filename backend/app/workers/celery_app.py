"""Celery worker + beat 定时任务（Phase 2 P2-7 ObserverAgent 定时 poll）。

启动：
  celery -A app.workers.celery_app worker --loglevel=info
  celery -A app.workers.celery_app beat --loglevel=info
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "netsage",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    beat_schedule={
        # ObserverAgent 每 5 分钟 poll 全网（v2.0 开发计划十八章 18.2）
        "observer-poll-every-5min": {
            "task": "app.workers.tasks.observer_poll_task",
            "schedule": crontab(minute="*/5"),
        },
    },
)


@celery_app.task(name="app.workers.tasks.observer_poll_task")
def observer_poll_task() -> dict:
    """定时触发 ObserverAgent（同步入口，内部 asyncio 跑 async handler）。"""
    import asyncio
    from functools import partial

    from app.agents.observer_handlers import (
        observer_alert,
        observer_analyze,
        observer_poll,
    )
    from app.tools.registry import MockToolRegistry

    async def _run():
        tools = MockToolRegistry()  # Phase 2 W4 后接真实 suzieq-mcp
        state = {}
        state = await partial(observer_poll, tools=tools)(state)
        state = await partial(observer_analyze, tools=tools)(state)
        state = await partial(observer_alert, tools=tools)(state)
        return {
            "alert_status": state.get("alert_status"),
            "anomalies": state.get("anomalies", []),
        }

    return asyncio.run(_run())
