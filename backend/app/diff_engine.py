from difflib import SequenceMatcher
from typing import List, Tuple

from .models import ChangeSet, ChangeSpan
from .utils import tokenize_legal, sentence_split


def _diff_tokens(before: List[str], after: List[str]) -> Tuple[List[ChangeSpan], List[ChangeSpan], List[ChangeSpan]]:
    insertions, deletions, substitutions = [], [], []
    sm = SequenceMatcher(None, before, after)
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == "insert":
            insertions.append(ChangeSpan(before="", after=" ".join(after[b0:b1]), token_start=b0, token_end=b1))
        elif op == "delete":
            deletions.append(ChangeSpan(before=" ".join(before[a0:a1]), after="", token_start=a0, token_end=a1))
        elif op == "replace":
            substitutions.append(
                ChangeSpan(
                    before=" ".join(before[a0:a1]),
                    after=" ".join(after[b0:b1]),
                    token_start=b0,
                    token_end=b1,
                )
            )
    return insertions, deletions, substitutions


def diff_clause(before_text: str, after_text: str) -> ChangeSet:
    before_tokens = tokenize_legal(before_text)
    after_tokens = tokenize_legal(after_text)
    ins, dels, subs = _diff_tokens(before_tokens, after_tokens)
    return ChangeSet(
        clause_id="",
        before_text=before_text,
        after_text=after_text,
        insertions=ins,
        deletions=dels,
        substitutions=subs,
        moved_blocks=[],
        table_cell_changes=[],
    )


def diff_sentences(before: str, after: str) -> List[ChangeSpan]:
    b_sent = sentence_split(before)
    a_sent = sentence_split(after)
    sm = SequenceMatcher(None, b_sent, a_sent)
    changes: List[ChangeSpan] = []
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op != "equal":
            changes.append(ChangeSpan(before=" ".join(b_sent[a0:a1]), after=" ".join(a_sent[b0:b1])))
    return changes


def diff_tables(before_cells: List[dict], after_cells: List[dict]) -> List[dict]:
    changes = []
    before_map = {(c.get("row"), c.get("col")): c for c in before_cells}
    after_map = {(c.get("row"), c.get("col")): c for c in after_cells}
    keys = set(before_map.keys()) | set(after_map.keys())
    for key in keys:
        b = before_map.get(key)
        a = after_map.get(key)
        if not b or not a:
            changes.append({"row": key[0], "col": key[1], "before": b, "after": a})
        elif b.get("text") != a.get("text"):
            changes.append({"row": key[0], "col": key[1], "before": b, "after": a})
    return changes
