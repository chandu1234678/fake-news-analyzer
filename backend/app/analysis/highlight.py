"""
Suspicious Phrase Highlighter

Identifies which words/phrases in a claim contributed most to the fake signal.
Uses three approaches (in priority order):
  1. SHAP values — principled token-level importance (when available)
  2. TF-IDF feature weights — top features that pushed toward fake
  3. Manipulation signal keywords — emotionally charged / clickbait patterns

Returns a list of (phrase, score, reason) tuples.
"""

import os
import re
import logging
from typing import List, Tuple, Dict, Optional
import time

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



def generate_shap_highlights(
    text: str,
    shap_values: Dict,
    threshold: float = 0.05,
    max_highlights: int = 10
) -> List[dict]:
    """
    Generate highlights based on SHAP importance scores
    
    Args:
        text: Original claim text
        shap_values: Output from SHAPExplainer.explain()
        threshold: Minimum absolute importance to highlight
        max_highlights: Maximum number of highlights to return
    
    Returns:
        [
            {
                "phrase": str,
                "importance": float,
                "direction": "fake" | "real",
                "position": {"start": int, "end": int},
                "confidence": float,
                "explanation": str
            }
        ]
    """
    if not shap_values or "token_importances" not in shap_values:
        logger.warning("Invalid SHAP values provided")
        return []
    
    token_importances = shap_values["token_importances"]
    
    # Step 1: Filter by importance threshold
    significant_tokens = [
        t for t in token_importances 
        if abs(t["importance"]) >= threshold
    ]
    
    if not significant_tokens:
        logger.debug("No tokens meet importance threshold")
        return []
    
    # Step 2: Sort by absolute importance
    significant_tokens.sort(key=lambda t: abs(t["importance"]), reverse=True)
    
    # Step 3: Merge adjacent tokens into phrases
    phrases = _merge_adjacent_tokens(significant_tokens, text)
    
    # Step 4: Convert to highlight format
    highlights = []
    for phrase_data in phrases[:max_highlights]:
        phrase_text = phrase_data["text"]
        importance = phrase_data["importance"]
        direction = "fake" if importance > 0 else "real"
        confidence = phrase_data["confidence"]
        
        # Find character positions in original text
        char_start, char_end = _find_phrase_position(text, phrase_text)
        
        if char_start == -1:
            continue  # Skip if phrase not found
        
        highlights.append({
            "phrase": phrase_text,
            "importance": round(importance, 4),
            "direction": direction,
            "position": {"start": char_start, "end": char_end},
            "confidence": round(confidence, 3),
            "explanation": _generate_explanation(phrase_text, importance, direction),
            "score": round(confidence, 3),  # Backward compatibility
            "reason": "shap"
        })
    
    return highlights


def _merge_adjacent_tokens(tokens: List[Dict], text: str) -> List[Dict]:
    """
    Merge adjacent tokens with same direction into phrases
    
    Args:
        tokens: List of token importance dicts
        text: Original text
    
    Returns:
        List of phrase dicts with merged tokens
    """
    if not tokens:
        return []
    
    phrases = []
    current_phrase = None
    
    for token in tokens:
        token_text = token["token"]
        importance = token["importance"]
        confidence = token["confidence"]
        
        if current_phrase is None:
            # Start new phrase
            current_phrase = {
                "tokens": [token_text],
                "importance": importance,
                "confidence": confidence,
                "direction": "fake" if importance > 0 else "real"
            }
        else:
            # Check if should merge with current phrase
            same_direction = (
                (importance > 0 and current_phrase["direction"] == "fake") or
                (importance < 0 and current_phrase["direction"] == "real")
            )
            
            if same_direction:
                # Merge into current phrase
                current_phrase["tokens"].append(token_text)
                current_phrase["importance"] += importance
                current_phrase["confidence"] = max(current_phrase["confidence"], confidence)
            else:
                # Save current phrase and start new one
                current_phrase["text"] = " ".join(current_phrase["tokens"])
                phrases.append(current_phrase)
                
                current_phrase = {
                    "tokens": [token_text],
                    "importance": importance,
                    "confidence": confidence,
                    "direction": "fake" if importance > 0 else "real"
                }
    
    # Add last phrase
    if current_phrase:
        current_phrase["text"] = " ".join(current_phrase["tokens"])
        phrases.append(current_phrase)
    
    # Sort by absolute importance
    phrases.sort(key=lambda p: abs(p["importance"]), reverse=True)
    
    return phrases


def _find_phrase_position(text: str, phrase: str) -> Tuple[int, int]:
    """
    Find character position of phrase in text
    
    Args:
        text: Original text
        phrase: Phrase to find
    
    Returns:
        (start_pos, end_pos) or (-1, -1) if not found
    """
    # Try exact match first
    start = text.lower().find(phrase.lower())
    if start != -1:
        return (start, start + len(phrase))
    
    # Try fuzzy match (handle tokenization differences)
    words = phrase.split()
    for word in words:
        start = text.lower().find(word.lower())
        if start != -1:
            return (start, start + len(word))
    
    return (-1, -1)


def _generate_explanation(phrase: str, importance: float, direction: str) -> str:
    """Generate human-readable explanation for highlight"""
    strength = "strongly" if abs(importance) > 0.3 else "moderately"
    
    if direction == "fake":
        return f"This phrase {strength} indicates potential misinformation"
    else:
        return f"This phrase {strength} supports the claim's credibility"


def get_highlights_with_shap(
    text: str,
    model,
    vectorizer=None,
    model_type: str = "auto",
    timeout_ms: int = 500
) -> Tuple[List[dict], str]:
    """
    Get highlights using SHAP if available, fallback to heuristic
    
    Args:
        text: Input text
        model: ML model
        vectorizer: TF-IDF vectorizer (for tfidf models)
        model_type: "tfidf", "transformer", or "auto"
        timeout_ms: SHAP computation timeout in milliseconds
    
    Returns:
        (highlights, explanation_type) where explanation_type is "shap" or "heuristic"
    """
    start_time = time.time()
    
    # Try SHAP explanation
    try:
        from .shap_explainer import explain_prediction
        
        shap_values = explain_prediction(
            text, model, vectorizer, model_type, num_samples=100
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        if shap_values and elapsed_ms < timeout_ms:
            highlights = generate_shap_highlights(text, shap_values)
            if highlights:
                logger.info(f"SHAP highlights generated in {elapsed_ms:.0f}ms")
                return (highlights, "shap")
            else:
                logger.debug("SHAP returned no highlights, using fallback")
        else:
            logger.warning(f"SHAP timeout ({elapsed_ms:.0f}ms > {timeout_ms}ms), using fallback")
    
    except ImportError:
        logger.debug("SHAP not available, using heuristic highlighting")
    except Exception as e:
        logger.warning(f"SHAP explanation failed: {e}, using fallback")
    
    # Fallback to heuristic highlighting
    highlights = get_highlights(text)
    return (highlights, "heuristic")


def get_highlights(text: str) -> List[dict]:
    """
    Returns list of highlighted phrases with scores and reasons.
    Each item: {"phrase": str, "score": float, "reason": str}
    
    This is the heuristic fallback method.
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
