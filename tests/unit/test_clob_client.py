"""
Unit tests for core/clob_client.py - Polymarket CLOB API interactions.
"""
import pytest
import asyncio
import time
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from core.clob_client import PolymarketClient
from config.settings import Settings
from utils.helpers import wei_to_usdc, usdc_to_wei
from web3.exceptions import ContractLogicError


class TestPolymarketClientInitialization:
    """Test PolymarketClient initialization."""

    def test_client_initialization_success(self, mock_web3, mock_clob_client, test_settings):
        """Test successful client initialization."""
        with patch('core.clob_client.Web3', return_value=mock_web3), \
             patch('core.clob_client.ClobClient', return_value=mock_clob_client):

            client = PolymarketClient()

            assert client.private_key == test_settings.trading.private_key
            assert client.wallet_address == test_settings.trading.wallet_address
            assert client.web3 == mock_web3
            assert client.client == mock_clob_client
            assert isinstance(client._market_cache, dict)
            assert client._market_cache_ttl == 300

    def test_client_initialization_clob_failure(self, mock_web3):
        """Test client initialization when CLOB client fails."""
        with patch('core.clob_client.Web3', return_value=mock_web3), \
             patch('core.clob_client.ClobClient', side_effect=Exception("CLOB connection failed")):

            with pytest.raises(Exception, match="CLOB connection failed"):
                PolymarketClient()

    def test_wallet_address_override(self, mock_web3, mock_clob_client):
        """Test wallet address override from settings."""
        override_address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44f"

        with patch('core.clob_client.Web3', return_value=mock_web3), \
             patch('core.clob_client.ClobClient', return_value=mock_clob_client), \
             patch('config.settings.settings') as mock_settings:

            mock_settings.trading.private_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            mock_settings.trading.wallet_address = override_address

            client = PolymarketClient()
            assert client.wallet_address == override_address


class TestPolymarketClientBalanceOperations:
    """Test balance-related operations."""

    async def test_get_balance_success(self, mock_polymarket_client, mock_clob_client):
        """Test successful balance retrieval."""
        mock_clob_client.get_balance.return_value = 1500.5

        balance = await mock_polymarket_client.get_balance()

        assert balance == 1500.5
        mock_clob_client.get_balance.assert_called_once()

    async def test_get_balance_failure(self, mock_polymarket_client, mock_clob_client):
        """Test balance retrieval failure."""
        mock_clob_client.get_balance.side_effect = Exception("API Error")

        balance = await mock_polymarket_client.get_balance()

        assert balance is None
        mock_clob_client.get_balance.assert_called_once()

    async def test_get_balance_with_retry(self, mock_polymarket_client, mock_clob_client):
        """Test balance retrieval with retry on failure."""
        mock_clob_client.get_balance.side_effect = [
            ConnectionError("Connection failed"),
            TimeoutError("Timeout"),
            1000.0
        ]

        balance = await mock_polymarket_client.get_balance()

        assert balance == 1000.0
        assert mock_clob_client.get_balance.call_count == 3


class TestPolymarketClientMarketOperations:
    """Test market-related operations."""

    async def test_get_market_success(self, mock_polymarket_client, mock_clob_client, sample_market_data):
        """Test successful market retrieval."""
        mock_clob_client.get_market.return_value = sample_market_data

        market = await mock_polymarket_client.get_market("test-condition-id")

        assert market == sample_market_data
        mock_clob_client.get_market.assert_called_once_with("test-condition-id")
        assert "test-condition-id" in mock_polymarket_client._market_cache

    async def test_get_market_cached(self, mock_polymarket_client, mock_clob_client, sample_market_data):
        """Test market retrieval from cache."""
        # Pre-populate cache
        mock_polymarket_client._market_cache["test-condition-id"] = (sample_market_data, time.time())

        market = await mock_polymarket_client.get_market("test-condition-id")

        assert market == sample_market_data
        # Should not call the API
        mock_clob_client.get_market.assert_not_called()

    async def test_get_market_cache_expiry(self, mock_polymarket_client, mock_clob_client, sample_market_data):
        """Test market cache expiry."""
        # Pre-populate cache with old timestamp
        old_time = time.time() - 400  # Older than TTL
        mock_polymarket_client._market_cache["test-condition-id"] = (sample_market_data, old_time)
        mock_clob_client.get_market.return_value = {"fresh": "data"}

        market = await mock_polymarket_client.get_market("test-condition-id")

        assert market == {"fresh": "data"}
        mock_clob_client.get_market.assert_called_once_with("test-condition-id")

    async def test_get_market_failure(self, mock_polymarket_client, mock_clob_client):
        """Test market retrieval failure."""
        mock_clob_client.get_market.side_effect = Exception("API Error")

        market = await mock_polymarket_client.get_market("test-condition-id")

        assert market is None

    async def test_get_markets_success(self, mock_polymarket_client, mock_clob_client):
        """Test successful markets list retrieval."""
        markets_data = [
            {"conditionId": "cond1", "active": True},
            {"conditionId": "cond2", "active": True}
        ]
        mock_clob_client.get_markets.return_value = markets_data

        markets = await mock_polymarket_client.get_markets()

        assert markets == markets_data
        mock_clob_client.get_markets.assert_called_once()


class TestPolymarketClientTokenOperations:
    """Test token-related operations."""

    async def test_get_token_balance_success(self, mock_polymarket_client, mock_web3):
        """Test successful token balance retrieval."""
        mock_contract = Mock()
        mock_contract.functions.balanceOf.return_value.call.return_value = 1000000000  # 1000 USDC in wei

        with patch.object(mock_polymarket_client.web3.eth, 'contract', return_value=mock_contract):
            balance = await mock_polymarket_client.get_token_balance("0xUSDC_ADDRESS")

            assert balance == 1000.0  # Should be converted to USDC
            mock_contract.functions.balanceOf.assert_called_once()

    async def test_get_token_balance_web3_disconnected(self, mock_polymarket_client, mock_web3):
        """Test token balance retrieval when Web3 is disconnected."""
        mock_web3.is_connected.return_value = False

        balance = await mock_polymarket_client.get_token_balance("0xUSDC_ADDRESS")

        assert balance == 0.0

    async def test_get_token_balance_contract_error(self, mock_polymarket_client, mock_web3):
        """Test token balance retrieval with contract error."""
        mock_contract = Mock()
        mock_contract.functions.balanceOf.side_effect = Exception("Contract error")

        with patch.object(mock_polymarket_client.web3.eth, 'contract', return_value=mock_contract):
            balance = await mock_polymarket_client.get_token_balance("0xUSDC_ADDRESS")

            assert balance == 0.0


class TestPolymarketClientOrderOperations:
    """Test order-related operations."""

    async def test_place_order_success(self, mock_polymarket_client, mock_clob_client, mock_web3, sample_trade):
        """Test successful order placement."""
        mock_clob_client.create_order.return_value = {"order": "data"}
        mock_clob_client.post_order.return_value = {"orderID": "test-order-123"}
        mock_web3.eth.gas_price = 50000000000

        result = await mock_polymarket_client.place_order(
            condition_id=sample_trade['condition_id'],
            side=sample_trade['side'],
            amount=sample_trade['amount'],
            price=sample_trade['price'],
            token_id=sample_trade['token_id']
        )

        assert result == {"orderID": "test-order-123"}
        mock_clob_client.create_order.assert_called_once()
        mock_clob_client.post_order.assert_called_once()

    async def test_place_order_invalid_amount(self, mock_polymarket_client, sample_trade):
        """Test order placement with invalid amount."""
        result = await mock_polymarket_client.place_order(
            condition_id=sample_trade['condition_id'],
            side=sample_trade['side'],
            amount=0.001,  # Below minimum
            price=sample_trade['price'],
            token_id=sample_trade['token_id']
        )

        assert result is None

    async def test_place_order_invalid_price(self, mock_polymarket_client, sample_trade):
        """Test order placement with invalid price."""
        result = await mock_polymarket_client.place_order(
            condition_id=sample_trade['condition_id'],
            side=sample_trade['side'],
            amount=sample_trade['amount'],
            price=1.5,  # Above 0.99
            token_id=sample_trade['token_id']
        )

        assert result is None

    async def test_place_order_contract_logic_error(self, mock_polymarket_client, mock_clob_client, sample_trade):
        """Test order placement with contract logic error."""
        mock_clob_client.post_order.side_effect = ContractLogicError("Contract error")

        result = await mock_polymarket_client.place_order(
            condition_id=sample_trade['condition_id'],
            side=sample_trade['side'],
            amount=sample_trade['amount'],
            price=sample_trade['price'],
            token_id=sample_trade['token_id']
        )

        assert result is None

    async def test_place_order_with_slippage_buy(self, mock_polymarket_client, mock_clob_client, mock_web3, sample_trade):
        """Test order placement with slippage protection for BUY orders."""
        mock_clob_client.create_order.return_value = {"order": "data"}
        mock_clob_client.post_order.return_value = {"orderID": "test-order-123"}
        mock_web3.eth.gas_price = 50000000000

        # Set max slippage to 2%
        mock_polymarket_client.settings.risk.max_slippage = 0.02

        result = await mock_polymarket_client.place_order(
            condition_id=sample_trade['condition_id'],
            side="BUY",
            amount=sample_trade['amount'],
            price=0.65,
            token_id=sample_trade['token_id']
        )

        # Price should be increased for BUY orders: 0.65 * (1 + 0.02) = 0.663
        call_args = mock_clob_client.create_order.call_args
        assert call_args[1]['price'] == 0.663

    async def test_place_order_with_slippage_sell(self, mock_polymarket_client, mock_clob_client, mock_web3, sample_trade):
        """Test order placement with slippage protection for SELL orders."""
        mock_clob_client.create_order.return_value = {"order": "data"}
        mock_clob_client.post_order.return_value = {"orderID": "test-order-123"}
        mock_web3.eth.gas_price = 50000000000

        # Set max slippage to 2%
        mock_polymarket_client.settings.risk.max_slippage = 0.02

        result = await mock_polymarket_client.place_order(
            condition_id=sample_trade['condition_id'],
            side="SELL",
            amount=sample_trade['amount'],
            price=0.65,
            token_id=sample_trade['token_id']
        )

        # Price should be decreased for SELL orders: 0.65 * (1 - 0.02) = 0.637
        call_args = mock_clob_client.create_order.call_args
        assert call_args[1]['price'] == 0.637

    async def test_get_optimal_gas_price(self, mock_polymarket_client, mock_web3):
        """Test optimal gas price calculation."""
        mock_web3.eth.gas_price = 30000000000  # 30 gwei
        mock_polymarket_client.settings.trading.gas_price_multiplier = 1.2
        mock_polymarket_client.settings.trading.max_gas_price = 200  # 200 gwei

        gas_price = await mock_polymarket_client._get_optimal_gas_price()

        # 30 * 1.2 = 36 gwei, should not exceed max
        assert gas_price == 36

    async def test_get_optimal_gas_price_capped(self, mock_polymarket_client, mock_web3):
        """Test optimal gas price capping."""
        mock_web3.eth.gas_price = 30000000000  # 30 gwei
        mock_polymarket_client.settings.trading.gas_price_multiplier = 10.0  # Would make it 300 gwei
        mock_polymarket_client.settings.trading.max_gas_price = 100  # 100 gwei cap

        gas_price = await mock_polymarket_client._get_optimal_gas_price()

        assert gas_price == 100  # Should be capped

    async def test_get_active_orders_success(self, mock_polymarket_client, mock_clob_client):
        """Test successful active orders retrieval."""
        orders_data = [
            {"orderID": "order1", "status": "open"},
            {"orderID": "order2", "status": "filled"}
        ]
        mock_clob_client.get_orders.return_value = orders_data

        orders = await mock_polymarket_client.get_active_orders()

        assert orders == orders_data
        mock_clob_client.get_orders.assert_called_once()

    async def test_cancel_order_success(self, mock_polymarket_client, mock_clob_client):
        """Test successful order cancellation."""
        mock_clob_client.cancel.return_value = True

        result = await mock_polymarket_client.cancel_order("test-order-id")

        assert result is True
        mock_clob_client.cancel.assert_called_once_with("test-order-id")

    async def test_cancel_order_failure(self, mock_polymarket_client, mock_clob_client):
        """Test order cancellation failure."""
        mock_clob_client.cancel.return_value = False

        result = await mock_polymarket_client.cancel_order("test-order-id")

        assert result is False


class TestPolymarketClientTradeOperations:
    """Test trade history operations."""

    async def test_get_trade_history_success(self, mock_polymarket_client, mock_clob_client):
        """Test successful trade history retrieval."""
        trades_data = [
            {"tradeID": "trade1", "amount": 100, "price": 0.65},
            {"tradeID": "trade2", "amount": 50, "price": 0.67}
        ]
        mock_clob_client.get_trades.return_value = trades_data

        trades = await mock_polymarket_client.get_trade_history("market-123")

        assert trades == trades_data
        mock_clob_client.get_trades.assert_called_once_with(market_id="market-123")

    async def test_get_trade_history_no_market(self, mock_polymarket_client, mock_clob_client):
        """Test trade history retrieval without market filter."""
        trades_data = [{"tradeID": "trade1"}]
        mock_clob_client.get_trades.return_value = trades_data

        trades = await mock_polymarket_client.get_trade_history()

        assert trades == trades_data
        mock_clob_client.get_trades.assert_called_once_with(market_id=None)


class TestPolymarketClientOrderBookOperations:
    """Test order book operations."""

    async def test_get_order_book_success(self, mock_polymarket_client, mock_clob_client, sample_order_book):
        """Test successful order book retrieval."""
        mock_clob_client.get_order_book.return_value = sample_order_book

        order_book = await mock_polymarket_client.get_order_book("test-condition-id")

        assert order_book == sample_order_book
        mock_clob_client.get_order_book.assert_called_once_with("test-condition-id")

    async def test_get_current_price_success(self, mock_polymarket_client, mock_clob_client, sample_order_book):
        """Test successful current price calculation."""
        mock_clob_client.get_order_book.return_value = sample_order_book

        price = await mock_polymarket_client.get_current_price("test-condition-id")

        # Should be midpoint of best bid (0.65) and best ask (0.66)
        assert price == 0.655

    async def test_get_current_price_no_order_book(self, mock_polymarket_client, mock_clob_client):
        """Test current price calculation with empty order book."""
        mock_clob_client.get_order_book.return_value = {}

        price = await mock_polymarket_client.get_current_price("test-condition-id")

        assert price is None

    async def test_get_current_price_missing_data(self, mock_polymarket_client, mock_clob_client):
        """Test current price calculation with missing order book data."""
        mock_clob_client.get_order_book.return_value = {"bids": [], "asks": []}

        price = await mock_polymarket_client.get_current_price("test-condition-id")

        assert price is None


class TestPolymarketClientCacheOperations:
    """Test cache operations."""

    def test_clean_cache(self, mock_polymarket_client):
        """Test cache cleaning."""
        # Populate cache with old and new entries
        now = time.time()
        mock_polymarket_client._market_cache = {
            "fresh": ({"data": "fresh"}, now - 100),
            "old": ({"data": "old"}, now - 400),
            "very_old": ({"data": "very_old"}, now - 600)
        }

        mock_polymarket_client._clean_cache()

        # Only fresh entries should remain
        assert "fresh" in mock_polymarket_client._market_cache
        assert "old" not in mock_polymarket_client._market_cache
        assert "very_old" not in mock_polymarket_client._market_cache


class TestPolymarketClientHealthCheck:
    """Test health check functionality."""

    async def test_health_check_success(self, mock_polymarket_client, mock_clob_client, mock_web3):
        """Test successful health check."""
        mock_clob_client.get_balance.return_value = 1000.0
        mock_web3.is_connected.return_value = True
        mock_web3.eth.gas_price = 30000000000

        healthy = await mock_polymarket_client.health_check()

        assert healthy is True
        mock_clob_client.get_balance.assert_called_once()

    async def test_health_check_balance_failure(self, mock_polymarket_client, mock_clob_client):
        """Test health check failure due to balance retrieval error."""
        mock_clob_client.get_balance.side_effect = Exception("API Error")

        healthy = await mock_polymarket_client.health_check()

        assert healthy is False

    async def test_health_check_high_gas_price(self, mock_polymarket_client, mock_clob_client, mock_web3):
        """Test health check with high gas price warning."""
        mock_clob_client.get_balance.return_value = 1000.0
        mock_web3.is_connected.return_value = True
        mock_web3.eth.gas_price = 200000000000  # 200 gwei - very high

        # Set max gas price to 50 gwei
        mock_polymarket_client.settings.trading.max_gas_price = 50

        healthy = await mock_polymarket_client.health_check()

        assert healthy is True  # Health check should still pass but log warning


class TestPolymarketClientErrorHandling:
    """Test error handling and retries."""

    async def test_retry_on_connection_error(self, mock_polymarket_client, mock_clob_client):
        """Test retry behavior on connection errors."""
        mock_clob_client.get_balance.side_effect = [
            ConnectionError("Connection failed"),
            TimeoutError("Timeout"),
            500.0
        ]

        balance = await mock_polymarket_client.get_balance()

        assert balance == 500.0
        assert mock_clob_client.get_balance.call_count == 3

    async def test_retry_exhaustion(self, mock_polymarket_client, mock_clob_client):
        """Test retry exhaustion."""
        mock_clob_client.get_balance.side_effect = ConnectionError("Persistent connection failure")

        balance = await mock_polymarket_client.get_balance()

        assert balance is None
        assert mock_clob_client.get_balance.call_count == 3  # Max attempts

    async def test_contract_logic_error_no_retry(self, mock_polymarket_client, mock_clob_client):
        """Test that ContractLogicError doesn't trigger retry."""
        mock_clob_client.get_balance.side_effect = ContractLogicError("Contract logic error")

        balance = await mock_polymarket_client.get_balance()

        assert balance is None
        # Should not retry on ContractLogicError
        mock_clob_client.get_balance.assert_called_once()


class TestPolymarketClientUtilityMethods:
    """Test utility methods."""

    def test_apply_slippage_buy_order(self, mock_polymarket_client):
        """Test slippage application for buy orders."""
        mock_polymarket_client.settings.risk.max_slippage = 0.02

        adjusted_price = mock_polymarket_client._apply_slippage_protection(0.65, "BUY")

        assert adjusted_price == 0.663  # 0.65 * (1 + 0.02)

    def test_apply_slippage_sell_order(self, mock_polymarket_client):
        """Test slippage application for sell orders."""
        mock_polymarket_client.settings.risk.max_slippage = 0.02

        adjusted_price = mock_polymarket_client._apply_slippage_protection(0.65, "SELL")

        assert adjusted_price == 0.637  # 0.65 * (1 - 0.02)

    def test_apply_slippage_buy_order_capped(self, mock_polymarket_client):
        """Test slippage application for buy orders with price cap."""
        mock_polymarket_client.settings.risk.max_slippage = 0.1

        # Price would be 0.99 * 1.1 = 1.089, but should be capped at 0.99
        adjusted_price = mock_polymarket_client._apply_slippage_protection(0.99, "BUY")

        assert adjusted_price == 0.99

    def test_apply_slippage_sell_order_floored(self, mock_polymarket_client):
        """Test slippage application for sell orders with price floor."""
        mock_polymarket_client.settings.risk.max_slippage = 0.1

        # Price would be 0.01 * 0.9 = 0.009, but should be floored at 0.01
        adjusted_price = mock_polymarket_client._apply_slippage_protection(0.01, "SELL")

        assert adjusted_price == 0.01


class TestPolymarketClientIntegration:
    """Integration tests for PolymarketClient."""

    async def test_full_order_flow(self, mock_polymarket_client, mock_clob_client, mock_web3, sample_trade):
        """Test complete order placement flow."""
        # Setup mocks
        mock_clob_client.get_market.return_value = {
            'conditionId': sample_trade['condition_id'],
            'tokens': [{'tokenId': sample_trade['token_id']}]
        }
        mock_clob_client.create_order.return_value = {"order": "data"}
        mock_clob_client.post_order.return_value = {"orderID": "test-order-123"}
        mock_web3.eth.gas_price = 50000000000

        # Execute order
        result = await mock_polymarket_client.place_order(
            condition_id=sample_trade['condition_id'],
            side=sample_trade['side'],
            amount=sample_trade['amount'],
            price=sample_trade['price'],
            token_id=sample_trade['token_id']
        )

        assert result == {"orderID": "test-order-123"}

        # Verify all expected calls were made
        mock_clob_client.get_market.assert_called_once_with(sample_trade['condition_id'])
        mock_clob_client.create_order.assert_called_once()
        mock_clob_client.post_order.assert_called_once()

    async def test_balance_and_health_check_flow(self, mock_polymarket_client, mock_clob_client, mock_web3):
        """Test balance retrieval and health check flow."""
        mock_clob_client.get_balance.return_value = 2500.75
        mock_web3.is_connected.return_value = True
        mock_web3.eth.gas_price = 25000000000

        # Get balance
        balance = await mock_polymarket_client.get_balance()
        assert balance == 2500.75

        # Health check
        healthy = await mock_polymarket_client.health_check()
        assert healthy is True

        # Verify calls
        assert mock_clob_client.get_balance.call_count == 2  # Once for balance, once for health check
