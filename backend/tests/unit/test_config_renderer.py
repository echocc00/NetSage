"""ConfigRenderer 测试：LLM 提参 → 模板渲染链路（v2.0 十章）。"""
from __future__ import annotations

import pytest

from app.services.config_renderer import ConfigRenderer, _extract_json
from app.services.template_loader import TemplateError


class MockLLM:
    """模拟 LLM：返回预设 JSON。"""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    async def complete(self, messages, tier="simple", **kw):
        self.calls.append({"messages": messages, "tier": tier})
        return self.responses.pop(0) if self.responses else "{}"


def test_extract_json_fenced():
    """容忍 ```json 围栏。"""
    text = "```json\n{\"a\": 1}\n```"
    assert _extract_json(text) == {"a": 1}


def test_extract_json_plain_and_noise():
    assert _extract_json('前文 {"x": 2} 后文') == {"x": 2}
    assert _extract_json("无 JSON") is None


@pytest.mark.asyncio
async def test_generate_bgp_full_flow():
    """LLM 返回参数 → 真实 huawei BGP 模板渲染。"""
    llm = MockLLM([
        '{"local_asn": 65001, "router_id": "1.1.1.1",'
        ' "peers": [{"address": "10.1.1.2", "remote_asn": 65002, "description": "SH-GZ"}]}'
    ])
    renderer = ConfigRenderer(llm)
    result = await renderer.generate("BGP peering 上海广州专线", "huawei", "bgp")

    assert result["template_id"] == "huawei_vrp_bgp_peering"
    assert "bgp 65001" in result["config_diff"]
    assert "peer 10.1.1.2 as-number 65002" in result["config_diff"]
    assert "router-id 1.1.1.1" in result["config_diff"]
    assert llm.calls[0]["tier"] == "code"  # 难度路由 CODE tier


@pytest.mark.asyncio
async def test_generate_llm_bad_json_raises():
    """LLM 输出非 JSON → 明确报错（不产生残缺配置）。"""
    llm = MockLLM(["不是 JSON 的内容"])
    renderer = ConfigRenderer(llm)
    with pytest.raises(TemplateError):
        await renderer.generate("bgp 配置", "huawei", "bgp")


@pytest.mark.asyncio
async def test_generate_unsupported_vendor():
    """无模板厂商 → 明确报错。"""
    llm = MockLLM(['{"local_asn": 1}'])
    renderer = ConfigRenderer(llm)
    with pytest.raises(TemplateError):
        await renderer.generate("bgp 配置", "unknown_vendor", "bgp")


@pytest.mark.asyncio
async def test_generate_ospf():
    """OSPF 场景走 area_config 模板。"""
    llm = MockLLM([
        '{"router_id": "2.2.2.2",'
        ' "network_areas": [{"area_id": 0, "network": "10.0.0.0", "wildcard": "255.0.0.0"}]}'
    ])
    renderer = ConfigRenderer(llm)
    result = await renderer.generate("OSPF area 0 配置", "huawei", "ospf")
    assert "ospf 1 router-id 2.2.2.2" in result["config_diff"]
    assert "network 10.0.0.0 255.0.0.0" in result["config_diff"]