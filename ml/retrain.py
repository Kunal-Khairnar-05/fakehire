"""Retrain with moderator feedback, and ship the new model ONLY if it isn't worse.

    reviewed reports (verified = scam, rejected = not a scam)
        + the original EMSCAD training split
        -> candidate model
        -> compared with the CURRENT model on the SAME fixed test sets
        -> passes the gate?  save model_v1.N and point models/current.json at it
                             (ml-service notices and hot-reloads within ~10 s)
           fails?           keep the current model, exit with code 1

Run on your laptop:      python ml/retrain.py
Run as a Docker job:     docker compose run --rm retrain
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psycopg

from fakehire_ml.model import build_pipeline, to_frame
from fakehire_ml.posting import Posting
from fakehire_ml.rules import RuleEngine
from fakehire_ml.scoring import SUSPICIOUS_FROM, combine
from fakehire_ml.training import SEED, augment, load_dataset, proba, product_rows, tune_threshold

ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv("DATASET_PATH", ROOT.parent / "data" / "raw" / "fake_job_postings.csv"))
MODELS = Path(os.getenv("MODELS_DIR", ROOT / "models"))
POINTER = MODELS / "current.json"
BASELINE = "model_v1.1.joblib"

FEEDBACK_WEIGHT = 10     # each reviewed report counts like 10 postings: they're rare, recent and India-specific
# "Not worse" must allow for NOISE. The test set has ~94 fake postings, so catching ONE more
# or fewer moves recall by ~0.011. A first version used 0.005, stricter than the test set can
# even measure, and rejected a candidate that differed by 2 postings. Tolerance = ~2 postings.
F1_TOLERANCE = 0.02
PR_AUC_TOLERANCE = 0.01
MAX_FALSE_ALARMS = 0.02  # never flag more than 2% of real postings


# ---------------------------------------------------------------- inputs
def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:   # running on the laptop: read it from .env
        for line in (ROOT.parent / ".env").read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    return url.replace("postgresql+psycopg://", "postgresql://")


def load_feedback() -> list[tuple[Posting, int]]:
    """Reviewed reports that carry the full posting. If the same text was reported several
    times, the most recent decision wins (DISTINCT ON keeps one row per text_hash).
    jsonb_typeof(...) = 'object' skips SQL NULL *and* a stored JSON null (an early bug)."""
    with psycopg.connect(database_url()) as conn:
        rows = conn.execute("""
            SELECT DISTINCT ON (c.text_hash) r.posting, r.status
            FROM reports r JOIN checks c ON c.id = r.check_id
            WHERE r.status IN ('verified', 'rejected') AND jsonb_typeof(r.posting) = 'object'
            ORDER BY c.text_hash, r.reviewed_at DESC
        """).fetchall()
    fields = Posting.__dataclass_fields__
    return [(Posting(**{k: (posting.get(k) or "") for k in fields}), int(status == "verified"))
            for posting, status in rows]


def current_model() -> tuple[dict, str]:
    """The model ml-service is serving: whatever current.json points at, else the baseline."""
    name = json.loads(POINTER.read_text())["file"] if POINTER.exists() else BASELINE
    return joblib.load(MODELS / name), name


def next_version() -> str:
    minors = [int(m.group(1)) for f in MODELS.glob("model_v1.*.joblib")
              if (m := re.fullmatch(r"model_v1\.(\d+)\.joblib", f.name))]
    return f"v1.{max(minors, default=1) + 1}"


# ---------------------------------------------------------------- the job
def main() -> int:
    feedback = load_feedback()
    current, current_file = current_model()
    scams = sum(label for _, label in feedback)
    print(f"Reviewed reports with text: {len(feedback)} ({scams} scams, {len(feedback) - scams} not scams)")
    print(f"Current model: {current['version']} ({current_file}), "
          f"trained on {current.get('feedback_examples', 0)} feedback examples")

    if len(feedback) <= current.get("feedback_examples", 0):
        print("Nothing new to learn from. Keeping the current model.")
        return 0

    ds = load_dataset(DATA)
    fb_postings = [p for p, _ in feedback]
    fb_labels = np.array([label for _, label in feedback])

    # Training data = EMSCAD train split + feedback (repeated), then + short copies of everything.
    # The val/test splits are untouched, so both models are judged on exactly the same postings.
    rng = np.random.default_rng(SEED)
    postings = list(ds.postings[ds.train]) + fb_postings * FEEDBACK_WEIGHT
    labels = np.concatenate([ds.y[ds.train], np.tile(fb_labels, FEEDBACK_WEIGHT)])
    X, y = augment(postings, labels, rng)
    print(f"Training candidate on {len(X):,} postings...")
    candidate = build_pipeline().fit(to_frame(X), y)

    # ---- compare on the same fixed test sets ----
    cur, cand = product_rows(current["pipeline"], ds), product_rows(candidate, ds)
    table = pd.DataFrame([{"model": f"current {current['version']}", **r} for r in cur] +
                         [{"model": "candidate", **r} for r in cand])
    print(f"\nRULES + MODEL, flagged at score >= {SUSPICIOUS_FROM} (EMSCAD test sets, never trained on)")
    print(table.to_string(index=False))

    # ---- fit check on the feedback itself (it's TRAINING data here, so this is optimistic) ----
    engine = RuleEngine()

    def flagged(model) -> int:
        p = proba(model, fb_postings)
        return sum(int(combine(pi, engine.evaluate(post)).score >= SUSPICIOUS_FROM) == label
                   for pi, post, label in zip(p, fb_postings, fb_labels))
    print(f"\nFeedback examples labelled correctly (fit check, not a test): "
          f"current {flagged(current['pipeline'])}/{len(feedback)}, candidate {flagged(candidate)}/{len(feedback)}")

    # ---- the gate ----
    gates = [
        ("full-posting F1 not worse", cand[0]["f1"] >= cur[0]["f1"] - F1_TOLERANCE,
         f"{cand[0]['f1']} vs {cur[0]['f1']} (tolerance {F1_TOLERANCE})"),
        ("short-input PR-AUC not worse", cand[1]["pr_auc"] >= cur[1]["pr_auc"] - PR_AUC_TOLERANCE,
         f"{cand[1]['pr_auc']} vs {cur[1]['pr_auc']} (tolerance {PR_AUC_TOLERANCE})"),
        (f"false alarms <= {MAX_FALSE_ALARMS:.0%}", cand[0]["false_alarm_rate"] <= MAX_FALSE_ALARMS,
         f"{cand[0]['false_alarm_rate']:.1%}"),
    ]
    print("\nGATE")
    for name, passed, detail in gates:
        print(f"  {'PASS' if passed else 'FAIL'}  {name:<32} {detail}")
    if not all(passed for _, passed, _ in gates):
        print("\nCandidate rejected. The current model stays in service.")
        return 1

    # ---- promote ----
    version = next_version()
    file = f"model_{version}.joblib"
    joblib.dump({"pipeline": candidate, "version": version, "threshold": tune_threshold(candidate, ds),
                 "feedback_examples": len(feedback),
                 "trained_at": datetime.now(timezone.utc).isoformat()}, MODELS / file)
    (MODELS / f"model_{version}.metrics.json").write_text(json.dumps(
        {"version": version, "previous": current["version"], "feedback_examples": len(feedback),
         "product": cand, "previous_product": cur}, indent=2))

    # Write the pointer ATOMICALLY: write a temp file, then rename it over the old one.
    # ml-service reads current.json any time; a rename means it can never see half a file.
    tmp = POINTER.with_suffix(".tmp")
    tmp.write_text(json.dumps({"file": file, "version": version}))
    os.replace(tmp, POINTER)
    print(f"\nPromoted {version}. ml-service will switch to it within ~10 seconds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
