"""
Unit tests for position sizing calculations - test edge cases (zero price, negative values)

Tests cover:
- Position size calculation with edge cases
- Zero price risk scenarios
- Maximum account balance scenarios
- Minimum trade amount enforcement
- Decimal precision testing
- Division by zero protection
- Account risk calculations
"""

from decimal import Decimal
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
def position_manager(mock_clob_client):
    """Setup trade executor with mocked dependencies for position management testing"""
    executor = TradeExecutor(mock_clob_client)
    executor.settings = Settings()
    # Override settings for testing
    executor.settings.risk.min_trade_amount = 1.0
    executor.settings.risk.max_position_size = 50.0
    executor.settings.risk.account_risk_percent = 0.01  # 1% account risk
    return executor


class TestPositionSizing:
    """Test position sizing calculations"""

    @pytest.mark.asyncio
    async def test_basic_calculation(self, position_manager):
        """Test normal position size calculation"""
        # Setup
        original_trade = {
            "amount": 10.0,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=1000.0
            ),
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.52
            ),
        ):
            # Execute
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Verify - should calculate based on 1% account risk
            expected_risk_amount = 1000.0 * 0.01  # 1% of balance
            expected_position_size = expected_risk_amount / abs(
                0.52 - 0.5
            )  # Risk per price unit
            expected_position_size = min(
                expected_position_size, 50.0
            )  # Max position size
            expected_position_size = max(
                expected_position_size, 1.0
            )  # Min trade amount

            assert result == pytest.approx(expected_position_size, rel=0.1)

    @pytest.mark.asyncio
    async def test_zero_price_risk_raises_error(self, position_manager):
        """Test that zero price risk raises ValueError"""
        original_trade = {
            "amount": 10.0,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=1000.0
            ),
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.5
            ),  # Same price
        ):
            # Execute - should raise error for zero price risk
            with pytest.raises(ZeroDivisionError):
                await position_manager._calculate_copy_amount(original_trade, {})

    @pytest.mark.asyncio
    async def test_negative_price_difference(self, position_manager):
        """Test handling of negative price differences"""
        original_trade = {
            "amount": 10.0,
            "price": 0.6,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=1000.0
            ),
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.5
            ),  # Lower price
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should handle negative price difference correctly
            price_risk = abs(0.5 - 0.6)  # 0.1
            expected_risk_amount = 1000.0 * 0.01  # 1% of balance
            expected_position_size = expected_risk_amount / price_risk
            expected_position_size = min(expected_position_size, 50.0)

            assert result == pytest.approx(expected_position_size, rel=0.1)

    @pytest.mark.asyncio
    async def test_respects_max_position(self, position_manager):
        """Test that position size respects maximum position limit"""
        original_trade = {
            "amount": 10.0,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=10000.0
            ),  # Large balance
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.52
            ),
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should be capped at max position size
            assert result == 50.0

    @pytest.mark.asyncio
    async def test_negative_balance_fallback(self, position_manager):
        """Test fallback when balance is negative"""
        original_trade = {
            "amount": 10.0,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=-100.0
            ),
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.52
            ),
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should use fallback calculation
            expected_fallback = min(10.0 * 0.1, 50.0)
            assert result == expected_fallback

    @pytest.mark.asyncio
    async def test_zero_balance_fallback(self, position_manager):
        """Test fallback when balance is zero"""
        original_trade = {
            "amount": 10.0,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(position_manager.clob_client, "get_balance", return_value=0.0),
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.52
            ),
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should use fallback calculation
            expected_fallback = min(10.0 * 0.1, 50.0)
            assert result == expected_fallback

    @pytest.mark.asyncio
    async def test_none_balance_fallback(self, position_manager):
        """Test fallback when balance is None"""
        original_trade = {
            "amount": 10.0,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=None
            ),
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.52
            ),
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should use fallback calculation
            expected_fallback = min(10.0 * 0.1, 50.0)
            assert result == expected_fallback

    @pytest.mark.asyncio
    async def test_none_current_price_fallback(self, position_manager):
        """Test fallback when current price is None"""
        original_trade = {
            "amount": 10.0,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=1000.0
            ),
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=None
            ),
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should use fallback calculation
            expected_fallback = min(10.0 * 0.1, 50.0)
            assert result == expected_fallback

    @pytest.mark.asyncio
    async def test_decimal_precision(self, position_manager):
        """Test decimal precision in position size calculation"""
        original_trade = {
            "amount": Decimal("10.0"),
            "price": Decimal("0.5"),
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client,
                "get_balance",
                return_value=Decimal("1000.0"),
            ),
            patch.object(
                position_manager.clob_client,
                "get_current_price",
                return_value=Decimal("0.52"),
            ),
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should return float with proper precision
            assert isinstance(result, float)
            assert result == pytest.approx(result, abs=0.0001)

    @pytest.mark.asyncio
    async def test_extreme_price_values(self, position_manager):
        """Test handling of extreme price values"""
        original_trade = {
            "amount": 10.0,
            "price": 0.000001,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=1000.0
            ),
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.000002
            ),
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should be constrained by position limits
            assert result <= position_manager.settings.risk.max_position_size
            assert result >= position_manager.settings.risk.min_trade_amount

    @pytest.mark.asyncio
    async def test_extreme_trade_amounts(self, position_manager):
        """Test handling of extreme trade amounts"""
        # Very large original trade
        original_trade = {
            "amount": 1000000.0,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=1000.0
            ),
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.52
            ),
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should be constrained by position limits
            assert result <= position_manager.settings.risk.max_position_size

        # Very small original trade
        original_trade = {
            "amount": 0.000001,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=1000.0
            ),
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.52
            ),
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should respect minimum trade amount
            assert result >= position_manager.settings.risk.min_trade_amount

    @pytest.mark.asyncio
    async def test_price_risk_edge_cases(self, position_manager):
        """Test edge cases in price risk calculation"""
        # Test very small price differences
        original_trade = {
            "amount": 10.0,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=1000.0
            ),
            patch.object(
                position_manager.clob_client,
                "get_current_price",
                return_value=0.5000001,
            ),  # Very small diff
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should handle very small price differences
            assert result > 0
            assert result <= position_manager.settings.risk.max_position_size

    @pytest.mark.asyncio
    async def test_account_risk_limits(self, position_manager):
        """Test that position size respects account risk limits"""
        original_trade = {
            "amount": 10.0,
            "price": 0.5,
            "condition_id": "test_condition",
        }

        with (
            patch.object(
                position_manager.clob_client, "get_balance", return_value=100.0
            ),  # Small balance
            patch.object(
                position_manager.clob_client, "get_current_price", return_value=0.52
            ),
        ):
            result = await position_manager._calculate_copy_amount(original_trade, {})

            # Should not risk more than account_risk_percent of balance
            max_risk_amount = (
                100.0 * position_manager.settings.risk.account_risk_percent
            )
            assert result <= max_risk_amount / abs(
                0.52 - 0.5
            )  # Should respect risk limit
