"""
ML Analysis — two-tier approach:

Primary:  Fine-tuned DeBERTa-v3-base (or RoBERTa) from HuggingFace
          Set DEBERTA_MODEL env var to your HF model ID after training
          Falls back to jy46604790/Fake-News-Bert-Detect if not set
Fallback: TF-IDF + Logistic Regression from local model.joblib
          Always available, used when transformer unavailable or OOM
"""

import os
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ── Transformer model (primary) ───────────────────────────────
# After training on Colab, set DEBERTA_MODEL=your-hf-username/factchecker-deberta
# Falls back to the public RoBERTa model if not configured
_DEFAULT_MODEL  = "jy46604790/Fake-News-Bert-Detect"
ROBERTA_MODEL   = os.getenv("DEBERTA_MODEL", _DEFAULT_MODEL)

_roberta_pipe   = None
_roberta_failed = False

# ── Transformer model (primary) ───────────────────────────────
# After training on Colab, set DEBERTA_MODEL=your-hf-username/factchecker-deberta
# Falls back to the public RoBERTa model if not configured
_DEFAULT_MODEL  = "jy46604790/Fake-News-Bert-Detect"
ROBERTA_MODEL   = os.getenv("DEBERTA_MODEL", _DEFAULT_MODEL)

_roberta_pipe   = None
_roberta_failed = False


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
        result = pipe(text[:1500])[0]
        label  = result["label"].upper()
        score  = float(result["score"])
        # Handle both label formats:
        # RoBERTa: LABEL_0=Fake, LABEL_1=Real
        # DeBERTa fine-tuned: FAKE, REAL
        if label in ("LABEL_0", "FAKE"):
            return round(score, 3)
        elif label in ("LABEL_1", "REAL"):
            return round(1.0 - score, 3)
        else:
            # Unknown label — use score as-is if > 0.5 means fake
            return round(score, 3)
    except Exception as e:
        logger.warning("Transformer inference failed: %s", e)
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
    Caches results for 24 hours to reduce compute costs.
    """
    # Try cache first
    try:
        from app.cache import partial_cache
        cached = partial_cache.get_ml_score(text)
        if cached is not None:
            logger.debug("ML cache hit")
            return {"fake": cached, "source": "cache"}
    except Exception as e:
        logger.debug(f"Cache lookup failed: {e}")
    
    # Compute score
    score = _roberta_score(text)
    if score is not None:
        source = "deberta" if "deberta" in ROBERTA_MODEL.lower() else "roberta"
        # Cache the result
        try:
            from app.cache import partial_cache
            partial_cache.set_ml_score(text, score)
        except Exception as e:
            logger.debug(f"Cache set failed: {e}")
        return {"fake": score, "source": source}

    score = _tfidf_score(text)
    if score is not None:
        # Cache the result
        try:
            from app.cache import partial_cache
            partial_cache.set_ml_score(text, score)
        except Exception as e:
            logger.debug(f"Cache set failed: {e}")
        return {"fake": score, "source": "tfidf"}

    logger.warning("Both ML models unavailable, returning default 0.5")
    return {"fake": 0.5, "source": "default"}
