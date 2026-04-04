"""
Meta-decision engine.

Uses a trained Logistic Regression (CalibratedClassifierCV) that learned
to combine ML + AI + evidence scores from labeled examples.

Falls back to the weighted heuristic if the model file is missing
(e.g. first deploy before training runs).
"""

import os
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_META_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "meta_model.joblib"
)
_meta_model = None


def _load_meta_model():
    global _meta_model
    if _meta_model is not None:
        return _meta_model
    if os.path.exists(_META_MODEL_PATH):
        try:
            import joblib
            _meta_model = joblib.load(_META_MODEL_PATH)
            logger.info("Meta-decision model loaded from %s", _META_MODEL_PATH)
        except Exception as e:
            logger.warning("Failed to load meta model: %s", e)
    return _meta_model


def _heuristic(ml_fake, ai_fake, evidence_score):
    """Original weighted heuristic — used as fallback."""
    fake_score   = 0.0
    total_weight = 0.0
    if ai_fake is not None:
        fake_score   += ai_fake * 0.50
        total_weight += 0.50
    if evidence_score is not None:
        fake_score   += (1 - evidence_score) * 0.32
        total_weight += 0.32
    if ml_fake is not None:
        fake_score   += ml_fake * 0.18
        total_weight += 0.18
    if total_weight == 0:
        return "uncertain", 0.5
    normalized = fake_score / total_weight
    confidence = round(min(0.97, max(0.50, abs(normalized - 0.5) * 2 + 0.5)), 2)
    verdict    = "fake" if normalized >= 0.5 else "real"
    return verdict, confidence


def decide(
    ml_fake: Optional[float],
    ai_fake: Optional[float],
    evidence_score: Optional[float],
):
    """
    Combine ML + AI + evidence scores into a final verdict.

    Uses trained meta-model when available, heuristic as fallback.
    Returns "uncertain" when signals conflict heavily or evidence is too weak.

    Args:
        ml_fake:        0–1, probability claim is FAKE (TF-IDF model)
        ai_fake:        0–1, probability claim is FAKE (LLM structured output)
        evidence_score: 0–1, news consistency score (1 = strongly real)

    Returns:
        (verdict: str, confidence: float)
    """
    ml  = float(ml_fake)        if ml_fake        is not None else 0.5
    ai  = float(ai_fake)        if ai_fake        is not None else 0.5
    ev  = float(evidence_score) if evidence_score is not None else 0.5

    # ── Uncertainty detection (before model inference) ────────
    # Case 1: AI and evidence strongly disagree
    ai_says_fake  = ai > 0.65
    ai_says_real  = ai < 0.35
    ev_says_real  = ev > 0.65
    ev_says_fake  = ev < 0.35

    signals_conflict = (ai_says_fake and ev_says_real) or (ai_says_real and ev_says_fake)

    # Case 2: All signals near 0.5 — genuinely uncertain
    all_near_center = abs(ml - 0.5) < 0.15 and abs(ai - 0.5) < 0.15 and abs(ev - 0.5) < 0.15

    if signals_conflict or all_near_center:
        return "uncertain", 0.5

    model = _load_meta_model()

    if model is not None:
        try:
            X = np.array([[ml, ai, ev]])
            proba      = model.predict_proba(X)[0]
            fake_prob  = float(proba[1])
            verdict    = "fake" if fake_prob >= 0.5 else "real"
            confidence = round(min(0.97, max(0.50, abs(fake_prob - 0.5) * 2 + 0.50)), 2)
            # If model itself is near-uncertain, surface that
            if confidence < 0.58:
                return "uncertain", confidence
            return verdict, confidence
        except Exception as e:
            logger.warning("Meta model inference failed, using heuristic: %s", e)

    return _heuristic(ml_fake, ai_fake, evidence_score)
