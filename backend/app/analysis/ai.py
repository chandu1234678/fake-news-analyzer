import os
import re
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(_env_path)

CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL   = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# ── Structured JSON prompt ────────────────────────────────────
# Ask the LLM to return a machine-readable verdict alongside the explanation.
# This replaces the old keyword-matching _score_from_text() hack.
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


def _get_keys():
    return {
        "cerebras": os.getenv("CEREBRAS_API_KEY"),
        "groq":     os.getenv("GROQ_API_KEY"),
        "gemini":   os.getenv("GEMINI_API_KEY"),
    }


def _parse_structured(raw: str) -> dict:
    """Extract JSON from LLM response, handling minor formatting issues."""
    # Strip markdown fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    # Find first { ... } block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON found in response: {raw[:200]}")


def _verdict_to_score(verdict: str) -> float:
    """Convert structured verdict to a fake probability score."""
    v = verdict.lower().strip()
    if v == "fake":      return 0.85
    if v == "real":      return 0.15
    if v == "uncertain": return 0.5
    return 0.5


def _call_cerebras(text: str) -> dict:
    key = _get_keys()["cerebras"]
    if not key:
        raise ValueError("Cerebras API key missing")
    r = requests.post(
        CEREBRAS_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": "llama3.1-8b",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Claim: {text}"}
            ],
            "temperature": 0.1,
            "max_tokens": 300,
        },
        timeout=12
    )
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"].strip()
    return _parse_structured(raw)


def _call_groq(text: str) -> dict:
    key = _get_keys()["groq"]
    if not key:
        raise ValueError("Groq API key missing")
    r = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Claim: {text}"}
            ],
            "temperature": 0.1,
            "max_tokens": 300,
        },
        timeout=12
    )
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"].strip()
    return _parse_structured(raw)


def _call_gemini(text: str) -> dict:
    key = _get_keys()["gemini"]
    if not key:
        raise ValueError("Gemini API key missing")
    prompt = f"{SYSTEM_PROMPT}\n\nClaim: {text}"
    r = requests.post(
        f"{GEMINI_URL}?key={key}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}
        },
        timeout=12
    )
    r.raise_for_status()
    raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    return _parse_structured(raw)


def _run_primaries_parallel(text: str):
    """Run all three providers in parallel, return first successful structured result."""
    primaries = [
        ("Cerebras", _call_cerebras),
        ("Groq",     _call_groq),
        ("Gemini",   _call_gemini),
    ]
    errors = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fn, text): name for name, fn in primaries}
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                return result, errors
            except Exception as e:
                errors[name] = str(e)
    return None, errors


def run_ai_analysis(text: str):
    """
    Runs Cerebras, Groq, Gemini in parallel.
    Returns structured verdict from the first successful provider.
    Caches results for 1 hour to reduce API costs.

    Returns: (ai_fake_score: float | None, explanation: str)
    """
    # Try cache first
    try:
        from app.cache import partial_cache
        cached = partial_cache.get_ai_score(text)
        if cached is not None:
            import logging
            logging.getLogger(__name__).debug("AI analysis cache hit")
            return cached.get("score"), cached.get("explanation", "")
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"Cache lookup failed: {e}")
    
    result, errors = _run_primaries_parallel(text)

    if result:
        score = _verdict_to_score(result.get("verdict", "uncertain"))
        # Blend with LLM's own confidence: if LLM says fake with 0.9 confidence,
        # push score toward 0.9 rather than fixed 0.85
        llm_conf = float(result.get("confidence", 0.5))
        if result.get("verdict") == "fake":
            score = max(score, llm_conf * 0.95)
        elif result.get("verdict") == "real":
            score = min(score, 1.0 - llm_conf * 0.95)
        explanation = result.get("explanation", "")
        
        # Cache the result
        try:
            from app.cache import partial_cache
            partial_cache.set_ai_score(text, score, explanation)
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Cache set failed: {e}")
        
        return score, explanation

    error_summary = " | ".join(f"{k}: {v}" for k, v in errors.items())
    return None, f"AI analysis unavailable. {error_summary}"
