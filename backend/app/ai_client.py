import json
import os
import urllib.request
from typing import Optional

from pydantic import ValidationError

from .models import AiResponse

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


AI_SCHEMA_HINT = {
    "insights": [
        {
            "change_id": "string",
            "semantic_label": "string",
            "risk_direction": "buyer-friendly | seller-friendly | neutral",
            "explanation": "string",
            "confidence": 0.0,
            "citations_to_facts": ["string"]
        }
    ],
    "impacts": [
        {
            "trigger_change_id": "string",
            "impacted_clause_id": "string",
            "impact_summary": "string",
            "why_linked": "term reference | cross-ref | numeric link",
            "confidence": 0.0
        }
    ],
    "summaries": [
        {
            "type": "executive | negotiation | economics | definitions",
            "bullets": ["string"],
            "backing_change_ids": ["string"]
        }
    ]
}


def build_prompt(payload: dict) -> str:
    return (
        "You are ChangeSense AI. You must NOT invent changes. "
        "Only interpret the facts provided. Output valid JSON ONLY.\n\n"
        "Rules:\n"
        "- Separate facts from interpretation.\n"
        "- Use cautious language: may/likely.\n"
        "- Cite deterministic IDs in citations_to_facts.\n"
        "- If uncertain, lower confidence.\n\n"
        "Return JSON with keys: insights, impacts, summaries.\n"
        f"JSON schema hint:\n{json.dumps(AI_SCHEMA_HINT, indent=2)}\n\n"
        f"FACTS:\n{json.dumps(payload, indent=2)}\n"
    )


def call_gemini(payload: dict, api_key: Optional[str] = None, model: Optional[str] = None) -> dict:
    api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY or GOOGLE_API_KEY")

    model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": build_prompt(payload)}],
            }
        ]
    }

    req = urllib.request.Request(
        GEMINI_API_URL.format(model=model),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)

    text = None
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        text = None

    if not text:
        raise RuntimeError("Gemini returned empty content")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {
            "insights": [],
            "impacts": [],
            "summaries": [],
            "raw_text": text,
        }

    # Schema validation (guardrail)
    try:
        AiResponse(**{**parsed, "ai_enabled": True})
        return parsed
    except ValidationError:
        return {
            "insights": [],
            "impacts": [],
            "summaries": [],
            "raw_text": text,
        }
