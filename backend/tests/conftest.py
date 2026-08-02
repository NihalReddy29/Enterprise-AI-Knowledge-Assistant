"""Pytest configuration and shared fixtures."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LOCAL_STORAGE_PATH"] = "./test_storage"
os.environ["VECTOR_STORE"] = "memory"
os.environ["DEFAULT_EMBEDDING_PROVIDER"] = "fake"
os.environ["DEFAULT_LLM_PROVIDER"] = "fake"
os.environ["EMBEDDING_DIMENSION"] = "64"

from app.config.settings import clear_settings_cache

clear_settings_cache()

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.services.vector_store import reset_vector_store

SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ensure background workers use the same test database
import app.database.session as db_session_module

db_session_module.engine = engine
db_session_module.SessionLocal = TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_database():
    """Create and tear down tables for each test."""
    import shutil
    from pathlib import Path

    storage_path = Path("./test_storage")
    if storage_path.exists():
        shutil.rmtree(storage_path)

    reset_vector_store()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    reset_vector_store()
    if storage_path.exists():
        shutil.rmtree(storage_path, ignore_errors=True)


@pytest.fixture
def db_session():
    """Provide a database session for direct DB assertions."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """Provide a FastAPI test client with overridden DB dependency."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client):
    """Register and return a test user payload."""
    payload = {
        "name": "Test Admin",
        "email": "admin@test.com",
        "password": "SecurePass1",
        "role": "employee",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    return payload


@pytest.fixture
def auth_headers(client, registered_user):
    """Return authorization headers for the registered admin user."""
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
