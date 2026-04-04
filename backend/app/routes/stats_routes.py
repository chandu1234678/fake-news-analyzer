"""
Stats API — feeds the dashboard with system intelligence metrics.
"""
import os
import json
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from database import get_db
from app.auth import get_current_user_optional
from app.models import User, ChatMessage, UserFeedback, ClaimRecord

router = APIRouter(prefix="/stats", tags=["stats"])
logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def _model_version() -> dict:
    path = os.path.join(_DATA_DIR, "model_version.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": "unknown"}


@router.get("/system")
def system_stats(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Returns model version, drift stats, top credible sources, feedback count."""
    from app.analysis.drift import get_stats as drift_stats
    from app.analysis.credibility import get_all_scores

    # Claim verdict distribution (all time)
    verdict_rows = db.query(
        ClaimRecord.verdict, func.count(ClaimRecord.id)
    ).group_by(ClaimRecord.verdict).all()
    verdict_dist = {v: c for v, c in verdict_rows}

    # Feedback count
    feedback_count = db.query(func.count(UserFeedback.id)).scalar() or 0

    # Top 5 most credible sources seen in evidence
    top_sources = get_all_scores()[:5]

    # Calibration data (from model_version.json)
    mv = _model_version()

    return {
        "model":         mv,
        "drift":         drift_stats(),
        "verdict_dist":  verdict_dist,
        "feedback_count": feedback_count,
        "top_sources":   top_sources,
    }


@router.get("/calibration")
def calibration_data():
    """
    Returns calibration curve data points for reliability diagram.
    Uses stored model metrics if available.
    """
    mv = _model_version()
    # Return stored metrics — actual curve requires running on test set
    return {
        "version":     mv.get("version", "unknown"),
        "accuracy":    mv.get("accuracy"),
        "f1_macro":    mv.get("f1_macro"),
        "brier_score": mv.get("brier_score"),
        "calibration": mv.get("calibration", "none"),
        "note": "Run train_calibrated.py to update these metrics."
    }
