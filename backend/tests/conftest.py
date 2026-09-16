"""Test DB, client, and auth fixtures. Every test gets a fresh in-memory
SQLite database; nothing here touches the real Postgres database."""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings
from app.core.deps import get_db
from app.db import models  # noqa: F401  (registers tables on SQLModel.metadata)
from main import app


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    def get_db_override():
        yield session

    app.dependency_overrides[get_db] = get_db_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
def auth_headers(client):
    def _register(email: str = "a@example.com", password: str = "testpass123") -> dict:
        resp = client.post("/api/auth/register", json={"email": email, "password": password})
        assert resp.status_code == 201, resp.text
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _register
