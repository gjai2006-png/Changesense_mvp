from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def build_pdf_report(summary: dict) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "ChangeSense Verification Report")

    y -= 30
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Deal Name: {summary.get('deal_name', 'N/A')}")

    y -= 20
    c.drawString(50, y, f"Version A: {summary.get('version_a', 'Version A')}")
    y -= 15
    c.drawString(50, y, f"Version B: {summary.get('version_b', 'Version B')}")

    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Summary Stats")

    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Total Clauses Modified: {summary.get('modified_count', 0)}")
    y -= 15
    c.drawString(50, y, f"Added Clauses: {summary.get('added_count', 0)}")
    y -= 15
    c.drawString(50, y, f"Deleted Clauses: {summary.get('deleted_count', 0)}")
    y -= 15
    c.drawString(50, y, f"High Risk Changes: {summary.get('high_risk_count', 0)}")
    y -= 15
    c.drawString(50, y, f"Obligation Shifts: {summary.get('obligation_shift_count', 0)}")

    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Verification Statement")

    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(50, y, "Clause-level deterministic verification completed.")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()
