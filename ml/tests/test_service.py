"""API tests for the ml-service. Needs a trained model (run ml/train.py first)."""
import json

import joblib
import pytest
from fastapi.testclient import TestClient

import service.app as ml_app
from service.app import MODEL_PATH, app

pytestmark = pytest.mark.skipif(not MODEL_PATH.exists(), reason="no trained model; run ml/train.py")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:   # "with" runs the startup code that loads the model
        yield c


def test_health_reports_model_version(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["model_version"].startswith("v1.")   # v1.1 baseline, or a retrained v1.N


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


def test_hot_reload_follows_the_pointer_and_survives_a_broken_model(tmp_path, monkeypatch):
    """retrain.py promotes a model by rewriting current.json; ml-service must switch to it
    without a restart, and must keep serving if the pointer names a broken file."""
    bundle = joblib.load(MODEL_PATH)
    joblib.dump(bundle, tmp_path / "model_v1.1.joblib")
    joblib.dump({**bundle, "version": "v1.9"}, tmp_path / "model_v1.9.joblib")
    (tmp_path / "model_v1.10.joblib").write_text("not a model")

    monkeypatch.setattr(ml_app, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(ml_app, "POINTER", tmp_path / "current.json")
    monkeypatch.setattr(ml_app, "MODEL_PATH", tmp_path / "model_v1.1.joblib")
    monkeypatch.setattr(ml_app, "RELOAD_CHECK_SECONDS", 0)       # check on every request

    with TestClient(app) as client:
        assert client.get("/health").json()["model_version"] == "v1.1"     # no pointer yet

        (tmp_path / "current.json").write_text(json.dumps({"file": "model_v1.9.joblib"}))
        assert client.get("/health").json()["model_version"] == "v1.9"     # hot-reloaded

        (tmp_path / "current.json").write_text(json.dumps({"file": "model_v1.10.joblib"}))
        assert client.get("/health").json()["model_version"] == "v1.9"     # broken file: old model stays


def test_internal_token_protects_predict_but_not_health(monkeypatch):
    monkeypatch.setattr(ml_app, "INTERNAL_TOKEN", "s3cret-token")
    body = {"description": "Pay a registration fee of Rs 1999 and message HR on WhatsApp."}
    with TestClient(app) as client:    # its own app start-up: other tests may have shut the shared one down
        assert client.post("/predict", json=body).status_code == 401
        assert client.post("/predict", json=body, headers={"X-Internal-Token": "wrong"}).status_code == 401
        assert client.post("/predict", json=body, headers={"X-Internal-Token": "s3cret-token"}).status_code == 200
        assert client.get("/health").status_code == 200        # monitoring stays open
