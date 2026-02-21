import re
from typing import List, Dict

from .models import DependencyGraph, DependencyEdge, ImpactReport, ImpactedClause, ChangeSpan

SECTION_REF = re.compile(r"section\s+([\d\.\(\)a-zA-Z]+)", re.IGNORECASE)


def build_term_index(clauses, defined_terms):
    usage = []
    for term in defined_terms:
        term_lower = term.term.lower()
        for clause in clauses:
            count = clause.text.lower().count(term_lower)
            if count:
                usage.append({"term": term.term, "clause_id": clause.clause_id, "count": count})
    return usage


def build_cross_refs(clauses):
    refs = []
    for clause in clauses:
        text = clause.text
        for match in SECTION_REF.findall(text):
            refs.append({"from_clause_id": clause.clause_id, "to_clause_path": match})
    return refs


def build_dependency_graph(clauses, defined_terms, term_usage, cross_refs, numeric_links):
    nodes = [c.clause_id for c in clauses]
    edges: List[DependencyEdge] = []
    for entry in term_usage:
        edges.append(DependencyEdge(source=entry["term"], target=entry["clause_id"], edge_type="term"))
    for ref in cross_refs:
        edges.append(DependencyEdge(source=ref["from_clause_id"], target=ref["to_clause_path"], edge_type="cross_ref"))
    for link in numeric_links:
        edges.append(DependencyEdge(source=link["value"], target=link["clause_id"], edge_type="numeric"))
    return DependencyGraph(nodes=nodes, edges=edges)


def build_impact_reports(definition_changes, term_usage):
    reports: List[ImpactReport] = []
    usage_by_term: Dict[str, List[Dict]] = {}
    for u in term_usage:
        usage_by_term.setdefault(u["term"], []).append(u)

    for change in definition_changes:
        term = change.get("term")
        usage = usage_by_term.get(term, [])
        affected = sorted(
            [
                ImpactedClause(clause_id=u["clause_id"], importance_score=float(u["count"]))
                for u in usage
            ],
            key=lambda x: x.importance_score,
            reverse=True,
        )
        reports.append(
            ImpactReport(
                term_changed=term,
                definition_diff=ChangeSpan(before=change.get("before"), after=change.get("after")),
                affected_clauses=affected,
            )
        )
    return reports
