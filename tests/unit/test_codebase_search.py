"""
Unit tests for codebase_search MCP server.

This module provides comprehensive tests for the CodebaseSearchServer class,
including pattern searching, caching, rate limiting, and circuit breaker
functionality.
"""

import time
from pathlib import Path

import pytest

# Add project root to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.mcp_config import CodebaseSearchConfig, SearchPattern
from mcp.codebase_search import (
    CodebaseSearchServer,
    RateLimiter,
    SearchCircuitBreaker,
    SearchResult,
    get_search_server,
)


class TestSearchCircuitBreaker:
    """Test suite for SearchCircuitBreaker class."""

    @pytest.fixture
    def circuit_breaker(self) -> SearchCircuitBreaker:
        """Create a circuit breaker instance for testing."""
        return SearchCircuitBreaker(failure_threshold=3, recovery_timeout_seconds=1)

    def test_initial_state_closed(self, circuit_breaker: SearchCircuitBreaker) -> None:
        """Test that circuit breaker starts in closed state."""
        assert circuit_breaker.state == "closed"
        assert not circuit_breaker.is_tripped()

    def test_record_failure(self, circuit_breaker: SearchCircuitBreaker) -> None:
        """Test that failures are recorded correctly."""
        circuit_breaker.record_failure()
        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.state == "closed"

    def test_circuit_opens_after_threshold(
        self, circuit_breaker: SearchCircuitBreaker
    ) -> None:
        """Test that circuit opens after failure threshold is reached."""
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.state == "open"
        assert circuit_breaker.is_tripped()

    def test_circuit_resets_on_success(
        self, circuit_breaker: SearchCircuitBreaker
    ) -> None:
        """Test that circuit resets to closed after success in half-open state."""
        # Open circuit
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.state == "open"

        # Wait for recovery timeout
        time.sleep(1.1)

        # Check circuit is now half-open
        assert not circuit_breaker.is_tripped()

        # Record success
        circuit_breaker.record_success()

        assert circuit_breaker.state == "closed"
        assert circuit_breaker.failure_count == 0

    def test_half_open_state(self, circuit_breaker: SearchCircuitBreaker) -> None:
        """Test that circuit transitions to half-open after recovery timeout."""
        # Open circuit
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.state == "open"

        # Wait for recovery timeout
        time.sleep(1.1)

        # Check circuit is now half-open (not tripped but allows requests)
        assert circuit_breaker.state == "half-open"
        assert not circuit_breaker.is_tripped()


class TestRateLimiter:
    """Test suite for RateLimiter class."""

    @pytest.fixture
    def rate_limiter(self) -> RateLimiter:
        """Create a rate limiter instance for testing."""
        return RateLimiter(max_requests_per_minute=3)

    @pytest.mark.asyncio
    async def test_acquire_under_limit(self, rate_limiter: RateLimiter) -> None:
        """Test that requests are allowed under the limit."""
        assert await rate_limiter.acquire() is True
        assert await rate_limiter.acquire() is True
        assert await rate_limiter.acquire() is True

    @pytest.mark.asyncio
    async def test_acquire_over_limit(self, rate_limiter: RateLimiter) -> None:
        """Test that requests are rejected over the limit."""
        # Use up all requests
        for _ in range(3):
            await rate_limiter.acquire()

        # Next request should be rejected
        assert await rate_limiter.acquire() is False

    @pytest.mark.asyncio
    async def test_reset_after_timeout(self, rate_limiter: RateLimiter) -> None:
        """Test that limit resets after timeout."""
        # Use up all requests
        for _ in range(3):
            await rate_limiter.acquire()

        assert await rate_limiter.acquire() is False

        # Wait for timeout (should be less than 60 seconds in practice)
        # For testing, we'll just check the wait time
        wait_time = rate_limiter.get_wait_time()
        assert wait_time > 0

    @pytest.mark.asyncio
    async def test_get_wait_time(self, rate_limiter: RateLimiter) -> None:
        """Test wait time calculation."""
        # No requests yet
        assert rate_limiter.get_wait_time() == 0.0

        # Use up all requests
        for _ in range(3):
            await rate_limiter.acquire()

        # Should have wait time
        wait_time = rate_limiter.get_wait_time()
        assert wait_time > 0
        assert wait_time <= 60.0


class TestCodebaseSearchConfig:
    """Test suite for CodebaseSearchConfig class."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = CodebaseSearchConfig()

        assert config.enabled is True
        assert config.cache_enabled is True
        assert config.cache_ttl_seconds == 3600
        assert config.max_results == 1000
        assert config.timeout_seconds == 30
        assert config.rate_limit_requests_per_minute == 10

    def test_search_patterns_defined(self) -> None:
        """Test that default search patterns are defined."""
        config = CodebaseSearchConfig()

        assert "money_calculations" in config.search_patterns
        assert "risk_controls" in config.search_patterns
        assert "variable_conflicts" in config.search_patterns
        assert "api_endpoints" in config.search_patterns

    def test_extended_patterns_initialized(self) -> None:
        """Test that extended patterns are properly initialized."""
        config = CodebaseSearchConfig()

        assert len(config.extended_patterns) > 0

        for name, pattern in config.extended_patterns.items():
            assert isinstance(pattern, SearchPattern)
            assert pattern.name == name
            assert len(pattern.pattern) > 0

    def test_get_pattern(self) -> None:
        """Test getting a pattern by name."""
        config = CodebaseSearchConfig()

        pattern = config.get_pattern("money_calculations")
        assert pattern is not None
        assert isinstance(pattern, str)

    def test_get_nonexistent_pattern(self) -> None:
        """Test getting a pattern that doesn't exist."""
        config = CodebaseSearchConfig()

        pattern = config.get_pattern("nonexistent_pattern")
        assert pattern is None

    def test_add_custom_pattern(self) -> None:
        """Test adding a custom pattern."""
        config = CodebaseSearchConfig()

        config.add_custom_pattern(
            name="test_pattern",
            pattern=r"test_\w+",
            description="Test pattern",
            category="test",
            severity="info",
        )

        assert "test_pattern" in config.search_patterns
        assert "test_pattern" in config.extended_patterns

        test_pattern = config.get_extended_pattern("test_pattern")
        assert test_pattern is not None
        assert test_pattern.name == "test_pattern"

    def test_list_patterns(self) -> None:
        """Test listing all patterns."""
        config = CodebaseSearchConfig()

        patterns = config.list_patterns()

        assert isinstance(patterns, dict)
        assert len(patterns) > 0

        for name, info in patterns.items():
            assert "pattern" in info
            assert "description" in info
            assert "category" in info
            assert "severity" in info


class TestSearchResult:
    """Test suite for SearchResult class."""

    @pytest.fixture
    def sample_result(self) -> SearchResult:
        """Create a sample search result."""
        return SearchResult(
            file_path="/path/to/file.py",
            line_number=42,
            line_content="account_balance * risk_percent",
            pattern_name="money_calculations",
            matched_text="account_balance * risk_percent",
            context_before=["line 1", "line 2"],
            context_after=["line 3", "line 4"],
        )

    def test_to_dict(self, sample_result: SearchResult) -> None:
        """Test converting search result to dictionary."""
        result_dict = sample_result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["file_path"] == "/path/to/file.py"
        assert result_dict["line_number"] == 42
        assert result_dict["pattern_name"] == "money_calculations"
        assert result_dict["matched_text"] == "account_balance * risk_percent"

    def test_to_dict_strips_whitespace(self, sample_result: SearchResult) -> None:
        """Test that to_dict strips whitespace from context."""
        result_dict = sample_result.to_dict()

        # Context should be stripped of leading/trailing whitespace
        for line in result_dict["context_before"]:
            assert not line.startswith(" ")
            assert not line.endswith(" ")

        for line in result_dict["context_after"]:
            assert not line.startswith(" ")
            assert not line.endswith(" ")


class TestCodebaseSearchServer:
    """Test suite for CodebaseSearchServer class."""

    @pytest.fixture
    def temp_codebase(self, tmp_path: Path) -> Path:
        """Create a temporary codebase for testing."""
        # Create test files with different patterns
        (tmp_path / "core").mkdir()
        (tmp_path / "utils").mkdir()

        # Core file with money calculations
        core_file = tmp_path / "core" / "test.py"
        core_file.write_text("""
def calculate_position(account_balance, risk_percent):
    position_size = account_balance * risk_percent
    return position_size

def circuit_breaker_check():
    if circuit_breaker.is_tripped():
        return False
    return True
""")

        # Utils file with variable conflict
        utils_file = tmp_path / "utils" / "helpers.py"
        utils_file.write_text("""
import time

def process_transactions():
    for time in range(10):
        print(time)
""")

        return tmp_path

    @pytest.fixture
    def server(self) -> CodebaseSearchServer:
        """Create a server instance for testing."""
        return CodebaseSearchServer()

    def test_initialization(self, server: CodebaseSearchServer) -> None:
        """Test server initialization."""
        assert server.config is not None
        assert server.circuit_breaker is not None
        assert server.rate_limiter is not None
        assert server.cache is not None
        assert server.search_count == 0

    def test_list_patterns(self, server: CodebaseSearchServer) -> None:
        """Test listing available patterns."""
        patterns = server.list_patterns()

        assert isinstance(patterns, dict)
        assert "money_calculations" in patterns
        assert "risk_controls" in patterns

    def test_get_stats(self, server: CodebaseSearchServer) -> None:
        """Test getting server statistics."""
        stats = server.get_stats()

        assert isinstance(stats, dict)
        assert "search_count" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "cache_hit_ratio" in stats
        assert "circuit_breaker_state" in stats

    def test_clear_cache(self, server: CodebaseSearchServer) -> None:
        """Test clearing the cache."""
        server.cache.set("test_key", "test_value")
        assert server.cache.get("test_key") == "test_value"

        server.clear_cache()
        assert server.cache.get("test_key") is None

    @pytest.mark.asyncio
    async def test_search_pattern_invalid_pattern(
        self, server: CodebaseSearchServer
    ) -> None:
        """Test searching with invalid pattern name."""
        with pytest.raises(ValueError, match="Pattern not found"):
            await server.search_pattern("invalid_pattern")

    @pytest.mark.asyncio
    async def test_search_pattern_circuit_breaker_tripped(
        self, server: CodebaseSearchServer
    ) -> None:
        """Test search when circuit breaker is tripped."""
        # Trip the circuit breaker
        for _ in range(10):
            server.circuit_breaker.record_failure()

        assert server.circuit_breaker.is_tripped()

        # Search should be rejected
        with pytest.raises(RuntimeError, match="Circuit breaker is active"):
            await server.search_pattern("money_calculations")

    @pytest.mark.asyncio
    async def test_shutdown(self, server: CodebaseSearchServer) -> None:
        """Test server shutdown."""
        await server.shutdown()
        # Should not raise any exceptions


class TestIntegration:
    """Integration tests for codebase search functionality."""

    @pytest.mark.asyncio
    async def test_full_search_workflow(self) -> None:
        """Test complete search workflow."""
        server = CodebaseSearchServer()

        try:
            # List patterns
            patterns = server.list_patterns()
            assert len(patterns) > 0

            # Get stats
            stats = server.get_stats()
            assert stats["search_count"] == 0

            # Shutdown
            await server.shutdown()

        except Exception as e:
            pytest.fail(f"Integration test failed: {e}")

    @pytest.mark.asyncio
    async def test_singleton_server(self) -> None:
        """Test that singleton server works correctly."""
        server1 = get_search_server()
        server2 = get_search_server()

        # Should be the same instance
        assert server1 is server2


class TestEdgeCases:
    """Edge case tests for codebase search."""

    @pytest.fixture
    def server(self) -> CodebaseSearchServer:
        """Create a server instance for testing."""
        return CodebaseSearchServer()

    def test_empty_pattern_name(self, server: CodebaseSearchServer) -> None:
        """Test searching with empty pattern name."""
        assert server.config.get_pattern("") is None

    @pytest.mark.asyncio
    async def test_search_nonexistent_directory(
        self, server: CodebaseSearchServer
    ) -> None:
        """Test searching in non-existent directory."""
        # Should not crash, just return empty results
        # Note: This test requires actual search execution
        pass

    @pytest.mark.asyncio
    async def test_max_results_limit(self, server: CodebaseSearchServer) -> None:
        """Test that max_results is respected."""
        # Note: This test requires actual codebase with patterns
        pass


class TestPerformance:
    """Performance tests for codebase search."""

    @pytest.fixture
    def server(self) -> CodebaseSearchServer:
        """Create a server instance for testing."""
        return CodebaseSearchServer()

    @pytest.mark.asyncio
    async def test_cache_performance(self) -> None:
        """Test that caching improves performance."""
        server = CodebaseSearchServer()

        # This test requires actual codebase with patterns
        # For now, just test cache functionality
        server.cache.set("test_key", "test_value")

        # Cache hit
        assert server.cache.get("test_key") == "test_value"

        await server.shutdown()

    @pytest.mark.asyncio
    async def test_rate_limiter_performance(self) -> None:
        """Test that rate limiter doesn't slow down normal operations."""
        limiter = RateLimiter(max_requests_per_minute=100)

        # Should be able to acquire quickly under limit
        start = time.time()
        for _ in range(10):
            await limiter.acquire()
        duration = time.time() - start

        # Should complete in under 1 second
        assert duration < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
