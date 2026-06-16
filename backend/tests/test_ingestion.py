"""
Tests for ingestion pipeline: parsers, chunker, embedder, pipeline.
"""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Ensure app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# PDF Parser tests
# ---------------------------------------------------------------------------

class TestPDFParser:
    """Tests for the PDF parser using mock fitz."""

    def test_parse_pdf_bytes_empty(self):
        """Empty/invalid bytes should return empty list."""
        from app.ingestion.parsers.pdf_parser import parse_pdf_bytes
        results = parse_pdf_bytes(b"", "empty.pdf")
        assert results == []

    def test_parse_pdf_bytes_structure(self):
        """Parsed records have required keys."""
        try:
            import fitz
            # Build a minimal PDF in memory
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), "Hello from test PDF. This is page one content.")
            content = doc.write()
            doc.close()

            from app.ingestion.parsers.pdf_parser import parse_pdf_bytes
            results = parse_pdf_bytes(content, "test.pdf")
            assert len(results) >= 1
            for r in results:
                assert "text" in r
                assert "page" in r
                assert "source" in r
                assert r["source"] == "test.pdf"
        except ImportError:
            pytest.skip("fitz (PyMuPDF) not installed")

    def test_parse_pdf_page_numbers_start_at_1(self):
        """Page numbers should be 1-indexed."""
        try:
            import fitz
            doc = fitz.open()
            for i in range(3):
                page = doc.new_page()
                page.insert_text((72, 72), f"Content for page {i + 1}.")
            content = doc.write()
            doc.close()

            from app.ingestion.parsers.pdf_parser import parse_pdf_bytes
            results = parse_pdf_bytes(content, "multi.pdf")
            pages = [r["page"] for r in results]
            assert min(pages) >= 1
        except ImportError:
            pytest.skip("fitz not installed")


# ---------------------------------------------------------------------------
# HTML Parser tests
# ---------------------------------------------------------------------------

class TestHTMLParser:
    def test_basic_html_extraction(self):
        from app.ingestion.parsers.html_parser import _parse_html_string
        html = """<html><body>
        <h1>Main Title</h1>
        <h2>Section One</h2>
        <p>This is the first paragraph with some useful content about machine learning.</p>
        <p>Second paragraph with more detail about the topic at hand here.</p>
        <h2>Section Two</h2>
        <p>Another paragraph about natural language processing and AI models.</p>
        </body></html>"""
        results = _parse_html_string(html, source="test.html", source_path="test.html")
        assert len(results) >= 1
        for r in results:
            assert "text" in r
            assert "section" in r
            assert "source" in r
            assert r["source"] == "test.html"

    def test_scripts_stripped(self):
        from app.ingestion.parsers.html_parser import _parse_html_string
        html = """<html><head><script>alert('hack');</script></head>
        <body><p>Clean content here that should be extracted properly.</p></body></html>"""
        results = _parse_html_string(html, source="test.html", source_path="test.html")
        for r in results:
            assert "alert" not in r["text"]
            assert "hack" not in r["text"]

    def test_empty_html(self):
        from app.ingestion.parsers.html_parser import _parse_html_string
        results = _parse_html_string("", source="empty.html", source_path="empty.html")
        assert results == []

    def test_headings_metadata(self):
        from app.ingestion.parsers.html_parser import _parse_html_string
        html = """<html><body>
        <h1>Document Title</h1>
        <h2>Chapter One</h2>
        <p>Content in chapter one. More words here to exceed minimum length.</p>
        </body></html>"""
        results = _parse_html_string(html, source="test.html", source_path="test.html")
        # headings should be in metadata
        if results:
            assert "headings" in results[0]


# ---------------------------------------------------------------------------
# CSV Parser tests
# ---------------------------------------------------------------------------

class TestCSVParser:
    def test_basic_csv(self):
        from app.ingestion.parsers.csv_parser import parse_csv_bytes
        csv_content = b"name,age,city\nAlice,30,NYC\nBob,25,LA\nCharlie,35,Chicago\n"
        results = parse_csv_bytes(csv_content, "test.csv")
        assert len(results) == 3
        for r in results:
            assert "text" in r
            assert "row_index" in r
            assert "name:" in r["text"].lower() or "Name:" in r["text"]

    def test_csv_sliding_window(self):
        from app.ingestion.parsers.csv_parser import parse_csv_bytes
        csv_content = b"col1,col2\na,1\nb,2\nc,3\nd,4\ne,5\n"
        results = parse_csv_bytes(csv_content, "test.csv", window_size=2, window_overlap=1)
        # With 5 rows, window=2, overlap=1 → step=1 → ~4 windows
        assert len(results) >= 2

    def test_empty_csv(self):
        from app.ingestion.parsers.csv_parser import parse_csv_bytes
        results = parse_csv_bytes(b"", "empty.csv")
        assert results == []

    def test_csv_with_semicolons(self):
        from app.ingestion.parsers.csv_parser import parse_csv_bytes
        csv_content = "name;value;note\nA;1;first\nB;2;second\n".encode("utf-8")
        results = parse_csv_bytes(csv_content, "semi.csv")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Chunker tests
# ---------------------------------------------------------------------------

class TestChunker:
    def test_recursive_chunker_respects_size(self):
        from app.ingestion.chunker import RecursiveCharacterChunker
        chunker = RecursiveCharacterChunker(chunk_size=100, chunk_overlap=10)
        text = "This is a sentence. " * 20
        chunks = chunker.chunk(text)
        for c in chunks:
            assert len(c) <= 200  # some tolerance for overlap

    def test_semantic_chunker_sentence_grouping(self):
        from app.ingestion.chunker import SemanticChunker
        chunker = SemanticChunker(chunk_size=100, chunk_overlap=0)
        text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        assert all(len(c) > 0 for c in chunks)

    def test_chunker_returns_chunk_objects(self):
        from app.ingestion.chunker import Chunker
        chunker = Chunker(chunk_size=200, chunk_overlap=20)
        records = [
            {"text": "This is the first document. " * 10, "source": "test.pdf", "page": 1},
        ]
        chunks = chunker.chunk_records(records, doc_id="doc1", doc_type="pdf")
        assert len(chunks) >= 1
        for c in chunks:
            assert c.doc_id == "doc1"
            assert c.chunk_id != ""
            assert c.source == "test.pdf"
            assert c.text != ""

    def test_chunker_empty_input(self):
        from app.ingestion.chunker import Chunker
        chunker = Chunker()
        chunks = chunker.chunk_records([], doc_id="doc1")
        assert chunks == []


# ---------------------------------------------------------------------------
# Embedder tests
# ---------------------------------------------------------------------------

class TestEmbedder:
    @patch("app.ingestion.embedder.SentenceTransformer")
    @patch("app.ingestion.embedder.diskcache")
    def test_embed_returns_numpy(self, mock_cache, mock_st):
        """Embedder.embed() should return np.ndarray."""
        import app.ingestion.embedder as emb_module

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.random.rand(2, 384).astype(np.float32)
        mock_st.return_value = mock_model

        mock_cache_obj = MagicMock()
        mock_cache_obj.get.return_value = None
        mock_cache.Cache.return_value = mock_cache_obj

        # Reset singleton
        emb_module._EMBEDDER_INSTANCE = None

        from app.ingestion.embedder import Embedder
        embedder = Embedder()
        embedder._model = mock_model
        embedder._dim = 384
        embedder._cache = mock_cache_obj

        result = embedder.embed(["hello", "world"])
        assert isinstance(result, np.ndarray)
        assert result.shape == (2, 384)

    @patch("app.ingestion.embedder.SentenceTransformer")
    @patch("app.ingestion.embedder.diskcache")
    def test_embed_query_shape(self, mock_cache, mock_st):
        import app.ingestion.embedder as emb_module

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.random.rand(1, 384).astype(np.float32)
        mock_st.return_value = mock_model

        mock_cache_obj = MagicMock()
        mock_cache_obj.get.return_value = None
        mock_cache.Cache.return_value = mock_cache_obj

        emb_module._EMBEDDER_INSTANCE = None

        from app.ingestion.embedder import Embedder
        embedder = Embedder()
        embedder._model = mock_model
        embedder._dim = 384
        embedder._cache = mock_cache_obj

        result = embedder.embed_query("test query")
        assert isinstance(result, np.ndarray)
        assert result.shape == (384,)


# ---------------------------------------------------------------------------
# Pipeline integration test (mocked)
# ---------------------------------------------------------------------------

class TestIngestionPipeline:
    @pytest.mark.asyncio
    async def test_ingest_bytes_returns_result(self):
        """Pipeline should return IngestionResult with status."""
        from app.ingestion.pipeline import IngestionPipeline

        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = np.random.rand(5, 384).astype(np.float32)

        mock_vs = MagicMock()
        mock_vs.add_chunks = MagicMock()

        mock_bm25 = MagicMock()
        mock_bm25.add_chunks = MagicMock()

        pipeline = IngestionPipeline(mock_embedder, mock_vs, mock_bm25)

        # Simple text ingestion
        result = await pipeline.ingest_bytes(
            content=b"This is test content for ingestion. " * 20,
            filename="test.txt",
            content_type="text/plain",
        )

        assert result.status == "success"
        assert result.filename == "test.txt"
        assert result.doc_id != ""

    @pytest.mark.asyncio
    async def test_ingest_bytes_csv(self):
        from app.ingestion.pipeline import IngestionPipeline

        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = np.random.rand(3, 384).astype(np.float32)
        mock_vs = MagicMock()
        mock_bm25 = MagicMock()

        pipeline = IngestionPipeline(mock_embedder, mock_vs, mock_bm25)

        csv_content = b"name,value\nalpha,1\nbeta,2\ngamma,3\n"
        result = await pipeline.ingest_bytes(csv_content, "data.csv", "text/csv")
        assert result.status == "success"
