"""Node functions for LangGraph Corrective-RAG orchestrator."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import get_settings
from app.services.context_validator import ContextValidator, REFUSAL_MESSAGE
from app.services.indexing import get_indexing_service
from app.services.llm import get_llm_service
from app.services.query_processor import preprocess_query
from app.services.reranker import get_reranker_service
from app.services.vector_store import SearchResult
from app.services.langgraph_orchestrator.state import CorrectiveRAGState

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are an enterprise knowledge assistant. You ONLY answer questions using the document context provided below.

Rules:
- Base your answer EXCLUSIVELY on the provided document context. Do NOT use general knowledge or training data.
- Always cite which document(s) you used (e.g., [1], [2]).
- Write clear, complete, accurate answers using full sentences.
- If the provided context does not contain enough information to answer the question, say exactly: "I don't have enough information in the uploaded documents to answer this question." Do NOT guess or use outside knowledge.
- Never say things like "based on general knowledge" or answer as if you were a search engine.
- When the answer spans multiple documents, summarize each document's perspective.
- Avoid repetition. Be concise but thorough.
- Formatting: use Markdown (headers, bullet lists, bold, tables) for structure. Do NOT use LaTeX math notation (no $...$ or $$...$$). Write formulas and equations as plain text instead, using standard math operators and parentheses — for example, write "Speedup(N) = 1 / ((1 - P) + (P / N))" rather than a LaTeX expression. Wrap variable names (like `P`, `N`) in backticks as inline code."""

def classify_and_decompose_node(state: CorrectiveRAGState) -> dict[str, Any]:
    """Identify if query requires multi-hop decomposition (narrow classifier node)."""
    question = state.get("question", "")
    processed = preprocess_query(question)

    comparison_keywords = {"compare", "vs", "versus", "difference", "differences", "contrast", "both", "all"}
    multi_part = any(kw in processed.lower() for kw in comparison_keywords) or len(processed.split(" and ")) > 1

    sub_queries = [processed]
    if multi_part:
        # Split simple conjunctions into sub-queries if present
        parts = [p.strip() for p in re.split(r"\b(and|vs|versus|compared to)\b", processed, flags=re.IGNORECASE) if len(p.strip()) > 3]
        if len(parts) > 1:
            sub_queries = [p for p in parts if p.lower() not in {"and", "vs", "versus", "compared to"}]

    return {
        "is_multi_part": multi_part,
        "sub_queries": sub_queries,
        "rewrite_count": state.get("rewrite_count", 0),
        "generation_count": state.get("generation_count", 0),
        "max_rewrites": state.get("max_rewrites", 2),
        "max_generations": state.get("max_generations", 2),
    }


def retrieve_hybrid_node(state: CorrectiveRAGState) -> dict[str, Any]:
    """Execute dense vector + sparse keyword search across sub-queries."""
    indexing = state.get("indexing_service") or get_indexing_service()
    sub_queries = state.get("sub_queries") or [state.get("question", "")]
    owner_id = state.get("owner_id")
    document_ids = state.get("document_ids")
    org_id = state.get("org_id")
    top_k = state.get("top_k", settings.vector_search_top_k)

    all_candidates: list[SearchResult] = []
    seen: set[tuple[int, int | None, str]] = set()

    for q in sub_queries:
        candidates = indexing.search(
            query=q,
            top_k=max(10, min(20, top_k)),
            owner_id=owner_id,
            document_ids=document_ids,
            org_id=org_id,
        )
        for c in candidates:
            identity = (c.document_id, c.chunk_index, c.text.strip())
            if identity not in seen:
                seen.add(identity)
                all_candidates.append(c)

    return {"retrieved_chunks": all_candidates}


def rerank_and_grade_node(state: CorrectiveRAGState) -> dict[str, Any]:
    """Run neural cross-encoder reranking and grade document relevance."""
    reranker = state.get("reranker_service") or get_reranker_service()
    validator = state.get("context_validator") or ContextValidator()
    question = state.get("question", "")
    retrieved = state.get("retrieved_chunks", [])
    rerank_k = state.get("rerank_top_k", settings.rerank_top_k)

    reranked = reranker.rerank(query=question, chunks=retrieved, top_k=rerank_k)
    usable = validator.usable_chunks(reranked)

    # Only mark insufficient when there are truly zero usable chunks.
    # The validate_context term-overlap check was too aggressive and caused
    # false refusals when the LLM uses different phrasing than the document.
    # Now we trust the embedding similarity score and cross-encoder reranking
    # to have already surfaced the most relevant chunks — just verify not empty.
    if not usable:
        return {
            "graded_chunks": [],
            "context_text": "",
            "insufficient_information": True,
        }

    context_text = validator.format_context(usable)
    return {
        "graded_chunks": usable,
        "context_text": context_text,
        "insufficient_information": False,
    }


def rewrite_query_node(state: CorrectiveRAGState) -> dict[str, Any]:
    """Rewrite query to optimize keyword search when context grading fails."""
    llm = state.get("llm_service") or get_llm_service()
    current_q = state.get("question", "")
    rewrite_count = state.get("rewrite_count", 0) + 1

    prompt = (
        f"The following user question failed to retrieve relevant documents from our enterprise knowledge base:\n"
        f"Question: \"{current_q}\"\n\n"
        f"Formulate a better, expanded search query focusing on key technical/business terms and synonyms. "
        f"Return ONLY the rewritten search query, nothing else."
    )
    try:
        resp = llm.generate(system_prompt="You are a search query optimizer.", user_prompt=prompt)
        rewritten = resp.content.strip()
        if not rewritten:
            rewritten = current_q
    except Exception as exc:
        logger.warning("Query rewrite LLM call failed: %s", exc)
        rewritten = current_q

    return {
        "question": rewritten,
        "sub_queries": [rewritten],
        "rewrite_count": rewrite_count,
    }


def generate_citations_node(state: CorrectiveRAGState) -> dict[str, Any]:
    """Generate LLM answer with source citations."""
    llm = state.get("llm_service") or get_llm_service()
    question = state.get("question", "")
    context_text = state.get("context_text", "")
    chat_history = state.get("chat_history")
    compare_mode = state.get("compare_mode", False)
    generation_count = state.get("generation_count", 0) + 1
    chunks = state.get("graded_chunks", [])

    history_block = ""
    if chat_history:
        lines = []
        for msg in chat_history[-settings.rag_history_turns :]:
            lines.append(f"{msg.get('role', 'user')}: {msg.get('content', '')}")
        history_block = "Chat History:\n" + "\n".join(lines) + "\n\n"

    compare_instruction = ""
    if compare_mode:
        compare_instruction = "\nIf multiple documents are present in context, compare them in a markdown table.\n"

    user_prompt = (
        f"{history_block}"
        f"Context:\n{context_text}\n\n"
        f"Question:\n{question}"
        f"{compare_instruction}"
    )

    try:
        llm_resp = llm.generate(SYSTEM_PROMPT, user_prompt)
        answer = llm_resp.content.strip()
        provider = llm_resp.provider
        model = llm_resp.model
    except Exception as e:
        logger.error("LLM generation node failed: %s", e)
        answer = REFUSAL_MESSAGE
        provider = llm.provider_name
        model = llm.model_name

    # Construct citations structure
    citations = []
    for idx, c in enumerate(chunks, start=1):
        citations.append({
            "index": idx,
            "document": c.filename,
            "document_id": c.document_id,
            "page_number": c.page_number,
            "section": c.section,
            "text": c.text[:500],
            "similarity_score": c.similarity_score,
        })

    return {
        "answer": answer,
        "citations": citations,
        "generation_count": generation_count,
        "llm_provider": provider,
        "llm_model": model,
    }


def verify_citations_node(state: CorrectiveRAGState) -> dict[str, Any]:
    """Verify citations and validate answer grounding against context."""
    validator = state.get("context_validator") or ContextValidator()
    answer = state.get("answer", "")
    chunks = state.get("graded_chunks", [])

    cleaned, answer_is_grounded = validator.validate_answer(answer, chunks)
    if not answer_is_grounded:
        return {
            "answer": REFUSAL_MESSAGE,
            "citations": [],
            "is_grounded": False,
            "insufficient_information": True,
        }

    # Verify citation tag consistency (e.g. [1], [2])
    citation_tags = re.findall(r"\[(\d+)\]", cleaned)
    max_idx = len(chunks)
    valid_tags = [int(tag) for tag in citation_tags if 1 <= int(tag) <= max_idx]

    return {
        "answer": cleaned,
        "is_grounded": True,
        "insufficient_information": False,
    }
