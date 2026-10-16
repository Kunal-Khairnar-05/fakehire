"""Train the model, evaluate honestly on full AND short inputs, save it.

Step 4  : leakage-free evaluation (dedupe before split, threshold tuned on validation).
Step 4b : manual testing showed short pasted postings get false alarms. This script
          trains two models side by side so the effect of the fix is measured:
            v1.0 = trained on full postings only
            v1.1 = trained on full postings + short copies (augmentation)

Run from the project root:  python ml/train.py
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

from fakehire_ml.augment import short_eval_copy, shorten
from fakehire_ml.model import build_pipeline, to_frame
from fakehire_ml.posting import Posting
from fakehire_ml.rules import RuleEngine
from fakehire_ml.scoring import SUSPICIOUS_FROM, combine

VERSION = "v1.1"
ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "raw" / "fake_job_postings.csv"
MODELS = ROOT / "models"
SEED = 42

df = pd.read_csv(DATA)
postings = np.array([Posting.from_row(r) for r in df.to_dict("records")], dtype=object)
y = df["fraudulent"].to_numpy()


def metrics(y_true, scores, threshold):
    pred = (scores >= threshold).astype(int)
    real = y_true == 0
    return {
        "precision": round(precision_score(y_true, pred, zero_division=0), 3),
        "recall": round(recall_score(y_true, pred), 3),
        "f1": round(f1_score(y_true, pred), 3),
        "pr_auc": round(average_precision_score(y_true, scores), 3),
        "false_alarm_rate": round(pred[real].mean(), 3),   # % of REAL postings flagged
    }


def proba(model, ps):
    return model.predict_proba(to_frame(list(ps)))[:, 1]


# ---------- 1. Remove duplicates, then split 70 / 15 / 15 ----------
key = df["description"].fillna("").str.lower().str.strip()
keep = ~key.duplicated(keep="first").to_numpy() | (key == "").to_numpy()
idx = np.arange(len(df))[keep]
tr, rest = train_test_split(idx, test_size=0.30, stratify=y[idx], random_state=SEED)
va, te = train_test_split(rest, test_size=0.50, stratify=y[rest], random_state=SEED)
print(f"Removed {(~keep).sum():,} duplicates. Train {len(tr):,} / val {len(va):,} / test {len(te):,}\n")

# Short versions of the SAME val/test postings: what a user pasting 1-2 lines looks like.
short_va = [short_eval_copy(p) for p in postings[va]]
short_te = [short_eval_copy(p) for p in postings[te]]

# ---------- 2. Train both models ----------
rng = np.random.default_rng(SEED)
train_full = list(postings[tr])
train_aug = train_full + [shorten(p, rng) for p in train_full]   # every posting + 1 short copy
y_aug = np.concatenate([y[tr], y[tr]])

models = {
    "v1.0 (full only)": build_pipeline().fit(to_frame(train_full), y[tr]),
    "v1.1 (+ short copies)": build_pipeline().fit(to_frame(train_aug), y_aug),
}

# ---------- 3. Evaluate both on full and short test sets ----------
rows, chosen = [], {}
thresholds = np.linspace(0.05, 0.95, 91)
y_val_both = np.concatenate([y[va], y[va]])
for name, model in models.items():
    # Threshold tuned on validation, full + short together (users send both kinds)
    val_scores = np.concatenate([proba(model, postings[va]), proba(model, short_va)])
    t = max(thresholds, key=lambda t: f1_score(y_val_both, (val_scores >= t).astype(int)))
    chosen[name] = t
    rows.append({"model": name, "test set": "full", "threshold": round(t, 2),
                 **metrics(y[te], proba(model, postings[te]), t)})
    rows.append({"model": name, "test set": "short", "threshold": round(t, 2),
                 **metrics(y[te], proba(model, short_te), t)})

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
engine = RuleEngine()
final_rows = []
for set_name, ps in [("full", list(postings[te])), ("short", short_te)]:
    p = proba(final_model, ps)
    final = np.array([combine(pi, engine.evaluate(post)).score for pi, post in zip(p, ps)]) / 100
    final_rows.append({"test set": set_name, **metrics(y[te], final, SUSPICIOUS_FROM / 100)})
print(f"\nWHAT USERS GET: rules + v1.1, flagged when score >= {SUSPICIOUS_FROM}")
print(pd.DataFrame(final_rows).to_string(index=False))

final_pred = (proba(final_model, postings[te]) >= chosen["v1.1 (+ short copies)"]).astype(int)
tn, fp, fn, tp = confusion_matrix(y[te], final_pred).ravel()
print(f"\nv1.1 on full test ({len(te):,} postings): caught {tp}, missed {fn}, false alarms {fp}, correct real {tn}")

# ---------- 6. Save ----------
MODELS.mkdir(exist_ok=True)
t_final = float(chosen["v1.1 (+ short copies)"])
joblib.dump({"pipeline": final_model, "version": VERSION, "threshold": t_final},
            MODELS / f"model_{VERSION}.joblib")
(MODELS / f"model_{VERSION}.metrics.json").write_text(json.dumps(
    {"version": VERSION, "threshold": round(t_final, 2), "comparison": rows, "product": final_rows}, indent=2))
print(f"\nSaved ml/models/model_{VERSION}.joblib and its metrics JSON.")
