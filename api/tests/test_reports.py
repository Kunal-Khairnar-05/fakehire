"""Scam reports and the moderator queue (fake ml-service, fake Redis, real test database)."""
from sqlalchemy import text

POSTING = {"title": "Data Entry", "description": "Pay a registration fee of Rs 1999 to confirm your seat today."}


def make_check(client, headers, title="Data Entry") -> int:
    return client.post("/api/v1/check", json={**POSTING, "title": title}, headers=headers).json()["id"]


def report(client, headers, check_id, company="Acme Jobs Pvt Ltd", reason="Asked me to pay a fee"):
    return client.post("/api/v1/reports", json={"check_id": check_id, "company_name": company, "reason": reason},
                       headers=headers)


# ---------- reporting ----------

def test_report_own_check_is_pending(client, auth):
    r = report(client, auth, make_check(client, auth))
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert r.json()["reviewed_at"] is None


def test_cannot_report_someone_elses_check(client, auth, new_user):
    other = new_user("ravi@example.com")
    their_check = make_check(client, other)
    # Same 404 as a check that doesn't exist: no hint that it belongs to someone else
    assert report(client, auth, their_check).status_code == 404
    assert report(client, auth, 999_999).status_code == 404


def test_same_check_reported_twice_is_409(client, auth):
    check_id = make_check(client, auth)
    report(client, auth, check_id)
    assert report(client, auth, check_id).status_code == 409


def test_company_name_is_validated_and_trimmed(client, auth):
    check_id = make_check(client, auth)
    assert report(client, auth, check_id, company="A").status_code == 422
    assert report(client, auth, check_id, company="   Acme Jobs   ").json()["company_name"] == "Acme Jobs"


def test_my_reports_lists_only_mine(client, auth, new_user):
    report(client, auth, make_check(client, auth))
    other = new_user("ravi@example.com")
    report(client, other, make_check(client, other))
    mine = client.get("/api/v1/reports/me", headers=auth).json()
    assert len(mine) == 1


# ---------- role-based access ----------

def test_queue_needs_login(client):
    assert client.get("/api/v1/reports/queue").status_code == 401


def test_students_cannot_see_or_review_the_queue(client, auth):
    report_id = report(client, auth, make_check(client, auth)).json()["id"]
    assert client.get("/api/v1/reports/queue", headers=auth).status_code == 403
    assert client.patch(f"/api/v1/reports/{report_id}", json={"status": "verified"}, headers=auth).status_code == 403


# ---------- moderation ----------

def test_queue_is_oldest_first_with_the_posting(client, auth, moderator):
    report(client, auth, make_check(client, auth, title="First"))
    report(client, auth, make_check(client, auth, title="Second"))
    items = client.get("/api/v1/reports/queue", headers=moderator).json()["items"]
    assert [i["title"] for i in items] == ["First", "Second"]
    assert items[0]["score"] == 87 and items[0]["snippet"].startswith("Pay a registration fee")


def test_queue_pagination(client, auth, moderator):
    for title in ["A", "B", "C"]:
        report(client, auth, make_check(client, auth, title=title))
    page1 = client.get("/api/v1/reports/queue?limit=2", headers=moderator).json()
    page2 = client.get("/api/v1/reports/queue", params={"limit": 2, "after": page1["next_after"]},
                       headers=moderator).json()
    assert [i["title"] for i in page1["items"]] == ["A", "B"]
    assert [i["title"] for i in page2["items"]] == ["C"]
    assert page2["next_after"] is None


def test_verify_records_who_and_when_and_leaves_the_queue(client, auth, moderator, db):
    report_id = report(client, auth, make_check(client, auth)).json()["id"]
    r = client.patch(f"/api/v1/reports/{report_id}", json={"status": "verified"}, headers=moderator)
    assert r.status_code == 200
    assert r.json()["status"] == "verified" and r.json()["reviewed_at"] is not None

    with db.connect() as conn:
        reviewer = conn.execute(text("SELECT u.email FROM reports r JOIN users u ON u.id = r.reviewed_by")).scalar_one()
    assert reviewer == "mod@example.com"
    assert client.get("/api/v1/reports/queue", headers=moderator).json()["items"] == []
    assert client.get("/api/v1/reports/me", headers=auth).json()[0]["status"] == "verified"


def test_a_report_cannot_be_reviewed_twice(client, auth, moderator):
    report_id = report(client, auth, make_check(client, auth)).json()["id"]
    client.patch(f"/api/v1/reports/{report_id}", json={"status": "rejected"}, headers=moderator)
    again = client.patch(f"/api/v1/reports/{report_id}", json={"status": "verified"}, headers=moderator)
    assert again.status_code == 409


def test_review_errors(client, moderator, auth):
    report_id = report(client, auth, make_check(client, auth)).json()["id"]
    assert client.patch("/api/v1/reports/999999", json={"status": "verified"}, headers=moderator).status_code == 404
    assert client.patch(f"/api/v1/reports/{report_id}", json={"status": "maybe"}, headers=moderator).status_code == 422


# ---------- posting text for retraining (004) ----------

def test_report_stores_the_checked_posting(client, auth, db):
    check_id = make_check(client, auth)
    r = client.post("/api/v1/reports", headers=auth, json={
        "check_id": check_id, "company_name": "Acme", "posting": {**POSTING, "title": "Data Entry"}})
    assert r.status_code == 201
    with db.connect() as conn:
        stored = conn.execute(text("SELECT posting FROM reports")).scalar_one()
    assert stored["description"] == POSTING["description"]


def test_same_text_with_different_spacing_still_matches(client, auth):
    check_id = make_check(client, auth)
    messy = {"title": "  DATA entry ", "description": "PAY a registration fee of Rs 1999   to confirm your seat today."}
    r = client.post("/api/v1/reports", headers=auth,
                    json={"check_id": check_id, "company_name": "Acme", "posting": messy})
    assert r.status_code == 201


def test_report_with_different_text_is_rejected(client, auth, db):
    check_id = make_check(client, auth)
    poisoned = {"title": "Data Entry", "description": "A perfectly normal software engineering internship posting."}
    r = client.post("/api/v1/reports", headers=auth,
                    json={"check_id": check_id, "company_name": "Acme", "posting": poisoned})
    assert r.status_code == 422
    with db.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM reports")).scalar_one() == 0


def test_report_without_posting_is_stored_as_sql_null(client, auth, db):
    # Regression: Python None used to be stored as JSON null, which "IS NOT NULL" lets through
    report(client, auth, make_check(client, auth))
    with db.connect() as conn:
        assert conn.execute(text("SELECT posting IS NULL FROM reports")).scalar_one() is True
