"""
TF-IDF / Dense 索引实现
从 rag/src/fraud_rag/index.py 迁移
支持 TF-IDF 字符级索引和 Sentence-Transformer 密集索引
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from src.brain.rag.models import KnowledgeChunk, SearchHit
from src.core.utils.json_utils import safe_json_loads


class SimilarityIndex:
    """
    相似度索引

    支持两种后端：
    1. TF-IDF: 轻量级，无需 GPU，基于字符 n-gram
    2. sentence-transformer: 语义嵌入，需要 GPU 获得最佳性能

    Attributes:
        backend: 索引类型 ("tfidf" | "sentence-transformer")
        chunks: 知识片段列表
        vectorizer: TF-IDF 向量化器 (仅 tfidf 模式)
        matrix: TF-IDF 矩阵 (仅 tfidf 模式)
        model_name: 密集模型名称 (仅 sentence-transformer 模式)
        embeddings: 密集向量矩阵 (仅 sentence-transformer 模式)
    """

    def __init__(
        self,
        *,
        backend: str,
        chunks: list[KnowledgeChunk],
        vectorizer: Any | None = None,
        matrix: Any | None = None,
        model_name: str | None = None,
        embeddings: np.ndarray | None = None,
    ) -> None:
        self.backend = backend
        self.chunks = chunks
        self.vectorizer = vectorizer
        self.matrix = matrix
        self.model_name = model_name
        self.embeddings = embeddings
        self._dense_model = None

    @classmethod
    def build(
        cls,
        chunks: list[KnowledgeChunk],
        *,
        backend: str,
        dense_model: str = "BAAI/bge-base-zh-v1.5",
    ) -> "SimilarityIndex":
        """
        构建新索引

        Args:
            chunks: 知识片段列表
            backend: 索引类型 ("tfidf" | "sentence-transformer")
            dense_model: 密集模型名称 (仅 sentence-transformer 模式)

        Returns:
            SimilarityIndex 实例
        """
        texts = [chunk.text for chunk in chunks]

        if backend == "sentence-transformer":
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "backend=sentence-transformer 需要安装可选依赖："
                    "pip install sentence-transformers"
                ) from exc

            model = SentenceTransformer(dense_model)
            embeddings = model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            instance = cls(
                backend=backend,
                chunks=chunks,
                model_name=dense_model,
                embeddings=embeddings,
            )
            instance._dense_model = model
            return instance

        # 默认使用 TF-IDF
        vectorizer = TfidfVectorizer(
            analyzer="char_wb",  # 字符级 n-gram
            ngram_range=(2, 4),  # 2-4 字符
            lowercase=False,     # 保持大小写
            sublinear_tf=True,   # 子线性 TF 缩放
        )
        matrix = vectorizer.fit_transform(texts)

        return cls(
            backend="tfidf",
            chunks=chunks,
            vectorizer=vectorizer,
            matrix=matrix,
        )

    def save(self, index_dir: Path) -> None:
        """
        保存索引到磁盘

        Args:
            index_dir: 索引保存目录
        """
        index_dir.mkdir(parents=True, exist_ok=True)

        # 保存元信息
        manifest = {
            "backend": self.backend,
            "model_name": self.model_name,
            "chunk_count": len(self.chunks),
        }
        (index_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 保存 chunks 元数据
        chunks_path = index_dir / "chunks.jsonl"
        with open(chunks_path, "w", encoding="utf-8") as f:
            for chunk in self.chunks:
                f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")

        # 保存模型数据
        if self.backend == "sentence-transformer":
            joblib.dump(
                {"embeddings": self.embeddings},
                index_dir / "dense.joblib",
            )
        else:
            joblib.dump(
                {
                    "vectorizer": self.vectorizer,
                    "matrix": self.matrix,
                },
                index_dir / "tfidf.joblib",
            )

    @classmethod
    def load(cls, index_dir: Path) -> "SimilarityIndex":
        """
        从磁盘加载索引

        Args:
            index_dir: 索引目录路径

        Returns:
            SimilarityIndex 实例
        """
        manifest = json.loads(
            (index_dir / "manifest.json").read_text(encoding="utf-8")
        )

        # 加载 chunks
        chunks = []
        with open(index_dir / "chunks.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    chunks.append(KnowledgeChunk.from_dict(data))

        backend = manifest["backend"]
        model_name = manifest.get("model_name")

        if backend == "sentence-transformer":
            payload = joblib.load(index_dir / "dense.joblib")
            return cls(
                backend=backend,
                chunks=chunks,
                model_name=model_name,
                embeddings=payload["embeddings"],
            )

        # TF-IDF 模式
        payload = joblib.load(index_dir / "tfidf.joblib")
        return cls(
            backend="tfidf",
            chunks=chunks,
            vectorizer=payload["vectorizer"],
            matrix=payload["matrix"],
        )

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        """
        执行相似度搜索

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            SearchHit 列表，按相似度降序排列
        """
        if not query.strip():
            return []

        if self.backend == "sentence-transformer":
            query_vector = self._encode_dense_query(query)
            scores = self.embeddings @ query_vector
        else:
            # TF-IDF 模式
            query_vector = self.vectorizer.transform([query])
            scores = (query_vector @ self.matrix.T).toarray()[0]

        # 获取 top-k 索引
        top_indices = np.argsort(scores)[::-1][:top_k]

        hits: list[SearchHit] = []
        for index in top_indices:
            score = float(scores[index])
            if score <= 0:
                continue
            hits.append(SearchHit(score=score, chunk=self.chunks[index]))

        return hits

    def _encode_dense_query(self, query: str) -> np.ndarray:
        """
        编码密集查询向量

        Args:
            query: 查询文本

        Returns:
            查询向量
        """
        if self._dense_model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "加载 dense 索引需要可选依赖：pip install sentence-transformers"
                ) from exc

            self._dense_model = SentenceTransformer(self.model_name)

        return self._dense_model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0]

    def get_stats(self) -> dict[str, Any]:
        """
        获取索引统计信息

        Returns:
            统计信息字典
        """
        return {
            "backend": self.backend,
            "model_name": self.model_name,
            "chunk_count": len(self.chunks),
            "backend_type": "dense" if self.backend == "sentence-transformer" else "sparse",
        }
