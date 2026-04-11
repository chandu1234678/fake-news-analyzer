"""
Image + Text Consistency Checker

60% of viral misinformation uses real images with false captions.
This module:
1. Extracts image URLs from article content
2. Uses Google Reverse Image Search (via SerpAPI) or Gemini Vision
   to check if the image matches the claimed context
3. Returns a consistency score and any mismatches found

No API key needed for basic URL extraction.
SerpAPI key (SERPAPI_KEY) enables reverse image search.
Gemini key enables vision-based caption consistency check.
"""
import os
import re
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
GEMINI_KEY  = os.getenv("GEMINI_API_KEY")

# Regex to extract image URLs from HTML/text
_IMG_URL_RE = re.compile(
    r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s"\'<>]*)?',
    re.IGNORECASE,
)

_session = requests.Session()
_session.headers.update({"User-Agent": "FactCheckerAI/2.0"})


def extract_image_urls(text: str) -> list:
    """Extract image URLs from text/HTML content."""
    return list(set(_IMG_URL_RE.findall(text)))[:5]


def _reverse_image_search(image_url: str) -> dict:
    """
    Use SerpAPI Google Reverse Image Search to find where an image appears.
    Returns dict with original_context and mismatch_risk.
    """
    if not SERPAPI_KEY:
        return {"available": False}
    try:
        r = _session.get(
            "https://serpapi.com/search",
            params={
                "engine":    "google_reverse_image",
                "image_url": image_url,
                "api_key":   SERPAPI_KEY,
            },
            timeout=10,
        )
        if r.status_code != 200:
            return {"available": False}

        data = r.json()
        image_results = data.get("image_results", [])
        knowledge_graph = data.get("knowledge_graph", {})

        # Extract contexts where this image has appeared
        contexts = []
        for result in image_results[:5]:
            contexts.append({
                "title":  result.get("title", ""),
                "source": result.get("source", {}).get("name", ""),
                "date":   result.get("date", ""),
            })

        return {
            "available":    True,
            "image_url":    image_url,
            "contexts":     contexts,
            "entity":       knowledge_graph.get("title", ""),
            "total_results": data.get("search_information", {}).get("total_results", 0),
        }
    except Exception as e:
        logger.debug("Reverse image search failed: %s", e)
        return {"available": False}


def _gemini_vision_check(image_url: str, claim_text: str) -> dict:
    """
    Use Gemini Vision to check if image content matches the claim.
    Returns consistency score and explanation.
    """
    if not GEMINI_KEY:
        return {"available": False}
    try:
        import json
        GEMINI_VISION_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        prompt = (
            f"Look at this image and the following claim. "
            f"Does the image support, contradict, or is it unrelated to the claim?\n\n"
            f"Claim: {claim_text[:300]}\n\n"
            f"Respond with ONLY JSON: "
            f'{{\"consistency\": \"support\"|\"contradict\"|\"unrelated\", '
            f'\"confidence\": <0.0-1.0>, \"reason\": \"<20 words max>\"}}'
        )
        r = _session.post(
            f"{GEMINI_VISION_URL}?key={GEMINI_KEY}",
            json={
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": None,
                         "file_data": {"mime_type": "image/jpeg", "file_uri": image_url}},
                    ]
                }],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 100},
            },
            timeout=12,
        )
        if r.status_code != 200:
            return {"available": False}

        raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return {
                "available":    True,
                "image_url":    image_url,
                "consistency":  data.get("consistency", "unrelated"),
                "confidence":   float(data.get("confidence", 0.5)),
                "reason":       data.get("reason", ""),
            }
    except Exception as e:
        logger.debug("Gemini vision check failed: %s", e)
    return {"available": False}


def check_image_consistency(claim_text: str, article_text: str = "") -> dict:
    """
    Main entry point. Checks image consistency with the claim.
    Accepts both http URLs and base64 data URIs (from file upload).
    """
    combined = f"{claim_text} {article_text}"

    # Check for base64 data URI first (from extension file upload)
    data_uri_match = re.match(r'^data:image/[^;]+;base64,', article_text or "")
    if data_uri_match:
        image_urls = [article_text]  # treat the data URI as the image
    else:
        image_urls = extract_image_urls(combined)

    if not image_urls:
        return {"images_found": 0, "checks": [], "mismatch_risk": 0.0, "flag": None}

    checks = []
    mismatch_signals = 0

    for url in image_urls[:2]:
        result = _gemini_vision_check(url, claim_text)
        if not result.get("available"):
            result = _reverse_image_search(url)

        if result.get("available"):
            checks.append(result)
            if result.get("consistency") == "contradict":
                mismatch_signals += 1

    mismatch_risk = round(mismatch_signals / max(len(checks), 1), 2) if checks else 0.0
    flag = "image_mismatch" if mismatch_risk > 0.5 else None

    return {
        "images_found": len(image_urls),
        "checks":       checks,
        "mismatch_risk": mismatch_risk,
        "flag":         flag,
    }
