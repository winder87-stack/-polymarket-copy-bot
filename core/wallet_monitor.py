import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from config.settings import settings
from utils.helpers import calculate_confidence_score, normalize_address
from utils.security import secure_log

logger = logging.getLogger(__name__)


class WalletMonitor:
    """Monitor wallet transactions for copy trading opportunities with performance optimizations"""

    def __init__(self, settings):
        self.settings = settings
        self.web3 = None
        self.polygonscan_api_key = settings.network.polygonscan_api_key

        # Target wallets to monitor
        self.target_wallets = settings.monitoring.target_wallets

        # Transaction processing state
        self.processed_transactions: set = set()
        self.max_processed_cache = 100000  # Limit cache size for memory efficiency
        self.last_checked_block = 0

        # Rate limiting
        self.api_call_delay = 0.2  # 5 calls per second max
        self.last_api_call = 0
        self.rate_limit_lock = asyncio.Lock()

        # Polymarket contract addresses
        self.polymarket_contracts = [
            "0x4D97DCc4e5c36A3b0c9072A2F5B3C1b1C1B1B1B1",  # Placeholder - replace with real contracts
            "0x8c16f85a4d5f8f23d29e9c7e3d4a3a5a6e4f2b2e",  # Polymarket CTF Exchange
        ]

        # Trade patterns for confidence scoring
        self.trade_patterns = {
            "min_amount": 10.0,
            "max_amount": 10000.0,
            "min_gas_price": 10**9,  # 1 gwei
            "contract_whitelist": set(self.polymarket_contracts),
        }

        # Performance optimizations
        self.transaction_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = (
            {}
        )  # cache_key -> (data, timestamp)
        self.cache_ttl: int = 300  # 5 minutes
        self.price_cache: Dict[str, Tuple[float, float]] = {}  # condition_id -> (price, timestamp)
        self.price_cache_ttl: int = 60  # 1 minute

        # Performance monitoring
        self.api_call_times: List[float] = []
        self.max_call_times = 1000  # Keep last 1000 measurements
        self.cache_hits = 0
        self.cache_misses = 0

        logger.info(f"Initialized wallet monitor for {len(self.target_wallets)} wallets")

    async def monitor_wallets(self) -> List[Dict[str, Any]]:
        """Monitor all target wallets for new trades"""
        if not self.target_wallets:
            return []

        detected_trades = []

        # Monitor wallets concurrently for better performance
        tasks = [self._monitor_single_wallet(wallet) for wallet in self.target_wallets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                detected_trades.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Error monitoring wallet: {result}")

        # Clean up processed transactions cache periodically
        if len(self.processed_transactions) > self.max_processed_cache:
            self._cleanup_processed_transactions()

        return detected_trades

    async def _monitor_single_wallet(self, wallet_address: str) -> List[Dict[str, Any]]:
        """Monitor a single wallet for trades with performance optimizations"""
        try:
            # Get recent transactions with caching
            transactions = await self.get_wallet_transactions(wallet_address)

            if not transactions:
                return []

            # Filter for Polymarket trades
            polymarket_trades = self.detect_polymarket_trades(transactions)

            return polymarket_trades

        except Exception as e:
            logger.error(f"Error monitoring wallet {wallet_address}: {e}")
            return []

    async def get_wallet_transactions(
        self,
        wallet_address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        max_transactions: int = 10000,
    ) -> List[Dict[str, Any]]:
        """Get transactions for a wallet address with caching and performance optimizations"""
        if not self.polygonscan_api_key:
            logger.warning("No Polygonscan API key configured. Using basic Web3 monitoring.")
            return await self._get_basic_transactions(wallet_address, start_block)

        try:
            # Create cache key for performance optimization
            cache_key = (
                f"{normalize_address(wallet_address)}_{start_block or 0}_{end_block or 'latest'}"
            )
            now = time.time()

            # Check cache first (significant performance boost)
            if cache_key in self.transaction_cache:
                cached_data, cache_time = self.transaction_cache[cache_key]
                if now - cache_time < self.cache_ttl:
                    self.cache_hits += 1
                    logger.debug(f"Cache hit for {wallet_address}")
                    return cached_data
                else:
                    # Cache expired, remove it
                    del self.transaction_cache[cache_key]

            # Rate limiting with performance tracking
            call_start = time.time()
            async with self.rate_limit_lock:
                time_since_last = now - self.last_api_call
                if time_since_last < self.api_call_delay:
                    sleep_time = self.api_call_delay - time_since_last
                    await asyncio.sleep(sleep_time)
                self.last_api_call = time.time()

            # Optimize block range queries for performance
            start_block = start_block or max(0, self.last_checked_block - 1000)
            current_block = (
                self.web3.eth.block_number
                if self.web3 and self.web3.is_connected()
                else start_block + 100
            )
            end_block = end_block or current_block

            # Prevent excessive block ranges (performance optimization)
            max_blocks = 2000  # Limit to 2000 blocks per call to prevent timeouts
            if end_block - start_block > max_blocks:
                end_block = start_block + max_blocks
                logger.debug(f"Limited block range to {max_blocks} blocks for performance")

            params = {
                "module": "account",
                "action": "txlist",
                "address": normalize_address(wallet_address),
                "startblock": start_block,
                "endblock": end_block,
                "sort": "desc",
                "apikey": self.polygonscan_api_key,
            }

            # Use optimized HTTP client settings for better performance
            connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
            timeout = aiohttp.ClientTimeout(total=15, connect=5)

            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(
                    "https://api.polygonscan.com/api", params=params
                ) as response:
                    call_time = time.time() - call_start
                    self.api_call_times.append(call_time)

                    # Keep only recent measurements for memory efficiency
                    if len(self.api_call_times) > self.max_call_times:
                        self.api_call_times = self.api_call_times[-self.max_call_times :]

                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "1" and data.get("message") == "OK":
                            transactions = data["result"]

                            # Limit transactions for performance
                            if len(transactions) > max_transactions:
                                transactions = transactions[:max_transactions]
                                logger.debug(
                                    f"Limited transactions to {max_transactions} for performance"
                                )

                            # Cache successful results
                            self.transaction_cache[cache_key] = (transactions.copy(), now)
                            self.cache_misses += 1

                            # Clean old cache entries periodically to prevent memory bloat
                            if len(self.transaction_cache) > 100:
                                self._cleanup_transaction_cache()

                            logger.debug(
                                f"Retrieved {len(transactions)} transactions for {wallet_address} in {call_time:.3f}s"
                            )
                            return transactions
                        else:
                            error_msg = data.get("message", "Unknown error")
                            logger.warning(
                                f"Polygonscan API error for {wallet_address}: {error_msg}"
                            )
                            return []
                    else:
                        logger.error(
                            f"Polygonscan API returned status {response.status} for {wallet_address}"
                        )
                        return []

        except asyncio.TimeoutError:
            logger.error(f"Timeout getting transactions for {wallet_address}")
            return []
        except Exception as e:
            logger.error(f"Error getting transactions for {wallet_address}: {e}")
            return []

    def _cleanup_transaction_cache(self):
        """Clean up expired cache entries for memory efficiency"""
        now = time.time()
        expired_keys = [
            key
            for key, (_, cache_time) in self.transaction_cache.items()
            if now - cache_time > self.cache_ttl
        ]
        for key in expired_keys:
            del self.transaction_cache[key]

        # Keep cache size reasonable to prevent memory exhaustion
        if len(self.transaction_cache) > 50:
            # Remove oldest 20% of entries
            items = list(self.transaction_cache.items())
            items.sort(key=lambda x: x[1][1])  # Sort by cache time
            remove_count = int(len(items) * 0.2)
            for key, _ in items[:remove_count]:
                del self.transaction_cache[key]

    async def _get_basic_transactions(
        self, wallet_address: str, start_block: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fallback method to get transactions using web3.py"""
        try:
            if not self.web3 or not self.web3.is_connected():
                logger.error("Not connected to Web3 provider")
                return []

            start_block = start_block or max(0, self.web3.eth.block_number - 100)
            current_block = self.web3.eth.block_number

            transactions = []

            # Limit block range for performance (only check recent blocks)
            for block_num in range(max(start_block, current_block - 50), current_block + 1):
                try:
                    block = self.web3.eth.get_block(block_num, full_transactions=True)
                    for tx in block.transactions:
                        if hasattr(tx, "from") and normalize_address(
                            tx["from"]
                        ) == normalize_address(wallet_address):
                            tx_dict = dict(tx)
                            tx_dict["blockNumber"] = block_num
                            tx_dict["timeStamp"] = block.timestamp
                            tx_dict["hash"] = tx.hash.hex()
                            transactions.append(tx_dict)
                except Exception as e:
                    logger.debug(f"Error processing block {block_num}: {e}")
                    continue

            logger.info(
                f"Basic monitoring found {len(transactions)} transactions for {wallet_address}"
            )
            return transactions

        except Exception as e:
            logger.error(f"Error in basic transaction monitoring: {e}")
            return []

    def detect_polymarket_trades(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter transactions to find Polymarket trades with performance optimizations"""
        polymarket_trades = []

        for tx in transactions:
            tx_hash = tx["hash"]

            # Skip already processed transactions (performance optimization)
            if tx_hash in self.processed_transactions:
                continue

            # Fast contract check (performance optimization)
            to_address = normalize_address(tx.get("to", ""))
            if to_address not in [
                normalize_address(contract) for contract in self.polymarket_contracts
            ]:
                continue

            # Parse the trade
            trade = self.parse_polymarket_trade(tx)
            if trade:
                polymarket_trades.append(trade)
                self.processed_transactions.add(tx_hash)

                # Prevent memory exhaustion by limiting processed transactions
                if len(self.processed_transactions) > self.max_processed_cache:
                    self._cleanup_processed_transactions()

        return polymarket_trades

    def _cleanup_processed_transactions(self):
        """Clean up old processed transactions to prevent memory exhaustion"""
        if len(self.processed_transactions) > self.max_processed_cache:
            # Remove oldest 20% of entries (simple FIFO eviction)
            remove_count = int(self.max_processed_cache * 0.2)
            self.processed_transactions = set(list(self.processed_transactions)[remove_count:])

    def parse_polymarket_trade(self, tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a transaction to extract Polymarket trade details with optimizations"""
        try:
            # Extract basic transaction details
            timestamp = datetime.fromtimestamp(int(tx.get("timeStamp", time.time())))

            # Skip recent transactions to avoid reorgs (performance optimization)
            if timestamp > datetime.now() - timedelta(seconds=30):
                return None

            # Calculate confidence score
            confidence_score = calculate_confidence_score(tx, self.trade_patterns)

            # Skip low confidence trades (performance optimization)
            if confidence_score < self.settings.monitoring.min_confidence_score:
                return None

            # Basic trade structure - this would need actual ABI decoding in production
            trade = {
                "tx_hash": tx["hash"],
                "timestamp": timestamp,
                "block_number": int(tx.get("blockNumber", 0)),
                "wallet_address": normalize_address(tx["from"]),
                "contract_address": normalize_address(tx["to"]),
                "value_eth": float(tx.get("value", 0)) / 10**18 if tx.get("value") else 0,
                "gas_used": int(tx.get("gasUsed", 0)) if tx.get("gasUsed") else 0,
                "gas_price": int(tx.get("gasPrice", 0)) if tx.get("gasPrice") else 0,
                "input_data": tx.get("input", "")[:1000],  # Truncate for performance
                "confidence_score": confidence_score,
                # Polymarket specific fields (these would be extracted from actual transaction data)
                "condition_id": tx.get("to", ""),  # Placeholder
                "market_id": "unknown",  # Placeholder
                "outcome_index": 0,  # Placeholder
                "side": "BUY",  # Placeholder
                "amount": float(tx.get("value", 0)) / 10**18 if tx.get("value") else 0,
                "price": 0.5,  # Placeholder
                "token_id": "unknown",  # Placeholder
            }

            return trade

        except Exception as e:
            logger.error(f"Error parsing Polymarket trade: {e}")
            return None

    async def clean_processed_transactions(self):
        """Clean up processed transactions cache (called periodically)"""
        self._cleanup_processed_transactions()
        self._cleanup_transaction_cache()

        # Log cache performance
        total_requests = self.cache_hits + self.cache_misses
        if total_requests > 0:
            hit_rate = self.cache_hits / total_requests
            logger.info(
                f"Cache performance: {self.cache_hits}/{total_requests} hits ({hit_rate:.1%})"
            )

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for monitoring"""
        total_requests = self.cache_hits + self.cache_misses
        avg_call_time = (
            sum(self.api_call_times) / len(self.api_call_times) if self.api_call_times else 0
        )

        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hits / total_requests if total_requests > 0 else 0,
            "avg_api_call_time": avg_call_time,
            "transaction_cache_size": len(self.transaction_cache),
            "processed_transactions_size": len(self.processed_transactions),
            "total_api_calls": len(self.api_call_times),
        }
