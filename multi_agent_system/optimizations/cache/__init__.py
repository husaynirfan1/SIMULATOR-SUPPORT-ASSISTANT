"""
Response Cache Module

Intelligent caching system with fuzzy matching for frequently asked questions.

Features:
- LRU eviction
- TTL expiration
- Fuzzy query matching
- Thread-safe operations
"""

from .response_cache import ResponseCache, get_cache, reset_cache

__all__ = ['ResponseCache', 'get_cache', 'reset_cache']
