"""Business logic for checking a posting.

    hash the text -> look in the cache -> HIT:  use the cached verdict (no ml-service call)
                                       -> MISS: ask ml-service, store the answer in the cache
                  -> save to history either way

(The rate limit runs before this, as a route dependency.)
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
from .cache import VerdictCache

SNIPPET_CHARS = 200
_WHITESPACE = re.compile(r"\s+")


def normalize(posting: PostingIn) -> str:
    """The same message pasted with different spacing or capitals should count as the
    same message, so the hash (and the cache key) treats them as identical."""
    parts = [posting.title, posting.company_profile, posting.description,
             posting.requirements, posting.benefits, posting.salary_range]
    return _WHITESPACE.sub(" ", " ".join(parts)).strip().lower()


def text_hash(posting: PostingIn) -> str:
    """SHA-256 = a 64-character fingerprint. Same text -> same hash, always."""
    return hashlib.sha256(normalize(posting).encode()).hexdigest()


@dataclass
class CheckResult:
    check: Check              # the saved row
    limited_info: bool        # returned to the user, not stored
    note: str | None


class CheckService:
    def __init__(self, session: Session, ml: MlClient, cache: VerdictCache):
        self.session = session
        self.ml = ml
        self.cache = cache
        self.checks = CheckRepository(session)

    def check(self, user_id: int, posting: PostingIn) -> CheckResult:
        fingerprint = text_hash(posting)

        # 1. Cache lookup (key includes the model version ml-service is running)
        verdict = self.cache.get(self.ml.current_version(), fingerprint)
        cache_hit = verdict is not None

        # 2. Miss: score it, then remember the answer for the next person
        if not cache_hit:
            verdict = self.ml.predict(posting.model_dump())   # raises MlServiceUnavailable if down
            self.cache.set(fingerprint, verdict)

        # 3. Save to the user's history either way
        check = self.checks.add(
            user_id=user_id,
            text_hash=fingerprint,
            title=posting.title or None,
            snippet=posting.description[:SNIPPET_CHARS],
            score=verdict["score"],
            verdict=verdict["label"],
            flags=verdict["flags"],
            model_version=verdict["model_version"],
            cache_hit=cache_hit,
        )
        self.session.commit()
        return CheckResult(check=check, limited_info=verdict["limited_info"], note=verdict["note"])

    def history(self, user_id: int, limit: int, before: datetime | None) -> tuple[list[Check], datetime | None]:
        items = self.checks.list_for_user(user_id, limit, before)
        # A full page means there may be more: the next page starts before the oldest item shown
        next_before = items[-1].created_at if len(items) == limit else None
        return items, next_before
