import uuid
from typing import Dict, List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .ingest import parse_upload
from .clause_tree import build_clause_tree
from .alignment import align_clauses
from .diff_engine import diff_clause, diff_tables
from .rules_engine import apply_rules
from .dependency import build_term_index, build_cross_refs, build_dependency_graph, build_impact_reports
from .numeric import extract_numeric_deltas, build_numeric_links
from .integrity import detect_integrity
from .audit import build_audit
from .exporter import build_html_report, build_pdf_report
from .ai_client import call_gemini
from .models import (
    CompareResponse,
    ChangeSet,
    MaterialityFinding,
    IntegrityAlert,
    NumericDelta,
    ImpactReport,
    AiResponse,
    AiChangeInsight,
    AiImpactAnalysis,
    AiSummary,
    Version,
    ComparisonRun,
    DealWorkspace,
    DocumentFamily,
    ReviewSession,
)
from .utils import now_iso

app = FastAPI(title="ChangeSense Backend MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS: Dict[str, CompareResponse] = {}
AI_RUNS: Dict[str, AiResponse] = {}


def _flatten(tree):
    nodes = []

    def walk(node):
        if node.clause_id != "root":
            nodes.append(node)
        for child in node.children:
            walk(child)

    walk(tree.root)
    return nodes


def _doc_text(canonical) -> str:
    return "\n".join(block.text for block in canonical.blocks if block.text)


def _table_cells(canonical):
    cells = []
    for block in canonical.blocks:
        if block.block_type == "table_cell":
            cells.append({
                "row": block.span.row,
                "col": block.span.col,
                "text": block.text,
            })
    return cells


def _ai_insights(compare: CompareResponse, ai_enabled: bool) -> AiResponse:
    if not ai_enabled:
        return AiResponse(insights=[], impacts=[], summaries=[], ai_enabled=False)

    # Minimal structured payload for external AI (no full document text).
    clause_nodes = _flatten(compare.clause_tree_b)
    clause_meta = {
        c.clause_id: {
            "label": c.label,
            "path": c.path,
            "type": c.type,
        }
        for c in clause_nodes
    }

    def _snippet(text: str, limit: int = 300) -> str:
        return (text or "")[:limit]

    payload = {
        "changes": [
            {
                "change_id": c.clause_id,
                "before_snippet": _snippet(c.before_text),
                "after_snippet": _snippet(c.after_text),
                "metadata": clause_meta.get(c.clause_id, {}),
                "insertions": [i.dict() for i in c.insertions[:3]],
                "deletions": [d.dict() for d in c.deletions[:3]],
                "substitutions": [s.dict() for s in c.substitutions[:3]],
            }
            for c in compare.changes[:25]
        ],
        "materiality_findings": [m.dict() for m in compare.materiality[:50]],
        "numeric_deltas": [n.dict() for n in compare.numeric_deltas[:50]],
        "impact_reports": [
            {
                "term_changed": r.term_changed,
                "affected_clauses": [c.clause_id for c in r.affected_clauses[:20]],
            }
            for r in compare.impact_reports[:20]
        ],
        "dependency_graph": {
            "edges": [e.dict() for e in compare.dependency_graph.edges[:200]],
        },
    }

    # Attempt Gemini call if API key is present.
    try:
        gemini_out = call_gemini(payload)
        insights = gemini_out.get("insights", [])
        impacts = gemini_out.get("impacts", [])
        summaries = gemini_out.get("summaries", [])

        # Confidence gating: flag low-confidence responses.
        for item in insights:
            if item.get("confidence", 0) < 0.5:
                item["explanation"] = f"Needs review: {item.get('explanation', '')}"
        for item in impacts:
            if item.get("confidence", 0) < 0.5:
                item["impact_summary"] = f"Needs review: {item.get('impact_summary', '')}"

        if not insights:
            return _fallback_ai(compare)

        return AiResponse(
            insights=insights,
            impacts=impacts,
            summaries=summaries,
            ai_enabled=True,
            raw_text=gemini_out.get("raw_text"),
        )
    except Exception as e:
        print(f"[AI] Gemini failed: {e}")
        return _fallback_ai(compare)

    insights: List[AiChangeInsight] = []
    for finding in compare.materiality[:10]:
        insights.append(
            AiChangeInsight(
                change_id=finding.clause_id,
                semantic_label=finding.category,
                risk_direction="buyer_friendly" if "weaken" in finding.rationale.lower() else "seller_friendly",
                explanation=f"Change indicates {finding.rationale.lower()}.",
                confidence=0.72,
                citations_to_facts=[finding.clause_id],
            )
        )

    impacts: List[AiImpactAnalysis] = []
    for report in compare.impact_reports[:10]:
        for impacted in report.affected_clauses[:3]:
            impacts.append(
                AiImpactAnalysis(
                    trigger_change_id=report.term_changed,
                    impacted_clause_id=impacted.clause_id,
                    impact_summary="Definition change may alter interpretation of this clause.",
                    why_linked="term reference",
                    confidence=0.65,
                )
            )

    summaries = [
        AiSummary(
            type="executive",
            bullets=[f"{len(compare.materiality)} material changes flagged."],
            backing_change_ids=[m.clause_id for m in compare.materiality[:5]],
        )
    ]

    return AiResponse(insights=insights, impacts=impacts, summaries=summaries, ai_enabled=True)


@app.post("/compare", response_model=CompareResponse)
async def compare(version_a: UploadFile = File(...), version_b: UploadFile = File(...)):
    data_a = await version_a.read()
    data_b = await version_b.read()

    canonical_a = parse_upload(version_a.filename, data_a)
    canonical_b = parse_upload(version_b.filename, data_b)

    tree_a = build_clause_tree(canonical_a.blocks)
    tree_b = build_clause_tree(canonical_b.blocks)

    alignment = align_clauses(tree_a, tree_b)

    clauses_a = _flatten(tree_a)
    clauses_b = {c.clause_id: c for c in _flatten(tree_b)}

    changes: List[ChangeSet] = []
    materiality: List[MaterialityFinding] = []
    numeric_deltas: List[NumericDelta] = []

    clause_texts = {}
    definition_changes = []
    term_map = {t.definition_clause_id: t.term for t in tree_b.defined_terms}

    for entry in alignment.entries:
        if not entry.new_clause_ids:
            continue
        old_clause = next((c for c in clauses_a if c.clause_id == entry.old_clause_id), None)
        if not old_clause:
            continue
        for new_id in entry.new_clause_ids:
            new_clause = clauses_b.get(new_id)
            if not new_clause:
                continue

            before = old_clause.text
            after = new_clause.text
            clause_texts[new_clause.clause_id] = after

            change = diff_clause(before, after)
            change.clause_id = new_clause.clause_id
            change.heading = new_clause.label
            change.before_text = before
            change.after_text = after
            if entry.move_detected:
                change.moved_blocks.append(entry.old_clause_id)
            changes.append(change)

            for finding in apply_rules(before, after):
                finding.clause_id = new_clause.clause_id
                materiality.append(finding)

            numeric_deltas.extend(extract_numeric_deltas(new_clause.clause_id, before, after))

            if new_clause.clause_id in term_map:
                definition_changes.append(
                    {"term": term_map[new_clause.clause_id], "before": before, "after": after}
                )

    # Table diff
    table_changes = diff_tables(_table_cells(canonical_a), _table_cells(canonical_b))
    if table_changes:
        changes.append(
            ChangeSet(
                clause_id="table-changes",
                heading="Table Changes",
                before_text="",
                after_text="",
                insertions=[],
                deletions=[],
                substitutions=[],
                moved_blocks=[],
                table_cell_changes=table_changes,
            )
        )

    # Defined-term changes

    term_usage = build_term_index(_flatten(tree_b), tree_b.defined_terms)
    cross_refs = build_cross_refs(_flatten(tree_b))
    numeric_links = build_numeric_links(_flatten(tree_b))
    dependency_graph = build_dependency_graph(_flatten(tree_b), tree_b.defined_terms, term_usage, cross_refs, numeric_links)
    impact_reports: List[ImpactReport] = build_impact_reports(definition_changes, term_usage)

    integrity_alerts: List[IntegrityAlert] = detect_integrity(changes)

    audit_log = build_audit(_doc_text(canonical_b), clause_texts)

    run = ComparisonRun(
        run_id=f"run-{uuid.uuid4().hex[:8]}",
        version_a=Version(version_id="v-a", name=version_a.filename or "Version A"),
        version_b=Version(version_id="v-b", name=version_b.filename or "Version B"),
    )
    workspace = DealWorkspace(workspace_id=f"ws-{uuid.uuid4().hex[:6]}", name="Demo Workspace")
    document_family = DocumentFamily(family_id=f"fam-{uuid.uuid4().hex[:6]}", name="SPA/APA")
    review_session = ReviewSession(review_id=f"rev-{uuid.uuid4().hex[:6]}", run_id=run.run_id, status="open")

    response = CompareResponse(
        canonical_a=canonical_a,
        canonical_b=canonical_b,
        clause_tree_a=tree_a,
        clause_tree_b=tree_b,
        alignment=alignment,
        changes=changes,
        materiality=materiality,
        dependency_graph=dependency_graph,
        impact_reports=impact_reports,
        numeric_deltas=numeric_deltas,
        integrity_alerts=integrity_alerts,
        audit_log=audit_log,
        run=run,
        workspace=workspace,
        document_family=document_family,
        review_session=review_session,
    )

    RUNS[run.run_id] = response
    return response


@app.post("/scan-integrity")
async def scan_integrity(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "integrity_alerts": RUNS[run_id].integrity_alerts, "generated_at": now_iso()}


@app.get("/report")
async def report(run_id: str, ai_enabled: bool = True):
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    compare = RUNS[run_id]
    ai = AI_RUNS.get(run_id) if ai_enabled else None
    if ai is None and ai_enabled:
        ai = _ai_insights(compare, ai_enabled)
        AI_RUNS[run_id] = ai
    pdf = build_pdf_report(compare.changes, compare.materiality, ai=ai)
    return Response(content=pdf, media_type="application/pdf")


@app.get("/report/html")
async def report_html(run_id: str, ai_enabled: bool = True):
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    compare = RUNS[run_id]
    ai = AI_RUNS.get(run_id) if ai_enabled else None
    if ai is None and ai_enabled:
        ai = _ai_insights(compare, ai_enabled)
        AI_RUNS[run_id] = ai
    html = build_html_report(compare.changes, compare.materiality, ai=ai)
    return Response(content=html, media_type="text/html")


@app.post("/ai/insights", response_model=AiResponse)
async def ai_insights(run_id: str, ai_enabled: bool = True):
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    compare = RUNS[run_id]
    ai = _ai_insights(compare, ai_enabled)
    AI_RUNS[run_id] = ai
    return ai
def _fallback_ai(compare: CompareResponse) -> AiResponse:
    insights = []
    change_ids = []
    exec_bullets = []
    econ_bullets = []
    def_bullets = []
    nego_bullets = []

    def _summarize_delta(before: str, after: str) -> str:
        from .rules_engine import CURRENCY_RE, PERCENT_RE, DATE_RE, DURATION_RE
        before_nums = CURRENCY_RE.findall(before) + PERCENT_RE.findall(before)
        after_nums = CURRENCY_RE.findall(after) + PERCENT_RE.findall(after)
        before_dates = DATE_RE.findall(before)
        after_dates = DATE_RE.findall(after)
        before_dur = DURATION_RE.findall(before)
        after_dur = DURATION_RE.findall(after)

        parts = []
        if before_nums != after_nums:
            parts.append(f"Economic terms changed from {', '.join(before_nums)} to {', '.join(after_nums)}.")
        if before_dates != after_dates:
            parts.append(f"Key dates shifted from {', '.join(before_dates)} to {', '.join(after_dates)}.")
        if before_dur != after_dur:
            parts.append(f"Timing windows changed from {', '.join(before_dur)} to {', '.join(after_dur)}.")
        if " shall " in f" {before.lower()} " and " may " in f" {after.lower()} ":
            parts.append("Obligation softened from mandatory to permissive (\"shall\" to \"may\").")
        if " may " in f" {before.lower()} " and " shall " in f" {after.lower()} ":
            parts.append("Obligation strengthened from permissive to mandatory (\"may\" to \"shall\").")
        return " ".join(parts) if parts else "Language updated with no clear numeric/date/modality shift; review the before/after wording for scope or meaning changes."

    # Build a quick map of impacted clauses (from dependency graph edges)
    impacted_map = {}
    for edge in compare.dependency_graph.edges:
        if edge.edge_type in ("term", "cross_ref", "numeric"):
            impacted_map.setdefault(edge.source, set()).add(edge.target)

    for change in compare.changes:
        label = change.heading or change.clause_id
        before = change.before_text or ""
        after = change.after_text or ""
        if not before and after:
            explanation = (
                "This section appears newly added. It likely introduces new obligations, rights, or conditions that did not exist "
                "in the prior draft, so it should be reviewed for deal impact and compliance implications."
            )
        elif before and not after:
            explanation = (
                "This section appears removed. Any obligations, protections, or conditions in the prior draft may no longer apply, "
                "which could materially shift risk or responsibilities."
            )
        else:
            explanation = _summarize_delta(before, after)

        impacted = list(impacted_map.get(change.clause_id, []))[:3]
        if impacted:
            explanation = f"{explanation} Related clauses that may be affected include: {', '.join(impacted)}."

        insights.append(
            {
                "change_id": change.clause_id,
                "semantic_label": label,
                "risk_direction": "neutral",
                "explanation": explanation,
                "confidence": 0.6,
                "citations_to_facts": [change.clause_id],
            }
        )
        change_ids.append(change.clause_id)

        # Build richer summaries
        if "definition" in label.lower():
            def_bullets.append(f"{label}: definition updated.")
        if "Economic terms changed" in explanation or "amounts/percentages" in explanation:
            econ_bullets.append(f"{label}: monetary/percentage terms changed.")
        if "Obligation strengthened" in explanation or "Obligation softened" in explanation:
            nego_bullets.append(f"{label}: obligation strength shifted.")
        if "Key dates shifted" in explanation or "Timing windows changed" in explanation:
            exec_bullets.append(f"{label}: timing changed.")

    summaries = [
        {
            "type": "executive",
            "bullets": [
                "Material changes detected across multiple sections.",
                *exec_bullets[:5],
                "Review sections with numeric, date, or obligation shifts first.",
            ],
            "backing_change_ids": change_ids[:12],
        }
    ]

    if nego_bullets:
        summaries.append(
            {
                "type": "negotiation",
                "bullets": nego_bullets[:6],
                "backing_change_ids": change_ids[:12],
            }
        )
    if econ_bullets:
        summaries.append(
            {
                "type": "economics",
                "bullets": econ_bullets[:6],
                "backing_change_ids": change_ids[:12],
            }
        )
    if def_bullets:
        summaries.append(
            {
                "type": "definitions",
                "bullets": def_bullets[:6],
                "backing_change_ids": change_ids[:12],
            }
        )
    return AiResponse(insights=insights, impacts=[], summaries=summaries, ai_enabled=True)
