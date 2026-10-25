"""测试配置：把项目根加入 sys.path，让 eval/ 包可被 backend 测试导入。

v0.5.0（审查修复）：原 test_inventory() 返回硬编码数字且无断言——
数字漂移（292/501 → 实际 288/506）不被发现，"测试数透明化"空转。
现改为收集钩子精确计数 + test_inventory_in_sync 强校验：数字漂移即红，
须同步 INVENTORY 与 CHANGELOG 口径后才能合并。
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 三层口径声明（唯一事实来源；变更时同步 CHANGELOG）
INVENTORY = {
    "unit_functions": 314,
    "unit_cases": 532,
    "e2e_scenarios": 18,
}

# 收集期精确计数（bucket: unit / unit_cases / e2e / files；integration 不在三口径内）
_collected: dict[str, set[str]] = {}


def pytest_collection_modifyitems(session, config, items) -> None:  # noqa: ANN001
    for item in items:
        rel = str(Path(str(item.fspath)).relative_to(Path(__file__).parent)).replace("\\", "/")
        _collected.setdefault("files", set()).add(rel)
        if rel.startswith("unit/"):
            bucket = "unit"
        elif rel.startswith("e2e/"):
            bucket = "e2e"
        else:
            continue  # integration / conftest 等另列口径
        fn_name = str(getattr(item, "originalname", None) or item.name)
        _collected.setdefault(bucket, set()).add((rel, fn_name))
        _collected.setdefault(bucket + "_cases", set()).add((rel, str(item.nodeid)))


def inventory() -> dict[str, int]:
    """三层测试口径（供 CHANGELOG / 引用方参考；自校验见 tests/unit/test_inventory_sync.py）。

    - unit_functions: tests/unit 收集的函数数（去 parametrize 展开）
    - unit_cases: 单元测试总算例（parametrize 展开后 = collected items）
    - e2e_scenarios: tests/e2e 真实 HTTP 场景函数数
    """
    return dict(INVENTORY)
