"""Business logic for checking a posting.

Step 8: score with ml-service, then save to history.
Step 9 will add: rate limit -> cache lookup -> (ml-service only on a miss) -> cache store.
"""
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from ..clients.ml_client import MlClient
from ..models import Check
from ..repositories.check_repo import CheckRepository
from ..schemas import PostingIn

SNIPPET_CHARS = 200
_WHITESPACE = re.compile(r"\s+")


def normalize(posting: PostingIn) -> str:
    """The same message pasted with different spacing or capitals should count as the
    same message, so the hash (and in Step 9 the cache) treats them as identical."""
    parts = [posting.title, posting.company_profile, posting.description,
             posting.requirements, posting.benefits, posting.salary_range]
    return _WHITESPACE.sub(" ", " ".join(parts)).strip().lower()


def text_hash(posting: PostingIn) -> str:
    """SHA-256 = a 64-character fingerprint. Same text -> same hash, always.
    We store this instead of comparing whole postings."""
    return hashlib.sha256(normalize(posting).encode()).hexdigest()


@dataclass
class CheckResult:
    check: Check              # the saved row
    limited_info: bool        # returned to the user, not stored
    note: str | None


class CheckService:
    def __init__(self, session: Session, ml: MlClient):
        self.session = session
        self.ml = ml
        self.checks = CheckRepository(session)

    def check(self, user_id: int, posting: PostingIn) -> CheckResult:
        # 1. Score it. Raises MlServiceUnavailable if ml-service is down: then nothing is saved.
        verdict = self.ml.predict(posting.model_dump())

        # 2. Save to the user's history
        check = self.checks.add(
            user_id=user_id,
            text_hash=text_hash(posting),
            title=posting.title or None,
            snippet=posting.description[:SNIPPET_CHARS],
            score=verdict["score"],
            verdict=verdict["label"],
            flags=verdict["flags"],
            model_version=verdict["model_version"],
            cache_hit=False,
        )
        self.session.commit()
        return CheckResult(check=check, limited_info=verdict["limited_info"], note=verdict["note"])

    def history(self, user_id: int, limit: int, before: datetime | None) -> tuple[list[Check], datetime | None]:
        items = self.checks.list_for_user(user_id, limit, before)
        # A full page means there may be more: the next page starts before the oldest item shown
        next_before = items[-1].created_at if len(items) == limit else None
        return items, next_before
