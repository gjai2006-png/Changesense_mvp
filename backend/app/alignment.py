import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

from .models import AlignmentMap, AlignmentEntry, AlignmentReason


def _normalize_label(label: str) -> str:
    return re.sub(r"\W+", "", label.lower())


HEADING_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\s*[\).]\s+(.+?)\s*$")


def _extract_heading_parts(node) -> Tuple[str, str]:
    if not getattr(node, "text", None):
        return "", ""
    first_line = (node.text or "").splitlines()[0].strip()
    m = HEADING_RE.match(first_line)
    if not m:
        return "", ""
    return m.group(1), m.group(2).strip()


def _match_key(node) -> str:
    _, title = _extract_heading_parts(node)
    if title:
        return _normalize_label(title)
    return _normalize_label(getattr(node, "label", "") or "")


def _bag_vector(text: str) -> Dict[str, int]:
    vec: Dict[str, int] = {}
    for tok in re.findall(r"\w+", text.lower()):
        vec[tok] = vec.get(tok, 0) + 1
    return vec


def _cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in a.keys())
    norm_a = sum(v * v for v in a.values()) ** 0.5
    norm_b = sum(v * v for v in b.values()) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def _flatten(tree) -> List:
    nodes = []

    def walk(node):
        if node.clause_id != "root":
            nodes.append(node)
        for child in node.children:
            walk(child)

    walk(tree.root)
    return nodes


def align_clauses(tree_a, tree_b) -> AlignmentMap:
    a_nodes = _flatten(tree_a)
    b_nodes = _flatten(tree_b)

    b_by_key: Dict[str, List] = {}
    for n in b_nodes:
        key = _match_key(n)
        if key:
            b_by_key.setdefault(key, []).append(n)
    used_b = set()
    entries: List[AlignmentEntry] = []

    for a in a_nodes:
        reasons = []
        matched = None
        key = _match_key(a)
        if key:
            for candidate in b_by_key.get(key, []):
                if candidate.clause_id in used_b:
                    continue
                matched = candidate
                reasons.append(AlignmentReason(method="title_exact", score=1.0))
                break

        if not matched:
            best = (0.0, None)
            for b in b_nodes:
                if b.clause_id in used_b:
                    continue
                a_title = _extract_heading_parts(a)[1] or a.label
                b_title = _extract_heading_parts(b)[1] or b.label
                label_sim = SequenceMatcher(None, a_title, b_title).ratio() if a_title and b_title else 0
                head_sim = SequenceMatcher(None, " ".join(a.text_tokens[:12]), " ".join(b.text_tokens[:12])).ratio()
                score = max(label_sim, head_sim)
                if score > best[0]:
                    best = (score, b)
            if best[1] and best[0] >= 0.7:
                matched = best[1]
                reasons.append(AlignmentReason(method="label_or_heading_fuzzy", score=best[0]))

        if not matched:
            a_vec = _bag_vector(" ".join(a.text_tokens))
            best = (0.0, None)
            for b in b_nodes:
                if b.clause_id in used_b:
                    continue
                score = _cosine(a_vec, _bag_vector(" ".join(b.text_tokens)))
                if score > best[0]:
                    best = (score, b)
            if best[1] and best[0] >= 0.55:
                matched = best[1]
                reasons.append(AlignmentReason(method="semantic_cosine", score=best[0]))

        if matched:
            used_b.add(matched.clause_id)
            a_num, a_title = _extract_heading_parts(a)
            b_num, b_title = _extract_heading_parts(matched)
            same_title = _normalize_label(a_title) and _normalize_label(a_title) == _normalize_label(b_title)
            renumber_only = same_title and a_num and b_num and a_num != b_num
            move_detected = (a.path != matched.path) and not renumber_only
            entries.append(
                AlignmentEntry(
                    old_clause_id=a.clause_id,
                    new_clause_ids=[matched.clause_id],
                    confidence=max(r.score for r in reasons) if reasons else 0.0,
                    reasons=reasons,
                    move_detected=move_detected,
                )
            )
        else:
            # Split/merge detection: allow mapping to multiple clauses if moderately similar.
            candidates = []
            a_vec = _bag_vector(" ".join(a.text_tokens))
            for b in b_nodes:
                if b.clause_id in used_b:
                    continue
                score = _cosine(a_vec, _bag_vector(" ".join(b.text_tokens)))
                if score >= 0.45:
                    candidates.append((score, b))
            candidates.sort(reverse=True, key=lambda x: x[0])
            if candidates:
                ids = [c[1].clause_id for c in candidates[:2]]
                entries.append(
                    AlignmentEntry(
                        old_clause_id=a.clause_id,
                        new_clause_ids=ids,
                        confidence=candidates[0][0],
                        reasons=[AlignmentReason(method="split_merge", score=candidates[0][0])],
                        move_detected=False,
                    )
                )
                for _, b in candidates[:2]:
                    used_b.add(b.clause_id)
            else:
                entries.append(
                    AlignmentEntry(
                        old_clause_id=a.clause_id,
                        new_clause_ids=[],
                        confidence=0.0,
                        reasons=[],
                        move_detected=False,
                    )
                )

    return AlignmentMap(entries=entries)
