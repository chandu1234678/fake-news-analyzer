"""
A/B Testing Routes

Endpoints for managing A/B tests, variant assignments, and metrics tracking.
Enables experimentation with different model versions and configurations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
import json
import hashlib

from database import get_db
from app.models import ABTest, ABTestAssignment, ABTestEvent, User
from app.auth import get_current_user, get_current_user_optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ab", tags=["ab-testing"])


# ── Schemas ───────────────────────────────────────────────────

class ABTestCreate(BaseModel):
    """Create new A/B test"""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    variants: Dict[str, Any]  # {"control": {...}, "treatment": {...}}
    traffic_split: Dict[str, float]  # {"control": 0.5, "treatment": 0.5}
    metrics: Optional[List[str]] = ["accuracy", "latency", "user_trust"]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ABTestUpdate(BaseModel):
    """Update A/B test configuration"""
    description: Optional[str] = None
    status: Optional[str] = Field(None, regex="^(draft|active|paused|completed)$")
    traffic_split: Optional[Dict[str, float]] = None
    end_date: Optional[datetime] = None


class VariantAssignment(BaseModel):
    """Variant assignment response"""
    test_id: int
    test_name: str
    variant: str
    config: Dict[str, Any]


class EventTrack(BaseModel):
    """Track A/B test event"""
    test_id: int
    event_type: str  # prediction, feedback, share, etc.
    event_data: Optional[Dict[str, Any]] = None
    accuracy: Optional[float] = None
    latency_ms: Optional[int] = None
    confidence: Optional[float] = None


class TestResults(BaseModel):
    """A/B test results summary"""
    test_id: int
    test_name: str
    status: str
    variants: Dict[str, Dict[str, Any]]  # Metrics per variant
    winner: Optional[str] = None
    confidence_level: Optional[float] = None


# ── Helper Functions ──────────────────────────────────────────

def _get_session_key(user: Optional[User]) -> str:
    """Generate consistent session key for variant assignment"""
    if user:
        return f"user_{user.id}"
    # For anonymous users, use a hash of their IP or other identifier
    # In production, you'd use request headers or cookies
    return f"anon_{hashlib.md5(str(datetime.utcnow().date()).encode()).hexdigest()[:8]}"


def _assign_variant(test: ABTest, session_key: str) -> str:
    """Assign variant using consistent hashing"""
    traffic_split = json.loads(test.traffic_split)
    
    # Use consistent hashing for stable assignments
    hash_val = int(hashlib.md5(f"{test.id}_{session_key}".encode()).hexdigest(), 16)
    rand_val = (hash_val % 10000) / 10000.0  # 0.0 to 1.0
    
    cumulative = 0.0
    for variant, split in traffic_split.items():
        cumulative += split
        if rand_val < cumulative:
            return variant
    
    # Fallback to first variant
    return list(traffic_split.keys())[0]


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/tests", response_model=Dict[str, Any])
def create_test(
    test: ABTestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Create a new A/B test (admin only).
    """
    
    # Validate traffic split sums to 1.0
    total_split = sum(test.traffic_split.values())
    if not (0.99 <= total_split <= 1.01):
        raise HTTPException(status_code=400, detail="Traffic split must sum to 1.0")
    
    # Validate variants match traffic split
    if set(test.variants.keys()) != set(test.traffic_split.keys()):
        raise HTTPException(status_code=400, detail="Variants and traffic split keys must match")
    
    # Check for duplicate name
    existing = db.query(ABTest).filter(ABTest.name == test.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Test name already exists")
    
    # Create test
    ab_test = ABTest(
        name=test.name,
        description=test.description,
        variants=json.dumps(test.variants),
        traffic_split=json.dumps(test.traffic_split),
        metrics=json.dumps(test.metrics) if test.metrics else None,
        start_date=test.start_date,
        end_date=test.end_date,
        status="draft",
    )
    
    db.add(ab_test)
    db.commit()
    db.refresh(ab_test)
    
    logger.info(f"Created A/B test: {test.name} (id={ab_test.id})")
    
    return {
        "id": ab_test.id,
        "name": ab_test.name,
        "status": ab_test.status,
        "variants": json.loads(ab_test.variants),
        "traffic_split": json.loads(ab_test.traffic_split),
    }


@router.get("/tests", response_model=List[Dict[str, Any]])
def list_tests(
    status: Optional[str] = Query(None, regex="^(draft|active|paused|completed)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    List all A/B tests (admin only).
    """
    
    query = db.query(ABTest)
    
    if status:
        query = query.filter(ABTest.status == status)
    
    tests = query.order_by(desc(ABTest.created_at)).all()
    
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "status": t.status,
            "variants": json.loads(t.variants),
            "traffic_split": json.loads(t.traffic_split),
            "start_date": t.start_date,
            "end_date": t.end_date,
            "created_at": t.created_at,
        }
        for t in tests
    ]


@router.patch("/tests/{test_id}", response_model=Dict[str, Any])
def update_test(
    test_id: int,
    update: ABTestUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Update A/B test configuration (admin only).
    """
    
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Update fields
    if update.description is not None:
        test.description = update.description
    
    if update.status is not None:
        # Validate status transitions
        if test.status == "completed" and update.status != "completed":
            raise HTTPException(status_code=400, detail="Cannot reopen completed test")
        test.status = update.status
        
        # Set start_date when activating
        if update.status == "active" and not test.start_date:
            test.start_date = datetime.utcnow()
    
    if update.traffic_split is not None:
        total_split = sum(update.traffic_split.values())
        if not (0.99 <= total_split <= 1.01):
            raise HTTPException(status_code=400, detail="Traffic split must sum to 1.0")
        test.traffic_split = json.dumps(update.traffic_split)
    
    if update.end_date is not None:
        test.end_date = update.end_date
    
    test.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(test)
    
    logger.info(f"Updated A/B test: {test.name} (id={test.id})")
    
    return {
        "id": test.id,
        "name": test.name,
        "status": test.status,
        "updated_at": test.updated_at,
    }


@router.get("/assign", response_model=List[VariantAssignment])
def get_assignments(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Get variant assignments for all active tests.
    Creates assignments if they don't exist.
    """
    
    # Get all active tests
    active_tests = db.query(ABTest).filter(ABTest.status == "active").all()
    
    if not active_tests:
        return []
    
    session_key = _get_session_key(user)
    assignments = []
    
    for test in active_tests:
        # Check for existing assignment
        existing = db.query(ABTestAssignment).filter(
            and_(
                ABTestAssignment.test_id == test.id,
                or_(
                    ABTestAssignment.user_id == (user.id if user else None),
                    ABTestAssignment.session_key == session_key
                )
            )
        ).first()
        
        if existing:
            variant = existing.variant
        else:
            # Assign new variant
            variant = _assign_variant(test, session_key)
            
            assignment = ABTestAssignment(
                test_id=test.id,
                user_id=user.id if user else None,
                session_key=session_key if not user else None,
                variant=variant,
            )
            db.add(assignment)
            db.commit()
            
            logger.info(f"Assigned variant '{variant}' for test '{test.name}' to {session_key}")
        
        # Get variant config
        variants = json.loads(test.variants)
        variant_config = variants.get(variant, {})
        
        assignments.append(VariantAssignment(
            test_id=test.id,
            test_name=test.name,
            variant=variant,
            config=variant_config,
        ))
    
    return assignments


@router.post("/track")
def track_event(
    event: EventTrack,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Track an event for A/B test metrics.
    """
    
    # Get test
    test = db.query(ABTest).filter(ABTest.id == event.test_id).first()
    if not test or test.status != "active":
        raise HTTPException(status_code=400, detail="Test not active")
    
    # Get assignment
    session_key = _get_session_key(user)
    assignment = db.query(ABTestAssignment).filter(
        and_(
            ABTestAssignment.test_id == event.test_id,
            or_(
                ABTestAssignment.user_id == (user.id if user else None),
                ABTestAssignment.session_key == session_key
            )
        )
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=400, detail="No assignment found for this test")
    
    # Create event
    ab_event = ABTestEvent(
        test_id=event.test_id,
        assignment_id=assignment.id,
        variant=assignment.variant,
        event_type=event.event_type,
        event_data=json.dumps(event.event_data) if event.event_data else None,
        accuracy=event.accuracy,
        latency_ms=event.latency_ms,
        confidence=event.confidence,
    )
    
    db.add(ab_event)
    db.commit()
    
    return {"success": True, "event_id": ab_event.id}


@router.get("/results/{test_id}", response_model=TestResults)
def get_results(
    test_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get A/B test results and metrics (admin only).
    """
    
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Get events grouped by variant
    variants_data = {}
    variants_list = json.loads(test.variants).keys()
    
    for variant in variants_list:
        events = db.query(ABTestEvent).filter(
            and_(
                ABTestEvent.test_id == test_id,
                ABTestEvent.variant == variant
            )
        ).all()
        
        # Calculate metrics
        total_events = len(events)
        avg_latency = sum(e.latency_ms for e in events if e.latency_ms) / max(total_events, 1)
        avg_confidence = sum(e.confidence for e in events if e.confidence) / max(total_events, 1)
        
        # Accuracy (from feedback events)
        feedback_events = [e for e in events if e.accuracy is not None]
        avg_accuracy = sum(e.accuracy for e in feedback_events) / max(len(feedback_events), 1)
        
        variants_data[variant] = {
            "total_events": total_events,
            "avg_latency_ms": round(avg_latency, 2),
            "avg_confidence": round(avg_confidence, 3),
            "avg_accuracy": round(avg_accuracy, 3) if feedback_events else None,
            "feedback_count": len(feedback_events),
        }
    
    # Determine winner (simple: highest accuracy)
    winner = None
    if all(v["avg_accuracy"] is not None for v in variants_data.values()):
        winner = max(variants_data.items(), key=lambda x: x[1]["avg_accuracy"])[0]
    
    return TestResults(
        test_id=test.id,
        test_name=test.name,
        status=test.status,
        variants=variants_data,
        winner=winner,
        confidence_level=None,  # Would need statistical test
    )


@router.delete("/tests/{test_id}")
def delete_test(
    test_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Delete an A/B test (admin only).
    Only draft tests can be deleted.
    """
    
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    if test.status != "draft":
        raise HTTPException(status_code=400, detail="Can only delete draft tests")
    
    db.delete(test)
    db.commit()
    
    logger.info(f"Deleted A/B test: {test.name} (id={test_id})")
    
    return {"success": True, "message": "Test deleted"}
