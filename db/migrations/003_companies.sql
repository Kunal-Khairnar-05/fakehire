-- 003_companies.sql: companies with VERIFIED scam reports, searchable by name.

BEGIN;

CREATE TABLE companies (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name             TEXT        NOT NULL,          -- shown to users, as first reported
    -- "Global  Typing Solutions" and "global typing solutions" are the same company:
    -- the key is lowercased with single spaces, and UNIQUE makes the upsert possible.
    name_key         TEXT        NOT NULL UNIQUE,
    verified_reports INTEGER     NOT NULL DEFAULT 0 CHECK (verified_reports >= 0),
    last_reported_at TIMESTAMPTZ,

    -- Full-text search document, kept up to date by Postgres itself (GENERATED ... STORED).
    -- 'simple' = split into lowercase words, no English stemming (company names aren't prose).
    search           TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', name)) STORED
);

-- GIN = "Generalized Inverted iNdex": like the index at the back of a book.
-- For each WORD it stores the list of rows containing it, so "find companies with the
-- word 'typing'" jumps straight to the matches instead of reading every name.
CREATE INDEX companies_search_idx ON companies USING GIN (search);

-- Which company a verified report was counted towards
ALTER TABLE reports ADD COLUMN company_id BIGINT REFERENCES companies(id) ON DELETE SET NULL;

-- ---- DATA migration: reports verified before this table existed ----
INSERT INTO companies (name, name_key, verified_reports, last_reported_at)
SELECT regexp_replace(trim(min(company_name)), '\s+', ' ', 'g'),   -- tidy spaces, like the API does
       lower(regexp_replace(trim(company_name), '\s+', ' ', 'g')) AS name_key,
       count(*),
       max(reviewed_at)
FROM reports
WHERE status = 'verified'
GROUP BY name_key;

UPDATE reports r
SET company_id = c.id
FROM companies c
WHERE r.status = 'verified'
  AND c.name_key = lower(regexp_replace(trim(r.company_name), '\s+', ' ', 'g'));

COMMIT;
