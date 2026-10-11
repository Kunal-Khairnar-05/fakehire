"""First look at the dataset: size, class balance, and missing values.

Run from the project root:  python ml/check_data.py
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "raw" / "fake_job_postings.csv"

df = pd.read_csv(DATA)

print(f"Rows: {len(df):,}   Columns: {df.shape[1]}\n")

# Class balance: how many postings are fake (1) vs real (0)?
counts = df["fraudulent"].value_counts()
print("Class balance")
print(f"  real (0): {counts[0]:>6,}")
print(f"  fake (1): {counts[1]:>6,}   -> {counts[1] / len(df):.1%} of all postings\n")

# A model that always says "real" would already get this accuracy:
print(f"Accuracy of always guessing 'real': {counts[0] / len(df):.1%}  <- why accuracy is a bad metric here\n")

# Missing values: empty fields can themselves be a scam signal.
print("Missing values (% of rows), real vs fake")
cols = ["company_profile", "salary_range", "requirements", "benefits", "department"]
missing = df[cols].isna().groupby(df["fraudulent"]).mean().T * 100
missing.columns = ["real %", "fake %"]
print(missing.round(1).to_string())
