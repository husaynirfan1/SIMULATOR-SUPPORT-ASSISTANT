"""
Response caching system for multi-agent queries
Implements intelligent caching with similarity matching and TTL
"""

import hashlib
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import threading
from collections import OrderedDict


class ResponseCache:
    """
    Intelligent response cache with semantic similarity matching
    Uses query normalization and fuzzy matching for cache hits
    """

    def __init__(
        self,
        max_size: int = 100,
        ttl_seconds: int = 3600,  # 1 hour default
        similarity_threshold: float = 0.85
    ):
        """
        Initialize response cache

        Args:
            max_size: Maximum number of cached responses (LRU eviction)
            ttl_seconds: Time-to-live for cached responses in seconds
            similarity_threshold: Minimum similarity score for cache hit (0.0-1.0)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold

        # Cache storage: OrderedDict for LRU behavior
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()

        # Lock for thread-safe operations
        self._lock = threading.Lock()

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0
        }

    def _normalize_query(self, query: str) -> str:
        """
        Normalize query for better matching

        Args:
            query: Raw query string

        Returns:
            Normalized query string
        """
        # Convert to lowercase
        normalized = query.lower().strip()

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        # Remove common punctuation at the end
        normalized = normalized.rstrip('?.!')

        return normalized

    def _generate_cache_key(self, query: str) -> str:
        """
        Generate cache key from normalized query

        Args:
            query: Query string

        Returns:
            Cache key (hash)
        """
        normalized = self._normalize_query(query)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _calculate_similarity(self, query1: str, query2: str) -> float:
        """
        Calculate similarity between two queries
        Uses simple token-based Jaccard similarity

        Args:
            query1: First query
            query2: Second query

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Normalize both queries
        q1_norm = self._normalize_query(query1)
        q2_norm = self._normalize_query(query2)

        # Exact match
        if q1_norm == q2_norm:
            return 1.0

        # Token-based Jaccard similarity
        tokens1 = set(q1_norm.split())
        tokens2 = set(q2_norm.split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)

        return len(intersection) / len(union)

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """
        Check if cache entry is expired

        Args:
            entry: Cache entry

        Returns:
            True if expired, False otherwise
        """
        timestamp = entry.get("timestamp", 0)
        age = time.time() - timestamp
        return age > self.ttl_seconds

    def _evict_lru(self):
        """Evict least recently used entry"""
        if self._cache:
            self._cache.popitem(last=False)
            self.stats["evictions"] += 1

    def _cleanup_expired(self):
        """Remove all expired entries"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if self._is_expired(entry)
            ]

            for key in expired_keys:
                del self._cache[key]
                self.stats["expirations"] += 1

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response for query

        Args:
            query: User query

        Returns:
            Cached response dict or None if not found
        """
        with self._lock:
            # Cleanup expired entries periodically
            if len(self._cache) > 0 and self.stats["hits"] % 10 == 0:
                self._cleanup_expired()

            # Try exact match first
            cache_key = self._generate_cache_key(query)

            if cache_key in self._cache:
                entry = self._cache[cache_key]

                # Check if expired
                if self._is_expired(entry):
                    del self._cache[cache_key]
                    self.stats["expirations"] += 1
                    self.stats["misses"] += 1
                    return None

                # Move to end (most recently used)
                self._cache.move_to_end(cache_key)
                self.stats["hits"] += 1

                return entry["response"]

            # Try fuzzy matching for similar queries
            best_match_key = None
            best_similarity = 0.0

            for key, entry in self._cache.items():
                if self._is_expired(entry):
                    continue

                similarity = self._calculate_similarity(query, entry["query"])

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_key = key

            # If we found a similar enough query, return its response
            if best_similarity >= self.similarity_threshold and best_match_key:
                entry = self._cache[best_match_key]
                self._cache.move_to_end(best_match_key)
                self.stats["hits"] += 1

                # Add metadata indicating this was a fuzzy match
                response = entry["response"].copy()
                response["_cache_metadata"] = {
                    "similarity": best_similarity,
                    "original_query": entry["query"],
                    "fuzzy_match": True
                }

                return response

            # No match found
            self.stats["misses"] += 1
            return None

    def set(self, query: str, response: Dict[str, Any]):
        """
        Cache a response for a query

        Args:
            query: User query
            response: Response to cache
        """
        with self._lock:
            cache_key = self._generate_cache_key(query)

            # If cache is full, evict LRU entry
            if len(self._cache) >= self.max_size and cache_key not in self._cache:
                self._evict_lru()

            # Store entry
            self._cache[cache_key] = {
                "query": query,
                "response": response,
                "timestamp": time.time()
            }

            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)

    def invalidate(self, query: str) -> bool:
        """
        Invalidate (remove) cached response for query

        Args:
            query: User query

        Returns:
            True if entry was removed, False if not found
        """
        with self._lock:
            cache_key = self._generate_cache_key(query)

            if cache_key in self._cache:
                del self._cache[cache_key]
                return True

            return False

    def clear(self):
        """Clear all cached responses"""
        with self._lock:
            self._cache.clear()
            self.stats = {
                "hits": 0,
                "misses": 0,
                "evictions": 0,
                "expirations": 0
            }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dict with cache statistics
        """
        with self._lock:
            total_requests = self.stats["hits"] + self.stats["misses"]
            hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self.stats["hits"],
                "misses": self.stats["misses"],
                "hit_rate": round(hit_rate * 100, 2),
                "evictions": self.stats["evictions"],
                "expirations": self.stats["expirations"],
                "ttl_seconds": self.ttl_seconds
            }

    def get_cached_queries(self) -> List[Dict[str, Any]]:
        """
        Get list of all cached queries with metadata

        Returns:
            List of cached query info
        """
        with self._lock:
            result = []
            current_time = time.time()

            for key, entry in self._cache.items():
                age = current_time - entry["timestamp"]
                remaining_ttl = max(0, self.ttl_seconds - age)

                result.append({
                    "query": entry["query"],
                    "age_seconds": round(age, 2),
                    "remaining_ttl_seconds": round(remaining_ttl, 2),
                    "expired": self._is_expired(entry)
                })

            return result


# Global cache instance
_global_cache: Optional[ResponseCache] = None


def get_cache(
    max_size: int = 100,
    ttl_seconds: int = 3600,
    similarity_threshold: float = 0.85
) -> ResponseCache:
    """
    Get or create global cache instance

    Args:
        max_size: Maximum cache size
        ttl_seconds: Time-to-live in seconds
        similarity_threshold: Similarity threshold for fuzzy matching

    Returns:
        ResponseCache instance
    """
    global _global_cache

    if _global_cache is None:
        _global_cache = ResponseCache(
            max_size=max_size,
            ttl_seconds=ttl_seconds,
            similarity_threshold=similarity_threshold
        )

    return _global_cache


def reset_cache():
    """Reset global cache instance"""
    global _global_cache
    if _global_cache:
        _global_cache.clear()
    _global_cache = None
