from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY missing from environment")

if not GEMINI_MODEL:
    raise RuntimeError("GEMINI_MODEL missing from environment")
