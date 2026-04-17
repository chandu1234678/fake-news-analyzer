"""
Review Queue Routes

Endpoints for reviewing uncertain claims (confidence 0.45-0.55) to enable active learning.
Human reviewers can provide corrections that improve model accuracy.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from database import get_db
from app.models import ClaimRecord, UserFeedback, User, VelocityRecord
from app.auth import get_current_user
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review", tags=["review"])


class ReviewSubmission(BaseModel):
    """User's review decision for an uncertain claim"""
    claim_id: int
    verdict: str  # "real" or "fake"
    confidence: Optional[float] = None
    notes: Optional[str] = None


class ReviewQueueItem(BaseModel):
    """Claim in review queue with all analysis data"""
    id: int
    claim_text: str
    current_verdict: str
    confidence: float
    ml_score: float
    ai_score: Optional[float]
    evidence_score: Optional[float]
    created_at: datetime
    # Priority signals
    velocity_score: Optional[float] = None
    is_viral: Optional[bool] = None
    is_trending: Optional[bool] = None
    cluster_size: Optional[int] = None
    # Review status
    already_reviewed: bool = False


class ReviewStats(BaseModel):
    """Statistics about review queue"""
    total_pending: int
    reviewed_today: int
    reviewed_total: int
    avg_confidence_gain: Optional[float]
    high_priority_count: int


@router.get("/queue", response_model=List[ReviewQueueItem])
def get_review_queue(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    priority: str = Query(default="all", regex="^(all|viral|trending|coordinated)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get claims that need human review (confidence 0.45-0.55).
    
    Priority filters:
    - all: All uncertain claims
    - viral: Claims with high velocity
    - trending: Claims gaining traction
    - coordinated: Potential coordinated campaigns
    """
    
    # Base query: uncertain claims (0.45-0.55 confidence)
    query = db.query(ClaimRecord).filter(
        and_(
            ClaimRecord.confidence >= 0.45,
            ClaimRecord.confidence <= 0.55
        )
    )
    
    # Apply priority filter
    if priority == "viral":
        # Join with velocity records to find viral claims
        query = query.join(
            VelocityRecord,
            ClaimRecord.claim_hash == VelocityRecord.claim_hash
        ).filter(VelocityRecord.is_viral == True)
    
    elif priority == "trending":
        query = query.join(
            VelocityRecord,
            ClaimRecord.claim_hash == VelocityRecord.claim_hash
        ).filter(VelocityRecord.is_trending == True)
    
    elif priority == "coordinated":
        query = query.join(
            VelocityRecord,
            ClaimRecord.claim_hash == VelocityRecord.claim_hash
        ).filter(VelocityRecord.is_coordinated == True)
    
    # Order by most recent first
    query = query.order_by(desc(ClaimRecord.created_at))
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    claims = query.offset(offset).limit(limit).all()
    
    # Enrich with velocity data and check review status
    result = []
    for claim in claims:
        # Get velocity data if exists
        velocity = db.query(VelocityRecord).filter(
            VelocityRecord.claim_hash == claim.claim_hash
        ).order_by(desc(VelocityRecord.created_at)).first()
        
        # Check if already reviewed by this user
        already_reviewed = db.query(UserFeedback).filter(
            and_(
                UserFeedback.user_id == user.id,
                UserFeedback.claim_text == claim.claim_text
            )
        ).first() is not None
        
        result.append(ReviewQueueItem(
            id=claim.id,
            claim_text=claim.claim_text,
            current_verdict=claim.verdict,
            confidence=claim.confidence,
            ml_score=claim.ml_score or 0.0,
            ai_score=claim.ai_score,
            evidence_score=claim.evidence_score,
            created_at=claim.created_at,
            velocity_score=velocity.velocity_score if velocity else None,
            is_viral=velocity.is_viral if velocity else None,
            is_trending=velocity.is_trending if velocity else None,
            cluster_size=velocity.cluster_size if velocity else None,
            already_reviewed=already_reviewed,
        ))
    
    logger.info(f"Review queue: {len(result)} items (total: {total}, priority: {priority})")
    return result


@router.post("/submit")
def submit_review(
    review: ReviewSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Submit a human review for an uncertain claim.
    Stores the correction in UserFeedback for future retraining.
    """
    
    # Validate verdict
    if review.verdict not in ("real", "fake"):
        raise HTTPException(status_code=400, detail="verdict must be 'real' or 'fake'")
    
    # Get the claim
    claim = db.query(ClaimRecord).filter(ClaimRecord.id == review.claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    # Check if already reviewed by this user
    existing = db.query(UserFeedback).filter(
        and_(
            UserFeedback.user_id == user.id,
            UserFeedback.claim_text == claim.claim_text
        )
    ).first()
    
    if existing:
        # Update existing review
        existing.actual = review.verdict
        existing.confidence = review.confidence or claim.confidence
        existing.created_at = datetime.utcnow()
        logger.info(f"Updated review for claim {claim.id} by user {user.id}")
    else:
        # Create new feedback
        feedback = UserFeedback(
            user_id=user.id,
            claim_text=claim.claim_text[:1000],
            predicted=claim.verdict,
            actual=review.verdict,
            confidence=review.confidence or claim.confidence,
        )
        db.add(feedback)
        logger.info(f"New review for claim {claim.id} by user {user.id}: {claim.verdict} → {review.verdict}")
    
    db.commit()
    
    # ── WebSocket notification ────────────────────────────────
    from app.websocket import notify_review_queue_update
    import asyncio
    try:
        asyncio.create_task(notify_review_queue_update("all"))
    except Exception as e:
        logger.debug(f"WebSocket notification skipped: {e}")
    
    return {
        "success": True,
        "message": "Review submitted successfully",
        "claim_id": claim.id,
        "verdict": review.verdict,
    }


@router.get("/stats", response_model=ReviewStats)
def get_review_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get statistics about the review queue and user's review activity.
    """
    
    # Total pending reviews (uncertain claims)
    total_pending = db.query(ClaimRecord).filter(
        and_(
            ClaimRecord.confidence >= 0.45,
            ClaimRecord.confidence <= 0.55
        )
    ).count()
    
    # Reviews by this user today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    reviewed_today = db.query(UserFeedback).filter(
        and_(
            UserFeedback.user_id == user.id,
            UserFeedback.created_at >= today_start
        )
    ).count()
    
    # Total reviews by this user
    reviewed_total = db.query(UserFeedback).filter(
        UserFeedback.user_id == user.id
    ).count()
    
    # High priority count (viral + trending + coordinated)
    high_priority_count = db.query(ClaimRecord).join(
        VelocityRecord,
        ClaimRecord.claim_hash == VelocityRecord.claim_hash
    ).filter(
        and_(
            ClaimRecord.confidence >= 0.45,
            ClaimRecord.confidence <= 0.55,
            or_(
                VelocityRecord.is_viral == True,
                VelocityRecord.is_trending == True,
                VelocityRecord.is_coordinated == True
            )
        )
    ).count()
    
    # Calculate average confidence gain (simplified - would need model retraining to measure accurately)
    # For now, just return None
    avg_confidence_gain = None
    
    return ReviewStats(
        total_pending=total_pending,
        reviewed_today=reviewed_today,
        reviewed_total=reviewed_total,
        avg_confidence_gain=avg_confidence_gain,
        high_priority_count=high_priority_count,
    )


@router.delete("/feedback/{feedback_id}")
def delete_review(
    feedback_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Delete a review (only your own reviews).
    """
    
    feedback = db.query(UserFeedback).filter(
        and_(
            UserFeedback.id == feedback_id,
            UserFeedback.user_id == user.id
        )
    ).first()
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Review not found or not authorized")
    
    db.delete(feedback)
    db.commit()
    
    logger.info(f"Deleted review {feedback_id} by user {user.id}")
    
    return {"success": True, "message": "Review deleted"}


@router.get("/history")
def get_review_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get user's review history.
    """
    
    feedbacks = db.query(UserFeedback).filter(
        UserFeedback.user_id == user.id
    ).order_by(desc(UserFeedback.created_at)).offset(offset).limit(limit).all()
    
    return {
        "reviews": [
            {
                "id": fb.id,
                "claim_text": fb.claim_text,
                "predicted": fb.predicted,
                "actual": fb.actual,
                "confidence": fb.confidence,
                "created_at": fb.created_at,
            }
            for fb in feedbacks
        ],
        "total": db.query(UserFeedback).filter(UserFeedback.user_id == user.id).count(),
    }
