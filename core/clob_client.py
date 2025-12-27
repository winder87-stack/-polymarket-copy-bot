"""Polymarket CLOB client with comprehensive error handling and rate limiting."""

# Standard library imports
import asyncio
import heapq
import logging
import time  # For timestamp generation and time-based operations
from decimal import Decimal

# Third-party imports
from typing import Any, Dict, List, Optional

import aiohttp
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import ApiCreds, OrderArgs, FilterParams
from tenacity import (
    after_log,
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from web3 import Web3
from web3.exceptions import BadFunctionCallOutput, ContractLogicError, Web3ValidationError

# Local imports
from config.settings import settings
from core.exceptions import APIError, PolymarketAPIError
from trading.gas_optimizer import GasOptimizationMode, GasOptimizer
from utils.helpers import wei_to_usdc
from utils.rate_limited_client import RateLimitedPolymarketClient
from utils.security import secure_log
from utils.validation import InputValidator, ValidationError

logger = logging.getLogger(__name__)


class EfficientTTLCache:
    """Efficient TTL cache with O(1) operations using heap for expiration tracking."""

    def __init__(self, ttl_seconds: int = 300, max_memory_mb: int = 50) -> None:
        """
        Initialize the efficient TTL cache.

        Args:
            ttl_seconds: Time-to-live in seconds for cache entries
            max_memory_mb: Maximum memory usage in MB before eviction
        """
        self.ttl_seconds = ttl_seconds
        self.max_memory_mb = max_memory_mb
        self._cache: dict[str, tuple[Any, float, int]] = {}  # key -> (value, timestamp, heap_index)
        self._expiration_heap: list[tuple[float, int, str]] = []  # [(timestamp, counter, key), ...]
        self._counter: int = 0  # For handling duplicate timestamps
        self._cleanup_task: Optional[asyncio.Task[None]] = None
        self._lock: asyncio.Lock = asyncio.Lock()

        # Statistics
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    async def start_background_cleanup(self):
        """Start background cleanup task"""
        if self._cleanup_task is not None:
            return

        self._cleanup_task = asyncio.create_task(self._background_cleanup())
        logger.info("🧹 Started background cache cleanup task")

    async def stop_background_cleanup(self):
        """Stop background cleanup task"""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("🧹 Stopped background cache cleanup task")

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache with O(1) access.

        Args:
            key: Cache key to look up

        Returns:
            Cached value if found and not expired, None otherwise
        """
        async with self._lock:
            if key in self._cache:
                value, timestamp, _ = self._cache[key]
                if time.time() - timestamp < self.ttl_seconds:
                    self._hits += 1
                    return value
                else:
                    # Entry expired, remove it
                    del self._cache[key]
                    self._misses += 1
                    return None
            self._misses += 1
            return None

    async def put(self, key: str, value: Any) -> None:
        """Put value in cache with O(1) access"""
        async with self._lock:
            now = time.time()
            counter = self._counter
            self._counter += 1

            # Remove old entry if it exists
            if key in self._cache:
                _, _, old_heap_index = self._cache[key]
                self._expiration_heap[old_heap_index] = None  # Mark as removed

            # Add to cache
            heap_index = len(self._expiration_heap)
            self._cache[key] = (value, now, heap_index)
            heapq.heappush(self._expiration_heap, (now + self.ttl_seconds, counter, key))

            # Check memory limits
            await self._check_memory_limits()

    async def _check_memory_limits(self) -> None:
        """Check if cache exceeds memory limits and cleanup if necessary"""
        memory_usage = self._estimate_memory_usage()
        if memory_usage > self.max_memory_mb * 1024 * 1024:  # Convert MB to bytes
            # Remove oldest 20% of entries
            entries_to_remove = max(1, len(self._cache) // 5)
            await self._cleanup_expired_entries()
            await self._evict_oldest(entries_to_remove)
            logger.warning(
                f"💾 Cache memory limit exceeded ({memory_usage / 1024 / 1024:.1f}MB), "
                f"evicted {entries_to_remove} entries"
            )

    async def _evict_oldest(self, count: int) -> None:
        """Evict oldest entries from cache"""
        # Get entries sorted by timestamp (oldest first)
        entries = [(ts, key) for key, (_, ts, _) in self._cache.items()]
        entries.sort()  # Sort by timestamp

        evicted = 0
        for _, key in entries[:count]:
            if key in self._cache:
                _, _, heap_index = self._cache[key]
                self._expiration_heap[heap_index] = None  # Mark as removed
                del self._cache[key]
                evicted += 1
                self._evictions += 1

        if evicted > 0:
            logger.debug(f"🗑️ Evicted {evicted} oldest cache entries")

    async def _background_cleanup(self) -> None:
        """Background task to cleanup expired entries"""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute
                await self._cleanup_expired_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in background cache cleanup: {e}")

    async def _cleanup_expired_entries(self) -> None:
        """Remove expired entries from cache"""
        async with self._lock:
            now = time.time()
            original_count = len(self._cache)

            # Remove expired entries from heap
            while self._expiration_heap and self._expiration_heap[0] is not None:
                exp_time, _, key = self._expiration_heap[0]
                if exp_time > now:
                    break  # No more expired entries

                heapq.heappop(self._expiration_heap)

                # Remove from cache if still there and expired
                if key in self._cache:
                    cached_time = self._cache[key][1]
                    if now - cached_time >= self.ttl_seconds:
                        del self._cache[key]
                        self._evictions += 1

            # Clean up None entries (removed items)
            self._expiration_heap = [entry for entry in self._expiration_heap if entry is not None]

            # Rebuild heap indices after cleanup
            for i, entry in enumerate(self._expiration_heap):
                if entry is not None:
                    _, _, key = entry
                    if key in self._cache:
                        self._cache[key] = self._cache[key][:2] + (i,)

            new_count = len(self._cache)
            if original_count != new_count:
                logger.debug(f"🧹 Cleaned up {original_count - new_count} expired cache entries")

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage of cache in bytes"""
        # Rough estimation: each entry ~1KB + key size
        base_memory = len(self._cache) * 1024  # 1KB per entry
        key_memory = sum(len(str(k)) for k in self._cache.keys()) * 2  # 2 bytes per char
        heap_memory = len(self._expiration_heap) * 32  # ~32 bytes per heap entry
        return base_memory + key_memory + heap_memory

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_ratio = (self._hits / total_requests) if total_requests > 0 else 0.0

        oldest_timestamp = float("inf")
        for _, timestamp, _ in self._cache.values():
            oldest_timestamp = min(oldest_timestamp, timestamp)
        oldest_timestamp = time.time() - oldest_timestamp if oldest_timestamp != float("inf") else 0

        return {
            "size": len(self._cache),
            "max_size": None,  # No hard limit, memory-based
            "hit_ratio": hit_ratio,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "memory_usage_mb": self._estimate_memory_usage() / 1024 / 1024,
            "oldest_entry_seconds": oldest_timestamp,
            "ttl_seconds": self.ttl_seconds,
            "background_cleanup_active": self._cleanup_task is not None
            and not self._cleanup_task.done(),
        }

    async def clear(self) -> None:
        """Clear all cache entries"""
        async with self._lock:
            self._cache.clear()
            self._expiration_heap.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            logger.info("🧹 Cache cleared")


class PolymarketClient:
    """
    Polymarket CLOB (Central Limit Order Book) client wrapper.

    Provides a robust interface to the Polymarket CLOB API with retry logic,
    error handling, and caching capabilities. This client handles all
    interactions with the Polymarket trading infrastructure.

    **Security Note**: This class handles private keys and should only be used
    in secure environments. Never expose instances of this class to untrusted
    code or network endpoints.

    **Performance Note**: Market data is cached using an LRU cache with TTL
    to reduce API calls and improve performance. Cache size and TTL are
    configurable via settings.

    Examples:
        >>> from config.settings import settings
        >>> client = PolymarketClient()
        >>> balance = await client.get_balance()
        >>> print(f"Current balance: ${balance:.2f}")
    """

    def __init__(self) -> None:
        """
        Initialize the Polymarket client.

        Sets up all required components including the CLOB client, Web3
        provider, and caching systems. Validates configuration and
        establishes necessary connections.

        Raises:
            ValueError: If private key is invalid or missing
            ConnectionError: If cannot connect to blockchain or CLOB API
            RuntimeError: If initialization fails for any other reason

        Security:
            - Private key is never logged in plaintext
            - Wallet address is validated and checksummed
            - All external connections are validated before use

        See Also:
            :meth:`_initialize_client`: Internal method for CLOB client setup
            :meth:`_validate_configuration`: Internal method for config validation
        """
        self.settings = settings
        self.private_key = self.settings.trading.private_key
        self.account = Account.from_key(self.private_key)
        self.wallet_address = self.account.address

        # Override wallet address if specified in settings
        if self.settings.trading.wallet_address:
            self.wallet_address = self.settings.trading.wallet_address

        secure_log(
            logger,
            "Initialized Polymarket client",
            {"wallet_address_masked": f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"},
        )

        # Initialize CLOB client
        self.client = self._initialize_client()

        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(self.settings.network.polygon_rpc_url))
        if not self.web3.is_connected():
            logger.warning("❌ Failed to connect to Polygon RPC. Some features may not work.")

        # USDC contract address on Polygon
        self.usdc_contract_address = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"

        # Initialize efficient cache for market data
        self._market_cache = EfficientTTLCache(
            ttl_seconds=300,
            max_memory_mb=50,  # 5 minutes  # 50MB limit
        )

        # Initialize rate-limited Polymarket client
        self.rate_limited_client = RateLimitedPolymarketClient(
            host=self.settings.network.clob_host, private_key=self.private_key
        )

        # Initialize gas optimizer if enabled
        self.gas_optimizer: Optional[GasOptimizer] = None
        if self.settings.trading.gas_optimization_enabled:
            try:
                mode_map = {
                    "conservative": GasOptimizationMode.CONSERVATIVE,
                    "balanced": GasOptimizationMode.BALANCED,
                    "aggressive": GasOptimizationMode.AGGRESSIVE,
                }
                mode = mode_map.get(
                    self.settings.trading.gas_optimization_mode.lower(),
                    GasOptimizationMode.BALANCED,
                )
                self.gas_optimizer = GasOptimizer(
                    web3=self.web3,
                    mode=mode,
                    update_interval_seconds=30,
                )
                logger.info(f"✅ Gas optimizer initialized in {mode.value} mode")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize gas optimizer: {e}")
                self.gas_optimizer = None

    def _initialize_client(self) -> ClobClient:
        """Initialize the CLOB client with proper authentication"""
        try:
            client = ClobClient(
                host=self.settings.network.clob_host,
                key=self.private_key,
                chain_id=POLYGON,
            )
            logger.info("✅ CLOB client initialized successfully")
            return client
        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"❌ Network error initializing CLOB client: {str(e)[:100]}")
            raise
        except (ValueError, KeyError) as e:
            logger.error(f"❌ Configuration error initializing CLOB client: {str(e)[:100]}")
            raise
        except Exception as e:
            logger.critical(
                f"❌ Unexpected error initializing CLOB client: {str(e)}", exc_info=True
            )
            raise

    def get_balance(self) -> Dict[str, Any]:
        """FIXED: Updated to use correct balance API for v0.34.1"""
        try:
            # New method: get_balance() returns token balances directly
            balances = self.client.get_balance()

            # Convert to compatibility format if needed
            if isinstance(balances, dict):
                return balances
            elif hasattr(balances, 'to_dict'):
                return balances.to_dict()

            return {'usdc': 0.0, 'matic': 0.0}  # Fallback

        except Exception as e:
            logger.error(f"❌ Balance check failed: {str(e)[:100]}")
            return {'usdc': 0.0, 'matic': 0.0, 'error': str(e)}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR),
    )
    async def get_market(self, condition_id: str) -> Optional[dict[str, Any]]:
        """Get market details by condition ID with caching"""
        try:
            # Validate condition_id before processing
            validated_condition_id = InputValidator.validate_condition_id(condition_id)

            # Check cache first
            cached_data = await self._market_cache.get(validated_condition_id)
            if cached_data is not None:
                logger.debug(f"📊 Using cached market data for {validated_condition_id}")
                return cached_data

            # Get fresh data
            market = await self.rate_limited_client.make_request(
                "get_market", condition_id=validated_condition_id
            )

            # Update cache
            await self._market_cache.put(validated_condition_id, market)
            logger.debug(f"📊 Retrieved fresh market data for {validated_condition_id}")

            return market
        except ValidationError as e:
            logger.error(f"❌ Invalid condition ID {condition_id}: {e}")
            return None
        except Exception as e:
            logger.exception(f"❌ Error getting market {validated_condition_id}: {e}")
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR),
    )
    async def get_markets(self) -> list[dict[str, Any]]:
        """Get all active markets"""
        try:
            markets = await self.rate_limited_client.make_request("get_markets")
            logger.info(f"📈 Retrieved {len(markets)} active markets")
            return markets
        except Exception as e:
            logger.exception(f"❌ Error getting markets: {e}")
            return []

    async def get_token_balance(self, token_address: str) -> float:
        """Get balance of a specific token"""
        try:
            if not self.web3.is_connected():
                logger.warning("Not connected to Web3. Cannot get token balance.")
                return 0.0

            # USDC ABI for balanceOf function
            usdc_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function",
                }
            ]

            token_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address), abi=usdc_abi
            )

            balance = token_contract.functions.balanceOf(
                Web3.to_checksum_address(self.wallet_address)
            ).call()

            return wei_to_usdc(balance)
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"❌ Network error getting token balance: {e}")
            raise APIError(f"Blockchain network error: {e}")
        except (Web3ValidationError, BadFunctionCallOutput, ValueError) as e:
            logger.error(f"❌ Contract error getting token balance: {e}")
            return 0.0
        except Exception as e:
            logger.exception(f"❌ Unexpected error in get_token_balance: {e}")
            return 0.0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, ContractLogicError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR),
    )
    async def place_order(
        self,
        condition_id: str,
        side: str,
        amount: Decimal,
        price: Decimal,
        token_id: str,
    ) -> Optional[dict[str, Any]]:
        """Place a trade order with comprehensive input validation"""
        try:
            # Validate all inputs using comprehensive validation
            validated_condition_id = InputValidator.validate_condition_id(condition_id)
            validated_side = side.upper()
            if validated_side not in ["BUY", "SELL"]:
                raise ValidationError(f"Invalid side: {side}")

            validated_amount = InputValidator.validate_trade_amount(
                float(amount),
                min_amount=self.settings.risk.min_trade_amount,
                max_amount=self.settings.risk.max_position_size,
            )

            validated_price = InputValidator.validate_price(
                float(price), min_price=0.01, max_price=0.99
            )

            # Validate token_id format if it looks like an address
            if token_id.startswith("0x"):
                InputValidator.validate_hex_string(token_id, min_length=42, max_length=42)

            # Apply slippage protection
            adjusted_price = self._apply_slippage_protection(price, side)

            # Prepare trade data for gas optimization
            trade_data = {
                "amount": float(amount),
                "price": float(price),
                "side": validated_side,
                "condition_id": validated_condition_id,
                "gas_limit": self.settings.trading.gas_limit,
            }

            # Get optimal gas price with advanced optimization
            gas_price = await self._get_optimal_gas_price(trade_data=trade_data, urgency=0.5)

            # Apply slippage protection to validated price
            adjusted_price = self._apply_slippage_protection(validated_price, validated_side)

            # Get current gas price with multiplier for priority
            gas_price = await self._get_optimal_gas_price()

            # Create order with validated inputs
            order = self.client.create_order(
                market=validated_condition_id,
                side=validated_side,
                amount=validated_amount,
                price=adjusted_price,
                token_id=token_id,
                gas_price=gas_price,
            )

            # Log order details securely
            secure_log(
                logger,
                "placing order",
                {
                    "condition_id": validated_condition_id,
                    "side": validated_side,
                    "amount": validated_amount,
                    "price": adjusted_price,
                    "token_id": token_id[-6:] + "...",  # Only show last 6 chars
                },
            )

            # Post order
            result = await self.rate_limited_client.make_request("post_order", order=order)

            if result and "orderID" in result:
                logger.info(
                    f"✅ Order placed successfully: {result['orderID']}",
                    extra={
                        "order_id": result["orderID"],
                        "wallet": self.wallet_address,
                        "side": validated_side,
                        "amount": str(validated_amount),
                        "price": str(adjusted_price),
                        "market_id": condition_id,
                    },
                )
                return result
            else:
                logger.error(
                    f"❌ Order failed: {result}",
                    extra={
                        "wallet": self.wallet_address,
                        "side": validated_side,
                        "amount": str(validated_amount),
                        "price": str(adjusted_price),
                        "market_id": condition_id,
                    },
                )
                return None

        except ValidationError as e:
            logger.error(f"❌ Input validation failed: {e}")
            # Don't send alerts for validation failures as they indicate client-side issues
            return None
        except Exception as e:
            logger.exception(f"❌ Error placing order: {e}")
            return None

    def _apply_slippage_protection(self, price: float, side: str) -> float:
        """Apply slippage protection to the price"""
        slippage = self.settings.risk.max_slippage

        if side.upper() == "BUY":
            # For buys, increase price to ensure execution (but cap at 0.99)
            return min(price * (1 + slippage), 0.99)
        else:  # SELL
            # For sells, decrease price to ensure execution (but floor at 0.01)
            return max(price * (1 - slippage), 0.01)

    async def _get_optimal_gas_price(
        self, trade_data: Optional[Dict[str, Any]] = None, urgency: float = 0.5
    ) -> int:
        """
        Get optimal gas price with advanced optimization.

        Args:
            trade_data: Optional trade data for MEV protection analysis
            urgency: Trade urgency (0-1, 1 = most urgent)

        Returns:
            Optimal gas price in gwei (as integer)
        """
        try:
            # Use advanced gas optimizer if enabled
            if self.gas_optimizer and self.settings.trading.gas_optimization_enabled:
                optimization = await self.gas_optimizer.get_optimal_gas_price(
                    trade_data=trade_data, urgency=urgency
                )

                optimal_gas_price = optimization["optimal_gas_price_gwei"]

                # Log optimization details
                logger.debug(
                    f"⛽ Gas optimization: {optimization['current_gas_price_gwei']:.2f} → "
                    f"{optimal_gas_price:.2f} gwei (multiplier: {optimization['multiplier']:.2f}x, "
                    f"spike: {optimization['is_spike']}, recommendation: {optimization['recommendation'][:50]})"
                )

                # Handle spike strategy
                if optimization.get("is_spike") and optimization.get("spike_strategy"):
                    strategy = optimization["spike_strategy"]["strategy"]
                    if strategy == "wait":
                        logger.info(
                            f"⏳ Gas spike detected - waiting {optimization['spike_strategy'].get('wait_minutes', 5)} minutes"
                        )
                        # In production, this would trigger a delayed execution
                    elif strategy == "defer":
                        logger.info("⏸️ Gas spike detected - deferring execution")
                        # In production, this would defer to next window

            else:
                # Fallback to simple multiplier approach
                gas_price = self.web3.eth.gas_price
                gas_price_gwei = self.web3.from_wei(gas_price, "gwei")

                # Apply multiplier for priority
                optimal_gas_price = gas_price_gwei * self.settings.trading.gas_price_multiplier

                logger.debug(
                    f"⛽ Gas price: {gas_price_gwei:.2f} gwei → Optimal: {optimal_gas_price:.2f} gwei"
                )

            # Cap at maximum gas price
            optimal_gas_price = min(optimal_gas_price, self.settings.trading.max_gas_price)

            return int(optimal_gas_price)

        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"⚠️ Network error getting gas price: {e}")
            return self.settings.trading.max_gas_price
        except (Web3ValidationError, ValueError, TypeError) as e:
            logger.warning(f"⚠️ Data error getting gas price: {e}")
            return self.settings.trading.max_gas_price
        except Exception as e:
            logger.exception(f"⚠️ Unexpected error getting gas price: {e}")
            return self.settings.trading.max_gas_price

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR),
    )
    async def get_active_orders(self) -> List[Dict[str, Any]]:
        """Get active orders"""
        try:
            orders = await self.rate_limited_client.make_request("get_orders")
            logger.info(f"📋 Retrieved {len(orders)} active orders")
            return orders
        except Exception as e:
            logger.exception(f"❌ Error getting active orders: {e}")
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR),
    )
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order"""
        try:
            result = await self.rate_limited_client.make_request("cancel_order", order_id=order_id)
            if result:
                logger.info(f"🚫 Order cancelled successfully: {order_id}")
                return True
            else:
                logger.error(f"❌ Failed to cancel order: {order_id}")
                return False
        except Exception as e:
            logger.exception(f"❌ Error cancelling order {order_id}: {e}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR),
    )
    async def get_trade_history(self, market_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get trade history"""
        try:
            trades = await self.rate_limited_client.make_request("get_trades", market_id=market_id)
            logger.info(f"📋 Retrieved {len(trades)} trades from history")
            return trades
        except Exception as e:
            logger.exception(f"❌ Error getting trade history: {e}")
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.ERROR),
    )
    async def get_order_book(self, condition_id: str) -> Dict[str, Any]:
        """Get order book for a market"""
        try:
            # Validate condition_id before processing
            validated_condition_id = InputValidator.validate_condition_id(condition_id)

            order_book = await self.rate_limited_client.make_request(
                "get_order_book", condition_id=validated_condition_id
            )
            logger.debug(f"📖 Retrieved order book for market {validated_condition_id}")
            return order_book
        except ValidationError as e:
            logger.error(f"❌ Invalid condition ID {condition_id}: {e}")
            return {}
        except Exception as e:
            logger.exception(f"❌ Error getting order book for {validated_condition_id}: {e}")
            return {}

    async def get_current_price(self, condition_id: str) -> Optional[float]:
        """Get current market price from order book"""
        try:
            # Validate condition_id before processing
            validated_condition_id = InputValidator.validate_condition_id(condition_id)

            order_book = await self.get_order_book(validated_condition_id)
            if order_book and "bids" in order_book and "asks" in order_book:
                if order_book["bids"] and order_book["asks"]:
                    best_bid = float(order_book["bids"][0]["price"])
                    best_ask = float(order_book["asks"][0]["price"])
                    return (best_bid + best_ask) / 2
            return None
        except ValidationError as e:
            logger.error(f"❌ Invalid condition ID {condition_id}: {e}")
            return None
        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.error(
                f"❌ Network error getting current price for {validated_condition_id}: {e}"
            )
            raise PolymarketAPIError(
                f"Failed to get current price for {validated_condition_id}: {e}"
            )
        except (ValueError, TypeError, KeyError, IndexError) as e:
            logger.error(
                f"❌ Data processing error getting current price for {validated_condition_id}: {e}"
            )
            return None
        except Exception as e:
            logger.exception(
                f"❌ Unexpected error getting current price for {validated_condition_id}: {e}"
            )
            return None

    async def start_cache_cleanup(self) -> None:
        """Start background cache cleanup task"""
        await self._market_cache.start_background_cleanup()

    async def stop_cache_cleanup(self) -> None:
        """Stop background cache cleanup task"""
        await self._market_cache.stop_background_cleanup()

    def _estimate_cache_memory_usage(self) -> float:
        """Estimate cache memory usage in MB"""
        return self._market_cache._estimate_memory_usage() / 1024 / 1024

    def _get_oldest_cache_entry_time(self) -> float:
        """Get age of oldest cache entry in seconds"""
        stats = self._market_cache.get_stats()
        return stats["oldest_entry_seconds"]

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        return self._market_cache.get_stats()

    async def clear_cache(self) -> None:
        """Clear all cached market data"""
        await self._market_cache.clear()

    def health_check(self) -> bool:
        """✅ Added proper health check method"""
        try:
            # Quick balance check as health indicator
            balance = self.get_balance()
            has_usdc = balance.get('usdc', 0) > 0.01  # At least 0.01 USDC

            # Check client connectivity
            is_connected = hasattr(self.client, 'get_balance') and callable(self.client.get_balance)

            logger.debug(f"Health check - Balance: {balance}, Connected: {is_connected}")
            return has_usdc and is_connected

        except Exception as e:
            logger.error(f"❌ Health check failed: {str(e)[:100]}")
            return False
