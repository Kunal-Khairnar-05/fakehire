"""All configuration in one place, read from environment variables.

Locally the values come from E:\\FakeHire\\.env; in Docker they come from the
container's environment. The code never contains a password or secret.
"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    # extra="ignore": .env also holds POSTGRES_* values meant for the database container
    model_config = SettingsConfigDict(env_file=PROJECT_ENV, extra="ignore")

    database_url: str
    jwt_secret: str = Field(min_length=32)   # refuse to start with a weak secret
    jwt_expire_minutes: int = 60
    test_database_url: str | None = None

    # ml-service (Step 5). Locally the container is published on port 8001.
    ml_service_url: str = "http://localhost:8001"
    ml_timeout_seconds: float = 2.0   # never wait forever on another service

    # Database connection pool per API process. Serverless deployments run many small
    # instances, so they use a smaller pool (each instance only handles a few requests at once).
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # Redis (Step 9)
    redis_url: str = "redis://localhost:6379/0"
    # 0.25 s suits Redis in the next container; a cloud Redis (TLS, over the internet) needs longer
    redis_timeout_seconds: float = 0.25
    cache_ttl_seconds: int = 24 * 60 * 60     # cached verdicts expire after 24 h
    rate_limit_per_minute: int = 30           # checks per user per minute

    # Web check (P2.5). No key = the feature reports "unavailable" and everything else works.
    tavily_api_key: str | None = None
    web_timeout_seconds: float = 8.0
    web_cache_ttl_seconds: int = 24 * 60 * 60   # the same search within 24 h costs no quota


settings = Settings()
