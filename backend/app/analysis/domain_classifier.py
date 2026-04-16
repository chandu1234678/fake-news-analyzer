"""
Domain Classifier - Detect claim domain for specialized analysis

Classifies claims into domains:
- medical: Health, COVID-19, vaccines, medical treatments
- climate: Climate change, environment, weather
- political: Elections, politicians, government, policies
- general: Everything else

Uses keyword-based classification (fast) with optional ML classifier.
"""

import logging
import re
from typing import Tuple, Dict, List

logger = logging.getLogger(__name__)

# Domain keywords
MEDICAL_KEYWORDS = [
    'covid', 'vaccine', 'virus', 'disease', 'health', 'medical', 'doctor',
    'hospital', 'treatment', 'cure', 'medicine', 'drug', 'pandemic',
    'symptom', 'infection', 'patient', 'diagnosis', 'therapy', 'cancer',
    'heart disease', 'diabetes', 'who', 'cdc', 'fda', 'clinical trial'
]

CLIMATE_KEYWORDS = [
    'climate', 'global warming', 'greenhouse', 'carbon', 'emission',
    'temperature', 'weather', 'environment', 'pollution', 'renewable',
    'fossil fuel', 'ice cap', 'sea level', 'drought', 'flood',
    'hurricane', 'wildfire', 'deforestation', 'sustainability',
    'ipcc', 'paris agreement', 'carbon footprint', 'green energy'
]

POLITICAL_KEYWORDS = [
    'election', 'vote', 'politician', 'president', 'congress', 'senate',
    'government', 'policy', 'law', 'legislation', 'campaign', 'party',
    'democrat', 'republican', 'liberal', 'conservative', 'parliament',
    'minister', 'prime minister', 'political', 'ballot', 'referendum',
    'impeachment', 'scandal', 'corruption', 'lobby', 'bill', 'amendment'
]


def classify_domain(text: str) -> Tuple[str, float, Dict[str, float]]:
    """
    Classify claim domain using keyword matching
    
    Args:
        text: Claim text to classify
        
    Returns:
        (domain, confidence, scores)
        domain: 'medical', 'climate', 'political', or 'general'
        confidence: 0-1 confidence score
        scores: Dict of domain scores
    """
    text_lower = text.lower()
    
    # Count keyword matches for each domain
    medical_score = sum(1 for kw in MEDICAL_KEYWORDS if kw in text_lower)
    climate_score = sum(1 for kw in CLIMATE_KEYWORDS if kw in text_lower)
    political_score = sum(1 for kw in POLITICAL_KEYWORDS if kw in text_lower)
    
    # Normalize scores
    total = medical_score + climate_score + political_score
    
    if total == 0:
        return 'general', 1.0, {
            'medical': 0.0,
            'climate': 0.0,
            'political': 0.0,
            'general': 1.0
        }
    
    # Calculate probabilities
    medical_prob = medical_score / total
    climate_prob = climate_score / total
    political_prob = political_score / total
    
    # Determine domain (threshold: 0.4)
    if medical_prob >= 0.4:
        domain = 'medical'
        confidence = medical_prob
    elif climate_prob >= 0.4:
        domain = 'climate'
        confidence = climate_prob
    elif political_prob >= 0.4:
        domain = 'political'
        confidence = political_prob
    else:
        domain = 'general'
        confidence = 1.0 - max(medical_prob, climate_prob, political_prob)
    
    scores = {
        'medical': round(medical_prob, 3),
        'climate': round(climate_prob, 3),
        'political': round(political_prob, 3),
        'general': round(1.0 - (medical_prob + climate_prob + political_prob), 3)
    }
    
    logger.info(f"Domain classified: {domain} (confidence: {confidence:.3f})")
    
    return domain, round(confidence, 3), scores


def get_domain_specific_context(domain: str) -> Dict[str, any]:
    """
    Get domain-specific context for analysis
    
    Args:
        domain: Domain name
        
    Returns:
        Dict with domain-specific information
    """
    contexts = {
        'medical': {
            'trusted_sources': [
                'who.int', 'cdc.gov', 'nih.gov', 'nejm.org', 'thelancet.com',
                'bmj.com', 'jamanetwork.com', 'nature.com/nm', 'cell.com'
            ],
            'red_flags': [
                'miracle cure', 'doctors hate', 'big pharma hiding',
                'natural remedy cures all', 'government suppressing',
                'one weird trick', 'toxins', 'detox', 'cleanse'
            ],
            'verification_tips': [
                'Check peer-reviewed journals',
                'Verify with WHO/CDC guidelines',
                'Look for clinical trial data',
                'Consult medical professionals'
            ]
        },
        'climate': {
            'trusted_sources': [
                'ipcc.ch', 'climate.nasa.gov', 'noaa.gov', 'nature.com',
                'science.org', 'carbonbrief.org', 'skepticalscience.com'
            ],
            'red_flags': [
                'climate hoax', 'scientists lying', 'global cooling',
                'ice age coming', 'sun cycles explain all',
                'co2 is good', 'climate always changes'
            ],
            'verification_tips': [
                'Check IPCC reports',
                'Review peer-reviewed climate science',
                'Verify with NASA/NOAA data',
                'Look for scientific consensus'
            ]
        },
        'political': {
            'trusted_sources': [
                'apnews.com', 'reuters.com', 'bbc.com', 'npr.org',
                'politifact.com', 'factcheck.org', 'snopes.com'
            ],
            'red_flags': [
                'deep state', 'rigged election', 'fake news media',
                'they don\'t want you to know', 'wake up sheeple',
                'mainstream media hiding', 'conspiracy'
            ],
            'verification_tips': [
                'Check multiple news sources',
                'Verify with fact-checking sites',
                'Look for primary sources',
                'Check official government statements'
            ]
        },
        'general': {
            'trusted_sources': [
                'reuters.com', 'apnews.com', 'bbc.com', 'nytimes.com',
                'washingtonpost.com', 'theguardian.com', 'npr.org'
            ],
            'red_flags': [
                'shocking', 'you won\'t believe', 'share before deleted',
                'they don\'t want you to know', 'mainstream media hiding'
            ],
            'verification_tips': [
                'Check multiple reliable sources',
                'Look for original sources',
                'Verify dates and context',
                'Check fact-checking websites'
            ]
        }
    }
    
    return contexts.get(domain, contexts['general'])


def enhance_analysis_with_domain(text: str, base_analysis: Dict) -> Dict:
    """
    Enhance fact-check analysis with domain-specific insights
    
    Args:
        text: Claim text
        base_analysis: Base fact-check results
        
    Returns:
        Enhanced analysis with domain insights
    """
    domain, confidence, scores = classify_domain(text)
    context = get_domain_specific_context(domain)
    
    # Add domain information to analysis
    enhanced = base_analysis.copy()
    enhanced['domain'] = {
        'category': domain,
        'confidence': confidence,
        'scores': scores,
        'trusted_sources': context['trusted_sources'],
        'red_flags_detected': [
            flag for flag in context['red_flags']
            if flag.lower() in text.lower()
        ],
        'verification_tips': context['verification_tips']
    }
    
    return enhanced


# Example usage
if __name__ == "__main__":
    print("Domain Classifier Test")
    print("="*70)
    
    test_claims = [
        "New COVID-19 vaccine shows 95% efficacy in clinical trials",
        "Climate change causing record temperatures worldwide",
        "Election results show unexpected voter turnout",
        "Breaking news: Celebrity announces new movie project"
    ]
    
    for claim in test_claims:
        print(f"\nClaim: {claim[:60]}...")
        domain, confidence, scores = classify_domain(claim)
        print(f"  Domain: {domain} (confidence: {confidence:.3f})")
        print(f"  Scores: {scores}")
        
        context = get_domain_specific_context(domain)
        print(f"  Trusted sources: {len(context['trusted_sources'])}")
        print(f"  Red flags: {len(context['red_flags'])}")
