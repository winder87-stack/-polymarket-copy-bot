"""
Tests for MCP Testing Server

This module tests testing server that:
|- Executes test suites
|- Generates coverage reports
|- Validates code quality
|- Prevents regression bugs
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from mcp.testing_server import (
    TestingServer,
    TestingCircuitBreaker,
    TestGenerator,
    TestResult,
    TestSuiteResult,
    TestExecutionConfig,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger fixture."""
    with patch("mcp.testing_server.logger") as mock_logger:
        logger_instance = MagicMock()
        yield logger_instance


@pytest.fixture
def temp_project_root():
    """Create a temporary project root for testing."""
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir)
    yield temp_path
    # Cleanup
    import shutil

    try:
        shutil.rmtree(temp_dir)
    except OSError:
        pass


class TestTestingCircuitBreaker:
    """Test suite for TestingCircuitBreaker."""

    def test_initialization(self, mock_logger):
        """Test that circuit breaker initializes correctly."""
        breaker = TestingCircuitBreaker(failure_threshold=5, cooldown_seconds=300)

        assert breaker is not None
        assert breaker.state == "closed"
        assert breaker.failure_count == 0
        assert breaker.failure_threshold == 5
        assert breaker.cooldown_seconds == 300

    def test_is_open_closed(self, mock_logger):
        """Test circuit breaker is not open when closed."""
        breaker = TestingCircuitBreaker()

        assert breaker.is_open() is False

    def test_is_open_after_failures(self, mock_logger):
        """Test circuit breaker opens after threshold failures."""
        breaker = TestingCircuitBreaker(failure_threshold=3)

        # Record 3 failures
        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == "open"
        assert breaker.is_open() is True

    def test_is_open_cooldown_expired(self, mock_logger):
        """Test circuit breaker closes after cooldown expires."""
        import time

        breaker = TestingCircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)

        # Record failures to open
        for _ in range(2):
            breaker.record_failure()

        assert breaker.is_open() is True

        # Wait for cooldown to expire
        time.sleep(0.2)

        # Should be closed now
        assert breaker.is_open() is False

    def test_record_success(self, mock_logger):
        """Test recording success closes circuit breaker."""
        breaker = TestingCircuitBreaker(failure_threshold=2)

        # Open the circuit breaker
        for _ in range(2):
            breaker.record_failure()
        assert breaker.state == "open"

        # Record success
        breaker.record_success()

        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    def test_concurrent_access(self, mock_logger):
        """Test thread-safe concurrent access."""
        import threading

        breaker = TestingCircuitBreaker(failure_threshold=10)

        def record_failure():
            for _ in range(5):
                breaker.record_failure()

        # Create multiple threads
        threads = [threading.Thread(target=record_failure) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have recorded 15 failures
        assert breaker.state == "open"


class TestTestGenerator:
    """Test suite for TestGenerator."""

    def test_initialization(self, mock_logger, temp_project_root):
        """Test that test generator initializes correctly."""
        generator = TestGenerator(temp_project_root)

        assert generator is not None
        assert generator.project_root == temp_project_root

    @pytest.mark.asyncio
    async def test_generate_endgame_sweeper_tests(self, mock_logger, temp_project_root):
        """Test generating endgame sweeper tests."""
        generator = TestGenerator(temp_project_root)

        test_content = await generator.generate_endgame_sweeper_tests()

        assert test_content is not None
        assert isinstance(test_content, str)
        assert len(test_content) > 0
        assert "TestEndgameRiskParameters" in test_content
        assert "test_min_probability_threshold" in test_content
        assert "test_max_probability_exit_threshold" in test_content
        assert "test_position_size_limit" in test_content

    @pytest.mark.asyncio
    async def test_generate_quality_whale_tests(self, mock_logger, temp_project_root):
        """Test generating quality whale tests."""
        generator = TestGenerator(temp_project_root)

        test_content = await generator.generate_quality_whale_tests()

        assert test_content is not None
        assert isinstance(test_content, str)
        assert len(test_content) > 0
        assert "TestQualityWhaleFiltering" in test_content
        assert "test_minimum_confidence_score" in test_content
        assert "test_maximum_risk_score" in test_content
        assert "test_minimum_trade_volume" in test_content

    @pytest.mark.asyncio
    async def test_generate_cross_market_arbitrage_tests(
        self, mock_logger, temp_project_root
    ):
        """Test generating cross-market arbitrage tests."""
        generator = TestGenerator(temp_project_root)

        test_content = await generator.generate_cross_market_arbitrage_tests()

        assert test_content is not None
        assert isinstance(test_content, str)
        assert len(test_content) > 0
        assert "TestCrossMarketArbitrage" in test_content
        assert "test_high_correlation_threshold" in test_content
        assert "test_min_spread_percentage" in test_content


class TestTestResult:
    """Test suite for TestResult dataclass."""

    def test_to_dict(self, mock_logger):
        """Test TestResult serialization."""
        result = TestResult(
            test_name="test_example",
            module="test_module",
            status="passed",
            duration_seconds=1.5,
            error_message=None,
            traceback=None,
            coverage=0.95,
        )

        result_dict = result.to_dict()

        assert result_dict is not None
        assert result_dict["test_name"] == "test_example"
        assert result_dict["module"] == "test_module"
        assert result_dict["status"] == "passed"
        assert result_dict["duration_seconds"] == 1.5
        assert result_dict["error_message"] is None
        assert result_dict["traceback"] is None
        assert result_dict["coverage"] == 0.95


class TestTestSuiteResult:
    """Test suite for TestSuiteResult dataclass."""

    def test_to_dict(self, mock_logger):
        """Test TestSuiteResult serialization."""
        result = TestSuiteResult(
            module_name="test_module",
            total_tests=10,
            passed=8,
            failed=1,
            skipped=1,
            errors=0,
            duration_seconds=5.0,
            coverage=0.85,
            test_results=[
                TestResult(
                    test_name="test_1",
                    module="test_module",
                    status="passed",
                    duration_seconds=0.5,
                )
            ],
        )

        result_dict = result.to_dict()

        assert result_dict is not None
        assert result_dict["module_name"] == "test_module"
        assert result_dict["total_tests"] == 10
        assert result_dict["passed"] == 8
        assert result_dict["failed"] == 1
        assert result_dict["skipped"] == 1
        assert result_dict["errors"] == 0
        assert result_dict["duration_seconds"] == 5.0
        assert result_dict["coverage"] == 0.85
        assert "test_results" in result_dict
        assert len(result_dict["test_results"]) == 1

    def test_success_rate(self, mock_logger):
        """Test success rate calculation."""
        result = TestSuiteResult(
            module_name="test_module",
            total_tests=10,
            passed=8,
            failed=1,
            skipped=1,
            errors=0,
            duration_seconds=5.0,
            coverage=0.85,
        )

        success_rate = result.success_rate()

        assert success_rate == 80.0

    def test_success_rate_zero_tests(self, mock_logger):
        """Test success rate with zero tests."""
        result = TestSuiteResult(
            module_name="test_module",
            total_tests=0,
            passed=0,
            failed=0,
            skipped=0,
            errors=0,
            duration_seconds=0.0,
            coverage=0.0,
        )

        success_rate = result.success_rate()

        assert success_rate == 0.0


class TestTestingServer:
    """Test suite for TestingServer."""

    def test_initialization(self, mock_logger):
        """Test that testing server initializes correctly."""
        config = TestExecutionConfig()

        server = TestingServer(config)

        assert server is not None
        assert hasattr(server, "config")
        assert hasattr(server, "circuit_breaker")
        assert hasattr(server, "test_cache")
        assert hasattr(server, "coverage_cache")
        assert hasattr(server, "total_tests_run")
        assert hasattr(server, "total_failures")
        assert hasattr(server, "last_coverage_drop")

        # Verify config
        assert server.config.max_test_duration_seconds == 300
        assert server.config.max_memory_gb == 2.0
        assert server.config.coverage_target == 0.85

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_logger):
        """Test getting testing server statistics."""
        config = TestExecutionConfig()
        server = TestingServer(config)

        # Update some statistics
        server.total_tests_run = 50
        server.total_failures = 3

        stats = server.get_stats()

        assert stats is not None
        assert "total_tests_run" in stats
        assert "total_failures" in stats
        assert "success_rate" in stats
        assert "circuit_breaker_state" in stats
        assert "circuit_breaker_failures" in stats
        assert "cache_size" in stats
        assert "cache_hit_ratio" in stats
        assert "last_coverage_drop" in stats

        assert stats["total_tests_run"] == 50
        assert stats["total_failures"] == 3
        # Success rate = (50 - 3) / 50 = 0.94 = 94%
        assert stats["success_rate"] == 94.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_check(self, mock_logger):
        """Test circuit breaker check before test execution."""
        config = TestExecutionConfig()
        server = TestingServer(config)

        # Open the circuit breaker
        for _ in range(5):
            server.circuit_breaker.record_failure()

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Testing circuit breaker is active"):
            await server.run_critical_tests()

    @pytest.mark.asyncio
    async def test_get_test_dashboard_data(self, mock_logger):
        """Test getting test dashboard data."""
        config = TestExecutionConfig()
        server = TestingServer(config)

        # Update some statistics
        server.total_tests_run = 100
        server.total_failures = 10

        dashboard = await server.get_test_dashboard_data()

        assert dashboard is not None
        assert "total_tests_run" in dashboard
        assert "total_failures" in dashboard
        assert "success_rate" in dashboard
        assert "circuit_breaker_state" in dashboard
        assert "circuit_breaker_failures" in dashboard
        assert "last_coverage_drop" in dashboard
        assert "cache_stats" in dashboard
        assert "coverage_cache_stats" in dashboard

        assert dashboard["total_tests_run"] == 100
        assert dashboard["total_failures"] == 10
        # Success rate = (100 - 10) / 100 = 0.90 = 90%
        assert dashboard["success_rate"] == 90.0

    @pytest.mark.asyncio
    async def test_generate_tests_for_strategy(self, mock_logger, temp_project_root):
        """Test generating tests for new strategies."""
        config = TestExecutionConfig()
        server = TestingServer(config)
        server.project_root = temp_project_root

        # Create tests directory
        test_dir = temp_project_root / "tests" / "generated"
        test_dir.mkdir(parents=True, exist_ok=True)

        # Generate tests for endgame_sweeper
        test_file = await server.generate_tests_for_strategy("endgame_sweeper")

        assert test_file is not None
        assert isinstance(test_file, str)
        assert "test_endgame_sweeper.py" in test_file

        # Verify file was created
        assert Path(test_file).exists()

        # Verify file content
        with open(test_file, "r") as f:
            content = f.read()
            assert "TestEndgameRiskParameters" in content

    @pytest.mark.asyncio
    async def test_generate_tests_invalid_strategy(
        self, mock_logger, temp_project_root
    ):
        """Test generating tests for invalid strategy."""
        config = TestExecutionConfig()
        server = TestingServer(config)
        server.project_root = temp_project_root

        # Try to generate tests for invalid strategy
        with pytest.raises(ValueError, match="Unknown strategy"):
            await server.generate_tests_for_strategy("invalid_strategy")

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_logger):
        """Test testing server shutdown."""
        config = TestExecutionConfig()
        server = TestingServer(config)

        # Perform some operations
        stats = server.get_stats()
        assert stats is not None

        # Shutdown should complete without errors
        await server.shutdown()

        # Shutdown completes without errors, no assertion needed on logger

    def test_singleton_pattern(self, mock_logger):
        """Test that get_testing_server returns singleton instance."""
        from mcp.testing_server import get_testing_server, _testing_server

        # Clear singleton for test
        global _testing_server
        _testing_server = None

        # Get first instance
        instance1 = get_testing_server()

        # Get second instance
        instance2 = get_testing_server()

        # Should be same instance
        assert instance1 is instance2

    @pytest.mark.asyncio
    async def test_parse_test_output(self, mock_logger, temp_project_root):
        """Test parsing pytest output."""
        config = TestExecutionConfig()
        server = TestingServer(config)
        server.project_root = temp_project_root

        # Create a mock coverage.json
        coverage_file = temp_project_root / "coverage.json"
        coverage_data = {"totals": {"percent_covered": 85.5}}
        with open(coverage_file, "w") as f:
            json.dump(coverage_data, f)

        # Mock pytest output
        stdout = (
            "test_module.py::test_example PASSED\n"
            "test_module.py::test_another PASSED\n"
            "test_module.py::test_failed FAILED\n"
            "test_module.py::test_skipped SKIPPED\n\n"
            "3 passed, 1 failed, 1 skipped in 2.34s"
        )

        stderr = ""

        result = server._parse_test_output(stdout, stderr, 2.34, "test_module")

        assert result is not None
        assert result.module_name == "test_module"
        assert result.total_tests == 5
        assert result.passed == 3
        assert result.failed == 1
        assert result.skipped == 1
        assert result.errors == 0
        assert result.duration_seconds == 2.34
        assert result.coverage == 0.855  # 85.5%


class TestTestExecutionConfig:
    """Test suite for TestExecutionConfig dataclass."""

    def test_default_values(self, mock_logger):
        """Test default configuration values."""
        config = TestExecutionConfig()

        assert config.max_test_duration_seconds == 300
        assert config.max_memory_gb == 2.0
        assert config.max_cpu_cores == 4
        assert config.coverage_target == 0.85
        assert config.mock_external_apis is True
        assert config.use_test_data is True
        assert config.parallel_execution is True
        assert config.alert_on_failure is True

    def test_custom_values(self, mock_logger):
        """Test custom configuration values."""
        config = TestExecutionConfig(
            max_test_duration_seconds=600,
            max_memory_gb=4.0,
            max_cpu_cores=8,
            coverage_target=0.90,
        )

        assert config.max_test_duration_seconds == 600
        assert config.max_memory_gb == 4.0
        assert config.max_cpu_cores == 8
        assert config.coverage_target == 0.90
