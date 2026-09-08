"""Phase 4: RAG pipeline and chat query tests."""

from app.services.chunking import ChunkingService
from app.services.document_processor import ExtractedPage, ExtractionResult
from app.services.embeddings import EmbeddingService, FakeEmbeddingProvider
from app.services.indexing import IndexingService
from app.services.llm import FakeLLMProvider, LLMService
from app.services.context_validator import ContextValidator, REFUSAL_MESSAGE
from app.services.query_processor import preprocess_query
from app.services.rag import RAGService
from app.services.reranker import RerankerService
from app.services.vector_store import InMemoryVectorStore, SearchResult


def _index_leave_policy() -> IndexingService:
    store = InMemoryVectorStore()
    indexing = IndexingService(
        chunking=ChunkingService(chunk_size=500, chunk_overlap=50),
        embeddings=EmbeddingService(FakeEmbeddingProvider(dimension=64)),
        vector_store=store,
    )
    result = ExtractionResult(
        pages=[
            ExtractedPage(
                page_number=12,
                text="Employees receive 20 paid leaves annually according to company policy.",
                section="Leave Policy",
            )
        ],
        file_type="pdf",
    )
    indexing.index_document(result, document_id=1, filename="Employee_policy.pdf", owner_id=1)
    return indexing


def test_rag_answers_with_citations():
    indexing = _index_leave_policy()
    rag = RAGService(indexing=indexing, llm=LLMService(FakeLLMProvider()))

    result = rag.ask("How many paid leaves do employees get?", owner_id=1)

    assert not result.insufficient_information
    assert "20" in result.answer or "leave" in result.answer.lower()
    assert len(result.citations) >= 1
    assert result.citations[0].document == "Employee_policy.pdf"
    assert result.citations[0].page_number == 12
    assert result.provider == "fake"


def test_rag_insufficient_without_context():
    indexing = IndexingService(
        embeddings=EmbeddingService(FakeEmbeddingProvider(dimension=32)),
        vector_store=InMemoryVectorStore(),
    )
    rag = RAGService(indexing=indexing, llm=LLMService(FakeLLMProvider()))

    result = rag.ask("What is the bonus policy?", owner_id=1)
    assert result.insufficient_information
    assert result.answer == REFUSAL_MESSAGE


def test_query_preprocessing_normalizes_noise_and_empty_input():
    assert preprocess_query("  What\t\n is  MFA?  ") == "What is MFA?"
    assert preprocess_query("MFA\x00 policy") == "MFA policy"
    assert preprocess_query(" \n\t ") == ""
    assert preprocess_query("Leave policy?") == "Leave policy?"


def test_rag_uses_configured_candidate_pool_then_reranks():
    class CapturingIndexing:
        def __init__(self):
            self.top_k = None

        def search(self, **kwargs):
            self.top_k = kwargs["top_k"]
            return [
                SearchResult("Leave policy gives 20 paid days.", 1, "policy.pdf", 1, "Leave", .9, 0),
                SearchResult("Leave policy gives 20 paid days.", 2, "other.pdf", 1, "Leave", .8, 0),
            ]

    indexing = CapturingIndexing()
    rag = RAGService(indexing=indexing, llm=LLMService(FakeLLMProvider()))
    result = rag.ask("How many paid leave days?")

    assert indexing.top_k == 15
    assert len(result.retrieved_chunks) <= 5
    assert RAGService._candidate_top_k(10) == 10
    assert RAGService._candidate_top_k(15) == 15
    assert RAGService._candidate_top_k(20) == 20


def test_reranker_hybrid_signals_deduplicate_and_limit_results():
    chunks = [
        SearchResult("General employee information.", 1, "general.pdf", 1, None, .95, 0),
        SearchResult("Employees receive 20 paid leave days annually.", 2, "policy.pdf", 2, "Leave Policy", .70, 0),
        SearchResult("Employees receive 20 paid leave days annually.", 2, "policy.pdf", 2, "Leave Policy", .70, 0),
    ]
    reranked = RerankerService().rerank("paid leave policy", chunks, top_k=5)

    assert len(reranked) == 2
    assert reranked[0].document_id == 2


def test_context_and_answer_validation_reject_ungrounded_content():
    validator = ContextValidator(min_score=.05)
    chunks = [SearchResult("Employees receive 20 paid leaves annually.", 1, "policy.pdf", 1, "Leave", .8)]

    enough, context = validator.validate_context("paid leave policy", chunks)
    assert enough
    assert "Employees receive" in context
    assert validator.validate_context("bonus eligibility details", chunks) == (False, REFUSAL_MESSAGE)
    assert validator.validate_answer("Employees receive 20 paid leaves annually.", chunks)[1]
    assert validator.validate_answer("The company offers free spaceships.", chunks) == (REFUSAL_MESSAGE, False)
    assert validator.validate_answer("", chunks) == (REFUSAL_MESSAGE, False)
    assert validator.validate_answer(REFUSAL_MESSAGE, chunks) == (REFUSAL_MESSAGE, False)


def test_insufficient_context_never_calls_llm_or_llm_stream():
    class NoCallLLM(LLMService):
        def __init__(self):
            super().__init__(FakeLLMProvider())
            self.calls = 0
            self.stream_calls = 0

        def generate(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("LLM must not be called")

        def generate_stream(self, *args, **kwargs):
            self.stream_calls += 1
            raise AssertionError("LLM stream must not be called")

    indexing = IndexingService(
        embeddings=EmbeddingService(FakeEmbeddingProvider(dimension=32)),
        vector_store=InMemoryVectorStore(),
    )
    llm = NoCallLLM()
    rag = RAGService(indexing=indexing, llm=llm)

    assert rag.ask("bonus policy").answer == REFUSAL_MESSAGE
    events = list(rag.ask_stream("bonus policy"))
    assert llm.calls == 0
    assert llm.stream_calls == 0
    assert REFUSAL_MESSAGE in events[0]
    assert "[DONE]" in events[1]


def test_chat_query_api(client, auth_headers, db_session):
    content = (
        b"Employee Leave Policy\n\n"
        b"Employees receive 20 paid leaves annually.\n"
        b"Maternity leave is 26 weeks.\n"
    )
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("hr_policy.txt", content, "text/plain")},
    )
    assert upload.status_code == 201

    response = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={"question": "How many paid leaves annually?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] > 0
    assert data["message_id"] > 0
    assert data["provider"] == "fake"
    assert "leave" in data["answer"].lower() or "20" in data["answer"]
    assert isinstance(data["citations"], list)
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["document"] == "hr_policy.txt"

    history = client.get("/api/v1/chat/history", headers=auth_headers)
    assert history.status_code == 200
    assert history.json()["total"] >= 1

    detail = client.get(
        f"/api/v1/chat/conversations/{data['conversation_id']}",
        headers=auth_headers,
    )
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) >= 2


def test_chat_query_follow_up_same_conversation(client, auth_headers):
    content = b"Remote work policy: Employees may work remotely two days per week.\n"
    client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("remote.txt", content, "text/plain")},
    )

    first = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={"question": "What is the remote work policy?"},
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={
            "question": "How many remote days are allowed?",
            "conversation_id": conversation_id,
        },
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id


def test_delete_conversation(client, auth_headers):
    content = b"Security policy: Use MFA for all accounts.\n"
    client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("security.txt", content, "text/plain")},
    )
    query = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={"question": "Is MFA required?"},
    )
    conversation_id = query.json()["conversation_id"]

    deleted = client.delete(
        f"/api/v1/chat/conversations/{conversation_id}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204

    missing = client.get(
        f"/api/v1/chat/conversations/{conversation_id}",
        headers=auth_headers,
    )
    assert missing.status_code == 404


def test_chat_query_requires_auth(client):
    response = client.post("/api/v1/chat/query", json={"question": "Hello"})
    assert response.status_code == 401


def test_chat_stream_api(client, auth_headers):
    content = b"Holiday policy: Dec 25 and Jan 1 are company holidays.\n"
    client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("holidays.txt", content, "text/plain")},
    )

    response = client.post(
        "/api/v1/chat/stream",
        headers=auth_headers,
        json={"question": "What holidays are observed?"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    text = response.text
    assert "data: " in text
    assert "[DONE]" in text
    assert "[META]" in text

    # Verify conversation was saved in DB
    history = client.get("/api/v1/chat/history", headers=auth_headers)
    assert history.status_code == 200
    conversations = history.json()["conversations"]
    assert len(conversations) >= 1
    conv_id = conversations[0]["id"]

    detail = client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
