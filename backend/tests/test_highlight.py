"""Tests for citation highlighting helpers and document highlight API."""

import io

from app.utils.highlight import find_highlight_spans


def test_find_highlight_spans_exact():
    page = "Employees receive 20 paid leaves annually according to company policy."
    spans = find_highlight_spans(page, "20 paid leaves annually")
    assert len(spans) == 1
    assert "20 paid leaves" in spans[0].matched_text


def test_find_highlight_spans_fuzzy_whitespace():
    page = "Employees receive 20 paid leaves\nannually according to policy."
    spans = find_highlight_spans(page, "20 paid leaves annually")
    assert len(spans) >= 1


def test_document_highlight_api(client, auth_headers, db_session):
    content = (
        b"Employee Leave Policy\n\n"
        b"Employees receive 20 paid leaves annually.\n"
        b"Unused leaves may be carried forward.\n"
    )
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("leave.txt", content, "text/plain")},
    )
    doc_id = upload.json()["document"]["id"]

    response = client.get(
        f"/api/v1/documents/{doc_id}/highlight",
        headers=auth_headers,
        params={
            "excerpt": "Employees receive 20 paid leaves annually.",
            "page_number": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == doc_id
    assert data["page_number"] == 1
    assert data["filename"] == "leave.txt"
    assert len(data["matches"]) >= 1
    assert "20 paid leaves" in data["matches"][0]["matched_text"]


def test_document_file_api(client, auth_headers):
    content = b"Security policy text for download."
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("security.txt", io.BytesIO(content), "text/plain")},
    )
    doc_id = upload.json()["document"]["id"]

    response = client.get(
        f"/api/v1/documents/{doc_id}/file",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.content == content
    assert "text/plain" in response.headers.get("content-type", "")
