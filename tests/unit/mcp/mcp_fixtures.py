"""
Shared MCP Test Fixtures

This module provides reusable fixtures for MCP server testing,
focusing on improved async mocking and simplified test setup.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone


# =============================================================================
# Mock Configurations
# =============================================================================


@pytest.fixture
def mock_mcp_config():
    """Create mock MCP configurations."""
    config = MagicMock()
    config.enabled = True
    config.cache_enabled = True
    config.cache_ttl_seconds = 3600
    config.memory_limit_mb = 100.0
    config.rate_limit_requests_per_minute = 10
    config.max_results = 100
    config.timeout_seconds = 30
    config.monitor_interval_seconds = 60

    return config


@pytest.fixture
def mock_monitoring_config():
    """Create mock monitoring configuration."""
    config = MagicMock()
    config.enabled = True
    config.check_interval_seconds = 60
    config.max_cpu_percent = 90.0
    config.max_memory_mb = 100.0
    config.alert_enabled = False
    config.metrics_enabled = False
    config.dashboard_enabled = False
    config.duplicate_alerts = False
    config.circuit_breaker_enabled = True
    config.circuit_breaker_cpu_threshold = 85.0
    config.circuit_breaker_memory_threshold = 80.0
    config.recovery_enabled = True
    config.recovery_interval_seconds = 300
    config.max_recovery_attempts = 3
    config.check_main_bot = False
    config.check_wallet_monitor = False
    config.check_trade_executor = False
    config.check_alert_system = False

    return config


# =============================================================================
# Mock Servers
# =============================================================================


@pytest.fixture
def mock_codebase_search_server():
    """Create mock codebase search server."""
    server = AsyncMock()
    server.config = mock_mcp_config()
    server.circuit_breaker = MagicMock()
    server.rate_limiter = MagicMock()
    server.cache = MagicMock()
    server.search_count = 0
    server.cache_hits = 0
    server.cache_misses = 0

    # Mock methods
    async def mock_search_pattern(*args, **kwargs):
        return []

    async def mock_search_custom_pattern(*args, **kwargs):
        return []

    def mock_list_patterns():
        return {}

    def mock_get_stats():
        return {}

    def mock_clear_cache():
        pass

    async def mock_shutdown():
        pass

    server.search_pattern = mock_search_pattern
    server.search_custom_pattern = mock_search_custom_pattern
    server.list_patterns = mock_list_patterns
    server.get_stats = mock_get_stats
    server.clear_cache = mock_clear_cache
    server.shutdown = mock_shutdown

    return server


@pytest.fixture
def mock_testing_server():
    """Create mock testing server."""
    server = AsyncMock()
    server.config = mock_testing_config()
    server.circuit_breaker = MagicMock()
    server.test_cache = MagicMock()
    server.coverage_cache = MagicMock()
    server.total_tests_run = 0
    server.total_failures = 0
    server.last_coverage_drop = None

    # Mock methods
    async def mock_run_critical_tests(*args, **kwargs):
        return {}

    async def mock_get_stats():
        return {}

    async def mock_get_test_dashboard_data(*args, **kwargs):
        return {}

    async def mock_generate_tests_for_strategy(*args, **kwargs):
        return "test_file.py"

    async def mock_shutdown():
        pass

    server.run_critical_tests = mock_run_critical_tests
    server.get_stats = mock_get_stats
    server.get_test_dashboard_data = mock_get_test_dashboard_data
    server.generate_tests_for_strategy = mock_generate_tests_for_strategy
    server.shutdown = mock_shutdown

    return server


@pytest.fixture
def mock_monitoring_server():
    """Create mock monitoring server."""
    server = AsyncMock()
    server.config = mock_monitoring_config()
    server.health_history = []
    server.performance_history = []
    server.alert_history = []
    server._state_lock = asyncio.Lock()
    server.total_health_checks = 0
    server.total_performance_snapshots = 0
    server.total_alerts = 0
    server.max_history_size = 100
    server.max_performance_history = 50
    server.max_alert_history = 100

    # Mock methods
    async def mock_get_system_health(*args, **kwargs):
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "healthy",
            "health_checks": [],
            "performance_metrics": {},
            "alert_status": {},
            "duration_ms": 10.0,
            "resource_limits": {},
        }

    def mock_get_stats():
        return {}

    async def mock_shutdown():
        pass

    server.get_system_health = mock_get_system_health
    server.get_stats = mock_get_stats
    server.shutdown = mock_shutdown

    return server


# =============================================================================
# Mock System Resources
# =============================================================================


@pytest.fixture
def mock_psutil_process():
    """Create mock psutil process."""
    process = MagicMock()
    process.cpu_percent = MagicMock(return_value=15.0)
    process.memory_info = MagicMock(
        return_value=MagicMock(
            rss=262144000,  # 250MB in bytes
            percent=25.0,
            vms=130107200,
            shared=0,
            text=256000,
            lib=0,
            data=0,
        )
    )
    process.memory_percent = MagicMock(return_value=25.0)

    return process


@pytest.fixture
def mock_psutil():
    """Create mock psutil module."""
    psutil = MagicMock()
    psutil.Process = mock_psutil_process
    psutil.cpu_percent = MagicMock(return_value=15.0)

    # Mock virtual memory
    mock_vm = MagicMock()
    mock_vm.percent = MagicMock(return_value=75.0)
    psutil.virtual_memory = MagicMock(return_value=mock_vm)

    return psutil


# =============================================================================
# Test Data Generators
# =============================================================================


@pytest.fixture
def sample_health_check_data():
    """Generate sample health check data."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": "healthy",
        "health_checks": [
            {
                "name": "main_bot",
                "status": "healthy",
                "message": "Main bot is running",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 10.0,
            },
            {
                "name": "wallet_monitor",
                "status": "healthy",
                "message": "Wallet monitor is healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 15.0,
            },
        ],
        "performance_metrics": {
            "cpu_percent": 15.0,
            "memory_mb": 256.0,
            "memory_percent": 25.0,
            "uptime_seconds": 3600.0,
        },
        "alert_status": {
            "telegram_healthy": True,
            "email_healthy": False,
            "webhook_healthy": False,
            "success_rate": 0.95,
            "queue_size": 0,
            "recent_failures": 0,
        },
    }


@pytest.fixture
def sample_performance_metrics():
    """Generate sample performance metrics."""
    return {
        "cpu_percent": 15.0,
        "memory_mb": 256.0,
        "memory_percent": 25.0,
        "uptime_seconds": 3600.0,
    }


@pytest.fixture
def sample_alert_status():
    """Generate sample alert status."""
    return {
        "telegram_healthy": True,
        "email_healthy": False,
        "webhook_healthy": False,
        "success_rate": 0.95,
        "queue_size": 0,
        "recent_failures": 0,
    }
