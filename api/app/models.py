"""Python classes mapped onto the tables created by db/migrations/*.sql.

The SQL migrations own the schema (tables, constraints, indexes). These classes only
describe it so SQLAlchemy can read and write rows. We never call create_all().
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"
    # eager_defaults: after INSERT, fetch the values the DATABASE filled in (role, created_at)
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, server_default="student")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Check(Base):
    __tablename__ = "checks"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    text_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int] = mapped_column(SmallInteger)
    verdict: Mapped[str] = mapped_column(Text)
    flags: Mapped[list] = mapped_column(JSONB, server_default="[]")
    model_version: Mapped[str] = mapped_column(Text)
    cache_hit: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    __tablename__ = "reports"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    check_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("checks.id", ondelete="CASCADE"))
    reporter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    company_name: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    company_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("companies.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Company(Base):
    """A company with at least one VERIFIED scam report. Schema: db/migrations/003_companies.sql"""
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    name_key: Mapped[str] = mapped_column(Text, unique=True)
    verified_reports: Mapped[int] = mapped_column(Integer, server_default="0")
    last_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Filled by Postgres (Computed = never written by us); deferred = not loaded unless a query uses it.
    # Queries must use THIS column, because the GIN index is on it.
    search: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('simple', name)", persisted=True),
                                        deferred=True)
