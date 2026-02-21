import re
from datetime import datetime

MODAL_VERBS = {
    "may",
    "shall",
    "must",
    "should",
    "will",
    "can",
    "may not",
    "shall not",
    "must not",
}

DATE_PATTERNS = [
    r"\b\d{4}-\d{2}-\d{2}\b",  # YYYY-MM-DD
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",  # 1/2/2026
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
]

NUMBER_PATTERN = r"\b\d+(?:\.\d+)?%?\b"


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tokenize_modal(text: str) -> set[str]:
    t = text.lower()
    found = set()
    for mv in MODAL_VERBS:
        if mv in t:
            found.add(mv)
    return found


def extract_numbers(text: str) -> set[str]:
    return set(re.findall(NUMBER_PATTERN, text))


def extract_dates(text: str) -> set[str]:
    dates = set()
    for pat in DATE_PATTERNS:
        for m in re.findall(pat, text):
            dates.add(m)
    return dates


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"
