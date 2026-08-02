"""Phase 3: chunking, embeddings, vector search, and indexing tests."""

from app.services.chunking import ChunkingService, RecursiveCharacterTextSplitter
from app.services.document_processor import ExtractedPage, ExtractionResult
from app.services.embeddings import EmbeddingService, FakeEmbeddingProvider
from app.services.indexing import IndexingService
from app.services.vector_store import InMemoryVectorStore


def test_recursive_splitter_respects_chunk_size():
    splitter = RecursiveCharacterTextSplitter(chunk_size=50, chunk_overlap=10)
    text = "Paragraph one talks about leave policy. " * 10
    chunks = splitter.split_text(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= 50 + 20 for chunk in chunks)  # allow separator slack


def test_chunking_preserves_metadata():
    result = ExtractionResult(
        pages=[
            ExtractedPage(page_number=1, text="Leave policy section. Employees get 20 days.", section="Leave"),
            ExtractedPage(page_number=2, text="Benefits overview and health insurance details.", section="Benefits"),
        ],
        file_type="pdf",
    )
    service = ChunkingService(chunk_size=80, chunk_overlap=10)
    chunks = service.chunk_extraction(result, document_id=7, filename="policy.pdf", owner_id=3)

    assert len(chunks) >= 2
    assert chunks[0].document_id == 7
    assert chunks[0].filename == "policy.pdf"
    assert chunks[0].page_number == 1
    assert chunks[0].section == "Leave"
    assert chunks[0].owner_id == 3


def test_fake_embeddings_are_normalized():
    provider = FakeEmbeddingProvider(dimension=32)
    vectors = provider.embed_documents(["hello world", "leave policy"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 32
    norm = sum(v * v for v in vectors[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-5


def test_indexing_and_semantic_search():
    store = InMemoryVectorStore()
    embeddings = EmbeddingService(FakeEmbeddingProvider(dimension=64))
    indexing = IndexingService(
        chunking=ChunkingService(chunk_size=200, chunk_overlap=20),
        embeddings=embeddings,
        vector_store=store,
    )

    result = ExtractionResult(
        pages=[
            ExtractedPage(
                page_number=12,
                text="Employees receive 20 paid leaves annually according to company policy.",
                section="Leave Policy",
            ),
            ExtractedPage(
                page_number=3,
                text="The office cafeteria serves lunch from 12 to 2 PM every weekday.",
                section="Facilities",
            ),
        ],
        file_type="pdf",
    )

    index_result = indexing.index_document(
        result=result,
        document_id=1,
        filename="Employee_policy.pdf",
        owner_id=1,
    )
    assert index_result.chunk_count >= 2
    assert store.count() >= 2

    hits = indexing.search("paid leaves annually company policy", top_k=2, owner_id=1)
    assert len(hits) >= 1
    assert hits[0].document_id == 1
    assert hits[0].filename == "Employee_policy.pdf"
    assert "leave" in hits[0].text.lower()
    assert hits[0].page_number == 12

    cafeteria = indexing.search("cafeteria lunch weekday", top_k=1, owner_id=1)
    assert "cafeteria" in cafeteria[0].text.lower()


def test_delete_document_vectors():
    store = InMemoryVectorStore()
    indexing = IndexingService(
        embeddings=EmbeddingService(FakeEmbeddingProvider(dimension=32)),
        vector_store=store,
    )
    result = ExtractionResult(
        pages=[ExtractedPage(page_number=1, text="Confidential revenue figures for 2024.", section=None)],
        file_type="txt",
    )
    indexing.index_document(result, document_id=9, filename="fin.txt", owner_id=2)
    assert store.count() >= 1
    indexing.delete_document(9)
    assert store.count() == 0


def test_search_api(client, auth_headers, db_session):
    content = (
        b"Company Leave Policy\n\n"
        b"Employees receive 20 paid leaves annually.\n"
        b"Unused leaves may be carried forward up to 5 days.\n"
    )
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("leave_policy.txt", content, "text/plain")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["document"]["id"]

    # Background worker updates DB; response body may still show pre-task status
    from app.models.user import Document, DocumentStatus

    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    db_session.refresh(doc)
    assert doc.status == DocumentStatus.INDEXED
    assert doc.chunk_count is not None and doc.chunk_count >= 1

    response = client.post(
        "/api/v1/search/",
        headers=auth_headers,
        json={"query": "How many paid leaves do employees get?", "top_k": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert "leave" in data["results"][0]["text"].lower()
    assert data["results"][0]["document"] == "leave_policy.txt"
    assert "similarity_score" in data["results"][0]


def test_search_requires_auth(client):
    response = client.post("/api/v1/search/", json={"query": "test"})
    assert response.status_code == 401
