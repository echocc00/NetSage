"""nsc CLI 客户端：调后端 API + SSE 流（v2.0 十二章 + 开发计划十五章）。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

DEFAULT_BACKEND = os.getenv("NSC_BACKEND", "http://localhost:8000")
CONFIG_PATH = Path.home() / ".nsc" / "config.yaml"


class NSCClient:
    """后端 API 客户端。"""

    def __init__(self, backend: str | None = None, token: str | None = None) -> None:
        self.backend = backend or DEFAULT_BACKEND
        self.token = token or self._load_token()
        self.client = httpx.Client(
            base_url=self.backend,
            headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
            timeout=60.0,
        )

    @staticmethod
    def _load_token() -> str | None:
        if CONFIG_PATH.exists():
            import yaml

            data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
            return data.get("token")
        return None

    def health(self) -> dict:
        r = self.client.get("/api/v1/health")
        r.raise_for_status()
        return r.json()

    def create_session(self, query: str, vendor: str | None = None) -> dict:
        payload: dict[str, Any] = {"query": query}
        if vendor:
            payload["vendor"] = vendor
        r = self.client.post("/api/v1/agents/sessions", json=payload)
        r.raise_for_status()
        return r.json()["data"]

    def run_config(self, session_id: str, query: str, vendor: str = "huawei") -> dict:
        r = self.client.post(
            f"/api/v1/agents/sessions/{session_id}/config",
            json={"query": query, "vendor": vendor},
        )
        r.raise_for_status()
        return r.json()["data"]

    def run_validate(self, session_id: str) -> dict:
        r = self.client.post(f"/api/v1/agents/sessions/{session_id}/validate")
        r.raise_for_status()
        return r.json()["data"]
