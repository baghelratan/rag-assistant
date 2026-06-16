"""
Vector store wrapper around ChromaDB.
Provides add, search, delete, and stats operations.
"""

import logging
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import numpy as np
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.ingestion.chunker import Chunk

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "rag_documents"


@dataclass
class SearchResult:
    """A single retrieval result."""
    chunk_id: str
    doc_id: str
    text: str
    metadata: Dict[str, Any]
    score: float
    rerank_score: Optional[float] = None


class VectorStore:
    """
    ChromaDB-backed vector store.
    Uses a persistent client so embeddings survive restarts.
    """

    def __init__(self) -> None:
        persist_dir = settings.CHROMA_PERSIST_DIR
        os.makedirs(persist_dir, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "VectorStore ready. Collection '%s' has %d items.",
            _COLLECTION_NAME,
            self._collection.count(),
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        """
        Add chunks with pre-computed embeddings to the collection.

        Args:
            chunks: List of Chunk objects.
            embeddings: np.ndarray of shape (n, dim) matching chunks.
        """
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = []
        for c in chunks:
            meta = dict(c.metadata)
            meta["doc_id"] = c.doc_id
            meta["source"] = c.source
            # ChromaDB only accepts str/int/float/bool values
            sanitized = {
                k: (str(v) if not isinstance(v, (str, int, float, bool)) else v)
                for k, v in meta.items()
            }
            metadatas.append(sanitized)

        embedding_list = embeddings.tolist()

        # Upsert to handle re-ingestion gracefully
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embedding_list,
        )
        logger.debug("Upserted %d chunks into ChromaDB", len(chunks))

    def delete_document(self, doc_id: str) -> int:
        """
        Delete all chunks belonging to a document.

        Returns:
            Number of chunks deleted.
        """
        results = self._collection.get(where={"doc_id": doc_id}, include=[])
        ids_to_delete = results.get("ids", [])
        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
            logger.info("Deleted %d chunks for doc_id='%s'", len(ids_to_delete), doc_id)
        return len(ids_to_delete)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Similarity search using a pre-computed query embedding.

        Args:
            query_embedding: 1-D np.ndarray of shape (dim,).
            top_k: Number of results to return.
            where: Optional metadata filter dict.

        Returns:
            List of SearchResult sorted by similarity (highest first).
        """
        query_vec = query_embedding.tolist()
        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_vec],
            "n_results": min(top_k, max(1, self._collection.count())),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        try:
            response = self._collection.query(**kwargs)
        except Exception as exc:
            logger.error("ChromaDB query failed: %s", exc)
            return []

        results: List[SearchResult] = []
        ids = response.get("ids", [[]])[0]
        documents = response.get("documents", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]

        for chunk_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
            # ChromaDB cosine distance → similarity: 1 - distance
            score = 1.0 - float(dist)
            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    doc_id=meta.get("doc_id", ""),
                    text=doc,
                    metadata=meta,
                    score=score,
                )
            )

        return results

    def list_documents(self) -> List[Dict[str, Any]]:
        """Return unique documents with their chunk counts."""
        all_metas = self._collection.get(include=["metadatas"])["metadatas"] or []
        docs: Dict[str, Dict[str, Any]] = {}
        for meta in all_metas:
            doc_id = meta.get("doc_id", "unknown")
            if doc_id not in docs:
                docs[doc_id] = {
                    "doc_id": doc_id,
                    "source": meta.get("source", ""),
                    "chunk_count": 0,
                    "doc_type": meta.get("doc_type", ""),
                }
            docs[doc_id]["chunk_count"] += 1
        return list(docs.values())

    def get_stats(self) -> Dict[str, Any]:
        """Return collection statistics."""
        count = self._collection.count()
        # Approximate size: average ~1KB per chunk
        size_mb = (count * 1024) / (1024 * 1024)

        # Unique doc count
        if count > 0:
            all_metas = self._collection.get(include=["metadatas"])["metadatas"] or []
            doc_ids = {m.get("doc_id") for m in all_metas}
            num_docs = len(doc_ids)
        else:
            num_docs = 0

        return {
            "num_chunks": count,
            "num_documents": num_docs,
            "index_size_mb": round(size_mb, 3),
            "collection": _COLLECTION_NAME,
        }
