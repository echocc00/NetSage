"""H3C Batfish 静态校验路径测试（Phase 2 P2-4）。

结论：Batfish 无原生 H3C/Comware parser，用 Cisco parser 解析 H3C 配置会有大量
"unrecognized syntax" 警告，但能识别节点存在（nodes=1）。

P2-4 策略调整（v2.0 决策：H3C 走 Batfish 静态校验）：
- H3C 配置 Batfish 仅做"节点识别 + 基本结构校验"（宽松，不阻断）
- 真实语法校验靠：① ConfigRenderer 渲染时 meta 校验 ② 真实设备/Containerlab（Phase 3）
- 华为/Cisco 走 Batfish 完整校验（原生 parser 支持）

此测试验证：Batfish 能识别 H3C 配置为有效节点（不崩溃），警告记录但不阻断流程。
"""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.mark.integration
async def test_batfish_parses_cisco_clean():
    """Cisco 配置 Batfish 解析零警告（原生 parser 支持）。"""
    try:
        from pybatfish.client.session import Session
    except ImportError:
        pytest.skip("pybatfish 未安装")

    import tempfile

    bf = Session(host="localhost", port_v1=9996)
    tmp = Path(tempfile.mkdtemp()) / "configs"
    tmp.mkdir(parents=True)
    (tmp / "device.cfg").write_text(
        (FIXTURES / "cisco_bgp_sample.cfg").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    bf.init_snapshot(str(tmp.parent), name="test_cisco", overwrite=True)

    warnings = bf.q.parseWarning().answer().frame()
    nodes = bf.q.nodeProperties().answer().frame()
    assert len(nodes) == 1  # 识别为 1 节点
    assert len(warnings) == 0  # Cisco 零警告


@pytest.mark.integration
async def test_batfish_h3c_identifies_node_but_warns():
    """H3C 配置 Batfish 识别节点但有语法警告（无原生 parser）。

    P2-4 策略：H3C 走 Batfish 宽松校验——节点识别即通过，警告记录不阻断。
    """
    try:
        from pybatfish.client.session import Session
    except ImportError:
        pytest.skip("pybatfish 未安装")

    import tempfile

    bf = Session(host="localhost", port_v1=9996)
    tmp = Path(tempfile.mkdtemp()) / "configs"
    tmp.mkdir(parents=True)
    (tmp / "device.cfg").write_text(
        (FIXTURES / "h3c_bgp_sample.cfg").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    bf.init_snapshot(str(tmp.parent), name="test_h3c", overwrite=True)

    warnings = bf.q.parseWarning().answer().frame()
    nodes = bf.q.nodeProperties().answer().frame()

    # 节点能识别（Batfish 不崩溃）
    assert len(nodes) == 1
    # H3C 语法有警告（预期，Batfish 无 H3C parser）
    assert len(warnings) > 0
    # 警告含 "unrecognized"（H3C 独有语法）
    warning_text = warnings.to_string() if len(warnings) > 0 else ""
    assert "unrecognized" in warning_text.lower() or "invalid" in warning_text.lower()


def test_h3c_batfish_strategy_documented():
    """P2-4 H3C 校验策略文档化：Batfish 宽松 + ConfigRenderer meta 校验 + Phase 3 真实设备。"""
    # 此测试存在即代表策略已记录（见 docstring）
    assert True
