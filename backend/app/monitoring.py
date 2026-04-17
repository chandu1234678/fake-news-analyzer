"""
Monitoring and Metrics

Prometheus metrics for production monitoring.
Tracks request counts, latencies, model performance, and errors.
"""

import time
import logging
from functools import wraps
from typing import Callable, Optional
from prometheus_client import Counter, Histogram, Gauge, Info
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Request Metrics ───────────────────────────────────────────

# Total requests by endpoint and status
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Request duration
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Active requests
http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests in progress',
    ['method', 'endpoint']
)

# ── Model Metrics ─────────────────────────────────────────────

# Predictions by verdict
model_predictions_total = Counter(
    'model_predictions_total',
    'Total model predictions',
    ['verdict', 'model_version']
)

# Prediction confidence distribution
model_confidence = Histogram(
    'model_confidence',
    'Model prediction confidence',
    ['verdict'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Model latency
model_inference_duration_seconds = Histogram(
    'model_inference_duration_seconds',
    'Model inference duration in seconds',
    ['model_type'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

# Model accuracy (from feedback)
model_accuracy = Gauge(
    'model_accuracy',
    'Model accuracy from user feedback',
    ['model_version', 'time_window']
)

# ── Feature Metrics ───────────────────────────────────────────

# SHAP explanations
shap_explanations_total = Counter(
    'shap_explanations_total',
    'Total SHAP explanations generated',
    ['status']  # success, timeout, error
)

shap_duration_seconds = Histogram(
    'shap_duration_seconds',
    'SHAP computation duration in seconds',
    buckets=[0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
)

# Review queue
review_queue_size = Gauge(
    'review_queue_size',
    'Number of claims in review queue',
    ['priority']
)

reviews_submitted_total = Counter(
    'reviews_submitted_total',
    'Total reviews submitted by users',
    ['verdict']
)

# A/B testing
ab_test_assignments_total = Counter(
    'ab_test_assignments_total',
    'Total A/B test variant assignments',
    ['test_name', 'variant']
)

ab_test_events_total = Counter(
    'ab_test_events_total',
    'Total A/B test events tracked',
    ['test_name', 'variant', 'event_type']
)

# ── Cache Metrics ─────────────────────────────────────────────

cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type']
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type']
)

# ── Error Metrics ─────────────────────────────────────────────

errors_total = Counter(
    'errors_total',
    'Total errors',
    ['error_type', 'endpoint']
)

# ── System Metrics ────────────────────────────────────────────

# Application info
app_info = Info('app', 'Application information')
app_info.info({
    'version': '2.0.0',
    'name': 'FactCheck AI',
    'environment': 'production'
})

# Database connections
db_connections_active = Gauge(
    'db_connections_active',
    'Number of active database connections'
)

# ── Decorators ────────────────────────────────────────────────

def track_request_metrics(endpoint: str):
    """Decorator to track HTTP request metrics"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            method = "POST"  # Most endpoints are POST
            
            # Track in-progress requests
            http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
            
            start_time = time.time()
            status = "200"
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "500"
                errors_total.labels(error_type=type(e).__name__, endpoint=endpoint).inc()
                raise
            finally:
                # Track duration
                duration = time.time() - start_time
                http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
                
                # Track total requests
                http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
                
                # Decrement in-progress
                http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()
        
        return wrapper
    return decorator


def track_model_metrics(model_version: str = "1.0"):
    """Decorator to track model inference metrics"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Track prediction
                if isinstance(result, dict) and 'verdict' in result:
                    verdict = result['verdict']
                    confidence = result.get('confidence', 0.0)
                    
                    model_predictions_total.labels(
                        verdict=verdict,
                        model_version=model_version
                    ).inc()
                    
                    model_confidence.labels(verdict=verdict).observe(confidence)
                
                return result
            finally:
                # Track duration
                duration = time.time() - start_time
                model_inference_duration_seconds.labels(model_type="tfidf").observe(duration)
        
        return wrapper
    return decorator


# ── Helper Functions ──────────────────────────────────────────

def track_shap_explanation(success: bool, duration: float):
    """Track SHAP explanation metrics"""
    status = "success" if success else "timeout"
    shap_explanations_total.labels(status=status).inc()
    shap_duration_seconds.observe(duration)


def track_review_submission(verdict: str):
    """Track review submission"""
    reviews_submitted_total.labels(verdict=verdict).inc()


def track_ab_assignment(test_name: str, variant: str):
    """Track A/B test assignment"""
    ab_test_assignments_total.labels(test_name=test_name, variant=variant).inc()


def track_ab_event(test_name: str, variant: str, event_type: str):
    """Track A/B test event"""
    ab_test_events_total.labels(
        test_name=test_name,
        variant=variant,
        event_type=event_type
    ).inc()


def update_review_queue_metrics(db):
    """Update review queue size metrics"""
    try:
        from app.models import ClaimRecord, VelocityRecord
        from sqlalchemy import and_, or_
        
        # Total pending
        total = db.query(ClaimRecord).filter(
            and_(
                ClaimRecord.confidence >= 0.45,
                ClaimRecord.confidence <= 0.55
            )
        ).count()
        review_queue_size.labels(priority="all").set(total)
        
        # High priority (viral + trending + coordinated)
        high_priority = db.query(ClaimRecord).join(
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
        review_queue_size.labels(priority="high").set(high_priority)
        
    except Exception as e:
        logger.error(f"Failed to update review queue metrics: {e}")


def update_model_accuracy_metrics(db):
    """Update model accuracy from recent feedback"""
    try:
        from app.models import UserFeedback
        from datetime import timedelta
        
        # Last 24 hours
        since_24h = datetime.utcnow() - timedelta(hours=24)
        feedback_24h = db.query(UserFeedback).filter(
            UserFeedback.created_at >= since_24h
        ).all()
        
        if feedback_24h:
            correct = sum(1 for f in feedback_24h if f.predicted == f.actual)
            accuracy_24h = correct / len(feedback_24h)
            model_accuracy.labels(model_version="1.0", time_window="24h").set(accuracy_24h)
        
        # Last 7 days
        since_7d = datetime.utcnow() - timedelta(days=7)
        feedback_7d = db.query(UserFeedback).filter(
            UserFeedback.created_at >= since_7d
        ).all()
        
        if feedback_7d:
            correct = sum(1 for f in feedback_7d if f.predicted == f.actual)
            accuracy_7d = correct / len(feedback_7d)
            model_accuracy.labels(model_version="1.0", time_window="7d").set(accuracy_7d)
        
    except Exception as e:
        logger.error(f"Failed to update model accuracy metrics: {e}")
