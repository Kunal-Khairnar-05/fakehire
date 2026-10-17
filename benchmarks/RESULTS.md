# Benchmark results

## A. Database indexes and pagination

Run with `python benchmarks/index_benchmark.py` on a separate `fakehire_bench` database:
50,000 users and 1,005,000 checks, fixed random seed, each query run **200 times**.
Times are PostgreSQL's own `EXPLAIN ANALYZE` execution time (no network or Python overhead).
Raw data: [`results/index_benchmark.json`](results/index_benchmark.json).

| Query | Without | With | Speed-up | Plan change |
|---|---|---|---|---|
| "My checks" page 1 (1M rows) | 33.0 ms median, 39.1 ms p95 | **0.060 ms** median, 0.084 ms p95 | **550×** | `Sort > Seq Scan` → `Index Scan` on `(user_id, created_at DESC)` |
| History page 100 (5,000-check user) | OFFSET: 0.336 ms median | Keyset: **0.019 ms** median | **18×** | Both use the index; OFFSET still reads and discards 1,980 rows |
| Login lookup by email (50k users) | 2.64 ms median, 3.29 ms p95 | **0.025 ms** median, 0.035 ms p95 | **105×** | `Seq Scan` → `Index Scan` on the `UNIQUE(email)` index |

**Cost of the composite index:** 30 MB on a 160 MB table (about 19% extra space), plus slightly slower inserts.
Worth it: the history query runs on every visit to "My checks", and a check is inserted only once.

### What the plans show
- **Without the composite index**, Postgres reads all 1M rows, keeps one user's ~20, then sorts them.
  **With it**, rows are already grouped by user and ordered by time, so Postgres reads exactly 20 index entries and stops. There's no sort step.
- **OFFSET** gets slower the deeper you go, because skipped rows are still read. **Keyset** (`created_at < last seen`) jumps straight to the right place, so page 100 costs the same as page 1.
- **The email index was free:** `UNIQUE` creates it automatically. It turns login from scanning every user into a single lookup.

## B and C. Load tests (not yet run)

The tooling is ready. See `locustfile.py` and the commands in its docstring:

| Test | Scenario | Measures |
|---|---|---|
| B | `SCENARIO=hit` vs `SCENARIO=miss`, 3 replicas, 50 users | Latency and throughput with and without the Redis cache |
| C | `SCENARIO=hit`, 200 users, `--scale api=3` vs `--scale api=1` | Horizontal scaling across API replicas |

Run them in benchmark mode (`docker compose -f docker-compose.yml -f docker-compose.bench.yml up -d`),
which relaxes both rate limiters for the load generator.

### Finding from the first attempt
A version of the load test that signed up 200 users during the timed window **overloaded a single
API replica**: about 400 bcrypt hashes (roughly 0.25 s of CPU each) queued behind each other, logins took over 10 s,
and Nginx returned 180 × `504 Gateway Timeout`. Slow password hashing is intentional, but it makes login
the most CPU-expensive endpoint, so it needs its own protection (the per-IP Nginx limit), and benchmarks
must create accounts **before** the timer starts.
