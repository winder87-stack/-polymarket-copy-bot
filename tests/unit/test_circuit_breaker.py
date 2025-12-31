"""
Unit tests for circuit breaker logic in trade_executor.py

Tests cover:
- Circuit breaker activation and deactivation logic
- Daily loss limit activation
- High failure rate triggering
- Cooldown period handling
- Proper logging and alerting
- Edge cases and race conditions
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from config.settings import Settings
from core.trade_executor import TradeExecutor


@pytest.fixture
def mock_clob_client():
    """Create a mock CLOB client for testing"""
    mock_client = MagicMock()
    mock_client.wallet_address = "0x1234567890abcdef1234567890abcdef12345678"
    return mock_client


@pytest.fixture
def trade_executor(mock_clob_client):
    """Setup trade executor with mocked dependencies"""
    executor = TradeExecutor(mock_clob_client)
    executor.settings = Settings()
    # Override settings for testing
    executor.settings.risk.max_daily_loss = 100.0
    executor.settings.risk.max_position_size = 50.0
    return executor


class TestCircuitBreakerActivation:
    """Test circuit breaker activation scenarios"""

    def test_activate_circuit_breaker_on_daily_loss_limit(self, trade_executor):
        """Test circuit breaker activates when daily loss exceeds limit"""
        # Setup
        trade_executor.daily_loss = 150.0  # Exceeds 100.0 limit

        # Execute
        trade_executor._check_circuit_breaker_conditions()

        # Verify
        assert trade_executor.circuit_breaker_active
        assert "Daily loss limit reached" in trade_executor.circuit_breaker_reason
        assert trade_executor.circuit_breaker_time is not None

    def test_activate_circuit_breaker_on_high_failure_rate(self, trade_executor):
        """Test circuit breaker activates on high failure rate"""
        # Setup
        trade_executor.total_trades = 20
        trade_executor.failed_trades = 12  # 60% failure rate

        # Execute
        trade_executor._check_circuit_breaker_conditions()

        # Verify
        assert trade_executor.circuit_breaker_active
        assert "High failure rate" in trade_executor.circuit_breaker_reason

    def test_no_activation_when_conditions_not_met(self, trade_executor):
        """Test circuit breaker doesn't activate when conditions not met"""
        # Setup
        trade_executor.daily_loss = 50.0  # Below limit
        trade_executor.total_trades = 10
        trade_executor.failed_trades = 2  # 20% failure rate

        # Execute
        trade_executor._check_circuit_breaker_conditions()

        # Verify
        assert not trade_executor.circuit_breaker_active

    def test_activate_circuit_breaker_sets_timestamp(self, trade_executor):
        """Test circuit breaker activation sets proper timestamp"""
        start_time = time.time()

        # Execute
        trade_executor.activate_circuit_breaker("Test reason")

        # Verify
        assert trade_executor.circuit_breaker_active
        assert trade_executor.circuit_breaker_reason == "Test reason"
        assert trade_executor.circuit_breaker_time >= start_time
        assert trade_executor.circuit_breaker_time <= time.time()

    def test_activate_circuit_breaker_logs_critical(self, trade_executor, caplog):
        """Test circuit breaker activation logs critical message"""
        with caplog.at_level("CRITICAL"):
            trade_executor.activate_circuit_breaker("Test activation")

        assert "CIRCUIT BREAKER ACTIVATED" in caplog.text
        assert "Test activation" in caplog.text

    @patch("core.trade_executor.send_telegram_alert")
    def test_activate_circuit_breaker_sends_alert(self, mock_alert, trade_executor):
        """Test circuit breaker activation sends telegram alert"""
        trade_executor.activate_circuit_breaker("Test reason")

        # Verify alert was called
        mock_alert.assert_called_once()
        alert_text = mock_alert.call_args[0][0]
        assert "CIRCUIT BREAKER ACTIVATED" in alert_text
        assert "Test reason" in alert_text


class TestCircuitBreakerDeactivation:
    """Test circuit breaker deactivation and cooldown logic"""

    def test_reset_circuit_breaker(self, trade_executor):
        """Test circuit breaker can be manually reset"""
        # Setup
        trade_executor.activate_circuit_breaker("Test reason")

        # Execute
        trade_executor.reset_circuit_breaker()

        # Verify
        assert not trade_executor.circuit_breaker_active
        assert trade_executor.circuit_breaker_reason == ""
        assert trade_executor.circuit_breaker_time is None

    def test_circuit_breaker_auto_reset_after_cooldown(self, trade_executor):
        """Test circuit breaker automatically resets after cooldown period"""
        # Setup
        trade_executor.activate_circuit_breaker("Test reason")
        # Simulate cooldown period (61 minutes ago)
        trade_executor.circuit_breaker_time = time.time() - 3660

        # Execute
        trade_executor._check_circuit_breaker_conditions()

        # Verify
        assert not trade_executor.circuit_breaker_active

    def test_circuit_breaker_no_reset_during_cooldown(self, trade_executor):
        """Test circuit breaker doesn't reset during cooldown period"""
        # Setup
        trade_executor.activate_circuit_breaker("Test reason")
        # Simulate still in cooldown (30 minutes ago)
        trade_executor.circuit_breaker_time = time.time() - 1800

        # Execute
        trade_executor._check_circuit_breaker_conditions()

        # Verify
        assert trade_executor.circuit_breaker_active

    def test_circuit_breaker_reset_logs_info(self, trade_executor, caplog):
        """Test circuit breaker reset logs info message"""
        trade_executor.activate_circuit_breaker("Original reason")

        with caplog.at_level("INFO"):
            trade_executor.reset_circuit_breaker()

        assert "Circuit breaker reset" in caplog.text
        assert "Original reason" in caplog.text


class TestCircuitBreakerTradeBlocking:
    """Test that circuit breaker properly blocks trades"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_trade_execution(self, trade_executor):
        """Test circuit breaker blocks trade execution"""
        # Setup
        trade_executor.activate_circuit_breaker("Test blocking")

        # Execute
        result = await trade_executor._check_circuit_breaker_for_trade("test_trade_123")

        # Verify
        assert result is not None
        assert result["status"] == "skipped"
        assert "Circuit breaker" in result["reason"]
        assert result["trade_id"] == "test_trade_123"

    @pytest.mark.asyncio
    async def test_circuit_breaker_allows_trades_when_inactive(self, trade_executor):
        """Test trades proceed when circuit breaker is inactive"""
        # Setup
        trade_executor.circuit_breaker_active = False

        # Execute
        result = await trade_executor._check_circuit_breaker_for_trade("test_trade_123")

        # Verify
        assert result is None  # None means proceed with trade

    @pytest.mark.asyncio
    async def test_circuit_breaker_remaining_time_calculation(self, trade_executor):
        """Test remaining time calculation for circuit breaker"""
        # Setup
        trade_executor.activate_circuit_breaker("Test time")
        trade_executor.circuit_breaker_time = time.time() - 1800  # 30 minutes ago

        # Execute
        remaining_minutes = trade_executor._get_circuit_breaker_remaining_time()

        # Verify (3600 seconds = 60 minutes, minus 30 minutes elapsed = 30 minutes remaining)
        assert 25 <= remaining_minutes <= 35  # Allow some tolerance for test timing

    def test_circuit_breaker_remaining_time_when_inactive(self, trade_executor):
        """Test remaining time returns 0 when circuit breaker inactive"""
        # Setup
        trade_executor.circuit_breaker_active = False

        # Execute
        remaining_minutes = trade_executor._get_circuit_breaker_remaining_time()

        # Verify
        assert remaining_minutes == 0.0

    def test_circuit_breaker_remaining_time_edge_case(self, trade_executor):
        """Test remaining time calculation edge case"""
        # Setup
        trade_executor.activate_circuit_breaker("Test edge")
        # Set time far in the past to ensure cooldown expired
        trade_executor.circuit_breaker_time = time.time() - 7200  # 2 hours ago

        # Execute
        remaining_minutes = trade_executor._get_circuit_breaker_remaining_time()

        # Verify (should be 0 since cooldown expired)
        assert remaining_minutes == 0.0


class TestCircuitBreakerErrorHandling:
    """Test circuit breaker error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_handles_time_calculation_errors(
        self, trade_executor
    ):
        """Test circuit breaker handles errors in time calculations gracefully"""
        # Setup
        trade_executor.activate_circuit_breaker("Test errors")
        # Set invalid time to trigger error
        trade_executor.circuit_breaker_time = "invalid_time"

        # Execute - should not crash
        result = await trade_executor._check_circuit_breaker_for_trade("test_trade")

        # Verify - should continue with trade despite error
        assert result is None

    def test_circuit_breaker_activation_handles_none_time(self, trade_executor):
        """Test circuit breaker activation handles edge cases"""
        # Setup
        trade_executor.circuit_breaker_time = None

        # Execute multiple activations
        trade_executor.activate_circuit_breaker("First")
        first_time = trade_executor.circuit_breaker_time

        trade_executor.activate_circuit_breaker("Second")
        second_time = trade_executor.circuit_breaker_time

        # Verify second activation doesn't change time
        assert first_time == second_time

    def test_circuit_breaker_state_persistence(self, trade_executor):
        """Test circuit breaker state persists across operations"""
        # Setup
        trade_executor.activate_circuit_breaker("Persistence test")

        # Execute multiple checks
        for _ in range(3):
            trade_executor._check_circuit_breaker_conditions()
            assert trade_executor.circuit_breaker_active

        # Reset and verify
        trade_executor.reset_circuit_breaker()
        assert not trade_executor.circuit_breaker_active


class TestCircuitBreakerConcurrency:
    """Test circuit breaker behavior under concurrent operations"""

    @pytest.mark.asyncio
    async def test_concurrent_circuit_breaker_checks(self, trade_executor):
        """Test circuit breaker handles concurrent checks properly"""
        # Setup
        trade_executor.activate_circuit_breaker("Concurrency test")

        # Execute multiple concurrent checks
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                trade_executor._check_circuit_breaker_for_trade(f"trade_{i}")
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all returned blocked results
        assert all(result is not None for result in results)
        assert all(result["status"] == "skipped" for result in results)
        assert all("Circuit breaker" in result["reason"] for result in results)

    @pytest.mark.asyncio
    async def test_concurrent_activation_and_checks(self, trade_executor):
        """Test concurrent activation and trade checks"""

        async def activate_and_check(index):
            # Some tasks activate circuit breaker
            if index % 3 == 0:
                trade_executor.activate_circuit_breaker(f"Activation {index}")
            # All tasks check circuit breaker
            return await trade_executor._check_circuit_breaker_for_trade(
                f"trade_{index}"
            )

        # Execute concurrent operations
        tasks = [activate_and_check(i) for i in range(15)]
        results = await asyncio.gather(*tasks)

        # Verify circuit breaker was activated and all trades blocked
        assert trade_executor.circuit_breaker_active
        # Most results should be blocked (some might slip through before activation)
        blocked_count = sum(
            1 for r in results if r is not None and r["status"] == "skipped"
        )
        assert blocked_count > 10  # At least most trades should be blocked


class TestCircuitBreakerEdgeCases:
    """Test circuit breaker edge cases and boundary conditions"""

    def test_circuit_breaker_zero_loss_limit(self, trade_executor):
        """Test circuit breaker with zero loss limit"""
        trade_executor.settings.risk.max_daily_loss = 0.0
        trade_executor.daily_loss = 0.01  # Any loss should trigger

        trade_executor._check_circuit_breaker_conditions()
        assert trade_executor.circuit_breaker_active

    def test_circuit_breaker_extreme_failure_rate(self, trade_executor):
        """Test circuit breaker with extreme failure rates"""
        trade_executor.total_trades = 10
        trade_executor.failed_trades = 10  # 100% failure rate

        trade_executor._check_circuit_breaker_conditions()
        assert trade_executor.circuit_breaker_active
        assert "High failure rate" in trade_executor.circuit_breaker_reason

    def test_circuit_breaker_boundary_failure_rate(self, trade_executor):
        """Test circuit breaker at boundary failure rate (49%)"""
        trade_executor.total_trades = 100
        trade_executor.failed_trades = 49  # 49% failure rate (below threshold)

        trade_executor._check_circuit_breaker_conditions()
        assert not trade_executor.circuit_breaker_active

    def test_circuit_breaker_just_over_failure_threshold(self, trade_executor):
        """Test circuit breaker just over failure threshold (51%)"""
        trade_executor.total_trades = 100
        trade_executor.failed_trades = 51  # 51% failure rate

        trade_executor._check_circuit_breaker_conditions()
        assert trade_executor.circuit_breaker_active

    def test_circuit_breaker_loss_boundary(self, trade_executor):
        """Test circuit breaker at exact loss limit boundary"""
        trade_executor.daily_loss = 100.0  # Exactly at limit

        trade_executor._check_circuit_breaker_conditions()
        assert trade_executor.circuit_breaker_active

    def test_circuit_breaker_loss_just_under_limit(self, trade_executor):
        """Test circuit breaker just under loss limit"""
        trade_executor.daily_loss = 99.99  # Just under limit

        trade_executor._check_circuit_breaker_conditions()
        assert not trade_executor.circuit_breaker_active

    def test_circuit_breaker_negative_loss_values(self, trade_executor):
        """Test circuit breaker with negative loss values"""
        trade_executor.daily_loss = -100.0  # Negative (profits)

        trade_executor._check_circuit_breaker_conditions()
        assert not trade_executor.circuit_breaker_active

    def test_circuit_breaker_zero_trades(self, trade_executor):
        """Test circuit breaker with zero total trades"""
        trade_executor.total_trades = 0
        trade_executor.failed_trades = 0

        trade_executor._check_circuit_breaker_conditions()
        # Should not activate due to division by zero issues
        assert not trade_executor.circuit_breaker_active

    def test_circuit_breaker_extreme_time_values(self, trade_executor):
        """Test circuit breaker with extreme time values"""
        # Test with activation time far in the past
        trade_executor.activate_circuit_breaker("Test")
        trade_executor.circuit_breaker_time = 0  # Epoch time

        remaining = trade_executor._get_circuit_breaker_remaining_time()
        assert remaining == 0.0  # Should be expired

    def test_circuit_breaker_concurrent_activations(self, trade_executor):
        """Test multiple concurrent circuit breaker activations"""
        # Activate multiple times rapidly
        for i in range(5):
            trade_executor.activate_circuit_breaker(f"Activation {i}")

        # Should only have one active circuit breaker
        assert trade_executor.circuit_breaker_active

        # Reset should work
        trade_executor.reset_circuit_breaker()
        assert not trade_executor.circuit_breaker_active

    def test_circuit_breaker_state_after_reset_and_reactivation(self, trade_executor):
        """Test circuit breaker state after reset and immediate reactivation"""
        # Initial activation
        trade_executor.activate_circuit_breaker("First")
        assert trade_executor.circuit_breaker_active
        first_time = trade_executor.circuit_breaker_time

        # Reset
        trade_executor.reset_circuit_breaker()
        assert not trade_executor.circuit_breaker_active

        # Immediate reactivation
        trade_executor.activate_circuit_breaker("Second")
        assert trade_executor.circuit_breaker_active
        second_time = trade_executor.circuit_breaker_time

        # Should have new timestamp
        assert second_time > first_time

    def test_circuit_breaker_reason_persistence(self, trade_executor):
        """Test that circuit breaker reason persists correctly"""
        original_reason = "Original activation reason"
        trade_executor.activate_circuit_breaker(original_reason)

        # Reason should persist
        assert trade_executor.circuit_breaker_reason == original_reason

        # Multiple activations should update reason
        new_reason = "Updated activation reason"
        trade_executor.activate_circuit_breaker(new_reason)
        assert trade_executor.circuit_breaker_reason == new_reason

    def test_circuit_breaker_with_none_settings(self, trade_executor):
        """Test circuit breaker when settings are None"""
        trade_executor.settings = None

        # Should handle gracefully without crashing
        trade_executor._check_circuit_breaker_conditions()
        # Should not activate since settings are None
        assert not trade_executor.circuit_breaker_active
