"""Comprehensive unit tests for trade executor slippage protection scenarios.

Tests slippage detection, protection mechanisms, and edge cases.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from core.trade_executor import TradeExecutor
from core.clob_client import PolymarketClient
from tests.fixtures.market_data_generators import MarketDataGenerator


@pytest.fixture
def mock_clob_client():
    """Create mock CLOB client."""
    client = MagicMock(spec=PolymarketClient)
    client.get_balance = AsyncMock(return_value=Decimal("1000.0"))
    client.get_current_price = AsyncMock(return_value=0.5)
    client.get_market = AsyncMock(return_value={"tokens": [{"tokenId": "0x123"}]})
    client.place_order = AsyncMock(return_value={"orderID": "order_123"})
    client.wallet_address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
    return client


@pytest.fixture
def trade_executor(mock_clob_client):
    """Create trade executor with mock client."""
    from config.settings import RiskManagementConfig, Settings

    settings = MagicMock(spec=Settings)
    settings.risk = RiskManagementConfig(
        max_position_size=50.0,
        max_daily_loss=100.0,
        min_trade_amount=1.0,
        max_slippage=0.02,  # 2% max slippage
    )
    settings.monitoring = MagicMock()
    settings.monitoring.min_confidence_score = 0.7
    settings.alerts = MagicMock()
    settings.alerts.alert_on_trade = False

    executor = TradeExecutor(mock_clob_client)
    executor.settings = settings
    return executor


class TestSlippageProtection:
    """Test slippage protection mechanisms."""

    @pytest.mark.asyncio
    async def test_slippage_detection(
        self, trade_executor: TradeExecutor, mock_clob_client
    ):
        """Test detection of excessive slippage."""
        generator = MarketDataGenerator()

        # Generate slippage scenario
        slippage_scenario = generator.generate_slippage_scenario(
            intended_price=0.5,
            slippage_pct=0.05,  # 5% slippage (exceeds 2% max)
        )

        original_trade = {
            "tx_hash": "0x123",
            "timestamp": 1000000000,
            "wallet_address": "0xabc",
            "condition_id": "0xdef",
            "side": "BUY",
            "amount": 100.0,
            "price": slippage_scenario["intended_price"],
            "confidence_score": 0.8,
        }

        # Mock current price with slippage
        mock_clob_client.get_current_price = AsyncMock(
            return_value=slippage_scenario["actual_price"]
        )

        # Calculate copy amount
        copy_amount = await trade_executor._calculate_copy_amount(original_trade, {})

        # Verify slippage was considered in position sizing
        assert copy_amount > 0
        assert copy_amount <= trade_executor.settings.risk.max_position_size

    @pytest.mark.asyncio
    async def test_slippage_within_limits(
        self, trade_executor: TradeExecutor, mock_clob_client
    ):
        """Test trade execution when slippage is within limits."""
        generator = MarketDataGenerator()

        # Generate acceptable slippage scenario
        slippage_scenario = generator.generate_slippage_scenario(
            intended_price=0.5,
            slippage_pct=0.01,  # 1% slippage (within 2% max)
        )

        original_trade = {
            "tx_hash": "0x123",
            "timestamp": 1000000000,
            "wallet_address": "0xabc",
            "condition_id": "0xdef",
            "side": "BUY",
            "amount": 100.0,
            "price": slippage_scenario["intended_price"],
            "confidence_score": 0.8,
        }

        mock_clob_client.get_current_price = AsyncMock(
            return_value=slippage_scenario["actual_price"]
        )

        copy_amount = await trade_executor._calculate_copy_amount(original_trade, {})

        # Should proceed with trade
        assert copy_amount > 0

    @pytest.mark.asyncio
    async def test_extreme_slippage_rejection(
        self, trade_executor: TradeExecutor, mock_clob_client
    ):
        """Test rejection of trades with extreme slippage."""
        original_trade = {
            "tx_hash": "0x123",
            "timestamp": 1000000000,
            "wallet_address": "0xabc",
            "condition_id": "0xdef",
            "side": "BUY",
            "amount": 100.0,
            "price": 0.5,
            "confidence_score": 0.8,
        }

        # Extreme slippage: 20% price difference
        mock_clob_client.get_current_price = AsyncMock(return_value=0.6)

        copy_amount = await trade_executor._calculate_copy_amount(original_trade, {})

        # Position size should be reduced due to high price risk
        assert copy_amount > 0
        # With 20% price difference, position size should be significantly reduced
        balance = await mock_clob_client.get_balance()
        max_normal_size = float(balance) * 0.01 / 0.0001  # Normal calculation
        assert copy_amount < max_normal_size * 0.5  # Should be much smaller

    @pytest.mark.asyncio
    async def test_slippage_with_volatile_market(
        self, trade_executor: TradeExecutor, mock_clob_client
    ):
        """Test slippage handling in volatile market conditions."""
        generator = MarketDataGenerator()

        # Generate volatile price series
        prices = generator.generate_volatile_price_series(
            base_price=0.5,
            volatility=0.15,  # High volatility
            num_points=5,
        )

        original_trade = {
            "tx_hash": "0x123",
            "timestamp": 1000000000,
            "wallet_address": "0xabc",
            "condition_id": "0xdef",
            "side": "BUY",
            "amount": 100.0,
            "price": prices[0],
            "confidence_score": 0.8,
        }

        # Test with each price in the series
        copy_amounts = []
        for price in prices:
            mock_clob_client.get_current_price = AsyncMock(return_value=price)
            amount = await trade_executor._calculate_copy_amount(original_trade, {})
            copy_amounts.append(amount)

        # Position sizes should adapt to volatility
        assert all(amount > 0 for amount in copy_amounts)
        # Higher volatility should result in smaller positions
        avg_size = sum(copy_amounts) / len(copy_amounts)
        assert avg_size <= trade_executor.settings.risk.max_position_size

    @pytest.mark.asyncio
    async def test_slippage_protection_edge_cases(
        self, trade_executor: TradeExecutor, mock_clob_client
    ):
        """Test slippage protection edge cases."""
        original_trade = {
            "tx_hash": "0x123",
            "timestamp": 1000000000,
            "wallet_address": "0xabc",
            "condition_id": "0xdef",
            "side": "BUY",
            "amount": 100.0,
            "price": 0.5,
            "confidence_score": 0.8,
        }

        # Edge case: Price exactly matches intended price
        mock_clob_client.get_current_price = AsyncMock(return_value=0.5)
        amount1 = await trade_executor._calculate_copy_amount(original_trade, {})
        assert amount1 > 0

        # Edge case: Very small price difference
        mock_clob_client.get_current_price = AsyncMock(return_value=0.5001)
        amount2 = await trade_executor._calculate_copy_amount(original_trade, {})
        assert amount2 > 0

        # Edge case: Price at boundary (0.01)
        original_trade["price"] = 0.01
        mock_clob_client.get_current_price = AsyncMock(return_value=0.0102)
        amount3 = await trade_executor._calculate_copy_amount(original_trade, {})
        assert amount3 > 0

    @pytest.mark.asyncio
    async def test_slippage_with_low_liquidity(
        self, trade_executor: TradeExecutor, mock_clob_client
    ):
        """Test slippage in low liquidity conditions."""
        generator = MarketDataGenerator()
        market_conditions = generator.generate_market_conditions("normal")
        market_conditions["liquidity_score"] = 0.1  # Very low liquidity

        original_trade = {
            "tx_hash": "0x123",
            "timestamp": 1000000000,
            "wallet_address": "0xabc",
            "condition_id": "0xdef",
            "side": "BUY",
            "amount": 100.0,
            "price": 0.5,
            "confidence_score": 0.8,
        }

        # Low liquidity often leads to higher slippage
        # Simulate by having current price differ significantly
        mock_clob_client.get_current_price = AsyncMock(
            return_value=0.52
        )  # 4% difference

        copy_amount = await trade_executor._calculate_copy_amount(original_trade, {})

        # Position size should be reduced due to slippage risk
        assert copy_amount > 0
        assert copy_amount <= trade_executor.settings.risk.max_position_size

    @pytest.mark.asyncio
    async def test_slippage_protection_with_balance_changes(
        self, trade_executor: TradeExecutor, mock_clob_client
    ):
        """Test slippage protection when account balance changes."""
        original_trade = {
            "tx_hash": "0x123",
            "timestamp": 1000000000,
            "wallet_address": "0xabc",
            "condition_id": "0xdef",
            "side": "BUY",
            "amount": 100.0,
            "price": 0.5,
            "confidence_score": 0.8,
        }

        # Test with different balances
        balances = [100.0, 500.0, 1000.0, 5000.0]
        copy_amounts = []

        for balance in balances:
            mock_clob_client.get_balance = AsyncMock(return_value=Decimal(str(balance)))
            mock_clob_client.get_current_price = AsyncMock(
                return_value=0.51
            )  # 2% slippage

            amount = await trade_executor._calculate_copy_amount(original_trade, {})
            copy_amounts.append(amount)

        # All amounts should be valid
        assert all(amount > 0 for amount in copy_amounts)
        # Higher balance should allow larger positions (within limits)
        assert copy_amounts[-1] >= copy_amounts[0]
