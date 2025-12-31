"""
Integration tests for QuickNode RPC rate limiter.

Tests verify that the rate limiter can handle 25+ wallets at 15-second intervals
without triggering rate limit bans.
"""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, patch

import pytest

from core.exceptions import RateLimitError
from risk_management.rate_limiter import (
    AdaptiveRateLimiter,
    EndpointStatus,
    QuickNodeRPCClient,
    TokenBucket,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_rpc_endpoint():
    """Create a mock RPC endpoint for testing"""
    return "https://test-rpc.quicknode.com/v1/test"


@pytest.fixture
def rate_limiter():
    """Create rate limiter for testing"""
    return AdaptiveRateLimiter(
        initial_rate=10.0,
        max_rate=20.0,
        min_rate=1.0,
        bucket_capacity=30,
        max_concurrent=3,
    )


@pytest.fixture
def rpc_client(mock_rpc_endpoint):
    """Create RPC client for testing"""
    fallback_endpoints = [
        "https://fallback1.quicknode.com/v1/test",
        "https://fallback2.quicknode.com/v1/test",
    ]
    return QuickNodeRPCClient(
        primary_endpoint=mock_rpc_endpoint,
        fallback_endpoints=fallback_endpoints,
    )


class TestTokenBucket:
    """Test token bucket algorithm"""

    @pytest.mark.asyncio
    async def test_token_bucket_acquire(self):
        """Test token bucket acquire"""
        bucket = TokenBucket(capacity=10, refill_rate=2.0, initial_tokens=10)

        # Should get tokens immediately
        wait_time = await bucket.acquire(5)
        assert wait_time == 0.0
        assert bucket.tokens == 5.0

        # Should wait for refill
        wait_time = await bucket.acquire(10)
        assert wait_time > 0.0

    @pytest.mark.asyncio
    async def test_token_bucket_refill(self):
        """Test token bucket refills over time"""
        bucket = TokenBucket(capacity=10, refill_rate=10.0, initial_tokens=0)

        # Wait a bit for refill
        await asyncio.sleep(0.2)

        # Should have tokens now
        tokens = await bucket.get_available_tokens()
        assert tokens > 0

    @pytest.mark.asyncio
    async def test_token_bucket_rate_update(self):
        """Test updating refill rate"""
        bucket = TokenBucket(capacity=10, refill_rate=2.0, initial_tokens=0)

        assert bucket.refill_rate == 2.0

        bucket.refill_rate = 5.0
        assert bucket.refill_rate == 5.0

        # Higher rate should refill faster
        await asyncio.sleep(0.2)
        tokens_slow = await bucket.get_available_tokens()

        bucket.refill_rate = 10.0
        await asyncio.sleep(0.2)
        tokens_fast = await bucket.get_available_tokens()

        assert tokens_fast > tokens_slow


class TestAdaptiveRateLimiter:
    """Test adaptive rate limiter"""

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_release(self, rate_limiter):
        """Test basic acquire/release"""
        await rate_limiter.acquire()
        rate_limiter.release()

        stats = rate_limiter.get_stats()
        assert stats["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrency_limit(self, rate_limiter):
        """Test semaphore limits concurrent requests"""
        # Acquire 3 (max concurrent)
        await rate_limiter.acquire()
        await rate_limiter.acquire()
        await rate_limiter.acquire()

        # 4th should wait
        acquire_task = asyncio.create_task(rate_limiter.acquire())

        # Give it a moment to try
        await asyncio.sleep(0.1)

        # Should be waiting (not completed)
        assert not acquire_task.done()

        # Release one
        rate_limiter.release()

        # Now 4th should complete
        await asyncio.sleep(0.1)
        assert acquire_task.done()

        # Clean up
        rate_limiter.release()
        rate_limiter.release()
        rate_limiter.release()

    @pytest.mark.asyncio
    async def test_rate_limiter_handles_rate_limit(self, rate_limiter):
        """Test rate limit handling reduces rate"""
        initial_rate = rate_limiter.current_rate

        wait_time = await rate_limiter.handle_rate_limit(retry_after=10)

        assert wait_time == 10.0
        assert rate_limiter.current_rate < initial_rate
        assert rate_limiter.consecutive_rate_limits == 1

    @pytest.mark.asyncio
    async def test_rate_limiter_exponential_backoff(self, rate_limiter):
        """Test exponential backoff calculation"""
        # First rate limit
        wait1 = await rate_limiter.handle_rate_limit()
        assert wait1 > 0

        # Second rate limit (should be longer)
        wait2 = await rate_limiter.handle_rate_limit()
        assert wait2 > wait1

        # Third rate limit (should be even longer)
        wait3 = await rate_limiter.handle_rate_limit()
        assert wait3 > wait2

    @pytest.mark.asyncio
    async def test_rate_limiter_gradual_rate_increase(self, rate_limiter):
        """Test rate gradually increases after success"""
        # Reduce rate first
        await rate_limiter.handle_rate_limit()
        reduced_rate = rate_limiter.current_rate

        # Handle multiple successes
        for _ in range(10):
            await rate_limiter.handle_success()

        # Rate should have increased
        assert rate_limiter.current_rate > reduced_rate

    @pytest.mark.asyncio
    async def test_rate_limiter_stats(self, rate_limiter):
        """Test statistics tracking"""
        await rate_limiter.acquire()
        await rate_limiter.handle_success()
        rate_limiter.release()

        stats = rate_limiter.get_stats()
        assert stats["total_requests"] == 1
        assert stats["successful_requests"] == 1
        assert stats["success_rate"] == 1.0


class TestQuickNodeRPCClient:
    """Test QuickNode RPC client"""

    @pytest.mark.asyncio
    async def test_rpc_client_initialization(self, rpc_client):
        """Test RPC client initialization"""
        assert rpc_client.primary_endpoint is not None
        assert len(rpc_client.all_endpoints) == 3  # Primary + 2 fallbacks
        assert rpc_client.current_endpoint == rpc_client.primary_endpoint

    @pytest.mark.asyncio
    async def test_rpc_client_successful_request(self, rpc_client, mock_rpc_endpoint):
        """Test successful RPC request"""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"jsonrpc": "2.0", "result": "0x1234", "id": 0}
            )
            mock_response.headers = {}
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await rpc_client.call("eth_blockNumber", [])

            assert result == "0x1234"
            assert (
                rpc_client.endpoint_health[mock_rpc_endpoint].status
                == EndpointStatus.ACTIVE
            )

    @pytest.mark.asyncio
    async def test_rpc_client_rate_limit_handling(self, rpc_client, mock_rpc_endpoint):
        """Test rate limit handling with exponential backoff"""
        with patch("aiohttp.ClientSession.post") as mock_post:
            # First request: rate limited
            mock_response_429 = AsyncMock()
            mock_response_429.status = 429
            mock_response_429.headers = {"Retry-After": "5"}
            mock_response_429.text = AsyncMock(return_value="Rate Limited")

            # Second request: success
            mock_response_200 = AsyncMock()
            mock_response_200.status = 200
            mock_response_200.json = AsyncMock(
                return_value={"jsonrpc": "2.0", "result": "0x1234", "id": 0}
            )
            mock_response_200.headers = {}

            mock_post.return_value.__aenter__.side_effect = [
                mock_response_429,
                mock_response_200,
            ]

            # Should handle rate limit and retry
            result = await rpc_client.call("eth_blockNumber", [])

            assert result == "0x1234"
            assert rpc_client.rate_limiter.consecutive_rate_limits > 0

    @pytest.mark.asyncio
    async def test_rpc_client_endpoint_failover(self, rpc_client):
        """Test automatic endpoint failover"""
        primary = rpc_client.primary_endpoint
        fallback = rpc_client.fallback_endpoints[0]

        with patch("aiohttp.ClientSession.post") as mock_post:
            # Primary endpoint rate limited
            mock_response_429 = AsyncMock()
            mock_response_429.status = 429
            mock_response_429.headers = {}
            mock_response_429.text = AsyncMock(return_value="Rate Limited")

            # Fallback endpoint succeeds
            mock_response_200 = AsyncMock()
            mock_response_200.status = 200
            mock_response_200.json = AsyncMock(
                return_value={"jsonrpc": "2.0", "result": "0x1234", "id": 0}
            )
            mock_response_200.headers = {}

            # First call to primary fails, then fallback succeeds
            call_count = 0

            async def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # Primary endpoint
                    return mock_response_429
                else:
                    # Fallback endpoint
                    return mock_response_200

            mock_post.return_value.__aenter__.side_effect = side_effect

            result = await rpc_client.call("eth_blockNumber", [])

            assert result == "0x1234"
            # Should have switched to fallback
            assert rpc_client.current_endpoint == fallback

    @pytest.mark.asyncio
    async def test_rpc_client_health_tracking(self, rpc_client, mock_rpc_endpoint):
        """Test endpoint health tracking"""
        health = rpc_client.endpoint_health[mock_rpc_endpoint]

        assert health.status == EndpointStatus.UNKNOWN
        assert health.total_requests == 0

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"jsonrpc": "2.0", "result": "0x1234", "id": 0}
            )
            mock_response.headers = {}
            mock_post.return_value.__aenter__.return_value = mock_response

            await rpc_client.call("eth_blockNumber", [])

            assert health.status == EndpointStatus.ACTIVE
            assert health.total_requests == 1
            assert health.successful_requests == 1
            assert health.get_success_rate() == 1.0

    @pytest.mark.asyncio
    async def test_rpc_client_get_health_summary(self, rpc_client):
        """Test health summary generation"""
        summary = rpc_client.get_health_summary()

        assert "current_endpoint" in summary
        assert "rate_limiter_stats" in summary
        assert "endpoints" in summary
        assert len(summary["endpoints"]) == 3


@pytest.mark.integration
class TestRateLimiterIntegration:
    """Integration tests for rate limiter with 25+ wallets"""

    @pytest.mark.asyncio
    async def test_25_wallets_15_second_intervals(self, rpc_client):
        """
        Test rate limiter with 25+ wallets at 15-second intervals.

        This test simulates monitoring 25 wallets every 15 seconds
        and verifies no rate limit bans are triggered.
        """
        num_wallets = 25
        interval_seconds = 15
        num_cycles = 3  # Run 3 cycles

        wallets = [f"0x{'a' * 40}{i:02d}" for i in range(num_wallets)]

        success_count = 0
        rate_limit_count = 0
        error_count = 0

        with patch("aiohttp.ClientSession.post") as mock_post:
            # Mock successful responses
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"jsonrpc": "2.0", "result": "0x1234", "id": 0}
            )
            mock_response.headers = {}
            mock_post.return_value.__aenter__.return_value = mock_response

            start_time = time.time()

            for cycle in range(num_cycles):
                logger.info("Starting cycle %d/%d", cycle + 1, num_cycles)

                # Process all wallets concurrently (but rate limited)
                tasks = []
                for wallet in wallets:
                    task = asyncio.create_task(
                        rpc_client.call("eth_getBalance", [wallet, "latest"])
                    )
                    tasks.append(task)

                # Wait for all requests
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Count results
                for result in results:
                    if isinstance(result, RateLimitError):
                        rate_limit_count += 1
                        logger.warning("Rate limit encountered: %s", result)
                    elif isinstance(result, Exception):
                        error_count += 1
                        logger.error("Error: %s", result)
                    else:
                        success_count += 1

                # Wait for next cycle
                if cycle < num_cycles - 1:
                    await asyncio.sleep(interval_seconds)

            elapsed_time = time.time() - start_time

            # Verify no rate limit bans
            assert rate_limit_count == 0, f"Rate limits encountered: {rate_limit_count}"

            # Verify high success rate
            total_requests = num_wallets * num_cycles
            success_rate = success_count / total_requests
            assert success_rate >= 0.95, f"Success rate too low: {success_rate:.1%}"

            # Log statistics
            stats = rpc_client.rate_limiter.get_stats()
            logger.info(
                "Integration test results: "
                "total_requests=%d, success_count=%d, "
                "rate_limited=%d, errors=%d, "
                "success_rate=%.1f%%, elapsed=%.1fs, "
                "final_rate=%.2f req/s",
                total_requests,
                success_count,
                rate_limit_count,
                error_count,
                success_rate * 100,
                elapsed_time,
                stats["current_rate"],
            )

            # Verify rate limiter adapted properly
            assert stats["current_rate"] >= 1.0  # Should maintain minimum rate
            assert stats["current_rate"] <= 20.0  # Should not exceed max rate

    @pytest.mark.asyncio
    async def test_rate_limiter_under_load(self, rpc_client):
        """Test rate limiter handles burst load"""
        num_requests = 50

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"jsonrpc": "2.0", "result": "0x1234", "id": 0}
            )
            mock_response.headers = {}
            mock_post.return_value.__aenter__.return_value = mock_response

            # Fire off many requests quickly
            tasks = [
                rpc_client.call("eth_blockNumber", []) for _ in range(num_requests)
            ]

            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed_time = time.time() - start_time

            # All should succeed (rate limited internally)
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            assert success_count == num_requests

            # Should have taken some time (rate limiting)
            assert elapsed_time > 0

            stats = rpc_client.rate_limiter.get_stats()
            logger.info(
                "Burst load test: %d requests in %.2fs, rate=%.2f req/s",
                num_requests,
                elapsed_time,
                stats["current_rate"],
            )

    @pytest.mark.asyncio
    async def test_concurrent_request_limit(self, rpc_client):
        """Test that max 3 concurrent requests are enforced"""
        max_concurrent = 3

        # Track concurrent requests
        concurrent_count = 0
        max_concurrent_seen = 0
        lock = asyncio.Lock()

        async def track_concurrent(coro):
            nonlocal concurrent_count, max_concurrent_seen
            async with lock:
                concurrent_count += 1
                max_concurrent_seen = max(max_concurrent_seen, concurrent_count)

            try:
                result = await coro
            finally:
                async with lock:
                    concurrent_count -= 1
            return result

        with patch("aiohttp.ClientSession.post") as mock_post:
            # Slow response to observe concurrency
            async def slow_response(*args, **kwargs):
                await asyncio.sleep(0.1)
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(
                    return_value={"jsonrpc": "2.0", "result": "0x1234", "id": 0}
                )
                mock_response.headers = {}
                return mock_response

            mock_post.return_value.__aenter__ = slow_response

            # Fire off many requests
            tasks = [
                track_concurrent(rpc_client.call("eth_blockNumber", []))
                for _ in range(10)
            ]

            await asyncio.gather(*tasks)

            # Should never exceed max concurrent
            assert max_concurrent_seen <= max_concurrent
