import re
from typing import List

from .models import NumericDelta, ChangeSpan

CURRENCY_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?%\b")
DURATION_RE = re.compile(r"\b\d+\s+(?:days?|months?|years?)\b", re.IGNORECASE)
DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")


def _normalize(value: str) -> float | None:
    try:
        cleaned = value.replace("$", "").replace(",", "").replace("%", "")
        return float(cleaned)
    except ValueError:
        return None


def extract_numeric_deltas(clause_id: str, before: str, after: str) -> List[NumericDelta]:
    deltas: List[NumericDelta] = []
    b_vals = CURRENCY_RE.findall(before) + PERCENT_RE.findall(before) + DURATION_RE.findall(before) + DATE_RE.findall(before)
    a_vals = CURRENCY_RE.findall(after) + PERCENT_RE.findall(after) + DURATION_RE.findall(after) + DATE_RE.findall(after)

    if b_vals != a_vals:
        before_val = b_vals[0] if b_vals else None
        after_val = a_vals[0] if a_vals else None
        unit = "currency" if before_val and "$" in before_val else "percent" if before_val and "%" in before_val else "duration"
        deltas.append(
            NumericDelta(
                clause_id=clause_id,
                value_before=before_val,
                value_after=after_val,
                normalized=_normalize(after_val) if after_val else _normalize(before_val) if before_val else None,
                unit=unit,
                span=ChangeSpan(before=before, after=after),
            )
        )
    return deltas


def build_numeric_links(clauses):
    links = []
    for clause in clauses:
        text = clause.text
        for match in CURRENCY_RE.findall(text):
            links.append({"value": match, "clause_id": clause.clause_id})
    return links
