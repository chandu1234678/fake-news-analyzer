"""
ML Analysis — two-tier approach:

Primary:  jy46604790/Fake-News-Bert-Detect  (RoBERTa-base, ~95% accuracy)
          Downloaded from HuggingFace on first use, cached in ~/.cache/huggingface
Fallback: TF-IDF + Logistic Regression from local model.joblib
          Used when transformers/torch not installed or model unavailable
"""

import os
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ── RoBERTa (primary) ─────────────────────────────────────────
_roberta_pipe = None
_roberta_failed = False  # don't retry after a load failure
ROBERTA_MODEL = "jy46604790/Fake-News-Bert-Detect"


def _load_roberta():
    global _roberta_pipe, _roberta_failed
    if _roberta_pipe is not None or _roberta_failed:
        return _roberta_pipe
    # Skip RoBERTa on memory-constrained environments (< 1.5 GB available RAM)
    # Render free tier has 512 MB — torch alone needs ~800 MB
    try:
        import psutil
        available_mb = psutil.virtual_memory().available / (1024 * 1024)
        if available_mb < 1500:
            logger.warning(
                "Skipping RoBERTa load — only %.0f MB RAM available (need 1500 MB). Using TF-IDF.",
                available_mb,
            )
            _roberta_failed = True
            return None
    except ImportError:
        pass  # psutil not installed — proceed anyway

    try:
        from transformers import pipeline
        import torch
        device = 0 if torch.cuda.is_available() else -1
        _roberta_pipe = pipeline(
            "text-classification",
            model=ROBERTA_MODEL,
            tokenizer=ROBERTA_MODEL,
            device=device,
            truncation=True,
            max_length=512,
        )
        logger.info("RoBERTa fake-news model loaded (device=%s)", "GPU" if device == 0 else "CPU")
    except Exception as e:
        logger.warning("RoBERTa load failed, will use TF-IDF fallback: %s", e)
        _roberta_failed = True
    return _roberta_pipe


def _roberta_score(text: str) -> float | None:
    """Returns fake probability 0-1, or None if unavailable."""
    pipe = _load_roberta()
    if pipe is None:
        return None
    try:
        # Truncate to 1500 chars — model handles tokenization internally
        result = pipe(text[:1500])[0]
        label = result["label"]   # LABEL_0 = Fake, LABEL_1 = Real
        score = float(result["score"])
        # LABEL_0 → fake, LABEL_1 → real
        return round(score if label == "LABEL_0" else 1.0 - score, 3)
    except Exception as e:
        logger.warning("RoBERTa inference failed: %s", e)
        return None


# ── TF-IDF fallback ───────────────────────────────────────────
_model = None
_vectorizer = None


def _load_tfidf():
    global _model, _vectorizer
    if _model is not None:
        return True
    import joblib
    model_path = os.path.join(DATA_DIR, "model.joblib")
    vec_path   = os.path.join(DATA_DIR, "vectorizer.joblib")
    if not os.path.exists(model_path) or not os.path.exists(vec_path):
        return False
    try:
        _model      = joblib.load(model_path)
        _vectorizer = joblib.load(vec_path)
        logger.info("TF-IDF model loaded from %s", DATA_DIR)
        return True
    except Exception as e:
        logger.warning("TF-IDF load failed: %s", e)
        return False


def _tfidf_score(text: str) -> float | None:
    if not _load_tfidf():
        return None
    try:
        vec  = _vectorizer.transform([text])
        prob = _model.predict_proba(vec)[0][1]
        return round(float(prob), 3)
    except Exception as e:
        logger.warning("TF-IDF inference failed: %s", e)
        return None


# ── Public API ────────────────────────────────────────────────
def run_ml_analysis(text: str) -> dict:
    """
    Returns {"fake": float, "source": "roberta"|"tfidf"|"default"}

    Tries RoBERTa first, falls back to TF-IDF, then returns 0.5 if both fail.
    """
    score = _roberta_score(text)
    if score is not None:
        return {"fake": score, "source": "roberta"}

    score = _tfidf_score(text)
    if score is not None:
        return {"fake": score, "source": "tfidf"}

    logger.warning("Both ML models unavailable, returning default 0.5")
    return {"fake": 0.5, "source": "default"}
