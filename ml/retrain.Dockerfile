# The retrain JOB image: runs ml/retrain.py once, then exits.
# Started on demand with:  docker compose run --rm retrain
# (In production a scheduler would run that same command weekly, e.g. cron or a cloud scheduler.)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-retrain.txt .
RUN pip install --no-cache-dir -r requirements-retrain.txt

COPY fakehire_ml/ fakehire_ml/
COPY retrain.py .

# The dataset (read-only) and the models folder (read-write) are mounted by Compose
CMD ["python", "retrain.py"]
