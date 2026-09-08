"""State definition for LangGraph Corrective-RAG orchestrator."""

from __future__ import annotations

from typing import Any, TypedDict
from app.services.vector_store import SearchResult


class CorrectiveRAGState(TypedDict, total=False):
    """Execution state passed between nodes in the Corrective-RAG graph."""

    # Input parameters
    question: str
    owner_id: int | None
    document_ids: list[int] | None
    org_id: int | None
    top_k: int
    chat_history: list[dict[str, str]] | None
    compare_mode: bool
    indexing_service: Any
    llm_service: Any
    reranker_service: Any
    context_validator: Any

    # Query decomposition state
    is_multi_part: bool
    sub_queries: list[str]

    # Retrieval & Reranking state
    retrieved_chunks: list[SearchResult]
    graded_chunks: list[SearchResult]
    context_text: str

    # Control loop counters (hard bounds)
    rewrite_count: int
    generation_count: int
    max_rewrites: int
    max_generations: int

    # Output state
    answer: str
    citations: list[dict[str, Any]]
    insufficient_information: bool
    is_grounded: bool
    llm_provider: str
    llm_model: str
