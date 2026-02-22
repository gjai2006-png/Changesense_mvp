from typing import List

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

from .models import ChangeSet, MaterialityFinding, AiResponse


def build_html_report(changes: List[ChangeSet], materiality: List[MaterialityFinding], ai: AiResponse | None = None) -> str:
    rows = []
    for m in materiality:
        rows.append(f"<li><b>{m.category}</b> ({m.severity}) - {m.rationale}</li>")
    html = "<html><body><h1>ChangeSense Report</h1>"
    html += "<h2>Material Changes</h2><ul>" + "".join(rows) + "</ul>"
    if ai and ai.summaries:
        html += "<h2>AI Summary (Interpretive)</h2>"
        for summary in ai.summaries:
            html += f"<h3>{summary.type}</h3><ul>"
            for bullet in summary.bullets:
                html += f"<li>{bullet}</li>"
            html += "</ul>"
    html += "</body></html>"
    return html


def build_pdf_report(changes: List[ChangeSet], materiality: List[MaterialityFinding], ai: AiResponse | None = None) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "ChangeSense Verification Report (AI-Enhanced)")
    y -= 25
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Material findings: {len(materiality)}")
    y -= 20
    for finding in materiality[:15]:
        c.drawString(50, y, f"{finding.category} ({finding.severity}) - {finding.rationale}")
        y -= 14
        if y < 80:
            c.showPage()
            y = height - 50

    if ai and ai.summaries:
        y -= 10
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "AI Interpretive Summary")
        y -= 18
        c.setFont("Helvetica", 11)
        for summary in ai.summaries:
            c.drawString(50, y, f"{summary.type.title()}:")
            y -= 14
            for bullet in summary.bullets[:6]:
                c.drawString(60, y, f"- {bullet}")
                y -= 12
                if y < 80:
                    c.showPage()
                    y = height - 50

    if ai and ai.insights:
        c.showPage()
        y = height - 50
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "AI Per-Change Interpretation")
        y -= 18
        c.setFont("Helvetica", 10)
        for insight in ai.insights[:60]:
            c.drawString(50, y, f"{insight.semantic_label}")
            y -= 12
            c.drawString(60, y, insight.explanation[:160])
            y -= 12
            if y < 80:
                c.showPage()
                y = height - 50

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
