from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from app.schemas import MessageRequest, MessageResponse
from app.analysis.ml import run_ml_analysis
from app.analysis.ai import run_ai_analysis
from app.analysis.explain import explain
from app.analysis.evidence import fetch_evidence
from app.analysis.chat import is_claim, run_chat
from app.logic.decision import decide
from app.auth import get_current_user_optional
from app.models import User, ChatSession
from app.routes.history_routes import save_message

router = APIRouter()


@router.post("/message", response_model=MessageResponse)
def message(
    req: MessageRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    text = req.message.strip()

    # Resolve or create session for logged-in users
    session_id = None
    if user:
        if req.session_id:
            s = db.query(ChatSession).filter(ChatSession.id == req.session_id, ChatSession.user_id == user.id).first()
            session_id = s.id if s else None
        if not session_id:
            s = ChatSession(user_id=user.id, title="New Chat")
            db.add(s)
            db.commit()
            db.refresh(s)
            session_id = s.id

    # Build history from DB if logged in, else use request history
    if session_id:
        from app.routes.history_routes import _msg_dict
        from app.models import ChatMessage
        db_msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at).all()
        history = [{"role": m.role, "content": m.content} for m in db_msgs[-12:]]
    else:
        history = req.history or []

    # Save user message
    if session_id:
        save_message(db, session_id, "user", text)

    if not is_claim(text):
        reply = run_chat(text, history)
        if session_id:
            save_message(db, session_id, "assistant", reply)
        return {"is_claim": False, "session_id": session_id, "reply": reply}

    # Full fact-check pipeline
    ml = run_ml_analysis(text)
    raw_ai_score, explanation = run_ai_analysis(text)
    ai_score = float(raw_ai_score) if raw_ai_score is not None else 0.0
    evidence_score, evidence_sources = fetch_evidence(text)
    verdict, confidence = decide(
        ml_fake=ml["fake"],
        ai_fake=ai_score,
        evidence_score=evidence_score,
    )

    result = {
        "is_claim": True,
        "session_id": session_id,
        "verdict": verdict,
        "confidence": confidence,
        "ml_score": ml["fake"],
        "ai_score": ai_score,
        "explanation": explanation,
        "evidence": evidence_sources or [],
    }

    if session_id:
        save_message(db, session_id, "assistant", explanation, extra={
            "is_claim": True,
            "verdict": verdict,
            "confidence": confidence,
            "ml_score": ml["fake"],
            "ai_score": ai_score,
            "explanation": explanation,
            "evidence": evidence_sources or [],
        })

    return result
