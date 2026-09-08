"""Tests for organization management and shared team libraries."""

import io
from fastapi.testclient import TestClient


def _register_user(client: TestClient, name: str, email: str, password: str = "SecurePass1") -> dict:
    resp = client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password, "role": "employee"},
    )
    assert resp.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_organizations(client: TestClient, auth_headers: dict):
    # Create org
    resp = client.post(
        "/api/v1/orgs",
        headers=auth_headers,
        json={"name": "Engineering Team"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Engineering Team"
    assert data["slug"] == "engineering-team"
    assert data["member_count"] == 1
    assert data["my_role"] == "owner"
    org_id = data["id"]

    # List orgs
    list_resp = client.get("/api/v1/orgs", headers=auth_headers)
    assert list_resp.status_code == 200
    orgs = list_resp.json()
    assert len(orgs) == 1
    assert orgs[0]["id"] == org_id


def test_org_detail_and_members(client: TestClient, auth_headers: dict):
    created = client.post(
        "/api/v1/orgs",
        headers=auth_headers,
        json={"name": "Design Team"},
    ).json()
    org_id = created["id"]

    detail_resp = client.get(f"/api/v1/orgs/{org_id}", headers=auth_headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == org_id
    assert len(detail["members"]) == 1
    assert detail["members"][0]["role"] == "owner"


def test_invite_and_accept(client: TestClient, auth_headers: dict):
    # Admin creates org
    org = client.post(
        "/api/v1/orgs",
        headers=auth_headers,
        json={"name": "Product Team"},
    ).json()
    org_id = org["id"]

    # Second user registers
    emp_headers = _register_user(client, "Bob Employee", "bob@example.com")

    # Invite Bob
    invite_resp = client.post(
        f"/api/v1/orgs/{org_id}/invite",
        headers=auth_headers,
        json={"email": "bob@example.com", "role": "member"},
    )
    assert invite_resp.status_code == 201
    invite_data = invite_resp.json()
    token = invite_data["token"]

    # Bob accepts invite
    accept_resp = client.post(
        f"/api/v1/orgs/invites/{token}/accept",
        headers=emp_headers,
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["id"] == org_id

    # Check member count
    detail_resp = client.get(f"/api/v1/orgs/{org_id}", headers=emp_headers)
    assert detail_resp.status_code == 200
    assert len(detail_resp.json()["members"]) == 2


def test_publish_and_unpublish_document(client: TestClient, auth_headers: dict):
    # Create org
    org = client.post(
        "/api/v1/orgs",
        headers=auth_headers,
        json={"name": "Research Group"},
    ).json()
    org_id = org["id"]

    # Upload document
    upload_resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("research_paper.txt", io.BytesIO(b"Artificial Intelligence and RAG systems."), "text/plain")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["document"]["id"]

    # Publish to org
    pub_resp = client.patch(
        f"/api/v1/documents/{doc_id}/publish",
        headers=auth_headers,
        json={"org_id": org_id},
    )
    assert pub_resp.status_code == 200
    assert pub_resp.json()["org_id"] == org_id

    # Second user in org can see document
    emp_headers = _register_user(client, "Alice Research", "alice@example.com")
    invite = client.post(
        f"/api/v1/orgs/{org_id}/invite",
        headers=auth_headers,
        json={"email": "alice@example.com", "role": "member"},
    ).json()
    client.post(f"/api/v1/orgs/invites/{invite['token']}/accept", headers=emp_headers)

    # Alice lists org documents
    docs_resp = client.get(f"/api/v1/documents/?org_id={org_id}", headers=emp_headers)
    assert docs_resp.status_code == 200
    assert docs_resp.json()["total"] == 1

    # Unpublish document
    unpub_resp = client.delete(
        f"/api/v1/documents/{doc_id}/unpublish",
        headers=auth_headers,
    )
    assert unpub_resp.status_code == 200
    assert unpub_resp.json()["org_id"] is None
