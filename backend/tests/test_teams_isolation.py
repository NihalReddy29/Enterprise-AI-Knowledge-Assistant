"""Verify team document and vector isolation."""

from app.models.team import Team, TeamMember, TeamMemberRole, TeamMemberStatus
from app.models.user import Document, DocumentStatus, User
from app.services.indexing import IndexingService
from app.services.vector_store import InMemoryVectorStore


def _make_user(db, email: str, name: str) -> User:
    from app.utils.security import hash_password

    user = User(name=name, email=email, password_hash=hash_password("password123"))
    db.add(user)
    db.flush()
    return user


def _make_team(db, owner: User, name: str, collection: str) -> Team:
    from app.utils.team_join_codes import generate_join_code

    team = Team(
        name=name,
        description=None,
        owner_id=owner.id,
        qdrant_collection_name=collection,
        join_code=generate_join_code(db),
    )
    db.add(team)
    db.flush()
    db.add(
        TeamMember(
            team_id=team.id,
            user_id=owner.id,
            role=TeamMemberRole.OWNER,
            status=TeamMemberStatus.ACTIVE,
        )
    )
    db.flush()
    return team


def test_team_a_cannot_list_team_b_documents(client, db_session):
    """User in Team A must not see Team B documents via the team documents API."""
    user_a = _make_user(db_session, "alice@example.com", "Alice")
    user_b = _make_user(db_session, "bob@example.com", "Bob")
    team_a = _make_team(db_session, user_a, "Team A", "team_a_collection")
    team_b = _make_team(db_session, user_b, "Team B", "team_b_collection")

    doc_b = Document(
        filename="secret-b.pdf",
        file_type="pdf",
        owner_id=user_b.id,
        team_id=team_b.id,
        storage_path=f"teams/{team_b.id}/secret.pdf",
        status=DocumentStatus.INDEXED,
    )
    db_session.add(doc_b)
    db_session.commit()

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    token_a = login_a.json()["access_token"]

    # Alice can list Team A docs (empty)
    ok = client.get(
        f"/api/v1/teams/{team_a.id}/documents",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert ok.status_code == 200
    assert ok.json()["total"] == 0

    # Alice cannot list Team B docs
    denied = client.get(
        f"/api/v1/teams/{team_b.id}/documents",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert denied.status_code == 403


def test_team_documents_not_in_personal_list(client, db_session):
    """Team-scoped uploads must not appear on GET /documents/ (personal workspace)."""
    admin = _make_user(db_session, "admin@example.com", "Admin")
    admin.role = "admin"
    user = _make_user(db_session, "owner@example.com", "Owner")
    team = _make_team(db_session, user, "My Team", "team_personal_list")

    personal_doc = Document(
        filename="personal.pdf",
        file_type="pdf",
        owner_id=user.id,
        storage_path="uploads/personal.pdf",
        status=DocumentStatus.INDEXED,
    )
    team_doc = Document(
        filename="team-only.pdf",
        file_type="pdf",
        owner_id=user.id,
        team_id=team.id,
        storage_path=f"teams/{team.id}/team-only.pdf",
        status=DocumentStatus.INDEXED,
    )
    db_session.add_all([personal_doc, team_doc])
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    filenames = [doc["filename"] for doc in response.json()["documents"]]
    assert "personal.pdf" in filenames
    assert "team-only.pdf" not in filenames


def test_join_code_request_and_admin_approval(client, db_session):
    """Users can request to join via code; admins approve before membership is granted."""
    owner = _make_user(db_session, "owner@example.com", "Owner")
    outsider = _make_user(db_session, "guest@example.com", "Guest")
    team = _make_team(db_session, owner, "Open Team", "team_join_flow")
    db_session.commit()

    login_guest = client.post(
        "/api/v1/auth/login",
        json={"email": "guest@example.com", "password": "password123"},
    )
    guest_token = login_guest.json()["access_token"]

    preview = client.get(
        "/api/v1/teams/join/preview",
        params={"code": team.join_code},
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert preview.status_code == 200
    assert preview.json()["team_name"] == "Open Team"

    request_res = client.post(
        "/api/v1/teams/join",
        json={"join_code": team.join_code, "message": "Please add me"},
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert request_res.status_code == 201
    request_id = request_res.json()["id"]

    login_owner = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    owner_token = login_owner.json()["access_token"]

    pending = client.get(
        f"/api/v1/teams/{team.id}/join-requests",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert pending.status_code == 200
    assert pending.json()["total"] == 1

    approve = client.post(
        f"/api/v1/teams/{team.id}/join-requests/{request_id}/approve",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert approve.status_code == 200

    guest_teams = client.get(
        "/api/v1/teams",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert guest_teams.status_code == 200
    assert any(t["id"] == team.id for t in guest_teams.json())


def test_team_vectors_are_isolated_by_collection():
    """Vectors in team A collection must not appear in team B collection search."""
    store = InMemoryVectorStore()
    indexing = IndexingService(vector_store=store)

    from app.services.document_processor import ExtractedPage, ExtractionResult

    result = ExtractionResult(
        pages=[
            ExtractedPage(
                page_number=1,
                text="Team A confidential policy about widgets.",
            )
        ],
        total_pages=1,
        ocr_used=False,
    )

    indexing.index_document(
        result=result,
        document_id=101,
        filename="a.pdf",
        owner_id=1,
        team_id=10,
        collection_name="team_10",
    )

    team_a_hits = indexing.search(
        "widgets policy",
        top_k=5,
        team_id=10,
        collection_name="team_10",
    )
    team_b_hits = indexing.search(
        "widgets policy",
        top_k=5,
        team_id=20,
        collection_name="team_20",
    )
    personal_hits = indexing.search("widgets policy", top_k=5, owner_id=1)

    assert len(team_a_hits) >= 1
    assert team_b_hits == []
    assert personal_hits == []
