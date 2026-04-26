"""Keyword regex baseline for distress classification.
If LLM doesn't beat this by >= 0.10 F1, the LLM is unjustified."""
import re

KEYWORDS = [
    r"\bas[\s-]?is\b",
    r"\bcash\s+only\b",
    r"\bfixer[\s-]?upper\b",
    r"\bmotivated\s+seller\b",
    r"\bforeclosure\b",
    r"\bbank[\s-]?owned\b",
    r"\breo\b",
    r"\bshort\s+sale\b",
    r"\bprobate\b",
    r"\bestate\s+sale\b",
    r"\bdistressed\b",
    r"\bhandyman\s+special\b",
    r"\btlc\b",
    r"\bneeds\s+work\b",
    r"\bdivorce\b",
    r"\burgent\b",
    r"\bbring\s+(all\s+)?offers\b",
    r"\binvestor\s+special\b",
    r"\bcondemned\b",
    r"\babandoned\b",
]
RE = re.compile("|".join(KEYWORDS), re.IGNORECASE)


def predict(description: str | None) -> int:
    if not description:
        return 0
    return 1 if RE.search(description) else 0
