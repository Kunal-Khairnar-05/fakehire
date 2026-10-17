"""Database connection.

The engine keeps a POOL of open connections. Opening a PostgreSQL connection takes
milliseconds; reusing one from the pool takes microseconds.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .core.config import settings

engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,        # connections kept open per API process
    max_overflow=settings.db_max_overflow,  # extra connections allowed during bursts
    pool_pre_ping=True,   # check a connection is alive before using it (survives DB restarts)
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session():
    """FastAPI dependency: one session per request, always closed afterwards."""
    with SessionLocal() as session:
        yield session
