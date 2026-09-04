"""脱敏接入 LLM 网关测试（P7-1 安全 P0）。

验证 v2.0 二十章：黑盒阻断 / 灰盒强制脱敏 / 响应还原。
"""
from __future__ import annotations

import pytest

from app.redact.layer3_router import BlackboxBlockError
from app.services.llm_gateway import LLMGateway


class _FakeResponse:
    """模拟 litellm 响应。"""

    class _Choice:
        class _Msg:
            def __init__(self, content: str) -> None:
                self.content = content

        def __init__(self, content: str) -> None:
            self.message = self._Msg(content)

    class _Usage:
        total_tokens = 42

    def __init__(self, content: str) -> None:
        self.choices = [self._Choice(content)]
        self.usage = self._Usage()


@pytest.fixture
def gw(monkeypatch):
    """带假 key 的网关，acompletion 被 mock。"""
    g = LLMGateway()
    monkeypatch.setattr(g.settings, "deepseek_api_key", "fake-key")
    return g


@pytest.mark.asyncio
async def test_blackbox_blocked(gw):
    """running_config（黑盒）必须被阻断，不发云。"""
    with pytest.raises(BlackboxBlockError):
        await gw.complete(
            [{"role": "user", "content": "interface GE0/0/1\n ip address 10.1.1.1"}],
            content_type="running_config",
        )


@pytest.mark.asyncio
async def test_credentials_blocked(gw):
    """credentials（黑盒）必须被阻断。"""
    with pytest.raises(BlackboxBlockError):
        await gw.complete(
            [{"role": "user", "content": "password Huawei@123"}],
            content_type="credentials",
        )


@pytest.mark.asyncio
async def test_greybox_redacted_before_send(gw, monkeypatch):
    """灰盒内容送 LLM 前必须脱敏：真实 IP 不出现在 payload。"""
    sent: dict = {}

    async def fake_acompletion(model, messages, **kw):
        sent["messages"] = messages
        return _FakeResponse("配置已生成")

    monkeypatch.setattr("app.services.llm_gateway.acompletion", fake_acompletion)

    await gw.complete(
        [{"role": "user", "content": "为 10.1.1.1 配置 BGP AS 65001"}],
        content_type="topology_abstraction",
        cache=False,
    )
    payload = sent["messages"][0]["content"]
    assert "10.1.1.1" not in payload, "真实 IP 泄漏到 LLM payload"
    assert "[IPV4_1]" in payload
    assert "AS 65001" not in payload  # ASN 也脱敏


@pytest.mark.asyncio
async def test_response_restored(gw, monkeypatch):
    """LLM 返回的占位符还原为真实值（展示给用户）。"""
    async def fake_acompletion(model, messages, **kw):
        # LLM 回显脱敏后的占位符
        return _FakeResponse("已为 [IPV4_1] 配置完成")

    monkeypatch.setattr("app.services.llm_gateway.acompletion", fake_acompletion)

    result = await gw.complete(
        [{"role": "user", "content": "配置 10.1.1.1"}],
        content_type="topology_abstraction",
        cache=False,
    )
    assert "10.1.1.1" in result, "占位符未还原"
    assert "[IPV4_1]" not in result


@pytest.mark.asyncio
async def test_whitebox_no_redaction(gw, monkeypatch):
    """白盒（general_qa）无需脱敏，原文直发。"""
    sent: dict = {}

    async def fake_acompletion(model, messages, **kw):
        sent["messages"] = messages
        return _FakeResponse("BGP 是边界网关协议")

    monkeypatch.setattr("app.services.llm_gateway.acompletion", fake_acompletion)

    await gw.complete(
        [{"role": "user", "content": "什么是 BGP？"}],
        content_type="general_qa",
        cache=False,
    )
    assert sent["messages"][0]["content"] == "什么是 BGP？"


@pytest.mark.asyncio
async def test_redact_disabled_opt_out(gw, monkeypatch):
    """redact=False 显式关闭脱敏（仅内部可信调用）。"""
    sent: dict = {}

    async def fake_acompletion(model, messages, **kw):
        sent["messages"] = messages
        return _FakeResponse("ok")

    monkeypatch.setattr("app.services.llm_gateway.acompletion", fake_acompletion)

    await gw.complete(
        [{"role": "user", "content": "10.1.1.1"}],
        content_type="running_config",  # 黑盒也不拦（因 redact=False）
        redact=False,
        cache=False,
    )
    assert sent["messages"][0]["content"] == "10.1.1.1"


def test_default_content_type_is_greybox():
    """未指定 content_type 时默认 general_qa（白盒），但未知类型走灰盒保守策略。"""
    from app.redact.layer3_router import ContentTier, Layer3Router

    r = Layer3Router()
    assert r.classify("general_qa") == ContentTier.WHITE
    assert r.classify("unknown_type_xyz") == ContentTier.GREY  # 保守默认


def test_config_renderer_uses_greybox():
    """ConfigRenderer 调 LLM 时传 topology_abstraction（灰盒强制脱敏）。"""
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "app" / "services" / "config_renderer.py"
    content = src.read_text(encoding="utf-8")
    assert 'content_type="topology_abstraction"' in content
