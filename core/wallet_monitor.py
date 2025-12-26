import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from config.settings import Settings

import re

import aiohttp
import numpy as np
from web3.exceptions import BadFunctionCallOutput, ContractLogicError, Web3ValidationError

from config.settings import settings
from core.market_maker_detector import MarketMakerDetector
from utils.helpers import calculate_confidence_score, normalize_address
from utils.security import secure_log
from utils.validation import InputValidator, ValidationError

logger = logging.getLogger(__name__)


class BatchTransactionProcessor:
    """Efficient batch processor for blockchain transactions"""

    def __init__(self, monitor: "WalletMonitor"):
        self.monitor = monitor
        self._batch_cache = {}
        self._batch_stats = {
            "total_processed": 0,
            "filtered_out": 0,
            "trades_detected": 0,
            "avg_processing_time": 0.0,
        }

    async def process_transaction_batch(
        self, transactions: List[Dict[str, Any]], wallet_address: str
    ) -> List[Dict[str, Any]]:
        """Process a batch of transactions efficiently"""
        start_time = time.time()

        try:
            # Phase 1: Pre-filter transactions (fast operations)
            filtered_txs = await self._pre_filter_transactions(transactions)
            self._batch_stats["filtered_out"] += len(transactions) - len(filtered_txs)

            if not filtered_txs:
                logger.debug(f"🧹 All transactions filtered out for {wallet_address}")
                return []

            # Phase 2: Batch confidence scoring
            confidence_scores = await self._batch_confidence_scoring(filtered_txs)

            # Phase 3: Parallel trade detection
            trades = await self._parallel_trade_detection(filtered_txs, confidence_scores)

            # Phase 4: Batch deduplication and processing
            unique_trades = self._deduplicate_trades(trades)
            self._batch_stats["trades_detected"] += len(unique_trades)

            # Phase 5: Batch update processed transactions in batch
            await self._batch_update_processed_transactions(unique_trades)

            processing_time = time.time() - start_time
            self._batch_stats["total_processed"] += len(transactions)
            self._batch_stats["avg_processing_time"] = (
                self._batch_stats["avg_processing_time"]
                * (self._batch_stats["total_processed"] - len(transactions))
                + processing_time * len(transactions)
            ) / self._batch_stats["total_processed"]

            logger.info(
                f"⚡ Batch processed {len(transactions)} txs -> {len(unique_trades)} trades "
                f"for {wallet_address} in {processing_time:.2f}s "
                f"(avg: {self._batch_stats['avg_processing_time']:.4f}s/tx)"
            )

            return unique_trades

        except Exception as e:
            logger.error(f"❌ Error processing transaction batch: {e}", exc_info=True)
            return []

    async def _pre_filter_transactions(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fast pre-filtering of transactions before deep processing"""
        # Filter 1: Skip already processed transactions
        unprocessed_txs = [
            tx for tx in transactions if tx["hash"] not in self.monitor.processed_transactions
        ]

        # Filter 2: Skip transactions to non-Polymarket contracts
        polymarket_contract_set = {normalize_address(c) for c in self.monitor.polymarket_contracts}
        relevant_txs = [
            tx
            for tx in unprocessed_txs
            if normalize_address(tx.get("to", "")) in polymarket_contract_set
        ]

        # Filter 3: Skip very old transactions
        current_time = int(time.time())
        recent_txs = [
            tx
            for tx in relevant_txs
            if abs(current_time - int(tx.get("timeStamp", current_time))) < 3600  # Last hour
        ]

        logger.debug(
            f"🧹 Pre-filtering: {len(transactions)} -> {len(unprocessed_txs)} (unprocessed) "
            f"-> {len(relevant_txs)} (relevant) -> {len(recent_txs)} (recent)"
        )

        return recent_txs

    async def _batch_confidence_scoring(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate confidence scores for a batch of transactions efficiently"""
        # Prepare transaction data for vectorized processing
        tx_data = [
            {
                "value": float(tx.get("value", 0)),
                "gas_used": int(tx.get("gasUsed", 0)),
                "input_length": len(tx.get("input", "")),
                "timestamp": int(tx.get("timeStamp", time.time())),
            }
            for tx in transactions
        ]

        # Vectorized confidence scoring using numpy
        values = np.array([d["value"] for d in tx_data])
        gas_used = np.array([d["gas_used"] for d in tx_data])
        input_lengths = np.array([d["input_length"] for d in tx_data])

        # Base scores
        scores = np.full(len(transactions), 0.3)

        # Value-based scoring
        scores += np.where(values > 0, 0.2, np.where(input_lengths > 100, 0.3, 0))

        # Gas usage scoring
        gas_mask = (gas_used > 50000) & (gas_used < 500000)
        scores += np.where(gas_mask, 0.2, np.where(gas_used > 10000, 0.1, 0))

        # Input length scoring
        scores += np.where(input_lengths > 100, 0.1, 0)

        # Pattern matching scoring (batch version)
        pattern_scores = await self._batch_pattern_scoring(transactions)
        scores += pattern_scores

        # Clip to 0.0-1.0 range
        scores = np.clip(scores, 0.0, 1.0)

        return {tx["hash"]: float(score) for tx, score in zip(transactions, scores)}

    async def _batch_pattern_scoring(self, transactions: List[Dict[str, Any]]) -> np.ndarray:
        """Batch pattern matching for trade detection"""
        pattern_scores = np.zeros(len(transactions))

        # Compile patterns once
        patterns = [re.compile(p, re.IGNORECASE) for p in self.monitor.trade_patterns]

        # Process in chunks to avoid memory issues
        chunk_size = 50
        for i in range(0, len(transactions), chunk_size):
            chunk = transactions[i : i + chunk_size]
            chunk_inputs = [tx.get("input", "").lower() for tx in chunk]

            for pattern in patterns:
                matches = np.array([bool(pattern.search(inp)) for inp in chunk_inputs])
                pattern_scores[i : i + len(chunk)] += np.where(matches, 0.1, 0)

        return pattern_scores

    async def _parallel_trade_detection(
        self, transactions: List[Dict[str, Any]], confidence_scores: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Detect trades in parallel using asyncio.gather"""
        # Prepare tasks
        tasks = []
        for tx in transactions:
            tx_hash = tx["hash"]
            confidence_score = confidence_scores.get(tx_hash, 0.0)

            # Skip low confidence transactions early
            if confidence_score < self.monitor.settings.monitoring.min_confidence_score:
                continue

            task = asyncio.create_task(self._detect_single_trade(tx, confidence_score))
            tasks.append(task)

        # Execute in parallel with rate limiting
        results = []
        semaphore = asyncio.Semaphore(10)  # Limit concurrent operations

        async def limited_task(task):
            async with semaphore:
                return await task

        limited_tasks = [limited_task(task) for task in tasks]
        results = await asyncio.gather(*limited_tasks, return_exceptions=True)

        # Filter out exceptions and None results
        trades = [r for r in results if r is not None and not isinstance(r, Exception)]

        return trades

    async def _detect_single_trade(
        self, tx: Dict[str, Any], confidence_score: float
    ) -> Optional[Dict[str, Any]]:
        """Detect a single trade with confidence score"""
        try:
            timestamp = datetime.fromtimestamp(int(tx.get("timeStamp", time.time())))

            # Skip recent transactions to avoid reorgs
            if timestamp > datetime.now() - timedelta(seconds=30):
                return None

            # Parse trade (optimized version)
            trade = {
                "tx_hash": tx["hash"],
                "timestamp": timestamp,
                "block_number": int(tx.get("blockNumber", 0)),
                "wallet_address": normalize_address(tx["from"]),
                "contract_address": normalize_address(tx["to"]),
                "value_eth": float(tx.get("value", 0)) / 10**18 if tx.get("value") else 0,
                "gas_used": int(tx.get("gasUsed", 0)),
                "gas_price": int(tx.get("gasPrice", 0)),
                "input_data": tx.get("input", "")[:200],  # Truncate for performance
                "condition_id": self._extract_condition_id(tx),
                "market_id": self._derive_market_id(tx),
                "outcome_index": self._extract_outcome_index(tx),
                "side": self._determine_trade_side_batch(tx),
                "amount": self._extract_trade_amount_batch(tx),
                "price": self._extract_trade_price_batch(tx),
                "token_id": self._extract_token_id(tx),
                "confidence_score": confidence_score,
            }

            return trade

        except Exception as e:
            logger.debug(f"Error parsing trade {tx['hash']}: {e}")
            return None

    def _deduplicate_trades(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate trades from batch results"""
        seen_hashes = set()
        unique_trades = []

        for trade in trades:
            if trade["tx_hash"] in seen_hashes:
                continue
            seen_hashes.add(trade["tx_hash"])
            unique_trades.append(trade)

        if len(trades) != len(unique_trades):
            logger.debug(f"🧹 Deduplicated {len(trades)} -> {len(unique_trades)} trades")

        return unique_trades

    async def _batch_update_processed_transactions(self, trades: List[Dict[str, Any]]):
        """Update processed transactions in batch"""
        new_hashes = {trade["tx_hash"] for trade in trades}
        self.monitor.processed_transactions.update(new_hashes)

        # Periodic cleanup
        if len(self.monitor.processed_transactions) > 10000:
            await self.monitor.clean_processed_transactions()

    def _extract_condition_id(self, tx: Dict[str, Any]) -> str:
        """Extract condition ID from transaction"""
        # This is a placeholder - in production this would decode the actual transaction
        input_data = tx.get("input", "")
        if len(input_data) > 10:
            # Simple heuristic - extract first 64 chars after method signature
            return input_data[10:74] if len(input_data) > 74 else input_data[10:]
        return tx.get("to", "")

    def _derive_market_id(self, tx: Dict[str, Any]) -> str:
        """Derive market ID from transaction data"""
        # Placeholder - would decode from actual transaction data
        return f"market_{hash(tx.get('to', '')) % 1000}"

    def _extract_outcome_index(self, tx: Dict[str, Any]) -> int:
        """Extract outcome index from transaction"""
        # Placeholder - would decode from actual transaction data
        input_data = tx.get("input", "")
        return hash(input_data) % 2  # Simple heuristic

    def _determine_trade_side_batch(self, tx: Dict[str, Any]) -> str:
        """Determine trade side (BUY/SELL)"""
        # Simple heuristic based on gas price patterns
        gas_price = int(tx.get("gasPrice", 0))
        return "BUY" if gas_price > 50000000000 else "SELL"  # 50 gwei threshold

    def _extract_trade_amount_batch(self, tx: Dict[str, Any]) -> float:
        """Extract trade amount"""
        value = float(tx.get("value", 0))
        return value / 10**18 if value > 0 else 1.0  # Default to 1 if no value

    def _extract_trade_price_batch(self, tx: Dict[str, Any]) -> float:
        """Extract trade price"""
        # Placeholder - would decode from actual transaction data
        return 0.5 + (hash(tx.get("hash", "")) % 100) / 200  # Random-ish price

    def _extract_token_id(self, tx: Dict[str, Any]) -> str:
        """Extract token ID from transaction"""
        # Placeholder - would decode from actual transaction data
        return f"token_{hash(tx.get('input', '')) % 10000}"

    def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics"""
        return self._batch_stats.copy()


class WalletMonitor:
    """Monitor wallet transactions for copy trading opportunities with performance optimizations"""

    def __init__(self, settings: "Settings") -> None:
        """
        Initialize wallet monitor with configuration settings.

        Args:
            settings (Settings): Application configuration settings
        """
        self.settings = settings
        self.web3 = None
        self.polygonscan_api_key = settings.network.polygonscan_api_key

        # Target wallets to monitor
        self.target_wallets = settings.monitoring.target_wallets

        # Initialize market maker detector
        self.market_maker_detector = MarketMakerDetector(settings)

        # Transaction processing state
        self.processed_transactions: set = set()
        self.max_processed_cache = 100000  # Limit cache size for memory efficiency
        self.last_checked_block = 0

        # Rate limiting
        self.api_call_delay = 0.1  # 10 calls per second max for v2 API
        self.last_api_call = 0
        self.rate_limit_lock = asyncio.Lock()

        # Polymarket contract addresses
        self.polymarket_contracts = [
            "0x4D97DCc4e5c36A3b0c9072A2F5B3C1b1C1B1B1B1",  # Placeholder - replace with real contracts
            "0x8c16f85a4d5f8f23d29e9c7e3d4a3a5a6e4f2b2e",  # Polymarket CTF Exchange
        ]

        # Trade patterns for confidence scoring (regex patterns)
        self.trade_patterns = [
            r"buy|purchase|0x6947ac42",  # Buy method signatures
            r"sell|0x6947ac43",  # Sell method signatures
            r"trade|swap|0x7c025200",  # Trade method signatures
            r"0x8a8c523c",  # Polymarket specific patterns
        ]

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

        # Wallet trade tracking for batch processing
        self.wallet_trade_history: Dict[str, List[Dict[str, Any]]] = {}
        self.wallet_last_trade_time: Dict[str, datetime] = {}

        # Initialize trade history for all target wallets
        for wallet in self.target_wallets:
            self.wallet_trade_history[wallet] = []
            self.wallet_last_trade_time[wallet] = datetime.min

        logger.info(f"Initialized wallet monitor for {len(self.target_wallets)} wallets")

    async def monitor_wallets(self) -> List[Dict[str, Any]]:
        """Main monitoring function with batch processing"""
        current_block = (
            self.web3.eth.block_number
            if self.web3.is_connected()
            else self.last_checked_block + 100
        )
        all_detected_trades = []

        logger.info(
            f"🔍 Monitoring {len(self.target_wallets)} wallets from block {self.last_checked_block} to {current_block}"
        )

        # Process wallets in batches to avoid overwhelming APIs
        batch_size = 5
        for i in range(0, len(self.target_wallets), batch_size):
            wallet_batch = self.target_wallets[i : i + batch_size]

            # Get transactions for all wallets in batch
            batch_tasks = [
                self.get_wallet_transactions(wallet, self.last_checked_block, current_block)
                for wallet in wallet_batch
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Process each wallet's transactions
            for wallet, transactions in zip(wallet_batch, batch_results):
                if isinstance(transactions, Exception):
                    logger.error(f"❌ Error getting transactions for {wallet}: {transactions}")
                    continue

                if not transactions:
                    continue

                # Use batch processor for efficient trade detection
                batch_processor = BatchTransactionProcessor(self)
                trades = await batch_processor.process_transaction_batch(transactions, wallet)

                if trades:
                    all_detected_trades.extend(trades)

        self.last_checked_block = current_block

        # Perform market maker analysis for all wallets (weekly or when significant new data)
        if self._should_run_market_maker_analysis():
            logger.info("🎯 Running market maker analysis for all wallets")
            analysis_tasks = [
                self._analyze_wallet_behavior(wallet) for wallet in self.target_wallets
            ]
            analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

            market_maker_analyses = []
            for result in analysis_results:
                if isinstance(result, dict):
                    market_maker_analyses.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Error in market maker analysis: {result}")

            # Save analysis data
            self.market_maker_detector.save_data()

            # Log summary
            if market_maker_analyses:
                market_makers = sum(
                    1 for a in market_maker_analyses if a.get("classification") == "market_maker"
                )
                logger.info(
                    f"🎯 Market maker analysis complete: {market_makers}/{len(market_maker_analyses)} potential market makers detected"
                )

        # Clean up processed transactions cache periodically
        if len(self.processed_transactions) > self.max_processed_cache:
            await self.clean_processed_transactions()

        return all_detected_trades

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

        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"Network error monitoring wallet {wallet_address}: {str(e)[:100]}")
            return []
        except (ValueError, TypeError, KeyError) as e:
            logger.error(
                f"Data validation error monitoring wallet {wallet_address}: {str(e)[:100]}"
            )
            return []
        except Exception as e:
            logger.critical(
                f"Unexpected error monitoring wallet {wallet_address}: {str(e)}", exc_info=True
            )
            return []

    def _should_use_polygonscan_api(self) -> bool:
        """Determine if Polygonscan API should be used"""
        return bool(self.polygonscan_api_key)

    def _get_polygonscan_api_url(self) -> str:
        """Get the appropriate Polygonscan API URL (v1 or v2)"""
        # Use v2 API if configured, fallback to v1
        return "https://api.polygonscan.com/v2/api"

    def _get_polygonscan_headers(self) -> Dict[str, str]:
        """Get headers for Polygonscan API requests"""
        headers = {
            "User-Agent": "Polymarket-Copy-Bot/1.0",
            "Accept": "application/json",
        }
        return headers

    async def get_wallet_transactions(
        self,
        wallet_address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        max_transactions: int = 10000,
    ) -> List[Dict[str, Any]]:
        """Get transactions for a wallet address with caching and performance optimizations"""
        if not self._should_use_polygonscan_api():
            logger.warning("No Polygonscan API key configured. Using basic Web3 monitoring.")
            return await self._get_basic_transactions(wallet_address, start_block)

        logger.debug(f"Using Polygonscan v2 API for {wallet_address}")

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

            # Prepare v2 API request
            url = self._get_polygonscan_api_url()
            headers = self._get_polygonscan_headers()

            # For v2 API, some parameters might be in headers
            headers["X-API-Key"] = self.polygonscan_api_key

            params = {
                "module": "account",
                "action": "txlist",
                "address": normalize_address(wallet_address),
                "startblock": start_block,
                "endblock": end_block,
                "sort": "desc",
                # API key moved to headers for v2
            }

            # Use optimized HTTP client settings for better performance
            connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
            timeout = aiohttp.ClientTimeout(total=15, connect=5)

            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    call_time = time.time() - call_start
                    self.api_call_times.append(call_time)

                    # Keep only recent measurements for memory efficiency
                    if len(self.api_call_times) > self.max_call_times:
                        self.api_call_times = self.api_call_times[-self.max_call_times :]

                    if response.status == 200:
                        data = await response.json()

                        # Validate API response structure
                        InputValidator.validate_api_response(data, dict)

                        # Handle both v1 and v2 API response formats
                        if (data.get("status") == "1" and data.get("message") == "OK") or data.get(
                            "status"
                        ) == "success":
                            transactions = data.get("result", [])

                            # Handle different response structures
                            if isinstance(transactions, dict) and "transactions" in transactions:
                                transactions = transactions["transactions"]

                            if not isinstance(transactions, list):
                                logger.warning(
                                    f"Unexpected transaction data format for {wallet_address}: {type(transactions)}"
                                )
                                return []

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
                            error_msg = data.get("message", data.get("error", "Unknown error"))
                            logger.warning(
                                f"Polygonscan v2 API error for {wallet_address}: {error_msg} (status: {data.get('status')})"
                            )
                            return []
                    else:
                        # Try to get error details from response
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get("message", f"HTTP {response.status}")
                        except:
                            error_msg = f"HTTP {response.status}"

                        logger.error(
                            f"Polygonscan v2 API returned status {response.status} for {wallet_address}: {error_msg}"
                        )
                        return []

        except asyncio.TimeoutError:
            logger.error(f"Timeout getting transactions for {wallet_address}")
            return []
        except (ConnectionError, aiohttp.ClientError) as e:
            logger.error(f"Network error getting transactions for {wallet_address}: {str(e)[:100]}")
            return []
        except (ValueError, TypeError, KeyError) as e:
            logger.error(
                f"Data validation error getting transactions for {wallet_address}: {str(e)[:100]}"
            )
            return []
        except Exception as e:
            logger.critical(
                f"Unexpected error getting transactions for {wallet_address}: {str(e)}",
                exc_info=True,
            )
            return []

    def _generate_transaction_cache_key(
        self, wallet_address: str, start_block: Optional[int], end_block: Optional[int]
    ) -> str:
        """Generate a unique cache key for the transaction request"""
        return f"{normalize_address(wallet_address)}_{start_block or 0}_{end_block or 'latest'}"

    async def _check_transaction_cache_validity(
        self, cache_key: str, wallet_address: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Check if valid cached data exists for the request"""
        if cache_key not in self.transaction_cache:
            return None

        cached_data, cache_time = self.transaction_cache[cache_key]
        now = time.time()

        if now - cache_time < self.cache_ttl:
            self.cache_hits += 1
            logger.debug(f"Cache hit for {wallet_address}")
            return cached_data
        else:
            # Cache expired, remove it
            del self.transaction_cache[cache_key]
            return None

    async def _apply_transaction_rate_limiting(self) -> None:
        """Apply rate limiting before making API calls"""
        async with self.rate_limit_lock:
            now = time.time()
            time_since_last = now - self.last_api_call
            if time_since_last < self.api_call_delay:
                sleep_time = self.api_call_delay - time_since_last
                await asyncio.sleep(sleep_time)
            self.last_api_call = time.time()

    async def _optimize_transaction_block_range(
        self, wallet_address: str, start_block: Optional[int], end_block: Optional[int]
    ) -> Tuple[int, int]:
        """Optimize block range for transaction queries"""
        start_block = start_block or max(0, self.last_checked_block - 1000)
        current_block = (
            self.web3.eth.block_number
            if self.web3 and self.web3.is_connected()
            else start_block + 100
        )
        end_block = end_block or current_block

        # Prevent excessive block ranges
        max_blocks = 2000
        if end_block - start_block > max_blocks:
            end_block = start_block + max_blocks
            logger.debug(f"Limited block range to {max_blocks} blocks for performance")

        return start_block, end_block

    def _cleanup_transaction_cache(self) -> None:
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
                except (Web3ValidationError, BadFunctionCallOutput, ValueError) as e:
                    logger.debug(f"Block processing error for block {block_num}: {str(e)[:100]}")
                    continue
                except Exception as e:
                    logger.debug(f"Unexpected error processing block {block_num}: {str(e)[:100]}")
                    continue

            logger.info(
                f"Basic monitoring found {len(transactions)} transactions for {wallet_address}"
            )
            return transactions

        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Network error in basic transaction monitoring: {str(e)[:100]}")
            return []
        except (Web3ValidationError, ValueError, TypeError) as e:
            logger.error(f"Data validation error in basic transaction monitoring: {str(e)[:100]}")
            return []
        except Exception as e:
            logger.critical(
                f"Unexpected error in basic transaction monitoring: {str(e)}", exc_info=True
            )
            return []

    def detect_polymarket_trades(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect Polymarket trades with input validation"""
        polymarket_trades = []

        for tx in transactions:
            try:
                # Validate transaction data
                validated_tx = InputValidator.validate_transaction_data(tx)
                tx_hash = validated_tx["hash"]

                # Skip already processed transactions (performance optimization)
                if tx_hash in self.processed_transactions:
                    continue

                # Fast contract check (performance optimization)
                to_address = validated_tx["to"]
                if to_address not in [
                    normalize_address(contract) for contract in self.polymarket_contracts
                ]:
                    continue

                # Parse the trade with validated data
                trade = self.parse_polymarket_trade(validated_tx)
                if trade:
                    polymarket_trades.append(trade)
                    self.processed_transactions.add(tx_hash)

                    # Prevent memory exhaustion by limiting processed transactions
                    if len(self.processed_transactions) > self.max_processed_cache:
                        self._cleanup_processed_transactions()

            except ValidationError as e:
                logger.warning(f"Skipping invalid transaction {tx.get('hash', 'unknown')}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error processing transaction {tx.get('hash', 'unknown')}: {e}")
                continue

        return polymarket_trades

    def _cleanup_processed_transactions(self) -> None:
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

        except (ValueError, TypeError, KeyError, IndexError) as e:
            logger.error(f"Data parsing error in parse_polymarket_trade: {str(e)[:100]}")
            return None
        except Exception as e:
            logger.critical(f"Unexpected error parsing Polymarket trade: {str(e)}", exc_info=True)
            return None

    async def clean_processed_transactions(self) -> None:
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

        # Get batch processor stats if available
        batch_stats = {}
        try:
            batch_processor = BatchTransactionProcessor(self)
            batch_stats = batch_processor.get_batch_stats()
        except Exception:
            pass

        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hits / total_requests if total_requests > 0 else 0,
            "avg_api_call_time": avg_call_time,
            "transaction_cache_size": len(self.transaction_cache),
            "processed_transactions_size": len(self.processed_transactions),
            "total_api_calls": len(self.api_call_times),
            "batch_processing_stats": batch_stats,
        }

    def _should_run_market_maker_analysis(self) -> bool:
        """Determine if market maker analysis should run based on schedule and data changes"""
        # Run analysis weekly or if we haven't run it in the last 7 days
        last_analysis_file = self.market_maker_detector.behavior_dir / "last_analysis.txt"

        try:
            if last_analysis_file.exists():
                with open(last_analysis_file, "r") as f:
                    last_run = datetime.fromisoformat(f.read().strip())
                    days_since = (datetime.now() - last_run).days
                    return days_since >= 7
            else:
                # First run
                return True
        except Exception:
            # If we can't read the file, run analysis
            return True

    async def _analyze_wallet_behavior(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Analyze market maker behavior for a single wallet"""
        try:
            # Get extended trade history for analysis (longer period than monitoring)
            extended_trades = await self.get_wallet_trade_history(
                wallet_address, days_back=14  # 2 weeks for better analysis
            )

            if not extended_trades:
                logger.debug(f"No trade history found for {wallet_address}")
                return None

            # Perform market maker analysis
            analysis = await self.market_maker_detector.analyze_wallet_behavior(
                wallet_address, extended_trades
            )

            # Update last analysis timestamp
            last_analysis_file = self.market_maker_detector.behavior_dir / "last_analysis.txt"
            with open(last_analysis_file, "w") as f:
                f.write(datetime.now().isoformat())

            return analysis

        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.error(
                f"Network error analyzing wallet behavior for {wallet_address}: {str(e)[:100]}"
            )
            return None
        except (ValueError, TypeError, KeyError) as e:
            logger.error(
                f"Data validation error analyzing wallet behavior for {wallet_address}: {str(e)[:100]}"
            )
            return None
        except Exception as e:
            logger.critical(
                f"Unexpected error analyzing wallet behavior for {wallet_address}: {str(e)}",
                exc_info=True,
            )
            return None

    async def get_wallet_trade_history(
        self, wallet_address: str, days_back: int = 7, max_trades: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get extended trade history for market maker analysis"""
        try:
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)

            # Get transactions from the extended period
            transactions = await self.get_wallet_transactions(
                wallet_address,
                start_block=None,  # Will be calculated from time
                end_block=None,
                max_transactions=max_trades * 2,  # Get more to filter for trades
            )

            if not transactions:
                return []

            # Filter transactions by time and convert to trade format
            trade_history = []
            for tx in transactions:
                tx_time = datetime.fromtimestamp(int(tx.get("timeStamp", 0)))
                if start_time <= tx_time <= end_time:
                    trade = self.parse_polymarket_trade(tx)
                    if trade:
                        trade_history.append(trade)

            # Sort by timestamp
            trade_history.sort(key=lambda x: x.get("timestamp", datetime.min))

            logger.debug(
                f"Retrieved {len(trade_history)} trades for {wallet_address} over {days_back} days"
            )
            return trade_history[:max_trades]  # Limit final results

        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.error(
                f"Network error getting trade history for {wallet_address}: {str(e)[:100]}"
            )
            return []
        except (ValueError, TypeError, KeyError) as e:
            logger.error(
                f"Data validation error getting trade history for {wallet_address}: {str(e)[:100]}"
            )
            return []
        except Exception as e:
            logger.critical(
                f"Unexpected error getting trade history for {wallet_address}: {str(e)}",
                exc_info=True,
            )
            return []

    async def get_market_maker_summary(self) -> Dict[str, Any]:
        """Get summary of market maker analysis for all wallets"""
        return await self.market_maker_detector.get_market_maker_summary()

    async def get_wallet_classification_report(self, wallet_address: str) -> Dict[str, Any]:
        """Get detailed classification report for a specific wallet"""
        return await self.market_maker_detector.get_wallet_classification_report(wallet_address)

    async def detect_behavior_changes(self) -> List[Dict[str, Any]]:
        """Detect wallets with recent classification changes"""
        return await self.market_maker_detector.detect_classification_changes()
