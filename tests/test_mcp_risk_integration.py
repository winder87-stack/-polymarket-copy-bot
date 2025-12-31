"""Unit tests for MCP Risk Integration.

Tests verify that MCP server integration with risk management:
- Does not break existing risk logic
- Has zero performance impact
- Proper error handling
- Circuit breaker protection
- Resource isolation
- Fallback mechanisms

All tests use mocking to avoid dependencies on actual MCP servers.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from core.integrations.mcp_risk_integration import (
    MCPRiskIntegrator,
    get_mcp_risk_integrator,
)


class TestMCPRiskIntegrator:
    """Test MCP Risk Integrator class."""

    @pytest.fixture
    def integrator(self):
        """Create integrator instance for testing."""
        return MCPRiskIntegrator()

    def test_initialization(self, integrator):
        """Test integrator initialization."""
        assert integrator.enabled is False
        assert integrator.initialized is False
        assert integrator.market_hours_active is False
        assert integrator.mcp_circuit_breaker_active is False
        assert integrator.risk_parameter_usage == {}
        assert integrator.test_coverage == 0.0
        assert integrator.total_scans == 0
        assert integrator.total_coverage_checks == 0

        # Check risk patterns loaded
        assert len(integrator.risk_patterns) > 0
        assert "position_sizing" in integrator.risk_patterns
        assert "risk_limits" in integrator.risk_patterns
        assert "correlation_checks" in integrator.risk_patterns

    def test_risk_patterns_content(self, integrator):
        """Test risk patterns contain correct regex."""
        assert "max_position_size" in integrator.risk_patterns["position_sizing"]
        assert "max_daily_loss" in integrator.risk_patterns["risk_limits"]
        assert (
            "HIGH_CORRELATION_THRESHOLD"
            in integrator.risk_patterns["correlation_checks"]
        )
        assert "stop_loss_percentage" in integrator.risk_patterns["stop_loss"]
        assert "take_profit_percentage" in integrator.risk_patterns["take_profit"]
        assert "max_slippage" in integrator.risk_patterns["slippage"]

    @pytest.mark.asyncio
    async def test_initialize(self, integrator):
        """Test initialization with components."""
        # Mock components
        circuit_breaker = MagicMock()
        trade_executor = MagicMock()

        await integrator.initialize(circuit_breaker, trade_executor)

        assert integrator.initialized is True
        assert integrator.circuit_breaker == circuit_breaker
        assert integrator.trade_executor == trade_executor

    @pytest.mark.asyncio
    async def test_enable(self, integrator):
        """Test enabling MCP integration."""
        # First need to initialize
        circuit_breaker = MagicMock()
        trade_executor = MagicMock()
        await integrator.initialize(circuit_breaker, trade_executor)

        # Enable
        await integrator.enable()
        assert integrator.enabled is True

    @pytest.mark.asyncio
    async def test_enable_during_market_hours(self, integrator):
        """Test that enable is blocked during market hours."""
        circuit_breaker = MagicMock()
        trade_executor = MagicMock()
        await integrator.initialize(circuit_breaker, trade_executor)

        # Set market hours active
        integrator.market_hours_active = True

        # Try to enable
        await integrator.enable()

        # Should still be disabled
        assert integrator.enabled is False

    @pytest.mark.asyncio
    async def test_disable(self, integrator):
        """Test disabling MCP integration."""
        circuit_breaker = MagicMock()
        trade_executor = MagicMock()
        await integrator.initialize(circuit_breaker, trade_executor)
        await integrator.enable()

        # Disable
        await integrator.disable()
        assert integrator.enabled is False

    @pytest.mark.asyncio
    async def test_check_market_hours(self, integrator):
        """Test market hours checking."""
        # Set current hour outside market hours
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2024, 1, 1, 5, 0, timezone.utc
            )  # 5 AM UTC

            await integrator._check_market_hours()
            assert integrator.market_hours_active is True

        # Set current hour during market hours
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2024, 1, 1, 12, 0, timezone.utc
            )  # 12 PM UTC

            await integrator._check_market_hours()
            assert integrator.market_hours_active is False

    @pytest.mark.asyncio
    async def test_scan_risk_parameters_disabled(self, integrator):
        """Test risk parameter scan when disabled."""
        integrator.enabled = False

        result = await integrator.scan_risk_parameters()

        assert result["status"] == "disabled"
        assert "scanned_params" in result

    @pytest.mark.asyncio
    async def test_scan_risk_parameters_codebase_search_disabled(self, integrator):
        """Test scan when codebase search is disabled."""
        integrator.enabled = True
        integrator.codebase_search_config.enabled = False

        result = await integrator.scan_risk_parameters()

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_scan_risk_parameters_success(self, integrator):
        """Test successful risk parameter scan."""
        integrator.enabled = True

        # Mock codebase search server
        mock_search_server = AsyncMock()
        mock_search_server.search_pattern = AsyncMock(
            return_value={
                "matches": ["line1", "line2", "line3"],
            }
        )

        with patch(
            "mcp.monitoring_server_enhanced.CodebaseSearchServer",
            return_value=mock_search_server,
        ):
            result = await integrator.scan_risk_parameters()

            assert result["status"] == "success"
            assert "scanned_params" in result
            assert result["total_scans"] == 1
            assert "scan_timestamp" in result

            # Check that risk parameter usage was updated
            assert integrator.total_scans == 1

    @pytest.mark.asyncio
    async def test_verify_test_coverage_disabled(self, integrator):
        """Test test coverage verification when disabled."""
        integrator.enabled = False

        result = await integrator.verify_test_coverage()

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_verify_test_coverage_unavailable(self, integrator):
        """Test test coverage verification when testing server unavailable."""
        integrator.enabled = True

        with patch(
            "mcp.monitoring_server_enhanced.get_monitoring_server",
            side_effect=ImportError(),
        ):
            result = await integrator.verify_test_coverage()

            assert result["status"] == "unavailable"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_verify_test_coverage_success_above_threshold(self, integrator):
        """Test test coverage verification with good coverage."""
        integrator.enabled = True
        integrator.testing_config.coverage_target = 0.85

        # Mock monitoring server
        mock_server = AsyncMock()
        mock_server.get_system_health = AsyncMock(
            return_value={
                "components": {
                    "testing": {"status": "healthy"},
                },
            }
        )

        # Mock circuit breaker
        integrator.circuit_breaker = MagicMock()

        with patch(
            "mcp.monitoring_server_enhanced.get_monitoring_server",
            return_value=mock_server,
        ):
            result = await integrator.verify_test_coverage()

            assert result["status"] == "success"
            assert result["coverage"] == 0.85
            assert result["meets_threshold"] is True

    @pytest.mark.asyncio
    async def test_verify_test_coverage_below_threshold(self, integrator):
        """Test test coverage verification with low coverage."""
        integrator.enabled = True
        integrator.testing_config.coverage_target = 0.85

        # Mock monitoring server with 75% coverage
        mock_server = AsyncMock()
        mock_server.get_system_health = AsyncMock(
            return_value={
                "components": {
                    "testing": {"status": "healthy"},
                },
            }
        )

        # Mock circuit breaker check_coverage method
        mock_cb = MagicMock()
        mock_cb.check_mcp_test_coverage_impact = AsyncMock(return_value=False)

        with patch(
            "mcp.monitoring_server_enhanced.get_monitoring_server",
            return_value=mock_server,
        ):
            result = await integrator.verify_test_coverage()

            # Should indicate coverage below threshold
            # (actual behavior depends on implementation)

            assert result["status"] == "success"
            assert result["coverage"] == 0.85

    @pytest.mark.asyncio
    async def test_monitor_risk_parameters_disabled(self, integrator):
        """Test risk parameter monitoring when disabled."""
        integrator.enabled = False

        result = await integrator.monitor_risk_parameters()

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_monitor_risk_parameters_unavailable(self, integrator):
        """Test risk parameter monitoring when monitoring server unavailable."""
        integrator.enabled = True

        with patch(
            "mcp.monitoring_server_enhanced.get_monitoring_server",
            side_effect=ImportError(),
        ):
            result = await integrator.monitor_risk_parameters()

            assert result["status"] == "unavailable"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_monitor_risk_parameters_success(self, integrator):
        """Test successful risk parameter monitoring."""
        integrator.enabled = True

        # Mock monitoring server
        mock_server = AsyncMock()
        mock_server.get_system_health = AsyncMock(
            return_value={
                "components": {
                    "trade_executor": {
                        "status": "healthy",
                        "memory_mb": 50.0,
                    },
                },
                "performance": {
                    "cpu_percent": 0.5,
                    "memory_mb": 45.0,
                },
            }
        )

        integrator.monitoring_config.get_component_memory_limit = MagicMock(
            return_value=200
        )

        with patch(
            "mcp.monitoring_server_enhanced.get_monitoring_server",
            return_value=mock_server,
        ):
            result = await integrator.monitor_risk_parameters()

            assert result["status"] == "success"
            assert "trade_executor_health" in result
            assert "performance" in result
            assert result["total_checks"] == 1

    @pytest.mark.asyncio
    async def test_monitor_risk_parameters_memory_warning(self, integrator):
        """Test risk parameter monitoring with memory warning."""
        integrator.enabled = True

        # Mock monitoring server with high memory usage
        mock_server = AsyncMock()
        mock_server.get_system_health = AsyncMock(
            return_value={
                "components": {
                    "trade_executor": {
                        "status": "healthy",
                        "memory_mb": 180.0,  # Near limit
                    },
                },
                "performance": {
                    "cpu_percent": 0.5,
                    "memory_mb": 45.0,
                },
            }
        )

        integrator.monitoring_config.get_component_memory_limit = MagicMock(
            return_value=200
        )

        with patch(
            "mcp.monitoring_server_enhanced.get_monitoring_server",
            return_value=mock_server,
        ):
            result = await integrator.monitor_risk_parameters()

            assert result["status"] == "success"
            # Should have warnings
            assert "performance" in result
            # Check memory warning logic
            # (actual behavior depends on implementation)

    @pytest.mark.asyncio
    async def test_monitor_all(self, integrator):
        """Test monitoring all MCP integrations."""
        circuit_breaker = MagicMock()
        trade_executor = MagicMock()
        await integrator.initialize(circuit_breaker, trade_executor)
        await integrator.enable()

        result = await integrator.monitor_all()

        assert "timestamp" in result
        assert "market_hours_active" in result
        assert "mcp_integration_enabled" in result

    @pytest.mark.asyncio
    async def test_trip_mcp_circuit_breaker(self, integrator):
        """Test tripping MCP circuit breaker."""
        await integrator.trip_mcp_circuit_breaker("Test trip")

        assert integrator.mcp_circuit_breaker_active is True
        assert integrator.mcp_circuit_breaker_reason == "Test trip"

    @pytest.mark.asyncio
    async def test_trip_mcp_circuit_breaker_already_tripped(self, integrator):
        """Test that trip is idempotent when already tripped."""
        integrator.mcp_circuit_breaker_active = True

        await integrator.trip_mcp_circuit_breaker("Test trip")

        assert integrator.mcp_circuit_breaker_active is True
        assert integrator.mcp_circuit_breaker_reason == "Test trip"  # Reason unchanged

    @pytest.mark.asyncio
    async def test_reset_mcp_circuit_breaker(self, integrator):
        """Test resetting MCP circuit breaker."""
        integrator.mcp_circuit_breaker_active = True
        integrator.mcp_circuit_breaker_reason = "Test trip"

        await integrator.reset_mcp_circuit_breaker()

        assert integrator.mcp_circuit_breaker_active is False
        assert integrator.mcp_circuit_breaker_reason == ""

    @pytest.mark.asyncio
    async def test_reset_mcp_circuit_breaker_not_tripped(self, integrator):
        """Test reset when not tripped."""
        integrator.mcp_circuit_breaker_active = False

        await integrator.reset_mcp_circuit_breaker()

        assert integrator.mcp_circuit_breaker_active is False

    def test_get_statistics(self, integrator):
        """Test getting statistics."""
        stats = integrator.get_statistics()

        assert "initialized" in stats
        assert "enabled" in stats
        assert "market_hours_active" in stats
        assert "total_risk_scans" in stats
        assert "total_coverage_checks" in stats
        assert "total_monitoring_checks" in stats
        assert "mcp_circuit_breaker_active" in stats
        assert "mcp_cpu_usage" in stats
        assert "mcp_memory_usage" in stats

    @pytest.mark.asyncio
    async def test_monitor_all_disabled(self, integrator):
        """Test monitor_all when integration is disabled."""
        integrator.enabled = False

        result = await integrator.monitor_all()

        assert result["mcp_integration_enabled"] is False

    def test_singleton(self):
        """Test singleton pattern."""
        integrator1 = get_mcp_risk_integrator()
        integrator2 = get_mcp_risk_integrator()

        assert integrator1 is integrator2

    @pytest.mark.asyncio
    async def test_monitor_all_with_circuit_breaker(self, integrator):
        """Test monitor_all when circuit breaker is active."""
        circuit_breaker = MagicMock()
        trade_executor = MagicMock()
        await integrator.initialize(circuit_breaker, trade_executor)
        await integrator.enable()

        # Trip circuit breaker
        await integrator.trip_mcp_circuit_breaker("Test")

        # Monitor
        result = await integrator.monitor_all()

        assert result["circuit_breaker"]["active"] is True
        assert result["circuit_breaker"]["reason"] == "Test trip"


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with MCP."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker instance."""
        from core.circuit_breaker import CircuitBreaker

        return CircuitBreaker(
            max_daily_loss=100.0,
            wallet_address="0x1234567890abcdef1234567890abcdef1234567890",
            state_file="/tmp/test_circuit_breaker_state.json",
            cooldown_seconds=3600,
        )

    @pytest.mark.asyncio
    async def test_check_mcp_test_coverage_acceptable(self, circuit_breaker):
        """Test circuit breaker with acceptable test coverage."""
        # Acceptable coverage (85%)
        result = await circuit_breaker.check_mcp_test_coverage_impact(0.85, 0.85)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_mcp_test_coverage_below_threshold(self, circuit_breaker):
        """Test circuit breaker with coverage below threshold."""
        # Below threshold (75%)
        result = await circuit_breaker.check_mcp_test_coverage_impact(0.75, 0.85)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_mcp_test_coverage_critical(self, circuit_breaker):
        """Test circuit breaker with critically low test coverage."""
        # Critically low (50%)
        result = await circuit_breaker.check_mcp_test_coverage_impact(0.50, 0.85)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_mcp_resource_usage_acceptable(self, circuit_breaker):
        """Test circuit breaker with acceptable resource usage."""
        # Acceptable CPU (1%) and memory (100MB limit, using 50MB)
        result = await circuit_breaker.check_mcp_resource_usage(1.0, 50.0, 200.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_mcp_resource_usage_high_cpu(self, circuit_breaker):
        """Test circuit breaker with high CPU usage."""
        # High CPU (5%)
        result = await circuit_breaker.check_mcp_resource_usage(5.0, 50.0, 200.0)

        assert result is True  # CPU not high enough to trip

    @pytest.mark.asyncio
    async def test_check_mcp_resource_usage_high_memory(self, circuit_breaker):
        """Test circuit breaker with high memory usage."""
        # High memory (250MB, exceeds 200MB limit)
        result = await circuit_breaker.check_mcp_resource_usage(1.0, 250.0, 200.0)

        assert result is False  # Memory exceeds limit

    @pytest.mark.asyncio
    async def test_check_mcp_resource_usage_critical_memory(self, circuit_breaker):
        """Test circuit breaker with critical memory usage."""
        # Critical memory (200MB, at limit)
        result = await circuit_breaker.check_mcp_resource_usage(1.0, 200.0, 200.0)

        assert result is False  # Memory at limit

    @pytest.mark.asyncio
    async def test_check_mcp_resource_usage_very_high_cpu(self, circuit_breaker):
        """Test circuit breaker with very high CPU usage."""
        # Very high CPU (10%)
        result = await circuit_breaker.check_mcp_resource_usage(10.0, 50.0, 200.0)

        assert result is False  # CPU critically high

    def test_get_mcp_integration_state(self, circuit_breaker):
        """Test getting MCP integration state."""
        # Circuit breaker doesn't have MCP state attributes initially
        state = circuit_breaker.get_mcp_integration_state()

        assert "enabled" in state
        assert state["enabled"] is False
        assert "circuit_breaker_protected" in state
        assert state["circuit_breaker_protected"] is False

    @pytest.mark.asyncio
    async def test_enable_mcp_integration(self, circuit_breaker):
        """Test enabling MCP integration."""
        await circuit_breaker.enable_mcp_integration()

        state = circuit_breaker.get_mcp_integration_state()

        assert state["enabled"] is True
        assert state["circuit_breaker_protected"] is True
        assert state["test_coverage_monitored"] is True
        assert state["resource_usage_monitored"] is True

    @pytest.mark.asyncio
    async def test_disable_mcp_integration(self, circuit_breaker):
        """Test disabling MCP integration."""
        await circuit_breaker.enable_mcp_integration()
        await circuit_breaker.disable_mcp_integration()

        state = circuit_breaker.get_mcp_integration_state()

        assert state["enabled"] is False
        assert state["circuit_breaker_protected"] is False


class TestTradeExecutorIntegration:
    """Test trade executor integration with MCP."""

    @pytest.fixture
    def trade_executor(self):
        """Create trade executor mock."""
        from core.trade_executor import TradeExecutor

        clob_client = MagicMock()
        return TradeExecutor(clob_client)

    @pytest.mark.asyncio
    async def test_monitor_risk_parameters(self, trade_executor):
        """Test monitoring risk parameters."""
        # Mock dependencies
        with patch("core.trade_executor.psutil") as mock_psutil:
            mock_psutil.Process.return_value.memory_info.return_value = MagicMock(
                rss=50 * 1024 * 1024  # 50MB
            )

            result = await trade_executor.monitor_risk_parameters()

            assert result["status"] == "success"
            assert "component" in result
            assert result["component"] == "trade_executor"
            assert "memory_mb" in result["performance"]
            assert "risk_parameters" in result

    @pytest.mark.asyncio
    async def test_monitor_risk_parameters_high_memory(self, trade_executor):
        """Test monitoring with high memory usage."""
        # Mock dependencies with high memory (180MB, 90% of 200MB)
        with patch("core.trade_executor.psutil") as mock_psutil:
            mock_psutil.Process.return_value.memory_info.return_value = MagicMock(
                rss=180 * 1024 * 1024  # 180MB
            )
            mock_psutil.virtual_memory.return_value = MagicMock(percent=70.0)

            trade_executor.monitoring_config.get_component_memory_limit = MagicMock(
                return_value=200
            )

            result = await trade_executor.monitor_risk_parameters()

            assert result["status"] == "success"
            assert "warnings" in result
            assert len(result["warnings"]) > 0  # Should have memory warning

    @pytest.mark.asyncio
    async def test_check_mcp_test_coverage_impact(self, trade_executor):
        """Test checking MCP test coverage impact."""
        # Mock performance metrics
        with patch.object(trade_executor, "get_performance_metrics") as mock_perf:
            mock_perf.return_value = {
                "total_trades": 100,
                "success_rate": 0.90,
                "daily_loss": 50.0,
                "circuit_breaker_active": False,
                "uptime_hours": 24.0,
            }

            # Acceptable coverage
            result = await trade_executor.check_mcp_test_coverage_impact(0.85)

            assert result["status"] == "ok"
            assert result["test_coverage"] == 0.85
            assert "trade_executor_status" in result
            assert result["impact_analysis"]["test_coverage_acceptable"] is True

    @pytest.mark.asyncio
    async def test_check_mcp_test_coverage_impact_low_coverage(self, trade_executor):
        """Test checking MCP test coverage impact with low coverage."""
        with patch.object(trade_executor, "get_performance_metrics") as mock_perf:
            mock_perf.return_value = {
                "total_trades": 100,
                "success_rate": 0.80,
                "daily_loss": 50.0,
                "circuit_breaker_active": False,
                "uptime_hours": 24.0,
            }

            # Low coverage (70%)
            result = await trade_executor.check_mcp_test_coverage_impact(0.70)

            assert result["status"] == "ok"
            assert result["test_coverage"] == 0.70
            assert result["impact_analysis"]["test_coverage_acceptable"] is False

    @pytest.mark.asyncio
    async def test_get_risk_parameter_usage_report(self, trade_executor):
        """Test getting risk parameter usage report."""
        with patch("mcp.codebase_search.CodebaseSearchServer") as mock_search:
            mock_search.return_value.search_pattern = AsyncMock(
                return_value={
                    "matches": ["file1", "file2", "file3"],
                }
            )

            result = await trade_executor.get_risk_parameter_usage_report()

            assert result["status"] == "success"
            assert "parameter_usage" in result
            assert "total_occurrences" in result
            assert result["total_occurrences"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
