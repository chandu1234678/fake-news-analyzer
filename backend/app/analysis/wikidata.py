"""
Level 90 — Wikidata Entity Verification

Extracts named entities from a claim and verifies them against Wikidata.
Free, no API key required.

Returns: list of entity verification results with consistency flags.
"""
import re
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_SEARCH = "https://www.wikidata.org/w/api.php"

_session = requests.Session()
_session.headers.update({"User-Agent": "FactCheckerAI/2.0 (fact-checking research)"})

# Simple NER patterns — catches most claim entities without spaCy dependency
_PERSON_RE  = re.compile(r'\b([A-Z][a-z]+ (?:[A-Z][a-z]+ )*[A-Z][a-z]+)\b')
_ORG_RE     = re.compile(r'\b((?:the )?(?:US|UK|UN|EU|WHO|CDC|NASA|FBI|CIA|NATO|[A-Z]{2,6}))\b')
_YEAR_RE    = re.compile(r'\b((?:19|20)\d{2})\b')
_NUMBER_RE  = re.compile(r'\b(\d[\d,]*(?:\.\d+)?(?:\s*(?:million|billion|trillion|percent|%))?)\b', re.IGNORECASE)


def _search_entity(name: str) -> Optional[dict]:
    """Search Wikidata for an entity by name, return first result."""
    try:
        r = _session.get(WIKIDATA_SEARCH, params={
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "limit": 1,
            "format": "json",
        }, timeout=5)
        results = r.json().get("search", [])
        if results:
            return {"id": results[0]["id"], "label": results[0].get("label", name), "description": results[0].get("description", "")}
    except Exception as e:
        logger.debug("Wikidata search failed for '%s': %s", name, e)
    return None


def _get_entity_facts(entity_id: str) -> dict:
    """Get key facts about a Wikidata entity."""
    try:
        query = f"""
        SELECT ?prop ?propLabel ?value ?valueLabel WHERE {{
          wd:{entity_id} ?prop ?value .
          ?propEntity wikibase:directClaim ?prop .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
        }} LIMIT 10
        """
        r = _session.get(WIKIDATA_SPARQL, params={"query": query, "format": "json"}, timeout=8)
        bindings = r.json().get("results", {}).get("bindings", [])
        facts = {}
        for b in bindings:
            prop  = b.get("propLabel", {}).get("value", "")
            value = b.get("valueLabel", {}).get("value", "")
            if prop and value and not prop.startswith("P"):
                facts[prop] = value
        return facts
    except Exception:
        return {}


def extract_entities(text: str) -> dict:
    """Extract named entities from claim text."""
    persons = list(set(_PERSON_RE.findall(text)))[:3]
    orgs    = list(set(_ORG_RE.findall(text)))[:3]
    years   = list(set(_YEAR_RE.findall(text)))[:3]
    numbers = list(set(_NUMBER_RE.findall(text)))[:3]
    return {"persons": persons, "orgs": orgs, "years": years, "numbers": numbers}


def verify_entities(text: str) -> list:
    """
    Verify named entities in the claim against Wikidata.

    Returns list of dicts:
      {"entity": str, "found": bool, "description": str, "flag": str|None}
    """
    entities = extract_entities(text)
    results  = []

    # Only verify persons and orgs — years/numbers checked differently
    candidates = entities["persons"][:2] + entities["orgs"][:2]

    for name in candidates:
        if len(name) < 3:
            continue
        entity = _search_entity(name)
        if entity:
            results.append({
                "entity":      name,
                "found":       True,
                "wikidata_id": entity["id"],
                "description": entity["description"][:120] if entity["description"] else "",
                "flag":        None,
            })
        else:
            # Entity not found in Wikidata — could be fabricated
            results.append({
                "entity":      name,
                "found":       False,
                "wikidata_id": None,
                "description": "Not found in Wikidata",
                "flag":        "unverified_entity",
            })

    return results


def get_entity_risk_score(verifications: list) -> float:
    """
    Returns 0.0–1.0 risk score based on entity verification.
    Higher = more suspicious (unverified entities).
    """
    if not verifications:
        return 0.0
    unverified = sum(1 for v in verifications if not v["found"])
    return round(unverified / len(verifications), 2)
