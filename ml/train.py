"""Step 4: train the model, prove the leakage problem, evaluate honestly, save it.

Run from the project root:  python ml/train.py
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, confusion_matrix, f1_score,
                             precision_score, recall_score)
from sklearn.model_selection import train_test_split

from fakehire_ml.model import build_pipeline, to_frame
from fakehire_ml.posting import Posting
from fakehire_ml.rules import RuleEngine
from fakehire_ml.scoring import SUSPICIOUS_FROM, combine

VERSION = "v1.0"
ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "raw" / "fake_job_postings.csv"
MODELS = ROOT / "models"
SEED = 42

df = pd.read_csv(DATA)
postings = np.array([Posting.from_row(r) for r in df.to_dict("records")], dtype=object)
y = df["fraudulent"].to_numpy()


def report(name, y_true, scores, threshold):
    pred = (scores >= threshold).astype(int)
    return {
        "name": name,
        "precision": round(precision_score(y_true, pred, zero_division=0), 3),
        "recall": round(recall_score(y_true, pred), 3),
        "f1": round(f1_score(y_true, pred), 3),
        "pr_auc": round(average_precision_score(y_true, scores), 3),
    }


# ======================================================================
# Experiment A: the WRONG way. Random split with duplicates left in.
# ======================================================================
tr, te = train_test_split(np.arange(len(df)), test_size=0.2, stratify=y, random_state=SEED)
leaky = build_pipeline().fit(to_frame(list(postings[tr])), y[tr])
leaky_scores = leaky.predict_proba(to_frame(list(postings[te])))[:, 1]
leaky_result = report("leaky split", y[te], leaky_scores, 0.5)

# ======================================================================
# Experiment B: the RIGHT way. Remove duplicates first, then split.
# train 70% (learn) / val 15% (pick threshold) / test 15% (final, touched once)
# ======================================================================
key = df["description"].fillna("").str.lower().str.strip()
keep = ~key.duplicated(keep="first").to_numpy() | (key == "").to_numpy()
idx = np.arange(len(df))[keep]
print(f"Removed {(~keep).sum():,} duplicate postings; {keep.sum():,} remain "
      f"({y[keep].sum()} fake).\n")

tr, rest = train_test_split(idx, test_size=0.30, stratify=y[idx], random_state=SEED)
va, te = train_test_split(rest, test_size=0.50, stratify=y[rest], random_state=SEED)

model = build_pipeline().fit(to_frame(list(postings[tr])), y[tr])

# Pick the threshold that gives the best F1 on VALIDATION (never on test).
val_scores = model.predict_proba(to_frame(list(postings[va])))[:, 1]
thresholds = np.linspace(0.05, 0.95, 91)
best_t = max(thresholds, key=lambda t: f1_score(y[va], (val_scores >= t).astype(int)))

# Final, one-time evaluation on TEST.
engine = RuleEngine()
test_p = model.predict_proba(to_frame(list(postings[te])))[:, 1]
test_rules = np.array([engine.evaluate(p).score for p in postings[te]])
test_final = np.array([combine(p, engine.evaluate(post)).score
                       for p, post in zip(test_p, postings[te])]) / 100

results = [
    leaky_result,
    report("rules only", y[te], test_rules, 0.5),
    report("model only @0.5", y[te], test_p, 0.5),
    report(f"model only @{best_t:.2f}", y[te], test_p, best_t),
    report(f"rules+model @{SUSPICIOUS_FROM}", y[te], test_final, SUSPICIOUS_FROM / 100),
]
print("RESULTS (test set: postings the model has never seen)")
print(pd.DataFrame(results).to_string(index=False))
print("\nThe leaky row looks better ONLY because near-copies of test postings were in training.")

tn, fp, fn, tp = confusion_matrix(y[te], (test_p >= best_t).astype(int)).ravel()
print(f"\nConfusion matrix, model @{best_t:.2f} on {len(te):,} test postings:")
print(f"  caught fakes (TP): {tp:4}   missed fakes (FN): {fn:4}")
print(f"  false alarms (FP): {fp:4}   correct real (TN): {tn:4}")

# What did the model learn? Biggest positive weights = strongest "fake" signals.
names = model.named_steps["features"].get_feature_names_out()
coefs = model.named_steps["clf"].coef_[0]
print("\nTop 15 signals pushing towards FAKE:")
for i in np.argsort(coefs)[::-1][:15]:
    print(f"  {names[i].split('__', 1)[1]:<28} {coefs[i]:+.2f}")
print("\nTop 10 signals pushing towards REAL:")
for i in np.argsort(coefs)[:10]:
    print(f"  {names[i].split('__', 1)[1]:<28} {coefs[i]:+.2f}")

# Save the model + its metrics. The .joblib is ignored by git; the metrics JSON is committed.
MODELS.mkdir(exist_ok=True)
metrics = {"version": VERSION, "threshold": round(float(best_t), 2),
           "test_size": int(len(te)), "results": results}
joblib.dump({"pipeline": model, "version": VERSION, "threshold": float(best_t)},
            MODELS / f"model_{VERSION}.joblib")
(MODELS / f"model_{VERSION}.metrics.json").write_text(json.dumps(metrics, indent=2))
print(f"\nSaved ml/models/model_{VERSION}.joblib and its metrics JSON.")
