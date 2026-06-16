"""
Ingestion pipeline: orchestrates parsing → chunking → embedding → storage.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import settings
from app.ingestion.chunker import Chunker, Chunk
from app.ingestion.embedder import Embedder
from app.ingestion.parsers.pdf_parser import parse_pdf, parse_pdf_bytes
from app.ingestion.parsers.html_parser import parse_html, parse_html_bytes
from app.ingestion.parsers.csv_parser import parse_csv, parse_csv_bytes
from app.retrieval.vector_store import VectorStore
from app.retrieval.bm25_store import BM25Store

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result returned after ingesting a single document."""
    doc_id: str
    filename: str
    chunk_count: int
    duration_ms: float
    status: str  # "success" | "error"
    error: Optional[str] = None


_EXTENSION_MAP = {
    ".pdf": "pdf",
    ".html": "html",
    ".htm": "html",
    ".csv": "csv",
    ".tsv": "csv",
    ".txt": "text",
    ".md": "md",
}

_CONTENT_TYPE_MAP = {
    "application/pdf": "pdf",
    "text/html": "html",
    "text/csv": "csv",
    "text/plain": "text",
}


class IngestionPipeline:
    """
    Orchestrates the full ingestion workflow:
    Parse → Chunk → Embed → Store in VectorDB + BM25.
    Thread-safe via asyncio lock.
    """

    def __init__(self, embedder: Embedder, vector_store: VectorStore, bm25_store: BM25Store):
        self._embedder = embedder
        self._vector_store = vector_store
        self._bm25_store = bm25_store
        self._chunker = Chunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest_file(
        self,
        file_path: str,
        file_type: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> IngestionResult:
        """
        Ingest a file from the filesystem.

        Args:
            file_path: Path to the file.
            file_type: Override file type detection ('pdf', 'html', 'csv').
            doc_id: Optional stable ID; generated if not provided.

        Returns:
            IngestionResult
        """
        path = Path(file_path)
        filename = path.name
        doc_id = doc_id or str(uuid.uuid4())
        detected_type = file_type or _EXTENSION_MAP.get(path.suffix.lower(), "text")

        start = time.perf_counter()
        try:
            records = self._parse_file(str(path), detected_type)
            result = await self._process(records, doc_id, filename, detected_type)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "Ingested '%s' → %d chunks in %.1f ms",
                filename, result.chunk_count, duration_ms,
            )
            return IngestionResult(
                doc_id=doc_id,
                filename=filename,
                chunk_count=result.chunk_count,
                duration_ms=round(duration_ms, 2),
                status="success",
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error("Failed to ingest '%s': %s", filename, exc, exc_info=True)
            return IngestionResult(
                doc_id=doc_id,
                filename=filename,
                chunk_count=0,
                duration_ms=round(duration_ms, 2),
                status="error",
                error=str(exc),
            )

    async def ingest_bytes(
        self,
        content: bytes,
        filename: str,
        content_type: str = "",
        doc_id: Optional[str] = None,
    ) -> IngestionResult:
        """
        Ingest document from raw bytes (e.g., API upload).

        Args:
            content: Raw file bytes.
            filename: Original filename.
            content_type: MIME type hint.
            doc_id: Optional stable ID.

        Returns:
            IngestionResult
        """
        doc_id = doc_id or str(uuid.uuid4())
        ext = Path(filename).suffix.lower()
        detected_type = (
            _CONTENT_TYPE_MAP.get(content_type)
            or _EXTENSION_MAP.get(ext)
            or "text"
        )

        start = time.perf_counter()
        try:
            records = self._parse_bytes(content, filename, detected_type)
            result = await self._process(records, doc_id, filename, detected_type)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "Ingested bytes '%s' → %d chunks in %.1f ms",
                filename, result.chunk_count, duration_ms,
            )
            return IngestionResult(
                doc_id=doc_id,
                filename=filename,
                chunk_count=result.chunk_count,
                duration_ms=round(duration_ms, 2),
                status="success",
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error("Failed to ingest bytes '%s': %s", filename, exc, exc_info=True)
            return IngestionResult(
                doc_id=doc_id,
                filename=filename,
                chunk_count=0,
                duration_ms=round(duration_ms, 2),
                status="error",
                error=str(exc),
            )

    async def get_stats(self) -> dict:
        """Return pipeline-level statistics."""
        vs_stats = self._vector_store.get_stats()
        bm25_stats = self._bm25_store.get_stats()
        return {
            "total_documents": vs_stats.get("num_documents", 0),
            "total_chunks": vs_stats.get("num_chunks", 0),
            "index_size_mb": vs_stats.get("index_size_mb", 0),
            "bm25_corpus_size": bm25_stats.get("corpus_size", 0),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_file(self, file_path: str, doc_type: str) -> list:
        if doc_type == "pdf":
            return parse_pdf(file_path)
        elif doc_type == "html":
            return parse_html(file_path)
        elif doc_type == "csv":
            return parse_csv(file_path)
        else:
            # Plain text
            text = Path(file_path).read_text(encoding="utf-8", errors="replace")
            return [{"text": text, "source": Path(file_path).name}]

    def _parse_bytes(self, content: bytes, filename: str, doc_type: str) -> list:
        if doc_type == "pdf":
            return parse_pdf_bytes(content, filename)
        elif doc_type == "html":
            return parse_html_bytes(content, filename)
        elif doc_type == "csv":
            return parse_csv_bytes(content, filename)
        else:
            text = content.decode("utf-8", errors="replace")
            return [{"text": text, "source": filename}]

    async def _process(self, records: list, doc_id: str, filename: str, doc_type: str) -> IngestionResult:
        """Chunk → embed → store (thread-safe)."""
        chunks: list[Chunk] = self._chunker.chunk_records(records, doc_id, doc_type)

        if not chunks:
            logger.warning("No chunks produced for '%s'", filename)
            return IngestionResult(
                doc_id=doc_id, filename=filename, chunk_count=0,
                duration_ms=0, status="success",
            )

        texts = [c.text for c in chunks]

        # Embed in thread pool (CPU-bound)
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, self._embedder.embed, texts)

        async with self._lock:
            self._vector_store.add_chunks(chunks, embeddings)
            self._bm25_store.add_chunks(chunks)

        return IngestionResult(
            doc_id=doc_id, filename=filename, chunk_count=len(chunks),
            duration_ms=0, status="success",
        )
