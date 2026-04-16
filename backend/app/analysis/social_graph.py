"""
Social Graph Analysis - Detect Coordinated Misinformation Campaigns

Integrates with social media APIs to track claim spread patterns:
- Twitter/X: Retweet graphs, user networks
- Reddit: Cross-post tracking, subreddit networks

Detects coordinated inauthentic behavior through:
- Network clustering (detect bot networks)
- Temporal patterns (synchronized posting)
- Account analysis (new accounts, similar profiles)

Note: Requires API keys for Twitter/X and Reddit
"""

import os
import logging
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)

# API credentials from environment
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "FactCheckerAI/1.0")


class SocialGraphAnalyzer:
    """
    Analyze social media spread patterns to detect coordinated campaigns
    
    Features:
    - Track retweet/share networks
    - Detect bot-like behavior patterns
    - Identify coordinated posting (same content, similar timing)
    - Calculate campaign score based on network structure
    """
    
    def __init__(self):
        # claim_hash -> spread data
        self.spread_data: Dict[str, Dict] = {}
        
        # Track user posting patterns
        self.user_activity: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        
        # Network edges (user_id -> list of connected user_ids)
        self.retweet_network: Dict[str, List[str]] = defaultdict(list)
    
    def analyze_twitter_spread(self, claim_text: str, 
                               search_limit: int = 100) -> Dict[str, any]:
        """
        Analyze claim spread on Twitter/X
        
        Args:
            claim_text: Claim to search for
            search_limit: Max tweets to analyze
            
        Returns:
            {
                'tweet_count': int,
                'retweet_count': int,
                'unique_users': int,
                'bot_score': float (0-1),
                'network_density': float (0-1),
                'temporal_clustering': float (0-1),
                'campaign_indicators': list[str]
            }
        """
        if not TWITTER_BEARER_TOKEN:
            logger.warning("Twitter API not configured (TWITTER_BEARER_TOKEN missing)")
            return self._empty_twitter_response()
        
        try:
            # Twitter API v2 search
            import requests
            
            headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
            params = {
                "query": claim_text[:500],  # Max query length
                "max_results": min(search_limit, 100),  # API limit
                "tweet.fields": "created_at,public_metrics,author_id",
                "expansions": "author_id,referenced_tweets.id",
                "user.fields": "created_at,public_metrics,verified"
            }
            
            response = requests.get(
                "https://api.twitter.com/2/tweets/search/recent",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.warning(f"Twitter API error: {response.status_code}")
                return self._empty_twitter_response()
            
            data = response.json()
            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
            
            if not tweets:
                return self._empty_twitter_response()
            
            # Analyze spread patterns
            return self._analyze_twitter_data(tweets, users, claim_text)
            
        except ImportError:
            logger.warning("requests library not installed")
            return self._empty_twitter_response()
        except Exception as e:
            logger.error(f"Twitter analysis failed: {e}")
            return self._empty_twitter_response()
    
    def _analyze_twitter_data(self, tweets: List[Dict], users: Dict[str, Dict],
                             claim_text: str) -> Dict[str, any]:
        """Analyze Twitter data for coordinated behavior"""
        tweet_count = len(tweets)
        retweet_count = 0
        unique_users = set()
        timestamps = []
        user_metrics = []
        
        for tweet in tweets:
            author_id = tweet.get("author_id")
            unique_users.add(author_id)
            
            # Count retweets
            metrics = tweet.get("public_metrics", {})
            retweet_count += metrics.get("retweet_count", 0)
            
            # Collect timestamps
            created_at = tweet.get("created_at")
            if created_at:
                timestamps.append(datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp())
            
            # Collect user metrics
            if author_id in users:
                user = users[author_id]
                user_metrics.append({
                    'followers': user.get("public_metrics", {}).get("followers_count", 0),
                    'following': user.get("public_metrics", {}).get("following_count", 0),
                    'verified': user.get("verified", False),
                    'account_age_days': self._calculate_account_age(user.get("created_at"))
                })
        
        # Bot score (0-1): based on suspicious patterns
        bot_score = self._calculate_bot_score(user_metrics)
        
        # Network density (0-1): how interconnected are the users
        network_density = min(retweet_count / max(tweet_count, 1) / 10, 1.0)
        
        # Temporal clustering (0-1): how synchronized are the posts
        temporal_clustering = self._calculate_temporal_clustering(timestamps)
        
        # Campaign indicators
        campaign_indicators = []
        if bot_score > 0.6:
            campaign_indicators.append("high_bot_activity")
        if temporal_clustering > 0.7:
            campaign_indicators.append("synchronized_posting")
        if network_density > 0.5:
            campaign_indicators.append("dense_retweet_network")
        if len(unique_users) < tweet_count * 0.3:
            campaign_indicators.append("few_unique_users")
        
        return {
            'tweet_count': tweet_count,
            'retweet_count': retweet_count,
            'unique_users': len(unique_users),
            'bot_score': round(bot_score, 3),
            'network_density': round(network_density, 3),
            'temporal_clustering': round(temporal_clustering, 3),
            'campaign_indicators': campaign_indicators,
            'is_coordinated': len(campaign_indicators) >= 2
        }
    
    def analyze_reddit_spread(self, claim_text: str,
                             search_limit: int = 100) -> Dict[str, any]:
        """
        Analyze claim spread on Reddit
        
        Args:
            claim_text: Claim to search for
            search_limit: Max posts to analyze
            
        Returns:
            {
                'post_count': int,
                'subreddit_count': int,
                'cross_post_rate': float,
                'account_age_score': float (0-1),
                'campaign_indicators': list[str]
            }
        """
        if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET):
            logger.warning("Reddit API not configured")
            return self._empty_reddit_response()
        
        try:
            import praw
            
            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent=REDDIT_USER_AGENT
            )
            
            # Search for claim
            posts = list(reddit.subreddit("all").search(
                claim_text[:500],
                limit=search_limit,
                sort="new"
            ))
            
            if not posts:
                return self._empty_reddit_response()
            
            return self._analyze_reddit_data(posts, claim_text)
            
        except ImportError:
            logger.warning("praw library not installed. Run: pip install praw")
            return self._empty_reddit_response()
        except Exception as e:
            logger.error(f"Reddit analysis failed: {e}")
            return self._empty_reddit_response()
    
    def _analyze_reddit_data(self, posts: List, claim_text: str) -> Dict[str, any]:
        """Analyze Reddit data for coordinated behavior"""
        post_count = len(posts)
        subreddits = set()
        cross_posts = 0
        account_ages = []
        
        for post in posts:
            subreddits.add(post.subreddit.display_name)
            
            # Check if cross-post
            if hasattr(post, 'crosspost_parent'):
                cross_posts += 1
            
            # Collect account age
            try:
                author = post.author
                if author:
                    account_age_days = (time.time() - author.created_utc) / 86400
                    account_ages.append(account_age_days)
            except:
                pass
        
        # Cross-post rate
        cross_post_rate = cross_posts / max(post_count, 1)
        
        # Account age score (0-1): newer accounts = more suspicious
        avg_account_age = sum(account_ages) / len(account_ages) if account_ages else 365
        account_age_score = max(0, 1 - (avg_account_age / 365))  # Normalize to 0-1
        
        # Campaign indicators
        campaign_indicators = []
        if len(subreddits) > post_count * 0.7:
            campaign_indicators.append("wide_subreddit_spread")
        if cross_post_rate > 0.5:
            campaign_indicators.append("high_cross_post_rate")
        if account_age_score > 0.6:
            campaign_indicators.append("new_accounts")
        
        return {
            'post_count': post_count,
            'subreddit_count': len(subreddits),
            'cross_post_rate': round(cross_post_rate, 3),
            'account_age_score': round(account_age_score, 3),
            'campaign_indicators': campaign_indicators,
            'is_coordinated': len(campaign_indicators) >= 2
        }
    
    def calculate_campaign_score(self, twitter_data: Dict, reddit_data: Dict,
                                 velocity_data: Dict) -> Tuple[float, List[str]]:
        """
        Calculate overall campaign score from multiple signals
        
        Args:
            twitter_data: Twitter analysis results
            reddit_data: Reddit analysis results
            velocity_data: Velocity tracking data
            
        Returns:
            (campaign_score, indicators)
            campaign_score: 0-1 (higher = more likely coordinated)
            indicators: List of detected campaign signals
        """
        signals = []
        indicators = []
        
        # Twitter signals
        if twitter_data.get('bot_score', 0) > 0.6:
            signals.append(0.3)
            indicators.append("twitter_bot_activity")
        
        if twitter_data.get('temporal_clustering', 0) > 0.7:
            signals.append(0.25)
            indicators.append("synchronized_twitter_posts")
        
        if twitter_data.get('is_coordinated'):
            signals.append(0.2)
            indicators.extend(twitter_data.get('campaign_indicators', []))
        
        # Reddit signals
        if reddit_data.get('is_coordinated'):
            signals.append(0.2)
            indicators.extend(reddit_data.get('campaign_indicators', []))
        
        # Velocity signals
        if velocity_data.get('is_viral'):
            signals.append(0.3)
            indicators.append("viral_velocity")
        
        if velocity_data.get('is_trending'):
            signals.append(0.15)
            indicators.append("trending")
        
        # Calculate score (cap at 1.0)
        campaign_score = min(sum(signals), 1.0)
        
        # Deduplicate indicators
        indicators = list(set(indicators))
        
        return round(campaign_score, 3), indicators
    
    def _calculate_bot_score(self, user_metrics: List[Dict]) -> float:
        """
        Calculate bot likelihood score based on user metrics
        
        Indicators:
        - Low follower count
        - High following/follower ratio
        - New accounts
        - Unverified accounts
        """
        if not user_metrics:
            return 0.0
        
        bot_signals = []
        
        for user in user_metrics:
            signals = 0
            
            # Low followers (< 50)
            if user['followers'] < 50:
                signals += 0.3
            
            # High following/follower ratio (> 5)
            if user['followers'] > 0:
                ratio = user['following'] / user['followers']
                if ratio > 5:
                    signals += 0.3
            
            # New account (< 30 days)
            if user['account_age_days'] < 30:
                signals += 0.2
            
            # Not verified
            if not user['verified']:
                signals += 0.1
            
            bot_signals.append(min(signals, 1.0))
        
        return sum(bot_signals) / len(bot_signals)
    
    def _calculate_temporal_clustering(self, timestamps: List[float]) -> float:
        """
        Calculate how clustered posts are in time
        
        Returns 0-1: higher = more synchronized
        """
        if len(timestamps) < 2:
            return 0.0
        
        timestamps = sorted(timestamps)
        
        # Calculate time gaps between consecutive posts
        gaps = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        
        # If most posts are within 1 hour of each other, it's suspicious
        short_gaps = sum(1 for gap in gaps if gap < 3600)  # 1 hour
        clustering_score = short_gaps / len(gaps)
        
        return clustering_score
    
    def _calculate_account_age(self, created_at: Optional[str]) -> int:
        """Calculate account age in days"""
        if not created_at:
            return 365  # Default to 1 year
        
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = (datetime.now(created.tzinfo) - created).days
            return max(age_days, 0)
        except:
            return 365
    
    def _empty_twitter_response(self) -> Dict[str, any]:
        """Empty response when Twitter API is unavailable"""
        return {
            'tweet_count': 0,
            'retweet_count': 0,
            'unique_users': 0,
            'bot_score': 0.0,
            'network_density': 0.0,
            'temporal_clustering': 0.0,
            'campaign_indicators': [],
            'is_coordinated': False,
            'error': 'Twitter API not available'
        }
    
    def _empty_reddit_response(self) -> Dict[str, any]:
        """Empty response when Reddit API is unavailable"""
        return {
            'post_count': 0,
            'subreddit_count': 0,
            'cross_post_rate': 0.0,
            'account_age_score': 0.0,
            'campaign_indicators': [],
            'is_coordinated': False,
            'error': 'Reddit API not available'
        }


# Singleton instance
_social_graph_analyzer = SocialGraphAnalyzer()


def analyze_social_spread(claim_text: str, velocity_data: Dict = None) -> Dict[str, any]:
    """
    Analyze claim spread across social media platforms
    
    Args:
        claim_text: Claim to analyze
        velocity_data: Optional velocity tracking data
        
    Returns:
        Combined analysis with campaign score
    """
    # Analyze Twitter
    twitter_data = _social_graph_analyzer.analyze_twitter_spread(claim_text)
    
    # Analyze Reddit
    reddit_data = _social_graph_analyzer.analyze_reddit_spread(claim_text)
    
    # Calculate campaign score
    velocity_data = velocity_data or {}
    campaign_score, indicators = _social_graph_analyzer.calculate_campaign_score(
        twitter_data, reddit_data, velocity_data
    )
    
    return {
        'twitter': twitter_data,
        'reddit': reddit_data,
        'campaign_score': campaign_score,
        'campaign_indicators': indicators,
        'is_coordinated_campaign': campaign_score > 0.6
    }


# Example usage
if __name__ == "__main__":
    print("Testing Social Graph Analysis")
    print("=" * 60)
    print("\nNote: Requires Twitter and Reddit API credentials")
    print("Set environment variables:")
    print("  - TWITTER_BEARER_TOKEN")
    print("  - REDDIT_CLIENT_ID")
    print("  - REDDIT_CLIENT_SECRET")
    print()
    
    test_claim = "Breaking news: major event happening now"
    
    result = analyze_social_spread(test_claim)
    
    print(f"Analyzing: {test_claim}\n")
    print("Twitter Analysis:")
    print(f"  Tweets: {result['twitter']['tweet_count']}")
    print(f"  Bot Score: {result['twitter']['bot_score']}")
    print(f"  Coordinated: {result['twitter']['is_coordinated']}")
    print()
    print("Reddit Analysis:")
    print(f"  Posts: {result['reddit']['post_count']}")
    print(f"  Subreddits: {result['reddit']['subreddit_count']}")
    print(f"  Coordinated: {result['reddit']['is_coordinated']}")
    print()
    print("Campaign Detection:")
    print(f"  Campaign Score: {result['campaign_score']}")
    print(f"  Is Coordinated: {result['is_coordinated_campaign']}")
    print(f"  Indicators: {', '.join(result['campaign_indicators']) if result['campaign_indicators'] else 'None'}")
