"""Step 3: read real scam postings, then measure every rule against the dataset.

Run from the project root:  python ml/explore_fakes.py
"""
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

from fakehire_ml.posting import Posting
from fakehire_ml.rules import DEFAULT_RULES

DATA = Path(__file__).resolve().parent.parent / "data" / "raw" / "fake_job_postings.csv"
df = pd.read_csv(DATA)
postings = [Posting.from_row(row) for row in df.to_dict("records")]
is_fake = df["fraudulent"] == 1

# ---------- 1. Read a few real scams ----------
print("=" * 70)
print("THREE RANDOM FAKE POSTINGS")
print("=" * 70)
for i in df[is_fake].sample(3, random_state=7).index:
    p = postings[i]
    print(f"\nTitle:    {p.title}")
    print(f"Location: {df.loc[i, 'location']}")
    print(f"Salary:   {p.salary_range or '(none)'}")
    print(f"Company:  {p.company_profile[:120] or '(EMPTY)'}")
    print(f"Desc:     {p.description[:300]}...")

# ---------- 2. How good is each rule? ----------
print("\n" + "=" * 70)
print("RULE REPORT")
print("  fires on fake = recall   (of all fakes, how many does it catch)")
print("  precision     = of the postings it flags, how many are really fake")
print("=" * 70)
rows = []
for rule in DEFAULT_RULES:
    fired = pd.Series([rule.matches(p) for p in postings])
    fake_hits = (fired & is_fake).sum()
    real_hits = (fired & ~is_fake).sum()
    rows.append({
        "rule": rule.name,
        "fires on fake": f"{fake_hits / is_fake.sum():.1%}",
        "fires on real": f"{real_hits / (~is_fake).sum():.1%}",
        "precision": f"{fake_hits / max(fake_hits + real_hits, 1):.1%}",
        "total flagged": int(fake_hits + real_hits),
    })
print(pd.DataFrame(rows).to_string(index=False))
print(f"\n(For reference, a random guess has precision {is_fake.mean():.1%})")

# ---------- 3. Which words do scams use more than real postings? ----------
print("\n" + "=" * 70)
print("WORDS MUCH MORE COMMON IN FAKE POSTINGS")
print("=" * 70)
dupes = df.duplicated("description", keep="first")
print(f"(Duplicate descriptions removed first: {dupes.sum():,} rows. Fake postings that are copies: "
      f"{(dupes & is_fake).sum()} of {is_fake.sum()}.)\n")
uniq = ~dupes.values
uniq_fake = is_fake.values[uniq]
vec = CountVectorizer(binary=True, stop_words="english", min_df=30, token_pattern=r"[a-z]{3,}")
X = vec.fit_transform([p.text for p, keep in zip(postings, uniq) if keep])
fake_rate = X[uniq_fake].mean(axis=0).A1
real_rate = X[~uniq_fake].mean(axis=0).A1
ratio = (fake_rate + 1e-3) / (real_rate + 1e-3)
top = ratio.argsort()[::-1][:15]
words = vec.get_feature_names_out()
for j in top:
    print(f"  {words[j]:<15} in {fake_rate[j]:6.1%} of fakes vs {real_rate[j]:6.1%} of real  ({ratio[j]:.1f}x)")
