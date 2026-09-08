"""Tests for LangGraph Corrective-RAG orchestrator and pipeline components."""

import pytest
from unittest.mock import MagicMock, patch

from app.services.langgraph_orchestrator import build_corrective_rag_graph, CorrectiveRAGState
from app.services.langgraph_orchestrator.nodes import classify_and_decompose_node
from app.services.reranker import RerankerService
from app.services.vector_store import SearchResult, QdrantVectorStore


def test_classify_and_decompose_single_query():
    state: CorrectiveRAGState = {"question": "What is our vacation policy?"}
    res = classify_and_decompose_node(state)
    assert res["is_multi_part"] is False
    assert res["sub_queries"] == ["What is our vacation policy?"]


def test_classify_and_decompose_comparison_query():
    state: CorrectiveRAGState = {"question": "Compare Vendor A SLA vs Vendor B SLA"}
    res = classify_and_decompose_node(state)
    assert res["is_multi_part"] is True
    assert len(res["sub_queries"]) >= 1


def test_reranker_fallback_without_cross_encoder():
    reranker = RerankerService(use_cross_encoder=False)
    chunks = [
        SearchResult(text="Vacation policy details", document_id=1, filename="policy.pdf", page_number=1, section="HR", similarity_score=0.7),
        SearchResult(text="Irrelevant text", document_id=2, filename="other.pdf", page_number=2, section="General", similarity_score=0.2),
    ]
    results = reranker.rerank("vacation policy", chunks, top_k=2)
    assert len(results) == 2
    assert results[0].document_id == 1


def test_langgraph_build():
    graph = build_corrective_rag_graph()
    assert graph is not None


@patch("app.services.reranker.RerankerService.rerank")
@patch("app.services.indexing.IndexingService.search")
@patch("app.services.llm.LLMService.generate")
def test_langgraph_execution(mock_generate, mock_search, mock_rerank):
    sample_chunk = SearchResult(
        text="The vacation policy permits 20 annual paid leave days.",
        document_id=101,
        filename="HR_Policy.pdf",
        page_number=3,
        section="Leave Policy",
        similarity_score=0.88,
        chunk_index=0,
    )
    # Mock search & rerank responses
    mock_search.return_value = [sample_chunk]
    mock_rerank.return_value = [sample_chunk]

    # Mock LLM generation response
    mock_resp = MagicMock()
    mock_resp.content = "Employees receive 20 paid leave days annually [1]."
    mock_resp.provider = "test_provider"
    mock_resp.model = "test_model"
    mock_generate.return_value = mock_resp

    graph = build_corrective_rag_graph()
    initial_state: CorrectiveRAGState = {
        "question": "What is the annual paid leave policy?",
        "owner_id": 1,
        "top_k": 5,
        "rewrite_count": 0,
        "generation_count": 0,
        "max_rewrites": 2,
        "max_generations": 2,
    }

    final_state = graph.invoke(initial_state)

    assert final_state["is_grounded"] is True
    assert "20 paid leave days" in final_state["answer"]
    assert len(final_state["citations"]) == 1
    assert final_state["citations"][0]["document"] == "HR_Policy.pdf"
