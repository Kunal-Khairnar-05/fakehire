-- 004_report_posting.sql: keep the full posting text of REPORTED checks, for retraining.
--
-- checks only stores a 200-character snippet (we don't keep everything people paste).
-- A reported posting is different: once a moderator verifies or rejects it, it becomes a
-- labelled training example, and training needs the full text.
-- The API only accepts it if its SHA-256 matches the check's text_hash.

BEGIN;

ALTER TABLE reports ADD COLUMN posting JSONB;

COMMIT;
