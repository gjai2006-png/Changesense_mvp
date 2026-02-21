from typing import List

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

from .models import ChangeSet, MaterialityFinding


def build_html_report(changes: List[ChangeSet], materiality: List[MaterialityFinding]) -> str:
    rows = []
    for m in materiality:
        rows.append(f"<li><b>{m.category}</b> ({m.severity}) - {m.rationale}</li>")
    html = "<html><body><h1>ChangeSense Report</h1>"
    html += "<h2>Material Changes</h2><ul>" + "".join(rows) + "</ul>"
    html += "</body></html>"
    return html


def build_pdf_report(changes: List[ChangeSet], materiality: List[MaterialityFinding]) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "ChangeSense Verification Report")
    y -= 25
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Material findings: {len(materiality)}")
    y -= 20
    for finding in materiality[:15]:
        c.drawString(50, y, f"{finding.category} ({finding.severity})")
        y -= 14
        if y < 80:
            c.showPage()
            y = height - 50
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
