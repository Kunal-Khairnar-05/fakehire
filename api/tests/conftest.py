"""Test setup: run the API against a SEPARATE database (fakehire_test), wiped before each test,
a FAKE ml-service and an in-memory fake Redis, so API tests need neither container running."""
import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.clients.ml_client import MlServiceUnavailable
from app.core.config import settings
from app.db import get_session
from app.deps import get_ml_client, get_rate_limiter, get_redis
from app.main import app
from app.services.rate_limiter import RateLimiter

TEST_RATE_LIMIT = 5

SCAM_VERDICT = {
    "score": 87, "label": "Likely scam", "p_model": 0.9, "rule_score": 0.95,
    "flags": [{"rule": "asks_for_money", "message": "Asks you to pay a fee or deposit."}],
    "model_version": "v1.1", "limited_info": True, "note": "Only a short snippet was given.", "took_ms": 5.0,
}


class FakeMlClient:
    """Stands in for the real ml-service. Same method, canned answer, counts calls."""

    def __init__(self):
        self.calls = 0
        self.down = False
        self.response = SCAM_VERDICT

    def predict(self, posting: dict) -> dict:
        self.calls += 1
        if self.down:
            raise MlServiceUnavailable("simulated outage")
        return self.response

    def current_version(self) -> str:
        # Like the real client: still knows the last version even while "down"
        return self.response["model_version"]

    def close(self):
        pass


@pytest.fixture(scope="session")
def engine():
    if not settings.test_database_url:
        pytest.skip("TEST_DATABASE_URL is not set in .env")
    return create_engine(settings.test_database_url)


@pytest.fixture
def db(engine):
    """Direct database access for tests that inspect what was stored."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE checks, users, companies RESTART IDENTITY CASCADE"))
    return engine


@pytest.fixture
def ml():
    return FakeMlClient()


@pytest.fixture
def rate_limit():
    """Checks allowed per minute in tests (the real default is 30)."""
    return TEST_RATE_LIMIT


@pytest.fixture
def redis():
    """A fresh, empty in-memory Redis for every test."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def client(db, ml, redis):
    TestSession = sessionmaker(bind=db, expire_on_commit=False)

    def test_session():
        with TestSession() as session:
            yield session

    # Dependency injection pays off: swap the real database, ml-service and Redis for test ones
    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[get_ml_client] = lambda: ml
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(redis, TEST_RATE_LIMIT)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_user(client, email: str) -> dict:
    """Register + log in. Returns the Authorization header for that user."""
    client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-7"})
    token = client.post("/api/v1/auth/login",
                        data={"username": email, "password": "correct-horse-7"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth(client):
    return make_user(client, "asha@example.com")


@pytest.fixture
def moderator(client, db):
    """Headers for a moderator. The role must be set BEFORE login, because it's baked into the token."""
    email = "mod@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-7"})
    with db.begin() as conn:
        conn.execute(text("UPDATE users SET role = 'moderator' WHERE email = :e"), {"e": email})
    token = client.post("/api/v1/auth/login",
                        data={"username": email, "password": "correct-horse-7"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def new_user(client):
    """Call new_user("ravi@example.com") inside a test to get a second user's headers."""
    return lambda email: make_user(client, email)
