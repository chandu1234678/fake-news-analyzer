"""
Explainability Engine

Generates structured, human-readable explanations for why a claim
was rated fake/real/uncertain. Goes beyond the LLM explanation to
provide signal-by-signal breakdowns that users can understand and trust.

Output format:
{
  "summary": "This claim is likely fake because...",
  "signals": [
    {"signal": "ML Model", "score": 0.87, "weight": "HIGH", "interpretation": "..."},
    {"signal": "AI Reasoning", "score": 0.82, "weight": "HIGH", "interpretation": "..."},
    ...
  ],
  "key_factors": ["sensational language", "unverified entity", "contradicted by Reuters"],
  "confidence_explanation": "High confidence because 3 independent signals agree",
  "uncertainty_reason": null | "AI and evidence disagree"
}
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _score_to_label(score: float) -> str:
    if score >= 0.75: return "strongly fake"
    if score >= 0.55: return "likely fake"
    if score <= 0.25: return "strongly real"
    if score <= 0.45: return "likely real"
    return "uncertain"


def _weight_label(score: float) -> str:
    diff = abs(score - 0.5)
    if diff >= 0.35: return "HIGH"
    if diff >= 0.20: return "MEDIUM"
    return "LOW"


def build_explanation(
    verdict: str,
    confidence: float,
    ml_score: float,
    ai_score: float,
    evidence_score: Optional[float],
    manipulation_score: float,
    manipulation_signals: list,
    entity_verifications: list,
    entity_risk: float,
    evidence_articles: list,
    previously_debunked: bool,
    debunk_sources: list,
    image_mismatch_risk: float,
    was_translated: bool,
    detected_language: Optional[str],
) -> dict:
    """
    Build a structured explainability report for the verdict.
    """
    signals = []
    key_factors = []

    # ── ML signal ─────────────────────────────────────────────
    ml_interp = (
        f"The text pattern analysis rates this as {_score_to_label(ml_score)} "
        f"({round(ml_score * 100)}% fake probability). "
    )
    if ml_score > 0.7:
        ml_interp += "The writing style, vocabulary, and structure match known fake news patterns."
    elif ml_score < 0.3:
        ml_interp += "The writing style matches credible news reporting."
    else:
        ml_interp += "The writing style is ambiguous."
    signals.append({
        "signal": "Text Pattern Analysis (ML)",
        "score": round(ml_score, 3),
        "weight": _weight_label(ml_score),
        "interpretation": ml_interp,
    })

    # ── AI reasoning signal ───────────────────────────────────
    ai_interp = (
        f"AI fact-checking rates this as {_score_to_label(ai_score)} "
        f"({round(ai_score * 100)}% fake probability). "
    )
    if ai_score > 0.7:
        ai_interp += "The AI identified factual inconsistencies or unverifiable claims."
    elif ai_score < 0.3:
        ai_interp += "The AI found the claim consistent with known facts."
    else:
        ai_interp += "The AI could not reach a definitive conclusion."
    signals.append({
        "signal": "AI Fact-Checking",
        "score": round(ai_score, 3),
        "weight": _weight_label(ai_score),
        "interpretation": ai_interp,
    })

    # ── Evidence signal ───────────────────────────────────────
    if evidence_score is not None:
        ev_interp = f"News evidence score: {round(evidence_score * 100)}% real. "
        supporting = [a for a in evidence_articles if a.get("stance") == "support"]
        contradicting = [a for a in evidence_articles if a.get("stance") == "contradict"]
        if contradicting:
            sources = ", ".join(a.get("source", "") for a in contradicting[:2])
            ev_interp += f"Contradicted by: {sources}."
            key_factors.append(f"contradicted by {sources}")
        elif supporting:
            sources = ", ".join(a.get("source", "") for a in supporting[:2])
            ev_interp += f"Supported by: {sources}."
        else:
            ev_interp += "No clear stance from news sources."
        signals.append({
            "signal": "News Evidence",
            "score": round(1.0 - evidence_score, 3),  # convert to fake score
            "weight": _weight_label(1.0 - evidence_score),
            "interpretation": ev_interp,
        })

    # ── Manipulation signal ───────────────────────────────────
    if manipulation_score > 0.1:
        manip_interp = (
            f"Manipulation score: {round(manipulation_score * 100)}%. "
            f"Detected: {', '.join(manipulation_signals[:3])}. "
            "Note: manipulative language doesn't prove a claim is false, "
            "but is a strong indicator of misinformation."
        )
        signals.append({
            "signal": "Manipulation Detection",
            "score": round(manipulation_score, 3),
            "weight": _weight_label(manipulation_score),
            "interpretation": manip_interp,
        })
        if manipulation_score > 0.4:
            key_factors.extend(manipulation_signals[:2])

    # ── Entity verification signal ────────────────────────────
    if entity_verifications:
        unverified = [e for e in entity_verifications if not e.get("found")]
        verified   = [e for e in entity_verifications if e.get("found")]
        if unverified:
            names = ", ".join(e["entity"] for e in unverified[:2])
            signals.append({
                "signal": "Entity Verification (Wikidata)",
                "score": round(entity_risk, 3),
                "weight": _weight_label(entity_risk),
                "interpretation": f"Could not verify: {names}. These entities may be fabricated or misspelled.",
            })
            key_factors.append(f"unverified entity: {unverified[0]['entity']}")
        elif verified:
            signals.append({
                "signal": "Entity Verification (Wikidata)",
                "score": 0.1,
                "weight": "LOW",
                "interpretation": f"All named entities verified in Wikidata: {', '.join(e['entity'] for e in verified[:2])}.",
            })

    # ── Previously debunked ───────────────────────────────────
    if previously_debunked:
        signals.append({
            "signal": "Existing Fact-Checks",
            "score": 0.95,
            "weight": "HIGH",
            "interpretation": f"This claim has already been fact-checked and debunked by: {', '.join(debunk_sources)}.",
        })
        key_factors.append(f"previously debunked by {debunk_sources[0] if debunk_sources else 'fact-checkers'}")

    # ── Image mismatch ────────────────────────────────────────
    if image_mismatch_risk > 0.3:
        signals.append({
            "signal": "Image Consistency",
            "score": round(image_mismatch_risk, 3),
            "weight": _weight_label(image_mismatch_risk),
            "interpretation": "The image associated with this claim appears to be used out of context or misrepresents the claim.",
        })
        key_factors.append("image used out of context")

    # ── Translation note ──────────────────────────────────────
    if was_translated and detected_language:
        signals.append({
            "signal": "Language",
            "score": 0.5,
            "weight": "INFO",
            "interpretation": f"Claim was originally in {detected_language} and auto-translated to English for analysis.",
        })

    # ── Confidence explanation ────────────────────────────────
    high_signals = [s for s in signals if s["weight"] == "HIGH"]
    agreeing = sum(1 for s in signals[:3] if
                   (verdict == "fake" and s["score"] > 0.6) or
                   (verdict == "real" and s["score"] < 0.4))

    if confidence >= 0.85:
        conf_explanation = f"{len(high_signals)} high-confidence signals strongly agree on this verdict."
    elif confidence >= 0.70:
        conf_explanation = f"{agreeing} out of {min(3, len(signals))} primary signals agree on this verdict."
    else:
        conf_explanation = "Signals are mixed — treat this verdict with caution."

    # ── Uncertainty reason ────────────────────────────────────
    uncertainty_reason = None
    if verdict == "uncertain":
        if evidence_score is not None and abs(ai_score - (1 - evidence_score)) > 0.4:
            uncertainty_reason = "AI reasoning and news evidence strongly disagree"
        elif abs(ml_score - 0.5) < 0.15 and abs(ai_score - 0.5) < 0.15:
            uncertainty_reason = "All signals are near 50% — insufficient evidence to decide"
        else:
            uncertainty_reason = "Conflicting signals prevent a definitive verdict"

    # ── Summary ───────────────────────────────────────────────
    if verdict == "fake":
        if key_factors:
            summary = f"This claim is likely fake. Key reasons: {'; '.join(key_factors[:3])}."
        else:
            summary = f"This claim is likely fake based on {len(signals)} analysis signals."
    elif verdict == "real":
        summary = f"This claim appears to be real. {conf_explanation}"
    else:
        summary = f"This claim's authenticity is uncertain. {uncertainty_reason or 'Signals conflict.'}."

    return {
        "summary":                summary,
        "signals":                signals,
        "key_factors":            key_factors[:5],
        "confidence_explanation": conf_explanation,
        "uncertainty_reason":     uncertainty_reason,
        "signal_count":           len(signals),
    }
