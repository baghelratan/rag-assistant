"""
Context compressor: extracts the most relevant sentences from each retrieved chunk
using TF-IDF cosine overlap with the query.
"""

import logging
import re
from typing import List, Optional

import numpy as np

from app.ingestion.embedder import Embedder
from app.retrieval.vector_store import SearchResult

logger = logging.getLogger(__name__)

_MAX_TOKENS = 400
_AVG_CHARS_PER_TOKEN = 4  # rough approximation


def _sentence_split(text: str) -> List[str]:
    """Split text into sentences using regex."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


class ContextCompressor:
    """
    Compresses retrieved context chunks to their most relevant sentences.
    Uses embedding cosine similarity between query and each sentence.
    """

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder

    def compress(
        self,
        query: str,
        results: List[SearchResult],
        max_chars: int = _MAX_TOKENS * _AVG_CHARS_PER_TOKEN,
    ) -> List[SearchResult]:
        """
        For each result, extract only the most query-relevant sentences.

        Args:
            query: User query string.
            results: List of SearchResult to compress.
            max_chars: Maximum character budget per chunk (≈ max_tokens × 4).

        Returns:
            Results with `.text` replaced by compressed text.
        """
        if not results:
            return results

        query_emb = self._embedder.embed_query(query)

        compressed: List[SearchResult] = []
        for result in results:
            try:
                c = self._compress_single(result, query_emb, max_chars)
                compressed.append(c)
            except Exception as exc:
                logger.warning("Compression failed for chunk '%s': %s", result.chunk_id, exc)
                compressed.append(result)

        return compressed

    def _compress_single(
        self,
        result: SearchResult,
        query_emb: np.ndarray,
        max_chars: int,
    ) -> SearchResult:
        """Compress a single result in place."""
        sentences = _sentence_split(result.text)
        if not sentences:
            return result

        if len(sentences) == 1:
            # Only one sentence — truncate if needed
            result.text = result.text[:max_chars]
            return result

        # Embed all sentences
        sent_embs = self._embedder.embed(sentences)

        # Cosine similarity between query and each sentence
        # (both are already L2-normalized from the embedder)
        similarities = sent_embs @ query_emb  # shape (n,)

        # Sort sentences by similarity, keep top ones within budget
        ranked_indices = np.argsort(similarities)[::-1].tolist()

        selected: List[str] = []
        total_chars = 0
        for idx in ranked_indices:
            s = sentences[idx]
            if total_chars + len(s) + 1 > max_chars:
                break
            selected.append(s)
            total_chars += len(s) + 1

        if not selected:
            # Safety: take first sentence truncated
            selected = [sentences[0][:max_chars]]

        # Restore original order for readability
        # Re-sort by original position
        original_order = sorted(
            [(sentences.index(s) if s in sentences else 999, s) for s in selected],
            key=lambda x: x[0],
        )
        compressed_text = " ".join(s for _, s in original_order)

        result.text = compressed_text
        return result
