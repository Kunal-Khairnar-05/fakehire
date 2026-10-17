"""Shared training and evaluation code for train.py (baseline) and retrain.py (feedback loop).

ONE implementation of loading, deduplicating, splitting and scoring. If train.py and
retrain.py each had their own copy and the split drifted even slightly, "is the new
model better?" would compare different test sets and mean nothing.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

from .augment import short_eval_copy, shorten
from .model import to_frame
from .posting import Posting
from .rules import RuleEngine
from .scoring import SUSPICIOUS_FROM, combine

SEED = 42
THRESHOLDS = np.linspace(0.05, 0.95, 91)


@dataclass
class Dataset:
    postings: np.ndarray        # every row of the CSV, as Posting objects
    y: np.ndarray               # 1 = fake, 0 = real
    train: np.ndarray           # row indices (duplicates removed BEFORE splitting: no leakage)
    val: np.ndarray
    test: np.ndarray
    duplicates_removed: int
    short_val: list             # short copies of the same val/test postings (Step 4b)
    short_test: list


def load_dataset(csv_path: Path) -> Dataset:
    df = pd.read_csv(csv_path)
    postings = np.array([Posting.from_row(r) for r in df.to_dict("records")], dtype=object)
    y = df["fraudulent"].to_numpy()

    key = df["description"].fillna("").str.lower().str.strip()
    keep = ~key.duplicated(keep="first").to_numpy() | (key == "").to_numpy()
    idx = np.arange(len(df))[keep]
    tr, rest = train_test_split(idx, test_size=0.30, stratify=y[idx], random_state=SEED)
    va, te = train_test_split(rest, test_size=0.50, stratify=y[rest], random_state=SEED)

    return Dataset(postings, y, tr, va, te, int((~keep).sum()),
                   short_val=[short_eval_copy(p) for p in postings[va]],
                   short_test=[short_eval_copy(p) for p in postings[te]])


def augment(postings: list, labels: np.ndarray, rng: np.random.Generator) -> tuple[list, np.ndarray]:
    """Every posting + one random short copy of it, same label (Step 4b)."""
    return postings + [shorten(p, rng) for p in postings], np.concatenate([labels, labels])


def proba(model, postings) -> np.ndarray:
    return model.predict_proba(to_frame(list(postings)))[:, 1]


def metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    pred = (scores >= threshold).astype(int)
    real = y_true == 0
    return {
        "precision": round(precision_score(y_true, pred, zero_division=0), 3),
        "recall": round(recall_score(y_true, pred), 3),
        "f1": round(f1_score(y_true, pred), 3),
        "pr_auc": round(average_precision_score(y_true, scores), 3),
        "false_alarm_rate": round(pred[real].mean(), 3),   # % of REAL postings flagged
    }


def tune_threshold(model, ds: Dataset) -> float:
    """Best-F1 threshold on VALIDATION (full + short together), never on test."""
    y_val = np.concatenate([ds.y[ds.val], ds.y[ds.val]])
    scores = np.concatenate([proba(model, ds.postings[ds.val]), proba(model, ds.short_val)])
    return float(max(THRESHOLDS, key=lambda t: f1_score(y_val, (scores >= t).astype(int))))


def model_metrics(model, ds: Dataset, threshold: float) -> list[tuple[str, dict]]:
    """The model alone at `threshold`, on the full and the short test set."""
    return [("full", metrics(ds.y[ds.test], proba(model, ds.postings[ds.test]), threshold)),
            ("short", metrics(ds.y[ds.test], proba(model, ds.short_test), threshold))]


def product_rows(model, ds: Dataset) -> list[dict]:
    """What users actually get: rules + model combined, flagged at score >= SUSPICIOUS_FROM."""
    engine = RuleEngine()
    rows = []
    for name, ps in [("full", list(ds.postings[ds.test])), ("short", ds.short_test)]:
        p = proba(model, ps)
        final = np.array([combine(pi, engine.evaluate(post)).score for pi, post in zip(p, ps)]) / 100
        rows.append({"test set": name, **metrics(ds.y[ds.test], final, SUSPICIOUS_FROM / 100)})
    return rows
