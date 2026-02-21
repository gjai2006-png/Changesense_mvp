from typing import Dict

from .models import AuditLogEntry
from .utils import doc_hash, clause_hash, now_iso


def build_audit(doc_text: str, clause_texts: Dict[str, str]) -> AuditLogEntry:
    clause_hashes = {cid: clause_hash(text) for cid, text in clause_texts.items()}
    return AuditLogEntry(
        doc_hash=doc_hash(doc_text),
        clause_hashes=clause_hashes,
        parser_version="docx-pdf-v1",
        diff_version="token-sentence-v1",
        rules_version="ma-mvp-v1",
        alignment_version="align-v1",
        timestamp=now_iso(),
    )
