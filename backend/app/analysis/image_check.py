"""
Image + Text Consistency Checker

Analyzes images sent with claims using Gemini Vision.
Accepts base64 data URIs (from extension file upload) and http URLs.

Returns a description of the image and whether it's consistent with the claim.
"""
import os
import re
import base64
import logging
import requests

logger = logging.getLogger(__name__)

def _get_gemini_key():
    return os.getenv("GEMINI_API_KEY")

GEMINI_VISION_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_VISION_FALLBACK_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent"

# Simple rate limiter — track last vision call time to avoid 429
import threading
_last_vision_call = 0.0
_vision_lock = threading.Lock()

def _wait_for_rate_limit():
    """Ensure at least 4 seconds between vision API calls (free tier: 15 RPM)."""
    import time
    global _last_vision_call
    with _vision_lock:
        now = time.time()
        elapsed = now - _last_vision_call
        if elapsed < 4.0:
            time.sleep(4.0 - elapsed)
        _last_vision_call = time.time()

_session = requests.Session()
_session.headers.update({"User-Agent": "FactCheckerAI/2.0"})

_DATA_URI_RE = re.compile(r'^data:(image/[^;]+);base64,(.+)$', re.DOTALL)
_IMG_URL_RE  = re.compile(
    r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s"\'<>]*)?',
    re.IGNORECASE,
)


def _gemini_vision_base64(mime_type: str, b64_data: str, prompt: str) -> dict:
    """Call Gemini Vision with inline base64 image data, with retry on 429."""
    GEMINI_KEY = _get_gemini_key()
    if not GEMINI_KEY:
        return {"available": False, "reason": "No Gemini API key"}

    import time
    _wait_for_rate_limit()
    url = GEMINI_VISION_URL
    for attempt in range(3):
        try:
            r = _session.post(
                f"{url}?key={GEMINI_KEY}",
                json={
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": mime_type, "data": b64_data}},
                        ]
                    }],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 300},
                },
                timeout=20,
            )
            if r.status_code == 429:
                wait = 2 ** attempt
                logger.warning("Gemini Vision 429 rate limit, retrying in %ss (attempt %d/3)", wait, attempt + 1)
                time.sleep(wait)
                if attempt >= 1:
                    url = GEMINI_VISION_FALLBACK_URL
                continue
            if r.status_code != 200:
                logger.warning("Gemini Vision returned %s: %s", r.status_code, r.text[:300])
                return {"available": False, "reason": f"HTTP {r.status_code}: {r.text[:100]}"}

            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            logger.info("Gemini Vision success, description length=%d", len(text))
            return {"available": True, "description": text}
        except Exception as e:
            logger.warning("Gemini Vision failed (attempt %d): %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2 ** attempt)

    return {"available": False, "reason": "Gemini Vision rate limited after 3 attempts"}


def _gemini_vision_url(image_url: str, prompt: str) -> dict:
    """Call Gemini Vision with a public image URL."""
    GEMINI_KEY = _get_gemini_key()
    if not GEMINI_KEY:
        return {"available": False, "reason": "No Gemini API key"}
    try:
        r = _session.post(
            f"{GEMINI_VISION_URL}?key={GEMINI_KEY}",
            json={
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"file_data": {"mime_type": "image/jpeg", "file_uri": image_url}},
                    ]
                }],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 300},
            },
            timeout=15,
        )
        if r.status_code != 200:
            logger.warning("Gemini Vision URL returned %s: %s", r.status_code, r.text[:300])
            return {"available": False, "reason": f"HTTP {r.status_code}"}
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return {"available": True, "description": text}
    except Exception as e:
        logger.warning("Gemini Vision URL failed: %s", e)
        return {"available": False, "reason": str(e)}


def check_image_consistency(claim_text: str, image_source: str = "") -> dict:
    """
    Analyze an image for consistency with a claim.

    image_source can be:
    - A base64 data URI: data:image/jpeg;base64,...
    - An http/https image URL
    - Plain text (no image analysis performed)

    Returns:
        {
          "images_found": int,
          "description": str,
          "consistency": "support"|"contradict"|"neutral",
          "mismatch_risk": float 0-1,
          "flag": str | None
        }
    """
    image_source = image_source or ""
    logger.info("check_image_consistency: source_len=%d, starts_with=%s",
                len(image_source), image_source[:30] if image_source else "EMPTY")

    # Check for base64 data URI
    data_match = _DATA_URI_RE.match(image_source)
    if data_match:
        mime_type = data_match.group(1)
        b64_data  = data_match.group(2)

        prompt = (
            f"Describe what you see in this image in 2-3 sentences. "
            f"Then assess: does the image support, contradict, or is it unrelated to this claim?\n\n"
            f"Claim: {claim_text[:300]}\n\n"
            f"Format your response as:\n"
            f"Description: [what you see]\n"
            f"Assessment: support | contradict | unrelated\n"
            f"Reason: [one sentence]"
        )

        result = _gemini_vision_base64(mime_type, b64_data, prompt)
        if result.get("available"):
            desc = result["description"]
            consistency = "neutral"
            if "contradict" in desc.lower():
                consistency = "contradict"
            elif "support" in desc.lower():
                consistency = "support"

            mismatch_risk = 0.7 if consistency == "contradict" else 0.0
            return {
                "images_found":  1,
                "description":   desc,
                "consistency":   consistency,
                "mismatch_risk": mismatch_risk,
                "flag":          "image_mismatch" if mismatch_risk > 0.5 else None,
            }
        else:
            logger.warning("Gemini Vision unavailable: %s", result.get("reason"))
            return {
                "images_found":  1,
                "description":   "Image received but vision analysis unavailable",
                "consistency":   "neutral",
                "mismatch_risk": 0.0,
                "flag":          None,
            }

    # Check for http URL
    url_match = _IMG_URL_RE.search(image_source)
    if url_match:
        url    = url_match.group(0)
        prompt = f"Describe this image briefly. Does it support or contradict: {claim_text[:200]}"
        result = _gemini_vision_url(url, prompt)
        if result.get("available"):
            return {
                "images_found":  1,
                "description":   result["description"],
                "consistency":   "neutral",
                "mismatch_risk": 0.0,
                "flag":          None,
            }

    return {"images_found": 0, "checks": [], "mismatch_risk": 0.0, "flag": None}
