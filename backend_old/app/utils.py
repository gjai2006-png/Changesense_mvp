import hashlib
import re
from datetime import datetime

LEGAL_MULTIWORD = [
    "to the extent",
    "provided that",
    "in accordance with",
    "subject to",
    "as set forth",
]


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def doc_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def clause_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_quotes(text: str) -> str:
    return (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def normalize_punctuation(text: str) -> str:
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s*\(\s*", "(", text)
    text = re.sub(r"\s*\)\s*", ")", text)
    return text


def normalize_numbering(text: str) -> str:
    return re.sub(r"\b(\d+)\.(\d+)\b", lambda m: f"{int(m.group(1))}.{int(m.group(2))}", text)


def canonicalize(text: str) -> str:
    text = normalize_quotes(text)
    text = normalize_punctuation(text)
    text = normalize_numbering(text)
    text = normalize_whitespace(text)
    return text


def tokenize_legal(text: str) -> list[str]:
    t = text.lower()
    for phrase in LEGAL_MULTIWORD:
        t = t.replace(phrase, phrase.replace(" ", "_"))
    tokens = re.findall(r"[\w_]+|[^\w\s]", t)
    return tokens


def sentence_split(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]
