"""
Mock CLOB API for testing Polymarket interactions.
"""
import json
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import logging
from unittest.mock import Mock

logger = logging.getLogger(__name__)


class CLOBAPIMock:
    """Mock Polymarket CLOB API for testing."""

    def __init__(self):
        self.markets: Dict[str, Dict[str, Any]] = {}
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.trades: List[Dict[str, Any]] = []
        self.balances: Dict[str, float] = {}
        self.order_books: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

        # Error simulation
        self.should_fail = False
        self.fail_with_exception = None
        self.delay_responses = False
        self.response_delay = 0.1

        self._setup_default_data()

    def _setup_default_data(self):
        """Set up default mock data."""
        # Default markets
        self.markets = {
            "0x1234567890abcdef1234567890abcdef12345678": {
                'conditionId': "0x1234567890abcdef1234567890abcdef12345678",
                'tokens': [
                    {'tokenId': "0xabcdef1234567890abcdef1234567890abcdef12", 'outcome': 'YES'},
                    {'tokenId': "0xabcdef1234567890abcdef1234567890abcdef13", 'outcome': 'NO'}
                ],
                'active': True,
                'closed': False,
                'question': 'Will ETH reach $5000 by end of 2024?',
                'description': 'Ethereum price prediction market'
            },
            "0xabcdef1234567890abcdef1234567890abcdef": {
                'conditionId': "0xabcdef1234567890abcdef1234567890abcdef",
                'tokens': [
                    {'tokenId': "0x1234567890abcdef1234567890abcdef12345678", 'outcome': 'YES'},
                    {'tokenId': "0x1234567890abcdef1234567890abcdef12345679", 'outcome': 'NO'}
                ],
                'active': True,
                'closed': False,
                'question': 'Will BTC reach $100k by end of 2024?',
                'description': 'Bitcoin price prediction market'
            }
        }

        # Default order book
        self.order_books = {
            "0x1234567890abcdef1234567890abcdef12345678": {
                'bids': [
                    {'price': '0.65', 'size': '100.0'},
                    {'price': '0.64', 'size': '50.0'},
                    {'price': '0.63', 'size': '75.0'}
                ],
                'asks': [
                    {'price': '0.66', 'size': '80.0'},
                    {'price': '0.67', 'size': '60.0'},
                    {'price': '0.68', 'size': '40.0'}
                ]
            }
        }

        # Default balance
        self.balances = {
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44e": 1000.0
        }

    async def get_balance(self) -> float:
        """Get account balance."""
        if self.should_fail:
            if self.fail_with_exception:
                raise self.fail_with_exception
            return None

        if self.delay_responses:
            await asyncio.sleep(self.response_delay)

        return self.balances.get("0x742d35Cc6634C0532925a3b844Bc454e4438f44e", 0.0)

    async def get_market(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """Get market details."""
        if self.should_fail:
            if self.fail_with_exception:
                raise self.fail_with_exception
            return None

        if self.delay_responses:
            await asyncio.sleep(self.response_delay)

        return self.markets.get(condition_id)

    async def get_markets(self) -> List[Dict[str, Any]]:
        """Get all markets."""
        if self.should_fail:
            if self.fail_with_exception:
                raise self.fail_with_exception
            return []

        if self.delay_responses:
            await asyncio.sleep(self.response_delay)

        return list(self.markets.values())

    async def get_order_book(self, condition_id: str) -> Dict[str, Any]:
        """Get order book for a market."""
        if self.should_fail:
            if self.fail_with_exception:
                raise self.fail_with_exception
            return {}

        if self.delay_responses:
            await asyncio.sleep(self.response_delay)

        return self.order_books.get(condition_id, {'bids': [], 'asks': []})

    async def get_orders(self) -> List[Dict[str, Any]]:
        """Get active orders."""
        if self.should_fail:
            if self.fail_with_exception:
                raise self.fail_with_exception
            return []

        if self.delay_responses:
            await asyncio.sleep(self.response_delay)

        return list(self.orders.values())

    async def get_trades(self, market_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get trade history."""
        if self.should_fail:
            if self.fail_with_exception:
                raise self.fail_with_exception
            return []

        if self.delay_responses:
            await asyncio.sleep(self.response_delay)

        if market_id:
            return [trade for trade in self.trades if trade.get('market_id') == market_id]
        return self.trades.copy()

    async def create_order(self, market: str, side: str, amount: float,
                          price: float, token_id: str, gas_price: int = None) -> Dict[str, Any]:
        """Create an order."""
        if self.should_fail:
            if self.fail_with_exception:
                raise self.fail_with_exception
            return None

        if self.delay_responses:
            await asyncio.sleep(self.response_delay)

        order = {
            'market': market,
            'side': side,
            'amount': amount,
            'price': price,
            'token_id': token_id,
            'gas_price': gas_price or 50000000000,
            'orderId': f"order_{len(self.orders) + 1}"
        }

        return order

    async def post_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Post an order."""
        if self.should_fail:
            if self.fail_with_exception:
                raise self.fail_with_exception
            return None

        if self.delay_responses:
            await asyncio.sleep(self.response_delay)

        order_id = f"posted_order_{len(self.orders) + 1}"
        self.orders[order_id] = order

        return {'orderID': order_id}

    async def cancel(self, order_id: str) -> bool:
        """Cancel an order."""
        if self.should_fail:
            if self.fail_with_exception:
                raise self.fail_with_exception
            return False

        if self.delay_responses:
            await asyncio.sleep(self.response_delay)

        if order_id in self.orders:
            del self.orders[order_id]
            return True
        return False

    # Test control methods
    def set_should_fail(self, should_fail: bool, exception: Exception = None):
        """Set failure mode for testing."""
        self.should_fail = should_fail
        self.fail_with_exception = exception

    def set_response_delay(self, delay: float):
        """Set response delay for testing."""
        self.delay_responses = True
        self.response_delay = delay

    def reset_delays(self):
        """Reset response delays."""
        self.delay_responses = False
        self.response_delay = 0.1

    def add_market(self, condition_id: str, market_data: Dict[str, Any]):
        """Add a market for testing."""
        self.markets[condition_id] = market_data

    def update_order_book(self, condition_id: str, bids: List[Dict[str, Any]],
                         asks: List[Dict[str, Any]]):
        """Update order book for testing."""
        self.order_books[condition_id] = {'bids': bids, 'asks': asks}

    def add_trade(self, trade: Dict[str, Any]):
        """Add a trade for testing."""
        self.trades.append(trade)

    def set_balance(self, address: str, balance: float):
        """Set balance for testing."""
        self.balances[address] = balance

    def clear_data(self):
        """Clear all mock data."""
        self.markets.clear()
        self.orders.clear()
        self.trades.clear()
        self.balances.clear()
        self.order_books.clear()
        self._setup_default_data()

    def get_call_stats(self) -> Dict[str, int]:
        """Get call statistics for testing."""
        return {
            'markets_calls': 0,  # Would need to be tracked in real implementation
            'orders_calls': 0,
            'trades_calls': 0,
            'balance_calls': 0
        }


class MockCLOBClient:
    """Mock CLOB client that mimics the py_clob_client interface."""

    def __init__(self, api_mock: CLOBAPIMock = None):
        self.api_mock = api_mock or CLOBAPIMock()

    def get_balance(self):
        """Synchronous wrapper for get_balance."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.api_mock.get_balance())
        finally:
            loop.close()

    def get_market(self, condition_id: str):
        """Synchronous wrapper for get_market."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.api_mock.get_market(condition_id))
        finally:
            loop.close()

    def get_markets(self):
        """Synchronous wrapper for get_markets."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.api_mock.get_markets())
        finally:
            loop.close()

    def get_order_book(self, condition_id: str):
        """Synchronous wrapper for get_order_book."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.api_mock.get_order_book(condition_id))
        finally:
            loop.close()

    def get_orders(self):
        """Synchronous wrapper for get_orders."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.api_mock.get_orders())
        finally:
            loop.close()

    def get_trades(self, market_id: str = None):
        """Synchronous wrapper for get_trades."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.api_mock.get_trades(market_id))
        finally:
            loop.close()

    def create_order(self, market: str, side: str, amount: float,
                    price: float, token_id: str, gas_price: int = None):
        """Synchronous wrapper for create_order."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.api_mock.create_order(market, side, amount, price, token_id, gas_price)
            )
        finally:
            loop.close()

    def post_order(self, order):
        """Synchronous wrapper for post_order."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.api_mock.post_order(order))
        finally:
            loop.close()

    def cancel(self, order_id: str):
        """Synchronous wrapper for cancel."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.api_mock.cancel(order_id))
        finally:
            loop.close()


class AsyncCLOBClient:
    """Async version of mock CLOB client."""

    def __init__(self, api_mock: CLOBAPIMock = None):
        self.api_mock = api_mock or CLOBAPIMock()

    async def get_balance(self):
        """Async get_balance."""
        return await self.api_mock.get_balance()

    async def get_market(self, condition_id: str):
        """Async get_market."""
        return await self.api_mock.get_market(condition_id)

    async def get_markets(self):
        """Async get_markets."""
        return await self.api_mock.get_markets()

    async def get_order_book(self, condition_id: str):
        """Async get_order_book."""
        return await self.api_mock.get_order_book(condition_id)

    async def get_orders(self):
        """Async get_orders."""
        return await self.api_mock.get_orders()

    async def get_trades(self, market_id: str = None):
        """Async get_trades."""
        return await self.api_mock.get_trades(market_id)

    async def create_order(self, market: str, side: str, amount: float,
                          price: float, token_id: str, gas_price: int = None):
        """Async create_order."""
        return await self.api_mock.create_order(market, side, amount, price, token_id, gas_price)

    async def post_order(self, order):
        """Async post_order."""
        return await self.api_mock.post_order(order)

    async def cancel(self, order_id: str):
        """Async cancel."""
        return await self.api_mock.cancel(order_id)


# Factory functions for easy testing
def create_mock_clob_client() -> MockCLOBClient:
    """Create a mock CLOB client for testing."""
    return MockCLOBClient()


def create_async_mock_clob_client() -> AsyncCLOBClient:
    """Create an async mock CLOB client for testing."""
    return AsyncCLOBClient()


def create_clob_api_with_custom_data(markets: Dict[str, Dict] = None,
                                   order_books: Dict[str, Dict] = None) -> CLOBAPIMock:
    """Create CLOB API mock with custom data."""
    api = CLOBAPIMock()

    if markets:
        api.markets.update(markets)

    if order_books:
        api.order_books.update(order_books)

    return api


if __name__ == "__main__":
    # Example usage
    api = CLOBAPIMock()
    client = MockCLOBClient(api)

    # Test basic functionality
    balance = client.get_balance()
    print(f"Balance: {balance}")

    markets = client.get_markets()
    print(f"Markets: {len(markets)}")

    if markets:
        market = client.get_market(markets[0]['conditionId'])
        print(f"First market: {market['question']}")
