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
                    "You are a fact-checking assistant. "
                    "Decide if a claim is true or false and explain briefly."
                )
            },
            {
                "role": "user",
                "content": f"Claim: {text}"
            }
        ],
        "temperature": 0.2,
        "max_tokens": 200
    }

    try:
        r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=10)
        r.raise_for_status()

        content = r.json()["choices"][0]["message"]["content"]
        explanation = content.strip()

        lowered = explanation.lower()
        ai_fake = 0.85 if any(x in lowered for x in ["false", "not true", "incorrect", "myth"]) else 0.15

        return ai_fake, explanation

    except Exception as e:
        return None, f"AI error (Cerebras): {str(e)}"
