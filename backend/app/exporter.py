from io import BytesIO
from typing import List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .models import AiResponse, ChangeSet, MaterialityFinding


def _draw_wrapped_lines(pdf: canvas.Canvas, text: str, x: int, y: int, width: int = 88, step: int = 12) -> int:
    words = (text or "").split()
    if not words:
        return y

    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) <= width:
            line = candidate
            continue
        pdf.drawString(x, y, line)
        y -= step
        line = word
    if line:
        pdf.drawString(x, y, line)
        y -= step
    return y


def build_html_report(changes: List[ChangeSet], materiality: List[MaterialityFinding], ai: Optional[AiResponse] = None) -> str:
    rows = []
    for finding in materiality:
        rows.append(f"<li><b>{finding.category}</b> ({finding.severity}) - {finding.rationale}</li>")

    html = "<html><body><h1>ChangeSense Verification Report</h1>"
    html += f"<p>Total changed clauses: {len(changes)}</p>"
    html += f"<p>Rule-based findings: {len(materiality)}</p>"
    html += "<h2>Material Changes</h2><ul>" + "".join(rows) + "</ul>"

    if ai and ai.summaries:
        html += "<h2>AI Interpretive Appendix</h2>"
        for summary in ai.summaries:
            html += f"<h3>{summary.type}</h3><ul>"
            for bullet in summary.bullets:
                html += f"<li>{bullet}</li>"
            html += "</ul>"

    html += "</body></html>"
    return html


def build_pdf_report(
    changes: List[ChangeSet],
    materiality: List[MaterialityFinding],
    ai: Optional[AiResponse] = None,
    *,
    version_a: str = "Version A",
    version_b: str = "Version B",
    run_id: Optional[str] = None,
    integrity_count: int = 0,
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50

    modified_count = sum(1 for change in changes if change.before_text and change.after_text)
    added_count = sum(1 for change in changes if not change.before_text and change.after_text)
    deleted_count = sum(1 for change in changes if change.before_text and not change.after_text)
    critical_findings = sum(1 for finding in materiality if finding.severity == "high")
    obligation_findings = sum(1 for finding in materiality if finding.category == "obligation_shift")

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "ChangeSense Verification Report")
    y -= 24

    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, "Clause-level deterministic verification completed.")
    y -= 16
    if run_id:
        pdf.drawString(50, y, f"Run ID: {run_id}")
        y -= 16

    pdf.drawString(50, y, f"Version A: {version_a}")
    y -= 14
    pdf.drawString(50, y, f"Version B: {version_b}")
    y -= 24

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Verification Summary")
    y -= 18

    pdf.setFont("Helvetica", 10)
    summary_lines = [
        f"Modified clauses: {modified_count}",
        f"Added clauses: {added_count}",
        f"Deleted clauses: {deleted_count}",
        f"Critical rule findings: {critical_findings}",
        f"Obligation shifts: {obligation_findings}",
        f"Integrity alerts: {integrity_count}",
    ]
    for line in summary_lines:
        pdf.drawString(50, y, line)
        y -= 14

    y -= 8
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Priority Findings")
    y -= 18

    pdf.setFont("Helvetica", 10)
    findings = materiality[:12]
    if not findings:
        pdf.drawString(50, y, "No rule-based material findings detected.")
        y -= 14

    for finding in findings:
        label = f"{finding.category} ({finding.severity})"
        pdf.drawString(50, y, label)
        y -= 12
        y = _draw_wrapped_lines(pdf, finding.rationale, 60, y, width=82, step=11)
        y -= 6
        if y < 110:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 10)

    if ai and ai.summaries:
        pdf.showPage()
        y = height - 50
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, "AI Interpretive Appendix")
        y -= 18
        pdf.setFont("Helvetica", 10)
        for summary in ai.summaries[:4]:
            pdf.drawString(50, y, f"{summary.type.title()}:")
            y -= 12
            for bullet in summary.bullets[:5]:
                y = _draw_wrapped_lines(pdf, f"- {bullet}", 60, y, width=84, step=11)
                if y < 110:
                    pdf.showPage()
                    y = height - 50
                    pdf.setFont("Helvetica", 10)
            y -= 6

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()
