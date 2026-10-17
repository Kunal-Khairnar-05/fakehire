-- 002_reports.sql: users can report a checked posting as a scam; moderators review reports.

BEGIN;

CREATE TABLE reports (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    check_id     BIGINT      NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
    reporter_id  BIGINT      NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    company_name TEXT        NOT NULL CHECK (length(company_name) BETWEEN 2 AND 200),
    reason       TEXT        CHECK (length(reason) <= 1000),
    status       TEXT        NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'verified', 'rejected')),
    reviewed_by  BIGINT      REFERENCES users(id) ON DELETE SET NULL,   -- keep the report if the moderator leaves
    reviewed_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- A user can report the same check only once (the database enforces it, not just the API)
    UNIQUE (check_id, reporter_id),
    -- A reviewed report must say who reviewed it and when; a pending one must not
    CHECK ((status = 'pending') = (reviewed_by IS NULL AND reviewed_at IS NULL))
);

-- Moderator queue:  WHERE status = 'pending' ORDER BY created_at  (oldest first)
-- PARTIAL index: it only contains PENDING rows. Reviewed reports pile up forever, but this
-- index stays as small as the queue itself, so it stays fast and cheap to maintain.
CREATE INDEX reports_pending_idx ON reports (created_at) WHERE status = 'pending';

-- "My reports":  WHERE reporter_id = ? ORDER BY created_at DESC
CREATE INDEX reports_reporter_recent_idx ON reports (reporter_id, created_at DESC);

COMMIT;
