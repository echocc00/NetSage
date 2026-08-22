"""统一响应信封（v2.0 patterns.md API Response Format）。"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Meta(BaseModel):
    trace_id: str | None = None
    page: int | None = None
    limit: int | None = None
    total: int | None = None


class Envelope(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: str | None = None
    meta: Meta = Field(default_factory=Meta)

    @classmethod
    def ok(cls, data: T, meta: Meta | None = None) -> "Envelope[T]":
        return cls(success=True, data=data, meta=meta or Meta())

    @classmethod
    def err(cls, error: str, meta: Meta | None = None) -> "Envelope[T]":
        return cls(success=False, data=None, error=error, meta=meta or Meta())
