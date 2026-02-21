import re
from typing import List

from .models import ClauseNode, ClauseTree, DefinedTerm
from .utils import tokenize_legal

HEADING_RE = re.compile(r"^\s*(\d+(?:\.\d+)*|[IVX]+|[A-Z])\s*[\).]\s+(.*)$")


def _make_node(idx: int, label: str, text: str, span, node_type: str = "section") -> ClauseNode:
    return ClauseNode(
        clause_id=f"clause-{idx}",
        type=node_type,
        label=label,
        path=label,
        text=text,
        text_tokens=tokenize_legal(text),
        source_span=span,
        children=[],
    )


def build_clause_tree(blocks) -> ClauseTree:
    root = ClauseNode(
        clause_id="root",
        type="section",
        label="root",
        path="root",
        text="",
        text_tokens=[],
        source_span=blocks[0].span if blocks else None,
        children=[],
    )

    defined_terms: List[DefinedTerm] = []
    idx = 0
    current_node = None
    buffer_text = ""
    buffer_span = None

    def flush():
        nonlocal idx, buffer_text, buffer_span, current_node
        if current_node and buffer_text.strip():
            idx += 1
            node = _make_node(idx, current_node["label"], buffer_text.strip(), buffer_span, current_node["type"])
            root.children.append(node)
            current_node = None
            buffer_text = ""
            buffer_span = None
            _extract_defined_terms(node, defined_terms)

    def _extract_defined_terms(node: ClauseNode, terms: List[DefinedTerm]):
        term_match = re.match(r"\"([^\"]+)\"\s+means\s+(.*)", node.text, re.IGNORECASE)
        if term_match:
            terms.append(
                DefinedTerm(
                    term=term_match.group(1),
                    definition_clause_id=node.clause_id,
                    definition_text=term_match.group(2),
                )
            )

    for block in blocks:
        if not block.text:
            continue
        m = HEADING_RE.match(block.text)
        if m:
            flush()
            label = m.group(1)
            heading_text = m.group(2)
            node_type = "definition" if heading_text.lower().startswith("definitions") else "section"
            current_node = {"label": label, "type": node_type}
            buffer_text = block.text
            buffer_span = block.span
            continue

        if block.block_type.startswith("table"):
            if current_node:
                buffer_text += "\n" + block.text
            else:
                idx += 1
                node = _make_node(idx, "table", block.text, block.span, node_type="table")
                root.children.append(node)
            continue

        if current_node:
            buffer_text += "\n" + block.text
        else:
            idx += 1
            node = _make_node(idx, "section", block.text, block.span)
            root.children.append(node)
            _extract_defined_terms(node, defined_terms)

    flush()

    return ClauseTree(root=root, defined_terms=defined_terms)
