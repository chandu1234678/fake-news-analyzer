"""
Adversarial Test Set Generator

Uses LLM to generate paraphrased / misleading variants of real claims
to test system robustness under distribution shift.

Generates:
  1. Paraphrased fake claims (same meaning, different wording)
  2. Partial truths (mostly true but with one false detail)
  3. Misleading headlines (true fact, misleading framing)

Output: backend/training/adversarial_test.csv

Run: python backend/training/gen_adversarial.py
"""

import os
import sys
import json
import csv
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_KEY = os.getenv("GROQ_API_KEY", "")

SEED_CLAIMS = [
    ("The COVID-19 vaccine contains microchips for tracking people.", "fake"),
    ("Scientists have confirmed that the Earth is flat.", "fake"),
    ("Drinking bleach cures cancer according to new research.", "fake"),
    ("NASA confirmed the moon landing was filmed in a studio.", "fake"),
    ("5G towers spread the coronavirus.", "fake"),
    ("The Great Wall of China is visible from space with the naked eye.", "fake"),
    ("Scientists discovered water on Mars in 2015.", "real"),
    ("The Eiffel Tower grows taller in summer due to thermal expansion.", "real"),
    ("Humans share about 60% of their DNA with bananas.", "real"),
    ("The Amazon rainforest produces 20% of the world's oxygen.", "real"),
]

PROMPT_TEMPLATE = """Given this claim and its label, generate 3 adversarial variants:
1. Paraphrase: same meaning, completely different wording
2. Partial truth: change one key detail to make it subtly wrong
3. Misleading frame: true facts but framed to imply something false

Claim: "{claim}"
Label: {label}

Respond with ONLY a JSON array of 3 objects:
[
  {{"type": "paraphrase", "text": "...", "label": "{label}"}},
  {{"type": "partial_truth", "text": "...", "label": "fake"}},
  {{"type": "misleading_frame", "text": "...", "label": "fake"}}
]"""


def generate_variants(claim: str, label: str) -> list:
    if not GROQ_KEY:
        print("⚠️  GROQ_API_KEY not set, skipping LLM generation")
        return []
    try:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": PROMPT_TEMPLATE.format(claim=claim, label=label)}],
                "temperature": 0.7,
                "max_tokens": 500,
            },
            timeout=20,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()
        # Extract JSON array
        import re
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"  ⚠️  Failed for '{claim[:40]}...': {e}")
    return []


def main():
    out_path = os.path.join(os.path.dirname(__file__), "adversarial_test.csv")
    rows = []

    for claim, label in SEED_CLAIMS:
        print(f"Generating variants for: {claim[:60]}...")
        variants = generate_variants(claim, label)
        # Always include original
        rows.append({"type": "original", "text": claim, "label": label})
        for v in variants:
            if isinstance(v, dict) and "text" in v and "label" in v:
                rows.append(v)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "text", "label"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Generated {len(rows)} adversarial samples → {out_path}")
    print(f"   Original: {sum(1 for r in rows if r['type']=='original')}")
    print(f"   Variants: {sum(1 for r in rows if r['type']!='original')}")


if __name__ == "__main__":
    main()
