"""
Multi-language Support

Detects the language of input text and translates non-English claims
to English before fact-checking. Uses:
1. langdetect for language detection (no API key)
2. Gemini/Groq for translation (uses existing LLM keys)

Supported: any language the LLMs can handle (100+)
"""
import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

# ISO 639-1 language names for logging/display
_LANG_NAMES = {
    "en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French",
    "de": "German",  "ar": "Arabic", "zh": "Chinese", "pt": "Portuguese",
    "ru": "Russian", "ja": "Japanese", "ko": "Korean", "it": "Italian",
    "nl": "Dutch",   "tr": "Turkish", "pl": "Polish",  "vi": "Vietnamese",
    "th": "Thai",    "id": "Indonesian", "ur": "Urdu", "bn": "Bengali",
    "ta": "Tamil",   "te": "Telugu",  "ml": "Malayalam", "mr": "Marathi",
}

_TRANSLATE_PROMPT = (
    "Translate the following text to English. "
    "Return ONLY the translated text, nothing else.\n\n"
    "Text: {text}"
)


def detect_language(text: str) -> str:
    """
    Detect language of text. Returns ISO 639-1 code (e.g. 'en', 'hi').
    Falls back to 'en' if detection fails.
    """
    try:
        from langdetect import detect
        lang = detect(text)
        return lang
    except Exception:
        pass

    # Fallback: simple heuristic — check for non-ASCII characters
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
    if ascii_ratio < 0.7:
        return "unknown"
    return "en"


def translate_to_english(text: str, source_lang: str = "auto") -> Tuple[str, str]:
    """
    Translate text to English using available LLM.

    Returns:
        (translated_text, source_language_name)
    """
    lang_name = _LANG_NAMES.get(source_lang, source_lang.upper())
    prompt = _TRANSLATE_PROMPT.format(text=text[:1000])
    messages = [{"role": "user", "content": prompt}]

    try:
        from app.analysis.chat import _call_openai_compat, _call_gemini, _get_keys, _first_success
        keys = _get_keys()
        fns = []
        if keys.get("gemini"):
            fns.append(("Gemini", lambda: _call_gemini(messages, max_tokens=500, temperature=0)))
        if keys.get("groq"):
            fns.append(("Groq", lambda: _call_openai_compat(
                "https://api.groq.com/openai/v1/chat/completions",
                keys["groq"], "llama3-8b-8192", messages, max_tokens=500, temperature=0
            )))
        if keys.get("cerebras"):
            fns.append(("Cerebras", lambda: _call_openai_compat(
                "https://api.cerebras.ai/v1/chat/completions",
                keys["cerebras"], "llama3.1-8b", messages, max_tokens=500, temperature=0
            )))

        if fns:
            translated = _first_success(fns)
            logger.info("Translated from %s to English", lang_name)
            return translated.strip(), lang_name
    except Exception as e:
        logger.warning("Translation failed: %s", e)

    return text, lang_name  # return original if translation fails


def normalize_claim(text: str) -> Tuple[str, str, bool]:
    """
    Detect language and translate to English if needed.

    Returns:
        (normalized_text, detected_language_name, was_translated)
    """
    lang = detect_language(text)

    if lang == "en" or lang == "unknown":
        return text, "English", False

    # Non-English — translate
    translated, lang_name = translate_to_english(text, lang)
    return translated, lang_name, True
