"""
A/B Testing Integration

Helper functions for integrating A/B tests into the main verification pipeline.
Handles variant assignment, model selection, and event tracking.
"""

import logging
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models import ABTest, ABTestAssignment, ABTestEvent, User

logger = logging.getLogger(__name__)


def get_active_model_variant(
    db: Session,
    user: Optional[User] = None,
    session_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get the active model variant for this user/session.
    Returns None if no active A/B test for models.
    
    Returns:
        {
            "test_id": int,
            "variant": str,
            "model_version": str,
            "model_path": str,
            ...
        }
    """
    
    # Look for active model A/B tests
    active_tests = db.query(ABTest).filter(
        ABTest.status == "active"
    ).all()
    
    for test in active_tests:
        variants = json.loads(test.variants)
        
        # Check if this is a model test (has model_version in variants)
        if not any("model_version" in v for v in variants.values()):
            continue
        
        # Get assignment
        assignment = db.query(ABTestAssignment).filter(
            ABTestAssignment.test_id == test.id
        )
        
        if user:
            assignment = assignment.filter(ABTestAssignment.user_id == user.id)
        elif session_key:
            assignment = assignment.filter(ABTestAssignment.session_key == session_key)
        else:
            continue
        
        assignment = assignment.first()
        
        if assignment:
            variant_config = variants.get(assignment.variant, {})
            return {
                "test_id": test.id,
                "test_name": test.name,
                "variant": assignment.variant,
                **variant_config
            }
    
    return None


def track_prediction_event(
    db: Session,
    test_id: int,
    user: Optional[User] = None,
    session_key: Optional[str] = None,
    verdict: str = None,
    confidence: float = None,
    latency_ms: int = None,
    event_data: Optional[Dict[str, Any]] = None
):
    """
    Track a prediction event for A/B testing metrics.
    """
    
    try:
        # Get assignment
        assignment = db.query(ABTestAssignment).filter(
            ABTestAssignment.test_id == test_id
        )
        
        if user:
            assignment = assignment.filter(ABTestAssignment.user_id == user.id)
        elif session_key:
            assignment = assignment.filter(ABTestAssignment.session_key == session_key)
        else:
            logger.warning("No user or session_key for A/B event tracking")
            return
        
        assignment = assignment.first()
        
        if not assignment:
            logger.warning(f"No assignment found for test {test_id}")
            return
        
        # Create event
        event = ABTestEvent(
            test_id=test_id,
            assignment_id=assignment.id,
            variant=assignment.variant,
            event_type="prediction",
            event_data=json.dumps(event_data) if event_data else None,
            confidence=confidence,
            latency_ms=latency_ms,
        )
        
        db.add(event)
        db.commit()
        
        logger.debug(f"Tracked prediction event for test {test_id}, variant {assignment.variant}")
        
    except Exception as e:
        logger.error(f"Failed to track A/B event: {e}")
        db.rollback()


def track_feedback_event(
    db: Session,
    test_id: int,
    user: Optional[User] = None,
    session_key: Optional[str] = None,
    predicted: str = None,
    actual: str = None,
    confidence: float = None
):
    """
    Track a feedback event (user correction) for A/B testing.
    Calculates accuracy for the variant.
    """
    
    try:
        # Get assignment
        assignment = db.query(ABTestAssignment).filter(
            ABTestAssignment.test_id == test_id
        )
        
        if user:
            assignment = assignment.filter(ABTestAssignment.user_id == user.id)
        elif session_key:
            assignment = assignment.filter(ABTestAssignment.session_key == session_key)
        else:
            return
        
        assignment = assignment.first()
        
        if not assignment:
            return
        
        # Calculate accuracy (1.0 if correct, 0.0 if wrong)
        accuracy = 1.0 if predicted == actual else 0.0
        
        # Create event
        event = ABTestEvent(
            test_id=test_id,
            assignment_id=assignment.id,
            variant=assignment.variant,
            event_type="feedback",
            event_data=json.dumps({"predicted": predicted, "actual": actual}),
            accuracy=accuracy,
            confidence=confidence,
        )
        
        db.add(event)
        db.commit()
        
        logger.debug(f"Tracked feedback event for test {test_id}, accuracy={accuracy}")
        
    except Exception as e:
        logger.error(f"Failed to track feedback event: {e}")
        db.rollback()


def should_use_variant_model(variant_config: Dict[str, Any]) -> bool:
    """
    Check if we should use the variant model instead of default.
    """
    return "model_version" in variant_config or "model_path" in variant_config


def get_model_path_for_variant(variant_config: Dict[str, Any], default_path: str) -> str:
    """
    Get the model path for a variant, or return default.
    """
    return variant_config.get("model_path", default_path)
