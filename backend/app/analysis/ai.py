"""
AI Analysis — Smart Waterfall Router
======================================
Instead of calling ALL providers in parallel (wastes free API credits),
we use a WATERFALL strategy:

  Tier 1 (always free, no rate limits):
    → Qwen3-8B via HF Router (nscale) — completely free, ~1-3s

  Tier 2 (free keys, generous limits):
    → Groq Llama3-8B     — 14,400 req/day free
    → Cerebras Llama3.1  — 60 req/min free

  Tier 3 (free keys, tighter limits — save for important claims):
    → Gemini 2.0 Flash   — 1,500 req/day free
    → Gemma 4 31B        — same key as Gemini

  Tier 4 (premium, only if user is Pro/Enterprise):
    → MiniMax M2.7       — paid API

Strategy per user tier:
  anonymous / free  → Tier 1 only (Qwen3)
  starter           → Tier 1 + Tier 2 (Qwen3 + Groq/Cerebras, 2-model vote)
  pro               → Tier 1 + 2 + 3 (4-model ensemble)
  enterprise        → All tiers (full 5-model ensemble)

This means 500 free users cost ZERO extra API credits.
"""

from __future__ import annotations

import os
import re
import json
import logging
import requests
from typing import List, Optional
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(_env_path)

logger = logging.getLogger(__name__)

# ── Endpoints ─────────────────────────────────────────────────
CEREBRAS_URL  = "https://api.cerebras.ai/v1/chat/completions"
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL    = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
MINIMAX_URL   = "https://api.minimax.io/v1/chat/completions"
HF_ROUTER_URL = "https://router.huggingface.co/nscale/v1/chat/completions"
QWEN3_MODEL   = "Qwen/Qwen3-8B"

# ── Structured JSON prompt ────────────────────────────────────
SYSTEM_PROMPT = """You are a professional fact-checker. Analyze the given claim and respond with ONLY a JSON object — no markdown, no extra text.

JSON format:
{
  "verdict": "fake" | "real" | "uncertain",
  "confidence": <float 0.0–1.0>,
  "explanation": "<3–5 sentence factual explanation>"
}

Rules:
- verdict must be exactly one of: fake, real, uncertain
- confidence is how certain you are (0.0 = no idea, 1.0 = certain)
- explanation must be factual, calm, and natural — no AI disclaimers
- Do NOT include markdown fences or any text outside the JSON"""

# ── Cached API keys ───────────────────────────────────────────
_KEYS: Optional[dict] = None


def _get_keys() -> dict:
    global _KEYS
    if _KEYS is None:
        _KEYS = {
            "hf":       os.getenv("HF_TOKEN"),
            "cerebras": os.getenv("CEREBRAS_API_KEY"),
            "groq":     os.getenv("GROQ_API_KEY"),
            "gemini":   os.getenv("GEMINI_API_KEY"),
            "minimax":  os.getenv("MINIMAX_API_KEY"),
        }
    return _KEYS


def _parse_structured(raw: str) -> dict:
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON found: {raw[:200]}")


def _verdict_to_score(verdict: str) -> float:
    v = verdict.lower().strip()
    if v == "fake":      return 0.85
    if v == "real":      return 0.15
    if v == "uncertain": return 0.5
    return 0.5


# ─────────────────────────────────────────────────────────────
# Individual provider callers
# ─────────────────────────────────────────────────────────────

def _call_qwen3(text: str) -> dict:
    """FREE — Qwen3-8B via HF Router (nscale). No rate limit for our usage."""
    key = _get_keys()["hf"]
    if not key:
        raise ValueError("HF_TOKEN not set")
    prompt = f"{SYSTEM_PROMPT}\n\nClaim: {text} /no_think"
    r = requests.post(
        HF_ROUTER_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": QWEN3_MODEL, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1, "max_tokens": 300},
        timeout=30,
    )
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    raw = (msg.get("content") or msg.get("reasoning_content") or "").strip()
    result = _parse_structured(raw)
    result["_source"] = "qwen3"
    return result


def _call_groq(text: str) -> dict:
    """FREE — 14,400 req/day. Use for Starter+ tiers."""
    key = _get_keys()["groq"]
    if not key:
        raise ValueError("Groq key missing")
    r = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "llama3-8b-8192",
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": f"Claim: {text}"}],
              "temperature": 0.1, "max_tokens": 300},
        timeout=12,
    )
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"].strip()
    result = _parse_structured(raw)
    result["_source"] = "groq"
    return result


def _call_cerebras(text: str) -> dict:
    """FREE — 60 req/min. Use for Starter+ tiers."""
    key = _get_keys()["cerebras"]
    if not key:
        raise ValueError("Cerebras key missing")
    r = requests.post(
        CEREBRAS_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "llama3.1-8b",
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": f"Claim: {text}"}],
              "temperature": 0.1, "max_tokens": 300},
        timeout=12,
    )
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"].strip()
    result = _parse_structured(raw)
    result["_source"] = "cerebras"
    return result


def _call_gemini(text: str) -> dict:
    """FREE — 1,500 req/day. Save for Pro+ tiers."""
    key = _get_keys()["gemini"]
    if not key:
        raise ValueError("Gemini key missing")
    prompt = f"{SYSTEM_PROMPT}\n\nClaim: {text}"
    r = requests.post(
        f"{GEMINI_URL}?key={key}",
        headers={"Content-Type": "application/json"},
        json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}},
        timeout=12,
    )
    r.raise_for_status()
    raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    result = _parse_structured(raw)
    result["_source"] = "gemini"
    return result


def _call_gemma4(text: str) -> dict:
    """FREE (same Gemini key) — Gemma 4 31B, best quality free model. Pro+ only."""
    key = _get_keys()["gemini"]
    if not key:
        raise ValueError("Gemini/Gemma key missing")
    prompt = f"{SYSTEM_PROMPT}\n\nClaim: {text}"
    for model in ["gemma-4-31b-it", "gemma-3-27b-it", "gemini-1.5-flash"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            r = requests.post(
                f"{url}?key={key}",
                headers={"Content-Type": "application/json"},
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0.1, "maxOutputTokens": 400}},
                timeout=15,
            )
            r.raise_for_status()
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            result = _parse_structured(raw)
            result["_source"] = "gemma4"
            return result
        except Exception:
            continue
    raise ValueError("Gemma4/Gemma3/Gemini all failed")


def _call_minimax(text: str) -> dict:
    """PAID — MiniMax M2.7 229B. Enterprise only."""
    key = _get_keys()["minimax"]
    if not key:
        raise ValueError("MiniMax key missing")
    for model in ["MiniMax-M2.7", "MiniMax-M2.7-highspeed"]:
        try:
            r = requests.post(
                MINIMAX_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model,
                      "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                   {"role": "user", "content": f"Claim: {text}"}],
                      "temperature": 0.1, "max_tokens": 500},
                timeout=20,
            )
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"].strip()
            result = _parse_structured(raw)
            result["_source"] = "minimax"
            return result
        except Exception:
            continue
    raise ValueError("MiniMax failed")


# ─────────────────────────────────────────────────────────────
# Ensemble voting
# ─────────────────────────────────────────────────────────────

# Model quality weights — higher = more trusted
_WEIGHTS = {
    "minimax":  2.5,   # 229B MoE — enterprise only
    "gemma4":   2.0,   # 31B reasoning — pro+
    "gemini":   1.2,   # 2.0 Flash — pro+
    "qwen3":    1.1,   # 8B thinking — always free
    "groq":     1.0,   # 8B fast — starter+
    "cerebras": 1.0,   # 8B fast — starter+
}


def _ensemble_vote(results: List[dict]) -> dict:
    """Weighted vote across multiple LLM verdicts."""
    if not results:
        return {"verdict": "uncertain", "confidence": 0.5, "explanation": ""}
    if len(results) == 1:
        return results[0]

    vote_scores = {"fake": 0.0, "real": 0.0, "uncertain": 0.0}
    total_weight = 0.0
    best_explanation = ""
    best_weight = 0.0

    for r in results:
        v = r.get("verdict", "uncertain").lower()
        conf = float(r.get("confidence", 0.5))
        src = r.get("_source", "groq")
        w = _WEIGHTS.get(src, 1.0) * conf
        vote_scores[v] = vote_scores.get(v, 0.0) + w
        total_weight += w
        if w > best_weight and r.get("explanation"):
            best_weight = w
            best_explanation = r["explanation"]

    winner = max(vote_scores, key=vote_scores.get)
    ensemble_conf = (vote_scores[winner] / total_weight) if total_weight > 0 else 0.5
    ensemble_conf = max(0.3, min(0.97, ensemble_conf))

    return {"verdict": winner, "confidence": ensemble_conf, "explanation": best_explanation}


# ─────────────────────────────────────────────────────────────
# Smart Waterfall Router — the core of the system
# ─────────────────────────────────────────────────────────────

def _get_providers_for_tier(user_tier: str) -> List[tuple]:
    """
    Return the list of (name, fn) providers to use based on user tier.

    Free API budget per day (approximate):
      Qwen3 (HF nscale): unlimited for our usage
      Groq:              14,400 req/day
      Cerebras:          ~3,600 req/day (60/min)
      Gemini:            1,500 req/day
      Gemma4:            1,500 req/day (same key)
      MiniMax:           paid

    For 500 free users doing 3 checks/day = 1,500 req/day
    → Qwen3 alone handles all free users with zero cost.
    """
    keys = _get_keys()
    providers = []

    if user_tier in ("anonymous", "free"):
        # Tier 1 only — Qwen3 is completely free, handles all load
        if keys["hf"]:
            providers.append(("qwen3", _call_qwen3))

    elif user_tier == "starter":
        # Tier 1 + best of Tier 2 — 2-model vote for better accuracy
        if keys["hf"]:
            providers.append(("qwen3", _call_qwen3))
        if keys["groq"]:
            providers.append(("groq", _call_groq))
        # Cerebras as fallback if Groq fails
        if keys["cerebras"] and not keys["groq"]:
            providers.append(("cerebras", _call_cerebras))

    elif user_tier == "pro":
        # Tier 1 + 2 + 3 — 4-model ensemble, best free quality
        if keys["hf"]:
            providers.append(("qwen3", _call_qwen3))
        if keys["groq"]:
            providers.append(("groq", _call_groq))
        if keys["gemini"]:
            providers.append(("gemini", _call_gemini))
            providers.append(("gemma4", _call_gemma4))

    elif user_tier == "enterprise":
        # All tiers — full 5-model ensemble including paid MiniMax
        if keys["hf"]:
            providers.append(("qwen3", _call_qwen3))
        if keys["groq"]:
            providers.append(("groq", _call_groq))
        if keys["gemini"]:
            providers.append(("gemini", _call_gemini))
            providers.append(("gemma4", _call_gemma4))
        if keys["minimax"]:
            providers.append(("minimax", _call_minimax))

    # Always ensure at least one provider
    if not providers:
        if keys["hf"]:
            providers.append(("qwen3", _call_qwen3))
        elif keys["groq"]:
            providers.append(("groq", _call_groq))
        elif keys["gemini"]:
            providers.append(("gemini", _call_gemini))

    return providers


def _run_waterfall(text: str, providers: List[tuple]) -> tuple[List[dict], dict]:
    """
    Run providers. For single provider: sequential (saves resources).
    For multiple: parallel (faster for paid tiers).
    Returns (successes, errors).
    """
    import concurrent.futures

    if not providers:
        return [], {"all": "No providers configured"}

    successes = []
    errors = {}

    if len(providers) == 1:
        # Single provider — just call it directly, no thread overhead
        name, fn = providers[0]
        try:
            result = fn(text)
            successes.append(result)
        except Exception as e:
            errors[name] = str(e)
            logger.warning("Provider %s failed: %s", name, e)
    else:
        # Multiple providers — run in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(providers)) as executor:
            futures = {executor.submit(fn, text): name for name, fn in providers}
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    successes.append(result)
                except Exception as e:
                    errors[name] = str(e)
                    logger.warning("Provider %s failed: %s", name, e)

    return successes, errors


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def run_ai_analysis(text: str, user_tier: str = "free"):
    """
    Smart waterfall AI analysis.

    Routes to the right set of models based on user tier:
      free/anonymous → Qwen3-8B only (free, handles 500+ users/day)
      starter        → Qwen3 + Groq (2-model vote, better accuracy)
      pro            → Qwen3 + Groq + Gemini + Gemma4 (4-model ensemble)
      enterprise     → All 5 models including MiniMax 229B

    Returns: (ai_fake_score: float | None, explanation: str)
    """
    # Cache check
    try:
        from app.cache import partial_cache
        cached = partial_cache.get_ai_score(text)
        if cached is not None:
            logger.debug("AI analysis cache hit")
            return cached.get("score"), cached.get("explanation", "")
    except Exception:
        pass

    providers = _get_providers_for_tier(user_tier)
    if not providers:
        return None, "No AI providers configured"

    successes, errors = _run_waterfall(text, providers)

    # If primary provider failed, try fallback
    if not successes and errors:
        logger.warning("All providers failed for tier %s, trying Qwen3 fallback", user_tier)
        keys = _get_keys()
        if keys["hf"]:
            try:
                result = _call_qwen3(text)
                successes = [result]
            except Exception as e:
                logger.error("Qwen3 fallback also failed: %s", e)

    if not successes:
        error_summary = " | ".join(f"{k}: {v}" for k, v in errors.items())
        return None, f"AI analysis unavailable. {error_summary}"

    ensemble = _ensemble_vote(successes)
    verdict = ensemble.get("verdict", "uncertain")
    llm_conf = float(ensemble.get("confidence", 0.5))
    explanation = ensemble.get("explanation", "")

    score = _verdict_to_score(verdict)
    if verdict == "fake":
        score = max(score, llm_conf * 0.95)
    elif verdict == "real":
        score = min(score, 1.0 - llm_conf * 0.95)

    logger.info(
        "AI [%s]: verdict=%s conf=%.2f score=%.3f providers=%s errors=%s",
        user_tier, verdict, llm_conf, score,
        [r.get("_source") for r in successes],
        list(errors.keys()) if errors else "none",
    )

    # Cache result
    try:
        from app.cache import partial_cache
        partial_cache.set_ai_score(text, score, explanation)
    except Exception:
        pass

    return score, explanation
