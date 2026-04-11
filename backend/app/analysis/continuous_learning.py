"""
Continuous Learning — Auto-Retraining Pipeline

Monitors user feedback count and triggers model retraining when:
- 50+ new corrections have accumulated since last retrain
- OR it's been 7 days since last retrain and 10+ corrections exist

Runs in a background thread — non-blocking, won't affect request latency.
The retrain uses the existing retrain_from_feedback.py script.

Triggered automatically after each feedback submission.
"""
import os
import json
import logging
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
_RETRAIN_THRESHOLD   = 50   # corrections before auto-retrain
_RETRAIN_MIN         = 10   # minimum corrections needed
_RETRAIN_INTERVAL_DAYS = 7  # days between scheduled retrains

_retrain_lock = threading.Lock()
_is_retraining = False


def _get_version_info() -> dict:
    path = os.path.join(_DATA_DIR, "model_version.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _should_retrain(feedback_count: int) -> tuple[bool, str]:
    """Returns (should_retrain, reason)."""
    if feedback_count < _RETRAIN_MIN:
        return False, f"Only {feedback_count} corrections (need {_RETRAIN_MIN})"

    version = _get_version_info()
    last_retrain_str = version.get("retrain_timestamp")

    # Check threshold
    new_since_last = feedback_count - version.get("feedback_at_retrain", 0)
    if new_since_last >= _RETRAIN_THRESHOLD:
        return True, f"{new_since_last} new corrections since last retrain"

    # Check time-based trigger
    if last_retrain_str:
        try:
            last_retrain = datetime.fromisoformat(last_retrain_str)
            days_since = (datetime.utcnow() - last_retrain).days
            if days_since >= _RETRAIN_INTERVAL_DAYS and feedback_count >= _RETRAIN_MIN:
                return True, f"{days_since} days since last retrain with {feedback_count} corrections"
        except Exception:
            pass
    elif feedback_count >= _RETRAIN_THRESHOLD:
        return True, f"{feedback_count} corrections accumulated"

    return False, "Threshold not reached"


def _run_retrain(feedback_count: int):
    """Run retraining in background thread."""
    global _is_retraining
    with _retrain_lock:
        if _is_retraining:
            return
        _is_retraining = True

    try:
        logger.info("Auto-retraining triggered with %d feedback corrections", feedback_count)
        import subprocess, sys
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                              "training", "retrain_from_feedback.py")
        if not os.path.exists(script):
            logger.warning("retrain_from_feedback.py not found at %s", script)
            return

        result = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            logger.info("Auto-retrain completed successfully:\n%s", result.stdout[-500:])
            # Update version info with retrain metadata
            version = _get_version_info()
            version["retrain_timestamp"]   = datetime.utcnow().isoformat()
            version["feedback_at_retrain"] = feedback_count
            version["auto_retrain"]        = True
            path = os.path.join(_DATA_DIR, "model_version.json")
            with open(path, "w") as f:
                json.dump(version, f, indent=2)
        else:
            logger.error("Auto-retrain failed:\n%s", result.stderr[-500:])
    except subprocess.TimeoutExpired:
        logger.error("Auto-retrain timed out after 5 minutes")
    except Exception as e:
        logger.error("Auto-retrain error: %s", e)
    finally:
        with _retrain_lock:
            _is_retraining = False


def maybe_retrain(db) -> dict:
    """
    Check if retraining should be triggered and start it if so.
    Call this after each feedback submission.

    Returns status dict for logging.
    """
    try:
        from app.models import UserFeedback
        from sqlalchemy import func
        feedback_count = db.query(func.count(UserFeedback.id)).filter(
            UserFeedback.predicted != UserFeedback.actual
        ).scalar() or 0

        should, reason = _should_retrain(feedback_count)

        if should and not _is_retraining:
            thread = threading.Thread(
                target=_run_retrain,
                args=(feedback_count,),
                daemon=True,
                name="auto-retrain",
            )
            thread.start()
            logger.info("Auto-retrain started: %s", reason)
            return {"triggered": True, "reason": reason, "feedback_count": feedback_count}

        return {"triggered": False, "reason": reason, "feedback_count": feedback_count}
    except Exception as e:
        logger.debug("maybe_retrain check failed: %s", e)
        return {"triggered": False, "reason": str(e)}
