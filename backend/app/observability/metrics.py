"""
Prometheus metrics definitions for the RAG backend.
"""

from prometheus_client import Counter, Histogram, Gauge

# ---------------------------------------------------------------------------
# HTTP request metrics
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ---------------------------------------------------------------------------
# Query pipeline metrics
# ---------------------------------------------------------------------------

QUERY_LATENCY = Histogram(
    "query_latency_seconds",
    "End-to-end query latency in seconds",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
)

RETRIEVAL_SCORE = Histogram(
    "retrieval_score",
    "Top-1 retrieval relevance score distribution",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

TOKENS_GENERATED = Counter(
    "tokens_generated_total",
    "Total number of LLM tokens generated",
)

LLM_MODEL_USED = Counter(
    "llm_model_used_total",
    "Number of times each LLM model was used",
    ["model"],
)

# ---------------------------------------------------------------------------
# Ingestion metrics
# ---------------------------------------------------------------------------

INGESTION_LATENCY = Histogram(
    "ingestion_latency_seconds",
    "Document ingestion pipeline latency in seconds",
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

DOCUMENTS_INGESTED = Counter(
    "documents_ingested_total",
    "Total number of documents successfully ingested",
)

# ---------------------------------------------------------------------------
# Cache metrics
# ---------------------------------------------------------------------------

CACHE_HITS = Counter(
    "cache_hits_total",
    "Total number of response cache hits",
)

# ---------------------------------------------------------------------------
# Quality metrics
# ---------------------------------------------------------------------------

HALLUCINATION_DETECTIONS = Counter(
    "hallucination_detections_total",
    "Total number of responses flagged as potential hallucinations",
)

# ---------------------------------------------------------------------------
# Session metrics
# ---------------------------------------------------------------------------

ACTIVE_SESSIONS = Gauge(
    "active_sessions",
    "Number of active conversation sessions",
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def track_query(
    duration: float,
    tokens: int,
    model: str,
    top_score: float,
) -> None:
    """
    Record metrics for a completed query.

    Args:
        duration: Query duration in seconds.
        tokens: Number of tokens in the response (approximate).
        model: Name of the LLM model used.
        top_score: Top retrieval/rerank score.
    """
    QUERY_LATENCY.observe(duration)
    TOKENS_GENERATED.inc(tokens)
    LLM_MODEL_USED.labels(model=model).inc()
    if top_score > 0:
        RETRIEVAL_SCORE.observe(top_score)


def track_ingestion(duration: float) -> None:
    """Record metrics for a completed ingestion."""
    INGESTION_LATENCY.observe(duration)
    DOCUMENTS_INGESTED.inc()
