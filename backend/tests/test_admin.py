"""Admin dashboard and feedback API tests."""

from app.models.user import Feedback, QueryLog


def test_chat_query_creates_query_log(client, auth_headers, db_session):
    content = b"Leave policy: Employees receive 20 paid leaves annually.\n"
    client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("policy.txt", content, "text/plain")},
    )
    response = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={"question": "What is the leave policy?"},
    )
    assert response.status_code == 200
    logs = db_session.query(QueryLog).all()
    assert len(logs) == 1
    assert "leave" in logs[0].question.lower()
    assert logs[0].topic is not None


def test_admin_statistics_and_queries(client, auth_headers, db_session):
    content = b"Remote work: two days remote each week.\n"
    client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("remote.txt", content, "text/plain")},
    )
    query = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={"question": "How many remote days are allowed?"},
    )
    assert query.status_code == 200

    stats = client.get("/api/v1/admin/statistics", headers=auth_headers)
    assert stats.status_code == 200
    data = stats.json()
    assert data["total_users"] >= 1
    assert data["total_documents"] >= 1
    assert data["total_questions"] >= 1
    assert "storage_mb" in data
    assert isinstance(data["most_searched_topics"], list)

    queries = client.get("/api/v1/admin/queries", headers=auth_headers)
    assert queries.status_code == 200
    assert queries.json()["total"] >= 1

    storage = client.get("/api/v1/admin/storage", headers=auth_headers)
    assert storage.status_code == 200
    assert storage.json()["total_documents"] >= 1

    docs = client.get("/api/v1/admin/documents", headers=auth_headers)
    assert docs.status_code == 200
    assert docs.json()["total"] >= 1


def test_feedback_submit_and_admin_list(client, auth_headers, db_session):
    content = b"MFA is required for all accounts.\n"
    client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("sec.txt", content, "text/plain")},
    )
    query = client.post(
        "/api/v1/chat/query",
        headers=auth_headers,
        json={"question": "Is MFA required?"},
    )
    message_id = query.json()["message_id"]

    feedback = client.post(
        f"/api/v1/chat/messages/{message_id}/feedback",
        headers=auth_headers,
        json={"rating": 1, "comment": "Accurate"},
    )
    assert feedback.status_code == 201
    assert feedback.json()["rating"] == 1
    assert db_session.query(Feedback).count() == 1

    admin_feedback = client.get("/api/v1/admin/feedback", headers=auth_headers)
    assert admin_feedback.status_code == 200
    assert admin_feedback.json()["total"] >= 1


def test_admin_delete_user(client, auth_headers):
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Temp User",
            "email": "temp.user@test.com",
            "password": "SecurePass1",
        },
    )
    users = client.get("/api/v1/admin/users", headers=auth_headers)
    target = next(u for u in users.json()["users"] if u["email"] == "temp.user@test.com")

    deleted = client.delete(f"/api/v1/admin/users/{target['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    users_after = client.get("/api/v1/admin/users", headers=auth_headers)
    emails = [u["email"] for u in users_after.json()["users"]]
    assert "temp.user@test.com" not in emails


def test_admin_cannot_delete_self(client, auth_headers, registered_user, db_session):
    from app.models.user import User

    admin = db_session.query(User).filter(User.email == registered_user["email"]).first()
    response = client.delete(f"/api/v1/admin/users/{admin.id}", headers=auth_headers)
    assert response.status_code == 400
