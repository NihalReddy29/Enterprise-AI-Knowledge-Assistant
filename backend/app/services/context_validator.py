"""Grounding checks used before and after RAG answer generation."""

from __future__ import annotations

import re

from app.config import get_settings
from app.services.vector_store import SearchResult

REFUSAL_MESSAGE = (
    "I don't have enough information in the uploaded documents to answer this question."
)


class ContextValidator:
    """Validate retrieved context and generated answers without another LLM call."""

    def __init__(
        self,
        min_score: float | None = None,
        min_grounding_ratio: float | None = None,
    ) -> None:
        settings = get_settings()
        self.min_score = settings.context_min_score if min_score is None else min_score
        self.min_grounding_ratio = (
            settings.context_min_grounding_ratio
            if min_grounding_ratio is None
            else min_grounding_ratio
        )

    def validate_context(
        self, query: str, chunks: list[SearchResult]
    ) -> tuple[bool, str]:
        """Return formatted context only when at least one relevant, usable chunk exists.

        Accuracy fix: replaced hard term-overlap rejection with a soft check.
        The old approach required exact token overlap between query and context,
        which fails when the user uses synonyms or different phrasing from the document.
        Now we only refuse if there are genuinely zero usable chunks.
        The similarity score threshold (context_min_score) serves as the quality gate.
        """
        if not query.strip() or not chunks:
            return False, REFUSAL_MESSAGE

        valid_chunks = self.usable_chunks(chunks)
        if not valid_chunks:
            return False, REFUSAL_MESSAGE

        return True, self.format_context(valid_chunks)

    def usable_chunks(self, chunks: list[SearchResult]) -> list[SearchResult]:
        """Return chunks safe to include in a validated prompt and its citations."""
        return [
            chunk
            for chunk in chunks
            if chunk.text
            and chunk.text.strip()
            and chunk.similarity_score >= self.min_score
        ]

    def validate_answer(
        self, answer: str, chunks: list[SearchResult]
    ) -> tuple[str, bool]:
        """Reject empty, explicit-refusal, or ungrounded answers.

        Uses a soft term-overlap ratio (not exact/binary match) so paraphrased
        or synonym-heavy correct answers still pass, while answers that aren't
        actually about the retrieved content get caught.
        """
        cleaned = answer.strip()
        if not cleaned or self._is_refusal(cleaned) or not chunks:
            return REFUSAL_MESSAGE, False

        context_terms: set[str] = set()
        for chunk in chunks:
            context_terms |= self._terms(chunk.text)

        answer_terms = self._terms(cleaned)
        if not answer_terms:
            return REFUSAL_MESSAGE, False

        overlap_ratio = len(answer_terms & context_terms) / len(answer_terms)
        if overlap_ratio < self.min_grounding_ratio:
            return REFUSAL_MESSAGE, False

        return cleaned, True

    @staticmethod
    def format_context(chunks: list[SearchResult]) -> str:
        blocks: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            location_parts = []
            if chunk.page_number is not None:
                location_parts.append(f"Page {chunk.page_number}")
            if chunk.section:
                location_parts.append(f"Section {chunk.section}")
            location = ", ".join(location_parts) if location_parts else "Unknown location"
            blocks.append(f"[{index}] {chunk.filename or 'document'} ({location})\n{chunk.text}")
        return "\n\n".join(blocks)

    @staticmethod
    def _is_refusal(answer: str) -> bool:
        normalized = answer.lower()
        return any(
            marker in normalized
            for marker in (
                "i don't have enough information",
                "i do not have enough information",
                "don't have enough information",
                "no relevant information",
            )
        )

    @staticmethod
    def _terms(text: str) -> set[str]:
        stopwords = {
            "a", "an", "and", "are", "at", "be", "for", "from", "how", "i",
            "in", "is", "it", "of", "on", "or", "the", "this", "to", "what",
            "when", "where", "which", "who", "with", "why", "you",
        }
        return {
            term
            for term in re.findall(r"[\w-]+", text.lower())
            if len(term) > 1 and term not in stopwords
        }
