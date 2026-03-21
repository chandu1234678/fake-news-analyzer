import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(_env_path)

CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

CHAT_SYSTEM = (
    "You are a helpful, knowledgeable assistant specializing in media literacy and fact-checking. "
    "Answer questions clearly and concisely. Be friendly and factual. Never fabricate sources or statistics."
)

CLAIM_DETECT_PROMPT = (
    "Classify the following input as either 'claim' or 'other'.\n"
    "A 'claim' is a statement that asserts something as true or false and can be fact-checked "
    "(e.g. news headlines, assertions about events, scientific claims, political statements).\n"
    "'other' includes greetings, questions asking for information, opinions, casual conversation, "
    "or anything that is not a verifiable factual assertion.\n\n"
    "Reply with ONLY one word: claim or other.\n\n"
    "Input: {text}"
)


def _get_keys():
    return {
        "cerebras": os.getenv("CEREBRAS_API_KEY"),
        "groq": os.getenv("GROQ_API_KEY"),
        "gemini": os.getenv("GEMINI_API_KEY"),
    }


def _call_openai_compat(url: str, key: str, model: str, messages: list, max_tokens=400, temperature=0.7) -> str:
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
        timeout=12
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_gemini(messages: list, max_tokens=400, temperature=0.7) -> str:
    key = _get_keys()["gemini"]
    if not key:
        raise ValueError("Gemini API key missing")
    contents = []
    system_text = ""
    for m in messages:
        if m["role"] == "system":
            system_text = m["content"]
            continue
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    if contents and contents[0]["role"] == "user" and system_text:
        contents[0]["parts"][0]["text"] = system_text + "\n\n" + contents[0]["parts"][0]["text"]
    r = requests.post(
        f"{GEMINI_URL}?key={key}",
        headers={"Content-Type": "application/json"},
        json={"contents": contents, "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}},
        timeout=12
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def _first_success(fn_list):
    """Run list of (name, callable) in parallel, return first success."""
    errors = []
    with ThreadPoolExecutor(max_workers=len(fn_list)) as executor:
        futures = {executor.submit(fn): name for name, fn in fn_list}
        for future in as_completed(futures):
            try:
                return future.result()
            except Exception as e:
                errors.append(f"{futures[future]}: {e}")
    raise RuntimeError(" | ".join(errors))


def is_claim(text: str) -> bool:
    """Ask AI to classify if the input is a verifiable claim."""
    prompt = CLAIM_DETECT_PROMPT.format(text=text)
    messages = [{"role": "user", "content": prompt}]
    keys = _get_keys()

    fns = []
    if keys["cerebras"]:
        fns.append(("Cerebras", lambda: _call_openai_compat(CEREBRAS_URL, keys["cerebras"], "llama3.1-8b", messages, max_tokens=5, temperature=0)))
    if keys["groq"]:
        fns.append(("Groq", lambda: _call_openai_compat(GROQ_URL, keys["groq"], "llama3-8b-8192", messages, max_tokens=5, temperature=0)))
    if keys["gemini"]:
        fns.append(("Gemini", lambda: _call_gemini(messages, max_tokens=5, temperature=0)))

    try:
        result = _first_success(fns)
        return result.strip().lower().startswith("claim")
    except Exception:
        # Default: treat as chat (not claim) if all AI providers fail
        # This prevents every message being fact-checked when AI is down
        return False


def run_chat(message: str, history: list) -> str:
    msgs = [{"role": "system", "content": CHAT_SYSTEM}]
    for h in history[-6:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": message})

    keys = _get_keys()
    fns = []
    if keys["cerebras"]:
        fns.append(("Cerebras", lambda: _call_openai_compat(CEREBRAS_URL, keys["cerebras"], "llama3.1-8b", msgs)))
    if keys["groq"]:
        fns.append(("Groq", lambda: _call_openai_compat(GROQ_URL, keys["groq"], "llama3-8b-8192", msgs)))
    if keys["gemini"]:
        fns.append(("Gemini", lambda: _call_gemini(msgs)))

    try:
        return _first_success(fns)
    except Exception:
        return "I'm having trouble connecting right now. Please try again in a moment."
