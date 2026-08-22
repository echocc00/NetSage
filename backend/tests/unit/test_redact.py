"""数据脱敏模块单元测试（v2.0 二十章验收）。

覆盖：
- Layer1 8 类 PII 正则替换
- MappingTable 可逆性
- Layer3 白/灰/黑盒路由 + 阻断
- 拦截器 LLM/工具 调用前后脱敏+还原
- 对抗样本（fuzz 子集）
"""
from __future__ import annotations

import pytest

from app.redact.interceptor import RedactingInterceptor
from app.redact.layer1_dict import Layer1Redactor
from app.redact.layer3_router import (
    BlackboxBlockError,
    ContentTier,
    GreyboxNotRedactedError,
    Layer3Router,
    Route,
)
from app.redact.mapping import MappingTable


@pytest.fixture
def redactor() -> Layer1Redactor:
    return Layer1Redactor()


@pytest.fixture
def mapping() -> MappingTable:
    return MappingTable()


@pytest.fixture
def router() -> Layer3Router:
    return Layer3Router()


@pytest.fixture
def interceptor() -> RedactingInterceptor:
    return RedactingInterceptor()


# ===== Layer 1: 8 类 PII =====


@pytest.mark.parametrize(
    "label,text,expected_key",
    [
        ("ipv4", "源 10.1.2.3 发送", "IPV4"),
        ("ipv6", "邻居 fe80::1 超时", "IPV6"),
        ("mac", "MAC 00:11:22:33:44:55 异常", "MAC"),
        ("asn", "AS65001 邻居", "ASN"),
        ("email", "联系 admin@corp.local", "EMAIL"),
        ("host", "访问 leaf01.corp", "HOST"),
    ],
)
def test_layer1_redacts_pii(redactor, mapping, label, text, expected_key):
    """Layer1 对 6 类核心 PII 自动 mask（v2.0 19.1 验收 9）。"""
    out = redactor.redact(text, mapping)
    assert expected_key in mapping.redacted_summary(), f"{label} 未脱敏"
    assert out != text, f"{label} 文本未变化"


def test_layer1_password_redacted(redactor, mapping):
    """密码行：关键字保留，值替换为 [REDACTED]。"""
    text = "password S3cr3tP@ss"
    out = redactor.redact(text, mapping)
    assert "S3cr3tP@ss" not in out
    assert "[REDACTED]" in out
    assert "password" in out  # 关键字保留


def test_layer1_snmp_community_redacted(redactor, mapping):
    text = "snmp-server community public RO"
    out = redactor.redact(text, mapping)
    assert "public" not in out.split("community")[1]
    assert "[REDACTED]" in out


# ===== MappingTable 可逆性 =====


def test_mapping_reversible(redactor, mapping):
    """占位符可还原（v2.0 20.6 可逆性）。"""
    original = "设备 10.1.2.3 (MAC aa:bb:cc:dd:ee:ff) 故障"
    redacted = redactor.redact(original, mapping)
    assert "10.1.2.3" not in redacted
    assert "aa:bb:cc:dd:ee:ff" not in redacted
    restored = mapping.restore(redacted)
    assert restored == original


def test_mapping_deterministic(redactor, mapping):
    """同一原值复用同一占位符（确定性）。"""
    text = "10.1.2.3 和 10.1.2.3"
    out = redactor.redact(text, mapping)
    # 两个相同 IP 应该用同一占位符
    placeholders = [p for p in mapping._placeholder_to_orig if "IPV4" in p]
    assert len(placeholders) == 1


def test_mapping_summary_no_leak(mapping):
    """统计不泄露原值。"""
    mapping.add("IPV4", "10.1.2.3")
    summary = mapping.redacted_summary()
    assert summary == {"IPV4": 1}
    assert "10.1.2.3" not in str(summary)


# ===== Layer 3: 路由 =====


def test_router_white_goes_cloud(router):
    assert router.route("general_qa", is_redacted=False) == Route.CLOUD


def test_router_grey_redacted_goes_cloud(router):
    assert router.route("postmortem_summary", is_redacted=True) == Route.CLOUD


def test_router_grey_not_redacted_blocked(router):
    """灰盒未脱敏 → BLOCKED（v2.0 20.4 违反规则立即阻断）。"""
    assert router.route("postmortem_summary", is_redacted=False) == Route.BLOCKED


def test_router_black_local_only(router):
    """黑盒 → LOCAL_ONLY（默认配置 redact_blackbox_local_only=true）。"""
    assert router.route("running_config", is_redacted=False) == Route.LOCAL_ONLY


def test_router_assert_blackbox_raises(router):
    with pytest.raises(BlackboxBlockError):
        router.assert_route("running_config", is_redacted=False)


def test_router_assert_grey_not_redacted_raises(router):
    with pytest.raises(GreyboxNotRedactedError):
        router.assert_route("postmortem_summary", is_redacted=False)


def test_router_assert_white_ok(router):
    """白盒不抛异常。"""
    router.assert_route("general_qa", is_redacted=False)  # 不抛


# ===== 拦截器集成 =====


def test_interceptor_llm_grey_redacts_and_restores(interceptor):
    """灰盒内容：LLM 调用前脱敏，返回后还原。"""
    mapping = MappingTable()
    messages = [{"role": "user", "content": "分析配置：interface GE0/0 ip 10.1.2.3"}]
    redacted_msgs = interceptor.before_llm_call(messages, "postmortem_summary", mapping)
    assert "10.1.2.3" not in redacted_msgs[0]["content"]

    # 模拟 LLM 返回带占位符的响应
    llm_response = f"接口 {list(m for m in mapping._placeholder_to_orig if 'IPV4' in m)[0]} 状态异常"
    restored = interceptor.after_llm_call(llm_response, mapping)
    assert "10.1.2.3" in restored


def test_interceptor_blackbox_blocked(interceptor):
    """黑盒内容调用 LLM 直接拦截。"""
    mapping = MappingTable()
    messages = [{"role": "user", "content": "完整 running-config"}]
    with pytest.raises((BlackboxBlockError, RuntimeError)):
        interceptor.before_llm_call(messages, "running_config", mapping)


def test_interceptor_tool_call_redacts(interceptor):
    """工具调用前脱敏 kwargs。"""
    mapping = MappingTable()
    kwargs = {"host": "10.1.2.3", "config": "password MyPass"}
    redacted = interceptor.before_tool_call("napalm.commit", kwargs, mapping)
    assert "10.1.2.3" not in redacted["host"]
    assert "MyPass" not in redacted["config"]


# ===== 对抗样本（fuzz 子集，v2.0 20.5） =====


@pytest.mark.parametrize(
    "text",
    [
        "10.0.0.1/24",                           # IP 带掩码
        "AS 65001 neighbor 10.1.1.1",            # ASN + IP 混合
        "email: user.name+tag@sub.example.com",  # 复杂邮箱
        "ipv6: 2001:db8::1",                     # IPv6
        "MAC: AA:BB:CC:DD:EE:FF",                # 大写 MAC
    ],
)
def test_fuzz_no_leak(redactor, mapping, text):
    """对抗样本：脱敏后原值不残留（v2.0 20.5 fuzz 集子集）。"""
    out = redactor.redact(text, mapping)
    # 提取原值检查不残留
    if "10.0.0.1" in text:
        assert "10.0.0.1" not in out
    if "65001" in text and "AS" in text:
        assert "65001" not in out
    if "user.name+tag@sub.example.com" in text:
        assert "user.name+tag@sub.example.com" not in out
    if "2001:db8::1" in text:
        assert "2001:db8::1" not in out
    if "AA:BB:CC:DD:EE:FF" in text:
        assert "AA:BB:CC:DD:EE:FF" not in out
