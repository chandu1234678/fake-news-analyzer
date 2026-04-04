"""
Prediction Distribution Drift Detector

Tracks rolling distribution of verdicts and confidence scores.
Alerts when distribution shifts significantly from baseline.

Stored in-memory (resets on restart) — good enough for free tier.
For persistence, swap _store with DB writes.
"""

import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

# Rolling window of last N predictions
_WINDOW = 500
_store: deque = deque(maxlen=_WINDOW)

# Baseline from training (approximate)
_BASELINE_FAKE_RATE = 0.45   # ~45% of claims are fake in training data
_DRIFT_THRESHOLD    = 0.20   # alert if fake rate shifts by >20 percentage points


def record(verdict: str, confidence: float):
    """Call after every prediction."""
    _store.append({
        "verdict":    verdict,
        "confidence": confidence,
    })
    if len(_store) % 100 == 0:
        _check_drift()


def _check_drift():
    if len(_store) < 50:
        return
    fake_rate = sum(1 for r in _store if r["verdict"] == "fake") / len(_store)
    drift = abs(fake_rate - _BASELINE_FAKE_RATE)
    if drift > _DRIFT_THRESHOLD:
        logger.warning(
            "DRIFT DETECTED: fake_rate=%.2f (baseline=%.2f, delta=%.2f). "
            "Consider retraining.",
            fake_rate, _BASELINE_FAKE_RATE, drift
        )
    else:
        logger.info(
            "Drift check OK: fake_rate=%.2f (n=%d)", fake_rate, len(_store)
        )


def get_stats() -> dict:
    """Return current distribution stats."""
    if not _store:
        return {"n": 0}
    n = len(_store)
    fake_rate    = sum(1 for r in _store if r["verdict"] == "fake") / n
    uncertain    = sum(1 for r in _store if r["verdict"] == "uncertain") / n
    avg_conf     = sum(r["confidence"] for r in _store) / n
    drift        = abs(fake_rate - _BASELINE_FAKE_RATE)
    return {
        "n":             n,
        "fake_rate":     round(fake_rate, 3),
        "uncertain_rate": round(uncertain, 3),
        "avg_confidence": round(avg_conf, 3),
        "drift_delta":   round(drift, 3),
        "drift_alert":   drift > _DRIFT_THRESHOLD,
    }
