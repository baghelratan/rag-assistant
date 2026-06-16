"""
Hybrid retriever combining dense (vector) + sparse (BM25) search
with Reciprocal Rank Fusion (RRF).
"""

import asyncio
import logging
from typing import List, Dict

from app.config import settings
from app.ingestion.embedder import Embedder
from app.retrieval.vector_store import VectorStore, SearchResult
from app.retrieval.bm25_store import BM25Store

logger = logging.getLogger(__name__)

_RRF_K = 60  # standard RRF constant


def _rrf_score(rank: int, k: int = _RRF_K) -> float:
    """Reciprocal Rank Fusion score for a given rank (0-indexed)."""
    return 1.0 / (k + rank + 1)


class HybridRetriever:
    """
    Combines dense (vector) and sparse (BM25) retrieval using RRF.
    Runs both searches in parallel via asyncio.gather.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_store: BM25Store,
        embedder: Embedder,
        alpha: float = 0.5,  # weight for dense vs sparse (unused in RRF but kept for future use)
    ) -> None:
        self._vector_store = vector_store
        self._bm25_store = bm25_store
        self._embedder = embedder
        self._alpha = alpha

    async def retrieve(
        self,
        query: str,
        top_k: int = None,
    ) -> List[SearchResult]:
        """
        Perform hybrid retrieval.

        Args:
            query: User query string.
            top_k: Number of final results. Defaults to config TOP_K_RETRIEVAL.

        Returns:
            List of SearchResult merged and re-ranked by RRF.
        """
        top_k = top_k or settings.TOP_K_RETRIEVAL
        fetch_k = top_k * 2  # fetch more candidates before merging

        # Run dense and sparse retrieval in parallel
        loop = asyncio.get_event_loop()

        dense_future = loop.run_in_executor(
            None, self._dense_search, query, fetch_k
        )
        sparse_future = loop.run_in_executor(
            None, self._sparse_search, query, fetch_k
        )

        dense_results, sparse_results = await asyncio.gather(dense_future, sparse_future)

        merged = self._merge_rrf(dense_results, sparse_results, top_k)
        logger.debug(
            "Hybrid retrieve: dense=%d, sparse=%d → merged=%d",
            len(dense_results), len(sparse_results), len(merged),
        )
        return merged

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _dense_search(self, query: str, top_k: int) -> List[SearchResult]:
        """Embed query and perform vector similarity search."""
        try:
            query_emb = self._embedder.embed_query(query)
            return self._vector_store.search(query_emb, top_k=top_k)
        except Exception as exc:
            logger.error("Dense search failed: %s", exc)
            return []

    def _sparse_search(self, query: str, top_k: int) -> List[SearchResult]:
        """Perform BM25 keyword search."""
        try:
            return self._bm25_store.search(query, top_k=top_k)
        except Exception as exc:
            logger.error("Sparse search failed: %s", exc)
            return []

    def _merge_rrf(
        self,
        dense: List[SearchResult],
        sparse: List[SearchResult],
        top_k: int,
    ) -> List[SearchResult]:
        """
        Merge dense and sparse results using Reciprocal Rank Fusion.

        RRF score = sum( 1 / (k + rank) ) across all ranked lists.
        """
        rrf_scores: Dict[str, float] = {}
        result_map: Dict[str, SearchResult] = {}

        # Accumulate RRF scores from dense results
        for rank, res in enumerate(dense):
            rrf_scores[res.chunk_id] = rrf_scores.get(res.chunk_id, 0.0) + _rrf_score(rank)
            if res.chunk_id not in result_map:
                result_map[res.chunk_id] = res

        # Accumulate RRF scores from sparse results
        for rank, res in enumerate(sparse):
            rrf_scores[res.chunk_id] = rrf_scores.get(res.chunk_id, 0.0) + _rrf_score(rank)
            if res.chunk_id not in result_map:
                result_map[res.chunk_id] = res

        # Sort by aggregated RRF score descending
        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        merged: List[SearchResult] = []
        for chunk_id, rrf in ranked:
            res = result_map[chunk_id]
            # Replace raw score with RRF score for downstream use
            res.score = rrf
            merged.append(res)

        return merged
