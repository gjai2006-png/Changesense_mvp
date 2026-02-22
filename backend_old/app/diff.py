import re
from difflib import SequenceMatcher
from typing import List, Dict, Tuple

from .utils import normalize_space

HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*|[IVX]+|[A-Z]|\([a-z]\))\s*[\).]\s+"
)


def _compute_word_diff_spans(before: str, after: str) -> Dict:
    """
    Compute word-level diff spans with character offsets.
    Returns a dict with 'before_spans' and 'after_spans'.
    Each span: {"text": word, "offset": char_pos, "type": "added"/"removed"/"unchanged"}
    """
    before_words = re.findall(r'\b\w+\b|\s+|[^\w\s]', before)
    after_words = re.findall(r'\b\w+\b|\s+|[^\w\s]', after)
    
    matcher = SequenceMatcher(lambda x: x.isspace() or x in '', before_words, after_words)
    
    before_spans = []
    after_spans = []
    before_char_pos = 0
    after_char_pos = 0
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        before_segment = before_words[i1:i2]
        after_segment = after_words[j1:j2]
        
        for word in before_segment:
            if tag != 'insert':
                before_spans.append({
                    "text": word,
                    "offset": before_char_pos,
                    "type": "removed" if tag == 'delete' else "unchanged"
                })
            before_char_pos += len(word)
        
        for word in after_segment:
            if tag != 'delete':
                after_spans.append({
                    "text": word,
                    "offset": after_char_pos,
                    "type": "added" if tag == 'insert' else "unchanged"
                })
            after_char_pos += len(word)
    
    return {"before_spans": before_spans, "after_spans": after_spans}


def segment_clauses(text: str) -> Tuple[List[Dict], List[str]]:
    """
    Segment clauses and return both clauses and paragraphs.
    Returns (clauses, paragraphs) where paragraphs is a list of all non-empty lines.
    """
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    clauses: List[Dict] = []
    current = {"heading": "Preamble", "text": "", "para_start": 0}
    
    def flush():
        if current["text"].strip():
            clause_id = f"clause-{len(clauses) + 1}"
            clauses.append(
                {
                    "id": clause_id,
                    "heading": current["heading"],
                    "text": normalize_space(current["text"]),
                    "paragraph_index_start": current["para_start"],
                    "paragraph_index_end": current["para_start"],
                }
            )

    for idx, ln in enumerate(lines):
        if HEADING_RE.match(ln):
            flush()
            head = HEADING_RE.sub("", ln).strip()
            current = {"heading": head or "Section", "text": ln, "para_start": idx}
        elif ln.isupper() and len(ln.split()) <= 6:
            flush()
            current = {"heading": ln.title(), "text": ln, "para_start": idx}
        else:
            current["text"] += " " + ln
    flush()
    
    # Re-pass to set correct paragraph end indices
    result = []
    for clause in clauses:
        start = clause["paragraph_index_start"]
        # Count lines in current clause's text to estimate end
        end = start
        # Simple heuristic: find next heading or end
        for i in range(start + 1, len(lines)):
            if i < len(lines) and HEADING_RE.match(lines[i]):
                end = i - 1
                break
            end = i
        clause["paragraph_index_end"] = end
        result.append(clause)
    
    return result, lines


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
    a_clauses, a_paragraphs = segment_clauses(a_text)
    b_clauses, b_paragraphs = segment_clauses(b_text)

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
                word_diffs = _compute_word_diff_spans(a["text"], b["text"])
                modified.append(
                    {
                        "id": b["id"],
                        "heading": b["heading"],
                        "before": a["text"],
                        "after": b["text"],
                        "before_text": a["text"],
                        "after_text": b["text"],
                        "similarity": round(ratio, 3),
                        "paragraph_index_start": b["paragraph_index_start"],
                        "paragraph_index_end": b["paragraph_index_end"],
                        "word_diffs": word_diffs,
                    }
                )

    # Try to pair unmatched clauses by content similarity (handles renumbering).
    for a, b in _match_by_similarity(unmatched_a, unmatched_b):
        ratio = SequenceMatcher(None, a["text"], b["text"]).ratio()
        word_diffs = _compute_word_diff_spans(a["text"], b["text"])
        modified.append(
            {
                "id": b["id"],
                "heading": b["heading"],
                "before": a["text"],
                "after": b["text"],
                "before_text": a["text"],
                "after_text": b["text"],
                "similarity": round(ratio, 3),
                "paragraph_index_start": b["paragraph_index_start"],
                "paragraph_index_end": b["paragraph_index_end"],
                "word_diffs": word_diffs,
            }
        )
        unmatched_a = [c for c in unmatched_a if c["id"] != a["id"]]
        unmatched_b = [c for c in unmatched_b if c["id"] != b["id"]]

    # For added clauses, add paragraph indices
    for clause in unmatched_b:
        added.append({
            **clause,
            "paragraph_index_start": clause["paragraph_index_start"],
            "paragraph_index_end": clause["paragraph_index_end"],
        })
    
    # For deleted clauses, add paragraph indices
    for clause in unmatched_a:
        deleted.append({
            **clause,
            "paragraph_index_start": clause["paragraph_index_start"],
            "paragraph_index_end": clause["paragraph_index_end"],
        })

    return {
        "clauses": {
            "added": added,
            "deleted": deleted,
            "modified": modified,
            "unchanged": unchanged,
        },
        "paragraphs_a": a_paragraphs,
        "paragraphs_b": b_paragraphs,
    }
