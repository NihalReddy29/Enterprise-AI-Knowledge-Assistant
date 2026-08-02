"""Phase 4: RAG pipeline and chat query tests."""

from app.services.chunking import ChunkingService
from app.services.document_processor import ExtractedPage, ExtractionResult
from app.services.embeddings import EmbeddingService, FakeEmbeddingProvider
from app.services.indexing import IndexingService
from app.services.llm import FakeLLMProvider, LLMService
from app.services.rag import RAGService
from app.services.vector_store import InMemoryVectorStore


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
    assert result.answer == "I don't have enough information."


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
