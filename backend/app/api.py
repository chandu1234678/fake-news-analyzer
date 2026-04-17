from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os

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
from app.analysis.highlight import get_highlights, get_highlights_with_shap
from app.analysis.credibility import update_from_stance, get_all_scores
from app.analysis.multilingual import normalize_claim
from app.analysis.explainability import build_explanation
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


@router.get("/velocity/stats")
def velocity_stats():
    """Return velocity tracking statistics."""
    try:
        from app.analysis.velocity import get_stats, get_top_viral
        stats = get_stats()
        top_viral = get_top_viral(limit=10)
        return {
            "stats": stats,
            "top_viral": top_viral
        }
    except Exception as e:
        logger.error("Velocity stats failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve velocity stats")


@router.get("/clustering/stats")
def clustering_stats():
    """Return semantic clustering statistics."""
    try:
        from app.analysis.semantic_clustering import get_cluster_stats, get_top_clusters
        stats = get_cluster_stats()
        top_clusters = get_top_clusters(limit=10)
        return {
            "stats": stats,
            "top_clusters": top_clusters
        }
    except Exception as e:
        logger.error("Clustering stats failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve clustering stats")


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

    logger.info("Feedback: predicted=%s actual=%s conf=%.2f",
                req.predicted, req.actual, req.confidence or 0)

    # Trigger auto-retraining if threshold reached
    try:
        from app.analysis.continuous_learning import maybe_retrain
        retrain_status = maybe_retrain(db)
        if retrain_status.get("triggered"):
            logger.info("Auto-retrain triggered: %s", retrain_status["reason"])
    except Exception as e:
        logger.debug("Continuous learning check failed: %s", e)

    return {"message": "Feedback recorded. Thank you."}


def _run_pipeline_parallel(text: str, image_url: str = None, db=None):
    """Run ML, AI, evidence in parallel. Image/platform only if configured."""
    results = {
        "ml": None, "ai": (None, ""), "evidence": (None, [], []),
        "image": None, "platform": None,
    }

    def do_ml():       return run_ml_analysis(text)
    def do_ai():       return run_ai_analysis(text)
    def do_evidence(): return fetch_evidence(text)

    # Only run image check if an image was explicitly provided
    def do_image():
        if not image_url:
            return None
        try:
            from app.analysis.image_check import check_image_consistency
            return check_image_consistency(text, image_source=image_url)
        except Exception:
            return None

    # Only run platform tracker if Google Fact Check API key is set
    def do_platform():
        if not os.getenv("GOOGLE_FACTCHECK_API_KEY"):
            return None
        try:
            from app.analysis.platform_tracker import get_spread_indicators
            return get_spread_indicators(text, db)
        except Exception:
            return None

    # Cap at 3 workers to stay within 512MB RAM on Render free tier
    # image/platform only run when explicitly needed
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(do_ml):       "ml",
            executor.submit(do_ai):       "ai",
            executor.submit(do_evidence): "evidence",
        }
        # Only add image/platform if needed (avoids spawning extra threads)
        if image_url:
            futures[executor.submit(do_image)] = "image"
        if os.getenv("GOOGLE_FACTCHECK_API_KEY"):
            futures[executor.submit(do_platform)] = "platform"

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

    # Chat vs claim — if image attached, always run image analysis first
    if req.image_url:
        if not is_claim(text):
            # Image with a chat-style message → describe image via Gemini Vision and reply
            try:
                from app.analysis.image_check import check_image_consistency
                img_result = check_image_consistency(text, image_source=req.image_url)
                description = img_result.get("description", "")
                logger.info("Image chat: images_found=%s desc=%s",
                            img_result.get("images_found"), description[:80] if description else "NONE")
                if description and img_result.get("images_found"):
                    reply = run_chat(
                        f"The user sent an image. Here is what the image shows: {description}\n\nUser message: {text}",
                        history
                    )
                else:
                    reply = run_chat(text, history)
            except Exception as e:
                logger.warning("Image chat path failed: %s", e)
                reply = run_chat(text, history)
            if session_id:
                save_message(db, session_id, "assistant", reply)
            return {"is_claim": False, "session_id": session_id, "reply": reply}
    elif not is_claim(text):
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
    if not sub_claims:
        sub_claims = [text]
    primary_claim = sub_claims[0]

    # ── Run core pipeline (3 workers max for 512MB RAM) ───────
    pipeline = _run_pipeline_parallel(primary_claim, image_url=req.image_url, db=db)

    ml_result = pipeline["ml"] or {"fake": 0.5}
    raw_ai_score, explanation = pipeline["ai"] if pipeline["ai"] else (None, "")
    evidence_score, evidence_urls, evidence_articles = pipeline["evidence"] if pipeline["evidence"] else (None, [], [])
    image_result    = pipeline["image"] or {}
    platform_result = pipeline["platform"] or {}

    ai_score = float(raw_ai_score) if raw_ai_score is not None else 0.5

    # If image was analyzed, prepend its description to the explanation context
    image_description = image_result.get("description", "")
    if image_description and req.image_url:
        logger.info("Image analyzed: %s", image_description[:100])

    # Manipulation analysis (fast, no API call)
    manip_score, manip_signals = analyze_manipulation(text)

    # ── Velocity tracking (rapid spread detection) ────────────
    velocity_metrics = None
    try:
        from app.analysis.velocity import track_claim
        velocity_metrics = track_claim(primary_claim)
        logger.debug("Velocity: score=%.3f viral=%s trending=%s",
                    velocity_metrics.get("velocity_score", 0),
                    velocity_metrics.get("is_viral", False),
                    velocity_metrics.get("is_trending", False))
    except Exception as e:
        logger.warning("Velocity tracking failed: %s", e)
        velocity_metrics = {
            "velocity_score": 0.0,
            "is_viral": False,
            "is_trending": False
        }
    
    # ── Semantic clustering (Phase 2.5) ────────────────────────
    cluster_data = None
    try:
        from app.analysis.semantic_clustering import cluster_claim
        cluster_data = cluster_claim(primary_claim)
        if cluster_data and not cluster_data.get("error"):
            logger.debug("Clustering: cluster_id=%s size=%d campaign_score=%.3f",
                        cluster_data.get("cluster_id"),
                        cluster_data.get("cluster_size", 0),
                        cluster_data.get("campaign_score", 0))
    except ImportError as e:
        logger.debug("Semantic clustering not available: %s", e)
        cluster_data = None
    except Exception as e:
        logger.warning("Semantic clustering failed: %s", e)
        cluster_data = None
    
    # Default cluster data if not available
    if not cluster_data:
        cluster_data = {
            "cluster_id": None,
            "cluster_size": 1,
            "campaign_score": 0.0,
            "is_coordinated_campaign": False
        }
    
    # ── Social graph analysis (Phase 2.4) ──────────────────────
    # Only run if enabled (requires API keys)
    social_data = None
    if os.getenv("SOCIAL_GRAPH_ENABLED", "false").lower() == "true":
        try:
            from app.analysis.social_graph import analyze_social_spread
            social_data = analyze_social_spread(primary_claim, velocity_metrics)
            if social_data:
                logger.debug("Social graph: campaign_score=%.3f coordinated=%s",
                            social_data.get("campaign_score", 0),
                            social_data.get("is_coordinated_campaign", False))
        except ImportError as e:
            logger.debug("Social graph analysis not available: %s", e)
            social_data = None
        except Exception as e:
            logger.warning("Social graph analysis failed: %s", e)
            social_data = None

    # ── Domain classification (Phase 3.3) ──────────────────────
    domain_info = None
    try:
        from app.analysis.domain_classifier import classify_domain, get_domain_specific_context
        domain, domain_confidence, domain_scores = classify_domain(primary_claim)
        context = get_domain_specific_context(domain)
        
        # Check for domain-specific red flags
        red_flags_detected = [
            flag for flag in context['red_flags']
            if flag.lower() in primary_claim.lower()
        ]
        
        domain_info = {
            'category': domain,
            'confidence': domain_confidence,
            'scores': domain_scores,
            'red_flags_detected': red_flags_detected,
            'trusted_sources': context['trusted_sources'][:5],  # Top 5
            'verification_tips': context['verification_tips']
        }
        
        logger.info("Domain classified: %s (confidence: %.3f)", domain, domain_confidence)
    except Exception as e:
        logger.error("Domain classification failed: %s", e, exc_info=True)
    
    # ── Wikidata entity verification (only if enabled) ────────
    # Disabled by default on free tier — set WIKIDATA_ENABLED=true to enable
    entity_verifications = []
    entity_risk = 0.0
    if os.getenv("WIKIDATA_ENABLED", "false").lower() == "true":
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

    # ── Cooldown score (viral misinformation risk) ────────────
    cooldown_data = None
    try:
        from app.analysis.cooldown import (
            calculate_cooldown_score,
            get_evidence_conflict_score,
            get_emotional_intensity_score
        )
        
        # Calculate component scores
        fake_probability = adjusted_ml if verdict == "fake" else (1.0 - confidence)
        velocity_score = velocity_metrics.get("velocity_score", 0.0)
        
        # Stance summary for evidence conflict
        stance_summary = {"support": 0, "contradict": 0, "neutral": 0}
        for a in evidence_articles:
            s = a.get("stance", "neutral")
            stance_summary[s] = stance_summary.get(s, 0) + 1
        
        emotional_intensity = get_emotional_intensity_score(manip_score, manip_signals)
        evidence_conflict = get_evidence_conflict_score(evidence_score, stance_summary)
        
        # Calculate cooldown score
        cooldown_score, cooldown_level, cooldown_breakdown = calculate_cooldown_score(
            fake_probability=fake_probability,
            velocity_score=velocity_score,
            emotional_intensity=emotional_intensity,
            evidence_conflict=evidence_conflict
        )
        
        cooldown_data = {
            "cooldown_score": cooldown_score,
            "cooldown_level": cooldown_level,
            "friction_type": cooldown_breakdown["friction_type"],
            "delay_seconds": cooldown_breakdown["delay_seconds"],
            "breakdown": cooldown_breakdown
        }
        
        logger.info("Cooldown: score=%.3f level=%s friction=%s",
                   cooldown_score, cooldown_level, cooldown_breakdown["friction_type"])
    except Exception as e:
        logger.warning("Cooldown calculation failed: %s", e)

    # Highlighted suspicious phrases (after verdict is known)
    # Try SHAP-based highlighting first, fallback to heuristic
    highlights = []
    explanation_type = "heuristic"
    
    if verdict == "fake" or manip_score > 0.2:
        try:
            # Get model and vectorizer for SHAP
            import joblib
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "model.joblib")
            vec_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vectorizer.joblib")
            
            if os.path.exists(model_path) and os.path.exists(vec_path):
                model = joblib.load(model_path)
                vectorizer = joblib.load(vec_path)
                
                # Try SHAP-based highlighting with timeout
                highlights, explanation_type = get_highlights_with_shap(
                    text, model, vectorizer, model_type="tfidf", timeout_ms=500
                )
                logger.debug(f"Highlights generated using {explanation_type}")
            else:
                highlights = get_highlights(text)
        except Exception as e:
            logger.warning(f"SHAP highlighting failed: {e}, using fallback")
            highlights = get_highlights(text)

    # Build evidence display: prefer article URLs, fallback to plain URLs
    display_evidence = (
        [a["url"] for a in evidence_articles if a.get("url")]
        or evidence_urls
    )

    # Record for drift detection
    record_drift(verdict, confidence)

    # Temporal claim tracking + velocity persistence
    import hashlib
    from app.models import ClaimRecord, VelocityRecord
    claim_hash = hashlib.sha256(primary_claim.lower().strip().encode()).hexdigest()
    try:
        db.add(ClaimRecord(
            claim_hash=claim_hash,
            claim_text=primary_claim[:500],
            verdict=verdict,
            confidence=confidence,
            ml_score=ml_result["fake"],
            ai_score=ai_score,
            evidence_score=evidence_score,
        ))
        
        # Store velocity record if tracking was successful
        if velocity_metrics and cooldown_data:
            try:
                velocity_record = VelocityRecord(
                    claim_hash=claim_hash,
                    claim_text=primary_claim[:500],
                    velocity_score=velocity_metrics.get("velocity_score", 0.0),
                    count_5min=velocity_metrics.get("count_5min", 0),
                    count_1hr=velocity_metrics.get("count_1hr", 0),
                    count_24hr=velocity_metrics.get("count_24hr", 0),
                    is_viral=velocity_metrics.get("is_viral", False),
                    is_trending=velocity_metrics.get("is_trending", False),
                    cooldown_score=cooldown_data.get("cooldown_score"),
                    cooldown_level=cooldown_data.get("cooldown_level"),
                )
                
                # Add clustering data (Phase 2.5) if available
                if cluster_data and cluster_data.get("cluster_id") is not None:
                    velocity_record.cluster_id = cluster_data.get("cluster_id")
                    velocity_record.cluster_size = cluster_data.get("cluster_size")
                    velocity_record.campaign_score = cluster_data.get("campaign_score")
                    velocity_record.is_coordinated = cluster_data.get("is_coordinated_campaign", False)
                
                db.add(velocity_record)
            except Exception as ve:
                logger.warning("Velocity record creation failed: %s", ve)
        
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Claim/velocity record persistence failed: %s", e)

    # Check if this claim has been seen before with a different verdict
    prior = db.query(ClaimRecord).filter(
        ClaimRecord.claim_hash == claim_hash,
        ClaimRecord.verdict != verdict,
    ).count()
    verdict_changed = prior > 0

    # Stance summary for frontend contradiction meter (already calculated above for cooldown)
    if not 'stance_summary' in locals():
        stance_summary = {"support": 0, "contradict": 0, "neutral": 0}
        for a in evidence_articles:
            s = a.get("stance", "neutral")
            stance_summary[s] = stance_summary.get(s, 0) + 1

    # ── Explainability report ──────────────────────────────────
    explainability = build_explanation(
        verdict=verdict,
        confidence=confidence,
        ml_score=ml_result["fake"],
        ai_score=ai_score,
        evidence_score=evidence_score,
        manipulation_score=manip_score,
        manipulation_signals=manip_signals,
        entity_verifications=entity_verifications,
        entity_risk=entity_risk,
        evidence_articles=evidence_articles,
        previously_debunked=platform_result.get("previously_debunked", False),
        debunk_sources=platform_result.get("debunk_sources", []),
        image_mismatch_risk=image_result.get("mismatch_risk", 0.0),
        was_translated=was_translated,
        detected_language=detected_lang if was_translated else None,
    )

    moderation_flags = []
    if verdict == "fake":
        moderation_flags.append("likely_misinformation")
    if platform_result.get("previously_debunked"):
        moderation_flags.append("previously_debunked")
    if manip_score > 0.2:
        moderation_flags.append("manipulation_signals")
    if entity_risk > 0.2:
        moderation_flags.append("entity_mismatch")
    if image_result.get("flag"):
        moderation_flags.append(image_result["flag"])

    moderation_risk = min(
        1.0,
        max(
            confidence if verdict == "fake" else 0.0,
            manip_score,
            entity_risk,
            image_result.get("mismatch_risk", 0.0),
            0.9 if platform_result.get("previously_debunked") else 0.0,
        ),
    )
    moderation_recommendation = "review" if moderation_risk >= 0.6 else "allow"

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
        "shap_highlights": highlights if explanation_type == "shap" else None,
        "explanation_type": explanation_type if 'explanation_type' in locals() else "heuristic",
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
        "image_description": image_result.get("description") if image_result.get("images_found") else None,
        # Platform spread / existing fact-checks
        "fact_checks": platform_result.get("fact_checks") or None,
        "previously_debunked": platform_result.get("previously_debunked") or None,
        "debunk_sources": platform_result.get("debunk_sources") or None,
        "spread_risk": platform_result.get("spread_risk") if platform_result.get("spread_risk", 0) > 0 else None,
        # Velocity tracking (Phase 2)
        "velocity_metrics": {
            "velocity_score": velocity_metrics.get("velocity_score", 0.0),
            "count_5min": velocity_metrics.get("count_5min", 0),
            "count_1hr": velocity_metrics.get("count_1hr", 0),
            "count_24hr": velocity_metrics.get("count_24hr", 0),
            "is_viral": velocity_metrics.get("is_viral", False),
            "is_trending": velocity_metrics.get("is_trending", False),
        } if velocity_metrics else None,
        # Cooldown score (Phase 2)
        "cooldown": cooldown_data if cooldown_data else None,
        # Semantic clustering (Phase 2.5)
        "clustering": {
            "cluster_id": cluster_data.get("cluster_id"),
            "cluster_size": cluster_data.get("cluster_size", 1),
            "similar_claims": cluster_data.get("similar_claims", []),
            "is_coordinated_campaign": cluster_data.get("is_coordinated_campaign", False),
            "campaign_score": cluster_data.get("campaign_score", 0.0),
        } if cluster_data and cluster_data.get("cluster_id") is not None else None,
        # Social graph analysis (Phase 2.4)
        "social_spread": social_data if social_data else None,
        # Domain classification (Phase 3.3)
        "domain": domain_info if domain_info else None,
        # Explainability
        "explainability": explainability,
        "moderation_summary": {
            "risk": round(moderation_risk, 3),
            "recommendation": moderation_recommendation,
            "flags": moderation_flags or None,
        },
    }

    if session_id:
        try:
            save_message(db, session_id, "assistant", explanation, extra={
                "is_claim": True,
                "verdict": verdict,
                "confidence": confidence,
                "ml_score": ml_result["fake"],
                "ai_score": ai_score,
                "explanation": explanation,
                "evidence": display_evidence,
            })
        except Exception as e:
            logger.warning("Failed to save assistant message: %s", e)

    return result
