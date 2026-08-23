"""厂商手册 ingest 脚本（v0.1.3 Part A）。

将 doc/vendor-manuals/<vendor>/*.md 分块入库到 kb_chunks。
用法：python scripts/ingest_manuals.py
前置：Postgres + pgvector 已启动。

华为 VRP 8.x 手册首发（v2.0 19.2 验收 5）。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from sqlalchemy import text

from app.core.logging import get_logger
from app.db import get_session
from app.rag.embedder import get_embedder
from app.rag.ingest import IngestService

logger = get_logger("ingest_manuals")

MANUALS_ROOT = Path(__file__).resolve().parent.parent.parent / "doc" / "vendor-manuals"

# 厂商 → tier（L1 官方手册 = tier 1）
VENDOR_TIER = {"huawei": 1, "cisco": 1, "h3c": 1}


async def ingest_all() -> dict:
    """ingest 所有厂商手册，返回统计。"""
    stats = {"vendors": 0, "files": 0, "chunks": 0}
    embedder = get_embedder()

    async for session in get_session():
        ingest = IngestService(embedder, session)
        for vendor_dir in sorted(MANUALS_ROOT.iterdir()):
            if not vendor_dir.is_dir() or vendor_dir.name.startswith("_"):
                continue
            vendor = vendor_dir.name
            tier = VENDOR_TIER.get(vendor, 1)
            md_files = sorted(vendor_dir.glob("*.md"))
            if not md_files:
                continue
            stats["vendors"] += 1
            for md in md_files:
                doc_id = f"{vendor}-{md.stem}"
                content = md.read_text(encoding="utf-8")
                # 从文件名解析版本（如 vrp-8.180-bgp → VRP-8.180）
                version = _parse_version(md.stem, vendor)
                source_url = f"https://support.{vendor}.com/{md.stem}"
                chunks = await ingest.ingest_text(
                    content, doc_id=doc_id,
                    source_url=source_url, version=version, tier=tier,
                )
                stats["files"] += 1
                stats["chunks"] += chunks
                logger.info("ingested", doc=doc_id, chunks=chunks, vendor=vendor)
            await session.commit()
        break

    return stats


def _parse_version(stem: str, vendor: str) -> str:
    """从文件名解析版本号。"""
    parts = stem.split("-")
    for p in parts:
        if any(c.isdigit() for c in p) and "." in p:
            return p.upper() if vendor == "huawei" else p
    return ""


async def verify_ingest() -> dict:
    """验证入库结果：按厂商统计 chunk 数。"""
    async for session in get_session():
        result = await session.execute(text("""
            SELECT
                split_part(doc_id, '-', 1) AS vendor,
                COUNT(*) AS chunks
            FROM kb_chunks
            GROUP BY vendor
            ORDER BY vendor
        """))
        rows = result.fetchall()
        return {"vendors": [{"vendor": r[0], "chunks": r[1]} for r in rows]}
    return {}


async def main() -> None:
    print("=" * 60)
    print("厂商手册 ingest（v0.1.3 Part A）")
    print("=" * 60)

    stats = await ingest_all()
    print(f"\n[ingest] 厂商 {stats['vendors']}，文件 {stats['files']}，"
          f"chunks {stats['chunks']}")

    verify = await verify_ingest()
    print(f"\n[验证] 入库分布:")
    for v in verify["vendors"]:
        print(f"  {v['vendor']}: {v['chunks']} chunks")

    print("\n✓ ingest 完成。可跑 hit_rate 评测：python scripts/eval_hit_rate.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
