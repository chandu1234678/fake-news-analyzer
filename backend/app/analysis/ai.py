import os
import requests
from dotenv import load_dotenv

load_dotenv()

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
API_URL = "https://api.cerebras.ai/v1/chat/completions"
MODEL = "llama3.1-8b"

HEADERS = {
    "Authorization": f"Bearer {CEREBRAS_API_KEY}",
    "Content-Type": "application/json"
}


def run_ai_analysis(text: str):
    """
    Returns:
      ai_fake_score (float | None)
      explanation (str)
    """

    if not CEREBRAS_API_KEY:
        return None, "AI unavailable (Cerebras API key missing)."

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
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
            },
            {
                "role": "user",
                "content": f"Claim: {text}"
            }
        ],
        "temperature": 0.15,
        "max_tokens": 220
    }

    try:
        r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=10)
        r.raise_for_status()

        explanation = r.json()["choices"][0]["message"]["content"].strip()
        lowered = explanation.lower()

        if any(x in lowered for x in ["false", "myth", "incorrect", "not true"]):
            ai_fake = 0.9
        elif any(x in lowered for x in ["true", "correct", "accurate", "valid"]):
            ai_fake = 0.1
        else:
            ai_fake = 0.5

        return ai_fake, explanation

    except Exception as e:
        return None, f"AI error (Cerebras): {e}"
