"""API tests for the ml-service. Needs a trained model (run ml/train.py first)."""
import pytest
from fastapi.testclient import TestClient

from service.app import MODEL_PATH, app

pytestmark = pytest.mark.skipif(not MODEL_PATH.exists(), reason="no trained model; run ml/train.py")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:   # "with" runs the startup code that loads the model
        yield c


def test_health_reports_model_version(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["model_version"] == "v1.1"


def test_short_snippet_gets_limited_info_note(client):
    body = client.post("/predict", json={"description": "Data entry job, on site, 5 days per week."}).json()
    assert body["limited_info"] is True
    assert body["note"]


def test_full_posting_has_no_note(client):
    body = client.post("/predict", json={
        "company_profile": "Acme builds accounting software used by 2,000 Indian small businesses.",
        "description": "We are hiring a backend intern to work on our Python APIs. " * 6,
    }).json()
    assert body["limited_info"] is False
    assert body["note"] is None


def test_scam_message_is_flagged(client):
    r = client.post("/predict", json={
        "title": "Work from home",
        "description": "Pay a registration fee of Rs 1999 and message HR on WhatsApp 9876543210.",
    })
    body = r.json()
    assert r.status_code == 200
    assert body["label"] == "Likely scam"
    assert "asks_for_money" in {f["rule"] for f in body["flags"]}


def test_too_short_description_is_rejected(client):
    r = client.post("/predict", json={"description": "hi"})
    assert r.status_code == 422   # Pydantic validation error
