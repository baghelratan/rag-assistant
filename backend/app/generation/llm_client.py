"""
LLM Client with Gemini as primary and OpenAI as fallback.
Supports streaming and non-streaming generation.
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# Fallback model chain
_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-1.5-flash",
    "gemini-1.0-pro",
]
_OPENAI_MODELS = ["gpt-4o-mini", "gpt-3.5-turbo"]


class LLMClient:
    """
    Multi-provider LLM client with automatic fallback.
    Primary: Google Gemini. Fallback: OpenAI.
    """

    def __init__(self) -> None:
        self._gemini_client = None
        self._openai_client = None
        self._last_model_used: str = ""

        self._init_gemini()
        self._init_openai()

    def _init_gemini(self) -> None:
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set — Gemini unavailable")
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._gemini_client = genai
            logger.info("Gemini client initialized")
        except Exception as exc:
            logger.error("Failed to initialize Gemini client: %s", exc)

    def _init_openai(self) -> None:
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set — OpenAI unavailable")
            return
        try:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI async client initialized")
        except Exception as exc:
            logger.error("Failed to initialize OpenAI client: %s", exc)

    @property
    def last_model_used(self) -> str:
        return self._last_model_used

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(self, prompt: str) -> str:
        """Generate a complete (non-streaming) response."""
        if settings.PRIMARY_LLM == "gemini" and self._gemini_client:
            for model_name in _GEMINI_MODELS:
                try:
                    result = await self._gemini_generate(prompt, model_name)
                    self._last_model_used = model_name
                    return result
                except Exception as exc:
                    logger.warning("Gemini model '%s' failed: %s — trying next", model_name, exc)

        # Fallback to OpenAI
        if self._openai_client:
            for model_name in _OPENAI_MODELS:
                try:
                    result = await self._openai_generate(prompt, model_name)
                    self._last_model_used = model_name
                    return result
                except Exception as exc:
                    logger.warning("OpenAI model '%s' failed: %s — trying next", model_name, exc)

        # Local Offline Fallback
        self._last_model_used = "local-offline-fallback"
        return self._get_offline_response(prompt)

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response, yielding text chunks.
        """
        if settings.PRIMARY_LLM == "gemini" and self._gemini_client:
            for model_name in _GEMINI_MODELS:
                try:
                    async for token in self._gemini_stream(prompt, model_name):
                        self._last_model_used = model_name
                        yield token
                    return
                except Exception as exc:
                    logger.warning(
                        "Gemini streaming model '%s' failed: %s — trying next", model_name, exc
                    )

        # Fallback to OpenAI streaming
        if self._openai_client:
            for model_name in _OPENAI_MODELS:
                try:
                    async for token in self._openai_stream(prompt, model_name):
                        self._last_model_used = model_name
                        yield token
                    return
                except Exception as exc:
                    logger.warning(
                        "OpenAI streaming model '%s' failed: %s — trying next", model_name, exc
                    )

        # Local Offline Fallback stream
        self._last_model_used = "local-offline-fallback"
        offline_response = self._get_offline_response(prompt)
        
        words = offline_response.split(" ")
        for i in range(0, len(words), 2):
            chunk = " ".join(words[i:i+2]) + " "
            yield chunk
            await asyncio.sleep(0.04)

    def _get_offline_response(self, prompt: str) -> str:
        """Parse prompt to generate a helpful offline response containing the retrieved context."""
        try:
            context_part = ""
            if "CONTEXT DOCUMENTS:" in prompt and "CONVERSATION HISTORY:" in prompt:
                context_part = prompt.split("CONTEXT DOCUMENTS:")[1].split("CONVERSATION HISTORY:")[0].strip()
                
            if context_part and context_part != "[No context documents available]":
                paragraphs = []
                for chunk_text in context_part.split("---"):
                    lines = [line.strip() for line in chunk_text.strip().split("\n") if line.strip()]
                    if len(lines) > 1:
                        header = lines[0]
                        body = "\n".join(lines[1:])
                        
                        source_cite = ""
                        if "Source:" in header:
                            source_cite = header.split("Source:")[1].split("(")[0].strip()
                        else:
                            source_cite = "Document"
                            
                        paragraphs.append(f"• **According to {source_cite}**:\n  \"{body[:350]}...\"")
                
                return (
                    "⚠️ **[Offline/Demo Mode — API Connection Unavailable]**\n\n"
                    "I was unable to connect to the Gemini/OpenAI APIs (please configure a valid `GEMINI_API_KEY` in your `.env` file). "
                    "However, the local RAG pipeline successfully retrieved the following matching information from your documents:\n\n"
                    + "\n\n".join(paragraphs) + "\n\n"
                    "*(Configure a valid Gemini API key to enable full AI answers.)*"
                )
            else:
                return (
                    "⚠️ **[Offline/Demo Mode — API Connection Unavailable]**\n\n"
                    "I was unable to connect to the Gemini/OpenAI APIs. I also could not find any relevant context in your uploaded documents to answer your question.\n\n"
                    "*(Please upload documents first, or configure a valid `GEMINI_API_KEY` in your `.env` file.)*"
                )
        except Exception as exc:
            return (
                "⚠️ **[Offline/Demo Mode — API Connection Unavailable]**\n\n"
                "I was unable to connect to the Gemini/OpenAI APIs. Please check your network connection and configure a valid `GEMINI_API_KEY` in your `.env` file.\n"
                f"*(Error: {exc})*"
            )


    # ------------------------------------------------------------------
    # Gemini implementations
    # ------------------------------------------------------------------

    async def _gemini_generate(self, prompt: str, model_name: str) -> str:
        loop = asyncio.get_event_loop()
        model = self._gemini_client.GenerativeModel(model_name)

        def _sync_call():
            response = model.generate_content(prompt)
            return response.text

        return await loop.run_in_executor(None, _sync_call)

    async def _gemini_stream(self, prompt: str, model_name: str) -> AsyncGenerator[str, None]:
        loop = asyncio.get_event_loop()
        model = self._gemini_client.GenerativeModel(model_name)

        # Gemini streaming is sync; run in executor and yield chunks
        queue: asyncio.Queue = asyncio.Queue()

        def _sync_stream():
            try:
                for chunk in model.generate_content(prompt, stream=True):
                    if chunk.text:
                        loop.call_soon_threadsafe(queue.put_nowait, chunk.text)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _sync_stream)

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    # ------------------------------------------------------------------
    # OpenAI implementations
    # ------------------------------------------------------------------

    async def _openai_generate(self, prompt: str, model_name: str) -> str:
        response = await self._openai_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    async def _openai_stream(self, prompt: str, model_name: str) -> AsyncGenerator[str, None]:
        stream = await self._openai_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
