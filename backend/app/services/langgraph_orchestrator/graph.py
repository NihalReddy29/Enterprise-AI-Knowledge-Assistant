"""LangGraph StateGraph builder for Corrective-RAG orchestrator."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.services.context_validator import REFUSAL_MESSAGE
from app.services.langgraph_orchestrator.nodes import (
    classify_and_decompose_node,
    generate_citations_node,
    rerank_and_grade_node,
    retrieve_hybrid_node,
    rewrite_query_node,
    verify_citations_node,
)
from app.services.langgraph_orchestrator.state import CorrectiveRAGState

logger = logging.getLogger(__name__)


def insufficient_info_fallback_node(state: CorrectiveRAGState) -> dict[str, Any]:
    """Fallback node when retrieval grading fails after max rewrites."""
    return {
        "answer": REFUSAL_MESSAGE,
        "citations": [],
        "insufficient_information": True,
        "is_grounded": False,
    }


def route_after_grade(state: CorrectiveRAGState) -> str:
    """Conditional edge after document grading."""
    graded = state.get("graded_chunks", [])
    retrieved = state.get("retrieved_chunks", [])
    rewrite_count = state.get("rewrite_count", 0)
    max_rewrites = state.get("max_rewrites", 2)

    if graded and len(graded) > 0:
        return "generate_citations"
    elif not retrieved:
        # If vector search returned 0 candidates, index is empty or doc not found; do not call rewrite LLM
        return "insufficient_info_fallback"
    elif rewrite_count < max_rewrites:
        return "rewrite_query"
    else:
        return "insufficient_info_fallback"


def route_after_verify(state: CorrectiveRAGState) -> str:
    """Conditional edge after citation verification."""
    is_grounded = state.get("is_grounded", False)
    generation_count = state.get("generation_count", 0)
    max_generations = state.get("max_generations", 2)

    if is_grounded:
        return END
    elif generation_count < max_generations:
        return "generate_citations"
    else:
        return "insufficient_info_fallback"


def build_corrective_rag_graph():
    """Construct and compile the deterministic Corrective-RAG StateGraph."""
    workflow = StateGraph(CorrectiveRAGState)

    # Add Nodes
    workflow.add_node("classify_and_decompose", classify_and_decompose_node)
    workflow.add_node("retrieve_hybrid", retrieve_hybrid_node)
    workflow.add_node("rerank_and_grade", rerank_and_grade_node)
    workflow.add_node("rewrite_query", rewrite_query_node)
    workflow.add_node("generate_citations", generate_citations_node)
    workflow.add_node("verify_citations", verify_citations_node)
    workflow.add_node("insufficient_info_fallback", insufficient_info_fallback_node)

    # Set Edges
    workflow.add_edge(START, "classify_and_decompose")
    workflow.add_edge("classify_and_decompose", "retrieve_hybrid")
    workflow.add_edge("retrieve_hybrid", "rerank_and_grade")

    # Conditional branch after grading
    workflow.add_conditional_edges(
        "rerank_and_grade",
        route_after_grade,
        {
            "generate_citations": "generate_citations",
            "rewrite_query": "rewrite_query",
            "insufficient_info_fallback": "insufficient_info_fallback",
        },
    )

    # Loop back from rewrite to retrieve
    workflow.add_edge("rewrite_query", "retrieve_hybrid")

    # Generation & verification flow
    workflow.add_edge("generate_citations", "verify_citations")
    workflow.add_conditional_edges(
        "verify_citations",
        route_after_verify,
        {
            END: END,
            "generate_citations": "generate_citations",
            "insufficient_info_fallback": "insufficient_info_fallback",
        },
    )
    workflow.add_edge("insufficient_info_fallback", END)

    return workflow.compile()
