"""The Posting is the one input shape every detector understands.

The dataset rows, the API request and the tests all get converted into a Posting,
so the rules and the model never care where the data came from.
"""
from dataclasses import dataclass


def _clean(value) -> str:
    # pandas gives NaN (a float) for empty cells; treat anything non-text as empty
    return value.strip() if isinstance(value, str) else ""


@dataclass
class Posting:
    title: str = ""
    company_profile: str = ""
    description: str = ""
    requirements: str = ""
    benefits: str = ""
    salary_range: str = ""

    @property
    def text(self) -> str:
        """All free-text fields joined and lowercased, for keyword rules and TF-IDF."""
        parts = [self.title, self.company_profile, self.description, self.requirements, self.benefits]
        return " ".join(p for p in parts if p).lower()

    @classmethod
    def from_row(cls, row) -> "Posting":
        """Build a Posting from one row of the Kaggle CSV."""
        return cls(**{field: _clean(row.get(field)) for field in cls.__dataclass_fields__})
