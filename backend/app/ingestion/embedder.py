"""
Embedder module: wraps sentence-transformers with disk caching and singleton pattern.
"""

import hashlib
import logging
from typing import List, Optional

import numpy as np
import diskcache
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

_EMBEDDER_INSTANCE: Optional["Embedder"] = None


class Embedder:
    """
    Singleton wrapper around a sentence-transformers model.
    - Loads model once at startup.
    - Caches embeddings on disk keyed by SHA256(text).
    """

    def __new__(cls) -> "Embedder":
        global _EMBEDDER_INSTANCE
        if _EMBEDDER_INSTANCE is None:
            instance = super().__new__(cls)
            instance._initialized = False
            _EMBEDDER_INSTANCE = instance
        return _EMBEDDER_INSTANCE

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._load_model()
        self._cache = diskcache.Cache(settings.CACHE_DIR + "/embeddings")
        logger.info("Embedder initialized with model '%s'", settings.EMBED_MODEL)

    def _load_model(self) -> None:
        """Load the sentence-transformer model (downloads from HuggingFace if needed)."""
        logger.info("Loading embedding model '%s' (may download on first run)…", settings.EMBED_MODEL)
        self._model = SentenceTransformer(settings.EMBED_MODEL)
        self._dim = self._model.get_sentence_embedding_dimension()
        logger.info("Embedding model loaded. Dimension: %d", self._dim)

    @property
    def dimension(self) -> int:
        return self._dim

    def _make_cache_key(self, text: str) -> str:
        return "emb_" + hashlib.sha256(text.encode("utf-8")).hexdigest()

    def embed(self, texts: List[str], show_progress: bool = False) -> np.ndarray:
        """
        Embed a batch of texts.
        Returns np.ndarray of shape (len(texts), dim).
        Uses disk cache for already-seen texts.
        """
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)

        result = np.zeros((len(texts), self._dim), dtype=np.float32)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        for i, text in enumerate(texts):
            key = self._make_cache_key(text)
            cached = self._cache.get(key)
            if cached is not None:
                result[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            logger.debug("Embedding %d texts (cache miss)", len(uncached_texts))
            new_embeddings: np.ndarray = self._model.encode(
                uncached_texts,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=64,
            )
            for idx, embedding in zip(uncached_indices, new_embeddings):
                result[idx] = embedding
                key = self._make_cache_key(texts[idx])
                self._cache.set(key, embedding, expire=60 * 60 * 24 * 30)  # 30 days TTL

        return result

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single query string.
        Returns np.ndarray of shape (dim,).
        """
        embeddings = self.embed([query])
        return embeddings[0]
