"""Password hashing (bcrypt) and access tokens (JWT)."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings

ALGORITHM = "HS256"


# ---------- passwords ----------
# bcrypt is deliberately SLOW (~0.2 s per hash) and adds a random "salt" to every hash.
# Slow = an attacker who steals the database can only try a few guesses per second.
# Salt = two users with the same password still get different hashes.

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# ---------- JWT ----------
# A JWT is three base64 parts: header.payload.signature
# The payload (user id, role, expiry) is readable by anyone, NOT encrypted.
# The signature proves the server created it: changing one character of the payload
# breaks the signature. So any API replica holding the same secret can trust it
# without asking the database. That is what makes the API stateless.

def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),        # "subject": who this token is about
        "role": role,
        "iat": now,                 # issued at
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),  # expiry
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Returns the payload, or raises jwt.PyJWTError if forged, tampered or expired."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
