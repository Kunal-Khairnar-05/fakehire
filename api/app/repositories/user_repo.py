"""Repository layer: the ONLY place that knows how users are stored.

Services ask "get user by email"; they never write SQL. If storage changes,
only this file changes.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import User


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        # Uses the index that UNIQUE(email) created
        return self.session.scalar(select(User).where(User.email == email))

    def add(self, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self.session.add(user)
        self.session.flush()   # send the INSERT now so id/role/created_at are filled in
        return user
