"""FakeHire API entry point.

Run locally (from the api/ folder):  python -m uvicorn app.main:app --reload --port 8000
"""
import socket

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_session
from .routes import auth

app = FastAPI(title="FakeHire API", version="1.0")
app.include_router(auth.router)


@app.get("/health", tags=["ops"])
def health(session: Session = Depends(get_session)):
    """Alive AND able to reach the database. 'instance' = which container answered
    (useful in Step 10 to watch the load balancer spread requests)."""
    session.execute(text("SELECT 1"))
    return {"status": "ok", "instance": socket.gethostname()}
