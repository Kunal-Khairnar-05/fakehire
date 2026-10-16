"""FakeHire API entry point.

Run locally (from the api/ folder):  python -m uvicorn app.main:app --reload --port 8000
"""
import socket
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .clients.ml_client import MlClient
from .core.config import settings
from .db import get_session
from .routes import auth, checks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: one shared ml-service client for the whole process
    app.state.ml_client = MlClient(settings.ml_service_url, settings.ml_timeout_seconds)
    yield
    # Shutdown: close its open connections cleanly
    app.state.ml_client.close()


app = FastAPI(title="FakeHire API", version="1.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(checks.router)


@app.get("/health", tags=["ops"])
def health(session: Session = Depends(get_session)):
    """Alive AND able to reach the database. 'instance' = which container answered
    (useful in Step 10 to watch the load balancer spread requests)."""
    session.execute(text("SELECT 1"))
    return {"status": "ok", "instance": socket.gethostname()}
