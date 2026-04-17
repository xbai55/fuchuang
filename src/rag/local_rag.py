"""
本地 BM25 RAG 引擎 — 检索 fraud_cases 表中的历史诈骗案例。

检索流程：
  1. 首次调用时从 SQLite 加载全量 fraud_cases，构建 BM25 索引（缓存至进程内存）
  2. query → jieba 分词 → BM25 打分 → top-k 结果
  3. 返回 (similar_cases, legal_basis)

数据库路径优先级：环境变量 LOCAL_DB_PATH → 相对于本文件的默认路径
"""

import os
import math
import logging
import sqlite3
from typing import List, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)

_DEFAULT_DB = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../backend/fraud_detection.db")
)

# BM25 超参数
_K1 = 1.5
_B = 0.75


def _tokenize(text: str) -> List[str]:
    if text is None:
        return []
    if not isinstance(text, str):
        text = str(text)
    try:
        import jieba
        return [t for t in jieba.cut(text) if t.strip()]
    except ImportError:
        # 降级：逐字符分词（无 jieba 时仍可运行）
        return list(text.replace(" ", ""))


class LocalRAG:
    def __init__(self, db_path: Optional[str] = None, top_k: int = 5):
        self.db_path = db_path or os.getenv("LOCAL_DB_PATH", _DEFAULT_DB)
        self.top_k = top_k
        self._docs: List[dict] = []
        self._tokens: List[List[str]] = []
        self._idf: dict = {}
        self._avg_dl: float = 0.0
        self._loaded = False

    # ------------------------------------------------------------------ #
    # 内部：索引构建
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True  # 即使失败也不重试，避免每次请求都尝试

        if not os.path.exists(self.db_path):
            logger.warning("LocalRAG: DB 文件不存在 %s", self.db_path)
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT id, cleaned_text, scam_type, risk_keywords, legal_references, severity "
                "FROM fraud_cases WHERE cleaned_text != '' AND cleaned_text IS NOT NULL"
            )
            rows = cur.fetchall()
            conn.close()
        except sqlite3.OperationalError as e:
            logger.warning("LocalRAG: 读取 fraud_cases 失败: %s", e)
            return

        self._docs = [
            {
                "id": r[0],
                "cleaned_text": r[1],
                "scam_type": r[2] or "未知",
                "risk_keywords": r[3] or "",
                "legal_references": r[4] or "",
                "severity": r[5] or "medium",
            }
            for r in rows
        ]

        self._tokens = [_tokenize(d["cleaned_text"]) for d in self._docs]

        # IDF
        N = len(self._tokens)
        if N == 0:
            return
        df: Counter = Counter()
        for toks in self._tokens:
            for t in set(toks):
                df[t] += 1
        self._idf = {
            t: math.log((N - n + 0.5) / (n + 0.5) + 1)
            for t, n in df.items()
        }
        self._avg_dl = sum(len(t) for t in self._tokens) / N

        logger.info("LocalRAG: 已加载 %d 条案例，DB=%s", N, self.db_path)

    def _bm25(self, query_tokens: List[str], doc_tokens: List[str]) -> float:
        dl = len(doc_tokens)
        tf: Counter = Counter(doc_tokens)
        score = 0.0
        for t in query_tokens:
            idf = self._idf.get(t, 0.0)
            if idf == 0.0:
                continue
            f = tf.get(t, 0)
            score += idf * (f * (_K1 + 1)) / (
                f + _K1 * (1 - _B + _B * dl / max(self._avg_dl, 1))
            )
        return score

    # ------------------------------------------------------------------ #
    # 公开接口
    # ------------------------------------------------------------------ #

    def search(self, query: str) -> Tuple[List[str], str]:
        """
        返回 (similar_cases, legal_basis)
        similar_cases: 格式化字符串列表，供 LLM 消费
        legal_basis:   关联法律条文拼接文本
        """
        self._load()
        if not self._docs:
            return [], ""

        query_tokens = _tokenize(query)
        scores = [self._bm25(query_tokens, toks) for toks in self._tokens]

        top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[: self.top_k]

        similar_cases: List[str] = []
        legal_parts: List[str] = []

        for i in top_idx:
            if scores[i] <= 0:
                continue
            doc = self._docs[i]
            snippet = doc["cleaned_text"][:300].replace("\n", " ")
            similar_cases.append(
                f"[本地案例 · {doc['scam_type']} · 严重度:{doc['severity']}] {snippet}"
            )
            if doc["legal_references"]:
                legal_parts.append(doc["legal_references"])

        legal_basis = "\n\n".join(dict.fromkeys(legal_parts))[:1000]  # 去重、截断
        return similar_cases, legal_basis

    def add_case(self, cleaned_text: str, scam_type: str = "", legal_references: str = "", severity: str = "medium") -> None:
        """
        实时追加新案例到内存索引（不写入 DB，DB 写入由 ETL 负责）。
        用于在检测结果确认后立即扩充知识库，使下一次检索能利用最新数据。
        """
        self._load()
        tokens = _tokenize(cleaned_text)
        if not tokens:
            return

        self._docs.append({
            "id": -1,
            "cleaned_text": cleaned_text,
            "scam_type": scam_type,
            "risk_keywords": "",
            "legal_references": legal_references,
            "severity": severity,
        })
        self._tokens.append(tokens)

        # 增量更新 IDF
        N = len(self._tokens)
        df_new: Counter = Counter(set(tokens))
        for t, inc in df_new.items():
            # 近似更新：重新计算变化项
            old_df = sum(1 for toks in self._tokens[:-1] if t in set(toks))
            new_df = old_df + inc
            self._idf[t] = math.log((N - new_df + 0.5) / (new_df + 0.5) + 1)
        self._avg_dl = sum(len(t) for t in self._tokens) / N


# 进程级单例
_rag_instance: Optional[LocalRAG] = None


def get_local_rag() -> LocalRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = LocalRAG()
    return _rag_instance
