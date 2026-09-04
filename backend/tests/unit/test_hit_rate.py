"""v0.1.3 hit_rate 评测逻辑单元测试（不依赖 DB，mock retriever）。"""
from __future__ import annotations

import pytest
from eval.runner import EvalQuestion, load_dataset


def _make_q(qid, refs=None, symptom="BGP 邻居抖动", question="根因"):
    return EvalQuestion(
        id=qid, title="t", category="troubleshoot", vendor="huawei",
        version="VRP-8.180", difficulty=3,
        input={"symptom": symptom, "question": question},
        expected_output={"references": refs or []},
        anti_examples=[], grading_rubric={},
    )


def test_url_key_extracts_protocol():
    from scripts.eval_hit_rate import _url_key
    assert _url_key("https://support.huawei.com/vrp-bgp") == "bgp"
    assert _url_key("https://support.huawei.com/vrp-ospf") == "ospf"
    assert _url_key("https://support.huawei.com/vrp-vxlan") == "vxlan"
    assert _url_key("") == ""


@pytest.mark.asyncio
async def test_eval_one_hit():
    from app.rag.retriever import RetrievedChunk
    from scripts.eval_hit_rate import eval_one

    class MockRetriever:
        async def search(self, query, top_k=5, tier_filter=None):
            return [RetrievedChunk(
                doc_id="huawei-vrp-8.180-bgp", text="BGP 计时器",
                source_url="https://support.huawei.com/vrp-bgp", version="VRP-8.180",
                tier=1, score=0.9, metadata={},
            )]

    q = _make_q("T1", refs=[{"url": "https://support.huawei.com/vrp-bgp"}])
    r = await eval_one(MockRetriever(), q)
    assert r["status"] == "hit"
    assert r["hit_doc"] == "huawei-vrp-8.180-bgp"


@pytest.mark.asyncio
async def test_eval_one_miss():
    from app.rag.retriever import RetrievedChunk
    from scripts.eval_hit_rate import eval_one

    class MockRetriever:
        async def search(self, query, top_k=5, tier_filter=None):
            return [RetrievedChunk(
                doc_id="huawei-vrp-8.180-ospf", text="OSPF",
                source_url="https://support.huawei.com/vrp-ospf", version="VRP-8.180",
                tier=1, score=0.9, metadata={},
            )]

    q = _make_q("T2", refs=[{"url": "https://support.huawei.com/vrp-bgp"}])
    r = await eval_one(MockRetriever(), q)
    assert r["status"] == "miss"


@pytest.mark.asyncio
async def test_eval_one_skip_no_refs():
    from scripts.eval_hit_rate import eval_one

    class MockRetriever:
        async def search(self, query, top_k=5, tier_filter=None):
            return []

    q = _make_q("T3", refs=[])
    r = await eval_one(MockRetriever(), q)
    assert r["status"] == "skipped"


def test_dataset_loads_30_questions():
    """v0.1.2 后评测集 ≥30 题（含 3 新排障场景）。"""
    questions = load_dataset()
    assert len(questions) >= 30
    ids = [q.id for q in questions]
    # v0.1.2 新增 3 题
    for new_id in ["NSG-Q-0031", "NSG-Q-0032", "NSG-Q-0033"]:
        assert new_id in ids, f"{new_id} 不在评测集"


def test_new_questions_have_references():
    """v0.1.2 新题必须有 references（hit_rate 评测锚点）。"""
    questions = load_dataset()
    new_ids = ["NSG-Q-0031", "NSG-Q-0032", "NSG-Q-0033"]
    for q in questions:
        if q.id in new_ids:
            refs = q.expected_output.get("references", [])
            assert len(refs) >= 1, f"{q.id} 无 references"
