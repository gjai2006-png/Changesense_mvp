import re
from difflib import SequenceMatcher
from typing import List, Dict, Tuple

from .utils import normalize_space

HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*|[IVX]+|[A-Z]|\([a-z]\))\s*[\).]\s+"
)


def segment_clauses(text: str) -> List[Dict]:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    clauses: List[Dict] = []
    current = {"heading": "Preamble", "text": ""}

    def flush():
        if current["text"].strip():
            clause_id = f"clause-{len(clauses) + 1}"
            clauses.append(
                {
                    "id": clause_id,
                    "heading": current["heading"],
                    "text": normalize_space(current["text"]),
                }
            )

    for ln in lines:
        if HEADING_RE.match(ln):
            flush()
            head = HEADING_RE.sub("", ln).strip()
            current = {"heading": head or "Section", "text": ln}
        elif ln.isupper() and len(ln.split()) <= 6:
            flush()
            current = {"heading": ln.title(), "text": ln}
        else:
            current["text"] += " " + ln
    flush()
    return clauses


def clause_key(clause: Dict) -> str:
    heading = clause.get("heading", "").lower()
    return re.sub(r"\W+", "", heading) or clause["id"]


def _shingles(text: str, k: int = 3) -> set:
    tokens = re.findall(r"\w+", text.lower())
    if len(tokens) < k:
        return set(tokens)
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _match_by_similarity(a_list: List[Dict], b_list: List[Dict]) -> List[Tuple[Dict, Dict]]:
    pairs: List[Tuple[Dict, Dict]] = []
    used_b = set()
    for a in a_list:
        a_sh = _shingles(a["text"])
        best = (0.0, None)
        for b in b_list:
            if b["id"] in used_b:
                continue
            score = _jaccard(a_sh, _shingles(b["text"]))
            if score > best[0]:
                best = (score, b)
        if best[1] and best[0] >= 0.55:
            used_b.add(best[1]["id"])
            pairs.append((a, best[1]))
    return pairs


def compute_diff(a_text: str, b_text: str) -> Dict:
    a_clauses = segment_clauses(a_text)
    b_clauses = segment_clauses(b_text)

    a_map = {clause_key(c): c for c in a_clauses}
    b_map = {clause_key(c): c for c in b_clauses}

    added, deleted, modified, unchanged = [], [], [], []

    all_keys = sorted(set(a_map.keys()) | set(b_map.keys()))
    unmatched_a = []
    unmatched_b = []
    for key in all_keys:
        a = a_map.get(key)
        b = b_map.get(key)
        if a and not b:
            unmatched_a.append(a)
        elif b and not a:
            unmatched_b.append(b)
        else:
            if a["text"] == b["text"]:
                unchanged.append(b)
            else:
                ratio = SequenceMatcher(None, a["text"], b["text"]).ratio()
                modified.append(
                    {
                        "id": b["id"],
                        "heading": b["heading"],
                        "before": a["text"],
                        "after": b["text"],
                        "similarity": round(ratio, 3),
                    }
                )

    # Try to pair unmatched clauses by content similarity (handles renumbering).
    for a, b in _match_by_similarity(unmatched_a, unmatched_b):
        ratio = SequenceMatcher(None, a["text"], b["text"]).ratio()
        modified.append(
            {
                "id": b["id"],
                "heading": b["heading"],
                "before": a["text"],
                "after": b["text"],
                "similarity": round(ratio, 3),
            }
        )
        unmatched_a = [c for c in unmatched_a if c["id"] != a["id"]]
        unmatched_b = [c for c in unmatched_b if c["id"] != b["id"]]

    deleted.extend(unmatched_a)
    added.extend(unmatched_b)

    return {
        "clauses": {
            "added": added,
            "deleted": deleted,
            "modified": modified,
            "unchanged": unchanged,
        }
    }
