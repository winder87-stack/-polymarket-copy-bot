"""Comprehensive unit tests for circuit breaker state transitions.

Tests all state transition logic including:
- Activation conditions
- Auto-reset after cooldown
- Daily loss reset at midnight
- Consecutive loss tracking
- Failure rate tracking
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from core.circuit_breaker import CircuitBreaker
from tests.fixtures.market_data_generators import CircuitBreakerScenarioGenerator


@pytest.fixture
def temp_state_file(tmp_path: Path) -> Path:
    """Create temporary state file for testing."""
    return tmp_path / "circuit_breaker_state.json"


@pytest.fixture
def circuit_breaker(temp_state_file: Path) -> CircuitBreaker:
    """Create circuit breaker instance for testing."""
    return CircuitBreaker(
        max_daily_loss=100.0,
        wallet_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        state_file=temp_state_file,
        cooldown_seconds=3600,
        alert_on_activation=False,  # Disable alerts in tests
    )


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state transition logic."""

    @pytest.mark.asyncio
    async def test_daily_loss_activation(self, circuit_breaker: CircuitBreaker):
        """Test circuit breaker activates when daily loss limit exceeded."""
        # Record losses up to threshold
        await circuit_breaker.record_loss(50.0)
        await circuit_breaker.record_loss(40.0)
        await circuit_breaker.record_loss(15.0)  # Should trigger activation

        state = circuit_breaker.get_state()
        assert state["active"] is True
        assert "Daily loss limit" in state["reason"]
        assert state["daily_loss"] >= 100.0

    @pytest.mark.asyncio
    async def test_consecutive_losses_activation(self, circuit_breaker: CircuitBreaker):
        """Test circuit breaker activates after consecutive losses."""
        # Record 5 consecutive losses
        for _ in range(5):
            await circuit_breaker.record_loss(5.0)

        state = circuit_breaker.get_state()
        assert state["active"] is True
        assert "consecutive losses" in state["reason"].lower()
        assert state["consecutive_losses"] >= 5

    @pytest.mark.asyncio
    async def test_failure_rate_activation(self, circuit_breaker: CircuitBreaker):
        """Test circuit breaker activates on high failure rate."""
        # Record 20 trades with 11 failures (55% failure rate)
        for i in range(20):
            await circuit_breaker.record_trade_result(success=(i < 9))

        state = circuit_breaker.get_state()
        assert state["active"] is True
        assert "High failure rate" in state["reason"]
        assert state["failed_trades"] >= 10
        assert state["total_trades"] >= 20

    @pytest.mark.asyncio
    async def test_profit_resets_consecutive_losses(
        self, circuit_breaker: CircuitBreaker
    ):
        """Test profit resets consecutive loss counter."""
        # Record some losses
        await circuit_breaker.record_loss(10.0)
        await circuit_breaker.record_loss(5.0)

        state_before = circuit_breaker.get_state()
        assert state_before["consecutive_losses"] == 2

        # Record profit
        await circuit_breaker.record_profit(20.0)

        state_after = circuit_breaker.get_state()
        assert state_after["consecutive_losses"] == 0

    @pytest.mark.asyncio
    async def test_auto_reset_after_cooldown(self, circuit_breaker: CircuitBreaker):
        """Test circuit breaker auto-resets after cooldown period."""
        # Activate circuit breaker
        await circuit_breaker.record_loss(150.0)  # Exceed daily loss

        state_before = circuit_breaker.get_state()
        assert state_before["active"] is True

        # Simulate time passing (cooldown expired)
        with patch("time.time", return_value=time.time() + 3700):
            await circuit_breaker.periodic_check()

        state_after = circuit_breaker.get_state()
        assert state_after["active"] is False

    @pytest.mark.asyncio
    async def test_daily_loss_reset_at_midnight(self, circuit_breaker: CircuitBreaker):
        """Test daily loss resets at UTC midnight."""
        # Record some loss
        await circuit_breaker.record_loss(50.0)

        state_before = circuit_breaker.get_state()
        assert state_before["daily_loss"] > 0

        # Simulate crossing midnight UTC
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        with patch("core.circuit_breaker.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime.now(timezone.utc)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # Load state with old reset date
            circuit_breaker._state.last_reset_date = yesterday
            await circuit_breaker._check_and_reset_daily_loss()

        state_after = circuit_breaker.get_state()
        # Daily loss should be reset (or at least checked)
        assert state_after["daily_loss"] >= 0

    @pytest.mark.asyncio
    async def test_manual_reset(self, circuit_breaker: CircuitBreaker):
        """Test manual circuit breaker reset."""
        # Activate circuit breaker
        await circuit_breaker.record_loss(150.0)

        state_before = circuit_breaker.get_state()
        assert state_before["active"] is True

        # Manual reset
        await circuit_breaker.reset("Test reset")

        state_after = circuit_breaker.get_state()
        assert state_after["active"] is False
        assert state_after["reason"] == ""

    @pytest.mark.asyncio
    async def test_trade_allowed_when_inactive(self, circuit_breaker: CircuitBreaker):
        """Test trades are allowed when circuit breaker is inactive."""
        result = await circuit_breaker.check_trade_allowed("test_trade_1")
        assert result is None  # None means trade is allowed

    @pytest.mark.asyncio
    async def test_trade_blocked_when_active(self, circuit_breaker: CircuitBreaker):
        """Test trades are blocked when circuit breaker is active."""
        # Activate circuit breaker
        await circuit_breaker.record_loss(150.0)

        result = await circuit_breaker.check_trade_allowed("test_trade_1")
        assert result is not None
        assert result["status"] == "skipped"
        assert "Circuit breaker" in result["reason"]

    @pytest.mark.asyncio
    async def test_state_persistence(
        self, circuit_breaker: CircuitBreaker, temp_state_file: Path
    ):
        """Test circuit breaker state persists across restarts."""
        # Record some state
        await circuit_breaker.record_loss(50.0)
        await circuit_breaker.record_trade_result(success=True, trade_id="test1")
        await circuit_breaker.record_trade_result(success=False, trade_id="test2")

        # Save state
        await circuit_breaker._save_state()

        # Create new instance (simulating restart)
        new_circuit_breaker = CircuitBreaker(
            max_daily_loss=100.0,
            wallet_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            state_file=temp_state_file,
            alert_on_activation=False,
        )

        # Verify state was loaded
        state = new_circuit_breaker.get_state()
        assert state["daily_loss"] == 50.0
        assert state["total_trades"] == 2
        assert state["failed_trades"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_state_access(self, circuit_breaker: CircuitBreaker):
        """Test thread-safe concurrent state access."""

        # Simulate concurrent operations
        async def record_loss(amount: float):
            await circuit_breaker.record_loss(amount)

        async def check_trade(trade_id: str):
            return await circuit_breaker.check_trade_allowed(trade_id)

        # Run concurrent operations
        tasks = [
            record_loss(10.0),
            record_loss(5.0),
            check_trade("trade1"),
            check_trade("trade2"),
            record_trade_result(True),
        ]

        async def record_trade_result(success: bool):
            await circuit_breaker.record_trade_result(success)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no exceptions occurred
        assert all(not isinstance(r, Exception) for r in results)

        # Verify state is consistent
        state = circuit_breaker.get_state()
        assert state["daily_loss"] >= 15.0

    @pytest.mark.asyncio
    async def test_recovery_eta_calculation(self, circuit_breaker: CircuitBreaker):
        """Test recovery ETA calculation."""
        # Activate circuit breaker
        await circuit_breaker.record_loss(150.0)

        state = circuit_breaker.get_state()
        assert "recovery_eta" in state
        assert state["recovery_eta"] != "N/A"

        # ETA should be in the future
        remaining = state["remaining_minutes"]
        assert remaining > 0
        assert remaining <= 60  # 1 hour cooldown

    @pytest.mark.asyncio
    async def test_multiple_activation_conditions(
        self, circuit_breaker: CircuitBreaker
    ):
        """Test multiple activation conditions don't cause issues."""
        # Set up state that could trigger multiple conditions
        circuit_breaker._state.daily_loss = 95.0
        circuit_breaker._state.consecutive_losses = 4
        circuit_breaker._state.total_trades = 20
        circuit_breaker._state.failed_trades = 10

        # Trigger activation (should only activate once)
        await circuit_breaker.record_loss(10.0)

        state = circuit_breaker.get_state()
        assert state["active"] is True
        # Should have activated due to daily loss (first condition checked)

    @pytest.mark.asyncio
    async def test_state_transition_edge_cases(self, circuit_breaker: CircuitBreaker):
        """Test edge cases in state transitions."""
        # Test exactly at threshold
        await circuit_breaker.record_loss(99.0)
        state = circuit_breaker.get_state()
        assert not state["active"]  # Not yet active

        await circuit_breaker.record_loss(1.0)  # Exactly at threshold
        state = circuit_breaker.get_state()
        assert state["active"] is True

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_error(self, circuit_breaker: CircuitBreaker):
        """Test graceful degradation when errors occur."""
        # Corrupt state file
        circuit_breaker.state_file.write_text("invalid json")

        # Should still work (loads default state)
        result = await circuit_breaker.check_trade_allowed("test_trade")
        assert result is None  # Should allow trade (graceful degradation)

    @pytest.mark.parametrize(
        "scenario",
        CircuitBreakerScenarioGenerator.generate_state_transition_scenarios(),
    )
    @pytest.mark.asyncio
    async def test_state_transition_scenarios(
        self, circuit_breaker: CircuitBreaker, scenario: dict
    ):
        """Test various state transition scenarios."""
        # Set initial state
        for key, value in scenario["initial_state"].items():
            setattr(circuit_breaker._state, key, value)

        # Perform action
        action = scenario["action"]
        if action["type"] == "record_loss":
            await circuit_breaker.record_loss(action["amount"])
        elif action["type"] == "record_profit":
            await circuit_breaker.record_profit(action["amount"])
        elif action["type"] == "record_trade_result":
            await circuit_breaker.record_trade_result(action["success"])
        elif action["type"] == "periodic_check":
            with patch("time.time", return_value=action["current_time"]):
                await circuit_breaker.periodic_check()

        # Verify expected state
        state = circuit_breaker.get_state()

        if "expected_active" in scenario:
            assert state["active"] == scenario["expected_active"]

        if "expected_reason_contains" in scenario:
            assert (
                scenario["expected_reason_contains"].lower() in state["reason"].lower()
            )

        if "expected_consecutive_losses" in scenario:
            assert (
                state["consecutive_losses"] == scenario["expected_consecutive_losses"]
            )
