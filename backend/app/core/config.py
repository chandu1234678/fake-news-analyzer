from dotenv import load_dotenv, find_dotenv
import os

# Explicitly load .env relative to this file's location
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(_env_path)

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not any([CEREBRAS_API_KEY, GROQ_API_KEY, GEMINI_API_KEY]):
    raise RuntimeError("At least one of CEREBRAS_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY must be set")
