-- 001_init.sql: Phase 1 schema (users + checks)
-- A "migration" is a numbered, append-only change to the database.
-- Never edit this file after it has been applied; add 002_*.sql instead.

BEGIN;  -- all-or-nothing: if any statement fails, nothing is created

-- ---------------------------------------------------------------------------
-- users: one row per account
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         TEXT        NOT NULL UNIQUE,      -- UNIQUE automatically creates an index -> fast login lookup
    password_hash TEXT        NOT NULL,             -- bcrypt hash, never the password itself
    role          TEXT        NOT NULL DEFAULT 'student'
                  CHECK (role IN ('student', 'moderator', 'admin')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- checks: one row per posting a user checked (their history)
-- ---------------------------------------------------------------------------
CREATE TABLE checks (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text_hash     CHAR(64)    NOT NULL,             -- SHA-256 of the normalized text (also the cache key)
    title         TEXT,
    snippet       TEXT,                             -- first ~200 characters, for the history page
    score         SMALLINT    NOT NULL CHECK (score BETWEEN 0 AND 100),
    verdict       TEXT        NOT NULL CHECK (verdict IN ('Safe', 'Suspicious', 'Likely scam')),
    flags         JSONB       NOT NULL DEFAULT '[]', -- list of red flags, stored as JSON
    model_version TEXT        NOT NULL,
    cache_hit     BOOLEAN     NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- "My checks" page:  WHERE user_id = ? ORDER BY created_at DESC LIMIT 20
-- Composite index: first narrows to one user, then rows are ALREADY sorted by time,
-- so Postgres reads exactly 20 entries and stops. No full scan, no sort.
CREATE INDEX checks_user_recent_idx ON checks (user_id, created_at DESC);

-- "How many times has this exact message been checked?"  WHERE text_hash = ?
CREATE INDEX checks_text_hash_idx ON checks (text_hash);

COMMIT;
