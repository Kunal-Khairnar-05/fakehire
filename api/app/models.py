"""Python classes mapped onto the tables created by db/migrations/*.sql.

The SQL migrations own the schema (tables, constraints, indexes). These classes only
describe it so SQLAlchemy can read and write rows. We never call create_all().
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Text, func
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
