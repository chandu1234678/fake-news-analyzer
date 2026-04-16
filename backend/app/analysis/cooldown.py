"""
Cooldown Score - Viral Misinformation Risk Assessment

Combines multiple risk factors to determine friction level:
- Fake probability (40%) - ML model confidence
- Velocity (30%) - Rapid spread detection
- Emotional intensity (15%) - Manipulation signals
- Evidence conflict (15%) - Contradictory sources

Risk Levels:
- VIRAL_PANIC (>0.80): Full-screen interstitial, 10s delay
- HIGH_CONCERN (>0.55): Friction card, 5s countdown
- CAUTION (>0.35): Warning banner
- NORMAL (≤0.35): Standard display
"""

import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Risk level thresholds
THRESHOLD_VIRAL_PANIC = 0.80
THRESHOLD_HIGH_CONCERN = 0.55
THRESHOLD_CAUTION = 0.35

# Component weights (must sum to 1.0)
WEIGHT_FAKE_PROB = 0.40
WEIGHT_VELOCITY = 0.30
WEIGHT_EMOTIONAL = 0.15
WEIGHT_EVIDENCE_CONFLICT = 0.15


def calculate_cooldown_score(
    fake_probability: float,
    velocity_score: float,
    emotional_intensity: float,
    evidence_conflict: float
) -> Tuple[float, str, Dict[str, any]]:
    """
    Calculate cooldown score using weighted geometric mean
    
    Args:
        fake_probability: ML model fake score (0-1)
        velocity_score: Normalized velocity (0-1)
        emotional_intensity: Manipulation score (0-1)
        evidence_conflict: Evidence contradiction score (0-1)
    
    Returns:
        (cooldown_score, cooldown_level, breakdown)
        
    Example:
        score, level, breakdown = calculate_cooldown_score(
            fake_probability=0.85,
            velocity_score=0.75,
            emotional_intensity=0.60,
            evidence_conflict=0.40
        )
    """
    # Clamp inputs to [0, 1]
    fake_prob = max(0.0, min(1.0, fake_probability))
    velocity = max(0.0, min(1.0, velocity_score))
    emotional = max(0.0, min(1.0, emotional_intensity))
    evidence_conf = max(0.0, min(1.0, evidence_conflict))
    
    # Weighted geometric mean
    # Formula: (x1^w1 * x2^w2 * x3^w3 * x4^w4)
    # This ensures all factors contribute multiplicatively
    cooldown_score = (
        (fake_prob ** WEIGHT_FAKE_PROB) *
        (velocity ** WEIGHT_VELOCITY) *
        (emotional ** WEIGHT_EMOTIONAL) *
        (evidence_conf ** WEIGHT_EVIDENCE_CONFLICT)
    )
    
    # Determine risk level
    if cooldown_score > THRESHOLD_VIRAL_PANIC:
        level = "VIRAL_PANIC"
        friction_type = "full_screen_interstitial"
        delay_seconds = 10
    elif cooldown_score > THRESHOLD_HIGH_CONCERN:
        level = "HIGH_CONCERN"
        friction_type = "friction_card"
        delay_seconds = 5
    elif cooldown_score > THRESHOLD_CAUTION:
        level = "CAUTION"
        friction_type = "warning_banner"
        delay_seconds = 0
    else:
        level = "NORMAL"
        friction_type = "none"
        delay_seconds = 0
    
    # Breakdown for debugging/explainability
    breakdown = {
        "cooldown_score": round(cooldown_score, 3),
        "cooldown_level": level,
        "friction_type": friction_type,
        "delay_seconds": delay_seconds,
        "components": {
            "fake_probability": {
                "value": round(fake_prob, 3),
                "weight": WEIGHT_FAKE_PROB,
                "contribution": round(fake_prob ** WEIGHT_FAKE_PROB, 3)
            },
            "velocity": {
                "value": round(velocity, 3),
                "weight": WEIGHT_VELOCITY,
                "contribution": round(velocity ** WEIGHT_VELOCITY, 3)
            },
            "emotional_intensity": {
                "value": round(emotional, 3),
                "weight": WEIGHT_EMOTIONAL,
                "contribution": round(emotional ** WEIGHT_EMOTIONAL, 3)
            },
            "evidence_conflict": {
                "value": round(evidence_conf, 3),
                "weight": WEIGHT_EVIDENCE_CONFLICT,
                "contribution": round(evidence_conf ** WEIGHT_EVIDENCE_CONFLICT, 3)
            }
        },
        "thresholds": {
            "VIRAL_PANIC": THRESHOLD_VIRAL_PANIC,
            "HIGH_CONCERN": THRESHOLD_HIGH_CONCERN,
            "CAUTION": THRESHOLD_CAUTION
        }
    }
    
    # Log high-risk detections
    if level in ("VIRAL_PANIC", "HIGH_CONCERN"):
        logger.warning(
            f"High-risk content detected: {level} "
            f"(score={cooldown_score:.3f}, fake={fake_prob:.2f}, "
            f"velocity={velocity:.2f}, emotional={emotional:.2f})"
        )
    
    return cooldown_score, level, breakdown


def get_evidence_conflict_score(evidence_score: Optional[float], 
                                stance_summary: Dict[str, int]) -> float:
    """
    Calculate evidence conflict score from evidence analysis
    
    Args:
        evidence_score: Overall evidence score (0-1, higher = more support)
        stance_summary: {"support": N, "contradict": M, "neutral": K}
    
    Returns:
        Conflict score (0-1, higher = more conflict)
    """
    # If no evidence, assume moderate conflict
    if evidence_score is None:
        return 0.5
    
    # Invert evidence score (low evidence = high conflict)
    base_conflict = 1.0 - evidence_score
    
    # Amplify if we have explicit contradictions
    contradict = stance_summary.get("contradict", 0)
    support = stance_summary.get("support", 0)
    total = contradict + support
    
    if total > 0:
        contradiction_ratio = contradict / total
        # Boost conflict if contradictions dominate
        base_conflict = min(1.0, base_conflict + contradiction_ratio * 0.2)
    
    return round(base_conflict, 3)


def get_emotional_intensity_score(manipulation_score: float,
                                  manipulation_signals: list) -> float:
    """
    Calculate emotional intensity from manipulation analysis
    
    Args:
        manipulation_score: Base manipulation score (0-1)
        manipulation_signals: List of detected signals
    
    Returns:
        Emotional intensity (0-1)
    """
    # Base score from manipulation detection
    intensity = manipulation_score
    
    # Amplify if multiple emotional signals detected
    emotional_signals = [
        s for s in manipulation_signals 
        if "emotional" in s.lower() or "sensational" in s.lower()
    ]
    
    if len(emotional_signals) > 1:
        intensity = min(1.0, intensity + 0.15)
    
    return round(intensity, 3)


# Example usage and testing
if __name__ == "__main__":
    print("Testing Cooldown Score Calculation")
    print("=" * 60)
    
    # Test case 1: Viral fake news
    print("\nTest 1: Viral Fake News")
    score, level, breakdown = calculate_cooldown_score(
        fake_probability=0.92,
        velocity_score=0.85,
        emotional_intensity=0.70,
        evidence_conflict=0.65
    )
    print(f"Score: {score:.3f}")
    print(f"Level: {level}")
    print(f"Friction: {breakdown['friction_type']} ({breakdown['delay_seconds']}s)")
    
    # Test case 2: Trending but uncertain
    print("\nTest 2: Trending but Uncertain")
    score, level, breakdown = calculate_cooldown_score(
        fake_probability=0.65,
        velocity_score=0.70,
        emotional_intensity=0.45,
        evidence_conflict=0.50
    )
    print(f"Score: {score:.3f}")
    print(f"Level: {level}")
    print(f"Friction: {breakdown['friction_type']} ({breakdown['delay_seconds']}s)")
    
    # Test case 3: Low risk
    print("\nTest 3: Low Risk")
    score, level, breakdown = calculate_cooldown_score(
        fake_probability=0.25,
        velocity_score=0.15,
        emotional_intensity=0.10,
        evidence_conflict=0.20
    )
    print(f"Score: {score:.3f}")
    print(f"Level: {level}")
    print(f"Friction: {breakdown['friction_type']} ({breakdown['delay_seconds']}s)")
    
    # Test case 4: High fake but low velocity
    print("\nTest 4: High Fake but Low Velocity")
    score, level, breakdown = calculate_cooldown_score(
        fake_probability=0.88,
        velocity_score=0.20,
        emotional_intensity=0.35,
        evidence_conflict=0.40
    )
    print(f"Score: {score:.3f}")
    print(f"Level: {level}")
    print(f"Friction: {breakdown['friction_type']} ({breakdown['delay_seconds']}s)")
