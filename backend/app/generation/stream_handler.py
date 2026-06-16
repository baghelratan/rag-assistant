"""
Server-Sent Events (SSE) stream handler for streaming LLM responses.
"""

import json
import logging
from typing import AsyncGenerator, Any, Dict, Optional

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


class StreamHandler:
    """
    Converts an async LLM token generator into a proper SSE StreamingResponse.
    SSE format: data: {json}\n\n
    """

    async def stream_response(
        self,
        generator: AsyncGenerator[str, None],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StreamingResponse:
        """
        Wrap an async generator in a StreamingResponse with SSE formatting.

        Args:
            generator: Async generator yielding text tokens.
            metadata: Optional metadata to attach to the final done event.

        Returns:
            FastAPI StreamingResponse with text/event-stream content type.
        """
        return StreamingResponse(
            content=self._sse_generator(generator, metadata or {}),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    async def _sse_generator(
        self,
        generator: AsyncGenerator[str, None],
        metadata: Dict[str, Any],
    ) -> AsyncGenerator[bytes, None]:
        """
        Internal generator that wraps token stream in SSE format.
        Handles client disconnection gracefully.
        """
        try:
            async for token in generator:
                if not token:
                    continue
                event = json.dumps({"token": token, "done": False})
                yield f"data: {event}\n\n".encode("utf-8")

            # Final done event with metadata
            final_event = json.dumps(
                {"token": "", "done": True, "metadata": metadata}
            )
            yield f"data: {final_event}\n\n".encode("utf-8")

        except GeneratorExit:
            logger.info("Client disconnected from SSE stream")
        except Exception as exc:
            logger.error("SSE streaming error: %s", exc, exc_info=True)
            error_event = json.dumps(
                {"token": "", "done": True, "error": str(exc), "metadata": metadata}
            )
            try:
                yield f"data: {error_event}\n\n".encode("utf-8")
            except Exception:
                pass  # Client already gone

    def make_error_stream(self, error_message: str) -> StreamingResponse:
        """Return a single SSE error event as a StreamingResponse."""
        async def _err_gen():
            event = json.dumps({"token": "", "done": True, "error": error_message})
            yield f"data: {event}\n\n".encode("utf-8")

        return StreamingResponse(
            content=_err_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )
