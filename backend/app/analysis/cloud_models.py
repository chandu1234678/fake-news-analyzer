"""
Cloud Model Inference — PiNE AI
================================
All heavy models run via HuggingFace Inference API (free tier, cloud).
Your laptop never loads them locally.

Models:
  Qwen3-8B  Bharat2004/Qwen3-8B (via nscale)    — PRIMARY LLM for fact-checking
  CLIP      openai/clip-vit-large-patch14       — image-text similarity (item 104)
  OCR       microsoft/trocr-base-printed         — text extraction from images (item 105)
  Deepfake  prithivMLmods/Deep-Fake-Detector-Model — deepfake detection (item 102)
  NER       dslim/bert-large-NER                 — named entity recognition (item 108)
  XLM-R     FacebookAI/xlm-roberta-large         — multilingual classification (item 118)

HF Inference API: free, rate-limited (~few hundred req/hr).
Set HF_TOKEN in .env for higher limits.

Usage:
    from app.analysis.cloud_models import (
        qwen3_fact_check, qwen3_chat,
        clip_similarity, ocr_image, detect_deepfake,
        ner_extract, xlm_classify
    )
"""

import os
import re
import json
import base64
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

HF_TOKEN   = os.getenv("HF_TOKEN", "")
HF_API_URL = "https://api-inference.huggingface.co/models"

_HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type":  "application/json",
}

# ── Model IDs ─────────────────────────────────────────────────
# Primary LLM — Qwen3-8B via HF Router (nscale provider, free)
QWEN3_MODEL     = "Qwen/Qwen3-8B"          # original — works via nscale router
QWEN3_PROVIDER  = "nscale"
HF_ROUTER_URL   = "https://router.huggingface.co"

CLIP_MODEL      = "openai/clip-vit-large-patch14"
OCR_MODEL       = "microsoft/trocr-base-printed"
DEEPFAKE_MODEL  = "prithivMLmods/Deep-Fake-Detector-Model"
NER_MODEL       = "dslim/bert-large-NER"
XLM_MODEL       = "FacebookAI/xlm-roberta-large"
SENTIMENT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"


# ─────────────────────────────────────────────────────────────
# Qwen3-8B — Primary Free LLM via HF Router
# ─────────────────────────────────────────────────────────────

def qwen3_chat(
    messages: list,
    max_tokens: int = 500,
    temperature: float = 0.3,
    thinking: bool = False,
) -> Optional[str]:
    """
    Call Qwen3-8B via HuggingFace Router (nscale provider).
    Free, ~1-3s response time, no API key needed beyond HF_TOKEN.

    Args:
        messages: OpenAI-format messages list
        max_tokens: max response tokens
        temperature: 0.0-1.0
        thinking: if False, appends /no_think to disable chain-of-thought

    Returns:
        Response text string or None
    """
    if not HF_TOKEN:
        logger.debug("HF_TOKEN not set — Qwen3 unavailable")
        return None

    # Append /no_think to last user message to skip reasoning preamble
    if not thinking and messages:
        msgs = [m.copy() for m in messages]
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].get("role") == "user":
                content = msgs[i].get("content", "")
                if "/no_think" not in content and "/think" not in content:
                    msgs[i]["content"] = content + " /no_think"
                break
    else:
        msgs = messages

    url = f"{HF_ROUTER_URL}/{QWEN3_PROVIDER}/v1/chat/completions"
    payload = {
        "model": QWEN3_MODEL,
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"},
            json=payload,
            timeout=40,
        )
        if r.status_code == 429:
            logger.warning("Qwen3 rate limited")
            return None
        if r.status_code != 200:
            logger.debug("Qwen3 returned %d: %s", r.status_code, r.text[:200])
            return None

        data = r.json()
        choices = data.get("choices", [])
        if not choices:
            return None
        msg = choices[0].get("message", {})
        # Qwen3 thinking models: content may be None, use reasoning_content
        return msg.get("content") or msg.get("reasoning_content") or None

    except Exception as e:
        logger.debug("Qwen3 call failed: %s", e)
        return None


def qwen3_fact_check(claim: str) -> Optional[dict]:
    """
    Fact-check a claim using Qwen3-8B.
    Returns structured verdict with confidence and explanation.

    Returns:
        {"verdict": "TRUE|FALSE|UNVERIFIED", "confidence": float,
         "explanation": str, "model": str}
    """
    prompt = (
        f"Fact check this claim: {claim}\n\n"
        "Respond ONLY with valid JSON (no markdown, no extra text):\n"
        '{"verdict": "TRUE or FALSE or UNVERIFIED", '
        '"confidence": 0.0-1.0, '
        '"explanation": "one clear sentence"}'
    )

    messages = [{"role": "user", "content": prompt}]
    raw = qwen3_chat(messages, max_tokens=200, temperature=0.1)
    if not raw:
        return None

    try:
        # Extract JSON from response
        raw = raw.strip()
        m = re.search(r"\{.*?\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            verdict = data.get("verdict", "UNVERIFIED").upper()
            if verdict not in ("TRUE", "FALSE", "UNVERIFIED"):
                verdict = "UNVERIFIED"
            return {
                "verdict":     verdict,
                "confidence":  float(data.get("confidence", 0.5)),
                "explanation": data.get("explanation", ""),
                "model":       QWEN3_MODEL,
                "provider":    QWEN3_PROVIDER,
            }
    except Exception as e:
        logger.debug("Qwen3 fact-check JSON parse failed: %s | raw: %s", e, raw[:200])

    return None


def qwen3_analyze_claim(claim: str, evidence: str = "") -> Optional[dict]:
    """
    Deep analysis of a claim with optional evidence context.
    Returns verdict + manipulation detection + key entities.
    """
    evidence_section = f"\n\nEvidence/Context:\n{evidence[:500]}" if evidence else ""

    prompt = (
        f"Analyze this claim for truthfulness:{evidence_section}\n\n"
        f"Claim: {claim}\n\n"
        "Respond ONLY with valid JSON:\n"
        '{"verdict": "TRUE or FALSE or UNVERIFIED", '
        '"confidence": 0.0-1.0, '
        '"explanation": "2-3 sentences", '
        '"manipulation_technique": "emotional_appeal or false_dichotomy or fake_expert or none", '
        '"key_claims": ["list", "of", "checkable", "facts"]}'
    )

    messages = [{"role": "user", "content": prompt}]
    raw = qwen3_chat(messages, max_tokens=400, temperature=0.2)
    if not raw:
        return None

    try:
        raw = raw.strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            verdict = data.get("verdict", "UNVERIFIED").upper()
            if verdict not in ("TRUE", "FALSE", "UNVERIFIED"):
                verdict = "UNVERIFIED"
            return {
                "verdict":               verdict,
                "confidence":            float(data.get("confidence", 0.5)),
                "explanation":           data.get("explanation", ""),
                "manipulation_technique": data.get("manipulation_technique", "none"),
                "key_claims":            data.get("key_claims", []),
                "model":                 QWEN3_MODEL,
                "provider":              QWEN3_PROVIDER,
            }
    except Exception as e:
        logger.debug("Qwen3 analyze JSON parse failed: %s | raw: %s", e, raw[:200])

    return None


def _hf_post(model_id: str, payload: dict, timeout: int = 30) -> Optional[dict]:
    """POST to HuggingFace Inference API. Returns parsed JSON or None."""
    url = f"{HF_API_URL}/{model_id}"
    try:
        r = requests.post(url, headers=_HEADERS, json=payload, timeout=timeout)
        if r.status_code == 503:
            # Model loading — retry once after 10s
            import time; time.sleep(10)
            r = requests.post(url, headers=_HEADERS, json=payload, timeout=timeout)
        if r.status_code == 429:
            logger.warning("HF API rate limited for %s", model_id)
            return None
        if r.status_code != 200:
            logger.debug("HF API %s returned %d: %s", model_id, r.status_code, r.text[:200])
            return None
        return r.json()
    except Exception as e:
        logger.debug("HF API call failed for %s: %s", model_id, e)
        return None


def _hf_post_binary(model_id: str, data: bytes, timeout: int = 30) -> Optional[dict]:
    """POST binary data (image bytes) to HF Inference API."""
    url = f"{HF_API_URL}/{model_id}"
    headers = {**_HEADERS, "Content-Type": "application/octet-stream"}
    try:
        r = requests.post(url, headers=headers, data=data, timeout=timeout)
        if r.status_code == 503:
            import time; time.sleep(10)
            r = requests.post(url, headers=headers, data=data, timeout=timeout)
        if r.status_code != 200:
            logger.debug("HF binary API %s returned %d", model_id, r.status_code)
            return None
        return r.json()
    except Exception as e:
        logger.debug("HF binary API failed for %s: %s", model_id, e)
        return None


# ─────────────────────────────────────────────────────────────
# CLIP — Image-Text Similarity (item 104)
# ─────────────────────────────────────────────────────────────

def clip_similarity(image_b64: str, candidate_labels: list[str]) -> Optional[dict]:
    """
    Compute CLIP similarity between an image and text labels.
    Uses openai/clip-vit-large-patch14 via HF Inference API.

    Args:
        image_b64: base64-encoded image (data URI or raw base64)
        candidate_labels: list of text descriptions to compare

    Returns:
        {"scores": {"label": float, ...}, "best_match": str, "best_score": float}
    """
    if not HF_TOKEN:
        logger.debug("HF_TOKEN not set — CLIP unavailable")
        return None

    # Strip data URI prefix if present
    if "base64," in image_b64:
        image_b64 = image_b64.split("base64,")[1]

    payload = {
        "inputs": {
            "image": image_b64,
            "candidate_labels": candidate_labels,
        }
    }
    result = _hf_post(CLIP_MODEL, payload)
    if not result:
        return None

    # HF returns list of {label, score}
    if isinstance(result, list):
        scores = {item["label"]: round(item["score"], 4) for item in result}
        best   = max(result, key=lambda x: x["score"])
        return {
            "scores":     scores,
            "best_match": best["label"],
            "best_score": round(best["score"], 4),
            "model":      CLIP_MODEL,
        }
    return None


def clip_image_text_match(image_b64: str, claim_text: str) -> Optional[float]:
    """
    Score how well an image matches a claim text (0–1).
    Uses CLIP zero-shot classification.
    """
    labels = [
        claim_text[:100],
        f"This image does not show: {claim_text[:80]}",
        "unrelated image",
    ]
    result = clip_similarity(image_b64, labels)
    if not result:
        return None
    # Score = probability that image matches the claim
    return result["scores"].get(labels[0], 0.0)


# ─────────────────────────────────────────────────────────────
# OCR — Text Extraction from Images (item 105)
# ─────────────────────────────────────────────────────────────

def ocr_image(image_bytes: bytes) -> Optional[str]:
    """
    Extract text from an image using microsoft/trocr-base-printed.
    Uses HF Inference API — no local model needed.

    Args:
        image_bytes: raw image bytes (JPEG/PNG)

    Returns:
        Extracted text string or None
    """
    if not HF_TOKEN:
        # Fallback: use Gemini Vision for OCR (already available)
        logger.debug("HF_TOKEN not set — using Gemini Vision for OCR")
        return None

    result = _hf_post_binary(OCR_MODEL, image_bytes)
    if not result:
        return None

    if isinstance(result, list) and result:
        return result[0].get("generated_text", "")
    if isinstance(result, dict):
        return result.get("generated_text", "")
    return None


def ocr_from_base64(image_b64: str) -> Optional[str]:
    """Extract text from base64 image."""
    if "base64," in image_b64:
        image_b64 = image_b64.split("base64,")[1]
    try:
        image_bytes = base64.b64decode(image_b64)
        return ocr_image(image_bytes)
    except Exception as e:
        logger.debug("OCR base64 decode failed: %s", e)
        return None


# ─────────────────────────────────────────────────────────────
# Deepfake Detection (item 102)
# ─────────────────────────────────────────────────────────────

def detect_deepfake(image_bytes: bytes) -> Optional[dict]:
    """
    Detect if an image is a deepfake using prithivMLmods/Deep-Fake-Detector-Model.
    Fine-tuned from google/siglip-base-patch16-512 for binary deepfake classification.

    Returns:
        {"is_deepfake": bool, "confidence": float, "label": str, "model": str}
    """
    if not HF_TOKEN:
        logger.debug("HF_TOKEN not set — deepfake detection unavailable")
        return None

    result = _hf_post_binary(DEEPFAKE_MODEL, image_bytes)
    if not result:
        return None

    # Result: [{"label": "Real"|"Fake", "score": float}, ...]
    if isinstance(result, list) and result:
        # Find the fake label
        fake_score = 0.0
        real_score = 0.0
        for item in result:
            label = item.get("label", "").lower()
            score = item.get("score", 0.0)
            if "fake" in label or "synthetic" in label or "generated" in label:
                fake_score = score
            elif "real" in label or "authentic" in label:
                real_score = score

        is_deepfake = fake_score > 0.5
        confidence  = fake_score if is_deepfake else real_score

        return {
            "is_deepfake": is_deepfake,
            "confidence":  round(confidence, 4),
            "fake_score":  round(fake_score, 4),
            "real_score":  round(real_score, 4),
            "label":       "DEEPFAKE" if is_deepfake else "AUTHENTIC",
            "model":       DEEPFAKE_MODEL,
        }
    return None


def detect_deepfake_b64(image_b64: str) -> Optional[dict]:
    """Detect deepfake from base64 image."""
    if "base64," in image_b64:
        image_b64 = image_b64.split("base64,")[1]
    try:
        return detect_deepfake(base64.b64decode(image_b64))
    except Exception as e:
        logger.debug("Deepfake b64 decode failed: %s", e)
        return None


# ─────────────────────────────────────────────────────────────
# NER — Named Entity Recognition (item 108)
# Cloud version — no local model needed
# ─────────────────────────────────────────────────────────────

def ner_extract_cloud(text: str) -> Optional[list]:
    """
    Extract named entities using dslim/bert-large-NER via HF Inference API.
    Returns list of {word, entity_group, score, start, end}.
    """
    if not HF_TOKEN:
        return None

    payload = {
        "inputs": text[:512],
        "parameters": {"aggregation_strategy": "simple"},
    }
    result = _hf_post(NER_MODEL, payload)
    if not result or not isinstance(result, list):
        return None

    return [
        {
            "word":         ent.get("word", ""),
            "entity_group": ent.get("entity_group", ""),
            "score":        round(ent.get("score", 0.0), 4),
            "start":        ent.get("start", 0),
            "end":          ent.get("end", 0),
        }
        for ent in result
        if ent.get("score", 0) >= 0.7
    ]


# ─────────────────────────────────────────────────────────────
# XLM-RoBERTa — Multilingual Classification (item 118)
# Cloud version — no local model needed
# ─────────────────────────────────────────────────────────────

def xlm_classify_cloud(text: str) -> Optional[dict]:
    """
    Classify text using cardiffnlp/twitter-xlm-roberta-base-sentiment
    via HF Inference API. Works for 100+ languages.

    Returns: {"label": str, "score": float, "fake_probability": float}
    """
    if not HF_TOKEN:
        return None

    payload = {"inputs": text[:512]}
    result  = _hf_post(SENTIMENT_MODEL, payload)
    if not result:
        return None

    # Result: [[{"label": "positive"|"negative"|"neutral", "score": float}]]
    items = result[0] if isinstance(result, list) and result else result
    if not isinstance(items, list):
        return None

    best = max(items, key=lambda x: x.get("score", 0))
    label = best.get("label", "").lower()
    score = best.get("score", 0.5)

    # Map sentiment to fake probability (negative sentiment → more likely fake/misleading)
    fake_prob = score if "negative" in label else (1.0 - score)

    return {
        "label":            best.get("label", ""),
        "score":            round(score, 4),
        "fake_probability": round(fake_prob, 4),
        "model":            SENTIMENT_MODEL,
    }


# ─────────────────────────────────────────────────────────────
# Psychological Inoculation (items 90-94)
# Uses existing LLM ensemble — no new model needed
# ─────────────────────────────────────────────────────────────

_INOCULATION_PROMPT = """Analyze this claim for manipulation techniques.
Identify ONE primary technique from: [emotional_appeal, false_dichotomy, fake_expert, 
conspiracy_thinking, scapegoating, fear_mongering, bandwagon, cherry_picking, 
misrepresentation, urgency_pressure, none]

Then write a ONE sentence inoculation message (max 15 words) that helps the reader 
think critically without being preachy.

Claim: {claim}

Respond with ONLY JSON: {{"technique": "...", "inoculation": "..."}}"""


def get_inoculation(claim_text: str) -> Optional[dict]:
    """
    Identify manipulation technique and generate prebunking message.
    Items 90-94: Psychological inoculation based on Roozenbeek & van der Linden (2019).
    Uses Qwen3-8B as primary, falls back to Groq/Gemini.

    Returns: {"technique": str, "inoculation": str} or None
    """
    prompt = _INOCULATION_PROMPT.format(claim=claim_text[:300])
    msgs = [{"role": "user", "content": prompt}]

    # Try Qwen3-8B first (free, fast)
    raw = qwen3_chat(msgs, max_tokens=100, temperature=0.1)

    # Fallback to other LLMs
    if not raw:
        try:
            from app.analysis.chat import _call_openai_compat, _call_gemini, _get_keys, _first_success
            keys = _get_keys()
            fns = []
            if keys.get("gemini"):
                fns.append(("Gemini", lambda: _call_gemini(msgs, max_tokens=80, temperature=0)))
            if keys.get("groq"):
                fns.append(("Groq", lambda: _call_openai_compat(
                    "https://api.groq.com/openai/v1/chat/completions",
                    keys["groq"], "llama3-8b-8192", msgs, max_tokens=80, temperature=0
                )))
            if fns:
                raw = _first_success(fns)
        except Exception as e:
            logger.debug("Inoculation fallback failed: %s", e)

    if not raw:
        return None

    try:
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            technique = data.get("technique", "none")
            if technique == "none":
                return None
            return {
                "technique":   technique,
                "inoculation": data.get("inoculation", ""),
                "source":      "qwen3-inoculation",
            }
    except Exception as e:
        logger.debug("Inoculation JSON parse failed: %s", e)
    return None


# ─────────────────────────────────────────────────────────────
# Adversarial Input Detection (item 116)
# ─────────────────────────────────────────────────────────────

import unicodedata

_HOMOGLYPH_MAP = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x",  # Cyrillic
    "ο": "o", "α": "a", "ε": "e",  # Greek
    "０": "0", "１": "1", "２": "2",  # Fullwidth
}

def detect_adversarial_input(text: str) -> dict:
    """
    Detect adversarial manipulation in input text (item 116).
    Checks for: homoglyphs, excessive emoji, invisible chars, typo attacks.

    Returns: {"is_adversarial": bool, "signals": list, "cleaned_text": str}
    """
    signals = []
    cleaned = text

    # 1. Homoglyph substitution (Cyrillic/Greek chars that look like Latin)
    homoglyph_count = sum(1 for c in text if c in _HOMOGLYPH_MAP)
    if homoglyph_count > 0:
        signals.append(f"homoglyphs:{homoglyph_count}")
        for src, dst in _HOMOGLYPH_MAP.items():
            cleaned = cleaned.replace(src, dst)

    # 2. Invisible/zero-width characters
    invisible = [c for c in text if unicodedata.category(c) in ("Cf", "Cc") and c not in "\n\t\r"]
    if invisible:
        signals.append(f"invisible_chars:{len(invisible)}")
        cleaned = "".join(c for c in cleaned if unicodedata.category(c) not in ("Cf",) or c in "\n\t\r")

    # 3. Excessive emoji injection
    emoji_count = sum(1 for c in text if unicodedata.category(c) == "So")
    if emoji_count > 5:
        signals.append(f"emoji_injection:{emoji_count}")

    # 4. Repeated character patterns (typo attack: "vaaccine", "truuump")
    import re
    repeated = re.findall(r'(.)\1{3,}', text)
    if repeated:
        signals.append(f"char_repetition:{len(repeated)}")

    # 5. Mixed scripts (Latin + Cyrillic in same word)
    words = text.split()
    mixed = 0
    for w in words:
        has_latin   = any('a' <= c.lower() <= 'z' for c in w)
        has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in w)
        if has_latin and has_cyrillic:
            mixed += 1
    if mixed > 0:
        signals.append(f"mixed_scripts:{mixed}")

    return {
        "is_adversarial": len(signals) > 0,
        "signals":        signals,
        "cleaned_text":   cleaned,
        "risk_score":     min(len(signals) * 0.2, 1.0),
    }
