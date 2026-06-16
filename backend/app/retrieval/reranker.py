"""
Cross-encoder reranker using sentence-transformers.
Falls back to original order on model failure.
"""

import logging
from typing import List, Optional

from app.config import settings
from app.retrieval.vector_store import SearchResult

logger = logging.getLogger(__name__)

_RERANKER_INSTANCE: Optional["Reranker"] = None


class Reranker:
    """
    Singleton cross-encoder reranker.
    Scores (query, passage) pairs and re-orders results by relevance.
    """

    def __new__(cls) -> "Reranker":
        global _RERANKER_INSTANCE
        if _RERANKER_INSTANCE is None:
            instance = super().__new__(cls)
            instance._initialized = False
            _RERANKER_INSTANCE = instance
        return _RERANKER_INSTANCE

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import CrossEncoder
            logger.info(
                "Loading reranker model '%s' (may download on first run)…",
                settings.RERANKER_MODEL,
            )
            self._model = CrossEncoder(settings.RERANKER_MODEL, max_length=512)
            self._available = True
            logger.info("Reranker model loaded.")
        except Exception as exc:
            logger.error("Could not load reranker model: %s — falling back to original order", exc)
            self._model = None
            self._available = False

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: Optional[int] = None,
    ) -> List[SearchResult]:
        """
        Re-rank a list of SearchResult objects using the cross-encoder.

        Args:
            query: Original user query.
            results: Initial retrieval results.
            top_k: Number to keep after reranking; None keeps all.

        Returns:
            Re-ordered list with `.rerank_score` set on each item.
        """
        if not results:
            return results

        if not self._available or self._model is None:
            logger.warning("Reranker not available; returning original order")
            top_k = top_k or len(results)
            return results[:top_k]

        try:
            pairs = [(query, r.text) for r in results]
            scores = self._model.predict(pairs)

            for result, score in zip(results, scores):
                result.rerank_score = float(score)

            reranked = sorted(results, key=lambda r: r.rerank_score or 0.0, reverse=True)

            if top_k is not None:
                reranked = reranked[:top_k]

            logger.debug(
                "Reranked %d results → top %d (best score=%.4f)",
                len(results), len(reranked),
                reranked[0].rerank_score if reranked else 0.0,
            )
            return reranked

        except Exception as exc:
            logger.error("Reranker prediction failed: %s — returning original order", exc)
            top_k = top_k or len(results)
            return results[:top_k]
