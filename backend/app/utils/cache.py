"""
Disk-backed response cache using diskcache.
"""

import hashlib
import logging
from typing import Optional, Dict, Any

import diskcache

from app.config import settings

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    Disk-backed LRU cache for query responses.
    Keys are SHA256 hashes of (query + session_id).
    """

    def __init__(self) -> None:
        self._cache = diskcache.Cache(
            directory=settings.CACHE_DIR + "/responses",
            size_limit=512 * 1024 * 1024,  # 512 MB max
        )
        self._hits = 0
        self._misses = 0
        logger.info("ResponseCache initialized at '%s'", settings.CACHE_DIR + "/responses")

    def make_key(self, query: str, session_id: str = "") -> str:
        """
        Create a cache key from query and session ID.

        Args:
            query: The user query string.
            session_id: Optional session ID for session-scoped caching.

        Returns:
            SHA256 hex digest string.
        """
        raw = f"{query.strip().lower()}|{session_id}"
        return "resp_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[str]:
        """
        Retrieve a cached response.

        Args:
            key: Cache key (from make_key).

        Returns:
            Cached string or None on miss.
        """
        value = self._cache.get(key)
        if value is not None:
            self._hits += 1
            logger.debug("Cache HIT for key '%s'", key[:16])
            return value
        self._misses += 1
        return None

    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        """
        Store a response in the cache.

        Args:
            key: Cache key.
            value: Response string to cache.
            ttl: Time-to-live in seconds (default: 1 hour).
        """
        self._cache.set(key, value, expire=ttl)
        logger.debug("Cache SET for key '%s' (ttl=%ds)", key[:16], ttl)

    def delete(self, key: str) -> None:
        """Remove a specific key from the cache."""
        self._cache.delete(key)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("ResponseCache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_rate": round(hit_rate, 4),
            "size_bytes": self._cache.volume(),
            "count": len(self._cache),
        }
