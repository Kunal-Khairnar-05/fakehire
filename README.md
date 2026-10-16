# FakeHire

[![CI](https://github.com/kunal-khairnar-05/fakehire/actions/workflows/ci.yml/badge.svg)](https://github.com/kunal-khairnar-05/fakehire/actions/workflows/ci.yml)

Detects fake job and internship postings. Paste a posting or recruiter message and get a 0–100 risk score, a verdict, and the red flags found.

## Architecture

```
laptop :80 ──► Nginx (load balancer, per-IP limit) ──► FastAPI ×3 ──► PostgreSQL (users, checks)
                                                                 ├──► Redis (verdict cache, rate limits)
                                                                 └──► ml-service (rules + TF-IDF/LR)
```

## Run it

```bash
cp .env.example .env        # then set your own passwords and JWT secret
docker compose up -d --build
```

Open http://localhost/docs.

## Folder layout

| Folder    | What lives here |
|-----------|-----------------|
| `ml/`     | Rule engine, model training, ml-service |
| `api/`    | FastAPI backend (routes → services → repositories) |
| `db/`     | SQL migrations and the first-start init script |
| `nginx/`  | Load balancer config |
| `.github/`| CI workflow |

## Status

Phase 1 in progress.
