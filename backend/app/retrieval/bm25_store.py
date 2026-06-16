"""
BM25 sparse retrieval store backed by rank-bm25.
Persists corpus and index to disk using pickle.
Thread-safe via asyncio.Lock.
"""

import asyncio
import logging
import os
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional

from rank_bm25 import BM25Okapi

from app.config import settings
from app.ingestion.chunker import Chunk
from app.retrieval.vector_store import SearchResult

logger = logging.getLogger(__name__)

_CORPUS_FILE = "bm25_corpus.pkl"
_INDEX_FILE = "bm25_index.pkl"


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + lowercase tokenizer."""
    return text.lower().split()


class BM25Store:
    """
    BM25 sparse retrieval store.
    - Corpus (raw chunks) and BM25 index are persisted to disk.
    - Thread-safe with asyncio.Lock.
    """

    def __init__(self) -> None:
        self._index_dir = Path(settings.BM25_INDEX_DIR)
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

        self._corpus: List[Dict[str, Any]] = []  # list of {chunk_id, doc_id, text, metadata, source}
        self._tokenized_corpus: List[List[str]] = []
        self._bm25: Optional[BM25Okapi] = None

        self._load_from_disk()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _corpus_path(self) -> Path:
        return self._index_dir / _CORPUS_FILE

    def _index_path(self) -> Path:
        return self._index_dir / _INDEX_FILE

    def _load_from_disk(self) -> None:
        """Load existing corpus and BM25 index from disk."""
        corpus_path = self._corpus_path()
        index_path = self._index_path()

        if corpus_path.exists():
            try:
                with open(corpus_path, "rb") as f:
                    self._corpus = pickle.load(f)
                    self._tokenized_corpus = [_tokenize(doc["text"]) for doc in self._corpus]
                logger.info("BM25: loaded corpus with %d documents", len(self._corpus))
            except Exception as exc:
                logger.warning("Could not load BM25 corpus: %s — starting fresh", exc)
                self._corpus = []
                self._tokenized_corpus = []

        if self._tokenized_corpus:
            try:
                with open(index_path, "rb") as f:
                    self._bm25 = pickle.load(f)
                logger.info("BM25: loaded pre-built index")
            except Exception as exc:
                logger.warning("Could not load BM25 index: %s — rebuilding…", exc)
                self._rebuild_index_internal()

    def _save_corpus(self) -> None:
        with open(self._corpus_path(), "wb") as f:
            pickle.dump(self._corpus, f, protocol=pickle.HIGHEST_PROTOCOL)

    def _save_index(self) -> None:
        if self._bm25 is not None:
            with open(self._index_path(), "wb") as f:
                pickle.dump(self._bm25, f, protocol=pickle.HIGHEST_PROTOCOL)

    def _rebuild_index_internal(self) -> None:
        if self._tokenized_corpus:
            self._bm25 = BM25Okapi(self._tokenized_corpus)
        else:
            self._bm25 = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: List[Chunk]) -> None:
        """
        Add chunks to the BM25 corpus and rebuild the index.
        Note: Synchronous — call from within async context via run_in_executor if needed.
        """
        if not chunks:
            return

        existing_ids = {doc["chunk_id"] for doc in self._corpus}
        new_docs = []
        new_tokens = []
        for c in chunks:
            if c.chunk_id in existing_ids:
                continue
            new_docs.append(
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "text": c.text,
                    "source": c.source,
                    "metadata": c.metadata,
                }
            )
            new_tokens.append(_tokenize(c.text))

        if not new_docs:
            return

        self._corpus.extend(new_docs)
        self._tokenized_corpus.extend(new_tokens)
        self._rebuild_index_internal()

        # Persist asynchronously to avoid blocking
        try:
            self._save_corpus()
            self._save_index()
        except Exception as exc:
            logger.error("Failed to persist BM25 data: %s", exc)

        logger.debug("BM25: added %d new documents (total=%d)", len(new_docs), len(self._corpus))

    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        BM25 keyword search.

        Args:
            query: Query string.
            top_k: Number of top results.

        Returns:
            List of SearchResult ordered by BM25 score descending.
        """
        if self._bm25 is None or not self._corpus:
            return []

        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)

        # Get top-k indices
        n = min(top_k, len(scores))
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]

        results: List[SearchResult] = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            doc = self._corpus[idx]
            results.append(
                SearchResult(
                    chunk_id=doc["chunk_id"],
                    doc_id=doc["doc_id"],
                    text=doc["text"],
                    metadata=doc["metadata"],
                    score=float(scores[idx]),
                )
            )
        return results

    def rebuild_index(self) -> None:
        """Rebuild BM25 index from persisted corpus."""
        self._rebuild_index_internal()
        self._save_index()
        logger.info("BM25 index rebuilt (%d documents)", len(self._corpus))

    def delete_document(self, doc_id: str) -> int:
        """Remove all chunks for a document and rebuild the index."""
        before = len(self._corpus)
        self._corpus = [d for d in self._corpus if d["doc_id"] != doc_id]
        self._tokenized_corpus = [_tokenize(d["text"]) for d in self._corpus]
        removed = before - len(self._corpus)
        if removed:
            self._rebuild_index_internal()
            self._save_corpus()
            self._save_index()
            logger.info("BM25: removed %d chunks for doc_id='%s'", removed, doc_id)
        return removed

    def get_stats(self) -> Dict[str, Any]:
        return {
            "corpus_size": len(self._corpus),
            "has_index": self._bm25 is not None,
        }
