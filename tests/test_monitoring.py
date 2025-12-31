"""Unit tests for monitoring system.

Tests cover:
- MonitoringConfig validation
- Alert deduplication
- Monitoring circuit breaker
- Health check components
- Prometheus metrics integration
- Resource limit enforcement
"""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from config.mcp_config import MonitoringConfig


class TestMonitoringConfig:
    """Test MonitoringConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MonitoringConfig()

        assert config.enabled is True
        assert config.dashboard_enabled is True
        assert config.alert_enabled is True
        assert config.metrics_enabled is True
        assert config.max_cpu_percent == 1.0
        assert config.max_memory_mb == 100.0
        assert config.circuit_breaker_enabled is True
        assert config.recovery_enabled is True

    def test_memory_thresholds(self):
        """Test memory threshold configuration."""
        config = MonitoringConfig()

        assert "wallet_monitor" in config.memory_threshold_mb
        assert "scanner" in config.memory_threshold_mb
        assert "trade_executor" in config.memory_threshold_mb
        assert config.memory_threshold_mb["wallet_monitor"] == 500
        assert config.memory_threshold_mb["scanner"] == 300
        assert config.memory_threshold_mb["trade_executor"] == 200

    def test_component_memory_limit(self):
        """Test get_component_memory_limit method."""
        config = MonitoringConfig()

        assert config.get_component_memory_limit("wallet_monitor") == 500
        assert config.get_component_memory_limit("scanner") == 300
        assert config.get_component_memory_limit("unknown") == 200

    def test_api_thresholds(self):
        """Test API threshold configuration."""
        config = MonitoringConfig()

        assert config.api_success_threshold == 0.8
        assert config.api_failure_count_threshold == 5

    def test_risk_thresholds(self):
        """Test risk threshold configuration."""
        config = MonitoringConfig()

        assert config.daily_loss_warning_percent == 0.12
        assert config.daily_loss_critical_percent == 0.15
        assert config.daily_loss_critical_percent > config.daily_loss_warning_percent

    def test_cpu_limit_warning(self, caplog):
        """Test warning when CPU limit is too high."""
        with caplog.at_level(logging.WARNING):
            config = MonitoringConfig(max_cpu_percent=5.0)
            assert "may impact trading" in caplog.text

    def test_memory_limit_warning(self, caplog):
        """Test warning when memory limit is too high."""
        with caplog.at_level(logging.WARNING):
            config = MonitoringConfig(max_memory_mb=500.0)
            assert "may be excessive" in caplog.text

    def test_invalid_risk_thresholds(self, caplog):
        """Test warning when critical threshold <= warning threshold."""
        with caplog.at_level(logging.WARNING):
            config = MonitoringConfig(
                daily_loss_warning_percent=0.15, daily_loss_critical_percent=0.12
            )
            assert "Critical loss threshold" in caplog.text


class TestAlertHistory:
    """Test AlertHistory class for deduplication."""

    @pytest.fixture
    def alert_history(self):
        """Create AlertHistory instance."""
        from mcp.monitoring_server_enhanced import AlertHistory

        return AlertHistory(max_window_minutes=10)

    def test_no_duplicate_new_alert(self, alert_history):
        """Test that new alert is not considered duplicate."""
        alert_key = "critical:wallet_monitor:High memory usage"

        is_duplicate = alert_history.is_duplicate(alert_key)
        assert is_duplicate is False

    def test_duplicate_within_window(self, alert_history):
        """Test that alert within window is duplicate."""
        alert_key = "warning:trade_executor:Degraded status"

        # Record alert
        alert_history.record_alert(alert_key)

        # Check immediately (within window)
        is_duplicate = alert_history.is_duplicate(alert_key)
        assert is_duplicate is True

    def test_no_duplicate_outside_window(self, alert_history):
        """Test that alert outside window is not duplicate."""
        alert_key = "warning:trade_executor:Degraded status"

        # Record alert and simulate time passing
        alert_history.record_alert(alert_key)
        alert_history.alerts[alert_key] = time.time() - (11 * 60)  # 11 minutes ago

        # Check outside window
        is_duplicate = alert_history.is_duplicate(alert_key)
        assert is_duplicate is False

    def test_cleanup_old_alerts(self, alert_history):
        """Test cleanup of old alerts."""
        # Add multiple alerts
        for i in range(10):
            alert_key = f"test_alert_{i}"
            alert_history.record_alert(alert_key)

        # Make half of them old
        for i in range(5):
            alert_key = f"test_alert_{i}"
            alert_history.alerts[alert_key] = time.time() - (11 * 60)

        # Cleanup
        alert_history.cleanup_old_alerts()

        # Should only have 5 alerts
        assert len(alert_history.alerts) == 5

    def test_multiple_different_alerts(self, alert_history):
        """Test multiple different alert keys."""
        alerts = [
            "critical:wallet_monitor:High memory",
            "warning:trade_executor:Slow execution",
            "info:scanner:Scan complete",
        ]

        for alert in alerts:
            assert alert_history.is_duplicate(alert) is False

        # Record all alerts
        for alert in alerts:
            alert_history.record_alert(alert)

        # All should be considered duplicates now
        for alert in alerts:
            assert alert_history.is_duplicate(alert) is True


class TestMonitoringCircuitBreaker:
    """Test MonitoringCircuitBreaker class."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker instance."""
        from mcp.monitoring_server_enhanced import MonitoringCircuitBreaker

        config = MonitoringConfig(
            circuit_breaker_enabled=True,
            recovery_enabled=True,
            max_recovery_attempts=3,
            recovery_interval_seconds=60,
        )

        return MonitoringCircuitBreaker(config=config)

    def test_initial_state(self, circuit_breaker):
        """Test initial circuit breaker state."""
        assert circuit_breaker.is_tripped is False
        assert circuit_breaker.trip_time is None
        assert circuit_breaker.recovery_attempt_count == 0

    def test_should_monitor_not_tripped(self, circuit_breaker):
        """Test that monitoring is allowed when not tripped."""
        is_allowed = asyncio.run(circuit_breaker.should_monitor())
        assert is_allowed is True

    @pytest.mark.asyncio
    async def test_trip_circuit_breaker(self, circuit_breaker):
        """Test tripping the circuit breaker."""
        await circuit_breaker.trip("CPU usage 95%")

        assert circuit_breaker.is_tripped is True
        assert circuit_breaker.trip_time is not None

    @pytest.mark.asyncio
    async def test_should_monitor_after_trip(self, circuit_breaker):
        """Test that monitoring is denied after trip."""
        await circuit_breaker.trip("CPU overload")

        # Should not allow monitoring immediately
        is_allowed = await circuit_breaker.should_monitor()
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, circuit_breaker):
        """Test circuit breaker recovery."""
        await circuit_breaker.trip("Memory overload")

        # Simulate resources being acceptable
        circuit_breaker.cpu_threshold = 50.0
        circuit_breaker.memory_threshold = 50.0

        # Force immediate recovery by setting trip_time in past
        circuit_breaker.trip_time = time.time() - 61

        # Should attempt recovery
        is_allowed = await circuit_breaker.should_monitor()
        assert is_allowed is True
        assert circuit_breaker.is_tripped is False

    @pytest.mark.asyncio
    async def test_max_recovery_attempts(self, circuit_breaker, caplog):
        """Test that recovery stops after max attempts."""
        # Configure max attempts = 1
        circuit_breaker.config.max_recovery_attempts = 1

        await circuit_breaker.trip("CPU overload")
        circuit_breaker.trip_time = time.time() - 61

        # First recovery fails (resources still high)
        circuit_breaker.cpu_threshold = 95.0
        is_allowed = await circuit_breaker.should_monitor()
        assert is_allowed is False

        # Second recovery should not be attempted
        circuit_breaker.recovery_attempt_count = 1
        is_allowed = await circuit_breaker.should_monitor()
        assert is_allowed is False

    def test_manual_reset(self, circuit_breaker):
        """Test manual circuit breaker reset."""
        circuit_breaker.is_tripped = True
        circuit_breaker.trip_time = time.time()
        circuit_breaker.recovery_attempt_count = 5

        circuit_breaker.reset()

        assert circuit_breaker.is_tripped is False
        assert circuit_breaker.trip_time is None
        assert circuit_breaker.recovery_attempt_count == 0


class TestProductionMonitoringServer:
    """Test ProductionMonitoringServer class."""

    @pytest.fixture
    async def monitoring_server(self):
        """Create monitoring server instance."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        # Disable actual monitoring for tests
        config = MonitoringConfig(
            enabled=False, dashboard_enabled=False, metrics_enabled=False
        )

        server = ProductionMonitoringServer()
        server.config = config

        return server

    def test_initialization(self, monitoring_server):
        """Test monitoring server initialization."""
        assert monitoring_server.running is False
        assert monitoring_server.start_time is None
        assert monitoring_server.config.enabled is False

    def test_circuit_breaker_initialization(self, monitoring_server):
        """Test circuit breaker is initialized."""
        assert monitoring_server.circuit_breaker is not None
        assert monitoring_server.circuit_breaker.config is not None

    def test_alert_history_initialization(self, monitoring_server):
        """Test alert history is initialized."""
        assert monitoring_server.alert_history is not None
        assert monitoring_server.alerts_suppressed == 0
        assert len(monitoring_server.alert_history.alerts) == 0

    @pytest.mark.asyncio
    async def test_determine_overall_status(self, monitoring_server):
        """Test overall status determination."""
        # All healthy
        components = {
            "main_bot": {"status": "healthy"},
            "wallet_monitor": {"status": "healthy"},
        }
        status = monitoring_server._determine_overall_status(components)
        assert status == "healthy"

        # One degraded
        components = {
            "main_bot": {"status": "healthy"},
            "wallet_monitor": {"status": "degraded"},
        }
        status = monitoring_server._determine_overall_status(components)
        assert status == "degraded"

        # Two degraded
        components = {
            "main_bot": {"status": "degraded"},
            "wallet_monitor": {"status": "degraded"},
        }
        status = monitoring_server._determine_overall_status(components)
        assert status == "critical"

        # One critical
        components = {
            "main_bot": {"status": "healthy"},
            "wallet_monitor": {"status": "critical"},
        }
        status = monitoring_server._determine_overall_status(components)
        assert status == "critical"

    @pytest.mark.asyncio
    async def test_check_main_bot(self, monitoring_server):
        """Test main bot health check."""
        health = await monitoring_server._check_main_bot()

        assert "status" in health
        assert "message" in health
        assert health["status"] in ["healthy", "degraded"]

    @pytest.mark.asyncio
    async def test_check_wallet_monitor(self, monitoring_server):
        """Test wallet monitor health check."""
        health = await monitoring_server._check_wallet_monitor()

        assert "status" in health
        assert "memory_mb" in health
        assert "memory_limit_mb" in health

    @pytest.mark.asyncio
    async def test_check_alert_system(self, monitoring_server):
        """Test alert system health check."""
        health = await monitoring_server._check_alert_system()

        assert "status" in health
        assert "enabled" in health
        assert "alerts_sent" in health

    @pytest.mark.asyncio
    async def test_alert_deduplication(self, monitoring_server, caplog):
        """Test alert deduplication logic."""
        monitoring_server.config.alert_enabled = True
        monitoring_server.config.deduplicate_alerts = True

        # Mock alert manager
        with patch("utils.alerts.send_telegram_alert") as mock_send:
            # Send first alert
            await monitoring_server._send_alert(
                severity="critical",
                component="wallet_monitor",
                message="High memory usage",
            )

            # Should have sent
            assert mock_send.call_count == 1

            # Try to send duplicate
            await monitoring_server._send_alert(
                severity="critical",
                component="wallet_monitor",
                message="High memory usage",
            )

            # Should be suppressed
            assert mock_send.call_count == 1
            assert monitoring_server.alerts_suppressed == 1

    @pytest.mark.asyncio
    async def test_history_update(self, monitoring_server):
        """Test health history update."""
        health = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "healthy",
            "components": {},
            "performance": {},
        }

        # Add health check
        await monitoring_server._update_history(health)

        assert len(monitoring_server.health_history) == 1
        assert monitoring_server.health_history[0] == health

        # Add more checks
        for _ in range(150):
            await monitoring_server._update_history(health)

        # Should be limited to max_history_size
        assert (
            len(monitoring_server.health_history) == monitoring_server.max_history_size
        )


class TestResourceLimits:
    """Test resource limit enforcement."""

    def test_memory_limit_validation(self):
        """Test memory limit validation."""
        config = MonitoringConfig(max_memory_mb=200.0)

        # Should log warning but still be valid
        assert config.max_memory_mb == 200.0

    def test_cpu_limit_validation(self):
        """Test CPU limit validation."""
        config = MonitoringConfig(max_cpu_percent=3.0)

        # Should log warning but still be valid
        assert config.max_cpu_percent == 3.0

    def test_component_memory_limits(self):
        """Test component-specific memory limits."""
        config = MonitoringConfig()

        # Each component should have appropriate limit
        assert config.get_component_memory_limit("wallet_monitor") == 500
        assert config.get_component_memory_limit("scanner") == 300
        assert config.get_component_memory_limit("trade_executor") == 200

        # Unknown component should get default
        assert config.get_component_memory_limit("unknown") == 200


@pytest.mark.integration
class TestMonitoringIntegration:
    """Integration tests for monitoring system."""

    @pytest.mark.asyncio
    async def test_full_monitoring_cycle(self, tmp_path):
        """Test complete monitoring cycle."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        # Create monitoring server
        server = ProductionMonitoringServer()

        # Mock components
        with patch("mcp.monitoring_server_enhanced.PrometheusMetrics"):
            # Start server
            await server.start()
            assert server.running is True

            # Get health
            health = await server.get_system_health()
            assert health["overall_status"] in ["healthy", "degraded", "critical"]

            # Update history
            await server._update_history(health)
            assert len(server.health_history) > 0

            # Stop server
            await server.stop()
            assert server.running is False

    @pytest.mark.asyncio
    async def test_dashboard_generation(self):
        """Test dashboard HTML generation."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()
        html = server._generate_dashboard_html()

        # Should contain key elements
        assert "<!DOCTYPE html>" in html
        assert "Polymarket Bot Monitoring" in html
        assert "overall-status" in html
        assert "component-grid" in html
        assert "refreshInterval" in html

    @pytest.mark.asyncio
    async def test_prometheus_metrics(self):
        """Test Prometheus metrics initialization."""
        from mcp.monitoring_server_enhanced import ProductionMonitoringServer

        server = ProductionMonitoringServer()

        # Check metrics are initialized
        if server.config.metrics_enabled:
            assert server.metric_health_checks is not None
            assert server.metric_alerts_sent is not None
            assert server.metric_cpu_usage is not None
            assert server.metric_memory_usage is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
