"""
Test script for response caching system
"""

import time
from graph import MultiAgentSystem
import os
from dotenv import load_dotenv

load_dotenv()


def test_cache():
    """Test caching functionality"""
    print("=" * 60)
    print("Testing Response Cache System")
    print("=" * 60)

    # Initialize system with caching enabled
    print("\n1. Initializing system with cache enabled...")
    system = MultiAgentSystem(
        morphik_uri=os.getenv("MORPHIK_URI", "http://localhost:8000"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        enable_cache=True,
        cache_ttl=300,  # 5 minutes for testing
        cache_size=50
    )

    # Test query 1 - First time (cache miss)
    print("\n2. Testing first query (should be CACHE MISS)...")
    query1 = "What is a deficiency report?"

    start = time.time()
    result1 = system.query(query1)
    time1 = time.time() - start

    print(f"   Query: {query1}")
    print(f"   Time: {time1:.2f}s")
    print(f"   From cache: {result1.get('from_cache', False)}")
    print(f"   Answer preview: {result1['final_answer'][:100]}...")

    # Test query 2 - Same query (cache hit)
    print("\n3. Testing same query again (should be CACHE HIT)...")

    start = time.time()
    result2 = system.query(query1)
    time2 = time.time() - start

    print(f"   Query: {query1}")
    print(f"   Time: {time2:.2f}s")
    print(f"   From cache: {result2.get('from_cache', False)}")
    print(f"   Speed improvement: {(time1 / time2):.2f}x faster")

    # Test query 3 - Similar query (fuzzy match)
    print("\n4. Testing similar query (fuzzy matching)...")
    query3 = "what's a deficiency report"  # Similar to query1

    start = time.time()
    result3 = system.query(query3)
    time3 = time.time() - start

    print(f"   Query: {query3}")
    print(f"   Time: {time3:.2f}s")
    print(f"   From cache: {result3.get('from_cache', False)}")
    if result3.get('from_cache'):
        cache_meta = result3.get('_cache_metadata', {})
        print(f"   Similarity: {cache_meta.get('similarity', 0):.2%}")
        print(f"   Original query: {cache_meta.get('original_query', 'N/A')}")

    # Test query 4 - Different query (cache miss)
    print("\n5. Testing different query (should be CACHE MISS)...")
    query4 = "How to troubleshoot interface issues?"

    start = time.time()
    result4 = system.query(query4)
    time4 = time.time() - start

    print(f"   Query: {query4}")
    print(f"   Time: {time4:.2f}s")
    print(f"   From cache: {result4.get('from_cache', False)}")

    # Show cache statistics
    print("\n6. Cache Statistics:")
    if system.cache_enabled:
        stats = system.cache.get_stats()
        print(f"   Total entries: {stats['size']}/{stats['max_size']}")
        print(f"   Hit rate: {stats['hit_rate']:.1f}%")
        print(f"   Hits: {stats['hits']}")
        print(f"   Misses: {stats['misses']}")
        print(f"   Evictions: {stats['evictions']}")

    print("\n" + "=" * 60)
    print("Cache test completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_cache()
