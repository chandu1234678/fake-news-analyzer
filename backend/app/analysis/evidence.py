"""
News evidence fetching with:
- Retry + exponential backoff on transient failures
- Increased timeout (15s)
- Reusable httpx session (connection pooling)
"""
import os
import re
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from app.analysis.credibility import get_trust_score, get_trust_label

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
load_dotenv(_env_path)

logger = logging.getLogger(__name__)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/everything"

# ── Reusable session with retry ───────────────────────────────
_retry_strategy = Retry(
    total=2,
    backoff_factor=0.5,          # 0.5s, 1s
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
_adapter = HTTPAdapter(max_retries=_retry_strategy)
_session = requests.Session()
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

TRUSTED_SOURCES = {
    "reuters", "bbc news", "bbc", "associated press", "ap news",
    "the verge", "medical news today", "nature", "who", "cdc",
    "the guardian", "the new york times", "washington post",
    "nbc news", "abc news", "cbs news", "npr", "pbs",
    "bloomberg", "financial times", "the economist",
    "al jazeera", "france 24", "dw news", "afp",
    "ndtv", "the hindu", "hindustan times", "india today",
    "times of india", "press trust of india", "ani",
    "snopes", "factcheck.org", "politifact", "fullfact",
}

_SUPPORT_WORDS = re.compile(
    r"\b(confirm|confirmed|verif|true|accurate|correct|real|legitimate|"
    r"evidence shows|study finds|research confirms|officials say|"
    r"according to|report shows|data shows|proves|proven)\b",
    re.IGNORECASE,
)
_CONTRADICT_WORDS = re.compile(
    r"\b(false|fake|debunk|mislead|misinform|incorrect|wrong|"
    r"no evidence|unverified|disputed|claim is|rumor|hoax|"
    r"fact.?check|not true|baseless|fabricat|manipulat)\b",
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    return text.lower().strip()


def _stance(title: str, description: str) -> str:
    blob = f"{title} {description or ''}".lower()
    s = len(_SUPPORT_WORDS.findall(blob))
    c = len(_CONTRADICT_WORDS.findall(blob))
    if c > s:
        return "contradict"
    if s > c:
        return "support"
    return "neutral"


def _consistency_score(articles: list) -> float:
    support    = sum(a.get("trust_score", 0.5) for a in articles if a.get("stance") == "support")
    contradict = sum(a.get("trust_score", 0.5) for a in articles if a.get("stance") == "contradict")
    total = support + contradict
    if total == 0:
        return 0.5
    return round(support / total, 2)


def fetch_evidence(text: str):
    """
    Returns:
        evidence_score (float | None)
        evidence_sources (list[str])
        evidence_articles (list[dict])
    """
    if not NEWS_API_KEY:
        return None, [], []

    params = {
        "q":        text[:100],
        "language": "en",
        "pageSize": 10,
        "sortBy":   "relevancy",
        "apiKey":   NEWS_API_KEY,
    }

    try:
        t0  = time.perf_counter()
        res = _session.get(NEWS_API_URL, params=params, timeout=15)
        elapsed = round((time.perf_counter() - t0) * 1000)

        if res.status_code != 200:
            logger.warning("NewsAPI returned %s in %sms", res.status_code, elapsed)
            return None, [], []

        logger.debug("NewsAPI OK in %sms", elapsed)
        articles = res.json().get("articles", [])
        if not articles:
            return 0.0, [], []

        trusted_articles = []
        all_urls = []

        for a in articles:
            url      = a.get("url") or ""
            title    = a.get("title") or ""
            desc     = a.get("description") or ""
            src      = a.get("source", {})
            src_id   = normalize(src.get("id")   or "")
            src_name = normalize(src.get("name") or "")

            if url and url != "[Removed]":
                all_urls.append(url)

            if src_id in TRUSTED_SOURCES or src_name in TRUSTED_SOURCES:
                stance = _stance(title, desc)
                trust  = get_trust_score(url)
                trusted_articles.append({
                    "title":       title,
                    "url":         url,
                    "source":      src.get("name", ""),
                    "stance":      stance,
                    "trust_score": trust,
                    "trust_label": get_trust_label(url),
                })

        if not trusted_articles:
            return 0.1, all_urls[:3], []

        score = _consistency_score(trusted_articles)
        coverage_bonus = min(len(trusted_articles) / 5, 0.15)
        score = round(min(1.0, score + coverage_bonus), 2)

        urls = [a["url"] for a in trusted_articles if a["url"]]
        return score, urls[:5], trusted_articles[:5]

    except requests.exceptions.Timeout:
        logger.warning("NewsAPI timed out after 15s")
        return None, [], []
    except Exception as e:
        logger.warning("NewsAPI error: %s", e)
        return None, [], []
