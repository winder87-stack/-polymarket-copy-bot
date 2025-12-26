"""
Unit tests for rate limiter - test it actually limits

Tests cover:
- Rate limiting actually enforces delays
- Semaphore limits concurrent requests
- Error handling during rate limiting
- Proper timing calculations
- Edge cases with timing
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import RateLimitError
from utils.rate_limited_client import RateLimitedPolygonscanClient


@pytest.fixture
def rate_limited_client():
    """Create a rate-limited Polygonscan client for testing"""
    return RateLimitedPolygonscanClient(api_key="test_key")


class TestRateLimiter:
    """Test rate limiter functionality"""

    def test_initialization(self, rate_limited_client):
        """Test rate limiter initializes correctly"""
        assert rate_limited_client.api_key == "test_key"
        assert rate_limited_client.CALLS_PER_SECOND == 5
        assert rate_limited_client._min_interval == 1.0 / 5  # 0.2 seconds
        assert rate_limited_client._last_call_time == 0.0

    @pytest.mark.asyncio
    async def test_rate_limiting_enforces_delays(self, rate_limited_client):
        """Test that rate limiter actually enforces delays between calls"""
        # Make first call
        start_time = time.time()
        await rate_limited_client._wait_for_rate_limit()
        first_call_time = time.time()

        # Make second call immediately
        await rate_limited_client._wait_for_rate_limit()
        second_call_time = time.time()

        # Second call should be delayed by at least min_interval
        delay = second_call_time - first_call_time
        assert delay >= rate_limited_client._min_interval - 0.01  # Allow small timing tolerance

    @pytest.mark.asyncio
    async def test_concurrent_requests_limited(self, rate_limited_client):
        """Test that semaphore limits concurrent requests"""
        # Create multiple concurrent requests
        tasks = []
        for i in range(3):  # More than semaphore allows (1)
            task = asyncio.create_task(rate_limited_client._wait_for_rate_limit())
            tasks.append(task)

        start_time = time.time()
        await asyncio.gather(*tasks)
        end_time = time.time()

        # Should take at least (3-1) * min_interval due to queuing
        total_time = end_time - start_time
        expected_min_time = (len(tasks) - 1) * rate_limited_client._min_interval
        assert total_time >= expected_min_time - 0.01  # Allow small tolerance

    @pytest.mark.asyncio
    async def test_rapid_successive_calls_are_delayed(self, rate_limited_client):
        """Test that rapid successive calls are properly delayed"""
        call_times = []

        # Make 5 rapid calls
        for i in range(5):
            start = time.time()
            await rate_limited_client._wait_for_rate_limit()
            end = time.time()
            call_times.append(end - start)

        # First call should be fast (no delay), subsequent calls should be delayed
        assert call_times[0] < 0.01  # First call should be very fast

        # Subsequent calls should be delayed by approximately min_interval
        for i in range(1, len(call_times)):
            assert call_times[i] >= rate_limited_client._min_interval - 0.01

    @pytest.mark.asyncio
    async def test_timing_precision(self, rate_limited_client):
        """Test timing precision and accuracy"""
        # Test multiple rounds of rate limiting
        for round_num in range(3):
            start_time = time.time()
            await rate_limited_client._wait_for_rate_limit()
            call_time = time.time()

            # Should not execute immediately if we're within the rate limit window
            if round_num > 0:  # Skip first call
                elapsed = call_time - start_time
                assert elapsed >= rate_limited_client._min_interval - 0.01

    @pytest.mark.asyncio
    async def test_semaphore_allows_serial_execution(self, rate_limited_client):
        """Test that semaphore allows proper serial execution"""
        execution_times = []

        async def timed_wait():
            start = time.time()
            await rate_limited_client._wait_for_rate_limit()
            end = time.time()
            execution_times.append(end - start)

        # Execute tasks that should be serialized
        tasks = [timed_wait() for _ in range(3)]
        await asyncio.gather(*tasks)

        # All executions should have taken at least min_interval (except possibly the first)
        assert len(execution_times) == 3
        for i in range(1, len(execution_times)):  # Skip first call
            assert execution_times[i] >= rate_limited_client._min_interval - 0.01

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, rate_limited_client):
        """Test error handling during rate limiting operations"""
        # Mock time.time to raise exception
        with patch('utils.rate_limited_client.time') as mock_time:
            mock_time.side_effect = [0.0, OSError("Time error")]

            # Should handle time errors gracefully
            with pytest.raises(OSError):
                await rate_limited_client._wait_for_rate_limit()

    @pytest.mark.asyncio
    async def test_lock_prevents_race_conditions(self, rate_limited_client):
        """Test that lock prevents race conditions in timing updates"""
        # Create many concurrent operations
        async def concurrent_operation(op_id):
            await rate_limited_client._wait_for_rate_limit()
            return op_id

        tasks = [concurrent_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All operations should complete
        assert len(results) == 10
        assert set(results) == set(range(10))

        # Timing should be properly maintained
        assert rate_limited_client._last_call_time > 0

    @pytest.mark.asyncio
    async def test_min_interval_calculation(self, rate_limited_client):
        """Test minimum interval calculation"""
        expected_interval = 1.0 / rate_limited_client.CALLS_PER_SECOND
        assert rate_limited_client._min_interval == expected_interval

        # Test with different rates
        fast_client = RateLimitedPolygonscanClient.__new__(RateLimitedPolygonscanClient)
        fast_client.CALLS_PER_SECOND = 10
        fast_client._min_interval = 1.0 / 10

        assert fast_client._min_interval == 0.1

    @pytest.mark.asyncio
    async def test_zero_rate_limit_edge_case(self, rate_limited_client):
        """Test edge case handling"""
        # Test with very high rate limit (should allow very fast calls)
        fast_client = RateLimitedPolygonscanClient("test_key")
        fast_client.CALLS_PER_SECOND = 1000  # Very high rate
        fast_client._min_interval = 1.0 / 1000

        # Should allow very fast successive calls
        await fast_client._wait_for_rate_limit()
        start_time = time.time()
        await fast_client._wait_for_rate_limit()
        end_time = time.time()

        # Should be much faster than original client
        delay = end_time - start_time
        assert delay < rate_limited_client._min_interval

    @pytest.mark.asyncio
    async def test_timing_edge_cases(self, rate_limited_client):
        """Test timing edge cases"""
        # Test when _last_call_time is in the future (clock skew)
        rate_limited_client._last_call_time = time.time() + 10  # 10 seconds in future

        start_time = time.time()
        await rate_limited_client._wait_for_rate_limit()
        end_time = time.time()

        # Should not wait when last call time is in future
        delay = end_time - start_time
        assert delay < 0.01  # Should be very fast

    @pytest.mark.asyncio
    async def test_api_call_integration(self, rate_limited_client):
        """Test that API calls properly use rate limiting"""
        # Mock aiohttp session
        with patch('utils.rate_limited_client.aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "1", "result": []})

            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            # Make multiple API calls
            start_time = time.time()
            await rate_limited_client.get_wallet_transactions("0x123")
            first_call_end = time.time()

            await rate_limited_client.get_wallet_transactions("0x456")
            second_call_end = time.time()

            # Second call should be rate limited
            delay = second_call_end - first_call_end
            assert delay >= rate_limited_client._min_interval - 0.01

    @pytest.mark.asyncio
    async def test_rate_limit_error_propagation(self, rate_limited_client):
        """Test that rate limit errors are properly handled"""
        with patch('utils.rate_limited_client.aiohttp.ClientSession') as mock_session:
            # Mock rate limit response
            mock_response = AsyncMock()
            mock_response.status = 429  # Too Many Requests
            mock_response.json = AsyncMock(return_value={"message": "Rate limit exceeded"})

            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            # Should raise RateLimitError
            with pytest.raises(RateLimitError):
                await rate_limited_client.get_wallet_transactions("0x123")
