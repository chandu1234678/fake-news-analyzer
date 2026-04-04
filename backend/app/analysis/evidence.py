import os
import re
import requests
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
load_dotenv(_env_path)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/everything"

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

# Words that suggest an article SUPPORTS the claim being true
_SUPPORT_WORDS = re.compile(
    r"\b(confirm|confirmed|verif|true|accurate|correct|real|legitimate|"
    r"evidence shows|study finds|research confirms|officials say|"
    r"according to|report shows|data shows|proves|proven)\b",
    re.IGNORECASE
)

# Words that suggest an article CONTRADICTS / debunks the claim
_CONTRADICT_WORDS = re.compile(
    r"\b(false|fake|debunk|mislead|misinform|incorrect|wrong|"
    r"no evidence|unverified|disputed|claim is|rumor|hoax|"
    r"fact.?check|not true|baseless|fabricat|manipulat)\b",
    re.IGNORECASE
)


def normalize(text: str) -> str:
    return text.lower().strip()


def _stance(title: str, description: str) -> str:
    """
    Classify article stance toward the claim as:
      support    — article corroborates the claim
      contradict — article debunks / disputes the claim
      neutral    — no clear signal
    """
    blob = f"{title} {description or ''}".lower()
    s = len(_SUPPORT_WORDS.findall(blob))
    c = len(_CONTRADICT_WORDS.findall(blob))
    if c > s:
        return "contradict"
    if s > c:
        return "support"
    return "neutral"


def _consistency_score(articles: list) -> float:
    """
    Compute evidence consistency as a real-signal score (0–1).
    More supporting trusted sources → higher score (real signal).
    More contradicting sources → lower score (fake signal).
    """
    support    = sum(1 for a in articles if a.get("stance") == "support")
    contradict = sum(1 for a in articles if a.get("stance") == "contradict")
    total = support + contradict
    if total == 0:
        return 0.5  # neutral / unknown
    # Ratio of support vs total signal
    return round(support / total, 2)


def fetch_evidence(text: str):
    """
    Returns:
        evidence_score (float | None)  — 0–1, real signal (1 = strongly real)
        evidence_sources (list[str])   — article URLs
        evidence_articles (list[dict]) — enriched with stance field
    """
    if not NEWS_API_KEY:
        return None, [], []

    query = text[:100]
    params = {
        "q": query,
        "language": "en",
        "pageSize": 10,
        "sortBy": "relevancy",
        "apiKey": NEWS_API_KEY,
    }

    try:
        res = requests.get(NEWS_API_URL, params=params, timeout=10)
        if res.status_code != 200:
            return None, [], []

        articles = res.json().get("articles", [])
        if not articles:
            return 0.0, [], []

        trusted_articles = []
        all_urls = []

        for a in articles:
            url   = a.get("url") or ""
            title = a.get("title") or ""
            desc  = a.get("description") or ""
            src   = a.get("source", {})
            src_id   = normalize(src.get("id")   or "")
            src_name = normalize(src.get("name") or "")

            if url and url != "[Removed]":
                all_urls.append(url)

            if src_id in TRUSTED_SOURCES or src_name in TRUSTED_SOURCES:
                stance = _stance(title, desc)
                trusted_articles.append({
                    "title":  title,
                    "url":    url,
                    "source": src.get("name", ""),
                    "stance": stance,
                })

        if not trusted_articles:
            return 0.1, all_urls[:3], []

        # Consistency score from stance analysis
        score = _consistency_score(trusted_articles)

        # Boost score slightly if many trusted sources found
        coverage_bonus = min(len(trusted_articles) / 5, 0.15)
        score = round(min(1.0, score + coverage_bonus), 2)

        urls = [a["url"] for a in trusted_articles if a["url"]]
        return score, urls[:5], trusted_articles[:5]

    except Exception:
        return None, [], []
