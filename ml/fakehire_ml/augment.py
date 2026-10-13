"""Data augmentation: make SHORT copies of full postings.

Why: the dataset has full postings (hundreds of words, usually with a company
profile). Real users paste one or two lines. A model that has never seen short
genuine postings treats "short + no company info" as fake. Training on short
copies teaches it what short REAL and short FAKE postings look like.
"""
import numpy as np

from .posting import Posting


def shorten(p: Posting, rng: np.random.Generator | None = None, *,
            n_words: int | None = None, keep_title: bool | None = None,
            keep_salary: bool | None = None) -> Posting:
    """Keep only the start of the description, drop company profile/requirements/benefits.

    With rng: random length (10-40 words) and randomly keep title/salary (for training).
    With fixed arguments: the same shortening every time (for a repeatable test set).
    """
    if n_words is None:
        n_words = int(rng.integers(10, 41))
    if keep_title is None:
        keep_title = bool(rng.random() < 0.7)
    if keep_salary is None:
        keep_salary = bool(rng.random() < 0.5)

    return Posting(
        title=p.title if keep_title else "",
        description=" ".join(p.description.split()[:n_words]),
        salary_range=p.salary_range if keep_salary else "",
    )


def short_eval_copy(p: Posting) -> Posting:
    """The fixed shortening used for the 'short input' validation and test sets."""
    return shorten(p, n_words=25, keep_title=True, keep_salary=False)
