import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Union, Tuple
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from web3 import Web3
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, before_log, after_log, retry_if_exception_type
from config.settings import settings
from utils.security import secure_log
from utils.helpers import wei_to_usdc, usdc_to_wei, normalize_address
from web3.exceptions import ContractLogicError

logger = logging.getLogger(__name__)

class PolymarketClient:
    def __init__(self):
        self.settings = settings
        self.private_key = self.settings.trading.private_key
        self.account = Account.from_key(self.private_key)
        self.wallet_address = self.account.address

        # Override wallet address if specified in settings
        if self.settings.trading.wallet_address:
            self.wallet_address = self.settings.trading.wallet_address

        logger.info(f"Intialized Polymarket client for wallet: {self.wallet_address}")

        # Initialize CLOB client
        self.client = self._initialize_client()

        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(self.settings.network.polygon_rpc_url))
        if not self.web3.is_connected():
            logger.warning("❌ Failed to connect to Polygon RPC. Some features may not work.")

        # USDC contract address on Polygon
        self.usdc_contract_address = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"

        # Cache for market data to reduce API calls
        self._market_cache = {}
        self._market_cache_ttl = 300  # 5 minutes
        self._last_cache_cleanup = 0

    def _initialize_client(self) -> ClobClient:
        """Initialize the CLOB client with proper authentication"""
        try:
            client = ClobClient(
                host=self.settings.network.clob_host,
                key=self.private_key,
                chain_id=POLYGON
            )
            logger.info("✅ CLOB client initialized successfully")
            return client
        except Exception as e:
            logger.error(f"❌ Failed to initialize CLOB client: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR)
    )
    async def get_balance(self) -> Optional[float]:
        """Get USDC balance asynchronously"""
        try:
            balance = self.client.get_balance()
            logger.info(f"💰 Current USDC balance: ${balance:,.2f}")
            return float(balance)
        except Exception as e:
            logger.error(f"❌ Error getting balance: {e}")
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR)
    )
    async def get_market(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """Get market details by condition ID with caching"""
        try:
            # Check cache first
            now = time.time()
            if condition_id in self._market_cache:
                cached_data, timestamp = self._market_cache[condition_id]
                if now - timestamp < self._market_cache_ttl:
                    logger.debug(f"📊 Using cached market data for {condition_id}")
                    return cached_data

            # Get fresh data
            market = self.client.get_market(condition_id)

            # Update cache
            self._market_cache[condition_id] = (market, now)
            logger.debug(f"📊 Retrieved fresh market data for {condition_id}")

            # Clean up old cache entries periodically
            if now - self._last_cache_cleanup > self._market_cache_ttl:
                self._clean_cache()
                self._last_cache_cleanup = now

            return market
        except Exception as e:
            logger.error(f"❌ Error getting market {condition_id}: {e}")
            return None

    def _clean_cache(self):
        """Clean up old cache entries"""
        now = time.time()
        old_count = len(self._market_cache)
        self._market_cache = {
            k: v for k, v in self._market_cache.items()
            if now - v[1] < self._market_cache_ttl
        }
        new_count = len(self._market_cache)
        if old_count != new_count:
            logger.debug(f"🧹 Cleaned market cache: {old_count} -> {new_count} entries")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR)
    )
    async def get_markets(self) -> List[Dict[str, Any]]:
        """Get all active markets"""
        try:
            markets = self.client.get_markets()
            logger.info(f"📈 Retrieved {len(markets)} active markets")
            return markets
        except Exception as e:
            logger.error(f"❌ Error getting markets: {e}")
            return []

    async def get_token_balance(self, token_address: str) -> float:
        """Get balance of a specific token"""
        try:
            if not self.web3.is_connected():
                logger.warning("Not connected to Web3. Cannot get token balance.")
                return 0.0

            # USDC ABI for balanceOf function
            usdc_abi = [{
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            }]

            token_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=usdc_abi
            )

            balance = token_contract.functions.balanceOf(
                Web3.to_checksum_address(self.wallet_address)
            ).call()

            return wei_to_usdc(balance)
        except Exception as e:
            logger.error(f"❌ Error getting token balance: {e}")
            return 0.0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, ContractLogicError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR)
    )
    async def place_order(
        self,
        condition_id: str,
        side: str,
        amount: float,
        price: float,
        token_id: str
    ) -> Optional[Dict[str, Any]]:
        """Place a trade order with comprehensive error handling"""
        try:
            # Validate parameters
            if amount <= self.settings.risk.min_trade_amount:
                logger.error(f"❌ Order amount {amount} below minimum {self.settings.risk.min_trade_amount}")
                return None

            if not 0.01 <= price <= 0.99:  # More realistic bounds
                logger.error(f"❌ Invalid price: {price:.4f}. Must be between 0.01 and 0.99")
                return None

            # Apply slippage protection
            adjusted_price = self._apply_slippage_protection(price, side)

            # Get current gas price with multiplier for priority
            gas_price = await self._get_optimal_gas_price()

            # Create order
            order = self.client.create_order(
                market=condition_id,
                side=side,
                amount=amount,
                price=adjusted_price,
                token_id=token_id,
                gas_price=gas_price
            )

            # Log order details securely
            secure_log(logger, "placing order", {
                'condition_id': condition_id,
                'side': side,
                'amount': amount,
                'price': adjusted_price,
                'token_id': token_id[-6:] + '...'  # Only show last 6 chars
            })

            # Post order
            result = self.client.post_order(order)

            if result and 'orderID' in result:
                logger.info(f"✅ Order placed successfully: {result['orderID']}")
                logger.info(f"   {side} {amount:.4f} shares at ${adjusted_price:.4f} per share")
                return result
            else:
                logger.error(f"❌ Order failed: {result}")
                return None

        except ContractLogicError as e:
            logger.error(f"❌ Smart contract error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error placing order: {e}")
            return None

    def _apply_slippage_protection(self, price: float, side: str) -> float:
        """Apply slippage protection to the price"""
        slippage = self.settings.risk.max_slippage

        if side.upper() == 'BUY':
            # For buys, increase price to ensure execution (but cap at 0.99)
            return min(price * (1 + slippage), 0.99)
        else:  # SELL
            # For sells, decrease price to ensure execution (but floor at 0.01)
            return max(price * (1 - slippage), 0.01)

    async def _get_optimal_gas_price(self) -> int:
        """Get optimal gas price with multiplier for priority"""
        try:
            # Get current gas price from network
            gas_price = self.web3.eth.gas_price
            gas_price_gwei = self.web3.from_wei(gas_price, 'gwei')

            # Apply multiplier for priority
            optimal_gas_price = gas_price_gwei * self.settings.trading.gas_price_multiplier

            # Cap at maximum gas price
            optimal_gas_price = min(optimal_gas_price, self.settings.trading.max_gas_price)

            logger.debug(f"⛽ Gas price: {gas_price_gwei:.2f} gwei → Optimal: {optimal_gas_price:.2f} gwei")
            return int(optimal_gas_price)
        except Exception as e:
            logger.warning(f"⚠️ Error getting gas price: {e}. Using default {self.settings.trading.max_gas_price} gwei")
            return self.settings.trading.max_gas_price

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR)
    )
    async def get_active_orders(self) -> List[Dict[str, Any]]:
        """Get active orders"""
        try:
            orders = self.client.get_orders()
            logger.info(f"📋 Retrieved {len(orders)} active orders")
            return orders
        except Exception as e:
            logger.error(f"❌ Error getting active orders: {e}")
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR)
    )
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order"""
        try:
            result = self.client.cancel(order_id)
            if result:
                logger.info(f"🚫 Order cancelled successfully: {order_id}")
                return True
            else:
                logger.error(f"❌ Failed to cancel order: {order_id}")
                return False
        except Exception as e:
            logger.error(f"❌ Error cancelling order {order_id}: {e}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR)
    )
    async def get_trade_history(self, market_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get trade history"""
        try:
            trades = self.client.get_trades(market_id=market_id)
            logger.info(f"📋 Retrieved {len(trades)} trades from history")
            return trades
        except Exception as e:
            logger.error(f"❌ Error getting trade history: {e}")
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR)
    )
    async def get_order_book(self, condition_id: str) -> Dict[str, Any]:
        """Get order book for a market"""
        try:
            order_book = self.client.get_order_book(condition_id)
            logger.debug(f"📖 Retrieved order book for market {condition_id}")
            return order_book
        except Exception as e:
            logger.error(f"❌ Error getting order book for {condition_id}: {e}")
            return {}

    async def get_current_price(self, condition_id: str) -> Optional[float]:
        """Get current market price from order book"""
        try:
            order_book = await self.get_order_book(condition_id)
            if order_book and 'bids' in order_book and 'asks' in order_book:
                if order_book['bids'] and order_book['asks']:
                    best_bid = float(order_book['bids'][0]['price'])
                    best_ask = float(order_book['asks'][0]['price'])
                    return (best_bid + best_ask) / 2
            return None
        except Exception as e:
            logger.error(f"❌ Error getting current price for {condition_id}: {e}")
            return None

    async def health_check(self) -> bool:
        """Perform health check on the client"""
        try:
            # Check CLOB connection
            balance = await self.get_balance()
            if balance is None:
                logger.error("❌ Health check failed: Could not get balance")
                return False

            # Check blockchain connection
            if not self.web3.is_connected():
                logger.warning("⚠️ Health check warning: Not connected to blockchain")

            # Check gas price
            gas_price = await self._get_optimal_gas_price()
            if gas_price > self.settings.trading.max_gas_price * 2:
                logger.warning(f"⚠️ Health check warning: High gas price ({gas_price} gwei)")

            logger.info(f"✅ Health check passed. Balance: ${balance:.2f}, Gas: {gas_price} gwei")
            return True
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False
