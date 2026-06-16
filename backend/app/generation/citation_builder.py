"""
Citation builder: converts SearchResult objects into structured Citation objects.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from app.retrieval.vector_store import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """A single source citation."""
    id: int
    source: str
    page_or_row: Optional[str]
    text_snippet: str
    url: Optional[str] = None
    doc_id: Optional[str] = None


class CitationBuilder:
    """
    Builds structured Citation objects from retrieval results.
    Deduplicates by source file.
    """

    def build_citations(self, chunks: List[SearchResult]) -> List[Citation]:
        """
        Build a list of deduplicated citations.

        Args:
            chunks: Retrieved and re-ranked SearchResult objects.

        Returns:
            List of Citation objects (deduplicated by source).
        """
        seen_sources: Dict[str, int] = {}
        citations: List[Citation] = []
        citation_id = 1

        for chunk in chunks:
            source = chunk.metadata.get("source", chunk.doc_id or "Unknown")

            # Page or row reference
            if "page" in chunk.metadata:
                page_or_row = f"page {chunk.metadata['page']}"
            elif "row_index" in chunk.metadata:
                page_or_row = f"row {chunk.metadata['row_index']}"
            elif "section" in chunk.metadata:
                page_or_row = f"section: {chunk.metadata['section']}"
            else:
                page_or_row = None

            url = chunk.metadata.get("url") or None
            snippet = chunk.text[:200].replace("\n", " ").strip()
            if len(chunk.text) > 200:
                snippet += "…"

            if source not in seen_sources:
                seen_sources[source] = citation_id
                citations.append(
                    Citation(
                        id=citation_id,
                        source=source,
                        page_or_row=page_or_row,
                        text_snippet=snippet,
                        url=url,
                        doc_id=chunk.doc_id,
                    )
                )
                citation_id += 1
            # If same source, optionally update page info for first occurrence
            else:
                existing_id = seen_sources[source]
                existing_cit = next(c for c in citations if c.id == existing_id)
                if existing_cit.page_or_row is None and page_or_row:
                    existing_cit.page_or_row = page_or_row

        return citations

    def format_context_with_citations(self, chunks: List[SearchResult]) -> str:
        """
        Format context blocks with numbered citation markers.

        Args:
            chunks: Retrieved SearchResult objects.

        Returns:
            Formatted string with numbered context sections.
        """
        if not chunks:
            return "No context available."

        sections = []
        for i, chunk in enumerate(chunks, start=1):
            source = chunk.metadata.get("source", chunk.doc_id or "Unknown")
            page_or_row = ""

            if "page" in chunk.metadata:
                page_or_row = f" | Page {chunk.metadata['page']}"
            elif "row_index" in chunk.metadata:
                page_or_row = f" | Row {chunk.metadata['row_index']}"
            elif "section" in chunk.metadata:
                page_or_row = f" | Section: {chunk.metadata['section']}"

            header = f"[{i}] {source}{page_or_row}"
            sections.append(f"{header}\n{chunk.text}")

        return "\n\n".join(sections)
