from pydantic import BaseModel
from typing import List, Optional

class MessageRequest(BaseModel):
    message: str
    session_id: Optional[int] = None      # if None and user logged in, auto-create
    history: Optional[List[dict]] = []    # used when not logged in

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
