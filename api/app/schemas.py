"""Shapes of request and response bodies. Pydantic validates incoming data against them.

Response schemas are also a security boundary: UserOut has no password_hash field,
so it can never be sent to a client by accident.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # build it straight from a User object

    id: int
    email: str
    role: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int        # seconds


# ---------- checks (Step 8) ----------

class PostingIn(BaseModel):
    """Same limits as ml-service. Validating here too ("defense in depth") means bad
    input is rejected at the front door and never costs an ml-service call."""
    title: str = Field("", max_length=300)
    company_profile: str = Field("", max_length=5000)
    description: str = Field(..., min_length=20, max_length=10_000)
    requirements: str = Field("", max_length=5000)
    benefits: str = Field("", max_length=5000)
    salary_range: str = Field("", max_length=100)

    model_config = {"json_schema_extra": {"example": {
        "title": "Data Entry Work From Home",
        "description": "No interview needed! Earn Rs 30000 per month from home. Pay a registration "
                       "fee of Rs 1999 to confirm your seat. Message HR on WhatsApp 9876543210.",
    }}}


class Flag(BaseModel):
    rule: str
    message: str


class CheckOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: int
    score: int
    verdict: str
    flags: list[Flag]
    limited_info: bool
    note: str | None
    model_version: str
    cache_hit: bool
    created_at: datetime
    took_ms: float           # time spent inside the API for this request


class CheckSummary(BaseModel):
    """One row of the history page: no flags, just enough to list it."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    snippet: str | None
    score: int
    verdict: str
    created_at: datetime


class CheckHistoryOut(BaseModel):
    items: list[CheckSummary]
    # Pass this as ?before=... to get the next page. None = no more pages.
    next_before: datetime | None


# ---------- reports (Phase 2) ----------

class ReportIn(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,   # "  Acme  " -> "Acme"
        # What Swagger pre-fills instead of "string" placeholders
        json_schema_extra={"example": {
            "check_id": 1,
            "company_name": "Global Typing Solutions",
            "reason": "Asked for a Rs 499 security deposit on Telegram before giving any work",
        }},
    )

    check_id: int
    company_name: str = Field(min_length=2, max_length=200)
    reason: str | None = Field(None, max_length=1000)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    check_id: int
    company_name: str
    reason: str | None
    status: Literal["pending", "verified", "rejected"]
    created_at: datetime
    reviewed_at: datetime | None


class QueueItem(ReportOut):
    """A pending report plus what the moderator needs to judge it: the checked posting."""
    title: str | None
    snippet: str | None
    score: int
    verdict: str


class QueueOut(BaseModel):
    items: list[QueueItem]
    # Pass as ?after=... for the next page. The queue is oldest-first, so pages move FORWARD in time.
    next_after: datetime | None


class ReviewIn(BaseModel):
    status: Literal["verified", "rejected"]
