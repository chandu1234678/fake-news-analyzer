from pydantic import BaseModel
from typing import List, Optional

class MessageRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    history: Optional[List[dict]] = []

class MessageResponse(BaseModel):
    is_claim: bool
    session_id: Optional[int] = None
    reply: Optional[str] = None
    verdict: Optional[str] = None
    confidence: Optional[float] = None
    ml_score: Optional[float] = None
    ai_score: Optional[float] = None
    explanation: Optional[str] = None
    evidence: Optional[List[str]] = None
    evidence_score: Optional[float] = None
    evidence_articles: Optional[List[dict]] = None
    # Stance breakdown: {"support": int, "contradict": int, "neutral": int}
    stance_summary: Optional[dict] = None
    # Manipulation detection
    manipulation_score: Optional[float] = None
    manipulation_signals: Optional[List[str]] = None
    highlights: Optional[List[dict]] = None
    sub_claims: Optional[List[str]] = None
    primary_claim: Optional[str] = None
    verdict_changed: Optional[bool] = None
