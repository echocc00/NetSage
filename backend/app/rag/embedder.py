"""Embedder（v2.0 六章 bge-m3）。

接口 + Mock 实现（Phase 1 W7 跑通管线用确定性 hash 向量）。
真实 BgeM3Embedder 需下载模型，网络就绪时切换。
"""
from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    """向量化接口。"""

    @property
    def dim(self) -> int: ...

    def encode(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Mock embedder：确定性 hash → 向量，跑通管线用（无语义能力，仅测试）。"""

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: list[str]) -> list[list[float]]:
        vecs = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            # 扩展 hash 到 dim 长度
            raw = (h * ((self._dim // len(h)) + 1))[: self._dim]
            vec = [(b - 128) / 128 for b in raw]
            # L2 归一化
            arr = np.array(vec, dtype=np.float32)
            norm = np.linalg.norm(arr) + 1e-8
            vecs.append((arr / norm).tolist())
        return vecs


class BgeM3Embedder:
    """真实 bge-m3（sentence-transformers）。

    需：pip install sentence-transformers
    模型首次下载约 2GB。网络就绪时启用。
    """

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_sentence_embedding_dimension()

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: list[str]) -> list[list[float]]:
        embs = self._model.encode(texts, normalize_embeddings=True)
        return embs.tolist()


def get_embedder() -> Embedder:
    """工厂：优先真实 bge-m3，回退 HashEmbedder。"""
    try:
        return BgeM3Embedder()
    except Exception:
        return HashEmbedder()
