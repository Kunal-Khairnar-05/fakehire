"""Repository for the checks table."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Check


class CheckRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, **fields) -> Check:
        check = Check(**fields)
        self.session.add(check)
        self.session.flush()
        return check

    def list_for_user(self, user_id: int, limit: int, before: datetime | None = None) -> list[Check]:
        """Newest first. Served by the (user_id, created_at DESC) index from 001_init.sql.

        Pagination is KEYSET ("give me 20 older than this time"), not OFFSET
        ("skip 400, give me 20"). OFFSET makes Postgres read and throw away all the
        skipped rows, so page 50 is slow. Keyset jumps straight to the right spot
        in the index, so every page is equally fast.
        """
        query = select(Check).where(Check.user_id == user_id)
        if before is not None:
            query = query.where(Check.created_at < before)
        query = query.order_by(Check.created_at.desc()).limit(limit)
        return list(self.session.scalars(query))
