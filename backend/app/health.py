import os
import json
import time
from fastapi import APIRouter

router = APIRouter()

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _get_model_version() -> dict:
    path = os.path.join(_DATA_DIR, "model_version.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": "unknown"}


@router.api_route("/health", methods=["GET", "HEAD"])
def health():
    from app.analysis.drift import get_stats as drift_stats
    return {
        "status": "ok",
        "version": "2.0.0",
        "ts": int(time.time()),
        "model": _get_model_version(),
        "drift": drift_stats(),
    }
