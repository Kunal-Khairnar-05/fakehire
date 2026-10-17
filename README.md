# FakeHire

[![CI](https://github.com/Kunal-Khairnar-05/fakehire/actions/workflows/ci.yml/badge.svg)](https://github.com/Kunal-Khairnar-05/fakehire/actions/workflows/ci.yml)

Detects fake job and internship postings. Paste a posting or recruiter message and get a 0–100 risk score, a verdict, and the red flags found.

## Architecture

```
browser :80 ──► Nginx ──► /     React app (static, built into the Nginx image)
                     └──► /api  FastAPI ×3 (round robin) ──► PostgreSQL (users, checks)
                                                     ├──► Redis (verdict cache, rate limits)
                                                     └──► ml-service (rules + TF-IDF/LR)
```

## Highlights

| Area | What it does | Result |
|---|---|---|
| ML | Hybrid India-specific rule engine + TF-IDF/Logistic Regression, trained without leakage (deduplicated before splitting), augmented for short inputs | F1 **0.80**, PR-AUC **0.85** on unseen postings; short-input PR-AUC 0.52 → **0.62** |
| Database | Composite index `(user_id, created_at DESC)`, keyset pagination, versioned SQL migrations | History query **550× faster** on 1M rows (33 ms → 0.06 ms) |
| Caching | Redis verdict cache keyed by model version + SHA-256 of normalized text, 24 h TTL, fail-open | Known scams answered without calling the ML service, even during an ML outage |
| Scaling | Nginx load balancing across 3 stateless API replicas (JWT auth, shared Redis state) | A replica can be killed with no failed requests |
| Auth | bcrypt, JWT, uniform login errors, timing-attack protection, per-user + per-IP rate limits | |
| CI | GitHub Actions: lint, 49 tests, model retrained from scratch behind a quality gate, Docker builds | A regression in F1 or false-alarm rate fails the build |

Full benchmark write-up: [`benchmarks/RESULTS.md`](benchmarks/RESULTS.md).

## Run it

```bash
cp .env.example .env        # then set your own passwords and JWT secret
docker compose up -d --build
```

Open http://localhost (the app) or http://localhost/docs (API docs).

## Folder layout

| Folder       | What lives here |
|--------------|-----------------|
| `ml/`        | Rule engine, model training, ml-service |
| `api/`       | FastAPI backend (routes → services → repositories) |
| `frontend/`  | React + TypeScript app |
| `db/`        | SQL migrations and the first-start init script |
| `nginx/`     | Load balancer config and the multi-stage frontend build |
| `benchmarks/`| Index benchmark, load test, results |
| `.github/`   | CI workflow |

## Status

Phase 1 (MVP) complete. Next: scam reports with moderation and a retraining loop (Phase 2), cloud deployment (Phase 3).
