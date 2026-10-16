"""Test setup: run the API against a SEPARATE database (fakehire_test), wiped before each test."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db import get_session
from app.main import app


@pytest.fixture(scope="session")
def engine():
    if not settings.test_database_url:
        pytest.skip("TEST_DATABASE_URL is not set in .env")
    return create_engine(settings.test_database_url)


@pytest.fixture
def db(engine):
    """Direct database access for tests that inspect what was stored."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE checks, users RESTART IDENTITY CASCADE"))
    return engine


@pytest.fixture
def client(db):
    TestSession = sessionmaker(bind=db, expire_on_commit=False)

    def test_session():
        with TestSession() as session:
            yield session

    # Dependency injection pays off: swap the real database for the test one
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
