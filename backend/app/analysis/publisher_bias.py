"""
Publisher Bias Database

Static bias ratings for 100+ news sources based on AllSides and
Media Bias/Fact Check data. Used to weight evidence and flag
politically motivated reporting.

Bias labels: LEFT, LEFT-CENTER, CENTER, RIGHT-CENTER, RIGHT, UNKNOWN
"""
from urllib.parse import urlparse
from typing import Dict

# Source: AllSides Media Bias Ratings + MBFC
# https://www.allsides.com/media-bias/media-bias-ratings
_BIAS_DB: Dict[str, str] = {
    # CENTER / LEAST BIASED
    "reuters.com":          "CENTER",
    "apnews.com":           "CENTER",
    "bbc.com":              "CENTER",
    "bbc.co.uk":            "CENTER",
    "pbs.org":              "CENTER",
    "npr.org":              "LEFT-CENTER",
    "csmonitor.com":        "CENTER",
    "thehill.com":          "CENTER",
    "axios.com":            "CENTER",
    "bloomberg.com":        "CENTER",
    "economist.com":        "CENTER",
    "ft.com":               "CENTER",
    "nature.com":           "CENTER",
    "science.org":          "CENTER",
    "who.int":              "CENTER",
    "cdc.gov":              "CENTER",
    "nih.gov":              "CENTER",
    "snopes.com":           "CENTER",
    "factcheck.org":        "CENTER",
    "politifact.com":       "CENTER",
    "fullfact.org":         "CENTER",
    # LEFT-CENTER
    "nytimes.com":          "LEFT-CENTER",
    "washingtonpost.com":   "LEFT-CENTER",
    "theguardian.com":      "LEFT-CENTER",
    "nbcnews.com":          "LEFT-CENTER",
    "abcnews.go.com":       "LEFT-CENTER",
    "cbsnews.com":          "LEFT-CENTER",
    "cnn.com":              "LEFT-CENTER",
    "msnbc.com":            "LEFT",
    "vox.com":              "LEFT",
    "huffpost.com":         "LEFT",
    "slate.com":            "LEFT",
    "motherjones.com":      "LEFT",
    "thenation.com":        "LEFT",
    "jacobin.com":          "LEFT",
    # RIGHT-CENTER
    "wsj.com":              "RIGHT-CENTER",
    "usatoday.com":         "CENTER",
    "nypost.com":           "RIGHT",
    "foxnews.com":          "RIGHT",
    "dailywire.com":        "RIGHT",
    "nationalreview.com":   "RIGHT",
    "washingtonexaminer.com": "RIGHT",
    "breitbart.com":        "RIGHT",
    "dailymail.co.uk":      "RIGHT-CENTER",
    "thesun.co.uk":         "RIGHT",
    "telegraph.co.uk":      "RIGHT-CENTER",
    "spectator.co.uk":      "RIGHT",
    # EXTREME / UNRELIABLE
    "infowars.com":         "EXTREME-RIGHT",
    "naturalnews.com":      "EXTREME-RIGHT",
    "zerohedge.com":        "RIGHT",
    "thegatewaypundit.com": "EXTREME-RIGHT",
    "occupydemocrats.com":  "EXTREME-LEFT",
    "addictinginfo.com":    "EXTREME-LEFT",
    # INTERNATIONAL
    "aljazeera.com":        "CENTER",
    "dw.com":               "CENTER",
    "france24.com":         "CENTER",
    "abc.net.au":           "CENTER",
    "cbc.ca":               "LEFT-CENTER",
    "thehindu.com":         "LEFT-CENTER",
    "ndtv.com":             "CENTER",
    "hindustantimes.com":   "CENTER",
    "indiatoday.in":        "CENTER",
    "timesofindia.com":     "CENTER",
    "rt.com":               "STATE-MEDIA",
    "xinhuanet.com":        "STATE-MEDIA",
    "cgtn.com":             "STATE-MEDIA",
    "tass.com":             "STATE-MEDIA",
    "sputniknews.com":      "STATE-MEDIA",
}

# Bias risk weights — how much to penalize evidence from biased sources
_BIAS_WEIGHT: Dict[str, float] = {
    "CENTER":       1.0,
    "LEFT-CENTER":  0.90,
    "RIGHT-CENTER": 0.90,
    "LEFT":         0.75,
    "RIGHT":        0.75,
    "EXTREME-LEFT":  0.40,
    "EXTREME-RIGHT": 0.40,
    "STATE-MEDIA":   0.30,
    "UNKNOWN":       0.60,
}


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "").lower()
    except Exception:
        return ""


def get_bias_label(url: str) -> str:
    """Return political bias label for a URL's domain."""
    domain = _extract_domain(url)
    return _BIAS_DB.get(domain, "UNKNOWN")


def get_bias_weight(url: str) -> float:
    """Return trust weight multiplier based on bias (0.3–1.0)."""
    label = get_bias_label(url)
    return _BIAS_WEIGHT.get(label, 0.60)


def get_all_bias_ratings() -> list:
    """Return all bias ratings for the dashboard."""
    return [
        {"domain": domain, "bias": bias, "weight": _BIAS_WEIGHT.get(bias, 0.60)}
        for domain, bias in sorted(_BIAS_DB.items())
    ]
