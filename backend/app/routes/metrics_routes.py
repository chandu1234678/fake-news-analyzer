"""
Metrics Routes

Prometheus metrics endpoint and monitoring utilities.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import logging

from database import get_db
from app.monitoring import update_review_queue_metrics, update_model_accuracy_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics_endpoint(db: Session = Depends(get_db)):
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus text format.
    """
    
    try:
        # Update dynamic metrics before returning
        update_review_queue_metrics(db)
        update_model_accuracy_metrics(db)
    except Exception as e:
        logger.error(f"Failed to update metrics: {e}")
    
    # Generate Prometheus metrics
    metrics_data = generate_latest()
    
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )


@router.get("/health/metrics")
def health_metrics(db: Session = Depends(get_db)):
    """
    Health check with basic metrics (JSON format for dashboards).
    """
    
    try:
        from app.models import ClaimRecord, UserFeedback, ABTest
        from datetime import datetime, timedelta
        
        # Claims processed (last 24h)
        since_24h = datetime.utcnow() - timedelta(hours=24)
        claims_24h = db.query(ClaimRecord).filter(
            ClaimRecord.created_at >= since_24h
        ).count()
        
        # Reviews submitted (last 24h)
        reviews_24h = db.query(UserFeedback).filter(
            UserFeedback.created_at >= since_24h
        ).count()
        
        # Active A/B tests
        active_tests = db.query(ABTest).filter(ABTest.status == "active").count()
        
        # Review queue size
        review_queue = db.query(ClaimRecord).filter(
            ClaimRecord.confidence >= 0.45,
            ClaimRecord.confidence <= 0.55
        ).count()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "claims_processed_24h": claims_24h,
                "reviews_submitted_24h": reviews_24h,
                "active_ab_tests": active_tests,
                "review_queue_size": review_queue,
            }
        }
        
    except Exception as e:
        logger.error(f"Health metrics failed: {e}")
        return {
            "status": "degraded",
            "error": str(e)
        }
