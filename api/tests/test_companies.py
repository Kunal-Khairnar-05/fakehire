"""Verified-scam companies: atomic counting, trending (Redis sorted set) and full-text search."""
import redis as redis_lib
from sqlalchemy import text

from app.deps import get_redis
from app.main import app

POSTING = {"title": "Data Entry", "description": "Pay a registration fee of Rs 1999 to confirm your seat today."}


def reported(client, headers, company: str) -> int:
    """One user: check a posting, report it under `company`. Returns the report id."""
    check_id = client.post("/api/v1/check", json=POSTING, headers=headers).json()["id"]
    return client.post("/api/v1/reports", json={"check_id": check_id, "company_name": company},
                       headers=headers).json()["id"]


def verify(client, moderator, report_id, decision="verified"):
    return client.patch(f"/api/v1/reports/{report_id}", json={"status": decision}, headers=moderator)


def companies_in_db(db):
    with db.connect() as conn:
        return conn.execute(text("SELECT name, verified_reports FROM companies ORDER BY name")).all()


# ---------- counting ----------

def test_verifying_creates_the_company(client, auth, moderator, db):
    verify(client, moderator, reported(client, auth, "Global Typing Solutions"))
    assert companies_in_db(db) == [("Global Typing Solutions", 1)]


def test_same_company_written_differently_is_counted_once(client, auth, new_user, moderator, db):
    verify(client, moderator, reported(client, auth, "Global Typing Solutions"))
    other = new_user("ravi@example.com")
    verify(client, moderator, reported(client, other, "  global   TYPING solutions "))
    assert companies_in_db(db) == [("Global Typing Solutions", 2)]


def test_rejected_and_pending_reports_are_not_counted(client, auth, new_user, moderator, db):
    verify(client, moderator, reported(client, auth, "Honest Corp"), decision="rejected")
    reported(client, new_user("ravi@example.com"), "Pending Corp")      # never reviewed
    assert companies_in_db(db) == []


# ---------- trending ----------

def test_trending_is_public_and_ranked_by_this_weeks_reports(client, auth, new_user, moderator):
    verify(client, moderator, reported(client, auth, "Alpha Jobs"))
    for email in ["b1@example.com", "b2@example.com"]:
        verify(client, moderator, reported(client, new_user(email), "Beta Hiring"))

    body = client.get("/api/v1/trending").json()          # no Authorization header
    assert body["source"] == "live"
    assert [(i["name"], i["this_week"]) for i in body["items"]] == [("Beta Hiring", 2), ("Alpha Jobs", 1)]


def test_trending_falls_back_to_database_when_redis_is_down(client, auth, moderator):
    verify(client, moderator, reported(client, auth, "Alpha Jobs"))
    app.dependency_overrides[get_redis] = lambda: redis_lib.Redis(port=1, socket_connect_timeout=0.1,
                                                                  socket_timeout=0.1)
    body = client.get("/api/v1/trending").json()
    assert body["source"] == "fallback"
    assert body["items"][0]["name"] == "Alpha Jobs" and body["items"][0]["this_week"] is None


def test_verify_still_works_when_redis_is_down(client, auth, moderator, db):
    report_id = reported(client, auth, "Alpha Jobs")
    app.dependency_overrides[get_redis] = lambda: redis_lib.Redis(port=1, socket_connect_timeout=0.1,
                                                                  socket_timeout=0.1)
    assert verify(client, moderator, report_id).status_code == 200
    assert companies_in_db(db) == [("Alpha Jobs", 1)]     # Postgres, the source of truth, is correct


# ---------- search ----------

def test_search_by_word_prefixes(client, auth, new_user, moderator):
    verify(client, moderator, reported(client, auth, "Global Typing Solutions"))
    verify(client, moderator, reported(client, new_user("ravi@example.com"), "QuickHire Data Services"))

    def names(q):
        return [c["name"] for c in client.get("/api/v1/companies/search", params={"q": q}).json()]

    assert names("glob") == ["Global Typing Solutions"]
    assert names("TYPING sol") == ["Global Typing Solutions"]      # case-insensitive, word prefixes
    assert names("quickhire data") == ["QuickHire Data Services"]
    assert names("amazon") == []


def test_search_input_cannot_break_the_query(client):
    # '&', '|', '!' and ':' are operators in tsquery syntax; they must not cause a 500
    for q in ["glob & | !", "a:*b", "!!", "%%", "' OR 1=1 --"]:
        assert client.get("/api/v1/companies/search", params={"q": q}).status_code == 200


def test_search_needs_two_characters(client):
    assert client.get("/api/v1/companies/search", params={"q": "g"}).status_code == 422
