"""Authentication endpoint tests."""

import pytest


def test_health_check(client):
  response = client.get("/health")
  assert response.status_code == 200
  assert response.json()["status"] == "ok"


def test_register_first_user_becomes_admin(client):
  payload = {
    "name": "Admin User",
    "email": "admin@company.com",
    "password": "SecurePass1",
    "role": "employee",
  }
  response = client.post("/api/v1/auth/register", json=payload)
  assert response.status_code == 201
  data = response.json()
  assert data["email"] == payload["email"]
  assert data["role"] == "admin"


def test_register_duplicate_email(client, registered_user):
  response = client.post(
    "/api/v1/auth/register",
    json={
      "name": "Another User",
      "email": registered_user["email"],
      "password": "SecurePass1",
    },
  )
  assert response.status_code == 409


def test_register_weak_password(client):
  response = client.post(
    "/api/v1/auth/register",
    json={
      "name": "Weak Pass",
      "email": "weak@test.com",
      "password": "weak",
    },
  )
  assert response.status_code == 422


def test_login_success(client, registered_user):
  response = client.post(
    "/api/v1/auth/login",
    json={
      "email": registered_user["email"],
      "password": registered_user["password"],
    },
  )
  assert response.status_code == 200
  data = response.json()
  assert "access_token" in data
  assert data["token_type"] == "bearer"
  assert data["expires_in"] > 0


def test_login_invalid_credentials(client, registered_user):
  response = client.post(
    "/api/v1/auth/login",
    json={
      "email": registered_user["email"],
      "password": "WrongPassword1",
    },
  )
  assert response.status_code == 401


def test_get_me_authenticated(client, registered_user):
  login = client.post(
    "/api/v1/auth/login",
    json={
      "email": registered_user["email"],
      "password": registered_user["password"],
    },
  )
  token = login.json()["access_token"]
  response = client.get(
    "/api/v1/auth/me",
    headers={"Authorization": f"Bearer {token}"},
  )
  assert response.status_code == 200
  assert response.json()["email"] == registered_user["email"]


def test_get_me_unauthenticated(client):
  response = client.get("/api/v1/auth/me")
  assert response.status_code == 401


def test_admin_users_requires_admin(client, registered_user):
  login = client.post(
    "/api/v1/auth/login",
    json={
      "email": registered_user["email"],
      "password": registered_user["password"],
    },
  )
  token = login.json()["access_token"]
  response = client.get(
    "/api/v1/admin/users",
    headers={"Authorization": f"Bearer {token}"},
  )
  assert response.status_code == 200
  assert response.json()["total"] == 1


def test_admin_users_forbidden_for_employee(client, registered_user):
  client.post(
    "/api/v1/auth/register",
    json={
      "name": "Employee",
      "email": "employee@test.com",
      "password": "SecurePass1",
    },
  )
  login = client.post(
    "/api/v1/auth/login",
    json={"email": "employee@test.com", "password": "SecurePass1"},
  )
  token = login.json()["access_token"]
  response = client.get(
    "/api/v1/admin/users",
    headers={"Authorization": f"Bearer {token}"},
  )
  assert response.status_code == 403
