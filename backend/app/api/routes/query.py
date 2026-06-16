"""
Query API routes.
POST /api/v1/query/stream — streaming SSE query
POST /api/v1/query — non-streaming query
"""

import asyncio
import logging
import time
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.generation.citation_builder import CitationBuilder
from app.generation.hallucination import HallucinationDetector
from app.generation.prompt_builder import PromptBuilder
from app.generation.stream_handler import StreamHandler
from app.observability.metrics import (
    HALLUCINATION_DETECTIONS, track_query
)
from app.security.injection_guard import InjectionGuard

logger = logging.getLogger(__name__)

router = APIRouter()

_prompt_builder = PromptBuilder()
_citation_builder = CitationBuilder()
_stream_handler = StreamHandler()
_injection_guard = InjectionGuard()

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=settings.MAX_QUERY_LENGTH)
    session_id: Optional[str] = Field(default=None)
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    use_cache: bool = Field(default=True)

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        return v.strip()


class QueryResponse(BaseModel):
    answer: str
    session_id: Optional[str]
    citations: list
    hallucination: dict
    model_used: str
    duration_ms: float
    cached: bool = False


# ---------------------------------------------------------------------------
# Shared pipeline logic
# ---------------------------------------------------------------------------

async def _run_rag_pipeline(request: Request, query_req: QueryRequest):
    """
    Full RAG pipeline:
    Injection scan → retrieve → rerank → compress → build prompt → generate → check hallucination
    """
    query = query_req.query
    session_id = query_req.session_id
    top_k = query_req.top_k or settings.TOP_K_RETRIEVAL

    # 1. Injection guard
    scan = _injection_guard.scan(query)
    if not scan.is_safe:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "injection_detected",
                "risk_level": scan.risk_level,
                "message": "Your query was flagged for potential prompt injection.",
            },
        )

    # 2. Check response cache
    cache = request.app.state.cache
    cache_key = cache.make_key(query, session_id or "")
    if query_req.use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return {"answer": cached, "cached": True, "citations": [], "hallucination": {}}

    # 3. Retrieve
    retriever = request.app.state.retriever
    results = await retriever.retrieve(query, top_k=top_k)

    if not results:
        raise HTTPException(status_code=404, detail="No relevant documents found.")

    # 4. Rerank
    reranker = request.app.state.reranker
    loop = asyncio.get_event_loop()
    reranked = await loop.run_in_executor(
        None, reranker.rerank, query, results, settings.TOP_K_RERANK
    )

    # 5. Compress context
    compressor = request.app.state.compressor
    compressed = await loop.run_in_executor(None, compressor.compress, query, reranked)

    # 6. Session history
    session_manager = request.app.state.session_manager
    history = []
    if session_id and await session_manager.session_exists(session_id):
        msgs = await session_manager.get_history(session_id, limit=10)
        history = [{"role": m.role, "content": m.content} for m in msgs]

    # 7. Build prompt
    prompt = _prompt_builder.build_rag_prompt(query, compressed, history)

    return {
        "prompt": prompt,
        "compressed": compressed,
        "session_id": session_id,
        "cache_key": cache_key,
    }


# ---------------------------------------------------------------------------
# Streaming endpoint
# ---------------------------------------------------------------------------

@router.post("/query/stream", summary="Query with SSE streaming response")
async def query_stream(request: Request, query_req: QueryRequest):
    """
    Full RAG pipeline with Server-Sent Events streaming.
    Returns token-by-token response with final metadata event.
    """
    t_start = time.perf_counter()

    try:
        pipeline_data = await _run_rag_pipeline(request, query_req)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Pipeline error: %s", exc, exc_info=True)
        return _stream_handler.make_error_stream(str(exc))

    if pipeline_data.get("cached"):
        async def _cached_gen():
            yield pipeline_data["answer"]

        return await _stream_handler.stream_response(
            _cached_gen(),
            metadata={"cached": True},
        )

    prompt = pipeline_data["prompt"]
    compressed = pipeline_data["compressed"]
    session_id = pipeline_data["session_id"]
    cache_key = pipeline_data["cache_key"]
    llm_client = request.app.state.llm_client
    session_manager = request.app.state.session_manager

    full_response: list[str] = []

    async def _gen_and_collect() -> AsyncGenerator[str, None]:
        async for token in llm_client.generate_stream(prompt):
            full_response.append(token)
            yield token

        # Post-generation: run hallucination check + save to session
        response_text = "".join(full_response)
        context_texts = [r.text for r in compressed]
        embedder = request.app.state.embedder
        detector = HallucinationDetector(embedder)
        hal_result = detector.check(response_text, context_texts)
        if hal_result.is_hallucination:
            HALLUCINATION_DETECTIONS.inc()

        # Save to session
        if session_id:
            try:
                await session_manager.add_message(session_id, "user", query_req.query)
                await session_manager.add_message(
                    session_id, "assistant", response_text,
                    metadata={
                        "model": llm_client.last_model_used,
                        "hallucination_score": hal_result.score,
                    },
                )
            except Exception as e:
                logger.error("Failed to save to session: %s", e)

        # Cache response
        request.app.state.cache.set(cache_key, response_text)

        # Track metrics
        duration = time.perf_counter() - t_start
        track_query(
            duration=duration,
            tokens=len(response_text.split()),
            model=llm_client.last_model_used,
            top_score=compressed[0].rerank_score or compressed[0].score if compressed else 0.0,
        )

    citations = _citation_builder.build_citations(compressed)
    metadata = {
        "session_id": session_id,
        "model_used": llm_client.last_model_used if hasattr(llm_client, "last_model_used") else "",
        "citations": [
            {
                "id": c.id,
                "source": c.source,
                "page_or_row": c.page_or_row,
                "snippet": c.text_snippet,
            }
            for c in citations
        ],
    }

    return await _stream_handler.stream_response(_gen_and_collect(), metadata=metadata)


# ---------------------------------------------------------------------------
# Non-streaming endpoint
# ---------------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse, summary="Query (non-streaming)")
async def query_sync(request: Request, query_req: QueryRequest):
    """
    Full RAG pipeline returning a complete JSON response.
    """
    t_start = time.perf_counter()

    try:
        pipeline_data = await _run_rag_pipeline(request, query_req)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Pipeline error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    if pipeline_data.get("cached"):
        return QueryResponse(
            answer=pipeline_data["answer"],
            session_id=query_req.session_id,
            citations=[],
            hallucination={},
            model_used="cache",
            duration_ms=0.0,
            cached=True,
        )

    prompt = pipeline_data["prompt"]
    compressed = pipeline_data["compressed"]
    session_id = pipeline_data["session_id"]
    cache_key = pipeline_data["cache_key"]
    llm_client = request.app.state.llm_client
    session_manager = request.app.state.session_manager

    # Generate (non-streaming)
    try:
        answer = await llm_client.generate(prompt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LLM generation failed: {exc}")

    # Hallucination check
    context_texts = [r.text for r in compressed]
    embedder = request.app.state.embedder
    detector = HallucinationDetector(embedder)
    hal_result = detector.check(answer, context_texts)
    if hal_result.is_hallucination:
        HALLUCINATION_DETECTIONS.inc()

    # Save to session
    if session_id:
        try:
            await session_manager.add_message(session_id, "user", query_req.query)
            await session_manager.add_message(
                session_id, "assistant", answer,
                metadata={
                    "model": llm_client.last_model_used,
                    "hallucination_score": hal_result.score,
                },
            )
        except Exception as e:
            logger.error("Failed to save to session: %s", e)

    # Cache
    request.app.state.cache.set(cache_key, answer)

    # Metrics
    duration = time.perf_counter() - t_start
    track_query(
        duration=duration,
        tokens=len(answer.split()),
        model=llm_client.last_model_used,
        top_score=compressed[0].rerank_score or compressed[0].score if compressed else 0.0,
    )

    citations = _citation_builder.build_citations(compressed)

    return QueryResponse(
        answer=answer,
        session_id=session_id,
        citations=[
            {
                "id": c.id,
                "source": c.source,
                "page_or_row": c.page_or_row,
                "snippet": c.text_snippet,
            }
            for c in citations
        ],
        hallucination={
            "score": hal_result.score,
            "is_hallucination": hal_result.is_hallucination,
            "flagged_count": len(hal_result.flagged_sentences),
        },
        model_used=llm_client.last_model_used,
        duration_ms=round(duration * 1000, 2),
        cached=False,
    )
