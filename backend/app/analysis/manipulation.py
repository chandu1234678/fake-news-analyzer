"""
Manipulation & Bias Detection

Analyzes claim text for patterns associated with misinformation:
  - Sensational / clickbait language
  - Emotional amplification
  - Absolute / exaggerated claims
  - Urgency / fear triggers
  - Unverified attribution ("sources say", "they don't want you to know")

Returns a score 0.0–1.0 and a list of detected signals.
"""

import re
from typing import Tuple, List

# ── Pattern libraries ─────────────────────────────────────────

SENSATIONAL = re.compile(
    r"\b(shocking|bombshell|explosive|breaking|exposed|leaked|scandal|"
    r"outrage|unbelievable|jaw.?dropping|mind.?blowing|stunning|"
    r"you won.?t believe|nobody is talking about|they don.?t want you to know|"
    r"the truth about|what they.?re hiding|wake up|open your eyes)\b",
    re.IGNORECASE
)

EMOTIONAL = re.compile(
    r"\b(terrifying|horrifying|disgusting|enraging|heartbreaking|"
    r"devastating|catastrophic|apocalyptic|evil|corrupt|criminal|"
    r"destroy|collapse|crisis|disaster|threat|danger|attack|"
    r"panic|fear|chaos|violence|war|death|kill|murder)\b",
    re.IGNORECASE
)

ABSOLUTE = re.compile(
    r"\b(always|never|everyone|nobody|all|none|every single|"
    r"100 percent|completely|totally|absolutely|proven fact|"
    r"undeniable|irrefutable|definitive proof|confirmed by all)\b",
    re.IGNORECASE
)

UNVERIFIED_ATTRIBUTION = re.compile(
    r"\b(sources say|insiders claim|anonymous sources|"
    r"reportedly|allegedly|rumored|unconfirmed|"
    r"according to some|many people are saying|"
    r"experts warn|scientists fear|officials admit)\b",
    re.IGNORECASE
)

URGENCY = re.compile(
    r"\b(urgent|act now|share immediately|spread the word|"
    r"before it.?s deleted|before they remove|"
    r"limited time|must see|must read|do this now)\b",
    re.IGNORECASE
)


def analyze_manipulation(text: str) -> Tuple[float, List[str]]:
    """
    Returns:
        score   (float 0–1): 0 = clean, 1 = highly manipulative
        signals (list[str]): detected manipulation types
    """
    signals = []
    weights = []

    s = len(SENSATIONAL.findall(text))
    e = len(EMOTIONAL.findall(text))
    a = len(ABSOLUTE.findall(text))
    u = len(UNVERIFIED_ATTRIBUTION.findall(text))
    g = len(URGENCY.findall(text))

    if s > 0:
        signals.append("sensational language")
        weights.append(min(s * 0.20, 0.40))

    if e > 1:
        signals.append("emotional amplification")
        weights.append(min(e * 0.10, 0.30))

    if a > 0:
        signals.append("absolute claims")
        weights.append(min(a * 0.10, 0.20))

    if u > 0:
        signals.append("unverified attribution")
        weights.append(min(u * 0.15, 0.30))

    if g > 0:
        signals.append("urgency trigger")
        weights.append(min(g * 0.20, 0.30))

    score = round(min(sum(weights), 1.0), 2)
    return score, signals
