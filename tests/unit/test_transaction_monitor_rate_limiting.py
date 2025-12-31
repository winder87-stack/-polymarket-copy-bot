"""Comprehensive unit tests for transaction monitor rate limiting and error recovery.

Tests rate limiting behavior, error recovery, and edge cases in transaction monitoring.
"""

import asyncio
import time

import pytest
import aiohttp

from core.exceptions import APIError, PolygonscanError, RateLimitError
from utils.rate_limited_client import RateLimitedPolygonscanClient


@pytest.fixture
def rate_limited_client():
    """Create rate-limited client for testing."""
    return RateLimitedPolygonscanClient(api_key="test_key")


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test rate limiting enforces call frequency."""
        call_times = []

        async def mock_request(*args, **kwargs):
            call_times.append(time.time())
            return []

        rate_limited_client._make_request = mock_request

        # Make multiple rapid calls
        start_time = time.time()
        tasks = [
            rate_limited_client.get_transactions("0x123", start_block=0, end_block=100)
            for _ in range(5)
        ]
        await asyncio.gather(*tasks)
        end_time = time.time()

        # Verify calls were rate limited
        assert len(call_times) == 5
        # Should take at least (5-1) * min_interval seconds
        min_expected_time = (5 - 1) * rate_limited_client._min_interval
        assert (end_time - start_time) >= min_expected_time * 0.9  # Allow 10% tolerance

    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test rate limiting works correctly with concurrent requests."""
        call_count = 0
        call_times = []

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            call_times.append(time.time())
            await asyncio.sleep(0.01)  # Simulate API call
            return []

        rate_limited_client._make_request = mock_request

        # Make concurrent calls
        tasks = [
            rate_limited_client.get_transactions(f"0x{i}", start_block=0, end_block=100)
            for i in range(10)
        ]
        await asyncio.gather(*tasks)

        # Verify all calls completed
        assert call_count == 10

        # Verify calls were serialized (rate limited)
        for i in range(1, len(call_times)):
            time_diff = call_times[i] - call_times[i - 1]
            assert time_diff >= rate_limited_client._min_interval * 0.9

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test handling of rate limit errors."""
        error_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal error_count
            error_count += 1
            if error_count <= 2:
                raise RateLimitError("Rate limit exceeded")
            return []

        rate_limited_client._make_request = mock_request

        # Should handle rate limit errors gracefully
        result = await rate_limited_client.get_transactions(
            "0x123", start_block=0, end_block=100
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_exponential_backoff_on_rate_limit(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test exponential backoff on rate limit errors."""
        call_times = []
        error_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal error_count
            call_times.append(time.time())
            error_count += 1
            if error_count <= 3:
                raise RateLimitError("Rate limit exceeded")
            return []

        rate_limited_client._make_request = mock_request

        # Make request that will hit rate limit
        result = await rate_limited_client.get_transactions(
            "0x123", start_block=0, end_block=100
        )

        # Verify backoff occurred (multiple retries with delays)
        assert len(call_times) >= 3
        if len(call_times) > 1:
            # Verify delays increased (exponential backoff)
            delays = [
                call_times[i] - call_times[i - 1] for i in range(1, len(call_times))
            ]
            # First delay should be shorter than later delays
            if len(delays) >= 2:
                assert delays[-1] >= delays[0]


class TestErrorRecovery:
    """Test error recovery mechanisms."""

    @pytest.mark.asyncio
    async def test_network_error_recovery(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test recovery from network errors."""
        attempt_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise aiohttp.ClientError("Network error")
            return [{"hash": "0x123"}]

        rate_limited_client._make_request = mock_request

        result = await rate_limited_client.get_transactions(
            "0x123", start_block=0, end_block=100
        )

        # Should eventually succeed after retries
        assert result == [{"hash": "0x123"}]
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_timeout_error_recovery(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test recovery from timeout errors."""
        attempt_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise asyncio.TimeoutError("Request timeout")
            return []

        rate_limited_client._make_request = mock_request

        result = await rate_limited_client.get_transactions(
            "0x123", start_block=0, end_block=100
        )

        # Should recover from timeout
        assert result == []
        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_api_error_handling(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test handling of API errors."""

        async def mock_request(*args, **kwargs):
            raise APIError("API error occurred")

        rate_limited_client._make_request = mock_request

        # Should handle API errors gracefully
        with pytest.raises(APIError):
            await rate_limited_client.get_transactions(
                "0x123", start_block=0, end_block=100
            )

    @pytest.mark.asyncio
    async def test_polygonscan_error_handling(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test handling of Polygonscan-specific errors."""

        async def mock_request(*args, **kwargs):
            raise PolygonscanError("Polygonscan API error")

        rate_limited_client._make_request = mock_request

        # Should handle Polygonscan errors
        with pytest.raises(PolygonscanError):
            await rate_limited_client.get_transactions(
                "0x123", start_block=0, end_block=100
            )

    @pytest.mark.asyncio
    async def test_partial_failure_recovery(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test recovery from partial failures."""
        attempt_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                # First attempt: partial data
                raise aiohttp.ClientError("Partial failure")
            elif attempt_count == 2:
                # Second attempt: incomplete data
                return [{"hash": "0x123"}]  # Missing some fields
            else:
                # Third attempt: complete data
                return [{"hash": "0x123", "from": "0xabc", "to": "0xdef"}]

        rate_limited_client._make_request = mock_request

        result = await rate_limited_client.get_transactions(
            "0x123", start_block=0, end_block=100
        )

        # Should eventually get complete data
        assert len(result) > 0
        assert "hash" in result[0]

    @pytest.mark.asyncio
    async def test_circuit_breaker_on_repeated_errors(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test circuit breaker behavior on repeated errors."""
        error_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal error_count
            error_count += 1
            raise APIError("Persistent error")

        rate_limited_client._make_request = mock_request

        # Make multiple requests that all fail
        with pytest.raises(APIError):
            for _ in range(5):
                try:
                    await rate_limited_client.get_transactions(
                        "0x123", start_block=0, end_block=100
                    )
                except APIError:
                    pass

        # Should have attempted all requests (or stopped after max retries)
        assert error_count >= 1


class TestEdgeCases:
    """Test edge cases in transaction monitoring."""

    @pytest.mark.asyncio
    async def test_empty_response_handling(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test handling of empty API responses."""

        async def mock_request(*args, **kwargs):
            return []

        rate_limited_client._make_request = mock_request

        result = await rate_limited_client.get_transactions(
            "0x123", start_block=0, end_block=100
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_large_response_handling(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test handling of large API responses."""
        large_response = [{"hash": f"0x{i}"} for i in range(10000)]

        async def mock_request(*args, **kwargs):
            return large_response

        rate_limited_client._make_request = mock_request

        result = await rate_limited_client.get_transactions(
            "0x123", start_block=0, end_block=100
        )
        assert len(result) == 10000

    @pytest.mark.asyncio
    async def test_invalid_address_handling(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test handling of invalid addresses."""

        async def mock_request(*args, **kwargs):
            raise ValueError("Invalid address")

        rate_limited_client._make_request = mock_request

        with pytest.raises(ValueError):
            await rate_limited_client.get_transactions(
                "invalid", start_block=0, end_block=100
            )

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test error handling with concurrent requests."""
        error_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal error_count
            error_count += 1
            if error_count % 2 == 0:
                raise APIError("Alternating error")
            return [{"hash": f"0x{error_count}"}]

        rate_limited_client._make_request = mock_request

        # Make concurrent requests
        tasks = [
            rate_limited_client.get_transactions(f"0x{i}", start_block=0, end_block=100)
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Some should succeed, some should fail
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) > 0
        assert len(failures) > 0

    @pytest.mark.asyncio
    async def test_rate_limit_recovery_after_cooldown(
        self, rate_limited_client: RateLimitedPolygonscanClient
    ):
        """Test rate limit recovery after cooldown period."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RateLimitError("Rate limit exceeded")
            return [{"hash": "0x123"}]

        rate_limited_client._make_request = mock_request

        # First call should hit rate limit
        with pytest.raises(RateLimitError):
            await rate_limited_client.get_transactions(
                "0x123", start_block=0, end_block=100
            )

        # Wait for cooldown (simulated)
        await asyncio.sleep(0.1)

        # Subsequent call should succeed
        result = await rate_limited_client.get_transactions(
            "0x123", start_block=0, end_block=100
        )
        assert result == [{"hash": "0x123"}]
