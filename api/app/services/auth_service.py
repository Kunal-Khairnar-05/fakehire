"""Service layer: the business rules of signing up and signing in.

No HTTP here (no status codes, no requests). It raises plain Python exceptions and
the route layer decides which HTTP error they become. That keeps this code easy to
test and reusable from anywhere (a CLI, a background job...).
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.security import create_access_token, hash_password, verify_password
from ..models import User
from ..repositories.user_repo import UserRepository


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


# Used when the email doesn't exist, so a failed login takes the same time either way.
# Otherwise an attacker could tell "no such account" (fast) from "wrong password" (slow).
_DUMMY_HASH = hash_password("timing-attack-protection")


class AuthService:
    def __init__(self, session: Session):
        self.session = session
        self.users = UserRepository(session)

    def register(self, email: str, password: str) -> User:
        try:
            user = self.users.add(email.lower(), hash_password(password))
            self.session.commit()
            return user
        except IntegrityError:
            # We don't check "does this email exist?" first and then insert: two requests
            # at the same moment could both pass the check. The UNIQUE constraint in the
            # database is the real guarantee, so we just try and handle the violation.
            self.session.rollback()
            raise EmailAlreadyRegistered()

    def login(self, email: str, password: str) -> str:
        user = self.users.get_by_email(email.lower())
        password_hash = user.password_hash if user else _DUMMY_HASH
        if not verify_password(password, password_hash) or user is None:
            raise InvalidCredentials()
        return create_access_token(user.id, user.role)
