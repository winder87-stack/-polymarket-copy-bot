"""
Comprehensive tests for circuit_breaker.py module

Tests cover:
- Atomic state transitions (no race conditions)
- Exception handling during market volatility
- Graceful degradation when circuit opens
- Daily loss reset at UTC midnight with persistence
- Telegram alerts with recovery ETA
- 5 consecutive losing trades triggering circuit break
- Market crash scenarios with rapid price movements
- Recovery procedures after circuit opens
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from core.circuit_breaker import CircuitBreaker


@pytest.fixture
def temp_state_file(tmp_path):
    """Create temporary state file for testing"""
    return tmp_path / "circuit_breaker_state.json"


@pytest.fixture
def circuit_breaker(temp_state_file):
    """Create circuit breaker instance for testing"""
    return CircuitBreaker(
        max_daily_loss=100.0,
        wallet_address="0x1234567890abcdef1234567890abcdef12345678",
        state_file=temp_state_file,
        cooldown_seconds=3600,
        alert_on_activation=False,  # Disable alerts for testing
    )


class TestCircuitBreakerActivation:
    """Test circuit breaker activation scenarios"""

    @pytest.mark.asyncio
    async def test_activate_on_daily_loss_limit(self, circuit_breaker):
        """Test circuit breaker activates when daily loss exceeds limit"""
        # Record losses up to limit
        await circuit_breaker.record_loss(50.0)
        await circuit_breaker.record_loss(50.0)  # Total: 100.0

        state = circuit_breaker.get_state()
        assert state["active"] is True
        assert "Daily loss limit reached" in state["reason"]
        assert state["daily_loss"] == 100.0

    @pytest.mark.asyncio
    async def test_activate_on_consecutive_losses(self, circuit_breaker):
        """Test circuit breaker activates on 5 consecutive losses"""
        # Record 5 consecutive losses
        for _ in range(5):
            await circuit_breaker.record_loss(10.0)

        state = circuit_breaker.get_state()
        assert state["active"] is True
        assert "consecutive losses" in state["reason"].lower()
        assert state["consecutive_losses"] == 5

    @pytest.mark.asyncio
    async def test_activate_on_high_failure_rate(self, circuit_breaker):
        """Test circuit breaker activates on high failure rate (50%+)"""
        # Record 10 trades with 6 failures (60% failure rate)
        for i in range(10):
            await circuit_breaker.record_trade_result(
                success=(i < 4)
            )  # 4 success, 6 failures

        state = circuit_breaker.get_state()
        assert state["active"] is True
        assert "High failure rate" in state["reason"]
        assert state["failed_trades"] == 6
        assert state["total_trades"] == 10

    @pytest.mark.asyncio
    async def test_no_activation_when_conditions_not_met(self, circuit_breaker):
        """Test circuit breaker doesn't activate when conditions not met"""
        # Record small losses
        await circuit_breaker.record_loss(30.0)
        await circuit_breaker.record_loss(20.0)  # Total: 50.0, below 100.0 limit

        # Record some successful trades
        for _ in range(5):
            await circuit_breaker.record_trade_result(success=True)

        state = circuit_breaker.get_state()
        assert state["active"] is False
        assert state["daily_loss"] == 50.0

    @pytest.mark.asyncio
    async def test_profit_resets_consecutive_losses(self, circuit_breaker):
        """Test that recording profit resets consecutive losses counter"""
        # Record 3 losses
        await circuit_breaker.record_loss(10.0)
        await circuit_breaker.record_loss(10.0)
        await circuit_breaker.record_loss(10.0)

        assert circuit_breaker.get_state()["consecutive_losses"] == 3

        # Record profit
        await circuit_breaker.record_profit(20.0)

        # Consecutive losses should be reset
        assert circuit_breaker.get_state()["consecutive_losses"] == 0


class TestCircuitBreakerTradeBlocking:
    """Test that circuit breaker properly blocks trades"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_trade_when_active(self, circuit_breaker):
        """Test circuit breaker blocks trade execution when active"""
        # Activate circuit breaker
        await circuit_breaker.record_loss(100.0)

        # Try to execute trade
        result = await circuit_breaker.check_trade_allowed("test_trade_123")

        assert result is not None
        assert result["status"] == "skipped"
        assert "Circuit breaker" in result["reason"]
        assert result["trade_id"] == "test_trade_123"
        assert "remaining_minutes" in result
        assert "recovery_eta" in result

    @pytest.mark.asyncio
    async def test_circuit_breaker_allows_trade_when_inactive(self, circuit_breaker):
        """Test trades proceed when circuit breaker is inactive"""
        result = await circuit_breaker.check_trade_allowed("test_trade_123")

        assert result is None  # None means proceed with trade

    @pytest.mark.asyncio
    async def test_recovery_eta_calculation(self, circuit_breaker):
        """Test recovery ETA calculation"""
        # Activate circuit breaker
        await circuit_breaker.record_loss(100.0)

        state = circuit_breaker.get_state()
        assert state["recovery_eta"] != "N/A"
        assert "minutes" in state["recovery_eta"] or "h" in state["recovery_eta"]


class TestDailyLossReset:
    """Test daily loss reset at UTC midnight"""

    @pytest.mark.asyncio
    async def test_daily_loss_resets_at_midnight_utc(self, circuit_breaker):
        """Test daily loss resets when crossing midnight UTC"""
        # Record some losses
        await circuit_breaker.record_loss(50.0)
        assert circuit_breaker.get_state()["daily_loss"] == 50.0

        # Simulate crossing midnight UTC
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        circuit_breaker._state.last_reset_date = yesterday

        # Check and reset
        await circuit_breaker._check_and_reset_daily_loss()

        # Daily loss should be reset
        assert circuit_breaker.get_state()["daily_loss"] == 0.0
        assert circuit_breaker.get_state()["consecutive_losses"] == 0

    @pytest.mark.asyncio
    async def test_daily_loss_persists_same_day(self, circuit_breaker):
        """Test daily loss persists within the same day"""
        # Record losses
        await circuit_breaker.record_loss(30.0)
        await circuit_breaker.record_loss(20.0)

        # Check (should not reset)
        await circuit_breaker._check_and_reset_daily_loss()

        # Daily loss should still be 50.0
        assert circuit_breaker.get_state()["daily_loss"] == 50.0

    @pytest.mark.asyncio
    async def test_daily_loss_reset_persistence(self, temp_state_file):
        """Test that daily loss reset persists across restarts"""
        # Create circuit breaker and record losses
        cb1 = CircuitBreaker(
            max_daily_loss=100.0,
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
            state_file=temp_state_file,
            alert_on_activation=False,
        )
        await cb1.record_loss(75.0)
        assert cb1.get_state()["daily_loss"] == 75.0

        # Simulate crossing midnight
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        cb1._state.last_reset_date = yesterday

        # Create new instance (simulating restart)
        cb2 = CircuitBreaker(
            max_daily_loss=100.0,
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
            state_file=temp_state_file,
            alert_on_activation=False,
        )

        # Daily loss should be reset
        assert cb2.get_state()["daily_loss"] == 0.0


class TestConsecutiveLosses:
    """Test 5 consecutive losing trades triggering circuit break"""

    @pytest.mark.asyncio
    async def test_five_consecutive_losses_triggers_circuit(self, circuit_breaker):
        """Test that exactly 5 consecutive losses trigger circuit breaker"""
        # Record 4 losses (should not trigger)
        for i in range(4):
            await circuit_breaker.record_loss(10.0)
            assert circuit_breaker.get_state()["active"] is False

        # Record 5th loss (should trigger)
        await circuit_breaker.record_loss(10.0)
        assert circuit_breaker.get_state()["active"] is True
        assert circuit_breaker.get_state()["consecutive_losses"] == 5

    @pytest.mark.asyncio
    async def test_profit_interrupts_consecutive_losses(self, circuit_breaker):
        """Test that profit interrupts consecutive loss count"""
        # Record 3 losses
        for _ in range(3):
            await circuit_breaker.record_loss(10.0)

        # Record profit (should reset counter)
        await circuit_breaker.record_profit(20.0)
        assert circuit_breaker.get_state()["consecutive_losses"] == 0

        # Record 4 more losses (total 4, not 7)
        for _ in range(4):
            await circuit_breaker.record_loss(10.0)

        # Should not trigger (only 4 consecutive)
        assert circuit_breaker.get_state()["active"] is False


class TestMarketCrashScenarios:
    """Test market crash scenarios with rapid price movements"""

    @pytest.mark.asyncio
    async def test_rapid_losses_during_market_crash(self, circuit_breaker):
        """Test rapid losses during market crash scenario"""
        # Simulate rapid losses
        losses = [20.0, 15.0, 25.0, 30.0, 10.0]  # Total: 100.0

        for loss in losses:
            await circuit_breaker.record_loss(loss)
            # Small delay to simulate real-world timing
            await asyncio.sleep(0.01)

        # Circuit breaker should activate
        state = circuit_breaker.get_state()
        assert state["active"] is True
        assert state["daily_loss"] == 100.0

    @pytest.mark.asyncio
    async def test_concurrent_loss_recording(self, circuit_breaker):
        """Test concurrent loss recording (race condition test)"""
        # Record losses concurrently
        tasks = [circuit_breaker.record_loss(10.0) for _ in range(10)]
        await asyncio.gather(*tasks)

        # Daily loss should be exactly 100.0 (no race conditions)
        state = circuit_breaker.get_state()
        assert state["daily_loss"] == 100.0
        assert state["active"] is True

    @pytest.mark.asyncio
    async def test_exception_handling_during_volatility(self, circuit_breaker):
        """Test exception handling during market volatility"""
        # Simulate exception during loss recording
        with patch.object(
            circuit_breaker, "_save_state", side_effect=Exception("IO Error")
        ):
            # Should not crash, but log error
            await circuit_breaker.record_loss(50.0)

        # State should still be updated (graceful degradation)
        assert circuit_breaker.get_state()["daily_loss"] == 50.0


class TestRecoveryProcedures:
    """Test recovery procedures after circuit opens"""

    @pytest.mark.asyncio
    async def test_auto_reset_after_cooldown(self, circuit_breaker):
        """Test circuit breaker auto-resets after cooldown period"""
        # Activate circuit breaker
        await circuit_breaker.record_loss(100.0)
        assert circuit_breaker.get_state()["active"] is True

        # Simulate cooldown period elapsed
        circuit_breaker._state.activation_time = time.time() - 3700  # 61+ minutes ago

        # Periodic check should reset
        await circuit_breaker.periodic_check()

        assert circuit_breaker.get_state()["active"] is False

    @pytest.mark.asyncio
    async def test_manual_reset(self, circuit_breaker):
        """Test manual circuit breaker reset"""
        # Activate circuit breaker
        await circuit_breaker.record_loss(100.0)
        assert circuit_breaker.get_state()["active"] is True

        # Manually reset
        await circuit_breaker.reset("Manual reset for testing")

        assert circuit_breaker.get_state()["active"] is False
        assert circuit_breaker.get_state()["reason"] == ""

    @pytest.mark.asyncio
    async def test_reset_preserves_daily_loss(self, circuit_breaker):
        """Test that reset doesn't clear daily loss (only resets circuit breaker)"""
        # Record losses and activate
        await circuit_breaker.record_loss(100.0)
        assert circuit_breaker.get_state()["daily_loss"] == 100.0

        # Reset circuit breaker
        await circuit_breaker.reset()

        # Daily loss should still be 100.0
        assert circuit_breaker.get_state()["daily_loss"] == 100.0
        assert circuit_breaker.get_state()["active"] is False


class TestStatePersistence:
    """Test state persistence across restarts"""

    @pytest.mark.asyncio
    async def test_state_persistence(self, temp_state_file):
        """Test that circuit breaker state persists across restarts"""
        # Create first instance and activate
        cb1 = CircuitBreaker(
            max_daily_loss=100.0,
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
            state_file=temp_state_file,
            alert_on_activation=False,
        )
        await cb1.record_loss(75.0)
        await cb1.record_loss(25.0)  # Activate circuit breaker

        state1 = cb1.get_state()
        assert state1["active"] is True
        assert state1["daily_loss"] == 100.0

        # Create second instance (simulating restart)
        cb2 = CircuitBreaker(
            max_daily_loss=100.0,
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
            state_file=temp_state_file,
            alert_on_activation=False,
        )

        state2 = cb2.get_state()
        assert state2["active"] == state1["active"]
        assert state2["daily_loss"] == state1["daily_loss"]
        assert state2["reason"] == state1["reason"]


class TestTelegramAlerts:
    """Test Telegram alerts on circuit activation"""

    @pytest.mark.asyncio
    async def test_telegram_alert_on_activation(self, temp_state_file):
        """Test that Telegram alert is sent on circuit breaker activation"""
        with patch("core.circuit_breaker.send_telegram_alert") as mock_alert:
            cb = CircuitBreaker(
                max_daily_loss=100.0,
                wallet_address="0x1234567890abcdef1234567890abcdef12345678",
                state_file=temp_state_file,
                alert_on_activation=True,
            )

            # Activate circuit breaker
            await cb.record_loss(100.0)

            # Verify alert was sent
            assert mock_alert.called
            alert_message = mock_alert.call_args[0][0]
            assert "CIRCUIT BREAKER ACTIVATED" in alert_message
            assert "Recovery ETA" in alert_message
            assert "Daily Loss" in alert_message

    @pytest.mark.asyncio
    async def test_alert_includes_recovery_eta(self, temp_state_file):
        """Test that alert includes recovery ETA"""
        with patch("core.circuit_breaker.send_telegram_alert") as mock_alert:
            cb = CircuitBreaker(
                max_daily_loss=100.0,
                wallet_address="0x1234567890abcdef1234567890abcdef12345678",
                state_file=temp_state_file,
                alert_on_activation=True,
            )

            await cb.record_loss(100.0)

            alert_message = mock_alert.call_args[0][0]
            assert "Recovery ETA" in alert_message
            assert "minutes" in alert_message or "h" in alert_message


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_zero_daily_loss_limit(self, temp_state_file):
        """Test circuit breaker with zero daily loss limit"""
        cb = CircuitBreaker(
            max_daily_loss=0.0,
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
            state_file=temp_state_file,
            alert_on_activation=False,
        )

        # Any loss should trigger
        await cb.record_loss(0.01)
        assert cb.get_state()["active"] is True

    @pytest.mark.asyncio
    async def test_negative_loss_amount(self, circuit_breaker):
        """Test that negative loss amounts are handled correctly"""
        # Record "negative" loss (should be treated as positive)
        await circuit_breaker.record_loss(-50.0)

        # Should still record as positive loss
        assert circuit_breaker.get_state()["daily_loss"] == 50.0

    @pytest.mark.asyncio
    async def test_concurrent_trade_checks(self, circuit_breaker):
        """Test concurrent trade checks (race condition test)"""
        # Activate circuit breaker
        await circuit_breaker.record_loss(100.0)

        # Concurrent trade checks
        tasks = [circuit_breaker.check_trade_allowed(f"trade_{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should be blocked
        assert all(result is not None for result in results)
        assert all(result["status"] == "skipped" for result in results)

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_exception(self, circuit_breaker):
        """Test graceful degradation when exception occurs"""
        # Simulate exception during check
        with patch.object(
            circuit_breaker,
            "_check_and_reset_daily_loss",
            side_effect=Exception("Error"),
        ):
            # Should not crash, should allow trade (fail-open)
            result = await circuit_breaker.check_trade_allowed("test_trade")
            assert result is None  # Fail-open: allow trade

    @pytest.mark.asyncio
    async def test_state_file_corruption_handling(self, temp_state_file):
        """Test handling of corrupted state file"""
        # Write corrupted JSON
        with open(temp_state_file, "w") as f:
            f.write("invalid json{")

        # Should load default state without crashing
        cb = CircuitBreaker(
            max_daily_loss=100.0,
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
            state_file=temp_state_file,
            alert_on_activation=False,
        )

        # Should have default state
        assert cb.get_state()["active"] is False
        assert cb.get_state()["daily_loss"] == 0.0


class TestAtomicStateTransitions:
    """Test atomic state transitions (no race conditions)"""

    @pytest.mark.asyncio
    async def test_atomic_activation(self, circuit_breaker):
        """Test that activation is atomic"""
        # Concurrent activations
        tasks = [circuit_breaker.record_loss(100.0) for _ in range(5)]
        await asyncio.gather(*tasks)

        # Should only activate once
        state = circuit_breaker.get_state()
        assert state["active"] is True
        # Daily loss should be exactly 500.0 (no race conditions)
        assert state["daily_loss"] == 500.0

    @pytest.mark.asyncio
    async def test_atomic_reset(self, circuit_breaker):
        """Test that reset is atomic"""
        # Activate
        await circuit_breaker.record_loss(100.0)

        # Concurrent resets
        tasks = [circuit_breaker.reset() for _ in range(5)]
        await asyncio.gather(*tasks)

        # Should be reset (not double-reset)
        assert circuit_breaker.get_state()["active"] is False

    @pytest.mark.asyncio
    async def test_atomic_loss_recording(self, circuit_breaker):
        """Test that loss recording is atomic"""
        # Record losses concurrently
        tasks = [circuit_breaker.record_loss(1.0) for _ in range(100)]
        await asyncio.gather(*tasks)

        # Total should be exactly 100.0
        assert circuit_breaker.get_state()["daily_loss"] == 100.0


class TestIntegrationWithPositionManager:
    """Test integration with position manager scenarios"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_position_closures(self, circuit_breaker):
        """Test circuit breaker behavior when positions are closed at loss"""
        # Simulate closing positions at loss
        position_losses = [20.0, 15.0, 25.0, 30.0, 10.0]

        for loss in position_losses:
            await circuit_breaker.record_loss(loss)

        # Circuit breaker should activate
        assert circuit_breaker.get_state()["active"] is True

        # Try to execute new trade (should be blocked)
        result = await circuit_breaker.check_trade_allowed("new_trade")
        assert result is not None
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset_allows_new_trades(self, circuit_breaker):
        """Test that resetting circuit breaker allows new trades"""
        # Activate
        await circuit_breaker.record_loss(100.0)
        assert circuit_breaker.get_state()["active"] is True

        # Reset
        await circuit_breaker.reset()

        # New trades should be allowed
        result = await circuit_breaker.check_trade_allowed("new_trade")
        assert result is None
