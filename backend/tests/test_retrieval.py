"""
Tests for retrieval components: VectorStore, BM25Store, HybridRetriever, Reranker.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.chunker import Chunk
from app.retrieval.vector_store import SearchResult


# ---------------------------------------------------------------------------
# BM25Store tests
# ---------------------------------------------------------------------------

class TestBM25Store:
    def _make_store(self, tmp_path):
        with patch("app.retrieval.bm25_store.settings") as mock_settings:
            mock_settings.BM25_INDEX_DIR = str(tmp_path)
            from app.retrieval.bm25_store import BM25Store
            store = BM25Store.__new__(BM25Store)
            import asyncio
            store._lock = asyncio.Lock()
            store._index_dir = tmp_path
            store._corpus = []
            store._tokenized_corpus = []
            store._bm25 = None
            return store

    def test_add_and_search(self, tmp_path):
        with patch("app.retrieval.bm25_store.settings") as mock_settings:
            mock_settings.BM25_INDEX_DIR = str(tmp_path)
            from app.retrieval.bm25_store import BM25Store

            # Manually initialize without loading from disk
            store = BM25Store.__new__(BM25Store)
            import asyncio
            store._lock = asyncio.Lock()
            store._index_dir = tmp_path
            store._corpus = []
            store._tokenized_corpus = []
            store._bm25 = None

            chunks = [
                Chunk(
                    text="machine learning algorithms for classification",
                    chunk_id="c1",
                    doc_id="d1",
                    source="ml.pdf",
                    metadata={"page": 1},
                ),
                Chunk(
                    text="deep learning neural networks and backpropagation",
                    chunk_id="c2",
                    doc_id="d1",
                    source="ml.pdf",
                    metadata={"page": 2},
                ),
                Chunk(
                    text="cooking recipes for pasta and italian cuisine",
                    chunk_id="c3",
                    doc_id="d2",
                    source="food.pdf",
                    metadata={"page": 1},
                ),
            ]

            store.add_chunks(chunks)
            results = store.search("machine learning", top_k=2)

            assert len(results) >= 1
            assert results[0].chunk_id in {"c1", "c2"}
            # Machine learning doc should rank above food doc
            assert results[0].chunk_id != "c3"

    def test_search_empty_store(self, tmp_path):
        with patch("app.retrieval.bm25_store.settings") as mock_settings:
            mock_settings.BM25_INDEX_DIR = str(tmp_path)
            from app.retrieval.bm25_store import BM25Store

            store = BM25Store.__new__(BM25Store)
            import asyncio
            store._lock = asyncio.Lock()
            store._index_dir = tmp_path
            store._corpus = []
            store._tokenized_corpus = []
            store._bm25 = None

            results = store.search("anything", top_k=5)
            assert results == []

    def test_delete_document(self, tmp_path):
        with patch("app.retrieval.bm25_store.settings") as mock_settings:
            mock_settings.BM25_INDEX_DIR = str(tmp_path)
            from app.retrieval.bm25_store import BM25Store

            store = BM25Store.__new__(BM25Store)
            import asyncio
            store._lock = asyncio.Lock()
            store._index_dir = tmp_path
            store._corpus = []
            store._tokenized_corpus = []
            store._bm25 = None

            chunks = [
                Chunk("hello world", "c1", "d1", "doc1.pdf"),
                Chunk("goodbye world", "c2", "d2", "doc2.pdf"),
            ]
            store.add_chunks(chunks)
            removed = store.delete_document("d1")
            assert removed == 1
            assert all(d["doc_id"] != "d1" for d in store._corpus)


# ---------------------------------------------------------------------------
# VectorStore tests (mocked ChromaDB)
# ---------------------------------------------------------------------------

class TestVectorStore:
    def test_add_and_search_mock(self):
        """Test VectorStore with mocked ChromaDB collection."""
        with patch("app.retrieval.vector_store.chromadb") as mock_chroma, \
             patch("app.retrieval.vector_store.settings") as mock_settings:

            mock_settings.CHROMA_PERSIST_DIR = "/tmp/test_chroma"

            mock_collection = MagicMock()
            mock_collection.count.return_value = 3
            mock_collection.query.return_value = {
                "ids": [["c1", "c2"]],
                "documents": [["text one", "text two"]],
                "metadatas": [[
                    {"doc_id": "d1", "source": "test.pdf", "page": 1},
                    {"doc_id": "d1", "source": "test.pdf", "page": 2},
                ]],
                "distances": [[0.1, 0.3]],
            }
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            from app.retrieval.vector_store import VectorStore
            vs = VectorStore()

            query_emb = np.random.rand(384).astype(np.float32)
            results = vs.search(query_emb, top_k=2)

            assert len(results) == 2
            assert results[0].score == pytest.approx(0.9, abs=0.01)  # 1 - 0.1
            assert results[1].score == pytest.approx(0.7, abs=0.01)  # 1 - 0.3

    def test_add_chunks_upsert_called(self):
        with patch("app.retrieval.vector_store.chromadb") as mock_chroma, \
             patch("app.retrieval.vector_store.settings") as mock_settings:

            mock_settings.CHROMA_PERSIST_DIR = "/tmp/test_chroma"
            mock_collection = MagicMock()
            mock_collection.count.return_value = 0
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            from app.retrieval.vector_store import VectorStore
            vs = VectorStore()

            chunks = [Chunk("test text", "c1", "d1", "source.pdf", {"page": 1})]
            embeddings = np.random.rand(1, 384).astype(np.float32)
            vs.add_chunks(chunks, embeddings)
            mock_collection.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# HybridRetriever tests
# ---------------------------------------------------------------------------

class TestHybridRetriever:
    @pytest.mark.asyncio
    async def test_rrf_merging(self):
        """RRF should merge and deduplicate results."""
        from app.retrieval.hybrid_retriever import HybridRetriever

        mock_vs = MagicMock()
        mock_bm25 = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384).astype(np.float32)

        dense_results = [
            SearchResult("c1", "d1", "text one", {}, 0.9),
            SearchResult("c2", "d1", "text two", {}, 0.7),
            SearchResult("c3", "d2", "text three", {}, 0.5),
        ]
        sparse_results = [
            SearchResult("c2", "d1", "text two", {}, 15.0),
            SearchResult("c4", "d3", "text four", {}, 10.0),
            SearchResult("c1", "d1", "text one", {}, 8.0),
        ]

        mock_vs.search.return_value = dense_results
        mock_bm25.search.return_value = sparse_results

        retriever = HybridRetriever(mock_vs, mock_bm25, mock_embedder)
        results = await retriever.retrieve("test query", top_k=4)

        # c1 and c2 appear in both lists → should rank high
        result_ids = [r.chunk_id for r in results]
        assert "c1" in result_ids
        assert "c2" in result_ids
        # No duplicates
        assert len(result_ids) == len(set(result_ids))

    @pytest.mark.asyncio
    async def test_retrieve_with_empty_stores(self):
        from app.retrieval.hybrid_retriever import HybridRetriever

        mock_vs = MagicMock()
        mock_bm25 = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384).astype(np.float32)

        mock_vs.search.return_value = []
        mock_bm25.search.return_value = []

        retriever = HybridRetriever(mock_vs, mock_bm25, mock_embedder)
        results = await retriever.retrieve("test query")
        assert results == []


# ---------------------------------------------------------------------------
# Reranker tests
# ---------------------------------------------------------------------------

class TestReranker:
    def test_reranker_orders_by_score(self):
        with patch("app.retrieval.reranker.settings") as mock_settings:
            mock_settings.RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

            from app.retrieval.reranker import Reranker
            import app.retrieval.reranker as reranker_module
            reranker_module._RERANKER_INSTANCE = None

            reranker = Reranker()
            mock_model = MagicMock()
            mock_model.predict.return_value = np.array([0.3, 0.9, 0.1])
            reranker._model = mock_model
            reranker._available = True

            results = [
                SearchResult("c1", "d1", "text one", {}, 0.8),
                SearchResult("c2", "d1", "text two", {}, 0.6),
                SearchResult("c3", "d2", "text three", {}, 0.4),
            ]
            reranked = reranker.rerank("test query", results, top_k=2)

            assert len(reranked) == 2
            assert reranked[0].chunk_id == "c2"  # highest rerank score 0.9
            assert reranked[0].rerank_score == pytest.approx(0.9)

    def test_reranker_fallback_on_model_error(self):
        with patch("app.retrieval.reranker.settings") as mock_settings:
            mock_settings.RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

            from app.retrieval.reranker import Reranker
            import app.retrieval.reranker as reranker_module
            reranker_module._RERANKER_INSTANCE = None

            reranker = Reranker()
            mock_model = MagicMock()
            mock_model.predict.side_effect = RuntimeError("Model error")
            reranker._model = mock_model
            reranker._available = True

            results = [
                SearchResult("c1", "d1", "text one", {}, 0.8),
                SearchResult("c2", "d1", "text two", {}, 0.6),
            ]
            # Should not raise, should return original order
            reranked = reranker.rerank("test query", results, top_k=2)
            assert len(reranked) == 2
