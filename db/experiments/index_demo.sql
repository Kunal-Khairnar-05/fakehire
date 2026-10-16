-- index_demo.sql: SEE what an index does. Run each block one at a time inside psql.
-- Uses fake demo rows; block 6 deletes them again.

-- ===== Block 1: turn on timing so psql prints how long each query takes =====
\timing on

-- ===== Block 2: create 5,000 demo users and 500,000 demo checks =====
-- generate_series(1, N) produces the numbers 1..N, so this is a "loop" in pure SQL.
INSERT INTO users (email, password_hash)
SELECT 'demo' || g || '@example.com', 'not-a-real-hash'
FROM generate_series(1, 5000) AS g;

INSERT INTO checks (user_id, text_hash, score, verdict, model_version, created_at)
SELECT (SELECT min(id) FROM users) + (random() * 4999)::int,  -- a random demo user
       md5(g::text) || md5((g + 1)::text),                      -- 64 fake hex chars
       (random() * 100)::int,
       'Safe',
       'v1.1',
       now() - random() * interval '365 days'                    -- a random time in the last year
FROM generate_series(1, 500000) AS g;

ANALYZE checks;  -- refresh the statistics the query planner uses to choose a plan

-- ===== Block 3: WITHOUT the index =====
DROP INDEX checks_user_recent_idx;

EXPLAIN ANALYZE
SELECT id, score, verdict, created_at
FROM checks
WHERE user_id = (SELECT min(id) FROM users) + 41
ORDER BY created_at DESC
LIMIT 20;
-- Look for: "Seq Scan on checks"  (reads ALL 500,000 rows)  + a "Sort" step.
-- Note the "Execution Time" at the bottom.

-- ===== Block 4: WITH the index =====
CREATE INDEX checks_user_recent_idx ON checks (user_id, created_at DESC);

EXPLAIN ANALYZE
SELECT id, score, verdict, created_at
FROM checks
WHERE user_id = (SELECT min(id) FROM users) + 41
ORDER BY created_at DESC
LIMIT 20;
-- Look for: "Index Scan using checks_user_recent_idx"  and NO Sort step.
-- Compare the Execution Time with block 3.

-- ===== Block 5 (bonus): how big is the index compared to the table? =====
SELECT pg_size_pretty(pg_relation_size('checks'))                 AS table_size,
       pg_size_pretty(pg_relation_size('checks_user_recent_idx')) AS index_size;
-- Indexes are not free: they take disk space and make every INSERT a little slower.
-- That's why we only add indexes that a real query needs.

-- ===== Block 6: clean up the demo data =====
TRUNCATE checks, users RESTART IDENTITY;
