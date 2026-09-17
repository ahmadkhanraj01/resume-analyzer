"""Test DB, client, and auth fixtures. Every test gets a fresh in-memory
SQLite database; nothing here touches the real Postgres database."""

import os
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-at-least-32-bytes")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core import limiter as limiter_module
from app.core.config import get_settings
from app.core.deps import get_db
from app.db import models  # noqa: F401  (registers tables on SQLModel.metadata)
from app.services import llm
from main import app


@pytest.fixture(autouse=True)
def no_live_llm():
    """Blocks the two provider calls so nothing in the suite reaches the
    network even with provider keys in .env. Every helper above them
    (extract_skills_llm, infer_role_profile, generate_report) still runs
    its real parse and fallback logic and sees a failed provider. Tests
    that want a specific response patch _call_groq or _call_gemini, or the
    helper itself; an inner patch wins. Before this, router tests made live calls whenever .env had keys,
    which broke the no-live-LLM rule in CLAUDE.md and made one test flaky."""

    def _blocked(*_args, **_kwargs):
        raise RuntimeError("live LLM calls are disabled in tests")

    with (
        patch.object(llm, "_call_groq", _blocked),
        patch.object(llm, "_call_gemini", _blocked),
    ):
        yield


@pytest.fixture(autouse=True)
def fresh_rate_limiters():
    """The limiters are module globals keyed by user id, and every test
    registers the same address, so without this a test's 429 depends on
    how many analyses earlier tests ran."""
    limiter_module._limiter = None
    limiter_module._auth_limiter = None
    yield
    limiter_module._limiter = None
    limiter_module._auth_limiter = None


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
