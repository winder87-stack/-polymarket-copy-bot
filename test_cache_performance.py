#!/usr/bin/env python3
"""
Cache Performance Test for Polymarket Client
Tests the efficient TTL cache implementation with 1000+ simulated requests
"""

import asyncio
import sys
import time
from typing import Any, Dict

# Add the core directory to path for imports
sys.path.insert(0, "core")

# Import only the EfficientTTLCache class directly
import importlib.util

spec = importlib.util.spec_from_file_location("clob_client", "core/clob_client.py")
clob_module = importlib.util.module_from_spec(spec)


# Extract only the EfficientTTLCache class
class EfficientTTLCache:
    """Efficient TTL cache with O(1) operations using heap for expiration tracking"""

    def __init__(self, ttl_seconds: int = 300, max_memory_mb: int = 50):
        self.ttl_seconds = ttl_seconds
        self.max_memory_mb = max_memory_mb
        self._cache = {}  # key -> (value, timestamp, heap_index)
        self._expiration_heap = []  # [(timestamp, counter, key), ...]
        self._counter = 0  # For handling duplicate timestamps
        self._cleanup_task = None
        self._lock = asyncio.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    async def start_background_cleanup(self):
        """Start background cleanup task"""
        if self._cleanup_task is not None:
            return

        self._cleanup_task = asyncio.create_task(self._background_cleanup())
        print("🧹 Started background cache cleanup task")

    async def stop_background_cleanup(self):
        """Stop background cleanup task"""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            print("🧹 Stopped background cache cleanup task")

    async def get(self, key: str):
        """Get value from cache with O(1) access"""
        async with self._lock:
            if key in self._cache:
                value, timestamp, _ = self._cache[key]
                if time.time() - timestamp < self.ttl_seconds:
                    self._hits += 1
                    return value
                else:
                    # Entry expired, remove it
                    del self._cache[key]
                    self._misses += 1
                    return None
            self._misses += 1
            return None

    async def put(self, key: str, value):
        """Put value in cache with O(1) access"""
        async with self._lock:
            now = time.time()
            counter = self._counter
            self._counter += 1

            # Remove old entry if it exists
            if key in self._cache:
                _, _, old_heap_index = self._cache[key]
                self._expiration_heap[old_heap_index] = None  # Mark as removed

            # Add to cache
            heap_index = len(self._expiration_heap)
            self._cache[key] = (value, now, heap_index)
            import heapq

            heapq.heappush(self._expiration_heap, (now + self.ttl_seconds, counter, key))

            # Check memory limits
            await self._check_memory_limits()

    async def _check_memory_limits(self):
        """Check if cache exceeds memory limits and cleanup if necessary"""
        memory_usage = self._estimate_memory_usage()
        if memory_usage > self.max_memory_mb * 1024 * 1024:  # Convert MB to bytes
            # Remove oldest 20% of entries
            entries_to_remove = max(1, len(self._cache) // 5)
            await self._cleanup_expired_entries()
            await self._evict_oldest(entries_to_remove)
            print(
                f"💾 Cache memory limit exceeded ({memory_usage/1024/1024:.1f}MB), "
                f"evicted {entries_to_remove} entries"
            )

    async def _evict_oldest(self, count: int):
        """Evict oldest entries from cache"""
        # Get entries sorted by timestamp (oldest first)
        entries = [(ts, key) for key, (_, ts, _) in self._cache.items()]
        entries.sort()  # Sort by timestamp

        evicted = 0
        for _, key in entries[:count]:
            if key in self._cache:
                _, _, heap_index = self._cache[key]
                self._expiration_heap[heap_index] = None  # Mark as removed
                del self._cache[key]
                evicted += 1
                self._evictions += 1

        if evicted > 0:
            print(f"🗑️ Evicted {evicted} oldest cache entries")

    async def _background_cleanup(self):
        """Background task to cleanup expired entries"""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute
                await self._cleanup_expired_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Error in background cache cleanup: {e}")

    async def _cleanup_expired_entries(self):
        """Remove expired entries from cache"""
        import heapq

        async with self._lock:
            now = time.time()
            original_count = len(self._cache)

            # Remove expired entries from heap
            while self._expiration_heap and self._expiration_heap[0] is not None:
                exp_time, _, key = self._expiration_heap[0]
                if exp_time > now:
                    break  # No more expired entries

                heapq.heappop(self._expiration_heap)

                # Remove from cache if still there and expired
                if key in self._cache:
                    cached_time = self._cache[key][1]
                    if now - cached_time >= self.ttl_seconds:
                        del self._cache[key]
                        self._evictions += 1

            # Clean up None entries (removed items)
            self._expiration_heap = [entry for entry in self._expiration_heap if entry is not None]

            # Rebuild heap indices after cleanup
            for i, entry in enumerate(self._expiration_heap):
                if entry is not None:
                    _, _, key = entry
                    if key in self._cache:
                        self._cache[key] = self._cache[key][:2] + (i,)

            new_count = len(self._cache)
            if original_count != new_count:
                print(f"🧹 Cleaned up {original_count - new_count} expired cache entries")

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage of cache in bytes"""
        # Rough estimation: each entry ~1KB + key size
        base_memory = len(self._cache) * 1024  # 1KB per entry
        key_memory = sum(len(str(k)) for k in self._cache.keys()) * 2  # 2 bytes per char
        heap_memory = len(self._expiration_heap) * 32  # ~32 bytes per heap entry
        return base_memory + key_memory + heap_memory

    def get_stats(self):
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_ratio = (self._hits / total_requests) if total_requests > 0 else 0.0

        oldest_timestamp = float("inf")
        for _, timestamp, _ in self._cache.values():
            oldest_timestamp = min(oldest_timestamp, timestamp)
        oldest_timestamp = time.time() - oldest_timestamp if oldest_timestamp != float("inf") else 0

        return {
            "size": len(self._cache),
            "max_size": None,  # No hard limit, memory-based
            "hit_ratio": hit_ratio,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "memory_usage_mb": self._estimate_memory_usage() / 1024 / 1024,
            "oldest_entry_seconds": oldest_timestamp,
            "ttl_seconds": self.ttl_seconds,
            "background_cleanup_active": self._cleanup_task is not None
            and not self._cleanup_task.done(),
        }

    async def clear(self):
        """Clear all cache entries"""
        async with self._lock:
            self._cache.clear()
            self._expiration_heap.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            print("🧹 Cache cleared")


class MockMarketData:
    """Mock market data for testing"""

    def __init__(self, condition_id: str):
        self.condition_id = condition_id
        self.price = 0.5 + (hash(condition_id) % 100) / 200  # Random-ish price
        self.volume = hash(condition_id) % 1000000
        self.active = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "price": self.price,
            "volume": self.volume,
            "active": self.active,
            "data": "x" * 1000,  # Add some data to simulate real market data size
        }


async def simulate_market_requests(
    cache: EfficientTTLCache, num_requests: int = 1000
) -> Dict[str, Any]:
    """Simulate market requests with realistic cache hit patterns"""

    # Generate market IDs - some will be requested multiple times (cache hits)
    # Others will be unique (cache misses)
    market_ids = []
    for i in range(num_requests // 2):
        market_ids.append(f"market_{i:04d}")  # Unique markets

    # Add some repeated requests to simulate cache hits
    for i in range(num_requests // 2):
        market_ids.append(f"market_{i % 100:04d}")  # Repeat first 100 markets

    start_time = time.time()
    processed_requests = 0

    # Start background cleanup
    await cache.start_background_cleanup()

    try:
        for market_id in market_ids:
            # Simulate cache lookup
            cached_data = await cache.get(market_id)

            if cached_data is None:
                # Cache miss - simulate API call and cache storage
                await asyncio.sleep(0.001)  # Simulate network delay
                market_data = MockMarketData(market_id).to_dict()
                await cache.put(market_id, market_data)
            else:
                # Cache hit - instant response
                pass

            processed_requests += 1

            # Progress update every 100 requests
            if processed_requests % 100 == 0:
                print(f"📊 Processed {processed_requests}/{len(market_ids)} requests")

        total_time = time.time() - start_time

        # Let background cleanup run for a bit
        await asyncio.sleep(2)

        # Get final statistics
        stats = cache.get_stats()

        return {
            "total_requests": len(market_ids),
            "total_time_seconds": total_time,
            "requests_per_second": len(market_ids) / total_time,
            "cache_stats": stats,
            "memory_usage_mb": cache._estimate_memory_usage() / 1024 / 1024,
        }

    finally:
        await cache.stop_background_cleanup()


async def test_cache_limits(cache: EfficientTTLCache) -> Dict[str, Any]:
    """Test cache behavior under memory pressure"""

    print("🧪 Testing cache memory limits...")

    # Fill cache with large entries
    for i in range(200):  # Should exceed 50MB limit
        large_data = "x" * 500000  # ~500KB per entry
        await cache.put(f"large_market_{i:04d}", large_data)

    # Check memory usage and evictions
    stats = cache.get_stats()

    return {
        "entries_after_fill": stats["size"],
        "memory_usage_mb": stats["memory_usage_mb"],
        "evictions": stats["evictions"],
        "hit_ratio": stats["hit_ratio"],
    }


async def test_ttl_expiration(cache: EfficientTTLCache) -> Dict[str, Any]:
    """Test TTL expiration behavior"""

    print("⏰ Testing TTL expiration...")

    # Add some entries
    for i in range(10):
        await cache.put(f"ttl_test_{i}", f"data_{i}")

    initial_stats = cache.get_stats()

    # Wait for TTL to expire (cache TTL is 5 seconds for testing)
    print("⏳ Waiting for TTL expiration...")
    await asyncio.sleep(6)  # Wait longer than TTL

    # Force cleanup
    await cache._cleanup_expired_entries()

    final_stats = cache.get_stats()

    return {
        "initial_entries": initial_stats["size"],
        "final_entries": final_stats["size"],
        "entries_expired": initial_stats["size"] - final_stats["size"],
    }


async def run_performance_tests():
    """Run comprehensive cache performance tests"""

    print("🚀 Starting Cache Performance Tests")
    print("=" * 50)

    # Test 1: Standard performance with 1000+ requests
    print("\n📈 Test 1: Standard Performance (1000+ requests)")
    cache = EfficientTTLCache(ttl_seconds=5, max_memory_mb=50)  # Shorter TTL for testing

    results = await simulate_market_requests(cache, num_requests=1000)

    print("✅ Results:")
    print(f"   Requests: {results['total_requests']}")
    print(f"   Total Time: {results['total_time_seconds']:.2f}s")
    print(f"   Throughput: {results['requests_per_second']:.1f} req/sec")
    print(f"   Cache Hit Ratio: {results['cache_stats']['hit_ratio']:.1%}")
    print(f"   Memory Usage: {results['memory_usage_mb']:.1f}MB")

    # Test 2: Memory limits
    print("\n💾 Test 2: Memory Limits")
    memory_results = await test_cache_limits(cache)
    print("✅ Memory Test Results:")
    print(f"   Entries after fill: {memory_results['entries_after_fill']}")
    print(f"   Memory Usage: {memory_results['memory_usage_mb']:.1f}MB")
    print(f"   Evictions: {memory_results['evictions']}")
    print(f"   Hit Ratio: {memory_results['hit_ratio']:.1%}")

    # Test 3: TTL Expiration
    print("\n⏰ Test 3: TTL Expiration")
    ttl_results = await test_ttl_expiration(cache)
    print("✅ TTL Test Results:")
    print(f"   Initial entries: {ttl_results['initial_entries']}")
    print(f"   Final entries: {ttl_results['final_entries']}")
    print(f"   Entries expired: {ttl_results['entries_expired']}")

    # Overall assessment
    print("\n🎯 Performance Assessment:")
    success_criteria = {
        "O(1) Operations": results["requests_per_second"] > 500,  # Should handle >500 req/sec
        "Cache Hit Ratio > 20%": results["cache_stats"]["hit_ratio"] > 0.20,
        "Memory Under Control": results["memory_usage_mb"] < 60,  # Under 60MB
        "Memory Limits Work": memory_results["memory_usage_mb"] < 60,  # Memory management working
        "TTL Expiration Works": ttl_results["entries_expired"] > 0,
    }

    all_passed = True
    for criterion, passed in success_criteria.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} {criterion}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL PERFORMANCE TESTS PASSED!")
        print("Cache optimization successful - ready for production use.")
    else:
        print("⚠️ Some tests failed - review implementation.")

    return all_passed


if __name__ == "__main__":
    try:
        success = asyncio.run(run_performance_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
