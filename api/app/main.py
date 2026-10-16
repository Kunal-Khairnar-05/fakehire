"""FakeHire API entry point.

Run locally (from the api/ folder):  python -m uvicorn app.main:app --reload --port 8000
"""
import socket
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.orm import Session

from .clients.ml_client import MlClient
from .core.config import settings
from .db import get_session
from .deps import get_redis
from .routes import auth, checks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: shared clients for the whole process
    app.state.ml_client = MlClient(settings.ml_service_url, settings.ml_timeout_seconds)
    # Short timeouts: if Redis is down we want to give up in 0.25 s and fail open,
    # not add seconds to every request.
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True,
                                     socket_timeout=0.25, socket_connect_timeout=0.25)
    yield
    # Shutdown: close open connections cleanly
    app.state.ml_client.close()
    app.state.redis.close()


app = FastAPI(title="FakeHire API", version="1.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(checks.router)


@app.get("/health", tags=["ops"])
def health(session: Session = Depends(get_session), redis: Redis = Depends(get_redis)):
    """Alive AND able to reach the database. 'instance' = which container answered
    (useful in Step 10 to watch the load balancer spread requests).
    Redis being down doesn't make us unhealthy: we fail open without it."""
    session.execute(text("SELECT 1"))
    try:
        redis.ping()
        redis_status = "ok"
    except RedisError:
        redis_status = "down"
    return {"status": "ok", "instance": socket.gethostname(), "redis": redis_status}
