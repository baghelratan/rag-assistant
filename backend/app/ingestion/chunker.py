"""
Document chunking strategies.
Provides RecursiveCharacterChunker, SemanticChunker, and a unified Chunker class.
"""

import re
import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a single text chunk from a document."""
    text: str
    chunk_id: str
    doc_id: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.chunk_id:
            self.chunk_id = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# RecursiveCharacterChunker
# ---------------------------------------------------------------------------

class RecursiveCharacterChunker:
    """
    Splits text recursively on a priority list of separators.
    Falls back to smaller separators when chunks are still too large.
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " "]

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or self.DEFAULT_SEPARATORS

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text using the separator list."""
        if not separators:
            # No more separators: force-split by characters
            return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

        sep = separators[0]
        remaining_seps = separators[1:]
        parts = text.split(sep)

        chunks: List[str] = []
        current = ""

        for part in parts:
            candidate = (current + sep + part) if current else part

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                # Part itself might be too large — recurse
                if len(part) > self.chunk_size:
                    sub_chunks = self._split_text(part, remaining_seps)
                    chunks.extend(sub_chunks)
                    current = ""
                else:
                    current = part

        if current.strip():
            chunks.append(current.strip())

        return [c for c in chunks if c]

    def chunk(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        raw_chunks = self._split_text(text, self.separators)
        if self.chunk_overlap <= 0:
            return raw_chunks

        # Apply overlap
        overlapped: List[str] = []
        for i, chunk in enumerate(raw_chunks):
            if i == 0 or self.chunk_overlap == 0:
                overlapped.append(chunk)
            else:
                prev = raw_chunks[i - 1]
                # Take the tail of previous chunk
                tail = prev[-self.chunk_overlap :] if len(prev) > self.chunk_overlap else prev
                overlapped.append((tail + " " + chunk).strip())
        return overlapped


# ---------------------------------------------------------------------------
# SemanticChunker
# ---------------------------------------------------------------------------

class SemanticChunker:
    """
    Groups sentences into chunks based on chunk_size.
    Respects sentence boundaries to keep semantic coherence.
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Basic sentence tokenizer using regex
        sentence_pattern = re.compile(r"(?<=[.!?])\s+")
        sentences = sentence_pattern.split(text.strip())
        # Further clean
        return [s.strip() for s in sentences if s.strip()]

    def chunk(self, text: str) -> List[str]:
        """Group sentences into chunks up to chunk_size characters."""
        sentences = self._split_sentences(text)
        chunks: List[str] = []
        current_sentences: List[str] = []
        current_len = 0

        for sentence in sentences:
            slen = len(sentence)
            if current_len + slen + 1 > self.chunk_size and current_sentences:
                chunks.append(" ".join(current_sentences))
                # Overlap: keep last N chars worth of sentences
                overlap_sentences: List[str] = []
                overlap_len = 0
                for s in reversed(current_sentences):
                    if overlap_len + len(s) <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_len += len(s)
                    else:
                        break
                current_sentences = overlap_sentences + [sentence]
                current_len = sum(len(s) for s in current_sentences)
            else:
                current_sentences.append(sentence)
                current_len += slen + 1

        if current_sentences:
            chunks.append(" ".join(current_sentences))

        return chunks


# ---------------------------------------------------------------------------
# Unified Chunker
# ---------------------------------------------------------------------------

class Chunker:
    """
    Selects chunking strategy based on document type and converts raw text
    records into typed Chunk objects.
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self._recursive = RecursiveCharacterChunker(chunk_size, chunk_overlap)
        self._semantic = SemanticChunker(chunk_size, chunk_overlap)

    def _get_strategy(self, doc_type: str):
        """Return chunker for a given document type."""
        if doc_type in ("html", "text", "md"):
            return self._semantic
        # PDF and CSV → recursive (better for structured/mixed content)
        return self._recursive

    def chunk_records(
        self,
        records: List[Dict[str, Any]],
        doc_id: str,
        doc_type: str = "pdf",
    ) -> List[Chunk]:
        """
        Convert a list of parsed records into Chunk objects.

        Args:
            records: Output from any parser (list of dicts with 'text' key).
            doc_id: Unique document identifier.
            doc_type: One of 'pdf', 'html', 'csv', 'text', 'md'.

        Returns:
            List of Chunk dataclass instances.
        """
        strategy = self._get_strategy(doc_type)
        chunks: List[Chunk] = []

        for record in records:
            text = record.get("text", "")
            if not text or not text.strip():
                continue

            # Build base metadata from record (exclude 'text')
            base_meta = {k: v for k, v in record.items() if k != "text"}
            base_meta["doc_type"] = doc_type

            sub_texts = strategy.chunk(text)
            for i, sub_text in enumerate(sub_texts):
                if not sub_text.strip():
                    continue
                chunk_id = str(uuid.uuid4())
                meta = dict(base_meta)
                meta["sub_index"] = i
                meta["total_sub_chunks"] = len(sub_texts)

                chunks.append(
                    Chunk(
                        text=sub_text.strip(),
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        source=record.get("source", doc_id),
                        metadata=meta,
                    )
                )

        logger.info(
            "Chunked doc '%s' (%s): %d records → %d chunks",
            doc_id, doc_type, len(records), len(chunks),
        )
        return chunks
