"""
Cross-Platform Claim Tracker

Tracks the same claim spreading across platforms by:
1. Checking if the claim hash exists in our ClaimRecord DB (already done)
2. Searching for the claim on public fact-check APIs
3. Checking Google Fact Check Tools API (free, no key needed for basic use)
4. Returning spread indicators and fact-check verdicts from other organizations

APIs used:
- Google Fact Check Tools API (free, 1000 req/day)
  https://developers.google.com/fact-check/tools/api
- ClaimBuster API (free tier)
  https://idir.uta.edu/claimbuster/
"""
import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

GOOGLE_FACTCHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
GOOGLE_API_KEY       = os.getenv("GOOGLE_FACTCHECK_API_KEY")  # optional, higher quota

_session = requests.Session()
_session.headers.update({"User-Agent": "FactCheckerAI/2.0"})


def search_fact_checks(claim_text: str) -> list:
    """
    Search Google Fact Check Tools for existing fact-checks on this claim.
    Returns list of fact-check results from Snopes, PolitiFact, AFP, etc.

    Free without API key (lower quota). Set GOOGLE_FACTCHECK_API_KEY for 1000/day.
    """
    params = {
        "query":        claim_text[:200],
        "languageCode": "en",
        "pageSize":     5,
    }
    if GOOGLE_API_KEY:
        params["key"] = GOOGLE_API_KEY

    try:
        r = _session.get(GOOGLE_FACTCHECK_URL, params=params, timeout=8)
        if r.status_code != 200:
            logger.debug("Google Fact Check API returned %s", r.status_code)
            return []

        claims = r.json().get("claims", [])
        results = []
        for c in claims:
            review = c.get("claimReview", [{}])[0]
            results.append({
                "claim":       c.get("text", ""),
                "claimant":    c.get("claimant", ""),
                "date":        c.get("claimDate", ""),
                "reviewer":    review.get("publisher", {}).get("name", ""),
                "url":         review.get("url", ""),
                "rating":      review.get("textualRating", ""),
                "title":       review.get("title", ""),
            })
        return results
    except Exception as e:
        logger.debug("Google Fact Check search failed: %s", e)
        return []


def get_spread_indicators(claim_text: str, db=None) -> dict:
    """
    Check how widely a claim is spreading and if it's been fact-checked.

    Returns:
        {
          "fact_checks": list of existing fact-check results,
          "fact_check_count": int,
          "previously_debunked": bool,
          "debunk_sources": list of source names,
          "spread_risk": float 0-1
        }
    """
    fact_checks = search_fact_checks(claim_text)

    # Check if any existing fact-check rates it as false
    false_ratings = {"false", "fake", "incorrect", "misleading", "pants on fire",
                     "mostly false", "four pinocchios", "debunked", "fabricated"}
    debunked = []
    for fc in fact_checks:
        rating = fc.get("rating", "").lower()
        if any(f in rating for f in false_ratings):
            debunked.append(fc.get("reviewer", "Unknown"))

    previously_debunked = len(debunked) > 0

    # Spread risk: higher if already debunked by multiple orgs
    spread_risk = min(1.0, len(fact_checks) * 0.15 + len(debunked) * 0.25)

    # Check DB for how many times this claim has been verified
    db_count = 0
    if db:
        try:
            import hashlib
            from app.models import ClaimRecord
            claim_hash = hashlib.sha256(claim_text.lower().strip().encode()).hexdigest()
            db_count = db.query(ClaimRecord).filter(
                ClaimRecord.claim_hash == claim_hash
            ).count()
        except Exception:
            pass

    return {
        "fact_checks":          fact_checks[:3],
        "fact_check_count":     len(fact_checks),
        "previously_debunked":  previously_debunked,
        "debunk_sources":       debunked,
        "db_verification_count": db_count,
        "spread_risk":          round(spread_risk, 2),
    }
