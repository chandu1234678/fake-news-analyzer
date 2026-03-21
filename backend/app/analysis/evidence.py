import os
import requests
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
load_dotenv(_env_path)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/everything"

# High-trust outlets
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


def normalize(text: str) -> str:
    return text.lower().strip()


def fetch_evidence(text: str):
    """
    Returns:
        evidence_score (float | None)  — 0.0 = fake signal, 1.0 = real signal
        evidence_sources (list[str])   — article URLs from trusted sources
        evidence_articles (list[dict]) — title + url + source for richer display
    """
    if not NEWS_API_KEY:
        return None, [], []

    # Use first 100 chars as query to avoid API limits
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
            url = a.get("url") or ""
            title = a.get("title") or ""
            src = a.get("source", {})
            src_id = normalize(src.get("id") or "")
            src_name = normalize(src.get("name") or "")

            if url and url != "[Removed]":
                all_urls.append(url)

            if src_id in TRUSTED_SOURCES or src_name in TRUSTED_SOURCES:
                trusted_articles.append({
                    "title": title,
                    "url": url,
                    "source": src.get("name", ""),
                })

        if not trusted_articles:
            # Articles exist but none from trusted sources — weak fake signal
            return 0.1, all_urls[:3], []

        # Score: more trusted hits = stronger real signal
        score = min(len(trusted_articles) / 3, 1.0)
        urls = [a["url"] for a in trusted_articles if a["url"]]
        return round(score, 2), urls[:5], trusted_articles[:5]

    except Exception:
        return None, [], []
