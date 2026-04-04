"""
Dynamic Source Credibility Scorer

Combines a static trust baseline with learned adjustments from:
  1. Stance consistency — sources that consistently support real claims get higher scores
  2. User feedback — when users correct a verdict, sources cited in that prediction lose trust

Trust score: 0.0 (untrustworthy) → 1.0 (highly credible)
Stored in-memory with DB persistence via ClaimRecord stance data.
"""

import re
import logging
from urllib.parse import urlparse
from typing import Dict

logger = logging.getLogger(__name__)

# ── Static baseline trust scores ─────────────────────────────
_STATIC_TRUST: Dict[str, float] = {
    # Tier 1 — wire services / public broadcasters
    "reuters.com":          0.95,
    "apnews.com":           0.95,
    "bbc.com":              0.93,
    "bbc.co.uk":            0.93,
    "npr.org":              0.92,
    "pbs.org":              0.90,
    # Tier 1 — major newspapers
    "nytimes.com":          0.90,
    "washingtonpost.com":   0.89,
    "theguardian.com":      0.88,
    "wsj.com":              0.88,
    "ft.com":               0.88,
    "bloomberg.com":        0.87,
    "economist.com":        0.87,
    # Tier 1 — science / health
    "nature.com":           0.95,
    "science.org":          0.95,
    "who.int":              0.95,
    "cdc.gov":              0.95,
    "nih.gov":              0.95,
    # Tier 1 — fact-checkers
    "snopes.com":           0.92,
    "factcheck.org":        0.92,
    "politifact.com":       0.91,
    "fullfact.org":         0.91,
    # Tier 2 — international
    "aljazeera.com":        0.82,
    "dw.com":               0.85,
    "france24.com":         0.84,
    "abc.net.au":           0.85,
    "cbc.ca":               0.85,
    # Tier 2 — Indian
    "thehindu.com":         0.83,
    "ndtv.com":             0.78,
    "hindustantimes.com":   0.76,
    "indiatoday.in":        0.74,
    "timesofindia.com":     0.72,
    # Tier 3 — general news
    "nbcnews.com":          0.80,
    "abcnews.go.com":       0.80,
    "cbsnews.com":          0.80,
    "foxnews.com":          0.60,
    "dailymail.co.uk":      0.45,
    "nypost.com":           0.55,
    "breitbart.com":        0.30,
    "infowars.com":         0.10,
    "naturalnews.com":      0.10,
}

# In-memory learned adjustments: domain → cumulative delta
_learned: Dict[str, float] = {}
_counts:  Dict[str, int]   = {}


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "").lower()
    except Exception:
        return ""


def get_trust_score(url: str) -> float:
    """Return trust score 0–1 for a given URL."""
    domain = _extract_domain(url)
    if not domain:
        return 0.5
    base = _STATIC_TRUST.get(domain, 0.5)
    # Apply learned adjustment (capped at ±0.2)
    delta = _learned.get(domain, 0.0)
    return round(min(1.0, max(0.0, base + delta)), 3)


def get_trust_label(url: str) -> str:
    score = get_trust_score(url)
    if score >= 0.85: return "HIGH"
    if score >= 0.65: return "MED"
    return "LOW"


def update_from_stance(domain: str, stance: str, verdict_correct: bool):
    """
    Update learned trust based on stance consistency.
    If source said 'support' and verdict was real → trust up.
    If source said 'support' and verdict was fake → trust down.
    """
    if not domain:
        return
    delta = 0.0
    if stance == "support" and verdict_correct:
        delta = +0.01
    elif stance == "support" and not verdict_correct:
        delta = -0.02
    elif stance == "contradict" and not verdict_correct:
        delta = +0.01
    elif stance == "contradict" and verdict_correct:
        delta = -0.01

    _learned[domain] = _learned.get(domain, 0.0) + delta
    _counts[domain]  = _counts.get(domain, 0) + 1
    # Cap adjustment
    _learned[domain] = max(-0.20, min(0.20, _learned[domain]))


def get_all_scores() -> list:
    """Return all domains with their current trust scores (for dashboard)."""
    all_domains = set(_STATIC_TRUST.keys()) | set(_learned.keys())
    result = []
    for domain in sorted(all_domains):
        result.append({
            "domain":   domain,
            "score":    get_trust_score(f"https://{domain}"),
            "base":     _STATIC_TRUST.get(domain, 0.5),
            "learned":  round(_learned.get(domain, 0.0), 4),
            "count":    _counts.get(domain, 0),
        })
    return sorted(result, key=lambda x: -x["score"])
