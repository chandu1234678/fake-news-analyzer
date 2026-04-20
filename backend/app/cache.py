"""
Redis Cache Layer

Multi-layer caching for predictions, evidence, and analysis results.
Reduces latency and API costs by caching expensive operations.
"""

import os
import json
import hashlib
import logging
from typing import Optional, Any, Dict
from datetime import timedelta
import redis
from functools import wraps

logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"

# TTL configuration (in seconds)
TTL_PREDICTION = 24 * 60 * 60  # 24 hours for predictions
TTL_EVIDENCE = 60 * 60  # 1 hour for evidence
TTL_AI_ANALYSIS = 60 * 60  # 1 hour for AI analysis
TTL_SHAP = 2 * 60 * 60  # 2 hours for SHAP explanations
TTL_IMAGE = 60 * 60  # 1 hour for image analysis


class CacheManager:
    """Manages Redis cache connections and operations"""
    
    def __init__(self):
        self.client = None
        self.enabled = REDIS_ENABLED
        
        if self.enabled:
            try:
                self.client = redis.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # Test connection
                self.client.ping()
                logger.info("Redis cache connected successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed, caching disabled: {e}")
                self.enabled = False
                self.client = None
    
    def is_available(self) -> bool:
        """Check if cache is available"""
        return self.enabled and self.client is not None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.is_available():
            return None
        
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = TTL_PREDICTION) -> bool:
        """Set value in cache with TTL"""
        if not self.is_available():
            return False
        
        try:
            serialized = json.dumps(value)
            self.client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.is_available():
            return False
        
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.is_available():
            return 0
        
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete pattern failed for {pattern}: {e}")
            return 0
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter"""
        if not self.is_available():
            return None
        
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            logger.warning(f"Cache increment failed for key {key}: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.is_available():
            return {
                "enabled": False,
                "connected": False
            }
        
        try:
            info = self.client.info("stats")
            return {
                "enabled": True,
                "connected": True,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                ),
                "keys": self.client.dbsize(),
                "memory_used": info.get("used_memory_human", "0"),
            }
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {
                "enabled": True,
                "connected": False,
                "error": str(e)
            }
    
    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate"""
        total = hits + misses
        if total == 0:
            return 0.0
        return round(hits / total, 3)


# Global cache manager instance
cache = CacheManager()


# ── Cache Key Generators ──────────────────────────────────────

def generate_claim_hash(text: str) -> str:
    """Generate consistent hash for claim text"""
    normalized = text.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def prediction_key(claim_text: str, user_id: Optional[int] = None) -> str:
    """Generate cache key for prediction"""
    claim_hash = generate_claim_hash(claim_text)
    if user_id:
        return f"pred:{claim_hash}:u{user_id}"
    return f"pred:{claim_hash}"


def evidence_key(claim_text: str) -> str:
    """Generate cache key for evidence"""
    claim_hash = generate_claim_hash(claim_text)
    return f"evidence:{claim_hash}"


def ai_analysis_key(claim_text: str) -> str:
    """Generate cache key for AI analysis"""
    claim_hash = generate_claim_hash(claim_text)
    return f"ai:{claim_hash}"


def shap_key(claim_text: str, model_version: str = "1.0") -> str:
    """Generate cache key for SHAP explanation"""
    claim_hash = generate_claim_hash(claim_text)
    return f"shap:{model_version}:{claim_hash}"


def image_key(image_url: str) -> str:
    """Generate cache key for image analysis"""
    url_hash = hashlib.sha256(image_url.encode()).hexdigest()
    return f"image:{url_hash}"


# ── Cache Decorators ──────────────────────────────────────────

def cached_prediction(ttl: int = TTL_PREDICTION):
    """Decorator to cache prediction results"""
    def decorator(func):
        @wraps(func)
        def wrapper(claim_text: str, *args, **kwargs):
            # Try to get from cache
            key = prediction_key(claim_text)
            cached_result = cache.get(key)
            
            if cached_result is not None:
                logger.debug(f"Cache hit for prediction: {key}")
                cache.increment("cache:prediction:hits")
                return cached_result
            
            # Cache miss - compute result
            logger.debug(f"Cache miss for prediction: {key}")
            cache.increment("cache:prediction:misses")
            result = func(claim_text, *args, **kwargs)
            
            # Store in cache
            if result is not None:
                cache.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator


def cached_evidence(ttl: int = TTL_EVIDENCE):
    """Decorator to cache evidence results"""
    def decorator(func):
        @wraps(func)
        def wrapper(claim_text: str, *args, **kwargs):
            # Try to get from cache
            key = evidence_key(claim_text)
            cached_result = cache.get(key)
            
            if cached_result is not None:
                logger.debug(f"Cache hit for evidence: {key}")
                cache.increment("cache:evidence:hits")
                return cached_result
            
            # Cache miss - compute result
            logger.debug(f"Cache miss for evidence: {key}")
            cache.increment("cache:evidence:misses")
            result = func(claim_text, *args, **kwargs)
            
            # Store in cache
            if result is not None:
                cache.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator


def cached_ai_analysis(ttl: int = TTL_AI_ANALYSIS):
    """Decorator to cache AI analysis results"""
    def decorator(func):
        @wraps(func)
        def wrapper(claim_text: str, *args, **kwargs):
            # Try to get from cache
            key = ai_analysis_key(claim_text)
            cached_result = cache.get(key)
            
            if cached_result is not None:
                logger.debug(f"Cache hit for AI analysis: {key}")
                cache.increment("cache:ai:hits")
                return cached_result
            
            # Cache miss - compute result
            logger.debug(f"Cache miss for AI analysis: {key}")
            cache.increment("cache:ai:misses")
            result = func(claim_text, *args, **kwargs)
            
            # Store in cache
            if result is not None:
                cache.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator


# ── Cache Invalidation ────────────────────────────────────────

def invalidate_model_cache(model_version: str):
    """Invalidate all caches when model is updated"""
    logger.info(f"Invalidating cache for model version: {model_version}")
    
    # Delete all prediction caches
    deleted = cache.delete_pattern("pred:*")
    logger.info(f"Deleted {deleted} prediction cache entries")
    
    # Delete all SHAP caches for this model version
    deleted = cache.delete_pattern(f"shap:{model_version}:*")
    logger.info(f"Deleted {deleted} SHAP cache entries")
    
    return deleted


def invalidate_claim_cache(claim_text: str):
    """Invalidate cache for a specific claim"""
    claim_hash = generate_claim_hash(claim_text)
    
    # Delete prediction cache
    cache.delete_pattern(f"pred:{claim_hash}*")
    
    # Delete evidence cache
    cache.delete(evidence_key(claim_text))
    
    # Delete AI analysis cache
    cache.delete(ai_analysis_key(claim_text))
    
    # Delete SHAP cache
    cache.delete_pattern(f"shap:*:{claim_hash}")
    
    logger.info(f"Invalidated cache for claim: {claim_text[:50]}...")


# ── Partial Caching ───────────────────────────────────────────

class PartialCache:
    """Cache individual pipeline components separately"""
    
    @staticmethod
    def get_ml_score(claim_text: str) -> Optional[float]:
        """Get cached ML score"""
        key = f"ml:{generate_claim_hash(claim_text)}"
        result = cache.get(key)
        return result.get("score") if result else None
    
    @staticmethod
    def set_ml_score(claim_text: str, score: float, ttl: int = TTL_PREDICTION):
        """Cache ML score"""
        key = f"ml:{generate_claim_hash(claim_text)}"
        cache.set(key, {"score": score}, ttl)
    
    @staticmethod
    def get_ai_score(claim_text: str) -> Optional[Dict[str, Any]]:
        """Get cached AI score and explanation"""
        key = ai_analysis_key(claim_text)
        return cache.get(key)
    
    @staticmethod
    def set_ai_score(claim_text: str, score: float, explanation: str, ttl: int = TTL_AI_ANALYSIS):
        """Cache AI score and explanation"""
        key = ai_analysis_key(claim_text)
        cache.set(key, {"score": score, "explanation": explanation}, ttl)
    
    @staticmethod
    def get_evidence(claim_text: str) -> Optional[Dict[str, Any]]:
        """Get cached evidence"""
        key = evidence_key(claim_text)
        return cache.get(key)
    
    @staticmethod
    def set_evidence(claim_text: str, evidence_data: Dict[str, Any], ttl: int = TTL_EVIDENCE):
        """Cache evidence"""
        key = evidence_key(claim_text)
        cache.set(key, evidence_data, ttl)
    
    @staticmethod
    def get_shap(claim_text: str, model_version: str = "1.0") -> Optional[Dict[str, Any]]:
        """Get cached SHAP explanation"""
        key = shap_key(claim_text, model_version)
        return cache.get(key)
    
    @staticmethod
    def set_shap(claim_text: str, shap_data: Dict[str, Any], model_version: str = "1.0", ttl: int = TTL_SHAP):
        """Cache SHAP explanation"""
        key = shap_key(claim_text, model_version)
        cache.set(key, shap_data, ttl)
    
    @staticmethod
    def get_image_analysis(image_url: str) -> Optional[Dict[str, Any]]:
        """Get cached image analysis"""
        key = image_key(image_url)
        return cache.get(key)
    
    @staticmethod
    def set_image_analysis(image_url: str, analysis_data: Dict[str, Any], ttl: int = TTL_IMAGE):
        """Cache image analysis"""
        key = image_key(image_url)
        cache.set(key, analysis_data, ttl)


# Initialize partial cache helper
partial_cache = PartialCache()


# ── Query Result Caching ─────────────────────────────────────

TTL_ANALYTICS = 5 * 60  # 5 minutes


def analytics_key(endpoint: str, **params: Any) -> str:
    """Generate a stable cache key for analytics endpoints."""
    normalized = "|".join(f"{k}={params[k]}" for k in sorted(params.keys()))
    payload = f"{endpoint}|{normalized}"
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"analytics:{endpoint}:{digest}"


def get_or_set_query_result(
    key: str,
    query_fn,
    ttl: int = TTL_ANALYTICS,
):
    """Return cached query result or execute and cache it."""
    cached_result = cache.get(key)
    if cached_result is not None:
        cache.increment("cache:query:hits")
        return cached_result

    cache.increment("cache:query:misses")
    result = query_fn()
    if result is not None:
        cache.set(key, result, ttl)
    return result
