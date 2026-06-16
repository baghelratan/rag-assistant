"""
Tests for generation components: PromptBuilder, CitationBuilder, HallucinationDetector.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval.vector_store import SearchResult


# ---------------------------------------------------------------------------
# PromptBuilder tests
# ---------------------------------------------------------------------------

class TestPromptBuilder:
    def test_prompt_contains_query(self):
        from app.generation.prompt_builder import PromptBuilder
        pb = PromptBuilder()
        chunks = [
            SearchResult("c1", "d1", "Some relevant text here.", {"source": "doc.pdf", "page": 1}, 0.9),
        ]
        prompt = pb.build_rag_prompt("What is machine learning?", chunks)
        assert "What is machine learning?" in prompt

    def test_prompt_contains_context(self):
        from app.generation.prompt_builder import PromptBuilder
        pb = PromptBuilder()
        chunks = [
            SearchResult("c1", "d1", "Machine learning is a subset of AI.", {"source": "ml.pdf", "page": 1}, 0.9),
        ]
        prompt = pb.build_rag_prompt("What is ML?", chunks)
        assert "Machine learning is a subset of AI." in prompt

    def test_prompt_includes_source_citation(self):
        from app.generation.prompt_builder import PromptBuilder
        pb = PromptBuilder()
        chunks = [
            SearchResult("c1", "d1", "Content here.", {"source": "myfile.pdf", "page": 3}, 0.9),
        ]
        prompt = pb.build_rag_prompt("Query?", chunks)
        assert "myfile.pdf" in prompt

    def test_prompt_includes_history(self):
        from app.generation.prompt_builder import PromptBuilder
        pb = PromptBuilder()
        chunks = []
        history = [
            {"role": "user", "content": "Previous question?"},
            {"role": "assistant", "content": "Previous answer."},
        ]
        prompt = pb.build_rag_prompt("New question?", chunks, history)
        assert "Previous question?" in prompt
        assert "Previous answer." in prompt

    def test_system_prompt_has_injection_guard_language(self):
        from app.generation.prompt_builder import SYSTEM_PROMPT
        # Verify the system prompt contains security instructions
        assert "ignore" in SYSTEM_PROMPT.lower() or "roleplay" in SYSTEM_PROMPT.lower()
        assert "context" in SYSTEM_PROMPT.lower()
        assert "cite" in SYSTEM_PROMPT.lower() or "source" in SYSTEM_PROMPT.lower()

    def test_prompt_empty_context_message(self):
        from app.generation.prompt_builder import PromptBuilder
        pb = PromptBuilder()
        prompt = pb.build_rag_prompt("Query?", [])
        assert "No context" in prompt or "No relevant" in prompt or "available" in prompt.lower()

    def test_prompt_no_context_says_dont_know(self):
        from app.generation.prompt_builder import SYSTEM_PROMPT
        # System prompt should instruct model to say "I don't know" if context insufficient
        assert "don't" in SYSTEM_PROMPT.lower() or "do not" in SYSTEM_PROMPT.lower()
        assert "information" in SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# CitationBuilder tests
# ---------------------------------------------------------------------------

class TestCitationBuilder:
    def test_basic_citations(self):
        from app.generation.citation_builder import CitationBuilder
        cb = CitationBuilder()
        chunks = [
            SearchResult("c1", "d1", "Text from page 1.", {"source": "doc.pdf", "page": 1}, 0.9),
            SearchResult("c2", "d1", "Text from page 2.", {"source": "doc.pdf", "page": 2}, 0.8),
            SearchResult("c3", "d2", "Text from another doc.", {"source": "other.pdf", "page": 1}, 0.7),
        ]
        citations = cb.build_citations(chunks)
        # Should deduplicate by source
        sources = [c.source for c in citations]
        assert len(citations) == 2  # doc.pdf and other.pdf
        assert "doc.pdf" in sources
        assert "other.pdf" in sources

    def test_citation_has_required_fields(self):
        from app.generation.citation_builder import CitationBuilder, Citation
        cb = CitationBuilder()
        chunks = [
            SearchResult("c1", "d1", "Some content.", {"source": "test.pdf", "page": 5}, 0.9),
        ]
        citations = cb.build_citations(chunks)
        assert len(citations) == 1
        c = citations[0]
        assert isinstance(c.id, int)
        assert c.source == "test.pdf"
        assert c.text_snippet != ""

    def test_format_context_with_citations(self):
        from app.generation.citation_builder import CitationBuilder
        cb = CitationBuilder()
        chunks = [
            SearchResult("c1", "d1", "Content A.", {"source": "a.pdf", "page": 1}, 0.9),
            SearchResult("c2", "d2", "Content B.", {"source": "b.pdf", "page": 2}, 0.8),
        ]
        formatted = cb.format_context_with_citations(chunks)
        assert "[1]" in formatted
        assert "[2]" in formatted
        assert "a.pdf" in formatted
        assert "b.pdf" in formatted

    def test_csv_row_citation(self):
        from app.generation.citation_builder import CitationBuilder
        cb = CitationBuilder()
        chunks = [
            SearchResult("c1", "d1", "Row data.", {"source": "data.csv", "row_index": 42}, 0.8),
        ]
        citations = cb.build_citations(chunks)
        assert citations[0].page_or_row == "row 42"

    def test_html_section_citation(self):
        from app.generation.citation_builder import CitationBuilder
        cb = CitationBuilder()
        chunks = [
            SearchResult("c1", "d1", "Section content.", {"source": "page.html", "section": "Introduction"}, 0.8),
        ]
        citations = cb.build_citations(chunks)
        assert "Introduction" in (citations[0].page_or_row or "")


# ---------------------------------------------------------------------------
# HallucinationDetector tests
# ---------------------------------------------------------------------------

class TestHallucinationDetector:
    def _make_embedder(self, texts_to_embeddings=None):
        """Create a mock embedder that returns predictable embeddings."""
        mock_embedder = MagicMock()

        def mock_embed(texts):
            # Return L2-normalized random vectors (deterministic per text)
            result = []
            for text in texts:
                np.random.seed(hash(text) % (2**31))
                v = np.random.rand(384).astype(np.float32)
                v = v / np.linalg.norm(v)
                result.append(v)
            return np.array(result)

        mock_embedder.embed.side_effect = mock_embed
        mock_embedder.embed_query.side_effect = lambda t: mock_embed([t])[0]
        return mock_embedder

    def test_supported_response_not_hallucination(self):
        from app.generation.hallucination import HallucinationDetector

        embedder = MagicMock()
        # Simulate high similarity (same embeddings → score = 1.0)
        v = np.ones(384, dtype=np.float32)
        v = v / np.linalg.norm(v)
        embedder.embed.return_value = np.tile(v, (10, 1))

        detector = HallucinationDetector(embedder)
        result = detector.check(
            response="Machine learning is used for classification.",
            context_chunks=["Machine learning algorithms are applied to classification tasks."],
        )
        assert result.score > 0.0  # some supported sentences

    def test_no_context_is_hallucination(self):
        from app.generation.hallucination import HallucinationDetector

        embedder = MagicMock()
        detector = HallucinationDetector(embedder)
        result = detector.check(
            response="The sky is made of cheese.",
            context_chunks=[],
        )
        assert result.is_hallucination is True
        assert result.score == 0.0

    def test_empty_response_not_flagged(self):
        from app.generation.hallucination import HallucinationDetector

        embedder = MagicMock()
        detector = HallucinationDetector(embedder)
        result = detector.check(response="", context_chunks=["Some context."])
        assert result.is_hallucination is False
        assert result.score == 1.0

    def test_result_has_required_fields(self):
        from app.generation.hallucination import HallucinationDetector, HallucinationResult

        embedder = MagicMock()
        v = np.random.rand(384).astype(np.float32)
        v /= np.linalg.norm(v)
        embedder.embed.return_value = np.tile(v, (6, 1))

        detector = HallucinationDetector(embedder)
        result = detector.check(
            response="This is a test sentence. Another sentence here.",
            context_chunks=["Context sentence one. Context sentence two."],
        )
        assert isinstance(result, HallucinationResult)
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.is_hallucination, bool)
        assert isinstance(result.flagged_sentences, list)
