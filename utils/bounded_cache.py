"""
BoundedCache - Memory-safe cache with TTL and size limits
Production-ready implementation for high-performance wallet scanning
"""

import time
import threading
from typing import Any, Dict, Optional, Callable, TypeVar

T = TypeVar("T")


class BoundedCache:
    """
    Thread-safe bounded cache with TTL and size limits

    Features:
    - Automatic cleanup of expired items
    - Size limits with LRU eviction
    - Memory usage tracking
    - Thread-safe operations
    - TTL-based expiration
    - Performance metrics

    Example:
        cache = BoundedCache(max_size=1000, ttl_seconds=3600)
        cache.set("key1", "value1")
        value = cache.get("key1")
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Initialize bounded cache

        Args:
            max_size: Maximum number of items to store (default: 1000)
            ttl_seconds: Time-to-live in seconds (default: 3600 = 1 hour)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple] = {}  # {key: (value, timestamp)}
        self._lock = threading.RLock()
        self._hit_count = 0
        self._miss_count = 0
        self._cleanup_count = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._miss_count += 1
                return None

            value, timestamp = self._cache[key]
            if self._is_expired(timestamp):
                del self._cache[key]
                self._cleanup_count += 1
                self._miss_count += 1
                return None

            self._hit_count += 1
            return value

    def set(self, key: str, value: Any) -> None:
        """
        Set item in cache

        Args:
            key: Cache key
            value: Value to store
        """
        with self._lock:
            # Clean up expired items first
            self._remove_expired()

            # Enforce size limit using LRU (least recently used)
            while len(self._cache) >= self.max_size:
                # Remove oldest item (first inserted)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._cleanup_count += 1

            # Add new item
            self._cache[key] = (value, time.time())

    def _is_expired(self, timestamp: float) -> bool:
        """Check if item is expired"""
        return time.time() - timestamp > self.ttl_seconds

    def _remove_expired(self) -> None:
        """Remove all expired items"""
        current_time = time.time()
        expired_keys = [
            k
            for k, (_, ts) in self._cache.items()
            if current_time - ts > self.ttl_seconds
        ]

        for key in expired_keys:
            del self._cache[key]
            self._cleanup_count += 1

    def clear(self) -> None:
        """Clear all items from cache"""
        with self._lock:
            self._cache.clear()
            self._cleanup_count += len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache metrics
        """
        with self._lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests if total_requests > 0 else 0

            # Estimate memory usage (very rough approximation)
            estimated_memory_mb = len(self._cache) * 0.001  # 1KB per item approx

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": hit_rate,
                "cleanup_count": self._cleanup_count,
                "estimated_memory_mb": estimated_memory_mb,
            }

    def __len__(self) -> int:
        """Get current cache size"""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache"""
        return key in self._cache


class AsyncBoundedCache(BoundedCache):
    """
    Async version of BoundedCache for async/await patterns
    """

    async def get_async(self, key: str) -> Optional[Any]:
        """Async get method"""
        return self.get(key)

    async def set_async(self, key: str, value: Any) -> None:
        """Async set method"""
        self.set(key, value)

    async def clear_async(self) -> None:
        """Async clear method"""
        self.clear()

    async def get_stats_async(self) -> Dict[str, Any]:
        """Async stats method"""
        return self.get_stats()


def cached_function(ttl_seconds: int = 300, max_size: int = 100):
    """
    Decorator for caching function results

    Args:
        ttl_seconds: Cache TTL in seconds
        max_size: Maximum cache size

    Example:
        @cached_function(ttl_seconds=60)
        def expensive_calculation(x, y):
            return x * y
    """
    cache = BoundedCache(max_size=max_size, ttl_seconds=ttl_seconds)

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            # Create cache key from function name and arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Calculate and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        return wrapper

    return decorator


# Global cache instances for common use cases
WALLET_DATA_CACHE = BoundedCache(max_size=5000, ttl_seconds=1800)  # 30 minutes
MARKET_DATA_CACHE = BoundedCache(max_size=1000, ttl_seconds=300)  # 5 minutes
API_RESPONSE_CACHE = BoundedCache(max_size=2000, ttl_seconds=60)  # 1 minute
