# FakeHire

Detects fake job and internship postings. Paste a posting or recruiter message and get a 0–100 risk score, a verdict, and the red flags found.

## Architecture (Phase 1)

```
Browser → Nginx (load balancer) → FastAPI ×3 → Redis (cache, rate limit)
                                             → PostgreSQL (users, checks)
                                             → ml-service (rules + TF-IDF/LR)
```

## Folder layout

| Folder   | What lives here |
|----------|-----------------|
| `ml/`    | Notebooks, rule engine, model training, and the ml-service |
| `api/`   | FastAPI backend (routes → services → repositories) |
| `nginx/` | Load balancer config |
| `data/`  | Datasets (not committed to git) |

## Status

Phase 1 in progress.
