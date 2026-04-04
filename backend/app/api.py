from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# Simple in-memory rate limiter: max 30 requests per minute per user/IP
_rate_store: dict = defaultdict(list)
_RATE_LIMIT  = 30
_RATE_WINDOW = 60  # seconds


def _check_rate_limit(key: str):
    now = time.time()
    window_start = now - _RATE_WINDOW
    _rate_store[key] = [t for t in _rate_store[key] if t > window_start]
    if len(_rate_store[key]) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
    _rate_store[key].append(now)

from database import get_db
from app.schemas import MessageRequest, MessageResponse
from app.analysis.ml import run_ml_analysis
from app.analysis.ai import run_ai_analysis
from app.analysis.evidence import fetch_evidence
from app.analysis.chat import is_claim, run_chat
from app.analysis.manipulation import analyze_manipulation
from app.analysis.claim_extractor import extract_claims
from app.analysis.drift import record as record_drift
from app.analysis.highlight import get_highlights
from app.analysis.credibility import update_from_stance, get_all_scores
from app.logic.decision import decide
from app.auth import get_current_user_optional
from app.models import User, ChatSession
from app.routes.history_routes import save_message

router = APIRouter()


class FeedbackRequest(BaseModel):
    claim_text: str
    predicted: str
    actual: str
    confidence: Optional[float] = None


@router.get("/credibility")
def source_credibility():
    """Return dynamic trust scores for all tracked domains."""
    return {"sources": get_all_scores()}


@router.post("/feedback")
def submit_feedback(
    req: FeedbackRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Store user correction for future retraining."""
    from app.models import UserFeedback
    if req.actual not in ("fake", "real"):
        raise HTTPException(status_code=400, detail="actual must be 'fake' or 'real'")
    fb = UserFeedback(
        user_id    = user.id if user else None,
        claim_text = req.claim_text[:1000],
        predicted  = req.predicted,
        actual     = req.actual,
        confidence = req.confidence,
    )
    db.add(fb)
    db.commit()

    # Update source credibility based on feedback
    # (we don't have articles here, but log the correction for future use)
    logger.info("Feedback: predicted=%s actual=%s conf=%.2f",
                req.predicted, req.actual, req.confidence or 0)

    return {"message": "Feedback recorded. Thank you."}


def _run_pipeline_parallel(text: str):
    """Run ML, AI, and NewsAPI evidence all in parallel for speed."""
    results = {"ml": None, "ai": (None, ""), "evidence": (None, [], [])}

    def do_ml():
        return run_ml_analysis(text)

    def do_ai():
        return run_ai_analysis(text)

    def do_evidence():
        return fetch_evidence(text)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(do_ml): "ml",
            executor.submit(do_ai): "ai",
            executor.submit(do_evidence): "evidence",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                logger.warning("Pipeline step '%s' failed: %s", key, e)

    return results


@router.post("/message", response_model=MessageResponse)
def message(
    req: MessageRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    # Rate limit by user ID or anonymous key
    rate_key = str(user.id) if user else "anon"
    _check_rate_limit(rate_key)

    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="Message too long (max 2000 characters)")

    # Resolve or create session for logged-in users
    session_id = None
    if user:
        if req.session_id:
            s = db.query(ChatSession).filter(
                ChatSession.id == req.session_id,
                ChatSession.user_id == user.id
            ).first()
            session_id = s.id if s else None
        if not session_id:
            s = ChatSession(user_id=user.id, title="New Chat")
            db.add(s)
            db.commit()
            db.refresh(s)
            session_id = s.id

    # Build history
    if session_id:
        from app.models import ChatMessage
        db_msgs = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at).all()
        history = [{"role": m.role, "content": m.content} for m in db_msgs[-12:]]
    else:
        history = req.history or []

    # Save user message
    if session_id:
        save_message(db, session_id, "user", text)

    # Chat vs claim
    if not is_claim(text):
        reply = run_chat(text, history)
        if session_id:
            save_message(db, session_id, "assistant", reply)
        return {"is_claim": False, "session_id": session_id, "reply": reply}

    # ── Claim extraction for long inputs ──────────────────────
    # For short inputs this returns [text] immediately (no LLM call)
    sub_claims = extract_claims(text)
    primary_claim = sub_claims[0]  # verify the primary claim

    # ── Run all three in parallel ──────────────────────────────
    pipeline = _run_pipeline_parallel(primary_claim)

    ml_result = pipeline["ml"] or {"fake": 0.5}
    raw_ai_score, explanation = pipeline["ai"] if pipeline["ai"] else (None, "")
    evidence_score, evidence_urls, evidence_articles = pipeline["evidence"] if pipeline["evidence"] else (None, [], [])

    ai_score = float(raw_ai_score) if raw_ai_score is not None else 0.5

    # Manipulation analysis (fast, no API call)
    manip_score, manip_signals = analyze_manipulation(text)

    # ── Decision ───────────────────────────────────────────────
    verdict, confidence = decide(
        ml_fake=ml_result["fake"],
        ai_fake=ai_score,
        evidence_score=evidence_score,
    )

    # Highlighted suspicious phrases (after verdict is known)
    highlights = get_highlights(text) if verdict == "fake" or manip_score > 0.2 else []

    # Build evidence display: prefer article URLs, fallback to plain URLs
    display_evidence = (
        [a["url"] for a in evidence_articles if a.get("url")]
        or evidence_urls
    )

    # Record for drift detection
    record_drift(verdict, confidence)

    # Temporal claim tracking
    import hashlib
    from app.models import ClaimRecord
    claim_hash = hashlib.sha256(primary_claim.lower().strip().encode()).hexdigest()
    db.add(ClaimRecord(
        claim_hash=claim_hash,
        claim_text=primary_claim[:500],
        verdict=verdict,
        confidence=confidence,
        ml_score=ml_result["fake"],
        ai_score=ai_score,
        evidence_score=evidence_score,
    ))
    db.commit()

    # Check if this claim has been seen before with a different verdict
    prior = db.query(ClaimRecord).filter(
        ClaimRecord.claim_hash == claim_hash,
        ClaimRecord.verdict != verdict,
    ).count()
    verdict_changed = prior > 0

    # Stance summary for frontend contradiction meter
    stance_summary = {"support": 0, "contradict": 0, "neutral": 0}
    for a in evidence_articles:
        s = a.get("stance", "neutral")
        stance_summary[s] = stance_summary.get(s, 0) + 1

    result = {
        "is_claim": True,
        "session_id": session_id,
        "verdict": verdict,
        "confidence": confidence,
        "ml_score": ml_result["fake"],
        "ai_score": ai_score,
        "evidence_score": evidence_score,
        "explanation": explanation,
        "evidence": display_evidence,
        "evidence_articles": evidence_articles,
        "stance_summary": stance_summary,
        "manipulation_score": manip_score,
        "manipulation_signals": manip_signals,
        "highlights": highlights,
        "sub_claims": sub_claims if len(sub_claims) > 1 else None,
        "primary_claim": primary_claim if len(sub_claims) > 1 else None,
        "verdict_changed": verdict_changed,
    }

    if session_id:
        save_message(db, session_id, "assistant", explanation, extra={
            "is_claim": True,
            "verdict": verdict,
            "confidence": confidence,
            "ml_score": ml_result["fake"],
            "ai_score": ai_score,
            "explanation": explanation,
            "evidence": display_evidence,
        })

    return result
