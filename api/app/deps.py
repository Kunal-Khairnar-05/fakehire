"""FastAPI dependencies: small functions that routes declare they need.

FastAPI calls them for every request and passes the results in. This is
dependency injection: routes never build their own sessions or services, which
is also what lets tests swap in a test database.
"""
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from redis import Redis
from sqlalchemy.orm import Session

from .clients.ml_client import MlClient
from .core.config import settings
from .core.security import decode_access_token
from .db import get_session
from .models import User
from .repositories.user_repo import UserRepository
from .services.auth_service import AuthService
from .services.cache import VerdictCache
from .services.check_service import CheckService
from .services.rate_limiter import RateLimiter
from .services.report_service import ReportService

# Reads "Authorization: Bearer <token>" from the request. tokenUrl tells Swagger where to log in.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_auth_service(session: Session = Depends(get_session)) -> AuthService:
    return AuthService(session)


def get_ml_client(request: Request) -> MlClient:
    """The one shared client created at startup (see main.py). Tests replace it with a fake."""
    return request.app.state.ml_client


def get_redis(request: Request) -> Redis:
    """The one shared Redis client created at startup. Tests replace it with fakeredis."""
    return request.app.state.redis


def get_check_service(session: Session = Depends(get_session),
                      ml: MlClient = Depends(get_ml_client),
                      redis: Redis = Depends(get_redis)) -> CheckService:
    return CheckService(session, ml, VerdictCache(redis, settings.cache_ttl_seconds))


def get_rate_limiter(redis: Redis = Depends(get_redis)) -> RateLimiter:
    return RateLimiter(redis, settings.rate_limit_per_minute)


def get_token_claims(token: str = Depends(oauth2_scheme)) -> dict:
    """Checks the token's signature and expiry. NO database call: this is what lets
    any API replica authenticate any request on its own."""
    try:
        return decode_access_token(token)
    except jwt.PyJWTError:
        raise UNAUTHORIZED


def get_current_user(claims: dict = Depends(get_token_claims),
                     session: Session = Depends(get_session)) -> User:
    """Claims + the full user row, for endpoints that need user details (like /me)."""
    user = UserRepository(session).get_by_id(int(claims["sub"]))
    if user is None:          # token is valid but the account was deleted
        raise UNAUTHORIZED
    return user


def enforce_rate_limit(claims: dict = Depends(get_token_claims),
                       limiter: RateLimiter = Depends(get_rate_limiter)) -> None:
    """Runs before the route. Over the limit -> 429 + Retry-After header (seconds)."""
    wait = limiter.hit(int(claims["sub"]))
    if wait is not None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many checks. Try again in {wait} seconds.",
                            headers={"Retry-After": str(wait)})


def get_report_service(session: Session = Depends(get_session)) -> ReportService:
    return ReportService(session)


def require_role(*allowed: str):
    """Role-based access control (RBAC). Usage:  Depends(require_role("moderator", "admin"))

    The role comes from the signed JWT, so no database call is needed. Trade-off: a role
    change takes effect at the user's next login (tokens last 60 minutes)."""
    def check_role(claims: dict = Depends(get_token_claims)) -> dict:
        if claims.get("role") not in allowed:
            # 403 = "I know who you are, and you're not allowed" (401 = "who are you?")
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do this")
        return claims
    return check_role
