from typing import Dict, List

from .utils import tokenize_modal, extract_numbers, extract_dates

OBLIGATION_SHIFT_MAP = {
    ("may", "shall"): "Permission tightened to obligation",
    ("may", "must"): "Permission tightened to obligation",
    ("should", "shall"): "Advisory hardened to obligation",
    ("should", "must"): "Advisory hardened to obligation",
    ("shall", "may"): "Obligation softened to permission",
    ("must", "may"): "Obligation softened to permission",
}


def detect_obligation_shift(before: str, after: str) -> List[Dict]:
    before_modals = tokenize_modal(before)
    after_modals = tokenize_modal(after)
    shifts = []
    for b in before_modals:
        for a in after_modals:
            if b != a and (b, a) in OBLIGATION_SHIFT_MAP:
                shifts.append({"from": b, "to": a, "reason": OBLIGATION_SHIFT_MAP[(b, a)]})
    return shifts


def detect_numeric_changes(before: str, after: str) -> Dict:
    b = extract_numbers(before)
    a = extract_numbers(after)
    return {
        "before": sorted(b),
        "after": sorted(a),
        "changed": b != a,
    }


def detect_date_changes(before: str, after: str) -> Dict:
    b = extract_dates(before)
    a = extract_dates(after)
    return {
        "before": sorted(b),
        "after": sorted(a),
        "changed": b != a,
    }


def risk_tag_clause(modified_clause: Dict) -> Dict:
    before = modified_clause["before"]
    after = modified_clause["after"]

    obligation_shifts = detect_obligation_shift(before, after)
    numbers = detect_numeric_changes(before, after)
    dates = detect_date_changes(before, after)

    risk_tags = []
    if obligation_shifts:
        risk_tags.append("obligation_shift")
    if numbers["changed"]:
        risk_tags.append("numeric_change")
    if dates["changed"]:
        risk_tags.append("date_change")

    return {
        "id": modified_clause["id"],
        "heading": modified_clause["heading"],
        "risk_tags": risk_tags,
        "obligation_shifts": obligation_shifts,
        "numeric": numbers,
        "dates": dates,
    }
