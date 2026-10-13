"""ml-service: a small HTTP API around the rule engine + trained model.

The main API (Step 7+) calls this over the internal network. Keeping ML in its own
service means it can be scaled, restarted or replaced without touching the API.

Run locally (from the ml/ folder):  uvicorn service.app:app --reload --port 8001
"""
import os
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
MODEL_PATH = Path(os.getenv("MODEL_PATH", Path(__file__).resolve().parent.parent / "models" / "model_v1.0.joblib"))

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model ONCE at startup, not on every request (loading takes ~1 s).
    bundle = joblib.load(MODEL_PATH)
    state["pipeline"] = bundle["pipeline"]
    state["version"] = bundle["version"]
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
    took_ms: float

    # Pydantic reserves names starting with "model_"; we really do mean model_version
    model_config = {"protected_namespaces": ()}


# ---------- endpoints ----------

@app.get("/health")
def health():
    """Used by Docker (and later Nginx) to ask: are you alive and is the model loaded?"""
    return {"status": "ok", "model_version": state.get("version")}


@app.post("/predict", response_model=VerdictOut)
def predict(body: PostingIn):
    start = time.perf_counter()
    posting = Posting(**body.model_dump())

    p_model = float(state["pipeline"].predict_proba(to_frame([posting]))[0, 1])
    verdict = combine(p_model, state["rules"].evaluate(posting))

    return VerdictOut(
        score=verdict.score,
        label=verdict.label,
        p_model=verdict.p_model,
        rule_score=verdict.rule_score,
        flags=[Flag(rule=h.rule, message=h.message) for h in verdict.flags],
        model_version=state["version"],
        took_ms=round((time.perf_counter() - start) * 1000, 2),
    )
