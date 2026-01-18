import os
import requests
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/everything"

# High-trust outlets (IDs and names normalized)
TRUSTED_SOURCES = {
    "reuters",
    "bbc news",
    "associated press",
    "the verge",
    "medical news today",
    "nature",
    "who",
    "cdc"
}


def normalize(text: str) -> str:
    return text.lower().strip()


def fetch_evidence(text: str):
    """
    Returns:
        evidence_score (float | None)
        evidence_sources (list[str])
    """

    if not NEWS_API_KEY:
        return None, []

    params = {
        "q": text,
        "language": "en",
        "pageSize": 10,
        "sortBy": "relevancy",
        "apiKey": NEWS_API_KEY,
    }

    try:
        res = requests.get(NEWS_API_URL, params=params, timeout=10)

        if res.status_code != 200:
            return None, []

        data = res.json()
        articles = data.get("articles", [])

        if not articles:
            return None, []

        trusted_hits = []

        for a in articles:
            src = a.get("source", {})
            src_id = normalize(src.get("id") or "")
            src_name = normalize(src.get("name") or "")

            if src_id in TRUSTED_SOURCES or src_name in TRUSTED_SOURCES:
                trusted_hits.append(src.get("name"))

        if not trusted_hits:
            # Articles exist but none are trusted
            return 0.0, []

        score = min(len(trusted_hits) / 5, 1.0)  # cap influence
        return round(score, 2), list(set(trusted_hits))

    except Exception:
        # Evidence must NEVER crash the API
        return None, []
