"""Trending scam companies and company search."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import Company
from ..repositories.company_repo import CompanyRepository
from .trending import TrendingBoard


@dataclass
class TrendingEntry:
    company: Company
    this_week: int | None      # None when served from the database fallback


class CompanyService:
    def __init__(self, session: Session, trending: TrendingBoard):
        self.companies = CompanyRepository(session)
        self.trending = trending

    def trending_now(self, limit: int) -> tuple[list[TrendingEntry], str]:
        """Returns (entries, source). source = "live" (Redis, this week) or "fallback" (database, all time)."""
        top = self.trending.top(limit)
        if top is None:
            return [TrendingEntry(c, None) for c in self.companies.most_reported(limit)], "fallback"

        # Redis knows ids + weekly counts; the names live in Postgres. One query for all of them.
        by_id = self.companies.get_many([company_id for company_id, _ in top])
        entries = [TrendingEntry(by_id[cid], count) for cid, count in top if cid in by_id]
        return entries, "live"

    def search(self, text: str, limit: int) -> list[Company]:
        return self.companies.search(text, limit)
