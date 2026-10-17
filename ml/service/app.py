"""ml-service: a small HTTP API around the rule engine + trained model.

The main API (Step 7+) calls this over the internal network. Keeping ML in its own
service means it can be scaled, restarted or replaced without touching the API.

Run locally (from the ml/ folder):  uvicorn service.app:app --reload --port 8001
"""
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
from fastapi import FastAPI
from pydantic import BaseModel, Field

from fakehire_ml.model import to_frame
from fakehire_ml.posting import Posting
from fakehire_ml.rules import RuleEngine
from fakehire_ml.scoring import combine

# Configuration comes from environment variables (12-factor app), with a local default.
MODELS_DIR = Path(os.getenv("MODELS_DIR", Path(__file__).resolve().parent.parent / "models"))
POINTER = MODELS_DIR / "current.json"     # written by retrain.py when a new model passes the gate
MODEL_PATH = Path(os.getenv("MODEL_PATH", MODELS_DIR / "model_v1.1.joblib"))   # used if there's no pointer
RELOAD_CHECK_SECONDS = 10

log = logging.getLogger("uvicorn.error")

LIMITED_NOTE = ("Only a short snippet was given, so this verdict is less reliable. "
                "Paste the full posting, including the company description, for a better check.")

state: dict = {}
_reload_lock = threading.Lock()


def _pointer_mtime() -> float | None:
    return POINTER.stat().st_mtime if POINTER.exists() else None


def load_model() -> None:
    """Load whichever model current.json points at (or MODEL_PATH if there's no pointer)."""
    path = MODELS_DIR / json.loads(POINTER.read_text())["file"] if POINTER.exists() else MODEL_PATH
    bundle = joblib.load(path)
    # ONE assignment swaps pipeline and version together, so a request running during a
    # reload can never pair the new version number with the old pipeline.
    state["model"] = (bundle["pipeline"], bundle["version"])
    state["pointer_mtime"] = _pointer_mtime()
    state["checked_at"] = time.monotonic()
    log.info("Serving model %s from %s", bundle["version"], path.name)


def reload_if_changed() -> None:
    """HOT RELOAD: every ~10 s, check whether current.json changed; if so, load the new model.
    No restart, no dropped requests. A broken new model is logged and the old one keeps serving."""
    if time.monotonic() - state["checked_at"] < RELOAD_CHECK_SECONDS:
        return
    with _reload_lock:                       # several requests may arrive at once; reload only once
        state["checked_at"] = time.monotonic()
        if _pointer_mtime() == state["pointer_mtime"]:
            return
        try:
            load_model()
        except Exception:
            log.exception("New model failed to load; still serving %s", state["model"][1])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model ONCE at startup, not on every request (loading takes ~1 s).
    load_model()
    state["rules"] = RuleEngine()
    yield
    state.clear()


app = FastAPI(title="FakeHire ml-service", version="1.0", lifespan=lifespan)


# ---------- request / response shapes (Pydantic validates them for us) ----------

class PostingIn(BaseModel):
    title: str = Field("", max_length=300)
    company_profile: str = Field("", max_length=5000)
    description: str = Field(..., min_length=20, max_length=10_000)
    requirements: str = Field("", max_length=5000)
    benefits: str = Field("", max_length=5000)
    salary_range: str = Field("", max_length=100)

    model_config = {"json_schema_extra": {"example": {
        "title": "Data Entry Work From Home",
        "description": "No interview needed! Earn Rs 30000 per month from home. Pay a registration "
                       "fee of Rs 1999 to confirm your seat. Message HR on WhatsApp 9876543210.",
    }}}


class Flag(BaseModel):
    rule: str
    message: str


class VerdictOut(BaseModel):
    score: int
    label: str
    p_model: float
    rule_score: float
    flags: list[Flag]
    model_version: str
    limited_info: bool
    note: str | None = None
    took_ms: float

    # Pydantic reserves names starting with "model_"; we really do mean model_version
    model_config = {"protected_namespaces": ()}


# ---------- endpoints ----------

@app.get("/health")
def health():
    """Used by Docker (and the API, to build cache keys) to ask: alive, and which model?"""
    reload_if_changed()
    return {"status": "ok", "model_version": state["model"][1]}


@app.post("/predict", response_model=VerdictOut)
def predict(body: PostingIn):
    start = time.perf_counter()
    reload_if_changed()
    pipeline, version = state["model"]
    posting = Posting(**body.model_dump())

    p_model = float(pipeline.predict_proba(to_frame([posting]))[0, 1])
    verdict = combine(p_model, state["rules"].evaluate(posting))

    return VerdictOut(
        score=verdict.score,
        label=verdict.label,
        p_model=verdict.p_model,
        rule_score=verdict.rule_score,
        flags=[Flag(rule=h.rule, message=h.message) for h in verdict.flags],
        model_version=version,
        limited_info=posting.is_limited,
        note=LIMITED_NOTE if posting.is_limited else None,
        took_ms=round((time.perf_counter() - start) * 1000, 2),
    )
