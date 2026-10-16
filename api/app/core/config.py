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


settings = Settings()
