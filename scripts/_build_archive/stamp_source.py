"""给 513 道评测题补 source 溯源字段（P7-8）。

来源判定依据（与 _build_archive 下的生成脚本一一对应）：
- manual          NSG-Q-0001~0033，build_0031/0032/0033.py 与人工手写，逐题构造证据链
- template_derived config 类且 references 指向 backend/templates 渲染产物
                   （build_batch3_config_auto.py / build_batch9_config_variants.py）
- auto_generated  其余 build_batch*.py 参数化批量生成

一次性脚本，已执行完毕，保留供审计追溯。
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

DATASET = Path(__file__).resolve().parents[2] / "eval" / "dataset"
MANUAL_MAX_ID = 33


def classify(path: Path, data: dict) -> str:
    num = int(re.search(r"(\d{4})", path.name).group(1))
    if num <= MANUAL_MAX_ID:
        return "manual"
    refs = (data.get("expected_output") or {}).get("references") or []
    if data.get("category") == "config" and any("support." in str(r.get("url", "")) for r in refs):
        return "template_derived"
    return "auto_generated"


def main() -> None:
    counts: dict[str, int] = {}
    for path in sorted(DATASET.glob("NSG-Q-*.yaml")):
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
        if "source" in data:
            continue
        source = classify(path, data)
        lines = text.splitlines(keepends=True)
        lines.insert(1, f"source: {source}\n")
        path.write_text("".join(lines), encoding="utf-8")
        counts[source] = counts.get(source, 0) + 1
    for k in sorted(counts):
        print(f"{k}: {counts[k]}")


if __name__ == "__main__":
    main()
