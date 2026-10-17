"""Web check: identifier extraction, evidence classification, caching, failure handling."""
from app.clients.search_client import SearchResult
from app.services.web_check import extract_identifiers

SCAM_TEXT = ("Earn Rs 800 per day. Pay Rs 499 deposit. Call +91 98765-43210 or mail "
             "HR.Jobs@gmail.com to join.")


def web_check(client, auth, description=SCAM_TEXT, company="Global Typing Solutions"):
    return client.post("/api/v1/web-check", headers=auth,
                       json={"posting": {"description": description}, "company_name": company})


# ---------- extracting what to search for ----------

def test_extracts_indian_phone_and_email_in_any_format():
    ids = extract_identifiers(SCAM_TEXT.lower(), "  Global   Typing Solutions ")
    assert ids.company == "Global Typing Solutions"
    assert ids.phones == ["9876543210"]
    assert ids.emails == ["hr.jobs@gmail.com"]


def test_nothing_to_search_without_company_phone_or_email(client, auth, search):
    body = web_check(client, auth, description="A normal posting with no contact details at all.", company=None).json()
    assert body["status"] == "nothing_to_search"
    assert search.calls == []              # no quota spent


# ---------- classifying results ----------

def test_complaints_are_found_and_listed_first(client, auth, search):
    search.results["scam OR fraud OR complaint"] = [
        SearchResult("Global Typing Solutions is a SCAM - consumer complaint", "https://example-forum.in/t/1",
                     "I paid Rs 499 for a job at Global Typing Solutions and never got work"),
        SearchResult("Typing jobs in Pune", "https://jobs.example.com/typing", "Unrelated typing jobs"),
    ]
    body = web_check(client, auth).json()
    assert body["status"] == "complaints_found"
    assert body["evidence"][0]["complaint"] is True
    assert body["evidence"][0]["domain"] == "example-forum.in"
    # The unrelated page doesn't mention the company, so it isn't evidence at all
    assert all("Unrelated" not in e["snippet"] for e in body["evidence"])


def test_phone_number_matches_even_when_written_with_spaces(client, auth, search):
    search.results['"9876543210"'] = [
        SearchResult("Fraud number list", "https://numbers.example.org/", "Beware of 98765 43210, fake job calls")]
    body = web_check(client, auth, company=None).json()
    assert body["status"] == "complaints_found"
    assert body["evidence"][0]["kind"] == "phone"


def test_no_reports_found(client, auth, search):
    body = web_check(client, auth).json()
    assert body["status"] == "no_reports_found"
    assert "isn't proof" in body["summary"]


def test_official_site_detected_but_job_boards_ignored(client, auth, search):
    search.results["official website"] = [
        SearchResult("Freightwise jobs - LinkedIn", "https://www.linkedin.com/company/freightwise", "..."),
        SearchResult("Freightwise | Logistics technology", "https://www.freightwise.in/", "Official site"),
    ]
    body = web_check(client, auth, company="Freightwise").json()
    assert body["official_site"]["domain"] == "freightwise.in"


def test_unsafe_links_are_dropped(client, auth, search):
    search.results["scam OR fraud OR complaint"] = [
        SearchResult("Global Typing Solutions scam", "javascript:alert(1)", "Global Typing Solutions fraud")]
    body = web_check(client, auth).json()
    assert body["evidence"] == []


# ---------- quota protection and failures ----------

def test_second_identical_web_check_uses_the_cache(client, auth, search):
    first = web_check(client, auth).json()
    calls_after_first = len(search.calls)
    second = web_check(client, auth).json()
    assert first["searches"] > 0
    assert second["searches"] == 0                     # everything from Redis
    assert len(search.calls) == calls_after_first      # no new API calls


def test_provider_down_returns_unavailable_not_an_error(client, auth, search):
    search.down = True
    r = web_check(client, auth)
    assert r.status_code == 200
    assert r.json()["status"] == "unavailable"


def test_web_check_requires_login(client):
    r = client.post("/api/v1/web-check", json={"posting": {"description": SCAM_TEXT}, "company_name": "X"})
    assert r.status_code == 401


# ---------- lessons from the first real run against Tavily ----------

def test_company_own_fraud_alert_page_is_not_a_complaint(client, auth, search):
    # Real case: Infosys's own "Recruitment Fraud Alert" page made a genuine company look like a scam
    search.results["scam OR fraud OR complaint"] = [
        SearchResult("Infosys Careers | Recruitment Fraud Alert", "https://www.infosys.com/careers/fraud.html",
                     "Infosys never asks candidates for money. Beware of fake job offers using our name.")]
    body = web_check(client, auth, description="A normal posting, no contact details here.", company="Infosys").json()
    assert body["status"] == "no_reports_found"
    assert body["evidence"][0]["official"] is True and body["evidence"][0]["complaint"] is False


def test_fraud_news_unrelated_to_jobs_is_not_a_complaint(client, auth, search):
    search.results["scam OR fraud OR complaint"] = [
        SearchResult("Infosys pays fine to settle tax fraud allegations", "https://news.example.com/a",
                     "Infosys agreed to pay a fine over tax fraud allegations.")]
    body = web_check(client, auth, description="A normal posting, no contact details here.", company="Infosys").json()
    assert body["status"] == "no_reports_found"


def test_recruiter_email_outside_the_official_domain_flags_impersonation(client, auth, search):
    search.results["official website"] = [
        SearchResult("Infosys | Navigate your next", "https://www.infosys.com/", "Official site")]
    body = web_check(client, auth, description="Offer letter attached. Reply to infosys.hr.desk@gmail.com today.",
                     company="Infosys").json()
    assert body["status"] == "impersonation_risk"
    assert "gmail.com" in body["summary"] and "infosys.com" in body["summary"]


def test_recruiter_on_the_official_domain_is_fine(client, auth, search):
    search.results["official website"] = [
        SearchResult("Infosys | Navigate your next", "https://www.infosys.com/", "Official site")]
    body = web_check(client, auth, description="Questions? Write to campus.hiring@careers.infosys.com",
                     company="Infosys").json()
    assert body["status"] == "no_reports_found"
