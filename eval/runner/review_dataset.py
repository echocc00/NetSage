"""评测集质量复审器（v0.5.0 波1）。

在 schema 校验之上叠深度检查，输出按 source 分层的质量报告：
- root_causes 数量低于该类别理想下限（troubleshoot ≥3）
- perf 类缺 tuning_params / bottleneck
- 严重度/概率字段缺失或越界（verify/fix 为空、probability 超 [0,1]）
- title 含模板味（"示例" / 编号尾缀 / 半角括号中英文混排检测信号）
- 跨题相似度过高（同 title 或同一 symptom 前缀 ≥80% 相似命中多题）
- 文本残留（占位符 / 乱码 / 厂商文档链接失效特征）——链接可达性不在离线检查范围
- vendor×category 覆盖矩阵空位

产物：stdout 摘要 + eval/reports/question-review-v1.md 完整报告。

用法：python eval/runner/review_dataset.py [--out eval/reports/question-review-v1.md]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
DATASET = ROOT / "eval" / "dataset"
REPORT_DIR = ROOT / "eval" / "reports"

# 直载 schema.py，避开 eval/runner/__init__.py 连带导入 backend app
import importlib.util

_spec = importlib.util.spec_from_file_location("schema_mod", ROOT / "eval" / "runner" / "schema.py")
_schema = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_schema)
VALID_CATEGORIES = _schema.VALID_CATEGORIES
VALID_VENDORS = _schema.VALID_VENDORS
validate_question = _schema.validate_question

CATEGORY_MIN_CAUSES = {"troubleshoot": 3, "perf": 2}
PLACEHOLDER_RE = re.compile(r"lorem|xxx|yyy|TBD|TODO|FIXME|待补|占位|（示例）|示例题|placeholder|REPLACE")
GARBLE_RE = re.compile(r"[�]|Ã[\x80-\xbf]|â\x20ac" )
VENDORS = ["huawei", "cisco", "h3c", "juniper", "arista", "mellanox"]


def _load() -> list[tuple[str, dict]]:
    items = []
    for f in sorted(DATASET.glob("NSG-Q-*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        items.append((f.name, d))
    return items


def _title_smell(title: str) -> list[str]:
    """标题模板味信号：明显示例/占位/冒号冒进等。"""
    hits = []
    if re.search(r"[一-鿿][:：].*?[:：]", title):
        hits.append("中文冒号连用")
    if re.search(r"\((cisco|huawei|h3c|arista|juniper|mellanox)\s*[0-9.-]+\)?$", title, re.IGNORECASE):
        hits.append("厂商(型号)括号尾缀")
    if "示例" in title or "样例" in title:
        hits.append("示例/样例字样")
    return hits


def _prob_out_of_range(causes: list) -> int:
    n = 0
    for c in causes:
        p = c.get("probability")
        if p is not None and not (0 <= float(p) <= 1):
            n += 1
    return n


def _checks(d: dict) -> dict[str, list[str]]:
    issues: dict[str, list[str]] = defaultdict(list)
    exp = d.get("expected_output", {})
    cat = d.get("category", "")
    src = d.get("source", "unknown")

    causes = exp.get("root_causes", [])
    min_c = CATEGORY_MIN_CAUSES.get(cat, 0)
    if cat in ("troubleshoot", "perf") and causes:
        if len(causes) < min_c:
            issues[f"root_causes<{min_c}"].append(f"[{src}] 仅 {len(causes)} 个")
        oob = _prob_out_of_range(causes)
        if oob:
            issues["probability越界"].append(f"[{src}] {oob} 条")
        for c in causes:
            for field in ("cause", "verify", "fix"):
                if not str(c.get(field, "")).strip():
                    issues[f"root_cause.{field}为空"].append(f"[{src}]")
                    break
    elif cat == "perf" and not exp.get("bottleneck") and not causes:
        issues["perf缺根因"].append(f"[{src}] 无 bottleneck 也无 root_causes")

    if not d.get("tags"):
        issues["缺tags"].append(f"[{src}]")
    if not exp.get("references") and not d.get("references"):
        issues["缺references"].append(f"[{src}]")
    if not d.get("grading_rubric", {}).get("must_have"):
        issues["grading_rubric缺must_have"].append(f"[{src}]")
    if cat == "troubleshoot" and not d.get("anti_examples"):
        issues["troubleshoot缺anti_examples"].append(f"[{src}]")

    title = d.get("title", "")
    for smell in _title_smell(title):
        issues[f"标题{smell}"].append(f"[{src}] {title[:40]}")

    blob = str(d)
    if PLACEHOLDER_RE.search(blob):
        issues["文本残留占位"].append(f"[{src}]")
    if GARBLE_RE.search(blob):
        issues["乱码"].append(f"[{src}]")
    return issues


def _sim_ratio(a: str, b: str) -> float:
    """前缀字符重合度近似（跨题重复检测用）。"""
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    same = 0
    for x, y in zip(a[:n], b[:n]):
        if x == y:
            same += 1
        else:
            break
    return same / n


def _detect_near_dupes(items: list[tuple[str, dict]]) -> list[tuple[str, str, float, bool]]:
    """疑似重复；返回 (a, b, ratio, is_series)。

    is_series=True：标题仅在末尾" N/M"编号不同（设计规模梯度变体，属有意覆盖非重复）。
    """
    series_suffix = re.compile(r"\s+\d{1,2}/\d{1,2}$")
    titles = [(name, d.get("title", "")) for name, d in items]
    pairs: list[tuple[str, str, float, bool]] = []
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            a, ta = titles[i]
            b, tb = titles[j]
            if ta == tb:
                pairs.append((a, b, 1.0, False))
                continue
            base_a = series_suffix.sub("", ta).strip()
            base_b = series_suffix.sub("", tb).strip()
            is_series = (base_a == base_b) and (ta != tb)
            r = max(_sim_ratio(ta, tb), _sim_ratio(tb, ta))
            if is_series or r >= 0.85:
                pairs.append((a, b, round(r, 2), is_series))
    return pairs


def _coverage_matrix(items: list[tuple[str, dict]]) -> dict[str, dict[str, int]]:
    m = {v: {c: 0 for c in sorted(VALID_CATEGORIES)} for v in VENDORS}
    for _, d in items:
        v = d.get("vendor")
        c = d.get("category")
        if v in m and c in m[v]:
            m[v][c] += 1
    return m


def main() -> None:
    parser = argparse.ArgumentParser(description="评测集质量复审")
    parser.add_argument("--out", default=str(REPORT_DIR / "question-review-v1.md"))
    args = parser.parse_args()

    items = _load()
    schema_fail = []
    all_issues: dict[str, list[str]] = defaultdict(list)
    for name, d in items:
        errs = validate_question(d)
        if errs:
            schema_fail.append(f"{name}: {errs}")
            continue
        for k, v in _checks(d).items():
            all_issues[k].extend(v)

    by_source = Counter(d.get("source", "unknown") for _, d in items)
    dupes = _detect_near_dupes(items)
    cov = _coverage_matrix(items)

    # 报告
    lines = ["# NetAI-Bench 评测集复审报告 · v1", ""]
    lines.append(f"> 扫描 {len(items)} 题 · 分层按 `source` 统计")
    lines.append("")
    lines.append("## 总览")
    lines.append(f"- schema 失败: **{len(schema_fail)}**")
    total_issues = sum(len(v) for v in all_issues.values())
    lines.append(f"- 深度检查命中: **{total_issues}** 条（跨 {len(all_issues)} 类）")
    lines.append(f"- 疑似近似重复: **{sum(1 for p in dupes if not p[3])}** 对真重复 + {sum(1 for p in dupes if p[3])} 对编号系列变体")
    lines.append("")
    lines.append("| source | 数量 |")
    for s, n in by_source.most_common():
        lines.append(f"| {s} | {n} |")
    lines.append("")
    lines.append("## 深度检查明细（按类别）")
    if all_issues:
        for k in sorted(all_issues):
            v = all_issues[k]
            lines.append(f"### {k}（{len(v)}）")
            by_src = Counter(x.split("]")[0].strip("[").strip("'\"") for x in v)
            sample = ", ".join(v[:8])
            lines.append(f"- 来源分布: {dict(by_src)}")
            lines.append(f"- 样本: {sample}")
            lines.append("")
    else:
        lines.append("无深度检查命中。")
    lines.append("## 疑似近似重复（已区分系列变体）")
    true_dupes = [p for p in dupes if not p[3]]
    series = [p for p in dupes if p[3]]
    lines.append(f"- 真重复（同题复现，需合并/改题）: **{len(true_dupes)}** 对")
    lines.append(f"- 编号系列变体（`设计 … N/M` 规模梯度，属有意覆盖，非重复）: {len(series)} 对")
    if true_dupes:
        for a, b, r, _ in true_dupes[:20]:
            lines.append(f"- {a} ↔ {b}（相似 {r}）")
        if len(true_dupes) > 20:
            lines.append(f"- …共 {len(true_dupes)} 对")
    else:
        lines.append("无真重复。")
    lines.append("")
    lines.append("## vendor×category 覆盖矩阵")
    lines.append("| vendor | " + " | ".join(sorted(VALID_CATEGORIES)) + " |")
    lines.append("|---|" + "---|" * len(VALID_CATEGORIES))
    for v in VENDORS:
        lines.append(f"| {v} | " + " | ".join(str(cov[v][c]) for c in sorted(VALID_CATEGORIES)) + " |")
    lines.append("")
    lines.append("## 待人工复核优先级")
    lines.append("按 source 分层：先 `manual`/`template_derived`（量少、专家证据链最可信），")
    lines.append("再按批次复核 `auto_generated`。auto_generated 的 root_causes<3 与疑似重复优先。")

    report = "\n".join(lines)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report, encoding="utf-8")

    true_n = sum(1 for p in dupes if not p[3])
    series_n = sum(1 for p in dupes if p[3])
    print(f"题目: {len(items)} | schema 失败: {len(schema_fail)} | 深度命中: {total_issues} 条/{len(all_issues)} 类 | 真重复: {true_n} | 编号系列变体: {series_n}")
    print(f"报告已写: {args.out}")
    for k, v in sorted(all_issues.items()):
        print(f"  ✗ {k}: {len(v)}")
    if schema_fail:
        print("  SCHEMA 失败(需先修):", *schema_fail[:5], sep="\n    ")
    # CI 门禁语义：schema 失败或出现真重复 → 非零退出
    if schema_fail or true_n:
        print(f"  → 门禁未过：schema 失败 {len(schema_fail)} / 真重复 {true_n}")
        sys.exit(1)


if __name__ == "__main__":
    main()
