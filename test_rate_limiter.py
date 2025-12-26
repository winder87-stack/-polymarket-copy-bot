#!/usr/bin/env python3
"""Basic test runner for rate limiter tests"""

import asyncio
import time
import sys
from unittest.mock import AsyncMock, patch

# Add project root to path
sys.path.insert(0, '.')

from utils.rate_limited_client import RateLimitedPolygonscanClient


def test_initialization():
    """Test rate limiter initializes correctly"""
    client = RateLimitedPolygonscanClient(api_key="test_key")

    assert client.api_key == "test_key"
    assert client.CALLS_PER_SECOND == 5
    assert client._min_interval == 1.0 / 5  # 0.2 seconds
    assert client._last_call_time == 0.0

    print("✅ Initialization test passed")


async def test_rate_limiting_enforces_delays():
    """Test that rate limiter actually enforces delays between calls"""
    client = RateLimitedPolygonscanClient("test_key")

    # Make first call
    start_time = time.time()
    await client._wait_for_rate_limit()
    first_call_time = time.time()

    # Make second call immediately
    await client._wait_for_rate_limit()
    second_call_time = time.time()

    # Second call should be delayed by at least min_interval
    delay = second_call_time - first_call_time
    assert delay >= client._min_interval - 0.01, f"Delay {delay} should be >= {client._min_interval}"

    print("✅ Rate limiting delay test passed")


async def test_concurrent_requests_limited():
    """Test that semaphore limits concurrent requests"""
    client = RateLimitedPolygonscanClient("test_key")

    # Create multiple concurrent requests (more than semaphore allows)
    tasks = []
    for i in range(3):  # More than semaphore allows (1)
        task = asyncio.create_task(client._wait_for_rate_limit())
        tasks.append(task)

    start_time = time.time()
    await asyncio.gather(*tasks)
    end_time = time.time()

    # Should take at least (3-1) * min_interval due to queuing
    total_time = end_time - start_time
    expected_min_time = (len(tasks) - 1) * client._min_interval
    assert total_time >= expected_min_time - 0.01, f"Total time {total_time} should be >= {expected_min_time}"

    print("✅ Concurrent request limiting test passed")


async def test_timing_precision():
    """Test timing precision and accuracy"""
    client = RateLimitedPolygonscanClient("test_key")

    # Test multiple rounds of rate limiting
    for round_num in range(3):
        start_time = time.time()
        await client._wait_for_rate_limit()
        call_time = time.time()

        # Should not execute immediately if we're within the rate limit window
        if round_num > 0:  # Skip first call
            elapsed = call_time - start_time
            assert elapsed >= client._min_interval - 0.01, f"Round {round_num}: elapsed {elapsed} should be >= {client._min_interval}"

    print("✅ Timing precision test passed")


async def test_rate_limiting_with_simulated_api():
    """Test that rate limiting works with simulated API calls"""
    client = RateLimitedPolygonscanClient("test_key")

    # Simulate API calls by calling _wait_for_rate_limit multiple times
    call_times = []

    for i in range(3):
        start = time.time()
        await client._wait_for_rate_limit()
        end = time.time()
        call_times.append(end - start)

    # First call should be fast, subsequent calls should be delayed
    assert call_times[0] < 0.01, "First call should be very fast"
    for i in range(1, len(call_times)):
        assert call_times[i] >= client._min_interval - 0.01, f"Call {i} should be delayed"

    print("✅ Simulated API rate limiting test passed")


if __name__ == "__main__":
    print("🧪 Running rate limiter tests...")

    try:
        test_initialization()
        asyncio.run(test_rate_limiting_enforces_delays())
        asyncio.run(test_concurrent_requests_limited())
        asyncio.run(test_timing_precision())
        asyncio.run(test_rate_limiting_with_simulated_api())

        print("\n🎉 All rate limiter tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
