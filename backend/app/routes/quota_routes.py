"""
Quota Management Routes

Endpoints for checking and managing user quotas and rate limits.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging
from datetime import datetime, timedelta

from database import get_db
from app.models import User, ClaimRecord
from app.auth import get_current_user
from app.rate_limit import rate_limiter, TIER_LIMITS
from sqlalchemy import func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quota", tags=["quota"])


@router.get("/usage")
async def get_usage(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get current user's usage statistics and quota information.
    
    Returns:
    - tier: User's subscription tier
    - limits: Rate limits for this tier
    - usage: Current month's usage
    - quota: Monthly quota information
    """
    tier = rate_limiter.get_user_tier(user)
    tier_config = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    
    # Get current month's usage
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
    
    claims_this_month = db.query(func.count(ClaimRecord.id)).filter(
        ClaimRecord.user_id == user.id,
        ClaimRecord.created_at >= month_start,
        ClaimRecord.created_at <= month_end
    ).scalar() or 0
    
    # Get total usage
    total_claims = db.query(func.count(ClaimRecord.id)).filter(
        ClaimRecord.user_id == user.id
    ).scalar() or 0
    
    # Calculate quota info
    monthly_limit = tier_config.get("monthly_claims", 100)
    quota_remaining = max(0, monthly_limit - claims_this_month) if monthly_limit != -1 else -1
    
    # Calculate reset time
    next_month = (month_start + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    return {
        "tier": tier,
        "limits": {
            "per_minute": tier_config.get("per_minute"),
            "per_hour": tier_config.get("per_hour"),
            "per_day": tier_config.get("per_day"),
            "monthly_claims": tier_config.get("monthly_claims"),
        },
        "usage": {
            "claims_this_month": claims_this_month,
            "total_claims": total_claims,
        },
        "quota": {
            "limit": monthly_limit,
            "used": claims_this_month,
            "remaining": quota_remaining,
            "reset_at": int(next_month.timestamp()),
            "reset_date": next_month.isoformat(),
        }
    }


@router.get("/tiers")
async def get_tiers() -> Dict[str, Any]:
    """
    Get all subscription tiers with pricing and limits.
    Pricing in INR via Razorpay.
    """
    return {
        "currency": "INR",
        "tiers": {
            "free": {
                "name": "Free",
                "price_inr": 0,
                "price_usd": 0,
                "limits": TIER_LIMITS["free"],
                "ai_models": "1 model (Qwen3-8B)",
                "features": [
                    "100 claims/month",
                    "Qwen3-8B AI analysis (free model)",
                    "Evidence from trusted sources",
                    "Basic manipulation detection",
                    "Community support",
                ]
            },
            "starter": {
                "name": "Starter",
                "price_inr": 99,
                "price_usd": 1.20,
                "limits": TIER_LIMITS["starter"],
                "ai_models": "2 models (Qwen3 + Groq)",
                "features": [
                    "500 claims/month",
                    "2-model AI ensemble (better accuracy)",
                    "Evidence + source credibility",
                    "Manipulation & bias detection",
                    "Email support",
                ]
            },
            "pro": {
                "name": "Pro",
                "price_inr": 499,
                "price_usd": 6.00,
                "limits": TIER_LIMITS["pro"],
                "ai_models": "4 models (Qwen3 + Groq + Gemini + Gemma4 31B)",
                "features": [
                    "5,000 claims/month",
                    "4-model AI ensemble (Gemini + Gemma4 31B)",
                    "SHAP explainability",
                    "Velocity & viral tracking",
                    "Semantic clustering",
                    "Priority support",
                ]
            },
            "enterprise": {
                "name": "Enterprise",
                "price_inr": 2999,
                "price_usd": 36.00,
                "limits": TIER_LIMITS["enterprise"],
                "ai_models": "5 models (all + MiniMax 229B)",
                "features": [
                    "Unlimited claims",
                    "5-model ensemble (MiniMax 229B included)",
                    "Dedicated support",
                    "API access",
                    "Custom integrations",
                    "SLA guarantee",
                ]
            }
        }
    }


@router.post("/upgrade")
async def upgrade_tier(
    target_tier: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Upgrade user to a higher tier.
    
    Note: This is a placeholder. In production, integrate with
    payment processor (Stripe, PayPal, etc.)
    """
    # Validate tier
    if target_tier not in ["pro", "enterprise"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid tier. Must be 'pro' or 'enterprise'"
        )
    
    # Check current tier
    current_tier = rate_limiter.get_user_tier(user)
    
    # Prevent downgrade (for now)
    tier_order = {"free": 0, "pro": 1, "enterprise": 2}
    if tier_order.get(target_tier, 0) <= tier_order.get(current_tier, 0):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot upgrade from {current_tier} to {target_tier}"
        )
    
    # TODO: Integrate with payment processor
    # For now, just update the tier (demo mode)
    user.tier = target_tier
    db.commit()
    
    logger.info(f"User {user.id} upgraded from {current_tier} to {target_tier}")
    
    return {
        "success": True,
        "message": f"Successfully upgraded to {target_tier}",
        "previous_tier": current_tier,
        "new_tier": target_tier,
        "new_limits": TIER_LIMITS[target_tier],
    }


@router.get("/history")
async def get_usage_history(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get usage history for the past N days.
    
    Returns daily claim counts for visualization.
    """
    from sqlalchemy import func, cast, Date
    
    # Get claims grouped by date
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    results = db.query(
        cast(ClaimRecord.created_at, Date).label("date"),
        func.count(ClaimRecord.id).label("count")
    ).filter(
        ClaimRecord.user_id == user.id,
        ClaimRecord.created_at >= cutoff_date
    ).group_by(
        cast(ClaimRecord.created_at, Date)
    ).order_by(
        cast(ClaimRecord.created_at, Date)
    ).all()
    
    # Format results
    history = [
        {
            "date": str(row.date),
            "claims": row.count
        }
        for row in results
    ]
    
    return {
        "days": days,
        "history": history,
        "total": sum(row["claims"] for row in history)
    }


@router.get("/rate-limit-status")
async def get_rate_limit_status(
    user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current rate limit status for all windows.
    
    Returns remaining requests for minute, hour, and day windows.
    """
    tier = rate_limiter.get_user_tier(user)
    identifier = f"user:{user.id}"
    
    status = {}
    for window in ["minute", "hour", "day"]:
        allowed, info = rate_limiter.check_rate_limit(
            identifier, tier, "/message", window
        )
        status[window] = {
            "limit": info.get("limit", 0),
            "remaining": info.get("remaining", 0),
            "reset": info.get("reset", 0),
        }
    
    return {
        "tier": tier,
        "status": status
    }
