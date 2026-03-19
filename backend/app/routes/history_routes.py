import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from app.models import User, ChatSession, ChatMessage
from app.auth import get_current_user

router = APIRouter(prefix="/history", tags=["history"])


# ── Sessions ─────────────────────────────────────────────────

@router.get("/sessions")
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [_session_dict(s) for s in sessions]


@router.post("/sessions")
def create_session(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = ChatSession(user_id=user.id, title="New Chat")
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_dict(session)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = _get_session(session_id, user.id, db)
    db.delete(session)
    db.commit()
    return {"ok": True}


@router.patch("/sessions/{session_id}/title")
def rename_session(session_id: int, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = _get_session(session_id, user.id, db)
    session.title = body.get("title", session.title)[:80]
    db.commit()
    return _session_dict(session)


# ── Messages ─────────────────────────────────────────────────

@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_session(session_id, user.id, db)
    msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at).all()
    return [_msg_dict(m) for m in msgs]


# ── Internal helper used by message route ────────────────────

def save_message(db: Session, session_id: int, role: str, content: str, extra: dict = None):
    extra = extra or {}
    msg = ChatMessage(
        session_id  = session_id,
        role        = role,
        content     = content,
        is_claim    = extra.get("is_claim", False),
        verdict     = extra.get("verdict"),
        confidence  = extra.get("confidence"),
        ml_score    = extra.get("ml_score"),
        ai_score    = extra.get("ai_score"),
        explanation = extra.get("explanation"),
        evidence    = json.dumps(extra.get("evidence", [])),
    )
    db.add(msg)
    # Auto-title session from first user message
    if role == "user":
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session and session.title == "New Chat":
            session.title = content[:60]
        if session:
            from datetime import datetime
            session.updated_at = datetime.utcnow()
    db.commit()
    return msg


# ── Helpers ──────────────────────────────────────────────────

def _get_session(session_id: int, user_id: int, db: Session) -> ChatSession:
    s = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


def _session_dict(s: ChatSession) -> dict:
    return {"id": s.id, "title": s.title, "created_at": s.created_at.isoformat(), "updated_at": s.updated_at.isoformat()}


def _msg_dict(m: ChatMessage) -> dict:
    return {
        "id": m.id, "role": m.role, "content": m.content,
        "is_claim": m.is_claim, "verdict": m.verdict,
        "confidence": m.confidence, "ml_score": m.ml_score, "ai_score": m.ai_score,
        "explanation": m.explanation,
        "evidence": json.loads(m.evidence) if m.evidence else [],
        "created_at": m.created_at.isoformat(),
    }
