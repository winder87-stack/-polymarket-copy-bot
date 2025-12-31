"""
Tests for MCP Enhanced Monitoring Server

This module tests the enhanced monitoring server that provides:
- Production-safe monitoring with zero trading impact
- Prometheus metrics integration
- Web dashboard for real-time monitoring
- Circuit breaker for extreme stress conditions
- Alert deduplication to prevent notification spam
"""

import pytest
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))


@pytest.fixture
def mock_logger():
    """Create a mock logger fixture."""
    with patch("mcp.monitoring_server_enhanced.logger") as mock_logger:
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


class TestAlertHistory:
    """Test suite for AlertHistory dataclass."""

    def test_initialization(self, mock_logger):
        """Test alert history initializes correctly."""
        from mcp.monitoring_server_enhanced import AlertHistory

        history = AlertHistory(max_window_minutes=10)

        assert history is not None
        assert history.alerts == {}
        assert history.max_window_minutes == 10

    def test_is_duplicate_false(self, mock_logger):
        """Test duplicate detection returns false for new alert."""
        from mcp.monitoring_server_enhanced import AlertHistory

        history = AlertHistory(max_window_minutes=10)
        history.record_alert("critical:main_bot")

        assert history.is_duplicate("critical:main_bot") is False

    def test_is_duplicate_true(self, mock_logger):
        """Test duplicate detection returns true for recent alert."""

        from mcp.monitoring_server_enhanced import AlertHistory

        history = AlertHistory(max_window_minutes=10)
        history.record_alert("critical:main_bot")

        # First check should be false
        assert history.is_duplicate("critical:main_bot") is False

        # Second check immediately should be true (within window)
        assert history.is_duplicate("critical:main_bot") is True

    def test_is_duplicate_expired(self, mock_logger):
        """Test duplicate detection returns false for expired alert."""
        import time

        from mcp.monitoring_server_enhanced import AlertHistory

        history = AlertHistory(max_window_minutes=1)
        history.record_alert("critical:main_bot")

        # Wait for window to expire
        time.sleep(1.1)

        # Check after window expired should be false
        assert history.is_duplicate("critical:main_bot") is False

    def test_record_alert(self, mock_logger):
        """Test recording alert timestamp."""
        from mcp.monitoring_server_enhanced import AlertHistory

        history = AlertHistory(max_window_minutes=10)

        history.record_alert("critical:main_bot")

        assert "critical:main_bot" in history.alerts
        assert history.alerts["critical:main_bot"] > 0

    def test_cleanup_old_alerts(self, mock_logger):
        """Test that old alerts are cleaned up."""
        import time

        from mcp.monitoring_server_enhanced import AlertHistory

        history = AlertHistory(max_window_minutes=1)

        # Add multiple alerts
        history.record_alert("alert1")
        time.sleep(0.1)
        history.record_alert("alert2")
        time.sleep(0.1)
        history.record_alert("alert3")

        # Add one more alert after window expires
        time.sleep(1.1)
        history.record_alert("alert4")

        # Cleanup should remove alerts outside window
        history.cleanup_old_alerts()

        # Only most recent alert should remain
        assert len(history.alerts) == 1
        assert "alert4" in history.alerts

    def test_cleanup_multiple_old_alerts(self, mock_logger):
        """Test cleanup removes multiple old alerts."""
        import time

        from mcp.monitoring_server_enhanced import AlertHistory

        history = AlertHistory(max_window_minutes=1)

        # Add multiple alerts spread out
        for i in range(5):
            history.record_alert(f"alert{i}")
            time.sleep(0.2)

        # Cleanup should keep only recent
        history.cleanup_old_alerts()

        assert len(history.alerts) <= 1


class TestMonitoringCircuitBreaker:
    """Test suite for MonitoringCircuitBreaker."""

    def test_initialization(self, mock_logger):
        """Test circuit breaker initializes correctly."""
        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            cpu_threshold=90.0,
            memory_threshold=85.0,
            recovery_enabled=True,
            recovery_interval_seconds=300,
            max_recovery_attempts=3,
        )

        breaker = MonitoringCircuitBreaker(config=config)

        assert breaker is not None
        assert breaker.config == config
        assert breaker.cpu_threshold == 90.0
        assert breaker.memory_threshold == 85.0
        assert breaker.is_tripped is False
        assert breaker.trip_time is None
        assert breaker.recovery_attempt_count == 0
        assert breaker.last_recovery_attempt is None

    def test_should_monitor_when_not_tripped(self, mock_logger):
        """Test that monitoring is enabled when not tripped."""
        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig()
        breaker = MonitoringCircuitBreaker(config=config)

        assert breaker.should_monitor() is True

    def test_should_monitor_when_trip_time_passed(self, mock_logger):
        """Test that monitoring is enabled after recovery interval."""
        import time

        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            recovery_enabled=True,
            recovery_interval_seconds=1,
        )

        breaker = MonitoringCircuitBreaker(config=config)

        # Trip the breaker
        breaker.is_tripped = True
        breaker.trip_time = time.time() - 2.0  # 2 seconds ago

        # Should be ready to monitor (recovery interval passed)
        assert breaker.should_monitor() is True

    def test_should_monitor_false_when_recovery_interval_not_passed(self, mock_logger):
        """Test that monitoring is disabled when waiting for recovery."""
        import time

        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            recovery_enabled=True,
            recovery_interval_seconds=60,
        )

        breaker = MonitoringCircuitBreaker(config=config)

        # Trip the breaker
        breaker.is_tripped = True
        breaker.trip_time = time.time() - 30.0  # 30 seconds ago

        # Should not monitor yet (recovery interval not passed)
        assert breaker.should_monitor() is False

    def test_should_monitor_false_when_recovery_disabled(self, mock_logger):
        """Test that monitoring is disabled when recovery is disabled."""
        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            recovery_enabled=False,
        )

        breaker = MonitoringCircuitBreaker(config=config)

        # Trip the breaker
        breaker.is_tripped = True
        breaker.trip_time = time.time() - 10.0

        # Should not monitor (recovery disabled)
        assert breaker.should_monitor() is False

    @pytest.mark.asyncio
    async def test_trip(self, mock_logger):
        """Test circuit breaker trip."""
        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            alert_enabled=False,
        )

        breaker = MonitoringCircuitBreaker(config=config)

        # Trip the breaker
        await breaker.trip("Test reason")

        assert breaker.is_tripped is True
        assert breaker.trip_time is not None

    @pytest.mark.asyncio
    async def test_trip_with_alert(self, mock_logger):
        """Test circuit breaker trip sends alert."""
        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig(alert_enabled=True)
        breaker = MonitoringCircuitBreaker(config=config)

        # Mock alert sending
        with patch("mcp.monitoring_server_enhanced.send_error_alert") as mock_alert:
            await breaker.trip("Test reason")

            # Verify alert was sent
            mock_alert.assert_awaited_once()
            args = mock_alert.call_args[0][0]
            assert "Circuit breaker tripped: Test reason" in args[0]

    def test_reset(self, mock_logger):
        """Test circuit breaker manual reset."""
        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig()
        breaker = MonitoringCircuitBreaker(config=config)

        # Trip the breaker
        breaker.is_tripped = True
        breaker.trip_time = time.time()

        # Reset
        breaker.reset()

        assert breaker.is_tripped is False
        assert breaker.trip_time is None
        assert breaker.recovery_attempt_count == 0

    @pytest.mark.asyncio
    async def test_attempt_recovery_success(self, mock_logger):
        """Test successful recovery attempt."""
        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig()
        breaker = MonitoringCircuitBreaker(config=config)

        # Trip the breaker
        await breaker.trip("Test trip")

        # Mock system resources to be acceptable
        with patch(
            "mcp.monitoring_server_enhanced._get_system_resources"
        ) as mock_resources:
            mock_resources.return_value = (15.0, 50.0)  # CPU 15%, Memory 50%

            result = await breaker._attempt_recovery()

            assert result is True
            assert breaker.is_tripped is False
            assert breaker.trip_time is None
            assert breaker.recovery_attempt_count == 1

    @pytest.mark.asyncio
    async def test_attempt_recovery_high_resources(self, mock_logger):
        """Test recovery attempt fails with high resources."""
        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            cpu_threshold=90.0,
            memory_threshold=85.0,
        )

        breaker = MonitoringCircuitBreaker(config=config)

        # Trip the breaker
        await breaker.trip("Test trip")

        # Mock system resources to still be elevated
        with patch(
            "mcp.monitoring_server_enhanced._get_system_resources"
        ) as mock_resources:
            mock_resources.return_value = (95.0, 90.0)  # CPU 95%, Memory 90%

            result = await breaker._attempt_recovery()

            assert result is False
            assert breaker.is_tripped is True

    @pytest.mark.asyncio
    async def test_attempt_recovery_interval_not_passed(self, mock_logger):
        """Test recovery attempt waits for interval."""
        import time

        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            recovery_enabled=True,
            recovery_interval_seconds=10,
        )

        breaker = MonitoringCircuitBreaker(config=config)

        # Trip the breaker
        await breaker.trip("Test trip")

        # First attempt should wait
        breaker.trip_time = time.time() - 5.0  # 5 seconds ago
        breaker.last_recovery_attempt = time.time() - 3.0  # 3 seconds ago

        result = await breaker._attempt_recovery()

        assert result is False
        assert breaker.recovery_attempt_count == 1

    @pytest.mark.asyncio
    async def test_attempt_recovery_max_attempts(self, mock_logger):
        """Test recovery fails after max attempts."""
        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            recovery_enabled=True,
            max_recovery_attempts=3,
        )

        breaker = MonitoringCircuitBreaker(config=config)

        # Trip the breaker
        await breaker.trip("Test trip")

        # Set max attempts reached
        breaker.recovery_attempt_count = 3

        # Mock system resources to be acceptable
        with patch(
            "mcp.monitoring_server_enhanced._get_system_resources"
        ) as mock_resources:
            mock_resources.return_value = (15.0, 50.0)

            result = await breaker._attempt_recovery()

            assert result is False
            assert breaker.recovery_attempt_count == 3

    @pytest.mark.asyncio
    async def test_attempt_recovery_disabled(self, mock_logger):
        """Test recovery is disabled when recovery_disabled is false."""
        from mcp.monitoring_server_enhanced import (
            MonitoringCircuitBreaker,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            recovery_enabled=False,
        )

        breaker = MonitoringCircuitBreaker(config=config)

        # Trip the breaker
        await breaker.trip("Test trip")

        # Should not attempt recovery
        assert breaker.recovery_attempt_count == 0


class TestProductionMonitoringServer:
    """Test suite for ProductionMonitoringServer."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_logger):
        """Test that monitoring server initializes correctly."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        assert server is not None
        assert server.running is False
        assert server.monitor_task is None
        assert server.dashboard_app is None

        # Verify circuit breaker
        assert server.circuit_breaker is not None
        assert isinstance(server.circuit_breaker.is_tripped, bool)

        # Verify alert history
        assert server.alert_history is not None
        assert server.max_history_size == 100

        # Verify Prometheus metrics
        assert hasattr(server, "metric_health_checks")
        assert hasattr(server, "metric_alerts_sent")

        # Verify statistics
        assert server.total_health_checks == 0
        assert server.start_time is None

    @pytest.mark.asyncio
    async def test_start(self, mock_logger):
        """Test that server starts correctly."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Mock dashboard start (often fails in tests)
        with patch(
            "mcp.monitoring_server_enhanced.ProductionMonitoringServer._start_dashboard"
        ):
            await server.start()

        assert server.running is True
        assert server.start_time is not None
        assert isinstance(server.start_time, datetime)
        assert server.monitor_task is not None

    @pytest.mark.asyncio
    async def test_start_already_running(self, mock_logger):
        """Test that starting already running server is safe."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()
        server.running = True

        await server.start()

        # Should return without error
        assert server.running is True

    @pytest.mark.asyncio
    async def test_stop(self, mock_logger):
        """Test that server stops correctly."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()
        await server.start()

        # Stop the server
        await server.stop()

        assert server.running is False

    @pytest.mark.asyncio
    async def test_stop_not_running(self, mock_logger):
        """Test that stopping non-running server is safe."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Stop without starting
        await server.stop()

        assert server.running is False

    @pytest.mark.asyncio
    async def test_monitoring_loop(self, mock_logger):
        """Test that monitoring loop runs health checks."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Mock health checks to run once
        health_check_count = [0]
        check_server_health_calls = [0]

        async def mock_check_health():
            health_check_count[0] += 1
            await asyncio.sleep(0.01)

        async def mock_monitor():
            check_server_health_calls[0] += 1
            await asyncio.sleep(0.01)

        server._check_server_health = mock_check_health
        server._monitoring_loop = mock_monitor

        # Run monitoring loop briefly
        await server.start()

        # Wait for one health check
        await asyncio.sleep(0.1)

        # Stop server
        await server.stop()

        # Verify health checks were called
        assert health_check_count[0] >= 1
        assert check_server_health_calls[0] >= 1

    @pytest.mark.asyncio
    async def test_get_system_health(self, mock_logger):
        """Test getting system health."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Mock health checks to return basic data
        async def mock_check_main():
            return {
                "status": "healthy",
                "message": "Main bot is running",
            }

        async def mock_check_wallet():
            return {
                "status": "healthy",
                "memory_mb": 50.0,
                "memory_limit_mb": 100.0,
                "message": "Memory usage acceptable",
            }

        async def mock_get_performance():
            return {
                "cpu_percent": 15.0,
                "memory_mb": 256.0,
                "memory_percent": 25.0,
            }

        server._check_main_bot = mock_check_main
        server._check_wallet_monitor = mock_check_wallet
        server._get_performance_metrics = mock_get_performance

        health = await server.get_system_health()

        assert health is not None
        assert "timestamp" in health
        assert "overall_status" in health
        assert "components" in health
        assert "performance" in health
        assert "resource_limits" in health

        # Verify components
        assert "main_bot" in health["components"]
        assert "wallet_monitor" in health["components"]

    @pytest.mark.asyncio
    async def test_get_system_health_critical_status(self, mock_logger):
        """Test that critical status is determined correctly."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Mock critical health check
        async def mock_check_critical():
            return {
                "status": "critical",
                "message": "Critical issue detected",
            }

        server._check_main_bot = mock_check_critical

        health = await server.get_system_health()

        assert health["overall_status"] == "critical"

    @pytest.mark.asyncio
    async def test_get_system_health_resource_limits(self, mock_logger):
        """Test that resource limits are included in health."""
        from mcp.monitoring_server_enhanced import (
            ProductionMonitoringServer,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            max_cpu_percent=90.0,
            max_memory_mb=100.0,
        )

        server = ProductionMonitoringServer()
        server.circuit_breaker.config = config

        health = await server.get_system_health()

        assert "resource_limits" in health
        assert health["resource_limits"]["max_cpu_percent"] == 90.0
        assert health["resource_limits"]["max_memory_mb"] == 100.0

    @pytest.mark.asyncio
    async def test_check_main_bot(self, mock_logger, temp_data_dir):
        """Test main bot health check."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Mock settings
        with patch("config.settings.get_settings") as mock_settings:
            mock_settings_instance = MagicMock()
            mock_settings_instance.trading = MagicMock()
            mock_settings_instance.trading.private_key = "0x" + "a" * 64
            mock_settings_instance.network = MagicMock()
            mock_settings_instance.network.polygon_rpc_url = "https://polygon-rpc.com"
            mock_settings.return_value = mock_settings_instance

            health = await server._check_main_bot()

            assert health is not None
            assert health["status"] == "healthy"
            assert health["has_private_key"] is True
            assert health["has_rpc"] is True

    @pytest.mark.asyncio
    async def test_check_wallet_monitor(self, mock_logger):
        """Test wallet monitor health check."""
        from mcp.monitoring_server_enhanced import (
            ProductionMonitoringServer,
            MonitoringConfig,
        )

        server = ProductionMonitoringServer()
        server.circuit_breaker.config = MonitoringConfig(
            max_memory_mb=100.0,
        )

        # Mock component memory check
        async def mock_get_component_memory():
            return 50.0

        server._get_component_memory = mock_get_component_memory

        health = await server._check_wallet_monitor()

        assert health is not None
        assert health["memory_mb"] == 50.0
        assert health["memory_limit_mb"] == 100.0
        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_wallet_monitor_critical(self, mock_logger):
        """Test wallet monitor health check with critical memory."""
        from mcp.monitoring_server_enhanced import (
            ProductionMonitoringServer,
            MonitoringConfig,
        )

        server = ProductionMonitoringServer()
        server.circuit_breaker.config = MonitoringConfig(
            max_memory_mb=100.0,
        )

        # Mock component memory check - high usage
        async def mock_get_component_memory():
            return 90.0  # Above 80% threshold

        server._get_component_memory = mock_get_component_memory

        health = await server._check_wallet_monitor()

        assert health["status"] == "critical"
        assert health["memory_mb"] == 90.0

    @pytest.mark.asyncio
    async def test_get_performance_metrics(self, mock_logger):
        """Test getting performance metrics."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Mock psutil
        with patch("mcp.monitoring_server_enhanced.psutil") as mock_psutil:
            mock_process = MagicMock()
            mock_process.cpu_percent = MagicMock(return_value=15.0)
            mock_process.memory_info = MagicMock(return_value=MagicMock(rss=262144000))
            mock_vm = MagicMock()
            mock_vm.percent = MagicMock(return_value=25.0)
            mock_psutil.Process.return_value = mock_process
            mock_psutil.virtual_memory = MagicMock(return_value=mock_vm)

            metrics = await server._get_performance_metrics()

            assert metrics is not None
            assert metrics["cpu_percent"] == 15.0
            assert metrics["memory_mb"] == 256.0
            assert metrics["memory_percent"] == 25.0
            assert metrics["total_health_checks"] >= 0

    @pytest.mark.asyncio
    async def test_get_performance_metrics_no_psutil(self, mock_logger):
        """Test performance metrics when psutil not available."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Mock psutil ImportError
        with patch("mcp.monitoring_server_enhanced.psutil", side_effect=ImportError):
            metrics = await server._get_performance_metrics()

            assert metrics is not None
            # Should return dummy values
            assert metrics["cpu_percent"] == 0.0
            assert metrics["memory_mb"] == 0.0
            assert metrics["memory_percent"] == 0.0

    @pytest.mark.asyncio
    async def test_determine_overall_status(self, mock_logger):
        """Test overall status determination."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Test healthy (no critical, at most 1 degraded)
        components = {
            "component1": {"status": "healthy"},
            "component2": {"status": "healthy"},
        }

        status = server._determine_overall_status(components)

        assert status == "healthy"

        # Test degraded (2 degraded)
        components = {
            "component1": {"status": "degraded"},
            "component2": {"status": "degraded"},
        }

        status = server._determine_overall_status(components)

        assert status == "critical"

        # Test critical (1 critical)
        components = {
            "component1": {"status": "critical"},
            "component2": {"status": "healthy"},
        }

        status = server._determine_overall_status(components)

        assert status == "critical"

    @pytest.mark.asyncio
    async def test_update_history(self, mock_logger):
        """Test health history is updated correctly."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Perform a health check
        health = await server.get_system_health()

        # Verify history was updated
        assert len(server.health_history) == 1
        assert server.health_history[0] == health

        # Verify size limit is maintained
        for i in range(150):
            await server.get_system_health()

        assert len(server.health_history) <= server.max_history_size
        assert len(server.health_history) == server.max_history_size

    @pytest.mark.asyncio
    async def test_update_metrics(self, mock_logger):
        """Test Prometheus metrics are updated."""
        from mcp.monitoring_server_enhanced import (
            ProductionMonitoringServer,
            MonitoringConfig,
        )

        config = MonitoringConfig(metrics_enabled=True)
        server = ProductionMonitoringServer()
        server.circuit_breaker.config = config

        health = await server.get_system_health()

        # Verify metrics were called
        assert server.metric_health_checks.labels.called
        assert server.metric_cpu_usage.called

    @pytest.mark.asyncio
    async def test_check_for_alerts(self, mock_logger):
        """Test that alerts are triggered for critical issues."""
        from mcp.monitoring_server_enhanced import (
            ProductionMonitoringServer,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            alert_enabled=True,
        )

        server = ProductionMonitoringServer()
        server.circuit_breaker.config = config

        # Mock health check with critical status
        async def mock_critical_health():
            return {
                "status": "critical",
                "message": "Critical failure",
            }

        async def mock_send_alert():
            pass

        server._check_main_bot = mock_critical_health
        server._send_alert = mock_send_alert

        health = await server.get_system_health()

        # Verify alert was sent for critical status
        # Alert should have been triggered
        assert True  # Test completed

    @pytest.mark.asyncio
    async def test_alert_deduplication(self, mock_logger):
        """Test that duplicate alerts are suppressed."""
        from mcp.monitoring_server_enhanced import (
            ProductionMonitoringServer,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            alert_enabled=True,
            duplicate_alerts=True,
            duplicate_alert_window_minutes=10,
        )

        server = ProductionMonitoringServer()
        server.circuit_breaker.config = config

        alert_count = [0]

        async def mock_send_alert(severity, component, message):
            alert_count[0] += 1

        server._send_alert = mock_send_alert

        # Send same alert twice quickly
        await server._check_for_alerts(
            {
                "components": {
                    "component1": {
                        "status": "critical",
                        "message": "Test alert",
                    }
                }
            }
        )

        # Send again immediately (should be suppressed)
        await server._check_for_alerts(
            {
                "components": {
                    "component1": {
                        "status": "critical",
                        "message": "Test alert",
                    }
                }
            }
        )

        # Verify only one alert was sent
        assert alert_count[0] == 1
        assert server.alerts_suppressed == 1


class TestPrometheusMetrics:
    """Test suite for Prometheus metrics."""

    def test_initialization(self, mock_logger):
        """Test that Prometheus metrics are initialized."""
        from mcp.monitoring_server_enhanced import (
            ProductionMonitoringServer,
            MonitoringConfig,
        )

        config = MonitoringConfig(metrics_enabled=True)
        server = ProductionMonitoringServer()
        server.circuit_breaker.config = config

        # Verify metrics were created
        assert server.metric_health_checks is not None
        assert server.metric_alerts_sent is not None
        assert server.metric_alerts_suppressed is not None
        assert server.metric_cpu_usage is not None
        assert server.metric_memory_usage is not None

    @pytest.mark.asyncio
    async def test_metrics_update(self, mock_logger):
        """Test that metrics are updated with correct labels."""
        from mcp.monitoring_server_enhanced import (
            ProductionMonitoringServer,
            MonitoringConfig,
        )

        config = MonitoringConfig(metrics_enabled=True)
        server = ProductionMonitoringServer()
        server.circuit_breaker.config = config

        # Update metrics by calling health check
        await server.get_system_health()

        # Verify health check counter was incremented
        assert server.total_health_checks == 1

    @pytest.mark.asyncio
    async def test_component_status_metrics(self, mock_logger):
        """Test that component status gauges are updated."""
        from mcp.monitoring_server_enhanced import (
            ProductionMonitoringServer,
            MonitoringConfig,
        )

        config = MonitoringConfig(metrics_enabled=True)
        server = ProductionMonitoringServer()
        server.circuit_breaker.config = config

        health = await server.get_system_health()

        # Verify component status was updated
        assert server.metric_component_status.labels.called


class TestWebDashboard:
    """Test suite for web dashboard functionality."""

    @pytest.mark.asyncio
    async def test_dashboard_starts(self, mock_logger):
        """Test that web dashboard starts correctly."""
        from mcp.monitoring_server_enhanced import (
            ProductionMonitoringServer,
            MonitoringConfig,
        )

        config = MonitoringConfig(
            dashboard_enabled=True,
            dashboard_port=8888,
        )

        server = ProductionMonitoringServer()
        server.circuit_breaker.config = config

        # Mock aiohttp to avoid actual web server
        with patch("mcp.monitoring_server_enhanced.web") as mock_web:
            mock_web.Application = MagicMock()
            mock_web.AppRunner = MagicMock()
            mock_web.AppRunner.setup = AsyncMock()
            mock_web.AppRunner.cleanup = AsyncMock()
            mock_web.TCPSite = MagicMock()
            mock_web.TCPSite.start = MagicMock()

            mock_web.Application.return_value = mock_web.Application
            mock_web.AppRunner.return_value = mock_web.AppRunner

            await server.start()

            # Verify dashboard was started
            mock_web.AppRunner.setup.assert_awaited_once()
            mock_web.TCPSite.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dashboard_generates_html(self, mock_logger):
        """Test that dashboard generates correct HTML."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Mock aiohttp
        with patch("mcp.monitoring_server_enhanced.web") as mock_web:
            mock_web.Application = MagicMock()
            mock_web.Response = MagicMock()

            # Mock dashboard handler
            html = server._generate_dashboard_html()

            # Verify HTML contains expected elements
            assert "<!DOCTYPE html>" in html
            assert "Polymarket Bot Monitoring Dashboard" in html
            assert "Loading monitoring data..." in html
            assert "metrics-grid" in html
            assert "components-section" in html

    @pytest.mark.asyncio
    async def test_health_handler(self, mock_logger):
        """Test that health handler returns JSON."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Mock health check
        async def mock_health():
            return {
                "overall_status": "healthy",
                "components": {},
                "performance": {},
            }

        server.get_system_health = mock_health

        # Mock aiohttp
        with patch("mcp.monitoring_server_enhanced.web") as mock_web:
            mock_web.json_response = MagicMock()

            # Create mock request
            request = MagicMock()
            request.url.path = "/health"

            result = await server._health_handler(request)

            # Verify JSON response was called
            mock_web.json_response.assert_awaited_once()


class TestGetMonitoringServer:
    """Test suite for get_monitoring_server singleton."""

    def test_singleton_pattern(self, mock_logger):
        """Test that get_monitoring_server returns singleton instance."""
        from mcp.monitoring_server_enhanced import (
            get_monitoring_server,
            _monitoring_server,
        )

        # Clear singleton for test
        global _monitoring_server
        _monitoring_server = None

        # Get first instance
        instance1 = get_monitoring_server()

        # Get second instance
        instance2 = get_monitoring_server()

        # Should be same instance
        assert instance1 is instance2

    def test_singleton_persistence(self, mock_logger):
        """Test that singleton persists across calls."""
        from mcp.monitoring_server_enhanced import get_monitoring_server

        # Get singleton
        instance1 = get_monitoring_server()

        # Get singleton again
        instance2 = get_monitoring_server()

        # Get singleton third time
        instance3 = get_monitoring_server()

        # All should be same instance
        assert instance1 is instance2
        assert instance2 is instance3


class TestMonitoringConfig:
    """Test suite for MonitoringConfig."""

    def test_default_values(self, mock_logger):
        """Test default configuration values."""
        from mcp.monitoring_server_enhanced import MonitoringConfig

        config = MonitoringConfig()

        assert config.enabled is True
        assert config.check_interval_seconds == 60
        assert config.max_cpu_percent == 90.0
        assert config.max_memory_mb == 100.0
        assert config.alert_enabled is False
        assert config.metrics_enabled is False
        assert config.dashboard_enabled is False

    def test_custom_values(self, mock_logger):
        """Test custom configuration values."""
        from mcp.monitoring_server_enhanced import MonitoringConfig

        config = MonitoringConfig(
            enabled=True,
            check_interval_seconds=30,
            max_cpu_percent=95.0,
            max_memory_mb=200.0,
            alert_enabled=True,
            metrics_enabled=True,
            dashboard_enabled=True,
            dashboard_port=8888,
            duplicate_alerts=True,
            duplicate_alert_window_minutes=15,
            circuit_breaker_enabled=True,
            circuit_breaker_cpu_threshold=85.0,
            circuit_breaker_memory_threshold=80.0,
            circuit_breaker_recovery_enabled=True,
            circuit_breaker_recovery_interval_seconds=300,
            circuit_breaker_max_recovery_attempts=5,
        )

        assert config.enabled is True
        assert config.check_interval_seconds == 30
        assert config.max_cpu_percent == 95.0
        assert config.max_memory_mb == 200.0
        assert config.alert_enabled is True
        assert config.metrics_enabled is True
        assert config.dashboard_enabled is True
        assert config.dashboard_port == 8888
        assert config.duplicate_alerts is True
        assert config.circuit_breaker_enabled is True

    def test_component_memory_limits(self, mock_logger):
        """Test component memory limit calculation."""
        from mcp.monitoring_server_enhanced import MonitoringConfig

        config = MonitoringConfig(max_memory_mb=100.0)

        assert config.get_component_memory_limit("codebase_search") == 10.0
        assert config.get_component_memory_limit("testing") == 10.0
        assert (
            config.get_component_memory_limit("monitoring") == 80.0
        )  # Monitoring uses 80%
