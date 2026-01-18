from pydantic import BaseModel
from typing import List, Optional

class AnalyzeRequest(BaseModel):
    text: str
    explain: bool = False


class AnalyzeResponse(BaseModel):
    verdict: str
    confidence: float
    ml_score: float
    ai_score: float
    keywords: List[str]
    explanation: str
    evidence: List[str]
