from __future__ import annotations

from typing import List, Dict, Optional, Literal
from pydantic import BaseModel


SpanType = Dict[str, int]


class SourceSpan(BaseModel):
    page: Optional[int] = None
    paragraph: Optional[int] = None
    run: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    table: Optional[int] = None
    row: Optional[int] = None
    col: Optional[int] = None


class Token(BaseModel):
    token_id: str
    text: str
    span: SourceSpan


class Block(BaseModel):
    block_id: str
    block_type: Literal["paragraph", "table", "table_row", "table_cell"]
    text: str
    span: SourceSpan


class CanonicalDoc(BaseModel):
    doc_id: str
    blocks: List[Block]
    tokens: List[Token]
    token_map: Dict[str, SourceSpan]


class ClauseNode(BaseModel):
    clause_id: str
    type: Literal["section", "definition", "table", "table_row", "exhibit"]
    label: str
    path: str
    text: str
    text_tokens: List[str]
    source_span: Optional[SourceSpan]
    children: List["ClauseNode"] = []


class DefinedTerm(BaseModel):
    term: str
    definition_clause_id: str
    definition_text: str


class ClauseTree(BaseModel):
    root: ClauseNode
    defined_terms: List[DefinedTerm]


class AlignmentReason(BaseModel):
    method: str
    score: float


class AlignmentEntry(BaseModel):
    old_clause_id: str
    new_clause_ids: List[str]
    confidence: float
    reasons: List[AlignmentReason]
    move_detected: bool = False


class AlignmentMap(BaseModel):
    entries: List[AlignmentEntry]


class ChangeSpan(BaseModel):
    before: str
    after: str
    token_start: Optional[int] = None
    token_end: Optional[int] = None


class ChangeSet(BaseModel):
    clause_id: str
    heading: Optional[str] = None
    before_text: str
    after_text: str
    insertions: List[ChangeSpan]
    deletions: List[ChangeSpan]
    substitutions: List[ChangeSpan]
    moved_blocks: List[str]
    table_cell_changes: List[Dict]


class MaterialityFinding(BaseModel):
    clause_id: str
    category: str
    severity: Literal["low", "medium", "high"]
    rationale: str
    exact_diff_span: ChangeSpan


class TermUsage(BaseModel):
    term: str
    clause_id: str
    count: int


class CrossRef(BaseModel):
    from_clause_id: str
    to_clause_path: str


class DependencyEdge(BaseModel):
    source: str
    target: str
    edge_type: Literal["term", "cross_ref", "numeric"]


class DependencyGraph(BaseModel):
    nodes: List[str]
    edges: List[DependencyEdge]


class ImpactedClause(BaseModel):
    clause_id: str
    importance_score: float


class ImpactReport(BaseModel):
    term_changed: str
    definition_diff: ChangeSpan
    affected_clauses: List[ImpactedClause]


class NumericDelta(BaseModel):
    clause_id: str
    value_before: Optional[str]
    value_after: Optional[str]
    normalized: Optional[float]
    unit: Optional[str]
    span: ChangeSpan


class IntegrityAlert(BaseModel):
    clause_id: str
    alert_type: str
    rationale: str


class AuditLogEntry(BaseModel):
    doc_hash: str
    clause_hashes: Dict[str, str]
    parser_version: str
    diff_version: str
    rules_version: str
    alignment_version: str
    timestamp: str


class DealWorkspace(BaseModel):
    workspace_id: str
    name: str


class DocumentFamily(BaseModel):
    family_id: str
    name: str


class Version(BaseModel):
    version_id: str
    name: str


class ComparisonRun(BaseModel):
    run_id: str
    version_a: Version
    version_b: Version


class ReviewSession(BaseModel):
    review_id: str
    run_id: str
    status: str


class ExportBundle(BaseModel):
    html: str
    pdf_bytes: bytes


class CompareResponse(BaseModel):
    canonical_a: CanonicalDoc
    canonical_b: CanonicalDoc
    clause_tree_a: ClauseTree
    clause_tree_b: ClauseTree
    alignment: AlignmentMap
    changes: List[ChangeSet]
    materiality: List[MaterialityFinding]
    dependency_graph: DependencyGraph
    impact_reports: List[ImpactReport]
    numeric_deltas: List[NumericDelta]
    integrity_alerts: List[IntegrityAlert]
    audit_log: AuditLogEntry
    run: ComparisonRun
    workspace: Optional[DealWorkspace] = None
    document_family: Optional[DocumentFamily] = None
    review_session: Optional[ReviewSession] = None


class AiChangeInsight(BaseModel):
    change_id: str
    semantic_label: str
    risk_direction: str
    explanation: str
    confidence: float
    citations_to_facts: List[str]


class AiImpactAnalysis(BaseModel):
    trigger_change_id: str
    impacted_clause_id: str
    impact_summary: str
    why_linked: str
    confidence: float


class AiSummary(BaseModel):
    type: Literal["executive", "negotiation", "economics", "definitions"]
    bullets: List[str]
    backing_change_ids: List[str]


class AiResponse(BaseModel):
    insights: List[AiChangeInsight]
    impacts: List[AiImpactAnalysis]
    summaries: List[AiSummary]
    ai_enabled: bool
    raw_text: Optional[str] = None
