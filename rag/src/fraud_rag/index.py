from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .models import KnowledgeChunk, SearchHit
from .utils import read_jsonl, write_jsonl


class SimilarityIndex:
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
        dense_model: str,
    ) -> "SimilarityIndex":
        texts = [chunk.text for chunk in chunks]
        if backend == "sentence-transformer":
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "backend=sentence-transformer 需要安装可选依赖：uv pip install -e '.[semantic]'"
                ) from exc
            model = SentenceTransformer(dense_model)
            embeddings = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
            instance = cls(
                backend=backend,
                chunks=chunks,
                model_name=dense_model,
                embeddings=embeddings,
            )
            instance._dense_model = model
            return instance

        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),
            lowercase=False,
            sublinear_tf=True,
        )
        matrix = vectorizer.fit_transform(texts)
        return cls(
            backend="tfidf",
            chunks=chunks,
            vectorizer=vectorizer,
            matrix=matrix,
        )

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "backend": self.backend,
            "model_name": self.model_name,
            "chunk_count": len(self.chunks),
        }
        (index_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_jsonl(index_dir / "chunks.jsonl", [chunk.to_dict() for chunk in self.chunks])
        if self.backend == "sentence-transformer":
            joblib.dump({"embeddings": self.embeddings}, index_dir / "dense.joblib")
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
        manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
        chunks = [KnowledgeChunk.from_dict(row) for row in read_jsonl(index_dir / "chunks.jsonl")]
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
        payload = joblib.load(index_dir / "tfidf.joblib")
        return cls(
            backend="tfidf",
            chunks=chunks,
            vectorizer=payload["vectorizer"],
            matrix=payload["matrix"],
        )

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        if not query.strip():
            return []
        if self.backend == "sentence-transformer":
            query_vector = self._encode_dense_query(query)
            scores = self.embeddings @ query_vector
        else:
            query_vector = self.vectorizer.transform([query])
            scores = (query_vector @ self.matrix.T).toarray()[0]
        top_indices = np.argsort(scores)[::-1][:top_k]
        hits: list[SearchHit] = []
        for index in top_indices:
            score = float(scores[index])
            if score <= 0:
                continue
            hits.append(SearchHit(score=score, chunk=self.chunks[index]))
        return hits

    def _encode_dense_query(self, query: str) -> np.ndarray:
        if self._dense_model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "加载 dense 索引需要可选依赖：uv pip install -e '.[semantic]'"
                ) from exc
            self._dense_model = SentenceTransformer(self.model_name)
        return self._dense_model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
