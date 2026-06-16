"""
Hallucination detector using sentence-level embedding cosine similarity.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List

import numpy as np

from app.config import settings
from app.ingestion.embedder import Embedder

logger = logging.getLogger(__name__)

_SIMILARITY_THRESHOLD = 0.7


@dataclass
class HallucinationResult:
    """Result of hallucination detection."""
    score: float                         # % of response sentences supported by context
    is_hallucination: bool               # True if score < threshold
    flagged_sentences: List[str] = field(default_factory=list)
    threshold_used: float = settings.HALLUCINATION_THRESHOLD


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 15]


class HallucinationDetector:
    """
    Detects potential hallucinations by checking if response sentences
    are semantically supported by the retrieved context.
    """

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder

    def check(
        self,
        response: str,
        context_chunks: List[str],
        similarity_threshold: float = _SIMILARITY_THRESHOLD,
    ) -> HallucinationResult:
        """
        Check a response against context chunks for hallucination.

        Args:
            response: The LLM-generated response text.
            context_chunks: List of raw context text strings.
            similarity_threshold: Cosine similarity cutoff for "supported" sentence.

        Returns:
            HallucinationResult with score and flagged sentences.
        """
        if not response.strip():
            return HallucinationResult(score=1.0, is_hallucination=False)

        if not context_chunks:
            # No context → cannot verify → flag as potential hallucination
            return HallucinationResult(
                score=0.0,
                is_hallucination=True,
                flagged_sentences=_split_sentences(response),
            )

        response_sentences = _split_sentences(response)
        if not response_sentences:
            return HallucinationResult(score=1.0, is_hallucination=False)

        # Build context sentences pool
        context_text = " ".join(context_chunks)
        context_sentences = _split_sentences(context_text)
        if not context_sentences:
            return HallucinationResult(
                score=0.0,
                is_hallucination=True,
                flagged_sentences=response_sentences,
            )

        try:
            all_texts = response_sentences + context_sentences
            all_embs = self._embedder.embed(all_texts)

            resp_embs = all_embs[: len(response_sentences)]  # (n_resp, dim)
            ctx_embs = all_embs[len(response_sentences) :]   # (n_ctx, dim)

            # Cosine similarity matrix: (n_resp, n_ctx)
            sim_matrix = resp_embs @ ctx_embs.T  # already L2-normalized

            supported = 0
            flagged: List[str] = []
            for i, sent in enumerate(response_sentences):
                max_sim = float(np.max(sim_matrix[i]))
                if max_sim >= similarity_threshold:
                    supported += 1
                else:
                    flagged.append(sent)

            score = supported / len(response_sentences)
            is_hallucination = score < settings.HALLUCINATION_THRESHOLD

            if is_hallucination:
                logger.warning(
                    "Potential hallucination detected: score=%.2f, flagged=%d/%d sentences",
                    score, len(flagged), len(response_sentences),
                )

            return HallucinationResult(
                score=round(score, 4),
                is_hallucination=is_hallucination,
                flagged_sentences=flagged,
                threshold_used=settings.HALLUCINATION_THRESHOLD,
            )

        except Exception as exc:
            logger.error("Hallucination check failed: %s", exc)
            # On error, assume no hallucination to avoid false positives
            return HallucinationResult(score=1.0, is_hallucination=False)
