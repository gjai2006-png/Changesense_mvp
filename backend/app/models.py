from pydantic import BaseModel
from typing import List, Optional, Dict


class Clause(BaseModel):
    id: str
    heading: str
    text: str


class ModifiedClause(BaseModel):
    id: str
    heading: str
    before: str
    after: str
    similarity: float


class DiffResult(BaseModel):
    clauses: Dict[str, List]


class RiskTag(BaseModel):
    id: str
    heading: str
    risk_tags: List[str]
    obligation_shifts: List[Dict]
    numeric: Dict
    dates: Dict


class CompareResponse(BaseModel):
    clauses: Dict[str, List]
    risks: List[RiskTag]
    stats: Dict
    generated_at: str


class GhostChange(BaseModel):
    id: str
    heading: str
    reason: str
    before: str
    after: str


class IntegrityResponse(BaseModel):
    ghost_changes: List[GhostChange]
    generated_at: str
