"""
SHAP Explanation Routes

Provides detailed SHAP-based explanations for fake news predictions.
"""

import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..auth import get_current_user_optional
from ..models import User
from ..schemas import ExplainRequest, ExplainResponse
from ..analysis.shap_explainer import explain_prediction
from ..analysis.attention_extractor import extract_attention_weights
from ..analysis.highlight import generate_shap_highlights
from ..analysis import ml

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/explain", tags=["explain"])


@router.post("", response_model=ExplainResponse)
def explain_claim(
    req: ExplainRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Generate detailed SHAP explanation for a claim
    
    Provides token-level importance scores, attention weights (for transformers),
    and visual highlights to explain why a claim was classified as fake or real.
    
    Args:
        req: ExplainRequest with text and options
        db: Database session
        user: Optional authenticated user
    
    Returns:
        ExplainResponse with SHAP explanation and highlights
    """
    start_time = time.time()
    
    text = req.text
    model_type = req.model_type
    include_attention = req.include_attention
    num_samples = req.num_samples
    
    logger.info(f"Explain request: model_type={model_type}, include_attention={include_attention}")
    
    # Get ML model and vectorizer
    try:
        # Load models
        import joblib
        import os
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        data_dir = os.path.join(base_dir, "data")
        
        model_path = os.path.join(data_dir, "model.joblib")
        vec_path = os.path.join(data_dir, "vectorizer.joblib")
        
        # Auto-detect model type if needed
        if model_type == "auto":
            # Try to determine from available models
            ml_result = ml.run_ml_analysis(text)
            model_type = ml_result.get("source", "tfidf")
            if model_type not in ["tfidf", "roberta", "deberta"]:
                model_type = "tfidf"
            if model_type in ["roberta", "deberta"]:
                model_type = "transformer"
        
        # Get prediction first
        ml_result = ml.run_ml_analysis(text)
        fake_prob = ml_result.get("fake", 0.5)
        verdict = "fake" if fake_prob >= 0.5 else "real"
        confidence = abs(fake_prob - 0.5) * 2
        
        prediction = {
            "verdict": verdict,
            "confidence": round(confidence, 3),
            "fake_probability": round(fake_prob, 3)
        }
        
        # Generate SHAP explanation
        shap_explanation = None
        attention_weights = None
        highlights = []
        explanation_type = "heuristic"
        
        if model_type == "tfidf":
            # TF-IDF model explanation
            if os.path.exists(model_path) and os.path.exists(vec_path):
                model = joblib.load(model_path)
                vectorizer = joblib.load(vec_path)
                
                shap_values = explain_prediction(
                    text, model, vectorizer, "tfidf", num_samples
                )
                
                if shap_values:
                    shap_explanation = shap_values
                    highlights = generate_shap_highlights(text, shap_values)
                    explanation_type = "shap"
                    logger.info("TF-IDF SHAP explanation generated")
        
        elif model_type == "transformer":
            # Transformer model explanation
            from ..analysis.transformer import get_transformer
            
            transformer = get_transformer()
            if transformer.is_available():
                # Get SHAP explanation
                shap_values = explain_prediction(
                    text, transformer.classifier, None, "transformer", num_samples
                )
                
                if shap_values:
                    shap_explanation = shap_values
                    highlights = generate_shap_highlights(text, shap_values)
                    explanation_type = "shap"
                    logger.info("Transformer SHAP explanation generated")
                
                # Get attention weights if requested
                if include_attention:
                    attention_data = extract_attention_weights(text)
                    if attention_data:
                        attention_weights = attention_data
                        logger.info("Attention weights extracted")
        
        # Fallback to heuristic highlighting if SHAP failed
        if not highlights:
            from ..analysis.highlight import get_highlights
            highlights = get_highlights(text)
            explanation_type = "heuristic"
            logger.info("Using heuristic highlighting (SHAP unavailable)")
        
        # Build visualization data
        visualization_data = None
        if shap_explanation:
            visualization_data = {
                "top_fake_signals": shap_explanation.get("top_positive", [])[:5],
                "top_real_signals": shap_explanation.get("top_negative", [])[:5],
                "base_value": shap_explanation.get("base_value", 0.5)
            }
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return ExplainResponse(
            text=text,
            prediction=prediction,
            shap_explanation=shap_explanation,
            attention_weights=attention_weights,
            highlights=highlights,
            visualization_data=visualization_data,
            latency_ms=latency_ms,
            explanation_type=explanation_type
        )
    
    except Exception as e:
        logger.error(f"Explanation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Explanation failed: {str(e)}")


@router.get("/health")
def explain_health():
    """Check if SHAP explainability is available"""
    try:
        import shap
        shap_available = True
    except ImportError:
        shap_available = False
    
    try:
        import transformers
        import torch
        transformers_available = True
    except ImportError:
        transformers_available = False
    
    return {
        "status": "ok",
        "shap_available": shap_available,
        "transformers_available": transformers_available,
        "features": {
            "tfidf_explanation": shap_available,
            "transformer_explanation": shap_available and transformers_available,
            "attention_extraction": transformers_available
        }
    }
