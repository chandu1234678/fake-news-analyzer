def decide(ml_fake: float | None, ai_fake: float | None, evidence_score: float | None):
    """
    Decide verdict based on ML, AI, and evidence signals.
    All values represent probability that the claim is FAKE (0–1).
    """

    ml_fake = float(ml_fake or 0.0)
    ai_fake = float(ai_fake or 0.0)

    # --- AI STRONG REAL OVERRIDE ---
    if ai_fake <= 0.2:
        return "real", round(1 - ai_fake, 2)

    # --- AI STRONG FAKE ---
    if ai_fake >= 0.85:
        return "fake", round(ai_fake, 2)

    # --- ML STRONG FAKE (ONLY IF AI IS UNCERTAIN) ---
    if ml_fake >= 0.75 and ai_fake > 0.4:
        return "fake", round(ml_fake, 2)

    # --- EVIDENCE OVERRIDE ---
    if evidence_score is not None:
        if evidence_score >= 0.6:
            return "real", round(evidence_score, 2)
        else:
            return "fake", round(1 - evidence_score, 2)

    # --- FALLBACK ---
    confidence = 1 - max(ml_fake, ai_fake)
    verdict = "real" if confidence > 0.5 else "fake"
    return verdict, round(confidence, 2)
