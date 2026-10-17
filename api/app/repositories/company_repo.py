"""Repository for companies with verified scam reports."""
import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models import Company

_WORD = re.compile(r"[a-z0-9]+")


def name_key(name: str) -> str:
    """Same rule as the SQL in 003_companies.sql: lowercase, single spaces."""
    return " ".join(name.split()).lower()


class CompanyRepository:
    def __init__(self, session: Session):
        self.session = session

    def count_verified_report(self, name: str) -> int:
        """ATOMIC UPSERT: create the company, or add 1 to its count, in ONE statement.

        INSERT ... ON CONFLICT (name_key) DO UPDATE ...
        "Check if it exists, then insert or update" in Python would break when two
        moderators verify the same company at the same moment (both see "doesn't exist",
        both insert, one crashes on the UNIQUE key). Postgres does it safely in one step.
        """
        now = datetime.now(timezone.utc)
        stmt = insert(Company).values(name=" ".join(name.split()), name_key=name_key(name),
                                      verified_reports=1, last_reported_at=now)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Company.name_key],
            set_={"verified_reports": Company.verified_reports + 1, "last_reported_at": now},
        ).returning(Company.id)
        return self.session.execute(stmt).scalar_one()

    def get_many(self, ids: list[int]) -> dict[int, Company]:
        rows = self.session.scalars(select(Company).where(Company.id.in_(ids)))
        return {c.id: c for c in rows}

    def most_reported(self, limit: int) -> list[Company]:
        """Fallback for 'trending' when Redis is unavailable: all-time, most recent first."""
        query = (select(Company)
                 .order_by(Company.verified_reports.desc(), Company.last_reported_at.desc().nulls_last())
                 .limit(limit))
        return list(self.session.scalars(query))

    def search(self, text: str, limit: int) -> list[Company]:
        """Full-text prefix search: 'glob typ' -> to_tsquery('glob:* & typ:*').

        Only letters and digits are kept, so user input can never break the tsquery
        syntax ('&', '|', '!' and ':' are operators there). Served by the GIN index.
        """
        words = _WORD.findall(text.lower())
        if not words:
            return []
        tsquery = func.to_tsquery("simple", " & ".join(f"{w}:*" for w in words))
        query = (select(Company)
                 .where(Company.search.op("@@")(tsquery))          # @@ = "matches"
                 .order_by(func.ts_rank(Company.search, tsquery).desc(), Company.verified_reports.desc())
                 .limit(limit))
        return list(self.session.scalars(query))
