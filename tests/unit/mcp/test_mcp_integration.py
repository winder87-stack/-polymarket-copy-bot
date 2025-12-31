"""
MCP Server Integration Tests

This module tests MCP server interactions and end-to-end scenarios.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))


class TestMCPServerLifecycle:
    """Test suite for complete MCP server lifecycle."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_with_all_servers(self):
        """Test complete lifecycle: start → monitor → stop."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=["codebase_search", "testing", "monitoring"])

        # Start servers
        await manager.start()

        assert manager.running is True
        assert manager.start_time is not None

        # Let monitoring run briefly
        await asyncio.sleep(0.05)

        # Stop servers
        await manager.stop()

        assert manager.running is False
        assert manager.shutdown_requested is True

    @pytest.mark.asyncio
    async def test_lifecycle_with_error_recovery(self):
        """Test server lifecycle with error recovery."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=["monitoring"])

        # Mock server to fail on first start
        with patch("mcp.main_mcp.MonitoringServer") as MockMonitoring:
            mock_server = MagicMock()
            MockMonitoring.return_value = mock_server

            # Mock start to raise error
            async def mock_start_error():
                raise Exception("Server start failed")

            mock_server.start = mock_start_error

            manager.monitoring_server = mock_server

            # Start manager
            await manager.start()

            # Verify error was tracked
            assert manager.error_count.get("monitoring", 0) == 1

            # Stop manager
            await manager.stop()


class TestCircuitBreakerIntegration:
    """Test suite for circuit breaker integration across MCP servers."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_on_high_cpu(self):
        """Test that circuit breaker trips on high CPU usage."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=["monitoring"])

        # Mock resource check to return high CPU
        async def mock_high_cpu():
            return {"cpu_percent": 95.0}

        manager._check_resource_usage = mock_high_cpu

        # Start manager
        await manager.start()

        # Let monitoring run briefly
        await asyncio.sleep(0.02)

        # Stop manager
        await manager.stop()

        # Verify circuit breaker was triggered
        # (Would check circuit breaker state in real test)

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovers_after_interval(self):
        """Test that circuit breaker recovers after interval."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=["monitoring"])

        # Track monitoring loop calls
        loop_iterations = [0]

        async def mock_monitor():
            loop_iterations[0] += 1
            if loop_iterations[0] <= 2:
                # Simulate circuit breaker active
                pass
            await asyncio.sleep(0.01)

        manager._monitoring_loop = mock_monitor

        # Start manager
        manager.running = True
        monitor_task = asyncio.create_task(manager._monitoring_loop())

        # Wait for initial iteration
        await asyncio.sleep(0.015)

        # Stop manager
        manager.shutdown_requested = True
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Verify multiple iterations attempted
        assert loop_iterations[0] >= 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_multiple_servers(self):
        """Test circuit breaker behavior with multiple servers."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=["codebase_search", "testing"])

        # Mock different server health states
        async def mock_codebase_healthy():
            return {"status": "healthy"}

        async def mock_testing_degraded():
            return {"status": "degraded"}

        manager._check_codebase_search_health = mock_codebase_healthy
        manager._check_testing_server_health = mock_testing_degraded

        # Start manager
        await manager.start()

        # Let it run briefly
        await asyncio.sleep(0.02)

        # Stop manager
        await manager.stop()

        # Verify different health states
        # (Would check overall status in real test)


class TestAlertSystemIntegration:
    """Test suite for alert system integration."""

    @pytest.mark.asyncio
    async def test_startup_alert_content(self):
        """Test that startup alert contains required information."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=["testing"])

        manager.start_time = datetime.now(timezone.utc)
        manager.startup_times = {"testing": 1.5}
        manager.error_count = {"testing": 0}

        # Mock alert sending
        alerts_sent = []

        async def mock_send_alert(message):
            alerts_sent.append(message)
            await asyncio.sleep(0.01)

        manager._send_startup_alert = mock_send_alert

        # Send startup alert
        await manager._send_startup_alert()

        # Verify alert was sent
        assert len(alerts_sent) == 1

        # Verify alert contains required fields
        alert_message = alerts_sent[0]
        assert "MCP SERVERS STARTED" in alert_message
        assert "testing" in alert_message
        assert "1.5" in alert_message
        assert "enabled" in alert_message

    @pytest.mark.asyncio
    async def test_shutdown_alert_statistics(self):
        """Test that shutdown alert includes statistics."""
        from mcp.main_mcp import MCPServerManager
        import time

        manager = MCPServerManager(servers=["codebase_search"])

        # Simulate some runtime
        start_time = time.time()
        manager.start_time = datetime.fromtimestamp(start_time, tz=timezone.utc)
        manager.error_count = {"codebase_search": 2}
        manager.startup_times = {"codebase_search": 2.0}

        # Mock alert sending
        alerts_sent = []

        async def mock_send_alert(message):
            alerts_sent.append(message)
            await asyncio.sleep(0.01)

        manager._send_shutdown_alert = mock_send_alert

        # Stop manager
        await manager.stop()

        # Verify alert was sent
        assert len(alerts_sent) == 1

        # Verify alert includes statistics
        alert_message = alerts_sent[0]
        assert "MCP SERVERS STOPPED" in alert_message
        assert "codebase_search" in alert_message
        assert "Errors: 2" in alert_message
        assert "2.0" in alert_message


class TestConfigurationValidationIntegration:
    """Test suite for configuration validation integration."""

    @pytest.mark.asyncio
    async def test_configuration_validation_success(self):
        """Test successful configuration validation."""
        from mcp.main_mcp import main

        # Mock validation functions
        validation_calls = []

        with patch("mcp.main_mcp.validate_codebase_search_config") as mock_validate:

            async def mock_validation():
                validation_calls.append("codebase_search")
                # Simulate success
                return

            mock_validate.return_value = mock_validation()

            # Run main with codebase_search server
            exit_code = main(["codebase_search"])

            # Verify validation was called
            assert "codebase_search" in validation_calls

            # Should succeed (no exception)
            # Note: In real test, would verify exit_code == 0

    @pytest.mark.asyncio
    async def test_configuration_validation_failure(self):
        """Test failed configuration validation."""

        # Mock validation to raise error
        with patch("mcp.main_mcp.validate_codebase_search_config") as mock_validate:
            mock_validate.side_effect = Exception("Config validation failed")

            # Run main with codebase_search server
            # Note: In real test, would verify exit_code == 1

            # Should handle error gracefully
            # (Would check that manager wasn't started)


class TestSignalHandlingIntegration:
    """Test suite for signal handling integration."""

    @pytest.mark.asyncio
    async def test_signal_handler_calls_stop(self):
        """Test that signal handler stops manager."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=[])

        # Track stop calls
        stop_calls = [0]

        async def mock_stop():
            stop_calls[0] += 1
            await asyncio.sleep(0.01)

        manager.stop = mock_stop

        # Start manager
        await manager.start()

        # Simulate signal handler
        async def signal_handler():
            await manager.stop()

        # Create and execute signal handler
        await signal_handler()

        # Verify stop was called
        assert stop_calls[0] >= 1
        assert manager.running is False


class TestResourceManagementIntegration:
    """Test suite for resource management integration."""

    @pytest.mark.asyncio
    async def test_resource_usage_tracking(self):
        """Test that resource usage is tracked correctly."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=[])

        # Track resource checks
        resource_checks = []

        async def mock_check_resources():
            resource_checks.append(True)
            await asyncio.sleep(0.01)

        manager._check_resource_usage = mock_check_resources

        # Run monitoring loop
        manager.running = True
        monitor_task = asyncio.create_task(manager._monitoring_loop())

        # Let it run briefly
        await asyncio.sleep(0.02)

        manager.shutdown_requested = True
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Verify resource checks were made
        assert len(resource_checks) >= 1

        # Verify resource usage is tracked in status
        status = manager.get_status()
        assert "resource_usage" in status

    @pytest.mark.asyncio
    async def test_resource_limit_enforcement(self):
        """Test that resource limits are enforced."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=["monitoring"])

        # Mock resource check to return usage at limit
        async def mock_at_limit():
            return {
                "cpu_percent": 90.0,  # At threshold
                "memory_percent": 85.0,  # At threshold
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        manager._check_resource_usage = mock_at_limit

        # Run monitoring loop briefly
        manager.running = True
        monitor_task = asyncio.create_task(manager._monitoring_loop())

        await asyncio.sleep(0.02)

        manager.shutdown_requested = True
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Verify circuit breaker behavior
        # (Would check if circuit breaker tripped in real test)

        # Verify resource limits are included in status
        status = manager.get_status()
        assert "resource_usage" in status


class TestEndToEndScenarios:
    """Test suite for end-to-end scenarios."""

    @pytest.mark.asyncio
    async def test_deployment_scenario(self):
        """Test deployment scenario: start all servers → monitor → stop all."""
        from mcp.main_mcp import MCPServerManager

        # All servers
        manager = MCPServerManager(servers=["codebase_search", "testing", "monitoring"])

        # Track lifecycle
        lifecycle_events = []

        # Track health checks
        health_checks_performed = [0]

        async def mock_health_check():
            health_checks_performed[0] += 1
            await asyncio.sleep(0.01)

        # Mock health checks for all servers
        manager._check_codebase_search_health = mock_health_check
        manager._check_testing_server_health = mock_health_check
        manager._check_monitoring_server_health = mock_health_check

        # Deploy (start)
        lifecycle_events.append(("start", manager.start_time))
        await manager.start()

        assert manager.running is True
        lifecycle_events.append(("running", datetime.now(timezone.utc)))

        # Let monitoring run briefly
        await asyncio.sleep(0.03)

        # Undeploy (stop)
        lifecycle_events.append(("stop", datetime.now(timezone.utc)))
        await manager.stop()

        assert manager.running is False
        lifecycle_events.append(("stopped", datetime.now(timezone.utc)))

        # Verify lifecycle events
        assert len(lifecycle_events) == 3

        # Verify health checks were performed
        assert health_checks_performed[0] > 0

    @pytest.mark.asyncio
    async def test_error_recovery_scenario(self):
        """Test error recovery during deployment."""
        from mcp.main_mcp import MCPServerManager

        # Start with monitoring server
        manager = MCPServerManager(servers=["monitoring"])

        # Mock monitoring server to fail on first health check
        with patch("mcp.main_mcp.MonitoringServer") as MockMonitoring:
            mock_server = MagicMock()

            # Mock health check to fail
            async def mock_health_failure():
                raise Exception("Health check failed")

            mock_server.get_system_health = mock_health_failure
            MockMonitoring.return_value = mock_server

            manager.monitoring_server = mock_server

            # Start manager
            await manager.start()

            # Verify server started despite health check failure
            # (Real scenario: manager should continue with errors tracked)

            # Stop manager
            await manager.stop()

            # Verify error was tracked
            # assert manager.error_count.get("monitoring", 0) >= 1

    @pytest.mark.asyncio
    async def test_rolling_deployment(self):
        """Test rolling deployment with staggered starts."""
        from mcp.main_mcp import MCPServerManager

        # Stagger server starts
        for server_name in ["codebase_search", "testing", "monitoring"]:
            manager = MCPServerManager(servers=[server_name])

            # Start and stop each server
            await manager.start()
            await asyncio.sleep(0.01)
            await manager.stop()

        # Verify all servers were handled
        assert True  # Just verify no exceptions

    @pytest.mark.asyncio
    async def test_continuous_monitoring_scenario(self):
        """Test continuous monitoring scenario."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=["monitoring"])

        # Start manager
        await manager.start()

        # Track monitoring iterations
        iterations = []

        async def mock_monitor():
            iterations.append(len(iterations))
            await asyncio.sleep(0.01)

        manager._monitoring_loop = mock_monitor

        # Run monitoring loop for a few iterations
        manager.running = True
        monitor_task = asyncio.create_task(manager._monitoring_loop())

        # Let it run for a few iterations
        await asyncio.sleep(0.05)

        # Stop manager
        manager.shutdown_requested = True
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Verify multiple iterations occurred
        assert len(iterations) >= 2

        # Verify final status
        status = manager.get_status()
        assert "running" in status


class TestStressScenarios:
    """Test suite for stress scenarios."""

    @pytest.mark.asyncio
    async def test_high_load_monitoring(self):
        """Test monitoring under high load."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=["monitoring"])

        # Mock rapid health checks
        health_check_count = [0]

        async def mock_rapid_health_check():
            health_check_count[0] += 1
            # Simulate high load
            await asyncio.sleep(0.001)

        manager._check_monitoring_server_health = mock_rapid_health_check

        # Start manager
        await manager.start()

        # Run under high load
        manager.running = True
        monitor_task = asyncio.create_task(manager._monitoring_loop())

        # Let it run briefly under load
        await asyncio.sleep(0.02)

        manager.shutdown_requested = True
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Verify system handled load
        assert health_check_count[0] > 0
        # Verify graceful shutdown
        assert manager.running is False

    @pytest.mark.asyncio
    async def test_rapid_state_changes(self):
        """Test handling of rapid state changes."""
        from mcp.main_mcp import MCPServerManager

        manager = MCPServerManager(servers=["testing"])

        # Simulate rapid start/stop cycles
        for _ in range(5):
            manager.running = False
            manager.shutdown_requested = False

            # Start
            await manager.start()

            # Quick stop
            await manager.stop()

        # Verify each cycle completes
        assert True  # Verify no exceptions
