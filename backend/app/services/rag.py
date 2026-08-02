"""RAG pipeline: retrieve context, prompt LLM, generate citations."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field

from app.config import get_settings
from app.services.indexing import IndexingService, get_indexing_service
from app.services.llm import LLMService, get_llm_service
from app.services.vector_store import SearchResult

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are an enterprise assistant.

Answer only using the provided context.
If the answer is unavailable say:
"I don't have enough information."

Always provide citations."""


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
    ) -> None:
        self.indexing = indexing or get_indexing_service()
        self.llm = llm or get_llm_service()

    def ask(
        self,
        question: str,
        owner_id: int | None = None,
        document_ids: list[int] | None = None,
        top_k: int | None = None,
        chat_history: list[dict[str, str]] | None = None,
        compare_mode: bool = False,
    ) -> RAGResult:
        """Run the full RAG pipeline for a user question."""
        k = top_k or settings.rag_top_k
        chunks = self.indexing.search(
            query=question,
            top_k=k,
            owner_id=owner_id,
            document_ids=document_ids,
        )

        citations = self._build_citations(chunks)
        context = self._format_context(chunks)
        user_prompt = self._build_user_prompt(
            question=question,
            context=context,
            chat_history=chat_history,
            compare_mode=compare_mode,
        )

        llm_response = self.llm.generate(SYSTEM_PROMPT, user_prompt)
        answer = llm_response.content.strip()
        insufficient = self._is_insufficient(answer, chunks)

        if insufficient:
            answer = "I don't have enough information."
            # Keep citations empty when we cannot ground the answer
            if not chunks:
                citations = []

        if compare_mode and chunks and not insufficient:
            answer = self._maybe_format_comparison(answer, chunks)

        return RAGResult(
            answer=answer,
            citations=citations if not insufficient or chunks else [],
            retrieved_chunks=[chunk.to_dict() for chunk in chunks],
            provider=llm_response.provider,
            model=llm_response.model,
            insufficient_information=insufficient,
        )

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

    def _format_context(self, chunks: list[SearchResult]) -> str:
        if not chunks:
            return "(no relevant context found)"

        blocks: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            location_parts = []
            if chunk.page_number is not None:
                location_parts.append(f"Page {chunk.page_number}")
            if chunk.section:
                location_parts.append(f"Section {chunk.section}")
            location = ", ".join(location_parts) if location_parts else "Unknown location"
            header = f"[{i}] {chunk.filename or 'document'} ({location})"
            blocks.append(f"{header}\n{chunk.text}")
        return "\n\n".join(blocks)

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
    def _is_insufficient(answer: str, chunks: list[SearchResult]) -> bool:
        if not chunks:
            return True
        normalized = answer.lower().strip()
        markers = [
            "i don't have enough information",
            "i do not have enough information",
            "don't have enough information",
            "no relevant information",
        ]
        return any(marker in normalized for marker in markers)

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
