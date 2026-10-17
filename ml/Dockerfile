# ---- Base image: a small official Linux image with Python 3.11 already installed ----
FROM python:3.11-slim

# Don't write .pyc files; print logs immediately instead of buffering them
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODELS_DIR=/app/models \
    MODEL_PATH=/app/models/model_v1.1.joblib

WORKDIR /app

# ---- Dependencies first (layer caching) ----
# Docker caches each step. Requirements change rarely, code changes often.
# Copying requirements alone first means editing code does NOT reinstall pandas/sklearn.
COPY requirements-service.txt .
RUN pip install --no-cache-dir -r requirements-service.txt

# ---- Then the code ----
COPY fakehire_ml/ fakehire_ml/
COPY service/ service/

# ---- Don't run as root inside the container (security best practice) ----
RUN useradd --create-home appuser
USER appuser

# The model is NOT baked into the image. It is mounted at /app/models at run time,
# so a new model version doesn't need a new image. models/current.json (written by
# retrain.py) says which file to serve; without it, MODEL_PATH (the v1.1 baseline) is used.

EXPOSE 8000

# Docker itself pings /health every 30 s and marks the container unhealthy if it fails
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
