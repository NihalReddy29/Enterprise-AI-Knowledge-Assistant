"""Hybrid & Cross-Encoder Reranker Service combining neural attention, semantic vector similarity, and BM25 lexical matching."""

import logging
import re
from typing import Sequence

from app.config import get_settings
from app.services.vector_store import SearchResult

logger = logging.getLogger(__name__)
settings = get_settings()


class RerankerService:
    """Reranks vector search candidates using a Neural CrossEncoder or hybrid multi-signal scoring algorithm."""

    def __init__(
        self,
        use_cross_encoder: bool = False,
        model_name: str = "BAAI/bge-reranker-base",
        semantic_weight: float = 0.6,
        lexical_weight: float = 0.3,
        title_section_weight: float = 0.1,
    ) -> None:
        self.use_cross_encoder = use_cross_encoder
        self.model_name = model_name
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight
        self.title_section_weight = title_section_weight
        self._cross_encoder = None
        self._cross_encoder_failed = False

    def _get_cross_encoder(self):
        if not self.use_cross_encoder or self._cross_encoder_failed:
            return None
        if self._cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder

                logger.info("Loading CrossEncoder model: %s", self.model_name)
                self._cross_encoder = CrossEncoder(self.model_name)
            except Exception as e:
                logger.warning("Could not load CrossEncoder model '%s': %s. Falling back to hybrid scoring.", self.model_name, e)
                self._cross_encoder_failed = True
                return None
        return self._cross_encoder

    def rerank(
        self,
        query: str,
        chunks: Sequence[SearchResult],
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """Rerank a pool of 10-20 candidate chunks down to top_k (default 3-5)."""
        k = top_k or settings.rerank_top_k
        if not chunks:
            return []

        # Deduplicate candidates first
        unique_chunks: list[SearchResult] = []
        seen: set[tuple[int, int | None, str]] = set()
        for chunk in chunks:
            identity = (chunk.document_id, chunk.chunk_index, chunk.text.strip())
            if identity not in seen:
                seen.add(identity)
                unique_chunks.append(chunk)

        # Attempt CrossEncoder reranking
        cross_encoder = self._get_cross_encoder()
        if cross_encoder is not None and len(unique_chunks) > 0:
            try:
                pairs = [[query, chunk.text] for chunk in unique_chunks]
                scores = cross_encoder.predict(pairs)
                scored_chunks = []
                for chunk, score in zip(unique_chunks, scores):
                    # Sigmoid or float norm score
                    score_val = float(score)
                    updated_chunk = SearchResult(
                        text=chunk.text,
                        document_id=chunk.document_id,
                        filename=chunk.filename,
                        page_number=chunk.page_number,
                        section=chunk.section,
                        similarity_score=round(score_val, 6),
                        chunk_index=chunk.chunk_index,
                        metadata=chunk.metadata,
                    )
                    scored_chunks.append((score_val, updated_chunk))
                scored_chunks.sort(key=lambda x: x[0], reverse=True)
                return [c for _, c in scored_chunks[:k]]
            except Exception as exc:
                logger.warning("CrossEncoder rerank failed (%s). Falling back to hybrid score.", exc)

        # Fallback to Hybrid Scoring (BM25 + Semantic Vector + Title match)
        query_terms = self._tokenize(query)
        if not query_terms:
            sorted_chunks = sorted(unique_chunks, key=lambda c: c.similarity_score, reverse=True)
            return sorted_chunks[:k]

        scored: list[tuple[float, SearchResult]] = []
        for chunk in unique_chunks:
            sem_score = max(0.0, float(chunk.similarity_score))
            lex_score = self._compute_lexical_score(query_terms, chunk.text)
            title_score = self._compute_title_section_score(query_terms, chunk.filename, chunk.section)

            hybrid_score = (
                self.semantic_weight * sem_score
                + self.lexical_weight * lex_score
                + self.title_section_weight * title_score
            )

            updated_chunk = SearchResult(
                text=chunk.text,
                document_id=chunk.document_id,
                filename=chunk.filename,
                page_number=chunk.page_number,
                section=chunk.section,
                similarity_score=round(hybrid_score, 6),
                chunk_index=chunk.chunk_index,
                metadata=chunk.metadata,
            )
            scored.append((hybrid_score, updated_chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:k]]

    def _compute_lexical_score(self, query_terms: set[str], text: str) -> float:
        """Compute BM25-style term frequency overlap score normalized between 0.0 and 1.0."""
        text_terms = self._tokenize(text)
        if not text_terms or not query_terms:
            return 0.0

        matched_terms = query_terms.intersection(text_terms)
        if not matched_terms:
            return 0.0

        overlap = len(matched_terms) / len(query_terms)
        tf_sum = 0.0
        text_lower = text.lower()
        for term in matched_terms:
            freq = text_lower.count(term)
            tf_sum += (freq * 2.0) / (freq + 1.0)

        raw_score = overlap * 0.6 + min(1.0, tf_sum / (len(query_terms) * 1.5)) * 0.4
        return min(1.0, max(0.0, raw_score))

    def _compute_title_section_score(
        self, query_terms: set[str], filename: str | None, section: str | None
    ) -> float:
        """Compute match score for document filename or section title."""
        target_text = f"{filename or ''} {section or ''}".lower().strip()
        if not target_text or not query_terms:
            return 0.0

        target_terms = self._tokenize(target_text)
        matches = query_terms.intersection(target_terms)
        if not matches:
            return 0.0

        return len(matches) / len(query_terms)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        words = re.findall(r"\w+", text.lower())
        stopwords = {
            "a", "an", "the", "in", "on", "at", "to", "for", "of", "with",
            "and", "or", "is", "are", "was", "were", "be", "been", "this",
            "that", "it", "what", "how", "why", "where", "which", "who"
        }
        return {w for w in words if w not in stopwords and len(w) > 1}


def get_reranker_service() -> RerankerService:
    """Factory for RerankerService."""
    return RerankerService()

