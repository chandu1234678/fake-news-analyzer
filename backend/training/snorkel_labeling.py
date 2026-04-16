"""
Self-Labeling Pipeline using Snorkel

Generates weak labels for unlabeled data using multiple heuristic labeling functions.
Uses Snorkel's label model to denoise and combine weak labels into probabilistic labels.

Labeling Functions:
1. Source Credibility - Trust score from credibility.py
2. Manipulation Detection - Manipulation score from manipulation.py
3. Evidence Consistency - Evidence score from evidence.py
4. Model Prediction - Existing ML model predictions
5. Keyword Patterns - Sensational/clickbait language
6. URL Patterns - Known fake news domains

For production: Run this weekly to generate 10k+ auto-labeled samples
"""

import sys
import os
import logging
import pandas as pd
import numpy as np
from typing import List, Tuple, Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)

# Label constants
ABSTAIN = -1
FAKE = 0
REAL = 1

# Lazy imports for Snorkel
_snorkel = None


def _get_snorkel():
    """Lazy load Snorkel"""
    global _snorkel
    if _snorkel is None:
        try:
            import snorkel
            from snorkel.labeling import labeling_function, PandasLFApplier, LFAnalysis
            from snorkel.labeling.model import LabelModel
            _snorkel = {
                'labeling_function': labeling_function,
                'PandasLFApplier': PandasLFApplier,
                'LFAnalysis': LFAnalysis,
                'LabelModel': LabelModel
            }
            logger.info("Loaded Snorkel framework")
        except ImportError:
            logger.warning("Snorkel not installed. Run: pip install snorkel")
            _snorkel = None
    return _snorkel


# ── Labeling Functions ────────────────────────────────────────

def lf_source_credibility(row):
    """
    Label based on source credibility score
    
    High trust (>0.8) → REAL
    Low trust (<0.3) → FAKE
    Otherwise → ABSTAIN
    """
    try:
        from app.analysis.credibility import get_trust_score
        
        url = row.get('url', '')
        if not url:
            return ABSTAIN
        
        trust_score = get_trust_score(url)
        
        if trust_score > 0.8:
            return REAL
        elif trust_score < 0.3:
            return FAKE
        return ABSTAIN
    except:
        return ABSTAIN


def lf_manipulation_score(row):
    """
    Label based on manipulation detection
    
    High manipulation (>0.6) → FAKE
    Low manipulation (<0.2) → REAL
    Otherwise → ABSTAIN
    """
    try:
        from app.analysis.manipulation import analyze_manipulation
        
        text = row.get('text', '')
        if not text or len(text) < 50:
            return ABSTAIN
        
        manip_score, _ = analyze_manipulation(text)
        
        if manip_score > 0.6:
            return FAKE
        elif manip_score < 0.2:
            return REAL
        return ABSTAIN
    except:
        return ABSTAIN


def lf_evidence_consistency(row):
    """
    Label based on evidence consistency
    
    High evidence (>0.7) → REAL
    Low evidence (<0.3) → FAKE
    Otherwise → ABSTAIN
    
    Note: This is expensive (API calls), use sparingly
    """
    try:
        from app.analysis.evidence import fetch_evidence
        
        text = row.get('text', '')
        if not text or len(text) < 50:
            return ABSTAIN
        
        # Only run on sample (too expensive for all)
        if np.random.random() > 0.1:  # 10% sample
            return ABSTAIN
        
        evidence_score, _, _ = fetch_evidence(text[:200])
        
        if evidence_score is None:
            return ABSTAIN
        
        if evidence_score > 0.7:
            return REAL
        elif evidence_score < 0.3:
            return FAKE
        return ABSTAIN
    except:
        return ABSTAIN


def lf_model_prediction(row):
    """
    Label based on existing ML model prediction
    
    High fake score (>0.8) → FAKE
    Low fake score (<0.2) → REAL
    Otherwise → ABSTAIN
    """
    try:
        from app.analysis.ml import run_ml_analysis
        
        text = row.get('text', '')
        if not text or len(text) < 50:
            return ABSTAIN
        
        result = run_ml_analysis(text)
        fake_score = result.get('fake', 0.5)
        
        if fake_score > 0.8:
            return FAKE
        elif fake_score < 0.2:
            return REAL
        return ABSTAIN
    except:
        return ABSTAIN


def lf_sensational_keywords(row):
    """
    Label based on sensational keyword patterns
    
    Many sensational keywords → FAKE
    No sensational keywords → REAL
    """
    text = row.get('text', '').lower()
    if not text:
        return ABSTAIN
    
    sensational_keywords = [
        'shocking', 'breaking', 'urgent', 'exposed', 'leaked',
        'scandal', 'bombshell', 'you won\'t believe', 'must see',
        'they don\'t want you to know', 'wake up', 'share before deleted'
    ]
    
    count = sum(1 for keyword in sensational_keywords if keyword in text)
    
    if count >= 3:
        return FAKE
    elif count == 0 and len(text) > 100:
        return REAL
    return ABSTAIN


def lf_fake_news_domains(row):
    """
    Label based on known fake news domains
    
    Known fake domain → FAKE
    Known trusted domain → REAL
    """
    url = row.get('url', '').lower()
    if not url:
        return ABSTAIN
    
    # Known fake news domains (sample list)
    fake_domains = [
        'fakenews.com', 'clickbait.net', 'conspiracy.org',
        'hoax.info', 'satire.news', 'parody.com'
    ]
    
    # Known trusted domains
    trusted_domains = [
        'reuters.com', 'apnews.com', 'bbc.com', 'bbc.co.uk',
        'nytimes.com', 'washingtonpost.com', 'theguardian.com',
        'npr.org', 'pbs.org', 'cnn.com', 'bloomberg.com'
    ]
    
    for domain in fake_domains:
        if domain in url:
            return FAKE
    
    for domain in trusted_domains:
        if domain in url:
            return REAL
    
    return ABSTAIN


def lf_all_caps_title(row):
    """
    Label based on ALL CAPS title (clickbait indicator)
    
    ALL CAPS title → FAKE
    """
    title = row.get('title', '')
    if not title or len(title) < 10:
        return ABSTAIN
    
    # Check if >70% of letters are uppercase
    letters = [c for c in title if c.isalpha()]
    if not letters:
        return ABSTAIN
    
    caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    
    if caps_ratio > 0.7:
        return FAKE
    return ABSTAIN


def lf_short_article(row):
    """
    Label based on article length
    
    Very short articles (<100 chars) are often low-quality
    """
    text = row.get('text', '')
    if not text:
        return ABSTAIN
    
    if len(text) < 100:
        return FAKE
    elif len(text) > 1000:
        return REAL
    return ABSTAIN


# ── Snorkel Pipeline ──────────────────────────────────────────

def create_labeling_functions():
    """
    Create list of labeling functions for Snorkel
    
    Returns:
        List of labeling functions
    """
    snorkel = _get_snorkel()
    if not snorkel:
        return []
    
    labeling_function = snorkel['labeling_function']
    
    # Wrap functions with Snorkel decorator
    lfs = [
        labeling_function(name="source_credibility")(lf_source_credibility),
        labeling_function(name="manipulation_score")(lf_manipulation_score),
        labeling_function(name="sensational_keywords")(lf_sensational_keywords),
        labeling_function(name="fake_news_domains")(lf_fake_news_domains),
        labeling_function(name="all_caps_title")(lf_all_caps_title),
        labeling_function(name="short_article")(lf_short_article),
        # Expensive LFs (use sparingly)
        # labeling_function(name="evidence_consistency")(lf_evidence_consistency),
        # labeling_function(name="model_prediction")(lf_model_prediction),
    ]
    
    return lfs


def apply_labeling_functions(df: pd.DataFrame, lfs: List) -> np.ndarray:
    """
    Apply labeling functions to dataframe
    
    Args:
        df: DataFrame with columns: text, title, url
        lfs: List of labeling functions
        
    Returns:
        Label matrix (n_samples x n_lfs)
    """
    snorkel = _get_snorkel()
    if not snorkel:
        raise ImportError("Snorkel not installed")
    
    PandasLFApplier = snorkel['PandasLFApplier']
    
    applier = PandasLFApplier(lfs=lfs)
    L_train = applier.apply(df=df)
    
    return L_train


def analyze_label_matrix(L_train: np.ndarray, lfs: List):
    """
    Analyze label matrix statistics
    
    Args:
        L_train: Label matrix
        lfs: List of labeling functions
    """
    snorkel = _get_snorkel()
    if not snorkel:
        return
    
    LFAnalysis = snorkel['LFAnalysis']
    
    analysis = LFAnalysis(L=L_train, lfs=lfs).lf_summary()
    print("\nLabeling Function Analysis:")
    print(analysis)
    
    return analysis


def train_label_model(L_train: np.ndarray, n_epochs: int = 500) -> 'LabelModel':
    """
    Train Snorkel label model to denoise weak labels
    
    Args:
        L_train: Label matrix
        n_epochs: Number of training epochs
        
    Returns:
        Trained label model
    """
    snorkel = _get_snorkel()
    if not snorkel:
        raise ImportError("Snorkel not installed")
    
    LabelModel = snorkel['LabelModel']
    
    label_model = LabelModel(cardinality=2, verbose=True)
    label_model.fit(L_train=L_train, n_epochs=n_epochs, log_freq=100)
    
    return label_model


def get_probabilistic_labels(label_model, L_train: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Get probabilistic labels from trained model
    
    Args:
        label_model: Trained label model
        L_train: Label matrix
        
    Returns:
        (predicted_labels, predicted_probabilities)
    """
    # Get probabilistic labels
    probs = label_model.predict_proba(L=L_train)
    
    # Get hard labels
    preds = label_model.predict(L=L_train)
    
    return preds, probs


def filter_high_confidence_labels(preds: np.ndarray, probs: np.ndarray,
                                  threshold: float = 0.8) -> Tuple[np.ndarray, np.ndarray]:
    """
    Filter to keep only high-confidence predictions
    
    Args:
        preds: Predicted labels
        probs: Predicted probabilities
        threshold: Confidence threshold (0-1)
        
    Returns:
        (filtered_indices, filtered_labels)
    """
    # Get max probability for each sample
    max_probs = np.max(probs, axis=1)
    
    # Filter by confidence threshold
    high_conf_mask = max_probs >= threshold
    high_conf_indices = np.where(high_conf_mask)[0]
    high_conf_labels = preds[high_conf_mask]
    
    print(f"\nHigh-confidence samples: {len(high_conf_indices)} / {len(preds)} ({len(high_conf_indices)/len(preds)*100:.1f}%)")
    print(f"  FAKE: {np.sum(high_conf_labels == FAKE)}")
    print(f"  REAL: {np.sum(high_conf_labels == REAL)}")
    
    return high_conf_indices, high_conf_labels


# ── Main Pipeline ─────────────────────────────────────────────

def run_self_labeling_pipeline(input_csv: str, output_csv: str,
                               confidence_threshold: float = 0.8):
    """
    Run complete self-labeling pipeline
    
    Args:
        input_csv: Path to unlabeled data CSV (columns: text, title, url)
        output_csv: Path to save auto-labeled data
        confidence_threshold: Minimum confidence for labels (0-1)
    """
    print("="*70)
    print("  SELF-LABELING PIPELINE (Snorkel)")
    print("="*70)
    
    # Check Snorkel installation
    if not _get_snorkel():
        print("\n❌ Snorkel not installed")
        print("Install with: pip install snorkel")
        return
    
    # Load data
    print(f"\n1. Loading data from {input_csv}...")
    df = pd.read_csv(input_csv)
    print(f"   Loaded {len(df)} samples")
    
    # Create labeling functions
    print("\n2. Creating labeling functions...")
    lfs = create_labeling_functions()
    print(f"   Created {len(lfs)} labeling functions")
    
    # Apply labeling functions
    print("\n3. Applying labeling functions...")
    L_train = apply_labeling_functions(df, lfs)
    print(f"   Generated label matrix: {L_train.shape}")
    
    # Analyze labels
    print("\n4. Analyzing label matrix...")
    analyze_label_matrix(L_train, lfs)
    
    # Train label model
    print("\n5. Training label model...")
    label_model = train_label_model(L_train, n_epochs=500)
    
    # Get probabilistic labels
    print("\n6. Generating probabilistic labels...")
    preds, probs = get_probabilistic_labels(label_model, L_train)
    
    # Filter high-confidence labels
    print(f"\n7. Filtering by confidence threshold ({confidence_threshold})...")
    high_conf_indices, high_conf_labels = filter_high_confidence_labels(
        preds, probs, threshold=confidence_threshold
    )
    
    # Save auto-labeled data
    print(f"\n8. Saving auto-labeled data to {output_csv}...")
    df_labeled = df.iloc[high_conf_indices].copy()
    df_labeled['label'] = high_conf_labels
    df_labeled['confidence'] = np.max(probs[high_conf_indices], axis=1)
    df_labeled.to_csv(output_csv, index=False)
    print(f"   Saved {len(df_labeled)} high-confidence samples")
    
    print("\n" + "="*70)
    print("  ✅ Self-labeling pipeline complete!")
    print("="*70)
    
    return df_labeled


# Example usage
if __name__ == "__main__":
    print("\nSelf-Labeling Pipeline with Snorkel")
    print("="*70)
    print("\nThis pipeline generates weak labels for unlabeled data using")
    print("multiple heuristic labeling functions, then uses Snorkel's label")
    print("model to denoise and combine them into probabilistic labels.")
    print("\nRequirements:")
    print("  - pip install snorkel")
    print("  - Input CSV with columns: text, title, url")
    print("\nExample:")
    print("  python snorkel_labeling.py")
    print("\nNote: For production, run this weekly on new unlabeled articles")
    print("to generate 10k+ auto-labeled samples for continuous learning.")
    print("="*70)
    
    # Check if Snorkel is installed
    if not _get_snorkel():
        print("\n❌ Snorkel not installed")
        print("Install with: pip install snorkel")
    else:
        print("\n✅ Snorkel is installed and ready")
        print("\nTo run the pipeline:")
        print("  1. Prepare unlabeled data CSV (text, title, url columns)")
        print("  2. Call: run_self_labeling_pipeline('input.csv', 'output.csv')")
