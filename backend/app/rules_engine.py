import re
from typing import List

from .models import MaterialityFinding, ChangeSpan

MODAL_SHIFTS = [
    ("may", "shall", "Discretion changed to a mandatory obligation"),
    ("may", "must", "Discretion changed to a mandatory obligation"),
    ("may", "will", "Discretion changed to a mandatory commitment"),
    ("shall", "may", "Mandatory obligation softened to discretionary language"),
    ("must", "may", "Mandatory obligation softened to discretionary language"),
    ("will", "may", "Firm commitment softened to discretionary language"),
]

CURRENCY_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?%\b")
DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")
DURATION_RE = re.compile(r"\b\d+\s+(?:days?|months?|years?)\b", re.IGNORECASE)

KEY_TERMS = {
    "mae": "MAE",
    "material adverse effect": "MAE",
    "closing conditions": "Closing Conditions",
    "termination": "Termination Rights",
    "drop-dead": "Termination Rights",
    "sandbagging": "Non-reliance/Sandbagging",
    "non-reliance": "Non-reliance/Sandbagging",
    "disclosure schedule": "Disclosure Schedule",
    "affiliate": "Definitions",
    "knowledge": "Definitions",
    "permitted liens": "Definitions",
    "material": "Definitions",
}


def _find_modal_shift(before: str, after: str) -> List[MaterialityFinding]:
    findings = []
    b = before.lower()
    a = after.lower()

    def has_modal(text: str, modal: str) -> bool:
        return re.search(rf"\b{re.escape(modal)}\b", text) is not None

    for frm, to, rationale in MODAL_SHIFTS:
        if has_modal(b, frm) and has_modal(a, to) and not has_modal(a, frm):
            findings.append(
                MaterialityFinding(
                    clause_id="",
                    category="obligation_shift",
                    severity="high",
                    rationale=rationale,
                    exact_diff_span=ChangeSpan(before=before, after=after),
                )
            )
    return findings


def _find_numeric(before: str, after: str) -> List[MaterialityFinding]:
    findings = []
    if CURRENCY_RE.findall(before) != CURRENCY_RE.findall(after):
        findings.append(
                MaterialityFinding(
                    clause_id="",
                    category="numeric_change",
                    severity="high",
                    rationale="Currency amount changed",
                    exact_diff_span=ChangeSpan(before=before, after=after),
                )
            )
    if PERCENT_RE.findall(before) != PERCENT_RE.findall(after):
        findings.append(
                MaterialityFinding(
                    clause_id="",
                    category="numeric_change",
                    severity="medium",
                    rationale="Percentage threshold changed",
                    exact_diff_span=ChangeSpan(before=before, after=after),
            )
        )
    return findings


def _find_time(before: str, after: str) -> List[MaterialityFinding]:
    findings = []
    if DATE_RE.findall(before) != DATE_RE.findall(after):
        findings.append(
                MaterialityFinding(
                    clause_id="",
                    category="date_change",
                    severity="high",
                    rationale="Date changed",
                    exact_diff_span=ChangeSpan(before=before, after=after),
            )
        )
    if DURATION_RE.findall(before) != DURATION_RE.findall(after):
        findings.append(
                MaterialityFinding(
                    clause_id="",
                    category="duration_change",
                    severity="medium",
                    rationale="Duration window changed",
                    exact_diff_span=ChangeSpan(before=before, after=after),
            )
        )
    return findings


def _find_key_terms(before: str, after: str) -> List[MaterialityFinding]:
    findings = []
    combined = (before + " " + after).lower()
    for needle, label in KEY_TERMS.items():
        if needle in combined and before != after:
            findings.append(
                MaterialityFinding(
                    clause_id="",
                    category=f"key_term_{label.lower().replace(' ', '_').replace('/', '_')}",
                    severity="medium",
                    rationale=f"Change detected in {label} language",
                    exact_diff_span=ChangeSpan(before=before, after=after),
                )
            )
    return findings


def apply_rules(before: str, after: str) -> List[MaterialityFinding]:
    findings: List[MaterialityFinding] = []
    findings.extend(_find_modal_shift(before, after))
    findings.extend(_find_numeric(before, after))
    findings.extend(_find_time(before, after))
    findings.extend(_find_key_terms(before, after))
    return findings
