"""Advanced rate limiter for QuickNode RPC API with token bucket algorithm.

This module provides robust rate limiting to prevent API bans while maintaining
high throughput for wallet monitoring operations. Features include:
- Token bucket algorithm for smooth rate limiting
- Adaptive rate adjustment based on 429 responses
- Exponential backoff for rate limit errors
- Endpoint health tracking and automatic failover
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

from core.exceptions import APIError, RateLimitError

logger = logging.getLogger(__name__)

# Rate Limiting Constants
DEFAULT_INITIAL_RATE_REQUESTS_PER_SECOND = 10.0  # Initial requests per second
DEFAULT_MAX_RATE_REQUESTS_PER_SECOND = 20.0  # Maximum requests per second
DEFAULT_MIN_RATE_REQUESTS_PER_SECOND = 1.0  # Minimum requests per second
DEFAULT_BUCKET_CAPACITY = 30  # Token bucket burst capacity
DEFAULT_MAX_CONCURRENT_REQUESTS = 3  # Maximum concurrent requests
DEFAULT_BACKOFF_BASE = 2.0  # Exponential backoff base multiplier
DEFAULT_MAX_BACKOFF_SECONDS = 300.0  # Maximum backoff time (5 minutes)
MIN_TOKEN_REFILL_RATE = 0.1  # Minimum token refill rate per second

# Endpoint Health Constants
MAX_CONSECUTIVE_FAILURES = 5  # Maximum consecutive failures before marking unhealthy
RATE_LIMIT_COOLDOWN_SECONDS = 300  # Cooldown period after rate limit (5 minutes)
STATS_LOG_INTERVAL_SECONDS = 60  # Interval for logging statistics (1 minute)

# HTTP Constants
HTTP_STATUS_OK = 200
HTTP_STATUS_RATE_LIMITED = 429
HTTP_TIMEOUT_TOTAL_SECONDS = 30  # Total HTTP timeout
HTTP_TIMEOUT_CONNECT_SECONDS = 10  # Connection timeout

# Response Time Calculation Constants
RESPONSE_TIME_AVG_WEIGHT_RECENT = 0.1  # Weight for recent response time
RESPONSE_TIME_AVG_WEIGHT_HISTORICAL = 0.9  # Weight for historical average


class EndpointStatus(Enum):
    """Status enumeration for RPC endpoint health.

    Attributes:
        ACTIVE: Endpoint is healthy and operational.
        RATE_LIMITED: Endpoint is currently rate limited.
        FAILED: Endpoint has failed and is unavailable.
        UNKNOWN: Endpoint status is unknown (initial state).
    """

    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class EndpointHealth:
    """Health metrics for an RPC endpoint.

    Tracks endpoint health status, request statistics, and response times
    to enable intelligent endpoint selection and failover.

    Attributes:
        url: Endpoint URL.
        status: Current endpoint status.
        consecutive_failures: Number of consecutive failures.
        last_rate_limit: Timestamp of last rate limit event.
        last_success: Timestamp of last successful request.
        total_requests: Total number of requests made.
        successful_requests: Number of successful requests.
        rate_limited_requests: Number of rate-limited requests.
        failed_requests: Number of failed requests.
        avg_response_time: Average response time in seconds.
        last_response_time: Response time of last request in seconds.
    """

    url: str
    status: EndpointStatus = EndpointStatus.UNKNOWN
    consecutive_failures: int = 0
    last_rate_limit: Optional[float] = None
    last_success: Optional[float] = None
    total_requests: int = 0
    successful_requests: int = 0
    rate_limited_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_response_time: Optional[float] = None

    def get_success_rate(self) -> float:
        """Calculate success rate as a fraction between 0.0 and 1.0.

        Returns:
            Success rate (successful_requests / total_requests).
            Returns 1.0 if no requests have been made yet.
        """
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    def is_healthy(self) -> bool:
        """Check if endpoint is currently healthy.

        An endpoint is considered unhealthy if:
        - Status is FAILED
        - Consecutive failures exceed MAX_CONSECUTIVE_FAILURES
        - Recently rate limited (within RATE_LIMIT_COOLDOWN_SECONDS)

        Returns:
            True if endpoint is healthy and available for requests.
        """
        if self.status == EndpointStatus.FAILED:
            return False
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            return False
        if (
            self.last_rate_limit
            and (time.time() - self.last_rate_limit) < RATE_LIMIT_COOLDOWN_SECONDS
        ):
            return False
        return True


class TokenBucket:
    """
    Token bucket algorithm for rate limiting.

    Tokens are added at a constant rate (refill_rate per second).
    Each request consumes tokens. If no tokens are available, the request must wait.
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        initial_tokens: Optional[int] = None,
    ) -> None:
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
            initial_tokens: Initial token count (defaults to capacity)
        """
        self.capacity = capacity
        self._refill_rate = refill_rate
        self.tokens = float(initial_tokens if initial_tokens is not None else capacity)
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    @property
    def refill_rate(self) -> float:
        """Get current refill rate"""
        return self._refill_rate

    @refill_rate.setter
    def refill_rate(self, value: float) -> None:
        """Update refill rate.

        Args:
            value: New refill rate in tokens per second.
                Will be clamped to minimum of MIN_TOKEN_REFILL_RATE.
        """
        self._refill_rate = max(MIN_TOKEN_REFILL_RATE, value)

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Wait time in seconds (0 if tokens available immediately)
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_refill

            # Refill tokens based on elapsed time
            self.tokens = min(
                self.capacity, self.tokens + (elapsed * self._refill_rate)
            )
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0

            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self._refill_rate
            self.tokens = 0.0
            return wait_time

    async def get_available_tokens(self) -> float:
        """Get current available tokens"""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(
                self.capacity, self.tokens + (elapsed * self._refill_rate)
            )
            self.last_refill = now
            return self.tokens


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter with token bucket algorithm.

    Features:
    - Token bucket for smooth rate limiting
    - Adaptive rate adjustment based on 429 responses
    - Exponential backoff for rate limit errors
    - Endpoint health tracking
    - Automatic endpoint failover
    """

    def __init__(
        self,
        initial_rate: float = DEFAULT_INITIAL_RATE_REQUESTS_PER_SECOND,
        max_rate: float = DEFAULT_MAX_RATE_REQUESTS_PER_SECOND,
        min_rate: float = DEFAULT_MIN_RATE_REQUESTS_PER_SECOND,
        bucket_capacity: int = DEFAULT_BUCKET_CAPACITY,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        max_backoff: float = DEFAULT_MAX_BACKOFF_SECONDS,
    ) -> None:
        """Initialize adaptive rate limiter.

        Creates a rate limiter with token bucket algorithm and adaptive
        rate adjustment based on API responses.

        Args:
            initial_rate: Initial requests per second.
                Defaults to DEFAULT_INITIAL_RATE_REQUESTS_PER_SECOND.
            max_rate: Maximum allowed requests per second.
                Defaults to DEFAULT_MAX_RATE_REQUESTS_PER_SECOND.
            min_rate: Minimum requests per second when throttled.
                Defaults to DEFAULT_MIN_RATE_REQUESTS_PER_SECOND.
            bucket_capacity: Token bucket burst capacity.
                Defaults to DEFAULT_BUCKET_CAPACITY.
            max_concurrent: Maximum concurrent requests allowed.
                Defaults to DEFAULT_MAX_CONCURRENT_REQUESTS.
            backoff_base: Base multiplier for exponential backoff.
                Defaults to DEFAULT_BACKOFF_BASE.
            max_backoff: Maximum backoff time in seconds.
                Defaults to DEFAULT_MAX_BACKOFF_SECONDS.
        """
        self.current_rate = initial_rate
        self.max_rate = max_rate
        self.min_rate = min_rate
        self.bucket_capacity = bucket_capacity
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff

        # Token bucket
        self.token_bucket = TokenBucket(
            capacity=bucket_capacity, refill_rate=initial_rate
        )

        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Rate limit tracking
        self.last_rate_limit_time: Optional[float] = None
        self.consecutive_rate_limits: int = 0
        self.total_requests: int = 0
        self.rate_limited_requests: int = 0

        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "rate_limited_requests": 0,
            "failed_requests": 0,
            "avg_wait_time": 0.0,
            "current_rate": initial_rate,
        }

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.

        This method will block until tokens are available and a semaphore slot is free.
        """
        # Wait for semaphore (concurrency control)
        await self.semaphore.acquire()

        try:
            # Wait for token bucket (rate limiting)
            wait_time = await self.token_bucket.acquire(1)
            if wait_time > 0:
                logger.debug(
                    "Rate limiting: waiting %.2fs (rate: %.2f req/s)",
                    wait_time,
                    self.current_rate,
                )
                await asyncio.sleep(wait_time)

            async with self._lock:
                self.total_requests += 1
                self.stats["total_requests"] = self.total_requests
        except Exception:
            self.semaphore.release()
            raise

    def release(self) -> None:
        """Release semaphore after request completes"""
        self.semaphore.release()

    async def handle_rate_limit(self, retry_after: Optional[int] = None) -> float:
        """
        Handle rate limit response and adjust rate.

        Args:
            retry_after: Seconds to wait before retrying (from Retry-After header)

        Returns:
            Wait time in seconds before retrying
        """
        async with self._lock:
            self.rate_limited_requests += 1
            self.consecutive_rate_limits += 1
            self.last_rate_limit_time = time.time()
            self.stats["rate_limited_requests"] = self.rate_limited_requests

            # Reduce rate aggressively on rate limit
            RATE_REDUCTION_MULTIPLIER = 0.5  # Cut rate in half
            self.current_rate = max(
                self.min_rate, self.current_rate * RATE_REDUCTION_MULTIPLIER
            )
            self.token_bucket.refill_rate = self.current_rate

            # Calculate exponential backoff
            if retry_after:
                wait_time = float(retry_after)
            else:
                wait_time = min(
                    self.max_backoff,
                    self.backoff_base**self.consecutive_rate_limits,
                )

            logger.warning(
                "Rate limit hit. Reducing rate to %.2f req/s. Waiting %.2fs before retry.",
                self.current_rate,
                wait_time,
            )

            return wait_time

    async def handle_success(self) -> None:
        """Handle successful request and gradually increase rate"""
        async with self._lock:
            self.stats["successful_requests"] += 1

            # Gradually increase rate if no recent rate limits
            RATE_INCREASE_COOLDOWN_SECONDS = 60  # 1 minute cooldown
            RATE_INCREASE_PERCENTAGE = 0.01  # 1% increase per request

            if (
                self.last_rate_limit_time is None
                or (time.time() - self.last_rate_limit_time)
                > RATE_INCREASE_COOLDOWN_SECONDS
            ):
                if self.consecutive_rate_limits > 0:
                    self.consecutive_rate_limits = max(
                        0, self.consecutive_rate_limits - 1
                    )

                # Gradually increase rate after cooldown period
                if self.current_rate < self.max_rate:
                    self.current_rate = min(
                        self.max_rate,
                        self.current_rate * (1.0 + RATE_INCREASE_PERCENTAGE),
                    )
                    self.token_bucket.refill_rate = self.current_rate

            self.stats["current_rate"] = self.current_rate

    async def handle_failure(self) -> None:
        """Handle failed request"""
        async with self._lock:
            self.stats["failed_requests"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limiter statistics"""
        # Note: This is synchronous, so we can't await get_available_tokens
        # We'll calculate it synchronously for stats
        success_rate = (
            self.stats["successful_requests"] / self.stats["total_requests"]
            if self.stats["total_requests"] > 0
            else 0.0
        )

        return {
            **self.stats,
            "success_rate": success_rate,
            "consecutive_rate_limits": self.consecutive_rate_limits,
            "last_rate_limit_time": self.last_rate_limit_time,
        }


class QuickNodeRPCClient:
    """
    QuickNode RPC client with advanced rate limiting, endpoint failover,
    and exponential backoff.

    Features:
    - Token bucket rate limiting with adaptive adjustment
    - Semaphore-based concurrency control (max 3 concurrent)
    - Exponential backoff for 429 responses
    - Automatic endpoint failover
    - Health monitoring and logging
    """

    def __init__(
        self,
        primary_endpoint: str,
        fallback_endpoints: Optional[List[str]] = None,
        rate_limiter: Optional[AdaptiveRateLimiter] = None,
    ) -> None:
        """
        Initialize QuickNode RPC client.

        Args:
            primary_endpoint: Primary QuickNode RPC endpoint URL
            fallback_endpoints: List of fallback RPC endpoints
            rate_limiter: Optional custom rate limiter
        """
        self.primary_endpoint = primary_endpoint
        self.fallback_endpoints = fallback_endpoints or []
        self.all_endpoints = [primary_endpoint] + self.fallback_endpoints

        # Endpoint health tracking
        self.endpoint_health: Dict[str, EndpointHealth] = {
            url: EndpointHealth(url=url) for url in self.all_endpoints
        }

        # Current active endpoint
        self.current_endpoint = primary_endpoint

        # Rate limiter
        self.rate_limiter = rate_limiter or AdaptiveRateLimiter()

        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None

        # Statistics
        self.request_count = 0
        self.last_stats_log = time.time()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session.

        Creates a new session if one doesn't exist or the current session
        is closed. Uses configured timeout constants.

        Returns:
            Active aiohttp ClientSession instance.
        """
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(
                total=HTTP_TIMEOUT_TOTAL_SECONDS,
                connect=HTTP_TIMEOUT_CONNECT_SECONDS,
            )
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close(self) -> None:
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

    def _get_healthy_endpoint(self) -> Optional[str]:
        """Get the healthiest available endpoint"""
        healthy_endpoints = [
            url for url in self.all_endpoints if self.endpoint_health[url].is_healthy()
        ]

        if not healthy_endpoints:
            # If no healthy endpoints, use primary anyway
            return self.primary_endpoint

        # Sort by success rate and response time
        healthy_endpoints.sort(
            key=lambda url: (
                -self.endpoint_health[url].get_success_rate(),
                self.endpoint_health[url].avg_response_time or float("inf"),
            )
        )

        return healthy_endpoints[0]

    async def _make_request(
        self,
        method: str,
        params: List[Any],
        endpoint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Make RPC request with rate limiting and error handling.

        Args:
            method: RPC method name (e.g., "eth_getBlockByNumber")
            params: RPC method parameters
            endpoint: Specific endpoint to use (None for auto-selection)

        Returns:
            RPC response data

        Raises:
            RateLimitError: If rate limited and all retries exhausted
            APIError: If request fails
        """
        endpoint = endpoint or self._get_healthy_endpoint() or self.current_endpoint
        health = self.endpoint_health[endpoint]

        # Acquire rate limit permission
        await self.rate_limiter.acquire()

        try:
            session = await self._get_session()
            start_time = time.time()

            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": self.request_count,
            }

            async with session.post(
                endpoint, json=payload, headers={"Content-Type": "application/json"}
            ) as response:
                response_time = time.time() - start_time
                health.last_response_time = response_time
                health.total_requests += 1

                # Update average response time using exponential moving average
                if health.avg_response_time == 0.0:
                    health.avg_response_time = response_time
                else:
                    health.avg_response_time = (
                        health.avg_response_time * RESPONSE_TIME_AVG_WEIGHT_HISTORICAL
                        + response_time * RESPONSE_TIME_AVG_WEIGHT_RECENT
                    )

                if response.status == HTTP_STATUS_RATE_LIMITED:
                    # Rate limited
                    health.status = EndpointStatus.RATE_LIMITED
                    health.rate_limited_requests += 1
                    health.last_rate_limit = time.time()
                    health.consecutive_failures += 1

                    # Get Retry-After header if available
                    retry_after = response.headers.get("Retry-After")
                    retry_after_seconds = int(retry_after) if retry_after else None

                    # Handle rate limit
                    wait_time = await self.rate_limiter.handle_rate_limit(
                        retry_after_seconds
                    )

                    # Try fallback endpoint if available
                    if endpoint != self.primary_endpoint:
                        logger.warning(
                            "Rate limited on fallback endpoint %s. Trying primary.",
                            endpoint,
                        )
                        await asyncio.sleep(wait_time)
                        return await self._make_request(
                            method, params, self.primary_endpoint
                        )

                    # If primary is rate limited, try fallbacks
                    for fallback in self.fallback_endpoints:
                        if fallback != endpoint:
                            fallback_health = self.endpoint_health[fallback]
                            if fallback_health.is_healthy():
                                logger.info(
                                    "Switching to fallback endpoint: %s",
                                    fallback,
                                )
                                self.current_endpoint = fallback
                                await asyncio.sleep(wait_time)
                                return await self._make_request(
                                    method, params, fallback
                                )

                    # All endpoints rate limited
                    raise RateLimitError(retry_after=int(wait_time), endpoint=endpoint)

                elif response.status == HTTP_STATUS_OK:
                    # Success
                    health.status = EndpointStatus.ACTIVE
                    health.successful_requests += 1
                    health.last_success = time.time()
                    health.consecutive_failures = 0

                    await self.rate_limiter.handle_success()

                    data = await response.json()

                    if "error" in data:
                        error_msg = data["error"].get("message", "Unknown RPC error")
                        raise APIError(f"RPC error: {error_msg}")

                    return data.get("result")

                else:
                    # Other error
                    health.status = EndpointStatus.FAILED
                    health.failed_requests += 1
                    health.consecutive_failures += 1

                    await self.rate_limiter.handle_failure()

                    error_text = await response.text()
                    raise APIError(
                        f"RPC request failed: HTTP {response.status} - {error_text[:200]}"
                    )

        except RateLimitError:
            raise
        except Exception as e:
            health.failed_requests += 1
            health.consecutive_failures += 1
            await self.rate_limiter.handle_failure()
            raise APIError(f"RPC request exception: {e}") from e
        finally:
            self.rate_limiter.release()
            self.request_count += 1

            # Log statistics periodically
            if time.time() - self.last_stats_log > STATS_LOG_INTERVAL_SECONDS:
                await self._log_statistics()
                self.last_stats_log = time.time()

    async def _log_statistics(self) -> None:
        """Log current rate limit statistics.

        Logs comprehensive statistics including current rate, total requests,
        success rate, rate-limited requests, and endpoint health information.
        """
        stats = self.rate_limiter.get_stats()
        endpoint_stats = {
            url: {
                "status": health.status.value,
                "success_rate": health.get_success_rate(),
                "total_requests": health.total_requests,
                "rate_limited": health.rate_limited_requests,
            }
            for url, health in self.endpoint_health.items()
        }

        logger.info(
            "📊 Rate Limiter Stats: rate=%.2f req/s, total=%d, success_rate=%.1f%%, "
            "rate_limited=%d, current_endpoint=%s",
            stats["current_rate"],
            stats["total_requests"],
            stats["success_rate"] * 100,
            stats["rate_limited_requests"],
            self.current_endpoint,
        )

        logger.debug(
            "Endpoint health: %s",
            {
                url: {
                    "status": health.status.value,
                    "success_rate": f"{health.get_success_rate():.1%}",
                    "avg_response_time": f"{health.avg_response_time:.3f}s",
                }
                for url, health in self.endpoint_health.items()
            },
        )

    async def call(
        self, method: str, params: List[Any], endpoint: Optional[str] = None
    ) -> Any:
        """
        Make RPC call with automatic retry and endpoint failover.

        Args:
            method: RPC method name
            params: RPC method parameters
            endpoint: Optional specific endpoint to use

        Returns:
            RPC response result
        """
        return await self._make_request(method, params, endpoint)

    async def get_block_number(self) -> int:
        """Get current block number from the blockchain.

        Returns:
            Current block number as an integer.

        Raises:
            APIError: If RPC call fails.
        """
        result = await self.call("eth_blockNumber", [])
        return int(result, 16)

    async def get_transactions(
        self, address: str, from_block: int, to_block: int
    ) -> List[Dict[str, Any]]:
        """Get transactions for an address.

        Note: This is a placeholder implementation. Real implementation would
        use eth_getLogs or similar methods depending on QuickNode capabilities.

        Args:
            address: Wallet address to query transactions for.
            from_block: Starting block number.
            to_block: Ending block number.

        Returns:
            List of transaction dictionaries. Currently returns empty list
            as this method needs QuickNode-specific implementation.

        Raises:
            APIError: If RPC call fails.
        """
        logger.warning(
            "get_transactions not fully implemented - needs QuickNode-specific implementation"
        )
        return []

    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary for all endpoints.

        Returns:
            Dictionary containing:
            - current_endpoint: Currently active endpoint URL
            - rate_limiter_stats: Statistics from rate limiter
            - endpoints: Health metrics for each endpoint including:
                - status: Endpoint status
                - success_rate: Success rate (0.0-1.0)
                - total_requests: Total requests made
                - successful_requests: Successful requests count
                - rate_limited_requests: Rate-limited requests count
                - failed_requests: Failed requests count
                - avg_response_time: Average response time in seconds
                - is_healthy: Whether endpoint is currently healthy
        """
        return {
            "current_endpoint": self.current_endpoint,
            "rate_limiter_stats": self.rate_limiter.get_stats(),
            "endpoints": {
                url: {
                    "status": health.status.value,
                    "success_rate": health.get_success_rate(),
                    "total_requests": health.total_requests,
                    "successful_requests": health.successful_requests,
                    "rate_limited_requests": health.rate_limited_requests,
                    "failed_requests": health.failed_requests,
                    "avg_response_time": health.avg_response_time,
                    "is_healthy": health.is_healthy(),
                }
                for url, health in self.endpoint_health.items()
            },
        }
