"""测试配置：把项目根加入 sys.path，让 eval/ 包可被 backend 测试导入。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_inventory():
    """三层测试口径，供 CHANGELOG / 引用方参考真实数字。

    - unit_functions: pytest --collect-only 收集的函数数（去 parametrize 展开）
    - unit_cases: 单元测试总算例（parametrize 展开后 = collected items）
    - e2e_scenarios: tests/e2e 真实 HTTP 场景函数数
    口径变更时需同步 CHANGELOG，勿硬编码代入其他文档。
    """
    return {
        "unit_functions": 292,
        "unit_cases": 501,
        "e2e_scenarios": 18,
    }
