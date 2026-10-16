"""Integration tests for POST /check and GET /checks/me (fake ml-service, real test database)."""
from sqlalchemy import text

POSTING = {"title": "Data Entry", "description": "Pay a registration fee of Rs 1999 to confirm your seat today."}


def test_check_requires_login(client):
    assert client.post("/api/v1/check", json=POSTING).status_code == 401


def test_check_returns_verdict_and_saves_it(client, auth, db):
    r = client.post("/api/v1/check", json=POSTING, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == 87
    assert body["verdict"] == "Likely scam"
    assert body["flags"][0]["rule"] == "asks_for_money"
    assert body["cache_hit"] is False

    with db.connect() as conn:
        row = conn.execute(text("SELECT user_id, text_hash, snippet, model_version FROM checks")).one()
    assert row.user_id == 1
    assert len(row.text_hash) == 64
    assert row.snippet.startswith("Pay a registration fee")
    assert row.model_version == "v1.1"


def test_same_text_with_different_spacing_and_case_has_same_hash(client, auth, db):
    client.post("/api/v1/check", json=POSTING, headers=auth)
    messy = {"title": "  DATA   entry ",
             "description": "PAY a registration fee of Rs 1999\n\nto confirm your seat today."}
    client.post("/api/v1/check", json=messy, headers=auth)
    with db.connect() as conn:
        hashes = conn.execute(text("SELECT DISTINCT text_hash FROM checks")).all()
    assert len(hashes) == 1


def test_invalid_input_never_reaches_ml_service(client, auth, ml):
    r = client.post("/api/v1/check", json={"description": "too short"}, headers=auth)
    assert r.status_code == 422
    assert ml.calls == 0


def test_ml_service_down_returns_503_and_saves_nothing(client, auth, ml, db):
    ml.down = True
    r = client.post("/api/v1/check", json=POSTING, headers=auth)
    assert r.status_code == 503
    with db.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM checks")).scalar_one() == 0


def test_history_is_newest_first_and_only_mine(client, auth, new_user):
    for i in range(3):
        client.post("/api/v1/check", json={**POSTING, "title": f"Job {i}"}, headers=auth)
    other = new_user("ravi@example.com")
    client.post("/api/v1/check", json={**POSTING, "title": "Ravi's job"}, headers=other)

    items = client.get("/api/v1/checks/me", headers=auth).json()["items"]
    assert [i["title"] for i in items] == ["Job 2", "Job 1", "Job 0"]


def test_history_pagination_with_before_cursor(client, auth):
    for i in range(5):
        client.post("/api/v1/check", json={**POSTING, "title": f"Job {i}"}, headers=auth)

    page1 = client.get("/api/v1/checks/me?limit=2", headers=auth).json()
    assert [i["title"] for i in page1["items"]] == ["Job 4", "Job 3"]

    page2 = client.get("/api/v1/checks/me", params={"limit": 2, "before": page1["next_before"]},
                       headers=auth).json()
    assert [i["title"] for i in page2["items"]] == ["Job 2", "Job 1"]

    page3 = client.get("/api/v1/checks/me", params={"limit": 2, "before": page2["next_before"]},
                       headers=auth).json()
    assert [i["title"] for i in page3["items"]] == ["Job 0"]
    assert page3["next_before"] is None
