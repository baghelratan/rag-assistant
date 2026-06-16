"""
Health check, stats, and Prometheus metrics endpoints.
GET /api/v1/health  — detailed component health
GET /api/v1/stats   — system statistics
GET /metrics        — Prometheus metrics (plain text)
"""

import logging
import time
from typing import Dict, Any

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def _check_vector_store(request: Request) -> Dict[str, Any]:
    try:
        vs = request.app.state.vector_store
        stats = vs.get_stats()
        return {"status": "ok", "chunks": stats.get("num_chunks", 0)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _check_embedder(request: Request) -> Dict[str, Any]:
    try:
        embedder = request.app.state.embedder
        # Quick smoke test
        _ = embedder.embed_query("health check")
        return {"status": "ok", "model": settings.EMBED_MODEL}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _check_session_db(request: Request) -> Dict[str, Any]:
    try:
        sm = request.app.state.session_manager
        sessions = await sm.list_sessions()
        return {"status": "ok", "session_count": len(sessions)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _check_llm(request: Request) -> Dict[str, Any]:
    try:
        llm = request.app.state.llm_client
        gemini_ok = llm._gemini_client is not None
        openai_ok = llm._openai_client is not None
        return {
            "status": "ok" if (gemini_ok or openai_ok) else "degraded",
            "gemini": gemini_ok,
            "openai": openai_ok,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@router.get("/api/v1/health", summary="Detailed health check")
async def health_check(request: Request):
    """
    Returns detailed health status for all backend components.
    """
    start_time = getattr(request.app.state, "start_time", time.time())
    uptime_seconds = time.time() - start_time

    vector_db_health, embedder_health, session_health = await _check_vector_store(request), \
        await _check_embedder(request), await _check_session_db(request)
    llm_health = _check_llm(request)

    components = {
        "vector_db": vector_db_health,
        "embedder": embedder_health,
        "session_db": session_health,
        "llm": llm_health,
    }

    all_ok = all(c.get("status") == "ok" for c in components.values())
    any_error = any(c.get("status") == "error" for c in components.values())

    overall = "healthy" if all_ok else ("degraded" if not any_error else "unhealthy")

    return {
        "status": overall,
        "version": settings.APP_VERSION,
        "uptime_seconds": round(uptime_seconds, 1),
        "components": components,
    }


# ---------------------------------------------------------------------------
# System stats
# ---------------------------------------------------------------------------

@router.get("/api/v1/stats", summary="System statistics")
async def get_stats(request: Request):
    """
    Returns system-wide statistics: document count, index size, cache stats, sessions.
    """
    pipeline = request.app.state.pipeline
    pipeline_stats = await pipeline.get_stats()

    cache = request.app.state.cache
    cache_stats = cache.get_stats()

    session_manager = request.app.state.session_manager
    sessions = await session_manager.list_sessions()

    return {
        "total_documents": pipeline_stats.get("total_documents", 0),
        "total_chunks": pipeline_stats.get("total_chunks", 0),
        "index_size_mb": pipeline_stats.get("index_size_mb", 0),
        "bm25_corpus_size": pipeline_stats.get("bm25_corpus_size", 0),
        "cache": cache_stats,
        "active_sessions": len(sessions),
        "version": settings.APP_VERSION,
    }


# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """Expose Prometheus metrics in text format."""
    data = generate_latest()
    return PlainTextResponse(
        content=data.decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )
