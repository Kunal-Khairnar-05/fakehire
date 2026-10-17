"""Train the BASELINE model, evaluate honestly on full AND short inputs, save it.

Step 4  : leakage-free evaluation (dedupe before split, threshold tuned on validation).
Step 4b : manual testing showed short pasted postings get false alarms. This script
          trains two models side by side so the effect of the fix is measured:
            v1.0 = trained on full postings only
            v1.1 = trained on full postings + short copies (augmentation)
Later versions (v1.2, v1.3, ...) come from retrain.py, which adds moderator feedback.

Run from the project root:  python ml/train.py
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from fakehire_ml.model import build_pipeline, to_frame
from fakehire_ml.posting import Posting
from fakehire_ml.scoring import SUSPICIOUS_FROM
from fakehire_ml.training import SEED, augment, load_dataset, model_metrics, proba, product_rows, tune_threshold

VERSION = "v1.1"
ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "raw" / "fake_job_postings.csv"
MODELS = ROOT / "models"

# ---------- 1. Load, remove duplicates, split 70 / 15 / 15 ----------
ds = load_dataset(DATA)
print(f"Removed {ds.duplicates_removed:,} duplicates. "
      f"Train {len(ds.train):,} / val {len(ds.val):,} / test {len(ds.test):,}\n")

# ---------- 2. Train both models ----------
rng = np.random.default_rng(SEED)
train_full = list(ds.postings[ds.train])
train_aug, y_aug = augment(train_full, ds.y[ds.train], rng)   # every posting + 1 short copy

models = {
    "v1.0 (full only)": build_pipeline().fit(to_frame(train_full), ds.y[ds.train]),
    "v1.1 (+ short copies)": build_pipeline().fit(to_frame(train_aug), y_aug),
}

# ---------- 3. Evaluate both on full and short test sets ----------
rows, chosen = [], {}
for name, model in models.items():
    t = tune_threshold(model, ds)
    chosen[name] = t
    for test_set, m in model_metrics(model, ds, t):
        rows.append({"model": name, "test set": test_set, "threshold": round(t, 2), **m})

print("MODEL COMPARISON (test sets the models never saw)")
print(pd.DataFrame(rows).to_string(index=False))

# ---------- 4. The input that exposed the problem ----------
probe = Posting(title="Data Entry Work From Home",
                description="Data entry job, On Site, 5 days per week. 3 Interview rounds and Salary is 5 LPA")
print("\nManual-test posting ('Data entry job, On Site, 5 days per week...'):")
for name, model in models.items():
    print(f"  {name:<24} p(fake) = {proba(model, [probe])[0]:.3f}")

# ---------- 5. Final product score (rules + v1.1) ----------
final_model = models["v1.1 (+ short copies)"]
final_rows = product_rows(final_model, ds)
print(f"\nWHAT USERS GET: rules + v1.1, flagged when score >= {SUSPICIOUS_FROM}")
print(pd.DataFrame(final_rows).to_string(index=False))

final_pred = (proba(final_model, ds.postings[ds.test]) >= chosen["v1.1 (+ short copies)"]).astype(int)
tn, fp, fn, tp = confusion_matrix(ds.y[ds.test], final_pred).ravel()
print(f"\nv1.1 on full test ({len(ds.test):,} postings): "
      f"caught {tp}, missed {fn}, false alarms {fp}, correct real {tn}")

# ---------- 6. Save ----------
MODELS.mkdir(exist_ok=True)
t_final = float(chosen["v1.1 (+ short copies)"])
joblib.dump({"pipeline": final_model, "version": VERSION, "threshold": t_final, "feedback_examples": 0},
            MODELS / f"model_{VERSION}.joblib")
(MODELS / f"model_{VERSION}.metrics.json").write_text(json.dumps(
    {"version": VERSION, "threshold": round(t_final, 2), "comparison": rows, "product": final_rows}, indent=2))
print(f"\nSaved ml/models/model_{VERSION}.joblib and its metrics JSON.")
