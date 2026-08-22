"""结构化 JSON 日志 + trace_id 全链路（v2.0 二十三章 23.3）。

审查修复：敏感字段 redactor + 客户端 trace_id 不信任（security M1/M6）。
"""
from __future__ import annotations

import logging
import re
import sys
import uuid
from typing import Any

import structlog
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

# 敏感字段 key 名（security M1：structlog 防密码泄漏到日志）
SENSITIVE_KEYS = {"password", "passwd", "pwd", "secret", "token", "api_key", "authorization", "credential"}

SECRET_VALUE_RE = re.compile(
    r"(password|passwd|pwd|secret|token|api[_-]?key)\s*[=: ]+\S+",
    re.IGNORECASE,
)


def redact_secrets(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    """把敏感键值替换为 [REDACTED]，防止密码/密钥写日志。"""
    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    # 兜底：值内嵌密码模式的字符串也脱敏
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            masked = SECRET_VALUE_RE.sub(r"\1 [REDACTED]", value)
            if masked != value:
                event_dict[key] = masked
    return event_dict


def setup_logging(app: FastAPI) -> None:
    """配置 structlog，输出 JSON 到 stdout。"""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_secrets,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class TraceIdMiddleware(BaseHTTPMiddleware):
    """每请求生成 trace_id，贯穿 API→Agent→MCP→LLM→DB。

    审查修复（security M6）：不信任客户端 X-Trace-Id 作为主 ID，
    客户端 ID 放 client_trace_id 字段，主 trace_id 服务端生成。
    """

    async def dispatch(self, request: Request, call_next):
        client_hint = request.headers.get("X-Trace-Id", "")[:64]
        trace_id = uuid.uuid4().hex[:16]
        structlog.contextvars.clear_contextvars()
        if client_hint:
            # client hint 仅入日志供关联，不作为主 ID（防注入/碰撞）
            structlog.contextvars.bind_contextvars(
                trace_id=trace_id, client_trace_id=client_hint
            )
        else:
            structlog.contextvars.bind_contextvars(trace_id=trace_id)
        request.state.trace_id = trace_id

        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
