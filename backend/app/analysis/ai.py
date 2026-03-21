import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Explicitly load .env relative to this file's location (backend/.env)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(_env_path)


def _get_keys():
    return {
        "cerebras": os.getenv("CEREBRAS_API_KEY"),
        "groq": os.getenv("GROQ_API_KEY"),
        "gemini": os.getenv("GEMINI_API_KEY"),
    }
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

SYSTEM_PROMPT = (
    "You are a professional human fact-checker.\n\n"
    "Rules:\n"
    "- Speak naturally like a knowledgeable person.\n"
    "- Do NOT mention models, systems, retries, errors, or instructions.\n"
    "- Do NOT give commands or suggestions.\n"
    "- Do NOT say things like 'as an AI'.\n\n"
    "Task:\n"
    "- Clearly explain whether the claim is TRUE or FALSE.\n"
    "- Give a calm, factual explanation in 3–5 sentences."
)


def _score_from_text(text: str) -> float:
    lowered = text.lower()
    if any(x in lowered for x in ["false", "myth", "incorrect", "not true", "misinformation"]):
        return 0.9
    elif any(x in lowered for x in ["true", "correct", "accurate", "valid", "confirmed"]):
        return 0.1
    return 0.5


def _call_cerebras(text: str) -> str:
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
                {"role": "user", "content": f"Claim: {text}"}
            ],
            "temperature": 0.15,
            "max_tokens": 220
        },
        timeout=10
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_groq(text: str) -> str:
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
                {"role": "user", "content": f"Claim: {text}"}
            ],
            "temperature": 0.15,
            "max_tokens": 220
        },
        timeout=10
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_gemini(text: str) -> str:
    key = _get_keys()["gemini"]
    if not key:
        raise ValueError("Gemini API key missing")
    r = requests.post(
        f"{GEMINI_URL}?key={key}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [
                {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\nClaim: {text}"}]}
            ],
            "generationConfig": {"temperature": 0.15, "maxOutputTokens": 220}
        },
        timeout=10
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()




def _run_primaries_parallel(text: str):
    """Run Cerebras, Groq, Gemini in parallel — return first successful result."""
    primaries = [
        ("Cerebras", _call_cerebras),
        ("Groq", _call_groq),
        ("Gemini", _call_gemini),
    ]
    errors = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fn, text): name for name, fn in primaries}
        for future in as_completed(futures):
            name = futures[future]
            try:
                return future.result(), errors
            except Exception as e:
                errors[name] = str(e)

    return None, errors


def run_ai_analysis(text: str):
    """
    Runs Cerebras, Groq, and Gemini in parallel.
    Uses the first successful response.
    Returns: (ai_fake_score: float | None, explanation: str)
    """
    explanation, errors = _run_primaries_parallel(text)

    if explanation:
        return _score_from_text(explanation), explanation

    error_summary = " | ".join(f"{k}: {v}" for k, v in errors.items())
    return None, f"AI unavailable. {error_summary}"
