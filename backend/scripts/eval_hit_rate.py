"""RAG hit_rate 评测脚本（v0.1.3 Part B 验收）。

对评测集每题：用题目 symptom/question 跑 RAG 检索 → 检查 top-K 是否命中
expected_output.references.url 对应的手册章节。
hit_rate = 命中题数 / 总题数，目标 ≥85%（v2.0 19.2 验收 5）。

用法：python scripts/eval_hit_rate.py
前置：Postgres + pgvector + 已 ingest 手册（scripts/ingest_manuals.py）。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import get_logger
from app.db import get_session
from app.rag.embedder import get_embedder
from app.rag.retriever import HybridRetriever
from eval.runner import load_dataset

logger = get_logger("hit_rate")

TOP_K = 5  # top-5 命中即算


async def eval_one(retriever: HybridRetriever, question) -> dict:
    """评测单题：检索 + 命中判断。"""
    # 构造查询：symptom + question
    query = question.input.get("symptom", "") + " " + question.input.get("question", "")
    if not query.strip():
        query = question.title

    results = await retriever.search(query, top_k=TOP_K)

    # 预期 URL（从 references 取）
    expected_urls = [
        r.get("url", "")
        for r in question.expected_output.get("references", [])
    ]
    if not expected_urls:
        # 无 references 的题：跳过（不计入分母）
        return {"id": question.id, "status": "skipped", "reason": "no references"}

    # 命中判断：任一结果 doc_id/url 包含预期 URL 关键词
    expected_keys = [_url_key(u) for u in expected_urls if u]
    hit = False
    hit_doc = ""
    for r in results:
        doc_key = _url_key(r.source_url or r.doc_id)
        for ek in expected_keys:
            if ek and (ek in doc_key or doc_key in ek):
                hit = True
                hit_doc = r.doc_id
                break
        if hit:
            break

    return {
        "id": question.id,
        "status": "hit" if hit else "miss",
        "query": query[:60],
        "expected_keys": expected_keys,
        "hit_doc": hit_doc,
        "top_results": [{"doc": r.doc_id, "score": round(r.score, 3)} for r in results[:3]],
    }


def _url_key(url: str) -> str:
    """从 URL 提取匹配关键词（协议名/厂商名）。"""
    if not url:
        return ""
    lower = url.lower()
    # 提取协议关键词
    for proto in ["bgp", "ospf", "vxlan", "vpn", "ipsec", "vlan", "interface", "wireless"]:
        if proto in lower:
            return proto
    return lower.split("/")[-1][:20]


async def main() -> None:
    print("=" * 60)
    print("RAG hit_rate 评测（v0.1.3 验收，目标 ≥85%）")
    print("=" * 60)

    questions = load_dataset()
    print(f"\n评测集: {len(questions)} 题")

    embedder = get_embedder()
    results = []
    async for session in get_session():
        retriever = HybridRetriever(embedder, session)
        for q in questions:
            r = await eval_one(retriever, q)
            results.append(r)
            status_icon = {"hit": "✓", "miss": "✗", "skipped": "-"}[r["status"]]
            print(f"  {status_icon} {r['id']}: {r['status']}"
                  + (f" → {r['hit_doc']}" if r["status"] == "hit" else ""))
        break

    evaluated = [r for r in results if r["status"] != "skipped"]
    hits = sum(1 for r in evaluated if r["status"] == "hit")
    total = len(evaluated)
    hit_rate = hits / total if total else 0

    print(f"\n{'=' * 60}")
    print(f"hit_rate: {hits}/{total} = {hit_rate:.1%}")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    if skipped:
        print(f"跳过（无 references）: {skipped}")

    if hit_rate >= 0.85:
        print(f"✓ 达标（≥85%）")
    else:
        print(f"✗ 未达标（<85%），需调参：同义词扩展 / HyDE / 重排序")
    print("=" * 60)

    # 保存详细报告
    report = {"hit_rate": hit_rate, "hits": hits, "total": total,
              "skipped": skipped, "results": results}
    report_path = Path(__file__).resolve().parent.parent.parent / "eval" / "reports" / "hit_rate.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"详细报告: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
