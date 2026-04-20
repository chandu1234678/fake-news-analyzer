"""
Multi-Model Ensemble for Enhanced Accuracy
==========================================
Loads fine-tuned models from backend/data/ensemble_config.json
(written by backend/training/train_finetune_ensemble.py).

When ensemble_config.json exists it uses:
  1. finetuned_roberta  — jy46604790/Fake-News-Bert-Detect fine-tuned on your data
  2. finetuned_deberta  — Arko007/fact-check1-v3-final fine-tuned on your data

Falls back to the original Bharat2004 models if no config is found.

Ensemble methods:
  - weighted  (default) — weighted average by each model's F1 score
  - voting              — majority vote
  - average             — simple mean
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
ENSEMBLE_CONFIG_PATH = os.path.join(DATA_DIR, "ensemble_config.json")

# ── Fallback models (used when no fine-tuned ensemble exists) ─
_FALLBACK_MODELS = {
    # Your own fine-tuned models — best to use first
    "distilbert_yours": {
        "model_id":   "Bharat2004/out",
        "fake_label": "LABEL_1",
        "weight":     1.8,   # 98.97% accuracy, 67MB — fast and accurate
        "max_length": 512,
        "description": "Bharat2004/out — DistilBERT 98.97% acc (your model)",
    },
    "deberta_yours": {
        "model_id":   "Bharat2004/deberta-fakenews-detector",
        "fake_label": "LABEL_1",
        "weight":     2.0,   # DeBERTa 200MB — higher accuracy
        "max_length": 512,
        "description": "Bharat2004/deberta-fakenews-detector — DeBERTa (your model)",
    },
    "deberta_v2": {
        "model_id":   "Bharat2004/deberta-factchecker",
        "fake_label": "LABEL_1",
        "weight":     1.5,
        "max_length": 512,
        "description": "Bharat2004/deberta-factchecker — DeBERTa (your model)",
    },
}

_model_pipelines: Dict[str, dict] = {}
_models_loaded = False
_active_config: Optional[dict] = None


def _load_ensemble_config() -> List[dict]:
    """
    Load model list from ensemble_config.json (written by train_finetune_ensemble.py).
    Falls back to _FALLBACK_MODELS if file doesn't exist.
    """
    global _active_config

    if os.path.exists(ENSEMBLE_CONFIG_PATH):
        try:
            with open(ENSEMBLE_CONFIG_PATH) as f:
                config = json.load(f)
            models = config.get("ensemble_models", [])
            if models:
                logger.info(
                    "Ensemble config loaded from %s (%d models, updated %s)",
                    ENSEMBLE_CONFIG_PATH,
                    len(models),
                    config.get("updated_at", "unknown"),
                )
                _active_config = config
                return models
        except Exception as e:
            logger.warning("Failed to read ensemble_config.json: %s", e)

    # Fallback
    logger.info("No ensemble_config.json found — using fallback Bharat2004 models")
    return [
        {"name": k, **v}
        for k, v in _FALLBACK_MODELS.items()
    ]


def _load_single_model(model_id: str, max_length: int) -> Optional[object]:
    """Load a single HuggingFace pipeline (local path or Hub ID)."""
    try:
        from transformers import pipeline
        import torch

        hf_token = os.getenv("HF_TOKEN")
        device = 0 if torch.cuda.is_available() else -1

        pipe = pipeline(
            "text-classification",
            model=model_id,
            tokenizer=model_id,
            token=hf_token,
            device=device,
            truncation=True,
            max_length=max_length,
        )
        return pipe
    except Exception as e:
        logger.warning("Failed to load model %s: %s", model_id, e)
        return None


def _load_all_models():
    """Load all models from config (or fallback). Called once lazily."""
    global _models_loaded, _model_pipelines

    if _models_loaded:
        return

    model_configs = _load_ensemble_config()
    logger.info("Loading %d ensemble models ...", len(model_configs))

    for cfg in model_configs:
        name     = cfg.get("name", cfg.get("model_id", "unknown"))
        model_id = cfg.get("model_id", "")
        weight   = float(cfg.get("weight", 1.0))
        max_len  = int(cfg.get("max_length", 512))
        fake_lbl = cfg.get("fake_label", "LABEL_0").upper()

        if not model_id:
            continue

        pipe = _load_single_model(model_id, max_len)
        if pipe:
            _model_pipelines[name] = {
                "pipeline":   pipe,
                "weight":     weight,
                "fake_label": fake_lbl,
                "model_id":   model_id,
                "description": cfg.get("description", model_id),
            }
            logger.info("  ✓ %-20s  weight=%.3f  %s", name, weight, model_id)

    _models_loaded = True

    if _model_pipelines:
        logger.info("Ensemble ready: %d/%d models loaded", len(_model_pipelines), len(model_configs))
    else:
        logger.warning("No ensemble models loaded — ensemble disabled")


def _predict_single(pipe, fake_label: str, text: str) -> Optional[Tuple[float, float]]:
    """
    Run inference on one model.
    Returns (fake_probability, raw_score) or None on failure.
    """
    try:
        result = pipe(text[:1500])[0]
        label = result["label"].upper()
        score = float(result["score"])

        # Normalize to fake probability regardless of label convention
        if label == fake_label:
            fake_prob = score
        else:
            fake_prob = 1.0 - score

        return fake_prob, score
    except Exception as e:
        logger.warning("Inference failed: %s", e)
        return None


def predict_ensemble(text: str, method: str = "weighted") -> Optional[Dict]:
    """
    Predict using the fine-tuned ensemble.

    Args:
        text:   Input text to classify
        method: "weighted" | "voting" | "average"

    Returns:
        {
          "fake":                  float,
          "confidence":            float,
          "source":                "ensemble",
          "models_used":           int,
          "individual_predictions": dict,
          "method":                str,
        }
        or None if no models are available.
    """
    if not _models_loaded:
        _load_all_models()

    if not _model_pipelines:
        return None

    predictions = {}
    for name, data in _model_pipelines.items():
        result = _predict_single(data["pipeline"], data["fake_label"], text)
        if result:
            fake_prob, raw_score = result
            predictions[name] = {
                "fake_probability": fake_prob,
                "confidence":       raw_score,
                "weight":           data["weight"],
                "model_id":         data["model_id"],
                "description":      data["description"],
            }

    if not predictions:
        return None

    # ── Ensemble aggregation ──────────────────────────────────
    if method == "weighted":
        total_w = sum(p["weight"] for p in predictions.values())
        fake_prob = sum(p["fake_probability"] * p["weight"] for p in predictions.values()) / total_w
        confidence = sum(p["confidence"] * p["weight"] for p in predictions.values()) / total_w

    elif method == "voting":
        votes = [1 if p["fake_probability"] > 0.5 else 0 for p in predictions.values()]
        fake_prob = sum(votes) / len(votes)
        confidence = abs(fake_prob - 0.5) * 2

    else:  # average
        fake_prob = sum(p["fake_probability"] for p in predictions.values()) / len(predictions)
        confidence = sum(p["confidence"] for p in predictions.values()) / len(predictions)

    return {
        "fake":                   round(fake_prob, 4),
        "confidence":             round(confidence, 4),
        "source":                 "ensemble",
        "models_used":            len(predictions),
        "individual_predictions": predictions,
        "method":                 method,
    }


def get_available_models() -> List[str]:
    if not _models_loaded:
        _load_all_models()
    return list(_model_pipelines.keys())


def get_model_info() -> Dict:
    if not _models_loaded:
        _load_all_models()
    return {
        "models_loaded":    len(_model_pipelines),
        "config_path":      ENSEMBLE_CONFIG_PATH,
        "config_exists":    os.path.exists(ENSEMBLE_CONFIG_PATH),
        "updated_at":       (_active_config or {}).get("updated_at"),
        "models": {
            name: {
                "model_id":    data["model_id"],
                "weight":      data["weight"],
                "description": data["description"],
            }
            for name, data in _model_pipelines.items()
        },
    }


if __name__ == "__main__":
    test_texts = [
        "COVID vaccines are safe and effective according to WHO",
        "Breaking: Scientists confirm earth is flat, NASA admits cover-up",
        "Stock market reaches new high amid economic recovery",
    ]

    print("Testing fine-tuned ensemble ...")
    for text in test_texts:
        result = predict_ensemble(text, method="weighted")
        if result:
            print(
                f"\n[{result['fake']:.0%} fake | {result['models_used']} models] "
                f"{text[:70]}"
            )
            for name, pred in result["individual_predictions"].items():
                print(f"  {name:20s}  {pred['fake_probability']:.0%}  (w={pred['weight']:.3f})")
        else:
            print(f"\nNo prediction for: {text[:60]}")
