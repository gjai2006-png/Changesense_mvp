# ChangeSense MVP

## What This Is
ChangeSense is a deterministic, clause-level verification demo for high-stakes legal documents. The backend accepts two document versions, segments them into clauses, computes structural diffs, flags risk signals (obligation/number/date changes), simulates ghost-change detection, and generates a PDF verification report.

## Backend Tech Stack
- **FastAPI**: HTTP API framework for the MVP endpoints.
- **Uvicorn**: ASGI server for local development.
- **python-docx**: DOCX ingestion for uploads.
- **ReportLab**: PDF report generation.
- **Pydantic**: Typed response models (optional typing clarity in `backend/app/models.py`).

## Backend Logic (Detailed, With Quoted Code)

### 1. Document Ingestion
The API accepts `version_a` and `version_b` uploads in `/compare` and `/scan-integrity`.  
DOCX is parsed into plaintext; TXT is decoded directly:

> `if name.endswith(".docx"):`  
> `    doc = Document(io.BytesIO(data))`  
> `    text = "\n".join(p.text for p in doc.paragraphs if p.text)`

File: `backend/app/main.py`

### 2. Clause Segmentation
Clauses are segmented by numbered headings or ALL-CAPS headings:

> `HEADING_RE = re.compile(r"^\\s*(?:\\d+(?:\\.\\d+)*|[IVX]+|[A-Z]|\\([a-z]\\))\\s*[\\).]\\s+")`  
> `if HEADING_RE.match(ln):`

Each clause is stored with an `id`, `heading`, and `text`.

File: `backend/app/diff.py`

### 3. Structural Diff (Deterministic)
First, clauses are matched by normalized heading key.  
Then, unmatched clauses are paired by **content similarity** using shingles + Jaccard:

> `def _shingles(text: str, k: int = 3) -> set:`  
> `    tokens = re.findall(r"\\w+", text.lower())`  
> `    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}`

> `def _jaccard(a: set, b: set) -> float:`  
> `    return len(a & b) / len(a | b)`

This allows detection of clauses that are renumbered or retitled but semantically similar.  
Final diff output is grouped into `added`, `deleted`, `modified`, and `unchanged`.

File: `backend/app/diff.py`

### 4. Risk Tag Engine (Deterministic Rules)
For each modified clause, the engine flags:
- **Obligation shifts** (modal changes such as `may → shall`)
- **Numeric changes**
- **Date changes**

Quoted examples:

> `OBLIGATION_SHIFT_MAP = {("may", "shall"): "Permission tightened to obligation", ...}`

> `if numbers["changed"]:`  
> `    risk_tags.append("numeric_change")`

File: `backend/app/rules.py`

### 5. Ghost Change Detection (Simulated)
This hackathon MVP simulates “ghost changes” by flagging modified clauses that do **not** include a `[tracked]` marker:

> `tracked = "[tracked]" in after.lower() or "[tracked]" in before.lower()`  
> `if not tracked:`  
> `    ghost_changes.append({...})`

File: `backend/app/main.py`

### 6. Verification Report (PDF)
The `/report` endpoint generates a PDF with summary stats and a verification statement:

> `c.drawString(50, y, "Clause-level deterministic verification completed.")`

File: `backend/app/report.py`

## Run Locally

### Backend
```bash
cd /Users/jaiaakash/Desktop/Changesense/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Gemini AI (Optional)
To enable AI interpretation via Gemini, set an API key before running the backend:

```bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
# Optional override (default is gemini-2.5-flash)
export GEMINI_MODEL="gemini-2.5-flash"
```

Then call:

```
POST /ai/insights?run_id=...&ai_enabled=true
```

### Frontend
```bash
cd /Users/jaiaakash/Desktop/Changesense/frontend
npm install
npm run dev
```

Open `http://localhost:5173` and upload the sample documents in `sample_docs/`.
