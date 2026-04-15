from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import re

# Strip HTML tags and null bytes from user-supplied strings
_TAG_RE = re.compile(r"<[^>]+>")

def _sanitize(v: str) -> str:
    if not isinstance(v, str):
        return v
    v = v.replace("\x00", "")          # null bytes
    v = _TAG_RE.sub("", v)             # strip HTML tags
    return v.strip()


class MessageRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    history: Optional[List[dict]] = Field(default_factory=list)
    image_url: Optional[str] = None   # URL of image attached to the claim

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v):
        v = _sanitize(v)
        # Allow short messages when used with image attachment
        if not v:
            raise ValueError("Message cannot be empty")
        return v

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v):
        if v is None:
            return v
        v = v.strip()
        if v.startswith(("http://", "https://")):
            return v[:500]
        if v.startswith("data:image/") and ";base64," in v:
            return v[:400000]
        raise ValueError("image_url must be a valid http/https URL or data:image/* base64 payload")

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
    entity_verifications: Optional[List[dict]] = None
    entity_risk: Optional[float] = None
    detected_language: Optional[str] = None
    was_translated: Optional[bool] = None
    image_check: Optional[dict] = None
    image_description: Optional[str] = None
    fact_checks: Optional[List[dict]] = None
    previously_debunked: Optional[bool] = None
    debunk_sources: Optional[List[str]] = None
    spread_risk: Optional[float] = None
    explainability: Optional[dict] = None
    moderation_summary: Optional[dict] = None
