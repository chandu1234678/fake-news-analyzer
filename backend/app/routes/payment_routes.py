"""
Razorpay Payment Integration
=============================
Handles subscription payments for Indian users.

Pricing (INR):
  Starter:    ₹99/month   (~$1.20)  — 500 claims/month
  Pro:        ₹499/month  (~$6)     — 5,000 claims/month
  Enterprise: ₹2,999/month (~$36)   — Unlimited claims

Setup:
  1. Create Razorpay account: https://razorpay.com
  2. Get API keys from Dashboard → Settings → API Keys
  3. Add to .env:
       RAZORPAY_KEY_ID=rzp_test_...
       RAZORPAY_KEY_SECRET=...
  4. Set webhook URL in Razorpay Dashboard:
       https://your-domain.com/payment/webhook
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging
import os
import hmac
import hashlib

from database import get_db
from app.models import User
from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment", tags=["payment"])

# Razorpay credentials
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_ENABLED = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)

# Pricing (in paise: 1 INR = 100 paise)
TIER_PRICING = {
    "starter": {
        "name": "Starter",
        "price_inr": 99,
        "price_paise": 9900,
        "price_usd": 1.20,
        "claims_per_month": 500,
        "features": [
            "500 claims per month",
            "2-model AI ensemble (Qwen3 + Groq)",
            "Evidence from trusted sources",
            "Basic analytics",
            "Email support",
        ]
    },
    "pro": {
        "name": "Pro",
        "price_inr": 499,
        "price_paise": 49900,
        "price_usd": 6.00,
        "claims_per_month": 5000,
        "features": [
            "5,000 claims per month",
            "4-model AI ensemble (includes Gemini + Gemma4)",
            "Priority processing",
            "Advanced analytics & SHAP explanations",
            "Velocity tracking & clustering",
            "Priority email support",
        ]
    },
    "enterprise": {
        "name": "Enterprise",
        "price_inr": 2999,
        "price_paise": 299900,
        "price_usd": 36.00,
        "claims_per_month": -1,  # Unlimited
        "features": [
            "Unlimited claims",
            "5-model AI ensemble (includes MiniMax 229B)",
            "Dedicated support",
            "Custom integrations",
            "API access",
            "SLA guarantee",
            "White-label option",
        ]
    }
}


@router.get("/plans")
async def get_plans() -> Dict[str, Any]:
    """Get all available subscription plans with pricing."""
    return {
        "currency": "INR",
        "plans": TIER_PRICING,
        "razorpay_enabled": RAZORPAY_ENABLED,
    }


@router.post("/create-order")
async def create_order(
    plan: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a Razorpay order for subscription payment.
    
    Returns order_id and other details needed for Razorpay checkout.
    """
    if not RAZORPAY_ENABLED:
        raise HTTPException(status_code=503, detail="Payments not configured")

    if plan not in TIER_PRICING:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}")

    plan_info = TIER_PRICING[plan]

    try:
        import razorpay
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

        # Create order
        order_data = {
            "amount": plan_info["price_paise"],  # Amount in paise
            "currency": "INR",
            "receipt": f"sub_{user.id}_{plan}_{int(os.urandom(4).hex(), 16)}",
            "notes": {
                "user_id": user.id,
                "email": user.email,
                "plan": plan,
            }
        }

        order = client.order.create(data=order_data)

        logger.info("Razorpay order created: user=%s plan=%s order_id=%s",
                    user.id, plan, order["id"])

        return {
            "order_id": order["id"],
            "amount": plan_info["price_paise"],
            "currency": "INR",
            "key_id": RAZORPAY_KEY_ID,
            "plan": plan,
            "plan_name": plan_info["name"],
            "user": {
                "name": user.name or user.email.split("@")[0],
                "email": user.email,
            }
        }

    except Exception as e:
        logger.error("Razorpay order creation failed: %s", e)
        raise HTTPException(status_code=500, detail="Payment order creation failed")


@router.post("/verify-payment")
async def verify_payment(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    plan: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Verify Razorpay payment signature and upgrade user tier.
    
    Called after successful payment on frontend.
    """
    if not RAZORPAY_ENABLED:
        raise HTTPException(status_code=503, detail="Payments not configured")

    if plan not in TIER_PRICING:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}")

    try:
        # Verify signature
        message = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        if expected_signature != razorpay_signature:
            logger.warning("Payment signature mismatch: user=%s order=%s",
                          user.id, razorpay_order_id)
            raise HTTPException(status_code=400, detail="Invalid payment signature")

        # Signature valid — upgrade user
        old_tier = user.tier
        user.tier = plan
        db.commit()

        logger.info("Payment verified: user=%s %s→%s order=%s payment=%s",
                    user.id, old_tier, plan, razorpay_order_id, razorpay_payment_id)

        return {
            "success": True,
            "message": f"Successfully upgraded to {TIER_PRICING[plan]['name']}",
            "previous_tier": old_tier,
            "new_tier": plan,
            "new_limits": {
                "claims_per_month": TIER_PRICING[plan]["claims_per_month"],
                "features": TIER_PRICING[plan]["features"],
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Payment verification failed: %s", e)
        raise HTTPException(status_code=500, detail="Payment verification failed")


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Razorpay webhook handler for payment events.
    
    Handles: payment.captured, subscription.charged, etc.
    """
    if not RAZORPAY_ENABLED:
        return {"status": "disabled"}

    try:
        # Get webhook signature
        signature = request.headers.get("X-Razorpay-Signature", "")
        body = await request.body()

        # Verify webhook signature
        expected_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if expected_signature != signature:
            logger.warning("Webhook signature mismatch")
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Parse event
        event = await request.json()
        event_type = event.get("event")
        payload = event.get("payload", {})

        logger.info("Razorpay webhook: event=%s", event_type)

        # Handle payment.captured
        if event_type == "payment.captured":
            payment = payload.get("payment", {}).get("entity", {})
            notes = payment.get("notes", {})
            user_id = notes.get("user_id")
            plan = notes.get("plan")

            if user_id and plan:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    user.tier = plan
                    db.commit()
                    logger.info("Webhook upgraded user %s to %s", user_id, plan)

        return {"status": "ok"}

    except Exception as e:
        logger.error("Webhook processing failed: %s", e)
        return {"status": "error", "message": str(e)}


@router.post("/cancel-subscription")
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Cancel user's subscription (downgrade to free tier).
    
    In production, this should also cancel the Razorpay subscription.
    """
    old_tier = user.tier

    if old_tier == "free":
        raise HTTPException(status_code=400, detail="Already on free tier")

    user.tier = "free"
    db.commit()

    logger.info("Subscription cancelled: user=%s %s→free", user.id, old_tier)

    return {
        "success": True,
        "message": "Subscription cancelled. Downgraded to free tier.",
        "previous_tier": old_tier,
        "new_tier": "free",
    }
