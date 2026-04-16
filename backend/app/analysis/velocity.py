"""
Velocity Tracking - Rapid Spread Detection

Tracks claim frequency in sliding time windows to detect viral misinformation.
Uses in-memory storage for development, Redis for production.

Time Windows:
- 5 minutes: Viral spike detection
- 1 hour: Trending detection  
- 24 hours: Baseline calculation

Velocity Score: Normalized 0-1 based on frequency vs baseline
"""

import time
import hashlib
import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Time windows in seconds
WINDOW_5MIN = 5 * 60
WINDOW_1HR = 60 * 60
WINDOW_24HR = 24 * 60 * 60

# Baseline thresholds (claims per window for "normal" content)
BASELINE_5MIN = 5      # 5 claims in 5 min = normal
BASELINE_1HR = 50      # 50 claims in 1 hr = normal
BASELINE_24HR = 500    # 500 claims in 24 hr = normal

# Multipliers for viral detection
VIRAL_MULTIPLIER = 10  # 10x baseline = viral


class VelocityTracker:
    """
    In-memory velocity tracker with sliding time windows
    
    For production, replace with Redis:
    - ZADD claim_hash timestamp
    - ZCOUNT claim_hash min_time max_time
    - ZREMRANGEBYSCORE claim_hash -inf old_time
    """
    
    def __init__(self):
        # claim_hash -> deque of timestamps
        self.claims: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.last_cleanup = time.time()
        self.cleanup_interval = 3600  # Clean up every hour
    
    def track_claim(self, text: str) -> Dict[str, any]:
        """
        Track a claim and return velocity metrics
        
        Args:
            text: Claim text to track
            
        Returns:
            {
                'claim_hash': str,
                'count_5min': int,
                'count_1hr': int,
                'count_24hr': int,
                'velocity_5min': float (0-1),
                'velocity_1hr': float (0-1),
                'velocity_24hr': float (0-1),
                'velocity_score': float (0-1),
                'is_viral': bool,
                'is_trending': bool
            }
        """
        # Generate claim hash
        claim_hash = self._hash_claim(text)
        current_time = time.time()
        
        # Add timestamp
        self.claims[claim_hash].append(current_time)
        
        # Calculate counts in each window
        count_5min = self._count_in_window(claim_hash, WINDOW_5MIN, current_time)
        count_1hr = self._count_in_window(claim_hash, WINDOW_1HR, current_time)
        count_24hr = self._count_in_window(claim_hash, WINDOW_24HR, current_time)
        
        # Normalize velocity scores (0-1)
        velocity_5min = min(count_5min / (BASELINE_5MIN * VIRAL_MULTIPLIER), 1.0)
        velocity_1hr = min(count_1hr / (BASELINE_1HR * VIRAL_MULTIPLIER), 1.0)
        velocity_24hr = min(count_24hr / (BASELINE_24HR * VIRAL_MULTIPLIER), 1.0)
        
        # Overall velocity score (weighted average, emphasize recent)
        velocity_score = (
            velocity_5min * 0.5 +    # 50% weight on 5-min (most recent)
            velocity_1hr * 0.3 +      # 30% weight on 1-hr
            velocity_24hr * 0.2       # 20% weight on 24-hr
        )
        
        # Viral detection: 5-min rate >> 24-hr average
        is_viral = count_5min > (BASELINE_5MIN * VIRAL_MULTIPLIER)
        
        # Trending: 1-hr rate significantly above baseline
        is_trending = count_1hr > (BASELINE_1HR * 3)
        
        # Periodic cleanup
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(current_time)
        
        result = {
            'claim_hash': claim_hash,
            'count_5min': count_5min,
            'count_1hr': count_1hr,
            'count_24hr': count_24hr,
            'velocity_5min': round(velocity_5min, 3),
            'velocity_1hr': round(velocity_1hr, 3),
            'velocity_24hr': round(velocity_24hr, 3),
            'velocity_score': round(velocity_score, 3),
            'is_viral': is_viral,
            'is_trending': is_trending,
            'timestamp': current_time
        }
        
        if is_viral:
            logger.warning(f"VIRAL CLAIM DETECTED: {claim_hash[:16]}... "
                          f"({count_5min} in 5min, {count_1hr} in 1hr)")
        elif is_trending:
            logger.info(f"Trending claim: {claim_hash[:16]}... "
                       f"({count_1hr} in 1hr)")
        
        return result
    
    def get_velocity(self, text: str) -> Optional[Dict[str, any]]:
        """
        Get velocity metrics without tracking (read-only)
        
        Args:
            text: Claim text
            
        Returns:
            Velocity metrics or None if not tracked
        """
        claim_hash = self._hash_claim(text)
        
        if claim_hash not in self.claims or not self.claims[claim_hash]:
            return None
        
        current_time = time.time()
        
        count_5min = self._count_in_window(claim_hash, WINDOW_5MIN, current_time)
        count_1hr = self._count_in_window(claim_hash, WINDOW_1HR, current_time)
        count_24hr = self._count_in_window(claim_hash, WINDOW_24HR, current_time)
        
        velocity_5min = min(count_5min / (BASELINE_5MIN * VIRAL_MULTIPLIER), 1.0)
        velocity_1hr = min(count_1hr / (BASELINE_1HR * VIRAL_MULTIPLIER), 1.0)
        velocity_24hr = min(count_24hr / (BASELINE_24HR * VIRAL_MULTIPLIER), 1.0)
        
        velocity_score = (
            velocity_5min * 0.5 +
            velocity_1hr * 0.3 +
            velocity_24hr * 0.2
        )
        
        return {
            'claim_hash': claim_hash,
            'count_5min': count_5min,
            'count_1hr': count_1hr,
            'count_24hr': count_24hr,
            'velocity_score': round(velocity_score, 3),
            'is_viral': count_5min > (BASELINE_5MIN * VIRAL_MULTIPLIER),
            'is_trending': count_1hr > (BASELINE_1HR * 3)
        }
    
    def _hash_claim(self, text: str) -> str:
        """Generate consistent hash for claim text"""
        # Normalize: lowercase, strip, remove extra spaces
        normalized = ' '.join(text.lower().strip().split())
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def _count_in_window(self, claim_hash: str, window_seconds: int, 
                        current_time: float) -> int:
        """Count occurrences within time window"""
        if claim_hash not in self.claims:
            return 0
        
        cutoff_time = current_time - window_seconds
        timestamps = self.claims[claim_hash]
        
        # Count timestamps after cutoff
        count = sum(1 for ts in timestamps if ts >= cutoff_time)
        return count
    
    def _cleanup_old_entries(self, current_time: float):
        """Remove timestamps older than 24 hours"""
        cutoff_time = current_time - WINDOW_24HR
        
        for claim_hash in list(self.claims.keys()):
            timestamps = self.claims[claim_hash]
            
            # Remove old timestamps
            while timestamps and timestamps[0] < cutoff_time:
                timestamps.popleft()
            
            # Remove empty entries
            if not timestamps:
                del self.claims[claim_hash]
        
        self.last_cleanup = current_time
        logger.info(f"Velocity tracker cleanup: {len(self.claims)} active claims")
    
    def get_stats(self) -> Dict[str, any]:
        """Get tracker statistics"""
        current_time = time.time()
        
        total_claims = len(self.claims)
        total_timestamps = sum(len(ts) for ts in self.claims.values())
        
        # Count viral and trending
        viral_count = 0
        trending_count = 0
        
        for claim_hash in self.claims:
            count_5min = self._count_in_window(claim_hash, WINDOW_5MIN, current_time)
            count_1hr = self._count_in_window(claim_hash, WINDOW_1HR, current_time)
            
            if count_5min > (BASELINE_5MIN * VIRAL_MULTIPLIER):
                viral_count += 1
            elif count_1hr > (BASELINE_1HR * 3):
                trending_count += 1
        
        return {
            'total_claims_tracked': total_claims,
            'total_timestamps': total_timestamps,
            'viral_claims': viral_count,
            'trending_claims': trending_count,
            'last_cleanup': datetime.fromtimestamp(self.last_cleanup).isoformat()
        }
    
    def get_top_viral(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get top viral claims by 5-minute velocity"""
        current_time = time.time()
        
        viral_claims = []
        for claim_hash in self.claims:
            count_5min = self._count_in_window(claim_hash, WINDOW_5MIN, current_time)
            count_1hr = self._count_in_window(claim_hash, WINDOW_1HR, current_time)
            
            if count_5min > BASELINE_5MIN:
                viral_claims.append({
                    'claim_hash': claim_hash,
                    'count_5min': count_5min,
                    'count_1hr': count_1hr,
                    'velocity_5min': min(count_5min / (BASELINE_5MIN * VIRAL_MULTIPLIER), 1.0)
                })
        
        # Sort by 5-min count
        viral_claims.sort(key=lambda x: x['count_5min'], reverse=True)
        return viral_claims[:limit]


# Singleton instance
_velocity_tracker = VelocityTracker()


def track_claim(text: str) -> Dict[str, any]:
    """Track a claim and return velocity metrics"""
    return _velocity_tracker.track_claim(text)


def get_velocity(text: str) -> Optional[Dict[str, any]]:
    """Get velocity metrics without tracking"""
    return _velocity_tracker.get_velocity(text)


def get_stats() -> Dict[str, any]:
    """Get tracker statistics"""
    return _velocity_tracker.get_stats()


def get_top_viral(limit: int = 10) -> List[Dict[str, any]]:
    """Get top viral claims"""
    return _velocity_tracker.get_top_viral(limit)


# Example usage
if __name__ == "__main__":
    # Test velocity tracking
    test_claim = "Breaking: Scientists confirm earth is flat"
    
    print("Testing velocity tracking...")
    print()
    
    # Simulate multiple checks
    for i in range(15):
        result = track_claim(test_claim)
        print(f"Check {i+1}:")
        print(f"  5-min count: {result['count_5min']}")
        print(f"  Velocity score: {result['velocity_score']}")
        print(f"  Is viral: {result['is_viral']}")
        print()
        
        if i < 14:
            time.sleep(0.1)  # Small delay
    
    # Get stats
    stats = get_stats()
    print("Tracker stats:")
    print(f"  Total claims: {stats['total_claims_tracked']}")
    print(f"  Viral claims: {stats['viral_claims']}")
