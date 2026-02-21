from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .diff import compute_diff
from .rules import risk_tag_clause
from .utils import now_iso
from .report import build_pdf_report

import io
from docx import Document

app = FastAPI(title="ChangeSense MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_RESULT = {"compare": None}


def read_upload(file: UploadFile) -> str:
    if not file:
        raise HTTPException(status_code=400, detail="Missing file")

    name = (file.filename or "").lower()
    data = file.file.read()

    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs if p.text)
        return text

    return data.decode("utf-8", errors="ignore")


@app.post("/compare")
async def compare(version_a: UploadFile = File(...), version_b: UploadFile = File(...)):
    a_text = read_upload(version_a)
    b_text = read_upload(version_b)

    diff = compute_diff(a_text, b_text)
    modified = diff["clauses"]["modified"]

    risks = [risk_tag_clause(cl) for cl in modified]

    stats = {
        "modified_count": len(modified),
        "added_count": len(diff["clauses"]["added"]),
        "deleted_count": len(diff["clauses"]["deleted"]),
        "high_risk_count": sum(1 for r in risks if r["risk_tags"]),
        "obligation_shift_count": sum(1 for r in risks if r["obligation_shifts"]),
    }

    payload = {
        "clauses": diff["clauses"],
        "risks": risks,
        "stats": stats,
        "generated_at": now_iso(),
    }

    LAST_RESULT["compare"] = payload
    return payload


@app.post("/scan-integrity")
async def scan_integrity(version_a: UploadFile = File(...), version_b: UploadFile = File(...)):
    a_text = read_upload(version_a)
    b_text = read_upload(version_b)

    diff = compute_diff(a_text, b_text)
    modified = diff["clauses"]["modified"]

    ghost_changes = []
    for clause in modified:
        before = clause["before"]
        after = clause["after"]
        tracked = "[tracked]" in after.lower() or "[tracked]" in before.lower()
        if not tracked:
            ghost_changes.append(
                {
                    "id": clause["id"],
                    "heading": clause["heading"],
                    "reason": "Edited text without track-change marker",
                    "before": before,
                    "after": after,
                }
            )

    payload = {"ghost_changes": ghost_changes, "generated_at": now_iso()}
    return payload


@app.get("/report")
async def report():
    data = LAST_RESULT.get("compare")
    if not data:
        raise HTTPException(status_code=400, detail="No comparison available")

    summary = {
        "deal_name": "Demo Deal",
        "version_a": "Version A",
        "version_b": "Version B",
        "modified_count": data["stats"]["modified_count"],
        "added_count": data["stats"]["added_count"],
        "deleted_count": data["stats"]["deleted_count"],
        "high_risk_count": data["stats"]["high_risk_count"],
        "obligation_shift_count": data["stats"]["obligation_shift_count"],
    }

    pdf = build_pdf_report(summary)
    return Response(content=pdf, media_type="application/pdf")
