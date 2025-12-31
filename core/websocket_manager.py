"""
WebSocket Connection Manager for Real-time Blockchain Monitoring

Provides:
- Auto-reconnect with exponential backoff
- Connection health monitoring
- Event-driven architecture
- Graceful fallback to polling
- Performance metrics tracking
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional, Set

from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidURI,
    WebSocketException,
)

from utils.alerts import send_error_alert, send_telegram_alert

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class WebSocketManager:
    """
    WebSocket connection manager with auto-reconnect and health monitoring.

    Features:
    - Automatic reconnection with exponential backoff
    - Connection health monitoring with heartbeat
    - Event-driven subscription management
    - Graceful degradation to polling fallback
    - Performance metrics tracking
    - Alert notifications on connection issues

    Thread Safety:
        All operations are async and use asyncio locks for state protection.
    """

    # Reconnection parameters
    INITIAL_RECONNECT_DELAY = 1.0  # Start with 1 second
    MAX_RECONNECT_DELAY = 60.0  # Max 60 seconds
    RECONNECT_MULTIPLIER = 2.0  # Exponential backoff multiplier
    MAX_RECONNECT_ATTEMPTS = 10  # Max attempts before marking as failed

    # Health check parameters
    HEARTBEAT_INTERVAL = 30.0  # Send heartbeat every 30 seconds
    CONNECTION_TIMEOUT = 10.0  # Connection timeout in seconds
    HEALTH_CHECK_INTERVAL = 60.0  # Health check every minute

    def __init__(
        self,
        ws_url: str,
        wallet_address: Optional[str] = None,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        alert_on_disconnect: bool = True,
    ) -> None:
        """
        Initialize WebSocket manager.

        Args:
            ws_url: WebSocket URL (e.g., wss://polygon-mainnet.g.alchemy.com/v2/API_KEY)
            wallet_address: Wallet address being monitored (for logging/alerts)
            on_message: Callback function for received messages
            on_error: Callback function for errors
            alert_on_disconnect: Whether to send alerts on disconnection
        """
        self.ws_url = ws_url
        self.wallet_address = wallet_address or "unknown"
        self.on_message = on_message
        self.on_error = on_error
        self.alert_on_disconnect = alert_on_disconnect

        # Connection state
        self.state: ConnectionState = ConnectionState.DISCONNECTED
        self.websocket: Optional[WebSocketClientProtocol] = None
        self._state_lock = asyncio.Lock()

        # Reconnection state
        self.reconnect_attempts = 0
        self.reconnect_delay = self.INITIAL_RECONNECT_DELAY
        self.last_connect_time: Optional[float] = None
        self.last_message_time: Optional[float] = None

        # Health monitoring
        self.health_check_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.receive_task: Optional[asyncio.Task] = None

        # Subscriptions
        self.active_subscriptions: Set[str] = set()

        # Performance metrics
        self.metrics = {
            "total_messages": 0,
            "total_errors": 0,
            "total_reconnects": 0,
            "total_uptime": 0.0,
            "last_message_time": None,
            "connection_start_time": None,
            "avg_message_latency": 0.0,
        }

        # Control flags
        self.running = False
        self._shutdown_event = asyncio.Event()

        logger.info(
            f"WebSocket manager initialized for wallet {self.wallet_address[-6:]} "
            f"with URL: {self.ws_url[:50]}..."
        )

    async def connect(self) -> bool:
        """
        Establish WebSocket connection.

        Returns:
            True if connection successful, False otherwise
        """
        async with self._state_lock:
            if self.state == ConnectionState.CONNECTED:
                logger.debug("Already connected")
                return True

            self.state = ConnectionState.CONNECTING

        try:
            logger.info(f"🔌 Connecting to WebSocket: {self.ws_url[:50]}...")

            # Connect with timeout
            self.websocket = await asyncio.wait_for(
                connect(self.ws_url, ping_interval=None),
                timeout=self.CONNECTION_TIMEOUT,
            )

            async with self._state_lock:
                self.state = ConnectionState.CONNECTED
                self.reconnect_attempts = 0
                self.reconnect_delay = self.INITIAL_RECONNECT_DELAY
                self.last_connect_time = time.time()
                self.metrics["connection_start_time"] = time.time()
                self.metrics["total_reconnects"] += 1

            logger.info("✅ WebSocket connected successfully")

            # Start background tasks
            self.receive_task = asyncio.create_task(self._receive_loop())
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self.health_check_task = asyncio.create_task(self._health_check_loop())

            return True

        except asyncio.TimeoutError:
            logger.error(
                f"❌ WebSocket connection timeout after {self.CONNECTION_TIMEOUT}s"
            )
            async with self._state_lock:
                self.state = ConnectionState.DISCONNECTED
            return False

        except (InvalidURI, WebSocketException) as e:
            logger.error(f"❌ WebSocket connection error: {e}")
            async with self._state_lock:
                self.state = ConnectionState.FAILED
            if self.on_error:
                await self._safe_callback(self.on_error, e)
            return False

        except Exception as e:
            logger.exception(f"❌ Unexpected error connecting WebSocket: {e}")
            async with self._state_lock:
                self.state = ConnectionState.DISCONNECTED
            if self.on_error:
                await self._safe_callback(self.on_error, e)
            return False

    async def disconnect(self) -> None:
        """Gracefully disconnect WebSocket"""
        logger.info("🔌 Disconnecting WebSocket...")

        self.running = False
        self._shutdown_event.set()

        # Cancel background tasks
        for task in [self.receive_task, self.heartbeat_task, self.health_check_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close WebSocket connection
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")

        async with self._state_lock:
            self.state = ConnectionState.DISCONNECTED
            self.websocket = None

        logger.info("✅ WebSocket disconnected")

    async def subscribe(self, subscription_params: Dict[str, Any]) -> bool:
        """
        Subscribe to blockchain events.

        Args:
            subscription_params: Subscription parameters (provider-specific)

        Returns:
            True if subscription successful, False otherwise
        """
        if not self.websocket or self.state != ConnectionState.CONNECTED:
            logger.warning("Cannot subscribe: WebSocket not connected")
            return False

        try:
            # Create subscription message (provider-specific format)
            # Example for Alchemy/QuickNode: {"jsonrpc": "2.0", "method": "eth_subscribe", "params": [...]}
            subscription_id = subscription_params.get("id", f"sub_{int(time.time())}")
            message = {
                "jsonrpc": "2.0",
                "id": subscription_id,
                "method": "eth_subscribe",
                "params": subscription_params.get("params", []),
            }

            await self.websocket.send(json.dumps(message))
            self.active_subscriptions.add(subscription_id)

            logger.info(f"📡 Subscribed to events: {subscription_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error subscribing: {e}")
            return False

    async def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.

        Args:
            subscription_id: Subscription ID to unsubscribe

        Returns:
            True if unsubscription successful, False otherwise
        """
        if not self.websocket or self.state != ConnectionState.CONNECTED:
            return False

        try:
            message = {
                "jsonrpc": "2.0",
                "id": int(time.time()),
                "method": "eth_unsubscribe",
                "params": [subscription_id],
            }

            await self.websocket.send(json.dumps(message))
            self.active_subscriptions.discard(subscription_id)

            logger.info(f"📡 Unsubscribed from events: {subscription_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error unsubscribing: {e}")
            return False

    async def _receive_loop(self) -> None:
        """Main message receiving loop"""
        if not self.websocket:
            return

        self.running = True

        try:
            async for message in self.websocket:
                if not self.running:
                    break

                try:
                    # Parse message
                    data = json.loads(message)
                    self.metrics["total_messages"] += 1
                    self.last_message_time = time.time()
                    self.metrics["last_message_time"] = datetime.now(
                        timezone.utc
                    ).isoformat()

                    # Update metrics
                    if self.metrics["connection_start_time"]:
                        uptime = time.time() - self.metrics["connection_start_time"]
                        self.metrics["total_uptime"] = uptime

                    # Handle message
                    if self.on_message:
                        await self._safe_callback(self.on_message, data)

                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ Invalid JSON message: {e}")
                    self.metrics["total_errors"] += 1
                except Exception as e:
                    logger.exception(f"❌ Error processing message: {e}")
                    self.metrics["total_errors"] += 1
                    if self.on_error:
                        await self._safe_callback(self.on_error, e)

        except ConnectionClosedOK:
            logger.info("🔌 WebSocket connection closed normally")
            async with self._state_lock:
                self.state = ConnectionState.DISCONNECTED
        except (ConnectionClosed, ConnectionClosedError) as e:
            logger.warning(f"🔌 WebSocket connection closed unexpectedly: {e}")
            async with self._state_lock:
                self.state = ConnectionState.DISCONNECTED
            await self._handle_disconnection()
        except Exception as e:
            logger.exception(f"❌ Error in receive loop: {e}")
            async with self._state_lock:
                self.state = ConnectionState.DISCONNECTED
            await self._handle_disconnection()

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat to keep connection alive"""
        while self.running and self.state == ConnectionState.CONNECTED:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)

                if self.websocket and self.state == ConnectionState.CONNECTED:
                    # Send ping (WebSocket protocol handles this automatically)
                    # Some providers may need explicit ping messages
                    try:
                        pong_waiter = await self.websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=5.0)
                    except asyncio.TimeoutError:
                        logger.warning("⚠️ Heartbeat timeout - connection may be stale")
                        await self._handle_disconnection()
                    except Exception as e:
                        logger.debug(f"Heartbeat error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Heartbeat loop error: {e}")

    async def _health_check_loop(self) -> None:
        """Periodic health check and metrics reporting"""
        while self.running:
            try:
                await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)

                async with self._state_lock:
                    state = self.state
                    last_msg = self.last_message_time

                # Check if connection is stale (no messages for 2 minutes)
                if state == ConnectionState.CONNECTED and last_msg:
                    time_since_last_msg = time.time() - last_msg
                    if time_since_last_msg > 120:  # 2 minutes
                        logger.warning(
                            f"⚠️ No messages received for {time_since_last_msg:.0f}s - connection may be stale"
                        )
                        await self._handle_disconnection()

                # Log metrics periodically
                if state == ConnectionState.CONNECTED:
                    logger.debug(
                        f"📊 WebSocket health: {self.metrics['total_messages']} messages, "
                        f"{self.metrics['total_errors']} errors, "
                        f"{len(self.active_subscriptions)} subscriptions"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Health check loop error: {e}")

    async def _handle_disconnection(self) -> None:
        """Handle disconnection and trigger reconnection"""
        async with self._state_lock:
            if self.state == ConnectionState.RECONNECTING:
                return  # Already handling reconnection

            self.state = ConnectionState.RECONNECTING

        # Send alert if configured
        if self.alert_on_disconnect:
            try:
                await send_telegram_alert(
                    f"⚠️ **WebSocket Disconnected**\n"
                    f"**Wallet:** `{self.wallet_address[-6:]}`\n"
                    f"**Attempting reconnection...**"
                )
            except Exception as e:
                logger.debug(f"Error sending disconnect alert: {e}")

        # Attempt reconnection
        await self._reconnect()

    async def _reconnect(self) -> None:
        """Reconnect with exponential backoff"""
        while self.reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
            self.reconnect_attempts += 1

            logger.info(
                f"🔄 Reconnecting attempt {self.reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS} "
                f"(delay: {self.reconnect_delay:.1f}s)"
            )

            await asyncio.sleep(self.reconnect_delay)

            # Attempt connection
            if await self.connect():
                logger.info("✅ Reconnection successful")
                return

            # Exponential backoff
            self.reconnect_delay = min(
                self.reconnect_delay * self.RECONNECT_MULTIPLIER,
                self.MAX_RECONNECT_DELAY,
            )

        # Max attempts reached
        logger.error("❌ Max reconnection attempts reached - marking as failed")
        async with self._state_lock:
            self.state = ConnectionState.FAILED

        # Send alert
        if self.alert_on_disconnect:
            try:
                await send_error_alert(
                    "WebSocket reconnection failed - falling back to polling",
                    {
                        "wallet": self.wallet_address[-6:],
                        "attempts": self.reconnect_attempts,
                    },
                )
            except Exception as e:
                logger.debug(f"Error sending failure alert: {e}")

    async def _safe_callback(self, callback: Callable, *args: Any) -> None:
        """Safely execute callback with error handling"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.exception(f"Error in callback: {e}")

    def get_state(self) -> Dict[str, Any]:
        """Get current connection state and metrics"""

        async def _get_state() -> Dict[str, Any]:
            async with self._state_lock:
                return {
                    "state": self.state.value,
                    "connected": self.state == ConnectionState.CONNECTED,
                    "reconnect_attempts": self.reconnect_attempts,
                    "active_subscriptions": len(self.active_subscriptions),
                    "metrics": self.metrics.copy(),
                    "last_connect_time": self.last_connect_time,
                    "last_message_time": self.last_message_time,
                }

        # For synchronous access, return current snapshot
        return {
            "state": self.state.value,
            "connected": self.state == ConnectionState.CONNECTED,
            "reconnect_attempts": self.reconnect_attempts,
            "active_subscriptions": len(self.active_subscriptions),
            "metrics": self.metrics.copy(),
        }

    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.state == ConnectionState.CONNECTED
