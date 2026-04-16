"""
Semantic Clustering - Detect Paraphrased Misinformation Variants

Uses sentence embeddings to cluster similar claims and detect coordinated
campaigns where the same misinformation is spread in multiple paraphrased forms.

Features:
- Generate embeddings using sentence-transformers
- Cluster similar claims with HDBSCAN
- Detect paraphrased variants (50+ variants = coordinated campaign)
- Track cluster evolution over time

For production: Consider using a vector database (Pinecone, Weaviate, Qdrant)
for efficient similarity search at scale.
"""

import logging
import hashlib
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

# Lazy imports for heavy dependencies
_sentence_transformer = None
_hdbscan = None


def _get_sentence_transformer():
    """Lazy load sentence-transformers model"""
    global _sentence_transformer
    if _sentence_transformer is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Use lightweight model for speed (384-dim embeddings)
            # For production, consider: all-MiniLM-L6-v2 (faster) or all-mpnet-base-v2 (better)
            _sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Loaded sentence-transformers model: all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("sentence-transformers not installed. Run: pip install sentence-transformers")
            _sentence_transformer = None
    return _sentence_transformer


def _get_hdbscan():
    """Lazy load HDBSCAN clustering"""
    global _hdbscan
    if _hdbscan is None:
        try:
            import hdbscan
            _hdbscan = hdbscan
            logger.info("Loaded HDBSCAN clustering library")
        except ImportError:
            logger.warning("hdbscan not installed. Run: pip install hdbscan")
            _hdbscan = None
    return _hdbscan


class ClaimCluster:
    """
    In-memory claim clustering with semantic embeddings
    
    For production, replace with vector database:
    - Pinecone: Managed vector DB with similarity search
    - Weaviate: Open-source vector search engine
    - Qdrant: Fast vector similarity search
    - Milvus: Scalable vector database
    """
    
    def __init__(self):
        # claim_hash -> (embedding, text, timestamp, cluster_id)
        self.claims: Dict[str, Tuple[np.ndarray, str, float, Optional[int]]] = {}
        
        # cluster_id -> list of claim_hashes
        self.clusters: Dict[int, List[str]] = defaultdict(list)
        
        # Track cluster creation time
        self.cluster_timestamps: Dict[int, float] = {}
        
        self.next_cluster_id = 0
        self.last_clustering = 0
        self.clustering_interval = 3600  # Re-cluster every hour
    
    def add_claim(self, text: str) -> Dict[str, any]:
        """
        Add claim and return clustering info
        
        Args:
            text: Claim text
            
        Returns:
            {
                'claim_hash': str,
                'cluster_id': int or None,
                'cluster_size': int,
                'similar_claims': list[str],
                'is_coordinated_campaign': bool,
                'campaign_score': float (0-1)
            }
        """
        model = _get_sentence_transformer()
        if model is None:
            return self._fallback_response(text)
        
        # Generate embedding
        try:
            embedding = model.encode(text, convert_to_numpy=True)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return self._fallback_response(text)
        
        # Generate claim hash
        claim_hash = self._hash_claim(text)
        current_time = datetime.now().timestamp()
        
        # Check if claim already exists
        if claim_hash in self.claims:
            _, _, _, cluster_id = self.claims[claim_hash]
            return self._get_cluster_info(claim_hash, cluster_id)
        
        # Find similar existing claims (cosine similarity > 0.85)
        similar_claims = self._find_similar_claims(embedding, threshold=0.85)
        
        # Assign to existing cluster or create new one
        cluster_id = None
        if similar_claims:
            # Join the cluster of the most similar claim
            most_similar_hash = similar_claims[0][0]
            _, _, _, existing_cluster_id = self.claims[most_similar_hash]
            if existing_cluster_id is not None:
                cluster_id = existing_cluster_id
                self.clusters[cluster_id].append(claim_hash)
        
        # Store claim
        self.claims[claim_hash] = (embedding, text, current_time, cluster_id)
        
        # Periodic re-clustering
        if current_time - self.last_clustering > self.clustering_interval:
            self._recluster_all()
        
        return self._get_cluster_info(claim_hash, cluster_id)
    
    def _find_similar_claims(self, embedding: np.ndarray, 
                            threshold: float = 0.85) -> List[Tuple[str, float]]:
        """
        Find claims with cosine similarity > threshold
        
        Returns:
            List of (claim_hash, similarity_score) sorted by similarity
        """
        if not self.claims:
            return []
        
        similarities = []
        for claim_hash, (stored_embedding, _, _, _) in self.claims.items():
            # Cosine similarity
            similarity = np.dot(embedding, stored_embedding) / (
                np.linalg.norm(embedding) * np.linalg.norm(stored_embedding)
            )
            if similarity >= threshold:
                similarities.append((claim_hash, float(similarity)))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities
    
    def _recluster_all(self):
        """
        Re-cluster all claims using HDBSCAN
        
        This is expensive - only run periodically or when cluster count is high
        """
        hdbscan_lib = _get_hdbscan()
        if hdbscan_lib is None or len(self.claims) < 10:
            return
        
        try:
            # Extract embeddings and hashes
            claim_hashes = list(self.claims.keys())
            embeddings = np.array([self.claims[h][0] for h in claim_hashes])
            
            # HDBSCAN clustering
            clusterer = hdbscan_lib.HDBSCAN(
                min_cluster_size=3,      # At least 3 similar claims
                min_samples=2,           # Minimum samples in neighborhood
                metric='cosine',         # Cosine distance for text embeddings
                cluster_selection_epsilon=0.15  # Merge clusters within 0.15 distance
            )
            
            cluster_labels = clusterer.fit_predict(embeddings)
            
            # Reset clusters
            self.clusters.clear()
            current_time = datetime.now().timestamp()
            
            # Assign new cluster IDs
            for claim_hash, label in zip(claim_hashes, cluster_labels):
                embedding, text, timestamp, _ = self.claims[claim_hash]
                
                if label == -1:
                    # Noise point - no cluster
                    self.claims[claim_hash] = (embedding, text, timestamp, None)
                else:
                    # Assign to cluster
                    cluster_id = int(label)
                    self.claims[claim_hash] = (embedding, text, timestamp, cluster_id)
                    self.clusters[cluster_id].append(claim_hash)
                    
                    if cluster_id not in self.cluster_timestamps:
                        self.cluster_timestamps[cluster_id] = current_time
            
            self.last_clustering = current_time
            logger.info(f"Re-clustered {len(self.claims)} claims into {len(self.clusters)} clusters")
            
        except Exception as e:
            logger.error(f"Clustering failed: {e}")
    
    def _get_cluster_info(self, claim_hash: str, cluster_id: Optional[int]) -> Dict[str, any]:
        """Get detailed cluster information"""
        if cluster_id is None:
            return {
                'claim_hash': claim_hash,
                'cluster_id': None,
                'cluster_size': 1,
                'similar_claims': [],
                'is_coordinated_campaign': False,
                'campaign_score': 0.0
            }
        
        # Get all claims in cluster
        cluster_claims = self.clusters.get(cluster_id, [])
        cluster_size = len(cluster_claims)
        
        # Get sample of similar claims (up to 5)
        similar_texts = []
        for h in cluster_claims[:5]:
            if h != claim_hash:
                _, text, _, _ = self.claims[h]
                similar_texts.append(text[:100])  # First 100 chars
        
        # Coordinated campaign detection
        # Threshold: 50+ paraphrased variants = likely coordinated
        is_coordinated = cluster_size >= 50
        
        # Campaign score (0-1): normalized by threshold
        campaign_score = min(cluster_size / 100, 1.0)  # Cap at 100 variants
        
        # Check temporal clustering (all within 24 hours = more suspicious)
        if cluster_size >= 10:
            timestamps = [self.claims[h][2] for h in cluster_claims]
            time_span = max(timestamps) - min(timestamps)
            if time_span < 86400:  # 24 hours
                campaign_score = min(campaign_score + 0.2, 1.0)
        
        return {
            'claim_hash': claim_hash,
            'cluster_id': cluster_id,
            'cluster_size': cluster_size,
            'similar_claims': similar_texts,
            'is_coordinated_campaign': is_coordinated,
            'campaign_score': round(campaign_score, 3),
            'cluster_age_hours': (datetime.now().timestamp() - self.cluster_timestamps.get(cluster_id, 0)) / 3600
        }
    
    def _hash_claim(self, text: str) -> str:
        """Generate consistent hash for claim text"""
        normalized = ' '.join(text.lower().strip().split())
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def _fallback_response(self, text: str) -> Dict[str, any]:
        """Fallback when sentence-transformers is not available"""
        return {
            'claim_hash': self._hash_claim(text),
            'cluster_id': None,
            'cluster_size': 1,
            'similar_claims': [],
            'is_coordinated_campaign': False,
            'campaign_score': 0.0,
            'error': 'sentence-transformers not available'
        }
    
    def get_cluster_stats(self) -> Dict[str, any]:
        """Get clustering statistics"""
        total_claims = len(self.claims)
        total_clusters = len(self.clusters)
        
        # Cluster size distribution
        cluster_sizes = [len(claims) for claims in self.clusters.values()]
        avg_cluster_size = np.mean(cluster_sizes) if cluster_sizes else 0
        max_cluster_size = max(cluster_sizes) if cluster_sizes else 0
        
        # Coordinated campaigns (50+ variants)
        coordinated_campaigns = sum(1 for size in cluster_sizes if size >= 50)
        
        # Unclustered claims
        unclustered = sum(1 for _, _, _, cid in self.claims.values() if cid is None)
        
        return {
            'total_claims': total_claims,
            'total_clusters': total_clusters,
            'avg_cluster_size': round(avg_cluster_size, 2),
            'max_cluster_size': max_cluster_size,
            'coordinated_campaigns': coordinated_campaigns,
            'unclustered_claims': unclustered,
            'last_clustering': datetime.fromtimestamp(self.last_clustering).isoformat() if self.last_clustering else None
        }
    
    def get_top_clusters(self, limit: int = 10) -> List[Dict[str, any]]:
        """Get largest clusters (potential coordinated campaigns)"""
        cluster_info = []
        
        for cluster_id, claim_hashes in self.clusters.items():
            if len(claim_hashes) < 3:
                continue
            
            # Get sample claims
            sample_texts = []
            for h in claim_hashes[:3]:
                _, text, _, _ = self.claims[h]
                sample_texts.append(text[:80])
            
            cluster_info.append({
                'cluster_id': cluster_id,
                'size': len(claim_hashes),
                'sample_claims': sample_texts,
                'is_coordinated': len(claim_hashes) >= 50,
                'created_at': datetime.fromtimestamp(
                    self.cluster_timestamps.get(cluster_id, 0)
                ).isoformat()
            })
        
        # Sort by size (descending)
        cluster_info.sort(key=lambda x: x['size'], reverse=True)
        return cluster_info[:limit]


# Singleton instance
_claim_cluster = ClaimCluster()


def cluster_claim(text: str) -> Dict[str, any]:
    """
    Add claim to clustering system and return cluster info
    
    Args:
        text: Claim text
        
    Returns:
        Cluster information including campaign detection
    """
    return _claim_cluster.add_claim(text)


def get_cluster_stats() -> Dict[str, any]:
    """Get clustering statistics"""
    return _claim_cluster.get_cluster_stats()


def get_top_clusters(limit: int = 10) -> List[Dict[str, any]]:
    """Get top clusters by size"""
    return _claim_cluster.get_top_clusters(limit)


# Example usage
if __name__ == "__main__":
    print("Testing Semantic Clustering")
    print("=" * 60)
    
    # Test claims (paraphrased variants)
    test_claims = [
        "Breaking: Scientists confirm earth is flat",
        "SHOCKING: New study proves earth is actually flat",
        "Scientists finally admit the earth is flat",
        "Earth is flat, scientists confirm in new research",
        "Flat earth theory confirmed by scientists",
        "Completely unrelated claim about weather",
        "Another unrelated claim about sports",
    ]
    
    print("\nAdding claims to clustering system...\n")
    
    for i, claim in enumerate(test_claims, 1):
        result = cluster_claim(claim)
        print(f"Claim {i}: {claim[:50]}...")
        print(f"  Cluster ID: {result.get('cluster_id')}")
        print(f"  Cluster Size: {result.get('cluster_size')}")
        print(f"  Campaign Score: {result.get('campaign_score')}")
        print(f"  Is Coordinated: {result.get('is_coordinated_campaign')}")
        print()
    
    # Get stats
    stats = get_cluster_stats()
    print("\nClustering Statistics:")
    print(f"  Total Claims: {stats['total_claims']}")
    print(f"  Total Clusters: {stats['total_clusters']}")
    print(f"  Avg Cluster Size: {stats['avg_cluster_size']}")
    print(f"  Max Cluster Size: {stats['max_cluster_size']}")
    print(f"  Coordinated Campaigns: {stats['coordinated_campaigns']}")
    
    # Get top clusters
    top = get_top_clusters(limit=5)
    print("\nTop Clusters:")
    for cluster in top:
        print(f"  Cluster {cluster['cluster_id']}: {cluster['size']} claims")
        print(f"    Sample: {cluster['sample_claims'][0][:60]}...")
