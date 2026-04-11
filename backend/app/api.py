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
from app.analysis.claim_extractor import extract_claims
from app.analysis.drift import record as record_drift
from app.analysis.highlight import get_highlights
from app.analysis.credibility import update_from_stance, get_all_scores
from app.analysis.multilingual import normalize_claim
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


def _run_pipeline_parallel(text: str, db=None):
    """Run ML, AI, evidence, image check, and platform tracker in parallel."""
    results = {
        "ml": None, "ai": (None, ""), "evidence": (None, [], []),
        "image": None, "platform": None,
    }

    def do_ml():       return run_ml_analysis(text)
    def do_ai():       return run_ai_analysis(text)
    def do_evidence(): return fetch_evidence(text)
    def do_image():
        try:
            from app.analysis.image_check import check_image_consistency
            return check_image_consistency(text)
        except Exception:
            return None
    def do_platform():
        try:
            from app.analysis.platform_tracker import get_spread_indicators
            return get_spread_indicators(text, db)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(do_ml):       "ml",
            executor.submit(do_ai):       "ai",
            executor.submit(do_evidence): "evidence",
            executor.submit(do_image):    "image",
            executor.submit(do_platform): "platform",
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

    # ── Multi-language normalization ───────────────────────────
    original_text = text
    detected_lang = "English"
    was_translated = False
    try:
        text, detected_lang, was_translated = normalize_claim(text)
    except Exception as e:
        logger.debug("Language normalization skipped: %s", e)

    # ── Claim extraction for long inputs ──────────────────────
    sub_claims = extract_claims(text)
    primary_claim = sub_claims[0]

    # ── Run all five in parallel ───────────────────────────────
    pipeline = _run_pipeline_parallel(primary_claim, db)

    ml_result = pipeline["ml"] or {"fake": 0.5}
    raw_ai_score, explanation = pipeline["ai"] if pipeline["ai"] else (None, "")
    evidence_score, evidence_urls, evidence_articles = pipeline["evidence"] if pipeline["evidence"] else (None, [], [])
    image_result    = pipeline["image"] or {}
    platform_result = pipeline["platform"] or {}

    ai_score = float(raw_ai_score) if raw_ai_score is not None else 0.5

    # Manipulation analysis (fast, no API call)
    manip_score, manip_signals = analyze_manipulation(text)

    # ── Wikidata entity verification (Level 90) ────────────────
    entity_verifications = []
    entity_risk = 0.0
    try:
        from app.analysis.wikidata import verify_entities, get_entity_risk_score
        entity_verifications = verify_entities(primary_claim)
        entity_risk = get_entity_risk_score(entity_verifications)
    except Exception as e:
        logger.debug("Wikidata verification skipped: %s", e)

    # ── Decision ───────────────────────────────────────────────
    # Blend entity risk + image mismatch into ml_score
    image_mismatch_risk = image_result.get("mismatch_risk", 0.0)
    adjusted_ml = min(1.0, ml_result["fake"] + entity_risk * 0.15 + image_mismatch_risk * 0.10)
    verdict, confidence = decide(
        ml_fake=adjusted_ml,
        ai_fake=ai_score,
        evidence_score=evidence_score,
        text_len=len(primary_claim),
    )

    # If already debunked by fact-checkers, override to fake with high confidence
    if platform_result.get("previously_debunked") and verdict != "fake":
        verdict    = "fake"
        confidence = max(confidence, 0.85)
        logger.info("Verdict overridden to fake — previously debunked by: %s",
                    platform_result.get("debunk_sources", []))

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
        "entity_verifications": entity_verifications if entity_verifications else None,
        "entity_risk": entity_risk if entity_risk > 0 else None,
        # Multi-language
        "detected_language": detected_lang if was_translated else None,
        "was_translated": was_translated if was_translated else None,
        # Image consistency
        "image_check": image_result if image_result.get("images_found") else None,
        # Platform spread / existing fact-checks
        "fact_checks": platform_result.get("fact_checks") or None,
        "previously_debunked": platform_result.get("previously_debunked") or None,
        "debunk_sources": platform_result.get("debunk_sources") or None,
        "spread_risk": platform_result.get("spread_risk") if platform_result.get("spread_risk", 0) > 0 else None,
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
