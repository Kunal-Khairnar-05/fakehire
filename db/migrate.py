"""Migration runner: applies db/migrations/*.sql that a database hasn't seen yet.

Each database gets a schema_migrations table listing the files already applied.
Running this twice is safe: the second run finds nothing new to do.

    python db/migrate.py

Migrates DATABASE_URL and, if set, TEST_DATABASE_URL (read from the environment,
or from .env). The same tool is used locally, in CI and later on the server.

Each migration runs in ONE transaction together with its schema_migrations row:
either the whole file applies and is recorded, or nothing changes. (Any BEGIN/COMMIT
lines inside the files are removed, because the runner supplies the transaction.)
"""
import os
import re
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "db" / "migrations"
OWN_TRANSACTION = re.compile(r"^\s*(BEGIN|COMMIT)\s*;\s*$", re.IGNORECASE | re.MULTILINE)


def setting(name: str) -> str | None:
    """Environment variable first (CI, Docker), then the .env file (your laptop)."""
    if os.getenv(name):
        return os.environ[name]
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return None


def migrate(url: str) -> None:
    url = url.replace("postgresql+psycopg://", "postgresql://")   # SQLAlchemy-style -> plain
    with psycopg.connect(url) as conn:
        print(f"Database '{conn.info.dbname}':")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}

        # "Baseline": databases created before this runner existed already have 001's
        # tables but no record of it. Record it instead of trying to create them again.
        if not applied and conn.execute("SELECT to_regclass('public.users')").fetchone()[0]:
            conn.execute("INSERT INTO schema_migrations (version) VALUES ('001_init.sql')")
            applied.add("001_init.sql")
            print("  baseline: 001_init.sql was already applied, recorded it")
        conn.commit()

        pending = [f for f in sorted(MIGRATIONS.glob("*.sql")) if f.name not in applied]
        for migration in pending:
            with conn.transaction():
                conn.execute(OWN_TRANSACTION.sub("", migration.read_text()))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration.name,))
            print(f"  applied {migration.name}")
        if not pending:
            print("  up to date")


if __name__ == "__main__":
    urls = [setting("DATABASE_URL"), setting("TEST_DATABASE_URL")]
    for url in dict.fromkeys(u for u in urls if u):   # skip missing and duplicates, keep order
        migrate(url)
