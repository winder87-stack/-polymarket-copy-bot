"""
WebSocket-based Wallet Monitor for Real-time Trade Detection

Provides:
- Real-time transaction monitoring via WebSocket
- Event-driven trade detection pipeline
- Automatic fallback to polling on WebSocket failure
- Single wallet monitoring (pilot implementation)
- Performance metrics and latency tracking
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from core.websocket_manager import ConnectionState, WebSocketManager
from utils.helpers import normalize_address
from utils.rate_limited_client import RateLimitedPolygonscanClient

logger = logging.getLogger(__name__)


class WebSocketWalletMonitor:
    """
    Real-time wallet monitoring using WebSocket with polling fallback.

    This is a pilot implementation for single wallet monitoring before
    full rollout to all wallets.

    Features:
    - WebSocket-based real-time transaction monitoring
    - Event-driven trade detection (sub-second latency)
    - Automatic fallback to polling when WebSocket fails
    - Performance benchmarking (latency comparison)
    - Maintains all existing risk management safeguards

    Architecture:
        1. Attempts WebSocket connection to blockchain provider
        2. Subscribes to wallet transaction events
        3. Processes events through existing trade detection pipeline
        4. Falls back to polling if WebSocket fails/disconnects
        5. Tracks performance metrics for comparison
    """

    def __init__(
        self,
        wallet_address: str,
        ws_url: str,
        polygonscan_client: Optional[RateLimitedPolygonscanClient],
        trade_detection_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        fallback_polling_interval: int = 15,
    ) -> None:
        """
        Initialize WebSocket wallet monitor.

        Args:
            wallet_address: Wallet address to monitor
            ws_url: WebSocket URL for blockchain provider
            polygonscan_client: Polygonscan client for fallback polling
            trade_detection_callback: Callback function for detected trades
            fallback_polling_interval: Polling interval when WebSocket unavailable (seconds)
        """
        self.wallet_address = normalize_address(wallet_address)
        self.ws_url = ws_url
        self.polygonscan_client = polygonscan_client
        self.trade_detection_callback = trade_detection_callback
        self.fallback_polling_interval = fallback_polling_interval

        # WebSocket manager
        self.ws_manager: Optional[WebSocketManager] = None

        # Fallback polling
        self.fallback_active = False
        self.fallback_task: Optional[asyncio.Task] = None
        self.last_polled_block = 0

        # Performance metrics
        self.metrics = {
            "websocket_messages": 0,
            "websocket_trades_detected": 0,
            "polling_cycles": 0,
            "polling_trades_detected": 0,
            "fallback_activations": 0,
            "avg_websocket_latency": 0.0,
            "avg_polling_latency": 0.0,
            "websocket_uptime": 0.0,
            "polling_uptime": 0.0,
            "last_trade_detection_time": None,
            "last_trade_detection_method": None,
        }

        # Processed transactions cache (for deduplication)
        self.processed_tx_hashes: set[str] = set()
        self.max_cache_size = 10000

        logger.info(
            f"WebSocket wallet monitor initialized for {self.wallet_address[:6]}...{self.wallet_address[-4:]}"
        )

    async def start(self) -> bool:
        """
        Start monitoring (WebSocket with polling fallback).

        Returns:
            True if started successfully, False otherwise
        """
        logger.info(
            f"🚀 Starting WebSocket monitoring for wallet {self.wallet_address[-6:]}"
        )

        # Initialize WebSocket manager
        self.ws_manager = WebSocketManager(
            ws_url=self.ws_url,
            wallet_address=self.wallet_address,
            on_message=self._handle_websocket_message,
            on_error=self._handle_websocket_error,
            alert_on_disconnect=True,
        )

        # Attempt WebSocket connection
        if await self.ws_manager.connect():
            # Subscribe to wallet transactions
            await self._subscribe_to_wallet_transactions()
            logger.info("✅ WebSocket monitoring active")
            return True
        else:
            # Fallback to polling immediately
            logger.warning(
                "⚠️ WebSocket connection failed - activating polling fallback"
            )
            await self._activate_fallback_polling()
            return False

    async def stop(self) -> None:
        """Stop monitoring"""
        logger.info(
            f"🛑 Stopping WebSocket monitoring for wallet {self.wallet_address[-6:]}"
        )

        # Stop WebSocket
        if self.ws_manager:
            await self.ws_manager.disconnect()

        # Stop fallback polling
        if self.fallback_task:
            self.fallback_task.cancel()
            try:
                await self.fallback_task
            except asyncio.CancelledError:
                pass

        logger.info("✅ Monitoring stopped")

    async def _subscribe_to_wallet_transactions(self) -> None:
        """Subscribe to wallet transaction events via WebSocket"""
        if not self.ws_manager:
            return

        # Subscribe to new pending transactions for this wallet
        # Format depends on provider (Alchemy, QuickNode, etc.)
        subscription_params = {
            "id": f"wallet_{self.wallet_address}",
            "params": [
                "newPendingTransactions",
                {"address": self.wallet_address},  # Provider-specific format
            ],
        }

        # Alternative: Subscribe to new blocks and filter transactions
        # This is more reliable across providers
        block_subscription = {
            "id": f"blocks_{self.wallet_address}",
            "params": ["newHeads"],
        }

        # Subscribe to both (provider may support one or both)
        await self.ws_manager.subscribe(subscription_params)
        await self.ws_manager.subscribe(block_subscription)

        logger.info(
            f"📡 Subscribed to transaction events for {self.wallet_address[-6:]}"
        )

    async def _handle_websocket_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming WebSocket message"""
        try:
            # Parse message based on provider format
            # Example formats:
            # - Alchemy: {"jsonrpc": "2.0", "method": "eth_subscription", "params": {...}}
            # - QuickNode: Similar format
            # - Direct RPC: {"result": {...}}

            method = message.get("method")
            params = message.get("params", {})

            if method == "eth_subscription":
                # Subscription notification
                subscription_data = params.get("result", {})
                await self._process_subscription_data(subscription_data)

            elif "result" in message:
                # Direct result (block data, transaction data, etc.)
                await self._process_transaction_data(message["result"])

            self.metrics["websocket_messages"] += 1

        except Exception as e:
            logger.exception(f"❌ Error handling WebSocket message: {e}")

    async def _process_subscription_data(self, data: Dict[str, Any]) -> None:
        """Process subscription data (transaction or block)"""
        # Check if this is a transaction for our wallet
        if isinstance(data, str):
            # Transaction hash - fetch full transaction details
            tx_hash = data
            await self._process_transaction_hash(tx_hash)
        elif isinstance(data, dict):
            # Block data - check for transactions
            if "transactions" in data:
                for tx in data["transactions"]:
                    if self._is_wallet_transaction(tx):
                        await self._process_transaction(tx)

    async def _process_transaction_data(self, data: Any) -> None:
        """Process transaction data"""
        if isinstance(data, dict):
            if self._is_wallet_transaction(data):
                await self._process_transaction(data)
        elif isinstance(data, str):
            # Transaction hash
            await self._process_transaction_hash(data)

    async def _process_transaction_hash(self, tx_hash: str) -> None:
        """Fetch and process transaction by hash"""
        if not self.polygonscan_client:
            return

        try:
            # Fetch transaction details
            tx = await self.polygonscan_client.get_transaction(tx_hash)
            if tx and self._is_wallet_transaction(tx):
                await self._process_transaction(tx)
        except Exception as e:
            logger.debug(f"Error fetching transaction {tx_hash}: {e}")

    async def _process_transaction(self, tx: Dict[str, Any]) -> None:
        """Process a transaction and detect trades"""
        start_time = time.time()

        try:
            tx_hash = tx.get("hash") or tx.get("transactionHash")
            if not tx_hash:
                return

            # Deduplication check
            if tx_hash in self.processed_tx_hashes:
                return

            # Add to processed cache
            self.processed_tx_hashes.add(tx_hash)
            if len(self.processed_tx_hashes) > self.max_cache_size:
                # Remove oldest entries (simple FIFO)
                self.processed_tx_hashes.pop()

            # Detect trades using existing pipeline
            # This integrates with the existing trade detection logic
            trades = await self._detect_trades_from_transaction(tx)

            if trades:
                self.metrics["websocket_trades_detected"] += len(trades)
                self.metrics["last_trade_detection_time"] = datetime.now(
                    timezone.utc
                ).isoformat()
                self.metrics["last_trade_detection_method"] = "websocket"

                # Calculate latency
                latency = time.time() - start_time
                self._update_latency_metric("websocket", latency)

                # Callback with detected trades
                if self.trade_detection_callback:
                    for trade in trades:
                        await self._safe_callback(self.trade_detection_callback, trade)

                logger.info(
                    f"⚡ WebSocket: Detected {len(trades)} trades in {latency * 1000:.1f}ms "
                    f"(tx: {tx_hash[:8]}...)"
                )

        except Exception as e:
            logger.exception(f"❌ Error processing transaction: {e}")

    def _is_wallet_transaction(self, tx: Dict[str, Any]) -> bool:
        """Check if transaction involves monitored wallet"""
        wallet_lower = self.wallet_address.lower()

        # Check from/to addresses
        from_addr = (tx.get("from") or "").lower()
        to_addr = (tx.get("to") or "").lower()

        return wallet_lower in from_addr or wallet_lower in to_addr

    async def _detect_trades_from_transaction(
        self, tx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect trades from transaction using existing detection logic.

        This integrates with the existing BatchTransactionProcessor
        and trade detection pipeline from wallet_monitor.py
        """
        # TODO: Integrate with existing trade detection logic
        # For now, return empty list (placeholder)
        # In production, this would call the existing detection methods

        # Example integration:
        # from core.wallet_monitor import BatchTransactionProcessor
        # processor = BatchTransactionProcessor(self.monitor)
        # trades = await processor.process_transaction_batch([tx], self.wallet_address)
        # return trades

        return []

    async def _handle_websocket_error(self, error: Exception) -> None:
        """Handle WebSocket errors"""
        logger.warning(f"⚠️ WebSocket error: {error}")

        # Check if we should activate fallback
        if self.ws_manager and self.ws_manager.state == ConnectionState.FAILED:
            if not self.fallback_active:
                await self._activate_fallback_polling()

    async def _activate_fallback_polling(self) -> None:
        """Activate polling fallback when WebSocket unavailable"""
        if self.fallback_active:
            return

        logger.info(
            f"🔄 Activating polling fallback (interval: {self.fallback_polling_interval}s)"
        )

        self.fallback_active = True
        self.metrics["fallback_activations"] += 1
        self.metrics["polling_uptime"] = time.time()

        # Start polling task
        self.fallback_task = asyncio.create_task(self._polling_loop())

        # Send alert
        try:
            from utils.alerts import send_telegram_alert

            await send_telegram_alert(
                f"⚠️ **Polling Fallback Activated**\n"
                f"**Wallet:** `{self.wallet_address[-6:]}`\n"
                f"**Reason:** WebSocket unavailable\n"
                f"**Polling Interval:** {self.fallback_polling_interval}s"
            )
        except Exception as e:
            logger.debug(f"Error sending fallback alert: {e}")

    async def _polling_loop(self) -> None:
        """Polling fallback loop"""
        logger.info(f"🔄 Starting polling fallback for {self.wallet_address[-6:]}")

        while self.fallback_active:
            try:
                start_time = time.time()

                # Get current block
                if not self.polygonscan_client:
                    await asyncio.sleep(self.fallback_polling_interval)
                    continue

                current_block = await self.polygonscan_client.get_latest_block()

                # Get transactions since last poll
                if self.last_polled_block == 0:
                    self.last_polled_block = (
                        current_block - 100
                    )  # Start from 100 blocks ago

                transactions = await self.polygonscan_client.get_transactions(
                    self.wallet_address, self.last_polled_block, current_block
                )

                # Process transactions
                for tx in transactions:
                    if tx.get("hash") not in self.processed_tx_hashes:
                        await self._process_transaction(tx)

                self.last_polled_block = current_block
                self.metrics["polling_cycles"] += 1

                # Calculate latency
                latency = time.time() - start_time
                self._update_latency_metric("polling", latency)

                # Check if WebSocket recovered
                if self.ws_manager and self.ws_manager.is_connected():
                    logger.info("✅ WebSocket recovered - switching back from polling")
                    self.fallback_active = False
                    break

                # Sleep until next poll
                await asyncio.sleep(self.fallback_polling_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"❌ Error in polling loop: {e}")
                await asyncio.sleep(self.fallback_polling_interval)

        logger.info("🛑 Polling fallback stopped")

    def _update_latency_metric(self, method: str, latency: float) -> None:
        """Update latency metrics"""
        if method == "websocket":
            current_avg = self.metrics["avg_websocket_latency"]
            count = self.metrics["websocket_trades_detected"]
            if count > 0:
                self.metrics["avg_websocket_latency"] = (
                    current_avg * (count - 1) + latency
                ) / count
        elif method == "polling":
            current_avg = self.metrics["avg_polling_latency"]
            count = self.metrics["polling_cycles"]
            if count > 0:
                self.metrics["avg_polling_latency"] = (
                    current_avg * (count - 1) + latency
                ) / count

    async def _safe_callback(self, callback: Callable, *args: Any) -> None:
        """Safely execute callback"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.exception(f"Error in callback: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        ws_state = self.ws_manager.get_state() if self.ws_manager else {}

        return {
            **self.metrics,
            "websocket_connected": self.ws_manager.is_connected()
            if self.ws_manager
            else False,
            "fallback_active": self.fallback_active,
            "websocket_state": ws_state.get("state", "unknown"),
            "processed_transactions": len(self.processed_tx_hashes),
        }

    def get_performance_comparison(self) -> Dict[str, Any]:
        """Get performance comparison between WebSocket and polling"""
        return {
            "websocket": {
                "avg_latency_ms": self.metrics["avg_websocket_latency"] * 1000,
                "trades_detected": self.metrics["websocket_trades_detected"],
                "messages_received": self.metrics["websocket_messages"],
                "uptime_seconds": self.metrics["websocket_uptime"],
            },
            "polling": {
                "avg_latency_ms": self.metrics["avg_polling_latency"] * 1000,
                "trades_detected": self.metrics["polling_trades_detected"],
                "cycles_completed": self.metrics["polling_cycles"],
                "uptime_seconds": self.metrics["polling_uptime"],
            },
            "improvement": {
                "latency_reduction_ms": (
                    self.metrics["avg_polling_latency"]
                    - self.metrics["avg_websocket_latency"]
                )
                * 1000
                if self.metrics["avg_polling_latency"] > 0
                else 0,
                "latency_reduction_percent": (
                    (
                        (
                            self.metrics["avg_polling_latency"]
                            - self.metrics["avg_websocket_latency"]
                        )
                        / self.metrics["avg_polling_latency"]
                        * 100
                    )
                    if self.metrics["avg_polling_latency"] > 0
                    else 0
                ),
            },
        }
