"""
API Rate Limiting & Quotas

Implements sophisticated rate limiting and usage quotas using Redis.
Supports tiered limits (free, pro, enterprise) and sliding window algorithm.
"""

import os
import time
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta
from functools import wraps
from fastapi import HTTPException, Request, Depends
from sqlalchemy.orm import Session

from database import get_db
from app.models import User
from app.auth import get_current_user, get_optional_user

logger = logging.getLogger(__name__)

# Rate limit configuration
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"

# ── Tier Limits ───────────────────────────────────────────────
# Designed for 500 free users on free API keys:
#   Free users → Qwen3 only (unlimited free)
#   500 users × 3 checks/day = 1,500 req/day → well within Qwen3 limits
#
# Paid tiers use more models but have fewer users, so total API usage stays low.
TIER_LIMITS = {
    "anonymous": {
        "per_minute": 3,
        "per_hour": 10,
        "per_day": 20,
        "monthly_claims": 10,
        "ai_models": 1,          # Qwen3 only
        "description": "No account",
    },
    "free": {
        "per_minute": 5,
        "per_hour": 30,
        "per_day": 100,
        "monthly_claims": 100,
        "ai_models": 1,          # Qwen3 only
        "description": "Free tier — 100 claims/month",
    },
    "starter": {
        "per_minute": 15,
        "per_hour": 200,
        "per_day": 600,
        "monthly_claims": 500,
        "ai_models": 2,          # Qwen3 + Groq
        "price_inr": 99,
        "description": "Starter — ₹99/month, 500 claims",
    },
    "pro": {
        "per_minute": 30,
        "per_hour": 500,
        "per_day": 5000,
        "monthly_claims": 5000,
        "ai_models": 4,          # Qwen3 + Groq + Gemini + Gemma4
        "price_inr": 499,
        "description": "Pro — ₹499/month, 5,000 claims",
    },
    "enterprise": {
        "per_minute": 100,
        "per_hour": 2000,
        "per_day": 50000,
        "monthly_claims": -1,    # Unlimited
        "ai_models": 5,          # All models including MiniMax 229B
        "price_inr": 2999,
        "description": "Enterprise — ₹2,999/month, unlimited",
    },
}

# Endpoint-specific limits (multipliers)
ENDPOINT_LIMITS = {
    "/message": 1.0,  # Standard
    "/explain": 0.5,  # Less expensive
    "/review/submit": 0.3,  # Encourage reviews
    "/feedback": 0.2,  # Encourage feedback
}


class RateLimiter:
    """Redis-based rate limiter with sliding window algorithm"""
    
    def __init__(self):
        self.enabled = RATE_LIMIT_ENABLED
        self.redis_client = None
        
        if self.enabled:
            try:
                from app.cache import cache
                if cache.is_available():
                    self.redis_client = cache.client
                    logger.info("Rate limiter initialized with Redis")
                else:
                    logger.warning("Rate limiter disabled - Redis not available")
                    self.enabled = False
            except Exception as e:
                logger.warning(f"Rate limiter initialization failed: {e}")
                self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if rate limiting is enabled"""
        return self.enabled and self.redis_client is not None
    
    def get_user_tier(self, user: Optional[User]) -> str:
        """Get user's subscription tier"""
        if not user:
            return "anonymous"
        
        # Check user's tier (default to free)
        tier = getattr(user, "tier", "free")
        return tier if tier in TIER_LIMITS else "free"
    
    def check_rate_limit(
        self,
        identifier: str,
        tier: str,
        endpoint: str = "/message",
        window: str = "minute"
    ) -> Tuple[bool, dict]:
        """
        Check if request is within rate limit using sliding window.
        
        Returns: (allowed: bool, info: dict)
        """
        if not self.is_enabled():
            return True, {}
        
        # Get limit for this tier and window
        tier_config = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        limit_key = f"per_{window}"
        limit = tier_config.get(limit_key, 100)
        
        # Apply endpoint multiplier
        endpoint_multiplier = ENDPOINT_LIMITS.get(endpoint, 1.0)
        limit = int(limit * endpoint_multiplier)
        
        # Window duration in seconds
        window_seconds = {
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }.get(window, 60)
        
        # Redis key
        key = f"ratelimit:{identifier}:{window}:{endpoint}"
        
        try:
            current_time = time.time()
            window_start = current_time - window_seconds
            
            # Remove old entries outside the window
            self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Count requests in current window
            current_count = self.redis_client.zcard(key)
            
            # Check if limit exceeded
            if current_count >= limit:
                # Get oldest request time to calculate reset
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                reset_time = int(oldest[0][1] + window_seconds) if oldest else int(current_time + window_seconds)
                
                return False, {
                    "limit": limit,
                    "remaining": 0,
                    "reset": reset_time,
                    "retry_after": reset_time - int(current_time),
                }
            
            # Add current request
            self.redis_client.zadd(key, {str(current_time): current_time})
            
            # Set expiry on key
            self.redis_client.expire(key, window_seconds + 10)
            
            # Calculate remaining and reset
            remaining = limit - (current_count + 1)
            reset_time = int(current_time + window_seconds)
            
            return True, {
                "limit": limit,
                "remaining": remaining,
                "reset": reset_time,
            }
        
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if rate limiting fails
            return True, {}
    
    def check_quota(
        self,
        user_id: int,
        tier: str,
        db: Session
    ) -> Tuple[bool, dict]:
        """
        Check if user is within monthly quota.
        
        Returns: (allowed: bool, info: dict)
        """
        tier_config = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        monthly_limit = tier_config.get("monthly_claims", 100)
        
        # Unlimited quota
        if monthly_limit == -1:
            return True, {
                "quota_limit": -1,
                "quota_used": 0,
                "quota_remaining": -1,
                "quota_reset": None,
            }
        
        # Get current month's usage
        from app.models import ClaimRecord
        from sqlalchemy import func, extract
        
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        
        usage = db.query(func.count(ClaimRecord.id)).filter(
            ClaimRecord.user_id == user_id,
            ClaimRecord.created_at >= month_start,
            ClaimRecord.created_at <= month_end
        ).scalar() or 0
        
        remaining = max(0, monthly_limit - usage)
        allowed = usage < monthly_limit
        
        # Calculate reset time (first day of next month)
        next_month = (month_start + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return allowed, {
            "quota_limit": monthly_limit,
            "quota_used": usage,
            "quota_remaining": remaining,
            "quota_reset": int(next_month.timestamp()),
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


# ── Rate Limit Decorators ─────────────────────────────────────

def rate_limit(window: str = "minute", endpoint: str = None):
    """
    Decorator to apply rate limiting to endpoints.
    
    Usage:
        @rate_limit(window="minute", endpoint="/message")
        async def my_endpoint(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and user from kwargs
            request: Optional[Request] = kwargs.get("request")
            user: Optional[User] = kwargs.get("user")
            
            # Get identifier (user ID or IP)
            if user:
                identifier = f"user:{user.id}"
                tier = rate_limiter.get_user_tier(user)
            else:
                # Use IP for anonymous users
                client_ip = request.client.host if request else "unknown"
                identifier = f"ip:{client_ip}"
                tier = "anonymous"
            
            # Determine endpoint path
            endpoint_path = endpoint or (request.url.path if request else "/unknown")
            
            # Check rate limit
            allowed, info = rate_limiter.check_rate_limit(
                identifier, tier, endpoint_path, window
            )
            
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": info.get("limit"),
                        "retry_after": info.get("retry_after"),
                        "reset": info.get("reset"),
                    },
                    headers={
                        "X-RateLimit-Limit": str(info.get("limit", 0)),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(info.get("reset", 0)),
                        "Retry-After": str(info.get("retry_after", 60)),
                    }
                )
            
            # Add rate limit headers to response
            if request:
                request.state.rate_limit_info = info
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def check_quota(func):
    """
    Decorator to check monthly quota before processing.
    
    Usage:
        @check_quota
        async def my_endpoint(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        user: Optional[User] = kwargs.get("user")
        db: Optional[Session] = kwargs.get("db")
        
        # Skip quota check for anonymous users or if no DB session
        if not user or not db:
            return await func(*args, **kwargs)
        
        # Get user tier
        tier = rate_limiter.get_user_tier(user)
        
        # Check quota
        allowed, info = rate_limiter.check_quota(user.id, tier, db)
        
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Monthly quota exceeded",
                    "quota_limit": info.get("quota_limit"),
                    "quota_used": info.get("quota_used"),
                    "quota_reset": info.get("quota_reset"),
                    "message": f"You've used {info.get('quota_used')} of {info.get('quota_limit')} claims this month. Upgrade to Pro for more.",
                },
                headers={
                    "X-Quota-Limit": str(info.get("quota_limit", 0)),
                    "X-Quota-Remaining": "0",
                    "X-Quota-Reset": str(info.get("quota_reset", 0)),
                }
            )
        
        # Add quota info to request state
        request: Optional[Request] = kwargs.get("request")
        if request:
            request.state.quota_info = info
        
        return await func(*args, **kwargs)
    
    return wrapper


# ── Middleware for Rate Limit Headers ─────────────────────────

async def add_rate_limit_headers(request: Request, call_next):
    """Middleware to add rate limit headers to all responses"""
    response = await call_next(request)
    
    # Add rate limit info if available
    if hasattr(request.state, "rate_limit_info"):
        info = request.state.rate_limit_info
        response.headers["X-RateLimit-Limit"] = str(info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(info.get("reset", 0))
    
    # Add quota info if available
    if hasattr(request.state, "quota_info"):
        info = request.state.quota_info
        response.headers["X-Quota-Limit"] = str(info.get("quota_limit", 0))
        response.headers["X-Quota-Remaining"] = str(info.get("quota_remaining", 0))
        response.headers["X-Quota-Reset"] = str(info.get("quota_reset", 0))
    
    return response
