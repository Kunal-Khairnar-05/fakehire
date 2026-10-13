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
    assert r.json()["model_version"] == "v1.0"


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
