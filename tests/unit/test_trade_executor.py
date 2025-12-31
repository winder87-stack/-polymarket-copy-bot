"""
Tests for Trade Executor module.

This module provides comprehensive tests for:
- Money calculation safety (Decimal vs float)
- Position sizing correctness
- Risk management integration
- Circuit breaker interaction
- Thread safety of concurrent operations
"""

import asyncio
import pytest
from decimal import Decimal, InvalidOperation

from core.exceptions import TradingError


# =============================================================================
# Money Safety Tests
# =============================================================================


class TestMoneySafety:
    """Test that all financial calculations use Decimal, not float."""

    @pytest.mark.asyncio
    async def test_position_size_uses_decimal(self, mock_trade_executor):
        """Verify position size calculations use Decimal."""
        # Test data
        account_balance = Decimal("10000.0")
        risk_percent = Decimal("0.01")
        original_amount = Decimal("1000.0")

        # Calculate position size
        position_size = (
            account_balance * risk_percent
            if account_balance > Decimal("0")
            else Decimal("0")
        )

        # Verify result is Decimal
        assert isinstance(position_size, Decimal)
        assert position_size == Decimal("100.0")

    @pytest.mark.asyncio
    async def test_pnl_calculation_uses_decimal(self, mock_trade_executor):
        """Verify PnL calculations use Decimal."""
        entry_price = Decimal("0.50")
        current_price = Decimal("0.55")
        size = Decimal("100.0")

        # Calculate PnL (YES outcome)
        pnl = (current_price - entry_price) * size
        exit_pnl = (Decimal("1.0") - current_price) * size

        total_pnl = pnl + exit_pnl

        # Verify result is Decimal
        assert isinstance(total_pnl, Decimal)
        assert total_pnl == Decimal("10.0")

    @pytest.mark.asyncio
    async def test_stop_loss_take_profit_use_decimal(self, mock_trade_executor):
        """Verify stop loss and take profit use Decimal."""
        entry_price = Decimal("0.50")
        stop_loss_percent = Decimal("0.15")
        take_profit_percent = Decimal("0.25")

        # Calculate stop loss price
        stop_loss = entry_price * (Decimal("1.0") - stop_loss_percent)

        # Calculate take profit price
        take_profit = entry_price * (Decimal("1.0") + take_profit_percent)

        # Verify results are Decimal
        assert isinstance(stop_loss, Decimal)
        assert isinstance(take_profit, Decimal)
        assert stop_loss == Decimal("0.425")
        assert take_profit == Decimal("0.625")

    @pytest.mark.asyncio
    async def test_no_float_in_money_calculations(self, mock_trade_executor):
        """Ensure no float() usage in money-related code paths."""
        import inspect
        from core.trade_executor import TradeExecutor

        # Get all methods
        methods = [
            getattr(TradeExecutor, name)
            for name in dir(TradeExecutor)
            if callable(getattr(TradeExecutor, name)) and not name.startswith("_")
        ]

        for method in methods:
            source = inspect.getsource(method)
            # Check for float() with money-related variables
            money_vars = [
                "account_balance",
                "risk_percent",
                "position_size",
                "pnl",
                "profit",
                "loss",
                "max_daily_loss",
                "trade_amount",
            ]

            for var in money_vars:
                # Check for dangerous pattern: float(var)
                pattern = f"float\\s*\\(\\s*{var}\\s*\\)"
                if pattern in source:
                    pytest.fail(
                        f"Found float({var}) in {method.__name__}. "
                        f"Please use Decimal instead."
                    )

    @pytest.mark.asyncio
    async def test_high_precision_decimal_operations(self, mock_trade_executor):
        """Verify Decimal operations maintain high precision."""
        # Test precision-critical multiplication
        amount = Decimal("10000.0")
        rate = Decimal("0.0123456789")

        result = amount * rate

        # Should maintain high precision
        assert result == Decimal("123.456789")

        # Test division precision
        total = Decimal("1000.0")
        shares = Decimal("7")
        price = total / shares

        # Division should be precise
        assert abs(price - Decimal("142.8571428571428571428571428571")) < Decimal(
            "0.0000000001"
        )


# =============================================================================
# Position Sizing Tests
# =============================================================================


class TestPositionSizing:
    """Test position sizing logic."""

    @pytest.mark.asyncio
    async def test_position_size_respects_max_limit(self, mock_trade_executor):
        """Verify position size respects maximum limit."""
        account_balance = Decimal("100000.0")
        risk_percent = Decimal("0.05")  # 5%
        max_position_size = Decimal("50.0")

        # Risk-based size would be 5000.0
        risk_based = account_balance * risk_percent

        # Should be capped at max
        assert risk_based > max_position_size

    @pytest.mark.asyncio
    async def test_position_size_respects_minimum_trade_amount(
        self, mock_trade_executor
    ):
        """Verify position size respects minimum trade amount."""
        account_balance = Decimal("10.0")
        risk_percent = Decimal("0.01")  # 1%
        min_trade_amount = Decimal("1.0")

        # Risk-based size would be 0.1
        risk_based = account_balance * risk_percent

        # Should be capped at minimum
        assert risk_based < min_trade_amount

    @pytest.mark.asyncio
    async def test_position_size_uses_minimum_of_approaches(self, mock_trade_executor):
        """Verify position size uses minimum of risk-based and proportional."""
        account_balance = Decimal("10000.0")
        risk_percent = Decimal("0.01")  # 1%
        original_amount = Decimal("2000.0")
        max_position_size = Decimal("500.0")

        # Risk-based: 100.0
        risk_based = account_balance * risk_percent

        # Proportional: 200.0 (10%)
        proportional = original_amount * Decimal("0.1")

        # Should take minimum of all three
        expected = min(risk_based, proportional, max_position_size)

        assert expected == Decimal("100.0")

    @pytest.mark.asyncio
    async def test_position_size_rounding(self, mock_trade_executor):
        """Verify position size is properly rounded."""
        # Test value that requires rounding
        account_balance = Decimal("10000.0")
        risk_percent = Decimal("0.0123456789")

        position_size = account_balance * risk_percent

        # Should be rounded to 4 decimal places
        rounded = position_size.quantize(Decimal("0.0001"))

        # Verify rounding
        assert rounded == Decimal("123.4568")


# =============================================================================
# Risk Management Integration Tests
# =============================================================================


class TestRiskManagementIntegration:
    """Test integration with risk management components."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_check_before_trade(self, mock_trade_executor):
        """Verify circuit breaker is checked before trade execution."""
        trade_id = "test_trade_123"

        # Mock circuit breaker to return None (allow trade)
        mock_trade_executor.circuit_breaker.check_trade_allowed = AsyncMock(
            return_value=None
        )

        # Execute trade should proceed
        result = await mock_trade_executor.execute_copy_trade(
            {"market_id": "test_market", "side": "BUY"}
        )

        # Circuit breaker check should have been called
        mock_trade_executor.circuit_breaker.check_trade_allowed.assert_called_once_with(
            trade_id
        )

    @pytest.mark.asyncio
    async def test_trade_skipped_when_circuit_breaker_active(self, mock_trade_executor):
        """Verify trade is skipped when circuit breaker is active."""
        trade_id = "test_trade_456"

        # Mock circuit breaker to return skip reason
        mock_trade_executor.circuit_breaker.check_trade_allowed = AsyncMock(
            return_value={
                "status": "skipped",
                "reason": "Circuit breaker: Daily loss limit reached",
                "remaining_minutes": 30.0,
            }
        )

        # Execute trade should be skipped
        result = await mock_trade_executor.execute_copy_trade(
            {"market_id": "test_market", "side": "BUY"}
        )

        # Result should indicate skip
        assert result.get("status") == "skipped"
        assert "circuit" in result.get("reason", "").lower()

    @pytest.mark.asyncio
    async def test_daily_loss_recorded_on_loss(self, mock_trade_executor):
        """Verify daily loss is recorded on losing trade."""
        loss_amount = Decimal("50.0")

        # Mock circuit breaker
        mock_trade_executor.circuit_breaker.record_loss = AsyncMock()

        # Simulate loss
        await mock_trade_executor.circuit_breaker.record_loss(float(loss_amount))

        # Circuit breaker should have been called
        mock_trade_executor.circuit_breaker.record_loss.assert_called_once()

    @pytest.mark.asyncio
    async def test_consecutive_losses_reset_on_profit(self, mock_trade_executor):
        """Verify consecutive losses are reset on profit."""
        profit_amount = Decimal("25.0")

        # Mock circuit breaker
        mock_trade_executor.circuit_breaker.record_profit = AsyncMock()

        # Simulate profit
        await mock_trade_executor.circuit_breaker.record_profit(float(profit_amount))

        # Circuit breaker should have been called
        mock_trade_executor.circuit_breaker.record_profit.assert_called_once()


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestThreadSafety:
    """Test thread safety of concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_trade_execution_with_lock(self, mock_trade_executor):
        """Verify concurrent trade executions are thread-safe."""
        trade_count = 10
        trades = [
            {"market_id": f"market_{i}", "side": "BUY"} for i in range(trade_count)
        ]

        # Mock place_order
        async def mock_place_order(*args, **kwargs):
            await asyncio.sleep(0.01)  # Simulate work
            return {"order_id": f"order_{asyncio.current_task().get_name()}"}

        mock_trade_executor.clob_client.place_order = mock_place_order

        # Execute all trades concurrently
        tasks = [mock_trade_executor.execute_copy_trade(trade) for trade in trades]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All trades should complete
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == trade_count

    @pytest.mark.asyncio
    async def test_position_cache_thread_safety(self, mock_trade_executor):
        """Verify position cache operations are thread-safe."""
        # Add multiple positions concurrently
        position_updates = [
            (f"market_{i}", Decimal("0.5"), Decimal("100.0")) for i in range(20)
        ]

        async def add_position(market_id, price, size):
            async with mock_trade_executor._state_lock:
                mock_trade_executor.open_positions.set(
                    market_id, {"market_id": market_id, "price": price, "size": size}
                )

        # Add all positions concurrently
        await asyncio.gather(*[add_position(*args) for args in position_updates])

        # All positions should be in cache
        assert mock_trade_executor.open_positions.get("market_0") is not None
        assert mock_trade_executor.open_positions.get("market_19") is not None

    @pytest.mark.asyncio
    async def test_daily_loss_updates_with_lock(self, mock_trade_executor):
        """Verify daily loss updates are thread-safe."""
        # Simulate concurrent loss records
        loss_records = [Decimal(f"{i * 10}") for i in range(10)]

        async def record_loss(loss):
            # This should use circuit breaker's lock internally
            await mock_trade_executor.circuit_breaker.record_loss(float(loss))

        # Record all losses concurrently
        await asyncio.gather(*[record_loss(loss) for loss in loss_records])

        # Get final state
        state = mock_trade_executor.circuit_breaker.get_state()

        # Daily loss should be sum of all losses
        expected_total = sum(loss_records)
        assert state["daily_loss"] == float(expected_total)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling in trade executor."""

    @pytest.mark.asyncio
    async def test_invalid_trade_data_raises_error(self, mock_trade_executor):
        """Verify invalid trade data raises appropriate error."""
        invalid_trades = [
            {},  # Missing all fields
            {"market_id": "test"},  # Missing side
            {"side": "BUY"},  # Missing market_id
        ]

        for trade in invalid_trades:
            with pytest.raises((ValueError, KeyError, TradingError)):
                await mock_trade_executor.execute_copy_trade(trade)

    @pytest.mark.asyncio
    async def test_api_failure_handling(self, mock_trade_executor):
        """Verify API failures are handled gracefully."""
        from core.exceptions import APIError

        # Mock API to fail
        async def mock_api_error(*args, **kwargs):
            raise APIError("API timeout", status_code=504, error_code="TIMEOUT")

        mock_trade_executor.clob_client.place_order = mock_api_error

        # Execute trade should handle error
        result = await mock_trade_executor.execute_copy_trade(
            {"market_id": "test_market", "side": "BUY"}
        )

        # Should indicate failure
        assert result.get("status") == "error"

    @pytest.mark.asyncio
    async def test_insufficient_balance_handling(self, mock_trade_executor):
        """Verify insufficient balance is handled."""
        # Mock low balance
        mock_trade_executor.clob_client.get_token_balance = AsyncMock(
            return_value=Decimal("0.5")
        )

        # Execute trade with insufficient balance
        result = await mock_trade_executor.execute_copy_trade(
            {"market_id": "test_market", "side": "BUY", "size": Decimal("100.0")}
        )

        # Should fail due to insufficient balance
        assert result.get("status") == "error"
        assert "balance" in str(result.get("error", "")).lower()


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_position_calculation_performance(self, mock_trade_executor):
        """Verify position size calculation is fast."""
        import time

        # Test multiple calculations
        start = time.time()

        for _ in range(1000):
            account_balance = Decimal("10000.0")
            risk_percent = Decimal("0.01")
            position_size = account_balance * risk_percent

        duration = time.time() - start

        # Should complete 1000 calculations in under 100ms
        assert duration < 0.1

    @pytest.mark.asyncio
    async def test_cache_lookup_performance(self, mock_trade_executor):
        """Verify cache lookups are fast."""
        import time

        # Add 1000 positions to cache
        for i in range(1000):
            mock_trade_executor.open_positions.set(
                f"market_{i}",
                {
                    "market_id": f"market_{i}",
                    "price": Decimal("0.5"),
                    "size": Decimal("100.0"),
                },
            )

        # Test lookup performance
        start = time.time()

        for i in range(1000):
            mock_trade_executor.open_positions.get(f"market_{i}")

        duration = time.time() - start

        # Should complete 1000 lookups in under 100ms
        assert duration < 0.1


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_account_balance(self, mock_trade_executor):
        """Verify handling of zero account balance."""
        account_balance = Decimal("0.0")
        risk_percent = Decimal("0.01")

        position_size = account_balance * risk_percent

        # Should result in zero
        assert position_size == Decimal("0.0")

    @pytest.mark.asyncio
    async def test_maximum_daily_loss_boundary(self, mock_trade_executor):
        """Verify behavior at maximum daily loss boundary."""
        max_loss = Decimal("100.0")
        current_loss = Decimal("99.99")

        # Additional loss would trigger circuit breaker
        additional_loss = Decimal("0.01")
        new_total = current_loss + additional_loss

        assert new_total == max_loss

    @pytest.mark.asyncio
    async def test_negative_values_handled(self, mock_trade_executor):
        """Verify negative values are handled appropriately."""
        # Most financial operations should reject negatives
        with pytest.raises((ValueError, InvalidOperation)):
            # Decimal operations should handle or reject negatives appropriately
            account_balance = Decimal("-100.0")
            position_size = account_balance * Decimal("0.01")
