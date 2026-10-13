"""Turns Postings into numbers and defines the ML pipeline.

The pipeline is TF-IDF on the text + 4 yes/no features -> Logistic Regression.
Everything is inside one sklearn Pipeline, so the exact same preprocessing runs
during training and inside the ml-service. No copy-pasted feature code = no
"training-serving skew".
"""
import re

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .posting import Posting

# Only features we can ALSO get from a pasted posting at prediction time.
# The CSV has has_company_logo / has_questions too, and they are strong signals,
# but a user pasting a WhatsApp message can't give us those, so we don't train on them.
META_FEATURES = ["has_company_profile", "has_salary", "has_requirements", "has_benefits"]

# The dataset hides URLs, emails and phone numbers as "#URL_a1b2c3...#".
# Turn each into one word, so "contains an email" becomes a usable signal.
_PLACEHOLDER = re.compile(r"#(url|email|phone)_[0-9a-f]+#")


def normalize(text: str) -> str:
    return _PLACEHOLDER.sub(lambda m: f" {m.group(1)}token ", text)


def to_frame(postings: list[Posting]) -> pd.DataFrame:
    """The table the pipeline expects: one text column + the yes/no columns."""
    return pd.DataFrame({
        "text": [normalize(p.text) for p in postings],
        "has_company_profile": [int(bool(p.company_profile)) for p in postings],
        "has_salary": [int(bool(p.salary_range)) for p in postings],
        "has_requirements": [int(bool(p.requirements)) for p in postings],
        "has_benefits": [int(bool(p.benefits)) for p in postings],
    })


def build_pipeline() -> Pipeline:
    features = ColumnTransformer([
        ("text", TfidfVectorizer(
            ngram_range=(1, 2),      # single words and word pairs ("registration fee")
            min_df=3,                # ignore words seen in fewer than 3 postings
            max_features=50_000,
            sublinear_tf=True,       # a word repeated 10x isn't 10x more important
            stop_words="english",
        ), "text"),
        ("meta", "passthrough", META_FEATURES),
    ])
    clf = LogisticRegression(
        class_weight="balanced",     # treat the 4.8% fakes as equally important as the 95% real
        C=4.0,
        max_iter=2000,
    )
    return Pipeline([("features", features), ("clf", clf)])
