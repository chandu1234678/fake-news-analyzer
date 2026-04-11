import os
import json
import time
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_REQUIRED_MODELS = ["model.joblib", "vectorizer.joblib", "meta_model.joblib"]


def _get_model_version() -> dict:
    path = os.path.join(_DATA_DIR, "model_version.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": "unknown"}


def _check_db() -> dict:
    try:
        from database import engine
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        logger.error("DB health check failed: %s", e)
        return {"status": "error", "detail": str(e)}


def _check_models() -> dict:
    missing = [f for f in _REQUIRED_MODELS if not os.path.exists(os.path.join(_DATA_DIR, f))]
    return {"status": "ok" if not missing else "degraded", "missing": missing}


@router.api_route("/health", methods=["GET", "HEAD"])
def health():
    mv       = _get_model_version()
    db_check = _check_db()
    ml_check = _check_models()

    try:
        from app.analysis.drift import get_stats as drift_stats
        drift = drift_stats()
    except Exception:
        drift = {}

    overall = "ok"
    if db_check["status"] != "ok":
        overall = "degraded"
    if ml_check["status"] != "ok":
        overall = "degraded"

    payload = {
        "status":  overall,
        "version": "2.0.0",
        "ts":      int(time.time()),
        "model":   mv,
        "drift":   drift,
        "checks": {
            "database": db_check,
            "models":   ml_check,
        },
    }

    status_code = 200 if overall == "ok" else 503
    return JSONResponse(content=payload, status_code=status_code)
