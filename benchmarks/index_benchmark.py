"""Benchmark A: how much do the indexes (and keyset pagination) actually help?

Creates a SEPARATE database (fakehire_bench), fills it with 1,000,000 checks, and runs
each query 200 times WITH and WITHOUT the relevant index, using EXPLAIN ANALYZE to get
the time PostgreSQL itself spent (no network or Python overhead in the numbers).
Your real data in the "fakehire" database is never touched.

Run from the project root (Compose stack running):
    python benchmarks/index_benchmark.py
"""
import json
import os
import random
import statistics
import time
from pathlib import Path

import psycopg
from psycopg import ClientCursor

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmarks" / "results"
BENCH_DB = "fakehire_bench"
USERS = 50_000
CHECKS = 1_000_000
POWER_USER_CHECKS = 5_000      # one heavy user, for the deep-pagination test
RUNS = 200
SEED = 42


def read_env() -> dict:
    """Minimal .env reader (KEY=VALUE lines) so this script needs no extra library."""
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def url(dbname: str) -> str:
    # BENCH_HOST/BENCH_PORT only exist so the script can be pointed elsewhere if needed
    env = read_env()
    host, port = os.getenv("BENCH_HOST", "localhost"), os.getenv("BENCH_PORT", "5433")
    return f"postgresql://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}@{host}:{port}/{dbname}"


def step(msg: str):
    print(f"\n==> {msg}", flush=True)


# ---------------------------------------------------------------- setup
def create_database():
    step(f"Creating a fresh '{BENCH_DB}' database (your real data is untouched)")
    with psycopg.connect(url("postgres"), autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {BENCH_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {BENCH_DB}")
    with psycopg.connect(url(BENCH_DB), autocommit=True) as conn:
        for migration in sorted((ROOT / "db" / "migrations").glob("*.sql")):
            conn.execute(migration.read_text())


def seed(conn):
    step(f"Seeding {USERS:,} users and {CHECKS + POWER_USER_CHECKS:,} checks (about 30-60 s)")
    start = time.perf_counter()
    conn.execute("SELECT setseed(0.42)")   # same random data every run
    conn.execute(f"""
        INSERT INTO users (email, password_hash)
        SELECT 'user' || g || '@example.com', 'x' FROM generate_series(1, {USERS}) AS g
    """)
    # Checks spread randomly over users and over the last year
    conn.execute(f"""
        INSERT INTO checks (user_id, text_hash, title, snippet, score, verdict, model_version, created_at)
        SELECT 1 + floor(random() * {USERS})::int,
               md5(g::text) || md5((g * 7)::text),
               'Posting ' || g, 'snippet', (random() * 100)::int, 'Safe', 'v1.1',
               now() - random() * interval '365 days'
        FROM generate_series(1, {CHECKS}) AS g
    """)
    # User #1 is a "power user" with thousands of checks, to test page 100 of history
    conn.execute(f"""
        INSERT INTO checks (user_id, text_hash, title, snippet, score, verdict, model_version, created_at)
        SELECT 1, md5('p' || g) || md5('q' || g), 'Posting', 'snippet', 50, 'Safe', 'v1.1',
               now() - g * interval '1 minute'
        FROM generate_series(1, {POWER_USER_CHECKS}) AS g
    """)
    conn.execute("ANALYZE")   # refresh the planner's statistics
    print(f"    done in {time.perf_counter() - start:.1f} s")


# ---------------------------------------------------------------- measuring
def measure(conn, sql: str, params_list: list) -> dict:
    """Run EXPLAIN ANALYZE for each parameter set; return timing stats + the plan used."""
    times, plan_root = [], None
    with ClientCursor(conn) as cur:          # ClientCursor: parameters are inlined, EXPLAIN-friendly
        for params in params_list:
            cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql, params)
            result = cur.fetchone()[0][0]
            times.append(result["Execution Time"])
            plan_root = plan_root or result["Plan"]
    times.sort()
    return {
        "median_ms": round(statistics.median(times), 3),
        "p95_ms": round(times[int(len(times) * 0.95) - 1], 3),
        "plan": describe(plan_root),
    }


def describe(plan: dict) -> str:
    """The interesting node types, e.g. 'Limit > Index Scan' or 'Limit > Sort > Seq Scan'."""
    names, node = [], plan
    while node:
        name = node["Node Type"]
        if "Index Name" in node:
            name += f" ({node['Index Name']})"
        names.append(name)
        node = (node.get("Plans") or [None])[0]
    return " > ".join(n for n in names if not n.startswith("Gather"))


def report(title: str, before: dict, after: dict, before_label: str, after_label: str) -> dict:
    speedup = before["median_ms"] / after["median_ms"]
    print(f"\n  {title}")
    for label, r in ((before_label, before), (after_label, after)):
        print(f"    {label:<28} median {r['median_ms']:>9.3f} ms   p95 {r['p95_ms']:>9.3f} ms   [{r['plan']}]")
    print(f"    -> {speedup:,.0f}x faster")
    return {"title": title, before_label: before, after_label: after, "speedup": round(speedup, 1)}


# ---------------------------------------------------------------- the three experiments
def main():
    random.seed(SEED)
    create_database()
    results = {"rows": {"users": USERS, "checks": CHECKS + POWER_USER_CHECKS}, "runs_per_query": RUNS, "tests": []}

    with psycopg.connect(url(BENCH_DB), autocommit=True) as conn:
        seed(conn)
        sample_users = [(random.randint(2, USERS),) for _ in range(RUNS)]

        # 1. "My checks" first page: composite index (user_id, created_at DESC) vs none
        step(f"Test 1: 'My checks' page 1 for {RUNS} random users")
        history_sql = ("SELECT id, title, score, verdict, created_at FROM checks "
                       "WHERE user_id = %s ORDER BY created_at DESC LIMIT 20")
        conn.execute("DROP INDEX checks_user_recent_idx")
        no_index = measure(conn, history_sql, sample_users)
        conn.execute("CREATE INDEX checks_user_recent_idx ON checks (user_id, created_at DESC)")
        conn.execute("ANALYZE checks")
        with_index = measure(conn, history_sql, sample_users)
        results["tests"].append(report("History page 1 (1M rows)", no_index, with_index,
                                       "no index", "composite index"))

        # 2. Deep pagination for the power user: page 100 with OFFSET vs keyset
        step("Test 2: page 100 of a 5,000-check history, OFFSET vs keyset")
        offset_sql = ("SELECT id, title, score, created_at FROM checks WHERE user_id = 1 "
                      "ORDER BY created_at DESC LIMIT 20 OFFSET %s")
        cursor_time = conn.execute(
            "SELECT created_at FROM checks WHERE user_id = 1 ORDER BY created_at DESC LIMIT 1 OFFSET 1979"
        ).fetchone()[0]
        keyset_sql = ("SELECT id, title, score, created_at FROM checks WHERE user_id = 1 AND created_at < %s "
                      "ORDER BY created_at DESC LIMIT 20")
        offset = measure(conn, offset_sql, [(1980,)] * RUNS)
        keyset = measure(conn, keyset_sql, [(cursor_time,)] * RUNS)
        results["tests"].append(report("History page 100 (power user)", offset, keyset,
                                       "OFFSET 1980", "keyset (created_at <)"))

        # 3. Login lookup by email: the index UNIQUE created automatically vs none
        step(f"Test 3: login lookup by email among {USERS:,} users")
        login_sql = "SELECT id, password_hash, role FROM users WHERE email = %s"
        emails = [(f"user{random.randint(1, USERS)}@example.com",) for _ in range(RUNS)]
        unique_index = measure(conn, login_sql, emails)
        conn.execute("ALTER TABLE users DROP CONSTRAINT users_email_key")
        no_unique = measure(conn, login_sql, emails)
        conn.execute("ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email)")
        results["tests"].append(report("Login by email (50k users)", no_unique, unique_index,
                                       "no index", "UNIQUE index"))

        sizes = conn.execute("""
            SELECT pg_size_pretty(pg_relation_size('checks')),
                   pg_size_pretty(pg_relation_size('checks_user_recent_idx'))
        """).fetchone()
        results["sizes"] = {"checks_table": sizes[0], "composite_index": sizes[1]}
        print(f"\n  Table size {sizes[0]}, composite index size {sizes[1]}")

    if os.getenv("KEEP_BENCH_DB") != "1":
        step(f"Dropping '{BENCH_DB}' (set KEEP_BENCH_DB=1 to keep it for exploring)")
        with psycopg.connect(url("postgres"), autocommit=True) as conn:
            conn.execute(f"DROP DATABASE {BENCH_DB} WITH (FORCE)")

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "index_benchmark.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nSaved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
