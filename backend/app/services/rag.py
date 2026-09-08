"""RAG pipeline: retrieve context, prompt LLM, generate citations."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Generator

from app.config import get_settings
from app.services.context_validator import ContextValidator, REFUSAL_MESSAGE
from app.services.indexing import IndexingService, get_indexing_service
from app.services.llm import LLMService, get_llm_service
from app.services.query_processor import preprocess_query
from app.services.reranker import RerankerService, get_reranker_service
from app.services.vector_store import SearchResult

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
- Avoid repetition. Be concise but thorough."""


@dataclass
class Citation:
    """Source citation for an answer."""

    index: int
    document: str | None
    document_id: int
    page_number: int | None = None
    section: str | None = None
    text: str = ""
    similarity_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RAGResult:
    """Complete RAG answer with sources."""

    answer: str
    citations: list[Citation] = field(default_factory=list)
    retrieved_chunks: list[dict] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    insufficient_information: bool = False


class RAGService:
    """Retrieval Augmented Generation orchestrator."""

    def __init__(
        self,
        indexing: IndexingService | None = None,
        llm: LLMService | None = None,
        reranker: RerankerService | None = None,
        context_validator: ContextValidator | None = None,
    ) -> None:
        self.indexing = indexing or get_indexing_service()
        self.llm = llm or get_llm_service()
        self.reranker = reranker or get_reranker_service()
        self.context_validator = context_validator or ContextValidator()

    # ------------------------------------------------------------------
    # Standard (non-streaming) path
    # ------------------------------------------------------------------

    def ask(
        self,
        question: str,
        owner_id: int | None = None,
        document_ids: list[int] | None = None,
        top_k: int | None = None,
        chat_history: list[dict[str, str]] | None = None,
        compare_mode: bool = False,
        org_id: int | None = None,
    ) -> RAGResult:
        """Run the full RAG pipeline via LangGraph Corrective-RAG orchestrator."""
        from app.services.langgraph_orchestrator import build_corrective_rag_graph

        initial_state = {
            "question": question,
            "owner_id": owner_id,
            "document_ids": document_ids,
            "top_k": top_k or settings.vector_search_top_k,
            "chat_history": chat_history,
            "compare_mode": compare_mode,
            "org_id": org_id,
            "rewrite_count": 0,
            "generation_count": 0,
            "max_rewrites": 2,
            "max_generations": 2,
            "indexing_service": self.indexing,
            "llm_service": self.llm,
            "reranker_service": self.reranker,
            "context_validator": self.context_validator,
        }

        graph = build_corrective_rag_graph()
        final_state = graph.invoke(initial_state)

        answer = final_state.get("answer", REFUSAL_MESSAGE)
        raw_citations = final_state.get("citations", [])
        citations = [
            Citation(
                index=c["index"],
                document=c.get("document"),
                document_id=c.get("document_id", 0),
                page_number=c.get("page_number"),
                section=c.get("section"),
                text=c.get("text", ""),
                similarity_score=c.get("similarity_score", 0.0),
            )
            for c in raw_citations
        ]
        retrieved_chunks = [c.to_dict() for c in final_state.get("graded_chunks", []) or final_state.get("retrieved_chunks", [])]

        return RAGResult(
            answer=answer,
            citations=citations,
            retrieved_chunks=retrieved_chunks,
            provider=final_state.get("llm_provider", self.llm.provider_name),
            model=final_state.get("llm_model", self.llm.model_name),
            insufficient_information=final_state.get("insufficient_information", False),
        )

    # ------------------------------------------------------------------
    # Streaming path
    # ------------------------------------------------------------------

    def ask_stream(
        self,
        question: str,
        owner_id: int | None = None,
        document_ids: list[int] | None = None,
        top_k: int | None = None,
        chat_history: list[dict[str, str]] | None = None,
        compare_mode: bool = False,
        org_id: int | None = None,
    ) -> Generator[str, None, dict]:
        """Yield SSE-formatted tokens using LangGraph Corrective-RAG pipeline.

        Emits text tokens as: ``data: <json>\\n\\n``
        Final sentinel:       ``data: [DONE] <json>\\n\\n``
        """
        # Run the full Corrective-RAG graph (same as non-streaming ask())
        # but stream the final generation step for perceived responsiveness.
        from app.services.langgraph_orchestrator import build_corrective_rag_graph

        initial_state = {
            "question": question,
            "owner_id": owner_id,
            "document_ids": document_ids,
            "top_k": top_k or settings.vector_search_top_k,
            "chat_history": chat_history,
            "compare_mode": compare_mode,
            "org_id": org_id,
            "rewrite_count": 0,
            "generation_count": 0,
            "max_rewrites": 2,
            "max_generations": 2,
            "indexing_service": self.indexing,
            "llm_service": self.llm,
            "reranker_service": self.reranker,
            "context_validator": self.context_validator,
        }

        # Run retrieval + grading stages synchronously via graph
        # then stream the generation for UX responsiveness.
        graph = build_corrective_rag_graph()
        final_state = graph.invoke(initial_state)

        answer = final_state.get("answer", REFUSAL_MESSAGE)
        raw_citations = final_state.get("citations", [])
        citations = [
            Citation(
                index=c["index"],
                document=c.get("document"),
                document_id=c.get("document_id", 0),
                page_number=c.get("page_number"),
                section=c.get("section"),
                text=c.get("text", ""),
                similarity_score=c.get("similarity_score", 0.0),
            )
            for c in raw_citations
        ]
        insufficient = final_state.get("insufficient_information", False)

        # Stream answer word-by-word for a responsive feel
        words = answer.split(" ")
        for i, word in enumerate(words):
            token = word if i == 0 else " " + word
            yield f"data: {json.dumps({'token': token})}\n\n"

        yield self._done_event(answer, citations, insufficient=insufficient)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _retrieve_context(
        self,
        question: str,
        owner_id: int | None,
        document_ids: list[int] | None,
        top_k: int | None,
        org_id: int | None,
    ) -> tuple[str, list[SearchResult], bool, str]:
        """Run the shared pre-generation retrieval stages for both request modes."""
        processed_query = preprocess_query(question)
        candidate_chunks = self.indexing.search(
            query=processed_query,
            top_k=self._candidate_top_k(top_k),
            owner_id=owner_id,
            document_ids=document_ids,
            org_id=org_id,
        )
        if not candidate_chunks and self._vector_store_is_empty():
            self._ensure_documents_indexed()
            candidate_chunks = self.indexing.search(
                query=processed_query,
                top_k=self._candidate_top_k(top_k),
                owner_id=owner_id,
                document_ids=document_ids,
                org_id=org_id,
            )

        chunks = self.reranker.rerank(
            query=processed_query,
            chunks=candidate_chunks,
            top_k=settings.rerank_top_k,
        )
        chunks = self.context_validator.usable_chunks(chunks)
        context_is_enough, context = self.context_validator.validate_context(processed_query, chunks)
        return processed_query, chunks, context_is_enough, context

    def _vector_store_is_empty(self) -> bool:
        try:
            return self.indexing.vector_store.count() == 0
        except Exception:
            return False

    def _ensure_documents_indexed(self) -> None:
        """If vector store is empty, sync extracted text from DB into vector store."""
        try:
            from app.database.session import SessionLocal
            from app.models.user import Document, DocumentStatus
            from app.services.document_processor import get_document_processor
            from app.services.storage import get_storage_backend

            processor = get_document_processor()
            storage = get_storage_backend()

            with SessionLocal() as db:
                indexed_docs = (
                    db.query(Document)
                    .filter(
                        Document.status == DocumentStatus.INDEXED,
                        Document.extracted_text_path.isnot(None),
                    )
                    .all()
                )
                for doc in indexed_docs:
                    if doc.extracted_text_path:
                        try:
                            result = processor.load_extraction_result(storage, doc.extracted_text_path)
                            self.indexing.index_document(
                                result=result,
                                document_id=doc.id,
                                filename=doc.filename,
                                owner_id=doc.owner_id,
                                org_id=doc.org_id,
                            )
                        except Exception as e:
                            logger.warning("Auto re-indexing document %d failed: %s", doc.id, e)
        except Exception as exc:
            logger.warning("Auto re-indexing check failed: %s", exc)

    @staticmethod
    def _candidate_top_k(requested_top_k: int | None) -> int:
        """Keep the public top_k override while retaining the 10-20 candidate pool."""
        if requested_top_k is None:
            return settings.vector_search_top_k
        return max(10, min(20, requested_top_k))

    def _insufficient_result(self, chunks: list[SearchResult]) -> RAGResult:
        return RAGResult(
            answer=REFUSAL_MESSAGE,
            retrieved_chunks=[chunk.to_dict() for chunk in chunks],
            provider=self.llm.provider_name,
            model=self.llm.model_name,
            insufficient_information=True,
        )

    def _done_event(
        self, answer: str, citations: list[Citation], insufficient: bool
    ) -> str:
        done_payload = {
            "answer": answer,
            "citations": [citation.to_dict() for citation in citations],
            "provider": self.llm.provider_name,
            "model": self.llm.model_name,
            "insufficient_information": insufficient,
        }
        return f"data: [DONE] {json.dumps(done_payload)}\n\n"

    def _build_citations(self, chunks: list[SearchResult]) -> list[Citation]:
        citations: list[Citation] = []
        for i, chunk in enumerate(chunks, start=1):
            citations.append(
                Citation(
                    index=i,
                    document=chunk.filename,
                    document_id=chunk.document_id,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    text=chunk.text[:500],
                    similarity_score=chunk.similarity_score,
                )
            )
        return citations

    def _build_user_prompt(
        self,
        question: str,
        context: str,
        chat_history: list[dict[str, str]] | None,
        compare_mode: bool,
    ) -> str:
        history_block = ""
        if chat_history:
            lines = []
            for msg in chat_history[-settings.rag_history_turns :]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                lines.append(f"{role}: {content}")
            history_block = "Chat History:\n" + "\n".join(lines) + "\n\n"

        compare_instruction = ""
        if compare_mode:
            compare_instruction = (
                "\nIf multiple documents are present in the context, "
                "compare them and present differences in a markdown table when useful.\n"
            )

        return (
            f"{history_block}"
            f"Context:\n{context}\n\n"
            f"Question:\n{question}"
            f"{compare_instruction}"
        )

    @staticmethod
    def _maybe_format_comparison(answer: str, chunks: list[SearchResult]) -> str:
        """Ensure comparison answers mention multiple documents when available."""
        docs = {c.filename for c in chunks if c.filename}
        if len(docs) < 2:
            return answer
        if "|" in answer or "comparison" in answer.lower() or "compare" in answer.lower():
            return answer
        doc_list = ", ".join(sorted(docs))
        return f"{answer}\n\n_Compared sources: {doc_list}_"


def get_rag_service() -> RAGService:
    """Return configured RAG service."""
    return RAGService()
