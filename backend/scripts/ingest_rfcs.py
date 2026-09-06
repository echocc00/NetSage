"""公开 RFC 语料拉取 + 入库（v0.5.0 波2：RAG 去 🟡）。

评测集里 50 题纯引公开 RFC、~55 题含 RFC（datatracker.ietf.org / rfc-editor.org，NDA-free）。
补 RFC 文本是把这些 miss 转 hit 的语料前提（命中判定：检索 top-K 内出现带对应 RFC
url_key 的 chunk；是否转 hit 还取决于 query 能否召回——design/HLD 类 query 依赖向量召回，
纯 CPU bge-m3 极慢，建议在 GPU/联网环境跑并容忍数十分钟~数小时）。

RFC 文本为公开标准（无版权障碍），本地存 doc/rfcs/（gitignored，体积大）。
用法（幂等：已入库跳过，可断点续跑）：
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python scripts/ingest_rfcs.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text as sqla_text

from app.db import get_session
from app.rag.embedder import get_embedder
from app.rag.ingest import IngestService

RFC_ROOT = Path(__file__).resolve().parent.parent.parent / "doc" / "rfcs"
RFC_IDS = ["2328", "2545", "3101", "3418", "3706", "3947", "4271", "4456",
           "4861", "5340", "5798", "5925", "7296", "7796", "7938", "9234"]
RFC_EDITOR = "https://www.rfc-editor.org/rfc/rfc{id}.txt"


async def fetch_missing() -> list[Path]:
    """下载缺失 RFC 到 doc/rfcs/，返回本地文件列表。"""
    RFC_ROOT.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as c:
        for rid in RFC_IDS:
            p = RFC_ROOT / f"rfc{rid}.txt"
            if p.exists() and p.stat().st_size > 1000:
                files.append(p)
                continue
            r = await c.get(RFC_EDITOR.format(id=rid))
            r.raise_for_status()
            p.write_text(r.text, encoding="utf-8")
            files.append(p)
            print(f"  ↓ rfc{rid}: {len(r.text)//1024} KB")
    return files


async def ingest(files: list[Path]) -> int:
    embedder = get_embedder()
    total = 0
    async for session in get_session():
        ingest_svc = IngestService(embedder, session)
        for p in files:
            rid = p.stem.replace("rfc", "")  # rfc4271.txt → 4271
            doc_id = f"rfc{rid}"
            source_url = f"https://www.rfc-editor.org/rfc/rfc{rid}.txt"
            # 幂等：已入库跳过（重跑续传，不必重复 embed 慢文件）
            exists = await session.execute(
                sqla_text("SELECT 1 FROM kb_chunks WHERE doc_id=:d LIMIT 1"), {"d": doc_id}
            )
            if exists.first():
                print(f"  = {doc_id} 已入库，跳过")
                continue
            content = p.read_text(encoding="utf-8")
            # RFC 页眉/页脚 ASCII 装饰线精简，减少噪声 chunk
            lines = [ln for ln in content.splitlines()
                     if not (ln.startswith("[Page ") or set(ln.strip()) <= {"-", "=", "_", " "})]
            text = "\n".join(lines)
            chunks = await ingest_svc.ingest_text(
                text, doc_id=doc_id, source_url=source_url,
                version=f"RFC {rid}", tier=1,
            )
            total += chunks
            print(f"  ✓ {doc_id}: {chunks} chunks", flush=True)
    return total


async def main() -> None:
    print(f"RFC 语料（{len(RFC_IDS)} 个公开标准，NDA-free）")
    files = await fetch_missing()
    total = await ingest(files)
    print(f"\n[OK] 入库 {len(files)} 个 RFC，共 {total} chunks")
    print("重跑 hit_rate：python scripts/eval_hit_rate.py")


if __name__ == "__main__":
    asyncio.run(main())
