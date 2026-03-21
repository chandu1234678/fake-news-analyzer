from typing import Optional


def decide(
    ml_fake: Optional[float],
    ai_fake: Optional[float],
    evidence_score: Optional[float],
):
    """
    Weighted verdict: AI 50%, News Evidence 32%, ML 18%

    ml_fake:        0–1, probability claim is FAKE (trained model)
    ai_fake:        0–1, probability claim is FAKE (LLM)
    evidence_score: 0–1, trusted news corroboration (1 = strongly real)
    """
    ml_fake = float(ml_fake) if ml_fake is not None else None
    ai_fake = float(ai_fake) if ai_fake is not None else None

    # ── Strong AI + strong evidence agreement → high confidence ──
    if ai_fake is not None and evidence_score is not None:
        if ai_fake <= 0.15 and evidence_score >= 0.5:
            conf = round(min(0.97, (1 - ai_fake) * 0.50 + evidence_score * 0.32 + (1 - (ml_fake or 0.5)) * 0.18), 2)
            return "real", conf
        if ai_fake >= 0.85 and evidence_score <= 0.2:
            conf = round(min(0.97, ai_fake * 0.50 + (1 - evidence_score) * 0.32 + (ml_fake or 0.5) * 0.18), 2)
            return "fake", conf

    # ── AI strong override (no evidence or evidence agrees) ──────
    if ai_fake is not None:
        if ai_fake <= 0.15:
            return "real", round(1 - ai_fake, 2)
        if ai_fake >= 0.88:
            # Only override if evidence doesn't strongly contradict
            if evidence_score is None or evidence_score < 0.65:
                return "fake", round(ai_fake, 2)

    # ── Evidence strong override ──────────────────────────────────
    if evidence_score is not None:
        if evidence_score >= 0.65:
            ai_part = (1 - ai_fake) * 0.50 if ai_fake is not None else 0.25
            ml_part = (1 - (ml_fake or 0.5)) * 0.18
            conf = round(min(0.97, evidence_score * 0.32 + ai_part + ml_part), 2)
            return "real", conf

    # ── Weighted blend: AI 50%, Evidence 32%, ML 18% ─────────────
    fake_score = 0.0
    total_weight = 0.0

    if ai_fake is not None:
        fake_score += ai_fake * 0.50
        total_weight += 0.50

    if evidence_score is not None:
        fake_score += (1 - evidence_score) * 0.32
        total_weight += 0.32

    if ml_fake is not None:
        fake_score += ml_fake * 0.18
        total_weight += 0.18

    if total_weight == 0:
        return "uncertain", 0.5

    normalized = fake_score / total_weight
    # Confidence = how far from 0.5 (uncertain midpoint), scaled to 0–1
    confidence = round(min(0.97, max(0.50, abs(normalized - 0.5) * 2 + 0.5)), 2)
    verdict = "fake" if normalized >= 0.5 else "real"
    return verdict, confidence
