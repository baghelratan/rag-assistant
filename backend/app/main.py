"""
Main FastAPI application entry point.
Includes CORS, rate limiting, Prometheus metrics, structured logging, and all routers.
"""

import logging
import time
import uuid
import json
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import settings
from app.security.rate_limiter import limiter
from app.observability.metrics import REQUEST_COUNT, REQUEST_LATENCY

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = []
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))


setup_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all shared components on startup and clean up on shutdown."""
    logger.info("Starting RAG backend…")
    settings.ensure_dirs()

    # 1. Embedder (singleton — downloads model on first run)
    from app.ingestion.embedder import Embedder
    app.state.embedder = Embedder()
    logger.info("Embedder ready: %s", settings.EMBED_MODEL)

    # 2. Vector store
    from app.retrieval.vector_store import VectorStore
    app.state.vector_store = VectorStore()
    logger.info("VectorStore (ChromaDB) ready")

    # 3. BM25 store
    from app.retrieval.bm25_store import BM25Store
    app.state.bm25_store = BM25Store()
    logger.info("BM25Store ready")

    # 4. Hybrid retriever
    from app.retrieval.hybrid_retriever import HybridRetriever
    app.state.retriever = HybridRetriever(
        vector_store=app.state.vector_store,
        bm25_store=app.state.bm25_store,
        embedder=app.state.embedder,
    )
    logger.info("HybridRetriever ready")

    # 5. Reranker
    from app.retrieval.reranker import Reranker
    app.state.reranker = Reranker()
    logger.info("Reranker ready: %s", settings.RERANKER_MODEL)

    # 6. Context compressor
    from app.retrieval.compressor import ContextCompressor
    app.state.compressor = ContextCompressor(embedder=app.state.embedder)
    logger.info("ContextCompressor ready")

    # 7. Session manager
    from app.session.manager import SessionManager
    app.state.session_manager = SessionManager()
    await app.state.session_manager.init()
    logger.info("SessionManager ready")

    # 8. LLM client
    from app.generation.llm_client import LLMClient
    app.state.llm_client = LLMClient()
    logger.info("LLMClient ready (primary=%s)", settings.PRIMARY_LLM)

    # 9. Ingestion pipeline
    from app.ingestion.pipeline import IngestionPipeline
    app.state.pipeline = IngestionPipeline(
        embedder=app.state.embedder,
        vector_store=app.state.vector_store,
        bm25_store=app.state.bm25_store,
    )
    logger.info("IngestionPipeline ready")

    # 10. Response cache
    from app.utils.cache import ResponseCache
    app.state.cache = ResponseCache()
    logger.info("ResponseCache ready")

    # Record startup time
    app.state.start_time = time.time()

    logger.info("RAG backend fully initialized ✓")
    yield

    # Shutdown
    logger.info("Shutting down RAG backend…")


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade RAG (Retrieval-Augmented Generation) assistant API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Callable) -> Response:
    """Inject X-Request-ID header into every request and response."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration:.4f}s"

    # Prometheus counters
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(endpoint=request.url.path).observe(duration)

    logger.info(
        "request handled",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_s": round(duration, 4),
        },
    )
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from app.api.routes import ingest, query, sessions, health  # noqa: E402

app.include_router(ingest.router, prefix="/api/v1", tags=["ingestion"])
app.include_router(query.router, prefix="/api/v1", tags=["query"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(health.router, tags=["health"])


# ---------------------------------------------------------------------------
# Frontend Static Files Serving (for Single Container Deployments)
# ---------------------------------------------------------------------------

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))

if os.path.exists(frontend_dist):
    # Mount assets folder for static resources (CSS, JS, etc.)
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Serve other top-level files like favicon.ico directly
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        fav_path = os.path.join(frontend_dist, "favicon.ico")
        if os.path.exists(fav_path):
            return FileResponse(fav_path)
        return Response(status_code=404)

    # Catch-all route to serve index.html for React SPA routing
    @app.get("/{catchall:path}", include_in_schema=False)
    async def serve_spa(request: Request, catchall: str):
        # Do not intercept API, docs, or schema calls
        if catchall.startswith("api") or catchall.startswith("docs") or catchall.startswith("openapi.json"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
            
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return JSONResponse(status_code=404, content={"detail": "Frontend index.html not found"})
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/api/docs",
        }
