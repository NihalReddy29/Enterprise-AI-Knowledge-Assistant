"""Document management endpoint tests."""

import io

import pytest

from app.models.user import Document, DocumentStatus
from app.services.document_processor import DocumentProcessor
from app.utils.text_cleaner import clean_text, is_text_sufficient


@pytest.fixture
def sample_txt_file():
    """Create an in-memory text file for upload."""
    content = b"Employee Leave Policy\n\nEmployees receive 20 paid leaves annually.\n"
    return ("policy.txt", io.BytesIO(content), "text/plain")


def test_upload_txt_document(client, auth_headers, sample_txt_file, db_session):
    filename, file_obj, content_type = sample_txt_file

    response = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": (filename, file_obj, content_type)},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["document"]["filename"] == "policy.txt"
    assert data["document"]["file_type"] == "txt"
    assert data["document"]["status"] in ("indexed", "extracted", "processing", "pending")

    # Background task should complete during TestClient request cycle
    doc_id = data["document"]["id"]
    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert doc is not None
    assert doc.status == DocumentStatus.INDEXED
    assert doc.page_count == 1
    assert doc.chunk_count is not None and doc.chunk_count >= 1
    assert doc.extracted_text_path is not None


def test_list_documents(client, auth_headers, sample_txt_file):
    filename, file_obj, content_type = sample_txt_file
    client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": (filename, file_obj, content_type)},
    )

    response = client.get("/api/v1/documents/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["documents"]) >= 1


def test_get_document_content(client, auth_headers, sample_txt_file):
    filename, file_obj, content_type = sample_txt_file
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": (filename, file_obj, content_type)},
    )
    doc_id = upload.json()["document"]["id"]

    response = client.get(
        f"/api/v1/documents/{doc_id}/content",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_pages"] == 1
    assert "20 paid leaves" in data["pages"][0]["text"]


def test_delete_document(client, auth_headers, sample_txt_file):
    filename, file_obj, content_type = sample_txt_file
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": (filename, file_obj, content_type)},
    )
    doc_id = upload.json()["document"]["id"]

    response = client.delete(
        f"/api/v1/documents/{doc_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


def test_upload_unauthenticated(client, sample_txt_file):
    filename, file_obj, content_type = sample_txt_file
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, file_obj, content_type)},
    )
    assert response.status_code == 401


def test_upload_invalid_file_type(client, auth_headers):
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("malware.exe", io.BytesIO(b"bad"), "application/octet-stream")},
    )
    assert response.status_code == 400


def test_upload_empty_file(client, auth_headers):
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400


def test_employee_cannot_access_other_users_document(client, auth_headers, sample_txt_file):
    filename, file_obj, content_type = sample_txt_file
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": (filename, file_obj, content_type)},
    )
    doc_id = upload.json()["document"]["id"]

    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Employee Two",
            "email": "employee2@test.com",
            "password": "SecurePass1",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "employee2@test.com", "password": "SecurePass1"},
    )
    emp_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get(f"/api/v1/documents/{doc_id}", headers=emp_headers)
    assert response.status_code == 403


def test_clean_text():
    assert clean_text("  Hello   World  \n\n\nTest  ") == "Hello World \n\nTest"
    assert clean_text("") == ""


def test_is_text_sufficient():
    assert is_text_sufficient("This is a long enough text with many alphanumeric chars 12345")
    assert not is_text_sufficient("hi")
    assert not is_text_sufficient("")


def test_document_processor_txt():
    processor = DocumentProcessor()
    content = b"Section 1\n\nEmployees receive 20 paid leaves annually."
    result = processor.process(content, "txt")
    assert result.total_pages == 1
    assert "20 paid leaves" in result.full_text
