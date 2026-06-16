"""
Ingestion API routes.
POST /api/v1/ingest — file upload
POST /api/v1/ingest/bulk — bulk directory ingest
GET  /api/v1/documents — list documents
DELETE /api/v1/documents/{doc_id} — delete document
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.ingestion.pipeline import IngestionPipeline, IngestionResult
from app.observability.metrics import DOCUMENTS_INGESTED, INGESTION_LATENCY
import time

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def get_pipeline(request: Request) -> IngestionPipeline:
    return request.app.state.pipeline


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class BulkIngestRequest(BaseModel):
    directory_path: str = Field(..., description="Absolute path to directory containing documents")
    recursive: bool = Field(default=True, description="Search subdirectories recursively")
    file_types: List[str] = Field(
        default=["pdf", "html", "htm", "csv"],
        description="File extensions to include (without dot)",
    )


class BulkIngestResponse(BaseModel):
    total_files: int
    succeeded: int
    failed: int
    results: List[dict]


class DocumentInfo(BaseModel):
    doc_id: str
    source: str
    chunk_count: int
    doc_type: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ingest", response_model=dict, summary="Ingest a single document")
async def ingest_file(
    request: Request,
    file: UploadFile = File(..., description="PDF, HTML, or CSV file to ingest"),
    pipeline: IngestionPipeline = Depends(get_pipeline),
):
    """
    Upload and ingest a single document (PDF, HTML, or CSV).
    Returns ingestion metadata including chunk count and duration.
    """
    allowed_types = {"application/pdf", "text/html", "text/csv", "text/plain"}
    allowed_extensions = {".pdf", ".html", ".htm", ".csv", ".txt", ".md"}

    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {allowed_extensions}",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    t0 = time.perf_counter()
    result: IngestionResult = await pipeline.ingest_bytes(
        content=content,
        filename=file.filename or "upload",
        content_type=file.content_type or "",
    )
    duration = time.perf_counter() - t0

    INGESTION_LATENCY.observe(duration)
    if result.status == "success":
        DOCUMENTS_INGESTED.inc()

    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.error or "Ingestion failed")

    return {
        "doc_id": result.doc_id,
        "filename": result.filename,
        "chunk_count": result.chunk_count,
        "duration_ms": result.duration_ms,
        "status": result.status,
    }


@router.post("/ingest/bulk", response_model=BulkIngestResponse, summary="Bulk ingest from directory")
async def bulk_ingest(
    request: Request,
    body: BulkIngestRequest,
    pipeline: IngestionPipeline = Depends(get_pipeline),
):
    """
    Ingest all matching files from a directory path.
    Runs ingestion concurrently with a semaphore of 4 workers.
    """
    dir_path = Path(body.directory_path)
    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory not found: {body.directory_path}",
        )

    # Collect matching files
    extensions = {f".{ext.lstrip('.')}" for ext in body.file_types}
    if body.recursive:
        files = [f for f in dir_path.rglob("*") if f.is_file() and f.suffix.lower() in extensions]
    else:
        files = [f for f in dir_path.iterdir() if f.is_file() and f.suffix.lower() in extensions]

    if not files:
        return BulkIngestResponse(total_files=0, succeeded=0, failed=0, results=[])

    logger.info("Bulk ingest: %d files from '%s'", len(files), dir_path)

    sem = asyncio.Semaphore(4)

    async def _ingest_one(file_path: Path) -> dict:
        async with sem:
            t0 = time.perf_counter()
            result = await pipeline.ingest_file(str(file_path))
            duration = time.perf_counter() - t0
            if result.status == "success":
                DOCUMENTS_INGESTED.inc()
                INGESTION_LATENCY.observe(duration)
            return {
                "filename": result.filename,
                "doc_id": result.doc_id,
                "chunk_count": result.chunk_count,
                "status": result.status,
                "error": result.error,
            }

    tasks = [_ingest_one(f) for f in files]
    results = await asyncio.gather(*tasks)

    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = len(results) - succeeded

    return BulkIngestResponse(
        total_files=len(files),
        succeeded=succeeded,
        failed=failed,
        results=list(results),
    )


@router.get("/documents", summary="List all ingested documents")
async def list_documents(request: Request):
    """
    Return a list of all documents currently indexed in the vector store.
    """
    vector_store = request.app.state.vector_store
    docs = vector_store.list_documents()
    return {"documents": docs, "total": len(docs)}


@router.delete("/documents/{doc_id}", summary="Delete a document")
async def delete_document(doc_id: str, request: Request):
    """
    Remove a document and all its chunks from vector store and BM25 index.
    """
    vector_store = request.app.state.vector_store
    bm25_store = request.app.state.bm25_store

    deleted_vector = vector_store.delete_document(doc_id)
    deleted_bm25 = bm25_store.delete_document(doc_id)

    if deleted_vector == 0 and deleted_bm25 == 0:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    return {
        "doc_id": doc_id,
        "deleted_chunks_vector": deleted_vector,
        "deleted_chunks_bm25": deleted_bm25,
        "status": "deleted",
    }
