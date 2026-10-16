"""FastAPI dependencies: small functions that routes declare they need.

FastAPI calls them for every request and passes the results in. This is
dependency injection: routes never build their own sessions or services, which
is also what lets tests swap in a test database.
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .core.security import decode_access_token
from .db import get_session
from .models import User
from .repositories.user_repo import UserRepository
from .services.auth_service import AuthService

# Reads "Authorization: Bearer <token>" from the request. tokenUrl tells Swagger where to log in.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_auth_service(session: Session = Depends(get_session)) -> AuthService:
    return AuthService(session)


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
