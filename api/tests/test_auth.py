"""Integration tests: real HTTP requests -> real FastAPI -> real PostgreSQL (test database)."""
import jwt
from sqlalchemy import text

from app.core.config import settings


def register(client, email="asha@example.com", password="correct-horse-7"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


def login(client, email="asha@example.com", password="correct-horse-7"):
    # Login uses the OAuth2 form format: fields "username" and "password"
    return client.post("/api/v1/auth/login", data={"username": email, "password": password})


def test_register_returns_user_without_password(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "asha@example.com"
    assert body["role"] == "student"
    assert "password" not in body and "password_hash" not in body


def test_password_is_stored_as_bcrypt_hash(client, db):
    register(client)
    with db.connect() as conn:
        stored = conn.execute(text("SELECT password_hash FROM users")).scalar_one()
    assert stored != "correct-horse-7"
    assert stored.startswith("$2b$")          # bcrypt's signature prefix


def test_duplicate_email_is_rejected_case_insensitive(client):
    register(client, email="asha@example.com")
    r = register(client, email="ASHA@example.com")
    assert r.status_code == 409


def test_short_password_is_rejected(client):
    assert register(client, password="short").status_code == 422


def test_login_returns_working_token(client):
    register(client)
    r = login(client)
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "asha@example.com"


def test_wrong_password_and_unknown_email_look_identical(client):
    register(client)
    wrong_pw = login(client, password="wrong-password")
    no_user = login(client, email="nobody@example.com")
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_me_without_token_is_401(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_tampered_token_is_rejected(client):
    register(client)
    token = login(client).json()["access_token"]
    # Forge a token claiming to be an admin, signed with the WRONG secret
    forged = jwt.encode({"sub": "1", "role": "admin"}, "attacker-secret-" * 4, algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    # And a real token with one character changed
    broken = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {broken}"}).status_code == 401


def test_expired_token_is_rejected(client):
    register(client)
    expired = jwt.encode({"sub": "1", "role": "student", "exp": 0}, settings.jwt_secret, algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
