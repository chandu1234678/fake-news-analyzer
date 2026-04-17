"""
Advanced Analytics & Insights Routes

Endpoints for misinformation trends, user behavior, and model performance analytics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_, cast, Date, extract
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from database import get_db
from app.models import User, ClaimRecord, UserFeedback, VelocityRecord
from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ── Misinformation Trends ─────────────────────────────────────

@router.get("/trends/viral")
async def get_viral_trends(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get viral misinformation trends over the past N days.
    
    Returns claims with high velocity scores and fake verdicts.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get viral fake claims
    viral_claims = db.query(
        VelocityRecord.claim_text,
        VelocityRecord.velocity_score,
        VelocityRecord.count_24hr,
        VelocityRecord.is_viral,
        VelocityRecord.cluster_size,
        VelocityRecord.created_at
    ).join(
        ClaimRecord,
        VelocityRecord.claim_hash == ClaimRecord.claim_hash
    ).filter(
        and_(
            VelocityRecord.created_at >= cutoff,
            VelocityRecord.is_viral == True,
            ClaimRecord.verdict == "fake"
        )
    ).order_by(
        desc(VelocityRecord.velocity_score)
    ).limit(limit).all()
    
    trends = [
        {
            "claim": claim.claim_text[:200],
            "velocity_score": float(claim.velocity_score),
            "count_24hr": claim.count_24hr,
            "cluster_size": claim.cluster_size or 1,
            "detected_at": claim.created_at.isoformat(),
        }
        for claim in viral_claims
    ]
    
    return {
        "period_days": days,
        "viral_claims": len(trends),
        "trends": trends
    }


@router.get("/trends/topics")
async def get_topic_trends(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get trending topics in misinformation over time.
    
    Uses domain classification to group claims by topic.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get claims with domain info (stored in JSON)
    # This is a simplified version - in production, you'd want a separate domain table
    claims = db.query(
        ClaimRecord.verdict,
        func.count(ClaimRecord.id).label("count")
    ).filter(
        ClaimRecord.created_at >= cutoff
    ).group_by(
        ClaimRecord.verdict
    ).all()
    
    # Get daily breakdown
    daily_stats = db.query(
        cast(ClaimRecord.created_at, Date).label("date"),
        ClaimRecord.verdict,
        func.count(ClaimRecord.id).label("count")
    ).filter(
        ClaimRecord.created_at >= cutoff
    ).group_by(
        cast(ClaimRecord.created_at, Date),
        ClaimRecord.verdict
    ).order_by(
        cast(ClaimRecord.created_at, Date)
    ).all()
    
    # Format daily data
    daily_data = {}
    for stat in daily_stats:
        date_str = str(stat.date)
        if date_str not in daily_data:
            daily_data[date_str] = {"date": date_str, "fake": 0, "real": 0, "uncertain": 0}
        daily_data[date_str][stat.verdict] = stat.count
    
    return {
        "period_days": days,
        "summary": {
            "fake": sum(c.count for c in claims if c.verdict == "fake"),
            "real": sum(c.count for c in claims if c.verdict == "real"),
            "uncertain": sum(c.count for c in claims if c.verdict == "uncertain"),
        },
        "daily_breakdown": list(daily_data.values())
    }


@router.get("/trends/geographic")
async def get_geographic_trends(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get geographic spread of misinformation.
    
    Note: Requires IP geolocation data (not implemented yet).
    Returns placeholder data structure.
    """
    return {
        "period_days": days,
        "message": "Geographic tracking not yet implemented",
        "regions": [],
        "note": "Requires IP geolocation integration"
    }


# ── User Behavior Analytics ───────────────────────────────────

@router.get("/users/engagement")
async def get_user_engagement(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get user engagement metrics.
    
    Returns active users, claims per user, feedback rate, etc.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Active users (users who made claims)
    active_users = db.query(
        func.count(func.distinct(ClaimRecord.user_id))
    ).filter(
        and_(
            ClaimRecord.user_id.isnot(None),
            ClaimRecord.created_at >= cutoff
        )
    ).scalar() or 0
    
    # Total claims
    total_claims = db.query(
        func.count(ClaimRecord.id)
    ).filter(
        ClaimRecord.created_at >= cutoff
    ).scalar() or 0
    
    # Claims with feedback
    claims_with_feedback = db.query(
        func.count(func.distinct(UserFeedback.claim_text))
    ).filter(
        UserFeedback.created_at >= cutoff
    ).scalar() or 0
    
    # Top contributors
    top_users = db.query(
        User.name,
        User.email,
        func.count(ClaimRecord.id).label("claim_count")
    ).join(
        ClaimRecord,
        User.id == ClaimRecord.user_id
    ).filter(
        ClaimRecord.created_at >= cutoff
    ).group_by(
        User.id, User.name, User.email
    ).order_by(
        desc("claim_count")
    ).limit(10).all()
    
    return {
        "period_days": days,
        "active_users": active_users,
        "total_claims": total_claims,
        "avg_claims_per_user": round(total_claims / active_users, 2) if active_users > 0 else 0,
        "feedback_rate": round(claims_with_feedback / total_claims, 3) if total_claims > 0 else 0,
        "top_contributors": [
            {
                "name": user.name or "Anonymous",
                "email": user.email[:20] + "..." if len(user.email) > 20 else user.email,
                "claims": user.claim_count
            }
            for user in top_users
        ]
    }


@router.get("/users/review-quality")
async def get_review_quality(
    user_id: Optional[int] = None,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get review quality metrics for a user or all users.
    
    Measures accuracy of user feedback compared to model predictions.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # If user_id not specified, use current user
    target_user_id = user_id or current_user.id
    
    # Get user's feedback
    feedbacks = db.query(UserFeedback).filter(
        and_(
            UserFeedback.user_id == target_user_id,
            UserFeedback.created_at >= cutoff
        )
    ).all()
    
    if not feedbacks:
        return {
            "user_id": target_user_id,
            "period_days": days,
            "total_reviews": 0,
            "message": "No reviews in this period"
        }
    
    # Calculate metrics
    total_reviews = len(feedbacks)
    corrections = sum(1 for f in feedbacks if f.predicted != f.actual)
    agreements = total_reviews - corrections
    
    # Breakdown by verdict
    verdict_breakdown = {
        "fake_to_real": sum(1 for f in feedbacks if f.predicted == "fake" and f.actual == "real"),
        "real_to_fake": sum(1 for f in feedbacks if f.predicted == "real" and f.actual == "fake"),
        "uncertain_to_fake": sum(1 for f in feedbacks if f.predicted == "uncertain" and f.actual == "fake"),
        "uncertain_to_real": sum(1 for f in feedbacks if f.predicted == "uncertain" and f.actual == "real"),
    }
    
    return {
        "user_id": target_user_id,
        "period_days": days,
        "total_reviews": total_reviews,
        "corrections": corrections,
        "agreements": agreements,
        "correction_rate": round(corrections / total_reviews, 3),
        "verdict_breakdown": verdict_breakdown,
        "quality_score": round(1.0 - (corrections / total_reviews), 3)  # Higher is better
    }


@router.get("/users/leaderboard")
async def get_leaderboard(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get contribution leaderboard.
    
    Ranks users by number of reviews and quality score.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get users with feedback counts
    user_stats = db.query(
        User.id,
        User.name,
        User.email,
        func.count(UserFeedback.id).label("review_count")
    ).join(
        UserFeedback,
        User.id == UserFeedback.user_id
    ).filter(
        UserFeedback.created_at >= cutoff
    ).group_by(
        User.id, User.name, User.email
    ).order_by(
        desc("review_count")
    ).limit(limit).all()
    
    leaderboard = []
    for rank, user in enumerate(user_stats, 1):
        # Calculate quality score for this user
        feedbacks = db.query(UserFeedback).filter(
            and_(
                UserFeedback.user_id == user.id,
                UserFeedback.created_at >= cutoff
            )
        ).all()
        
        corrections = sum(1 for f in feedbacks if f.predicted != f.actual)
        quality_score = 1.0 - (corrections / len(feedbacks)) if feedbacks else 0.0
        
        leaderboard.append({
            "rank": rank,
            "name": user.name or "Anonymous",
            "reviews": user.review_count,
            "quality_score": round(quality_score, 3),
            "points": int(user.review_count * quality_score * 100)  # Gamification score
        })
    
    return {
        "period_days": days,
        "leaderboard": leaderboard
    }


# ── Model Performance Analytics ───────────────────────────────

@router.get("/model/accuracy")
async def get_model_accuracy(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get model accuracy metrics over time.
    
    Uses user feedback as ground truth.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get all feedback in period
    feedbacks = db.query(UserFeedback).filter(
        UserFeedback.created_at >= cutoff
    ).all()
    
    if not feedbacks:
        return {
            "period_days": days,
            "message": "No feedback data available",
            "accuracy": None
        }
    
    # Calculate accuracy
    correct = sum(1 for f in feedbacks if f.predicted == f.actual)
    total = len(feedbacks)
    accuracy = correct / total if total > 0 else 0
    
    # Breakdown by verdict
    verdict_accuracy = {}
    for verdict in ["fake", "real", "uncertain"]:
        verdict_feedbacks = [f for f in feedbacks if f.predicted == verdict]
        if verdict_feedbacks:
            verdict_correct = sum(1 for f in verdict_feedbacks if f.predicted == f.actual)
            verdict_accuracy[verdict] = round(verdict_correct / len(verdict_feedbacks), 3)
        else:
            verdict_accuracy[verdict] = None
    
    # Daily accuracy trend
    daily_accuracy = db.query(
        cast(UserFeedback.created_at, Date).label("date"),
        func.count(UserFeedback.id).label("total"),
        func.sum(
            func.cast(UserFeedback.predicted == UserFeedback.actual, func.Integer())
        ).label("correct")
    ).filter(
        UserFeedback.created_at >= cutoff
    ).group_by(
        cast(UserFeedback.created_at, Date)
    ).order_by(
        cast(UserFeedback.created_at, Date)
    ).all()
    
    daily_trend = [
        {
            "date": str(day.date),
            "accuracy": round(day.correct / day.total, 3) if day.total > 0 else 0,
            "samples": day.total
        }
        for day in daily_accuracy
    ]
    
    return {
        "period_days": days,
        "overall_accuracy": round(accuracy, 3),
        "total_samples": total,
        "verdict_accuracy": verdict_accuracy,
        "daily_trend": daily_trend
    }


@router.get("/model/confidence-calibration")
async def get_confidence_calibration(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get confidence calibration metrics.
    
    Measures how well model confidence matches actual accuracy.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get claims with feedback
    claims_with_feedback = db.query(
        ClaimRecord.confidence,
        ClaimRecord.verdict,
        UserFeedback.actual
    ).join(
        UserFeedback,
        ClaimRecord.claim_text == UserFeedback.claim_text
    ).filter(
        and_(
            ClaimRecord.created_at >= cutoff,
            UserFeedback.created_at >= cutoff
        )
    ).all()
    
    if not claims_with_feedback:
        return {
            "period_days": days,
            "message": "No calibration data available"
        }
    
    # Group by confidence bins
    bins = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    calibration = []
    
    for i in range(len(bins) - 1):
        bin_start, bin_end = bins[i], bins[i + 1]
        bin_claims = [
            c for c in claims_with_feedback
            if bin_start <= c.confidence < bin_end
        ]
        
        if bin_claims:
            correct = sum(1 for c in bin_claims if c.verdict == c.actual)
            accuracy = correct / len(bin_claims)
            avg_confidence = sum(c.confidence for c in bin_claims) / len(bin_claims)
            
            calibration.append({
                "confidence_range": f"{bin_start:.1f}-{bin_end:.1f}",
                "avg_confidence": round(avg_confidence, 3),
                "accuracy": round(accuracy, 3),
                "samples": len(bin_claims),
                "calibration_error": round(abs(avg_confidence - accuracy), 3)
            })
    
    # Calculate ECE (Expected Calibration Error)
    total_samples = len(claims_with_feedback)
    ece = sum(
        (bin_data["samples"] / total_samples) * bin_data["calibration_error"]
        for bin_data in calibration
    )
    
    return {
        "period_days": days,
        "total_samples": total_samples,
        "expected_calibration_error": round(ece, 3),
        "calibration_curve": calibration
    }


@router.get("/model/drift")
async def get_model_drift(
    days: int = Query(default=90, ge=7, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get model drift metrics over time.
    
    Detects changes in prediction distribution and accuracy.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get weekly verdict distribution
    weekly_stats = db.query(
        extract('week', ClaimRecord.created_at).label('week'),
        extract('year', ClaimRecord.created_at).label('year'),
        ClaimRecord.verdict,
        func.count(ClaimRecord.id).label('count'),
        func.avg(ClaimRecord.confidence).label('avg_confidence')
    ).filter(
        ClaimRecord.created_at >= cutoff
    ).group_by(
        'week', 'year', ClaimRecord.verdict
    ).order_by(
        'year', 'week'
    ).all()
    
    # Format weekly data
    weekly_data = {}
    for stat in weekly_stats:
        week_key = f"{int(stat.year)}-W{int(stat.week):02d}"
        if week_key not in weekly_data:
            weekly_data[week_key] = {
                "week": week_key,
                "fake": 0,
                "real": 0,
                "uncertain": 0,
                "avg_confidence": 0
            }
        weekly_data[week_key][stat.verdict] = stat.count
        weekly_data[week_key]["avg_confidence"] = float(stat.avg_confidence or 0)
    
    return {
        "period_days": days,
        "weekly_distribution": list(weekly_data.values()),
        "note": "Monitor for significant changes in verdict distribution"
    }


# ── Business Intelligence ─────────────────────────────────────

@router.get("/business/summary")
async def get_business_summary(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get executive summary of key metrics.
    
    High-level overview for business intelligence.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Total claims
    total_claims = db.query(func.count(ClaimRecord.id)).filter(
        ClaimRecord.created_at >= cutoff
    ).scalar() or 0
    
    # Active users
    active_users = db.query(
        func.count(func.distinct(ClaimRecord.user_id))
    ).filter(
        and_(
            ClaimRecord.user_id.isnot(None),
            ClaimRecord.created_at >= cutoff
        )
    ).scalar() or 0
    
    # Fake claims detected
    fake_claims = db.query(func.count(ClaimRecord.id)).filter(
        and_(
            ClaimRecord.created_at >= cutoff,
            ClaimRecord.verdict == "fake"
        )
    ).scalar() or 0
    
    # Viral misinformation caught
    viral_caught = db.query(func.count(VelocityRecord.id)).filter(
        and_(
            VelocityRecord.created_at >= cutoff,
            VelocityRecord.is_viral == True
        )
    ).scalar() or 0
    
    # User feedback count
    feedback_count = db.query(func.count(UserFeedback.id)).filter(
        UserFeedback.created_at >= cutoff
    ).scalar() or 0
    
    # Growth rate (compare to previous period)
    previous_cutoff = cutoff - timedelta(days=days)
    previous_claims = db.query(func.count(ClaimRecord.id)).filter(
        and_(
            ClaimRecord.created_at >= previous_cutoff,
            ClaimRecord.created_at < cutoff
        )
    ).scalar() or 1
    
    growth_rate = ((total_claims - previous_claims) / previous_claims) * 100 if previous_claims > 0 else 0
    
    return {
        "period_days": days,
        "summary": {
            "total_claims": total_claims,
            "active_users": active_users,
            "fake_claims_detected": fake_claims,
            "fake_rate": round(fake_claims / total_claims, 3) if total_claims > 0 else 0,
            "viral_misinformation_caught": viral_caught,
            "user_feedback_received": feedback_count,
            "growth_rate_percent": round(growth_rate, 1),
        },
        "impact": {
            "claims_prevented_from_spreading": viral_caught,  # Simplified metric
            "users_protected": active_users,
            "misinformation_detection_rate": round(fake_claims / total_claims, 3) if total_claims > 0 else 0,
        }
    }
