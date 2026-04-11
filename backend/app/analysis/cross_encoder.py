"""
Level 70 — Cross-Encoder Evidence Reranking

Reranks NewsAPI articles by semantic relevance to the claim using
a lightweight cross-encoder approach via LLM scoring.

This replaces the simple keyword stance classifier with actual
semantic understanding of claim-article relevance.
"""
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

_RERANK_PROMPT = """Given this claim and news article, score the article's relevance and stance.

Claim: {claim}

Article title: {title}
Article description: {description}

Respond with ONLY a JSON object:
{{"relevance": <0.0-1.0>, "stance": "support"|"contradict"|"neutral", "reason": "<10 words max>"}}"""


def _score_article(claim: str, article: dict) -> Optional[dict]:
    """Score a single article against the claim using LLM."""
    try:
        from app.analysis.chat import _call_openai_compat, _call_gemini, _get_keys, _first_success
        import json, re

        keys = _get_keys()
        prompt = _RERANK_PROMPT.format(
            claim=claim[:300],
            title=article.get("title", "")[:200],
            description=article.get("description", "")[:300],
        )
        messages = [{"role": "user", "content": prompt}]

        fns = []
        if keys.get("cerebras"):
            fns.append(("Cerebras", lambda: _call_openai_compat(
                "https://api.cerebras.ai/v1/chat/completions",
                keys["cerebras"], "llama3.1-8b", messages, max_tokens=80, temperature=0
            )))
        if keys.get("groq"):
            fns.append(("Groq", lambda: _call_openai_compat(
                "https://api.groq.com/openai/v1/chat/completions",
                keys["groq"], "llama3-8b-8192", messages, max_tokens=80, temperature=0
            )))

        if not fns:
            return None

        raw = _first_success(fns)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return {
                "relevance": float(data.get("relevance", 0.5)),
                "stance":    data.get("stance", "neutral"),
                "reason":    data.get("reason", ""),
            }
    except Exception as e:
        logger.debug("Cross-encoder scoring failed: %s", e)
    return None


def rerank_articles(claim: str, articles: list, top_k: int = 5) -> list:
    """
    Rerank articles by semantic relevance to the claim.

    For each article, uses LLM to score relevance (0-1) and stance.
    Returns top_k most relevant articles with updated stance scores.

    Falls back to original order if LLM unavailable.
    """
    if not articles or len(articles) <= 1:
        return articles

    # Only rerank if we have more articles than top_k (otherwise no point)
    if len(articles) <= top_k:
        return articles

    scored = []
    # Run scoring in parallel — max 3 concurrent LLM calls
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_score_article, claim, a): i for i, a in enumerate(articles)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                score = future.result()
                if score:
                    articles[idx]["relevance_score"] = score["relevance"]
                    articles[idx]["stance"]          = score["stance"]  # override keyword stance
                    articles[idx]["stance_reason"]   = score["reason"]
                    scored.append((score["relevance"], articles[idx]))
                else:
                    scored.append((0.5, articles[idx]))
            except Exception:
                scored.append((0.5, articles[idx]))

    # Sort by relevance descending
    scored.sort(key=lambda x: x[0], reverse=True)
    reranked = [a for _, a in scored[:top_k]]

    logger.debug("Cross-encoder reranked %d → %d articles", len(articles), len(reranked))
    return reranked
