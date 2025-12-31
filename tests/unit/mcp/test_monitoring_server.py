"""
Tests for MCP Monitoring Server

This module tests monitoring server that provides:
- Real-time system health status
- Performance metrics tracking
- Alert system monitoring
- Resource utilization monitoring
- Integration with existing monitoring infrastructure
"""

import pytest
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from mcp.monitoring_server import (
    MonitoringServer,
    SystemHealthCheck,
    PerformanceSnapshot,
    AlertStatus,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger fixture."""
    with patch("mcp.monitoring_server.logger") as mock_logger:
        logger_instance = MagicMock()
        yield logger_instance


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    # Cleanup
    import shutil

    try:
        shutil.rmtree(temp_dir)
    except OSError:
        pass


@pytest.fixture
def temp_circuit_breaker_state(temp_data_dir):
    """Create a temporary circuit breaker state file."""
    state_file = temp_data_dir / "circuit_breaker_state.json"
    state_data = {
        "active": False,
        "reason": "",
        "daily_loss": 0.0,
        "consecutive_losses": 0,
        "failed_trades": 0,
        "total_trades": 0,
        "last_reset_date": datetime.now(timezone.utc).isoformat(),
    }
    with open(state_file, "w") as f:
        json.dump(state_data, f)
    yield state_file
    # Cleanup
    try:
        if state_file.exists():
            state_file.unlink()
    except OSError:
        pass


class TestMonitoringServer:
    """Test suite for MonitoringServer."""

    def test_initialization(self, mock_logger):
        """Test that monitoring server initializes correctly."""
        server = MonitoringServer()

        assert server is not None
        assert hasattr(server, "health_history")
        assert hasattr(server, "performance_history")
        assert hasattr(server, "alert_history")
        assert hasattr(server, "resource_limits")
        assert hasattr(server, "_state_lock")
        assert server.max_history_size == 100
        assert server.max_performance_history == 50
        assert server.max_alert_history == 100

        # Check resource limits
        assert server.resource_limits["max_cpu_percent"] == 90.0
        assert server.resource_limits["max_memory_percent"] == 85.0
        assert server.resource_limits["max_disk_percent"] == 80.0
        assert server.resource_limits["max_response_time_ms"] == 5000.0
        assert server.resource_limits["min_cache_hit_ratio"] == 0.70
        assert server.resource_limits["max_error_rate"] == 0.10

    @pytest.mark.asyncio
    async def test_get_system_health(self, mock_logger):
        """Test getting system health status."""
        server = MonitoringServer()

        health = await server.get_system_health()

        assert health is not None
        assert "timestamp" in health
        assert "overall_status" in health
        assert "health_checks" in health
        assert "performance_metrics" in health
        assert "alert_status" in health
        assert "duration_ms" in health
        assert "resource_limits" in health

        # Verify status is one of valid values
        assert health["overall_status"] in ["healthy", "degraded", "critical"]

        # Verify health checks exist (at least some checks)
        assert len(health["health_checks"]) >= 3

    @pytest.mark.asyncio
    async def test_health_check_monitoring_system(self, mock_logger):
        """Test monitoring system health check."""
        server = MonitoringServer()

        health_check = await server._check_monitoring_system_health()

        assert health_check is not None
        assert health_check.name == "monitoring_system"
        assert health_check.status in ["healthy", "degraded"]
        assert "details" in health_check.to_dict()

    @pytest.mark.asyncio
    async def test_health_check_external_dependencies(self, mock_logger):
        """Test external dependencies health check."""
        server = MonitoringServer()

        with patch("config.settings.get_settings") as mock_settings:
            mock_settings_instance = MagicMock()
            mock_settings_instance.network.polygon_rpc_url = "https://polygon-rpc.com"
            mock_settings_instance.network.polygonscan_api_key = "test_api_key"
            mock_settings_instance.alerts.telegram_bot_token = "test_token"
            mock_settings.return_value = mock_settings_instance

            health_check = await server._check_external_dependencies()

            assert health_check is not None
            assert health_check.name == "external_dependencies"
            assert health_check.status in ["healthy", "degraded"]
            assert "details" in health_check.to_dict()

    @pytest.mark.asyncio
    async def test_health_check_circuit_breaker(
        self, mock_logger, temp_circuit_breaker_state
    ):
        """Test circuit breaker health check."""
        server = MonitoringServer()

        # Test with circuit breaker state file
        health_check = await server._check_circuit_breaker_health()

        assert health_check is not None
        assert health_check.name == "circuit_breaker"
        assert health_check.status in ["healthy", "degraded"]

        # Test without circuit breaker state file
        temp_circuit_breaker_state.unlink()
        health_check_no_file = await server._check_circuit_breaker_health()
        assert health_check_no_file is not None
        assert health_check_no_file.status == "healthy"

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, mock_logger):
        """Test performance metrics collection."""
        server = MonitoringServer()

        metrics = await server._collect_performance_metrics()

        assert metrics is not None
        assert isinstance(metrics, PerformanceSnapshot)
        assert metrics.timestamp is not None
        assert metrics.cpu_percent >= 0
        assert metrics.memory_mb >= 0
        assert metrics.memory_percent >= 0
        assert metrics.disk_percent >= 0
        assert metrics.response_time_ms >= 0
        assert metrics.throughput_tps >= 0
        assert 0.0 <= metrics.cache_hit_ratio <= 1.0
        assert 0.0 <= metrics.error_rate <= 1.0

    @pytest.mark.asyncio
    async def test_alert_system_status_check(self, mock_logger):
        """Test alert system status check."""
        server = MonitoringServer()

        alert_status = await server._check_alert_system_health()

        assert alert_status is not None
        assert isinstance(alert_status, AlertStatus)
        assert alert_status.timestamp is not None
        assert isinstance(alert_status.telegram_healthy, bool)
        assert isinstance(alert_status.email_healthy, bool)
        assert isinstance(alert_status.webhook_healthy, bool)
        assert 0.0 <= alert_status.success_rate <= 1.0
        assert alert_status.queue_size >= 0
        assert alert_status.recent_failures >= 0
        assert alert_status.last_alert_delay >= 0

    def test_determine_overall_status_healthy(self, mock_logger):
        """Test overall status determination for healthy system."""
        server = MonitoringServer()

        # Create healthy health checks
        health_checks = [
            SystemHealthCheck(
                name="check1",
                status="healthy",
                message="OK",
                timestamp=datetime.now(timezone.utc).isoformat(),
                duration_ms=10.0,
            ),
            SystemHealthCheck(
                name="check2",
                status="healthy",
                message="OK",
                timestamp=datetime.now(timezone.utc).isoformat(),
                duration_ms=10.0,
            ),
        ]

        # Create healthy alert status
        alert_status = AlertStatus(
            timestamp=datetime.now(timezone.utc).isoformat(),
            telegram_healthy=True,
            email_healthy=False,
            webhook_healthy=False,
            success_rate=0.95,
            queue_size=0,
            recent_failures=0,
            last_alert_delay=0.5,
        )

        overall_status = server._determine_overall_status(health_checks, alert_status)

        assert overall_status == "healthy"

    def test_determine_overall_status_degraded(self, mock_logger):
        """Test overall status determination for degraded system."""
        server = MonitoringServer()

        # Create mixed health checks
        health_checks = [
            SystemHealthCheck(
                name="check1",
                status="healthy",
                message="OK",
                timestamp=datetime.now(timezone.utc).isoformat(),
                duration_ms=10.0,
            ),
            SystemHealthCheck(
                name="check2",
                status="degraded",
                message="Warning",
                timestamp=datetime.now(timezone.utc).isoformat(),
                duration_ms=10.0,
            ),
        ]

        # Create healthy alert status
        alert_status = AlertStatus(
            timestamp=datetime.now(timezone.utc).isoformat(),
            telegram_healthy=True,
            email_healthy=False,
            webhook_healthy=False,
            success_rate=0.95,
            queue_size=0,
            recent_failures=0,
            last_alert_delay=0.5,
        )

        overall_status = server._determine_overall_status(health_checks, alert_status)

        assert overall_status == "degraded"

    def test_determine_overall_status_critical(self, mock_logger):
        """Test overall status determination for critical system."""
        server = MonitoringServer()

        # Create critical health checks
        health_checks = [
            SystemHealthCheck(
                name="check1",
                status="critical",
                message="Error",
                timestamp=datetime.now(timezone.utc).isoformat(),
                duration_ms=10.0,
            ),
        ]

        # Create degraded alert status
        alert_status = AlertStatus(
            timestamp=datetime.now(timezone.utc).isoformat(),
            telegram_healthy=False,
            email_healthy=False,
            webhook_healthy=False,
            success_rate=0.80,
            queue_size=5,
            recent_failures=10,
            last_alert_delay=5.0,
        )

        overall_status = server._determine_overall_status(health_checks, alert_status)

        assert overall_status == "critical"

    @pytest.mark.asyncio
    async def test_health_history_management(self, mock_logger):
        """Test health check history management."""
        server = MonitoringServer()

        # Create multiple health checks
        for i in range(150):
            health_check = SystemHealthCheck(
                name=f"check_{i}",
                status="healthy",
                message="OK",
                timestamp=datetime.now(timezone.utc).isoformat(),
                duration_ms=10.0,
            )
            await server._update_health_history([health_check])

        # Verify history size limit
        assert len(server.health_history) <= server.max_history_size
        assert len(server.health_history) == server.max_history_size

        # Verify order (most recent last)
        assert server.health_history[-1].name == "check_149"

    @pytest.mark.asyncio
    async def test_performance_history_management(self, mock_logger):
        """Test performance metrics history management."""
        server = MonitoringServer()

        # Create multiple performance snapshots
        for i in range(75):
            metrics = PerformanceSnapshot(
                timestamp=datetime.now(timezone.utc).isoformat(),
                cpu_percent=10.0 + i,
                memory_mb=100.0 + i,
                memory_percent=20.0 + i * 0.1,
                disk_percent=40.0,
                response_time_ms=50.0,
                throughput_tps=5.0,
                cache_hit_ratio=0.85,
                error_rate=0.05,
            )
            await server._update_performance_history(metrics)

        # Verify history size limit
        assert len(server.performance_history) <= server.max_performance_history
        assert len(server.performance_history) == server.max_performance_history

    @pytest.mark.asyncio
    async def test_alert_history_management(self, mock_logger):
        """Test alert status history management."""
        server = MonitoringServer()

        # Create multiple alert statuses
        for i in range(150):
            alert_status = AlertStatus(
                timestamp=datetime.now(timezone.utc).isoformat(),
                telegram_healthy=True,
                email_healthy=False,
                webhook_healthy=False,
                success_rate=0.95 - i * 0.001,
                queue_size=i,
                recent_failures=i % 5,
                last_alert_delay=0.5 + i * 0.01,
            )
            await server._update_alert_history(alert_status)

        # Verify history size limit
        assert len(server.alert_history) <= server.max_alert_history
        assert len(server.alert_history) == server.max_alert_history

    def test_get_stats(self, mock_logger):
        """Test getting monitoring server statistics."""
        server = MonitoringServer()

        # Perform some operations to update stats
        server.total_health_checks = 5
        server.total_performance_snapshots = 3
        server.total_alerts = 2

        stats = server.get_stats()

        assert stats is not None
        assert "total_health_checks" in stats
        assert "total_performance_snapshots" in stats
        assert "total_alerts" in stats
        assert "health_history_size" in stats
        assert "performance_history_size" in stats
        assert "alert_history_size" in stats
        assert "resource_limits" in stats

        assert stats["total_health_checks"] == 5
        assert stats["total_performance_snapshots"] == 3
        assert stats["total_alerts"] == 2

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_logger):
        """Test monitoring server shutdown."""
        server = MonitoringServer()

        # Perform some operations
        await server.get_system_health()

        # Shutdown should complete without errors
        await server.shutdown()

    @pytest.mark.asyncio
    async def test_get_system_health_performance(self, mock_logger):
        """Test that get_system_health completes in reasonable time."""
        server = MonitoringServer()

        import time

        start_time = time.time()

        await server.get_system_health()

        duration_ms = (time.time() - start_time) * 1000

        # Should complete within 5 seconds
        assert duration_ms < 5000.0

    def test_singleton_pattern(self, mock_logger):
        """Test that get_monitoring_server returns singleton instance."""
        from mcp.monitoring_server import get_monitoring_server, _monitoring_server

        # Clear singleton for test
        global _monitoring_server
        _monitoring_server = None

        # Get first instance
        instance1 = get_monitoring_server()

        # Get second instance
        instance2 = get_monitoring_server()

        # Should be same instance
        assert instance1 is instance2

    @pytest.mark.asyncio
    async def test_resource_limit_validation(self, mock_logger):
        """Test resource limit validation in monitoring."""
        server = MonitoringServer()

        # Verify all resource limits are set
        assert server.resource_limits["max_cpu_percent"] > 0
        assert server.resource_limits["max_memory_percent"] > 0
        assert server.resource_limits["max_disk_percent"] > 0
        assert server.resource_limits["max_response_time_ms"] > 0
        assert 0.0 < server.resource_limits["min_cache_hit_ratio"] <= 1.0
        assert 0.0 < server.resource_limits["max_error_rate"] <= 1.0

        # Get health and verify limits are included
        health = await server.get_system_health()
        assert "resource_limits" in health
        assert health["resource_limits"] == server.resource_limits

    def test_dataclass_serialization(self, mock_logger):
        """Test dataclass serialization methods."""
        # Test SystemHealthCheck
        health_check = SystemHealthCheck(
            name="test_check",
            status="healthy",
            message="Test message",
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=10.0,
            details={"key": "value"},
        )

        health_dict = health_check.to_dict()
        assert health_dict["name"] == "test_check"
        assert health_dict["status"] == "healthy"
        assert health_dict["message"] == "Test message"
        assert health_dict["duration_ms"] == 10.0
        assert health_dict["details"] == {"key": "value"}

        # Test PerformanceSnapshot
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cpu_percent=15.2,
            memory_mb=256.0,
            memory_percent=25.0,
            disk_percent=45.2,
            response_time_ms=45.0,
            throughput_tps=5.2,
            cache_hit_ratio=0.85,
            error_rate=0.05,
        )

        snapshot_dict = snapshot.to_dict()
        assert snapshot_dict["cpu_percent"] == 15.2
        assert snapshot_dict["memory_mb"] == 256.0
        assert snapshot_dict["memory_percent"] == 25.0
        assert snapshot_dict["cache_hit_ratio"] == 0.85
        assert snapshot_dict["error_rate"] == 0.05

        # Test AlertStatus
        alert_status = AlertStatus(
            timestamp=datetime.now(timezone.utc).isoformat(),
            telegram_healthy=True,
            email_healthy=False,
            webhook_healthy=False,
            success_rate=0.95,
            queue_size=0,
            recent_failures=0,
            last_alert_delay=0.5,
        )

        alert_dict = alert_status.to_dict()
        assert alert_dict["telegram_healthy"] is True
        assert alert_dict["email_healthy"] is False
        assert alert_dict["success_rate"] == 0.95
        assert alert_dict["queue_size"] == 0
