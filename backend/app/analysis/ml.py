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
# Priority order (set DEBERTA_MODEL env var to override):
#   1. Bharat2004/out              — DistilBERT 67MB, 98.97% acc, FASTEST ← default
#   2. Bharat2004/deberta-fakenews-detector — DeBERTa 200MB, high accuracy
#   3. Bharat2004/deberta-factchecker       — DeBERTa 200MB, alternative
#   4. Bharat2004/factchecker-deberta       — DeBERTa 200MB, alternative
#   5. Arko007/fact-check1-v3-final         — DeBERTa-v3-large 400MB, 99.98% acc
#
# On Render free tier (512MB RAM): use Bharat2004/out (67MB, fits easily)
# On paid tier / local with >1.5GB RAM: use deberta-fakenews-detector for best accuracy
_DEFAULT_MODEL = "Bharat2004/out"
ROBERTA_MODEL  = os.getenv("DEBERTA_MODEL") or _DEFAULT_MODEL

_roberta_pipe   = None
_roberta_failed = False


def _load_roberta():
    global _roberta_pipe, _roberta_failed
    if _roberta_pipe is not None or _roberta_failed:
        return _roberta_pipe
    
    # Check if user wants to force load transformer (useful when you have fine-tuned models)
    force_load = os.getenv("FORCE_TRANSFORMER_LOAD", "false").lower() == "true"
    
    # Skip RoBERTa on memory-constrained environments (< 1.5 GB available RAM)
    # Render free tier has 512 MB — torch alone needs ~800 MB
    if not force_load:
        try:
            import psutil
            available_mb = psutil.virtual_memory().available / (1024 * 1024)
            if available_mb < 1500:
                logger.warning(
                    "Skipping RoBERTa load — only %.0f MB RAM available (need 1500 MB). Using TF-IDF.",
                    available_mb,
                )
                logger.info("Set FORCE_TRANSFORMER_LOAD=true in .env to load anyway")
                _roberta_failed = True
                return None
        except ImportError:
            pass  # psutil not installed — proceed anyway

    try:
        from transformers import pipeline
        import torch
        
        # Get HF token for your fine-tuned models
        hf_token = os.getenv("HF_TOKEN")
        if hf_token:
            logger.info("Using HuggingFace token for model download")
        
        device = 0 if torch.cuda.is_available() else -1
        _roberta_pipe = pipeline(
            "text-classification",
            model=ROBERTA_MODEL,
            tokenizer=ROBERTA_MODEL,
            token=hf_token,  # Use your HF token
            device=device,
            truncation=True,
            max_length=512,
        )
        logger.info("✓ RoBERTa model loaded: %s (device=%s)", ROBERTA_MODEL, "GPU" if device == 0 else "CPU")
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
        # Handle all known label formats:
        # Arko007/fact-check1-v3-final: FAKE, REAL
        # jy46604790/Fake-News-Bert-Detect: LABEL_0=Fake, LABEL_1=Real
        # Bharat2004 models: LABEL_0=real, LABEL_1=fake
        if label in ("LABEL_0", "REAL"):
            return round(1.0 - score, 3)   # score = confidence of REAL → invert for fake prob
        elif label in ("LABEL_1", "FAKE"):
            return round(score, 3)          # score = confidence of FAKE
        else:
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
    Returns {"fake": float, "source": "roberta"|"tfidf"|"default"|"ensemble"}

    Priority order:
      1. Fine-tuned ensemble (ENABLE_ENSEMBLE=true) — uses both fine-tuned models
         from train_finetune_ensemble.py via backend/data/ensemble_config.json
      2. Single transformer (DEBERTA_MODEL env var or default)
      3. TF-IDF + Logistic Regression (always available, ~96% accuracy)
      4. Default 0.5 if everything fails
    """
    enable_ensemble = os.getenv("ENABLE_ENSEMBLE", "false").lower() == "true"

    if enable_ensemble:
        try:
            from app.analysis.ml_ensemble import predict_ensemble
            result = predict_ensemble(text, method="weighted")
            if result:
                logger.info(
                    "Ensemble: fake=%.3f models=%d (%s)",
                    result["fake"],
                    result["models_used"],
                    ", ".join(result["individual_predictions"].keys()),
                )
                try:
                    from app.cache import partial_cache
                    partial_cache.set_ml_score(text, result["fake"])
                except Exception:
                    pass
                return {
                    "fake":        result["fake"],
                    "source":      "ensemble",
                    "models_used": result["models_used"],
                    "confidence":  result.get("confidence", 0.0),
                }
        except Exception as e:
            logger.warning("Ensemble prediction failed: %s", e)
    
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
