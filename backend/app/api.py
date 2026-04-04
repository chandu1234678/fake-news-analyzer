from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

from database import get_db
from app.schemas import MessageRequest, MessageResponse
from app.analysis.ml import run_ml_analysis
from app.analysis.ai import run_ai_analysis
from app.analysis.evidence import fetch_evidence
from app.analysis.chat import is_claim, run_chat
from app.analysis.manipulation import analyze_manipulation
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

    # ── Run all three in parallel ──────────────────────────────
    pipeline = _run_pipeline_parallel(text)

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

    # Build evidence display: prefer article URLs, fallback to plain URLs
    display_evidence = (
        [a["url"] for a in evidence_articles if a.get("url")]
        or evidence_urls
    )

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
