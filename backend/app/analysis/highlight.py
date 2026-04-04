"""
Suspicious Phrase Highlighter

Identifies which words/phrases in a claim contributed most to the fake signal.
Uses two approaches:
  1. TF-IDF feature weights — top features that pushed toward fake
  2. Manipulation signal keywords — emotionally charged / clickbait patterns

Returns a list of (phrase, score, reason) tuples.
"""

import os
import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Manipulation patterns (from manipulation.py — kept in sync)
_SENSATIONAL = re.compile(
    r"\b(shocking|bombshell|exposed|breaking|exclusive|leaked|secret|"
    r"conspiracy|hoax|scam|fraud|cover.?up|they don.?t want you|"
    r"wake up|sheeple|mainstream media|fake news|deep state|"
    r"urgent|alert|warning|danger|crisis|catastrophe|disaster)\b",
    re.IGNORECASE
)
_EMOTIONAL = re.compile(
    r"\b(outrage|furious|disgusting|horrifying|terrifying|unbelievable|"
    r"incredible|insane|crazy|shocking|devastating|explosive|bombshell|"
    r"scandalous|shameful|disgusted|appalled)\b",
    re.IGNORECASE
)
_ABSOLUTE = re.compile(
    r"\b(always|never|everyone|nobody|all|none|every|no one|"
    r"100%|proven|confirmed|definitive|undeniable|irrefutable)\b",
    re.IGNORECASE
)


def _ml_top_phrases(text: str, top_n: int = 5) -> List[Tuple[str, float, str]]:
    """Get top TF-IDF features that pushed toward fake."""
    try:
        import joblib
        import numpy as np
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        model_path = os.path.join(base, "data", "model.joblib")
        vec_path   = os.path.join(base, "data", "vectorizer.joblib")
        if not (os.path.exists(model_path) and os.path.exists(vec_path)):
            return []

        model      = joblib.load(model_path)
        vectorizer = joblib.load(vec_path)

        vec = vectorizer.transform([text])
        feature_names = vectorizer.get_feature_names_out()

        # Get the base LR model (unwrap CalibratedClassifierCV if needed)
        lr = model
        if hasattr(model, "calibrated_classifiers_"):
            lr = model.calibrated_classifiers_[0].estimator

        if not hasattr(lr, "coef_"):
            return []

        coef = lr.coef_[0]  # fake class coefficients
        # Only look at features present in this text
        nonzero = vec.nonzero()[1]
        scored = [(feature_names[i], float(coef[i])) for i in nonzero if coef[i] > 0]
        scored.sort(key=lambda x: -x[1])
        return [(phrase, score, "ml") for phrase, score in scored[:top_n]]
    except Exception as e:
        logger.debug("ML highlight failed: %s", e)
        return []


def _pattern_phrases(text: str) -> List[Tuple[str, float, str]]:
    """Find manipulation pattern matches."""
    results = []
    for match in _SENSATIONAL.finditer(text):
        results.append((match.group(), 0.8, "sensational"))
    for match in _EMOTIONAL.finditer(text):
        results.append((match.group(), 0.7, "emotional"))
    for match in _ABSOLUTE.finditer(text):
        results.append((match.group(), 0.6, "absolute_claim"))
    # Deduplicate by phrase
    seen = set()
    deduped = []
    for phrase, score, reason in results:
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            deduped.append((phrase, score, reason))
    return deduped


def get_highlights(text: str) -> List[dict]:
    """
    Returns list of highlighted phrases with scores and reasons.
    Each item: {"phrase": str, "score": float, "reason": str}
    """
    ml_phrases  = _ml_top_phrases(text, top_n=4)
    pat_phrases = _pattern_phrases(text)

    combined = {}
    for phrase, score, reason in pat_phrases + ml_phrases:
        key = phrase.lower()
        if key not in combined or combined[key]["score"] < score:
            combined[key] = {"phrase": phrase, "score": round(score, 3), "reason": reason}

    # Sort by score descending, return top 6
    results = sorted(combined.values(), key=lambda x: -x["score"])[:6]
    return results
