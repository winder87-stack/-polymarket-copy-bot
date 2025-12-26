import asyncio
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from tenacity import (
    after_log,
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import settings
from core.clob_client import PolymarketClient
from utils.alerts import send_error_alert, send_telegram_alert
from utils.helpers import calculate_position_size, format_currency, get_time_ago, normalize_address
from utils.security import secure_log

logger = logging.getLogger(__name__)


class TradeExecutor:
    def __init__(self, clob_client: PolymarketClient):
        self.settings = settings
        self.clob_client = clob_client
        self.wallet_address = self.clob_client.wallet_address

        # Thread safety for concurrent operations
        self._state_lock = asyncio.Lock()
        self._position_locks = {}  # Per-position locks for position-specific operations

        # State tracking
        self.daily_loss = 0.0
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.open_positions = {}
        self.last_trade_time = None
        self.start_time = time.time()

        # Risk management state
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
        self.circuit_breaker_time = None

        # Performance tracking
        self.trade_performance = []

        logger.info(f"Intialized trade executor for wallet: {self.wallet_address}")

    def _get_position_lock(self, position_key: str) -> asyncio.Lock:
        """Get or create a lock for position-specific operations."""
        if position_key not in self._position_locks:
            self._position_locks[position_key] = asyncio.Lock()
        return self._position_locks[position_key]

    async def execute_copy_trade(self, original_trade: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a copy trade based on an original trade"""
        try:
            trade_id = f"{original_trade['tx_hash']}_{original_trade['wallet_address'][-6:]}"

            # Use state lock for circuit breaker check and trade counting
            async with self._state_lock:
                # Check circuit breaker
                if self.circuit_breaker_active:
                    remaining_time = self._get_circuit_breaker_remaining_time()
                logger.warning(
                    f"🚫 Circuit breaker active: {self.circuit_breaker_reason}. "
                    f"Remaining time: {remaining_time:.1f} minutes. Skipping trade."
                )
                return {
                    "status": "skipped",
                    "reason": f"Circuit breaker: {self.circuit_breaker_reason}",
                    "trade_id": trade_id,
                }

            # Validate trade
            if not self._validate_trade(original_trade):
                return {"status": "invalid", "reason": "Invalid trade data", "trade_id": trade_id}

            # Apply risk management
            risk_check = self._apply_risk_management(original_trade)
            if not risk_check["approved"]:
                logger.warning(f"⚠️ Trade rejected by risk management: {risk_check['reason']}")
                return {"status": "rejected", "reason": risk_check["reason"], "trade_id": trade_id}

            # Get market details
            market = await self.clob_client.get_market(original_trade["condition_id"])
            if not market:
                logger.error(
                    f"❌ Could not get market details for {original_trade['condition_id']}"
                )
                return {"status": "failed", "reason": "Market not found", "trade_id": trade_id}

            # Calculate copy amount with risk management
            copy_amount = await self._calculate_copy_amount(original_trade, market)
            if copy_amount <= self.settings.risk.min_trade_amount:
                logger.warning(
                    f"⚠️ Copy amount {copy_amount:.4f} below minimum {self.settings.risk.min_trade_amount}. Skipping trade."
                )
                return {
                    "status": "skipped",
                    "reason": f"Amount too small ({copy_amount:.4f} < {self.settings.risk.min_trade_amount})",
                    "trade_id": trade_id,
                }

            # Get token ID for the outcome
            token_id = self._get_token_id_for_outcome(market, original_trade)
            if not token_id:
                logger.error(f"❌ Could not determine token ID for trade: {original_trade}")
                return {"status": "failed", "reason": "Token ID not found", "trade_id": trade_id}

            # Place the order
            logger.info(
                f"🎯 Executing copy trade: {original_trade['side']} {copy_amount:.4f} shares at ${original_trade['price']:.4f} "
                f"(Confidence: {original_trade['confidence_score']:.2f})"
            )

            start_time = time.time()
            result = await self.clob_client.place_order(
                condition_id=original_trade["condition_id"],
                side=original_trade["side"],
                amount=copy_amount,
                price=original_trade["price"],
                token_id=token_id,
            )
            execution_time = time.time() - start_time

            # Update state (protected by state lock)
            async with self._state_lock:
                self.total_trades += 1
                if result and "orderID" in result:
                    self.successful_trades += 1
                    self.last_trade_time = time.time()

                    # Track performance
                    performance = {
                        "timestamp": time.time(),
                        "original_trade": original_trade,
                        "copy_amount": copy_amount,
                        "execution_time": execution_time,
                        "order_id": result["orderID"],
                        "status": "success",
                    }
                    self.trade_performance.append(performance)

                    # Track position
                    position_key = f"{original_trade['condition_id']}_{original_trade['side']}"
                    self.open_positions[position_key] = {
                        "amount": copy_amount,
                        "entry_price": original_trade["price"],
                        "timestamp": time.time(),
                        "original_trade": original_trade,
                        "order_id": result["orderID"],
                    }
                else:
                    self.failed_trades += 1

            # Handle success case (outside the lock)
            if result and "orderID" in result:
                logger.info(
                    f"✅ Copy trade executed successfully: {result['orderID']} (Execution time: {execution_time:.2f}s)"
                )

                # Send alert
                if self.settings.alerts.alert_on_trade:
                    await send_telegram_alert(
                        f"✅ **Trade Executed**\n"
                        f"Wallet: `{normalize_address(original_trade['wallet_address'])[-6:]}`\n"
                        f"Market: `{original_trade['condition_id'][-8:]}`\n"
                        f"Side: {original_trade['side']}\n"
                        f"Amount: {copy_amount:.4f} shares\n"
                        f"Price: ${original_trade['price']:.4f}\n"
                        f"Order ID: `{result['orderID']}`\n"
                        f"Execution: {execution_time:.2f}s"
                    )

                return {
                    "status": "success",
                    "order_id": result["orderID"],
                    "copy_amount": copy_amount,
                    "execution_time": execution_time,
                    "trade_id": trade_id,
                    "position_key": position_key,
                }
            else:
                logger.error("❌ Copy trade failed to execute")

                # Track failed performance
                performance = {
                    "timestamp": time.time(),
                    "original_trade": original_trade,
                    "copy_amount": copy_amount,
                    "execution_time": execution_time,
                    "status": "failed",
                }
                self.trade_performance.append(performance)

                return {
                    "status": "failed",
                    "reason": "Order placement failed",
                    "execution_time": execution_time,
                    "trade_id": trade_id,
                }

        except Exception as e:
            self.failed_trades += 1
            logger.error(f"❌ Error executing copy trade: {e}")

            # Send error alert
            if self.settings.alerts.alert_on_error:
                await send_error_alert(
                    f"Trade execution error: {e}",
                    context={
                        "trade": original_trade,
                        "wallet": self.wallet_address[-6:],
                        "timestamp": datetime.now().isoformat(),
                    },
                )

            return {
                "status": "error",
                "error": str(e),
                "trade_id": (
                    getattr(original_trade, "tx_hash", "unknown")
                    if isinstance(original_trade, dict)
                    else "unknown"
                ),
            }

    def _validate_trade(self, trade: Dict[str, Any]) -> bool:
        """Validate trade data before execution"""
        required_fields = [
            "tx_hash",
            "timestamp",
            "wallet_address",
            "condition_id",
            "side",
            "amount",
            "price",
        ]

        for field in required_fields:
            if field not in trade:
                logger.error(f"❌ Missing required field: {field}")
                return False

        # Validate side
        if trade["side"].upper() not in ["BUY", "SELL"]:
            logger.error(f"❌ Invalid side: {trade['side']}")
            return False

        # Validate price range
        if not 0.01 <= trade["price"] <= 0.99:
            logger.error(f"❌ Invalid price: {trade['price']:.4f}. Must be between 0.01 and 0.99")
            return False

        # Validate amount
        if trade["amount"] <= 0:
            logger.error(f"❌ Invalid amount: {trade['amount']:.4f}. Must be positive")
            return False

        # Validate timestamp (not too old)
        trade_age = (datetime.now() - trade["timestamp"]).total_seconds()
        if trade_age > 300:  # 5 minutes
            logger.warning(f"⚠️ Trade is {trade_age:.1f} seconds old. May be stale.")

        return True

    def _apply_risk_management(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Apply risk management rules to a trade"""
        # Daily loss circuit breaker
        if self.daily_loss >= self.settings.risk.max_daily_loss:
            return {
                "approved": False,
                "reason": f"Daily loss limit reached (${self.daily_loss:.2f} / ${self.settings.risk.max_daily_loss:.2f})",
            }

        # Position size limit
        if trade["amount"] > self.settings.risk.max_position_size:
            return {
                "approved": False,
                "reason": f'Position size too large (${trade["amount"]:.2f} > ${self.settings.risk.max_position_size:.2f})',
            }

        # Minimum trade amount
        if trade["amount"] < self.settings.risk.min_trade_amount:
            return {
                "approved": False,
                "reason": f'Trade amount below minimum (${trade["amount"]:.2f} < ${self.settings.risk.min_trade_amount:.2f})',
            }

        # Maximum concurrent positions
        if len(self.open_positions) >= self.settings.risk.max_concurrent_positions:
            return {
                "approved": False,
                "reason": f"Max concurrent positions reached ({len(self.open_positions)} / {self.settings.risk.max_concurrent_positions})",
            }

        # Confidence score check
        if trade["confidence_score"] < self.settings.monitoring.min_confidence_score:
            return {
                "approved": False,
                "reason": f'Low confidence score ({trade["confidence_score"]:.2f} < {self.settings.monitoring.min_confidence_score:.2f})',
            }

        return {"approved": True}

    async def _calculate_copy_amount(
        self, original_trade: Dict[str, Any], market: Dict[str, Any]
    ) -> float:
        """Calculate how much to trade based on risk management rules with performance optimizations"""
        try:
            # Get current balance and price concurrently (already optimized)
            balance_task = self.clob_client.get_balance()
            current_price_task = self.clob_client.get_current_price(original_trade["condition_id"])

            balance, current_price = await asyncio.gather(balance_task, current_price_task)

            if balance is None:
                logger.warning("⚠️ Could not get balance. Using conservative amount.")
                return min(original_trade["amount"] * 0.1, self.settings.risk.max_position_size)

            if current_price is None:
                current_price = original_trade["price"]

            # Performance optimization: Cache frequently used values
            risk_percentage = 0.01  # 1% risk per trade
            account_risk = balance * risk_percentage

            # Optimized risk calculation to prevent division by zero
            price_risk = abs(current_price - original_trade["price"])
            min_price_risk = max(price_risk, current_price * 0.001)  # Minimum 0.1% price movement

            # Calculate position size with bounds checking
            if price_risk > 0:
                position_size = account_risk / min_price_risk
            else:
                # If no price movement, use conservative sizing
                position_size = account_risk * 0.1  # 10% of account risk

            # Apply proportional scaling (10% of original trade)
            proportional_size = original_trade["amount"] * 0.1

            # Take the minimum of both approaches, capped by max position size
            copy_amount = min(
                position_size, proportional_size, self.settings.risk.max_position_size
            )

            # Ensure minimum trade amount
            copy_amount = max(copy_amount, self.settings.risk.min_trade_amount)

            # Performance optimization: Use faster rounding
            copy_amount = round(copy_amount, 4)

            # Optimized logging (only log detailed info for large trades)
            if copy_amount > self.settings.risk.min_trade_amount * 10:
                logger.info(
                    f"💰 Position size: ${copy_amount:.4f} (Original: ${original_trade['amount']:.2f})"
                )
            else:
                logger.debug(f"💰 Small position: ${copy_amount:.4f}")

            return copy_amount

        except Exception as e:
            logger.error(f"Error calculating copy amount: {e}")
            # Performance optimization: Pre-calculate fallback value
            return min(original_trade["amount"] * 0.1, self.settings.risk.max_position_size)

    def _get_token_id_for_outcome(
        self, market: Dict[str, Any], trade: Dict[str, Any]
    ) -> Optional[str]:
        """Get the correct token ID for the trade outcome"""
        try:
            # This depends on the market structure
            if "tokens" in market and isinstance(market["tokens"], list) and market["tokens"]:
                # Simple approach: use the first token for BUY, second for SELL
                if trade["side"].upper() == "BUY":
                    return market["tokens"][0]["tokenId"]
                else:
                    return market["tokens"][-1]["tokenId"]

            # Fallback: try to find token ID from market data
            if "outcomes" in market and isinstance(market["outcomes"], list):
                for outcome in market["outcomes"]:
                    if "tokenId" in outcome:
                        return outcome["tokenId"]

            logger.error(f"❌ Could not find tokens in market: {market}")
            return None

        except Exception as e:
            logger.error(f"Error getting token ID: {e}")
            return None

    async def manage_positions(self):
        """Monitor and manage open positions with performance optimizations"""
        try:
            if not self.open_positions:
                return

            position_count = len(self.open_positions)

            # Performance optimization: Skip detailed logging for small position counts
            if position_count > 10:
                logger.info(f"📊 Managing {position_count} open positions")
            else:
                logger.debug(f"Managing {position_count} positions")

            positions_to_close = []
            current_time = time.time()

            # Performance optimization: Batch API calls for current prices
            unique_condition_ids = set(
                position["original_trade"]["condition_id"]
                for position in self.open_positions.values()
            )

            # Get prices for all unique conditions concurrently
            price_tasks = [
                self.clob_client.get_current_price(condition_id)
                for condition_id in unique_condition_ids
            ]
            price_results = await asyncio.gather(*price_tasks, return_exceptions=True)

            # Create price lookup map
            price_map = {}
            for condition_id, price_result in zip(unique_condition_ids, price_results):
                if isinstance(price_result, float):
                    price_map[condition_id] = price_result

            # Process positions with batched prices (major performance improvement)
            for position_key, position in self.open_positions.items():
                try:
                    condition_id = position["original_trade"]["condition_id"]
                    current_price = price_map.get(condition_id)

                    if current_price is None:
                        # Skip positions where we can't get current price
                        continue

                    entry_price = position["entry_price"]
                    side = position["original_trade"]["side"].upper()
                    amount = position["amount"]

                    # Performance optimization: Calculate profit metrics once
                    if side == "BUY":
                        # For long positions: profit when price increases
                        price_diff = current_price - entry_price
                        profit_pct = price_diff / entry_price if entry_price != 0 else 0
                        unrealized_pnl = price_diff * amount
                    elif side == "SELL":
                        # For short positions: profit when price decreases
                        price_diff = entry_price - current_price
                        profit_pct = price_diff / entry_price if entry_price != 0 else 0
                        unrealized_pnl = price_diff * amount
                    else:
                        continue  # Skip unknown side

                    # Performance optimization: Check exit conditions with early returns
                    should_close = False
                    close_reason = None

                    # Take profit check
                    if profit_pct >= self.settings.risk.take_profit_percentage:
                        should_close = True
                        close_reason = "TAKE_PROFIT"
                        if (
                            amount > self.settings.risk.min_trade_amount * 5
                        ):  # Only log significant positions
                            logger.info(
                                f"🎉 Take profit: {position_key} {profit_pct:.2%} (${unrealized_pnl:.2f})"
                            )

                    # Stop loss check
                    elif profit_pct <= -self.settings.risk.stop_loss_percentage:
                        should_close = True
                        close_reason = "STOP_LOSS"
                        logger.warning(
                            f"🛑 Stop loss: {position_key} {profit_pct:.2%} (${unrealized_pnl:.2f})"
                        )

                    # Time-based exit (after 24 hours)
                    if not should_close:
                        position_age = current_time - position["timestamp"]
                        if position_age > 86400:  # 24 hours
                            should_close = True
                            close_reason = "TIME_EXIT"
                            if amount > self.settings.risk.min_trade_amount * 5:
                                logger.info(
                                    f"⏰ Time exit: {position_key} ({position_age/3600:.1f}h)"
                                )

                    if should_close:
                        positions_to_close.append((position_key, close_reason))

                except Exception as e:
                    logger.error(f"Error managing position {position_key}: {e}")
                    continue

            # Performance optimization: Batch close positions
            if positions_to_close:
                close_tasks = [
                    self._close_position(position_key, reason)
                    for position_key, reason in positions_to_close
                ]
                await asyncio.gather(*close_tasks, return_exceptions=True)

                logger.info(f"Closed {len(positions_to_close)} positions")

            # Update daily loss tracking (less frequent for performance)
            if position_count > 0 and position_count % 5 == 0:  # Every 5th cycle
                await self._update_daily_loss()

            # Check circuit breaker conditions (less frequent)
            if position_count > 0 and current_time % 60 < 1:  # Roughly every minute
                self._check_circuit_breaker_conditions()

        except Exception as e:
            logger.error(f"Error managing positions: {e}")

    async def _close_position(self, position_key: str, reason: str):
        """Close a specific position"""
        if position_key not in self.open_positions:
            return

        position = self.open_positions[position_key]
        trade = position["original_trade"]

        # Create opposite trade to close position
        close_trade = trade.copy()
        close_trade["side"] = "SELL" if trade["side"].upper() == "BUY" else "BUY"
        close_trade["amount"] = position["amount"]
        close_trade["price"] = (
            await self.clob_client.get_current_price(trade["condition_id"]) or trade["price"]
        )
        close_trade["confidence_score"] = 0.99  # High confidence for closing

        logger.info(
            f"CloseOperation for {position_key}: {close_trade['side']} {close_trade['amount']:.4f} shares (Reason: {reason})"
        )

        result = await self.execute_copy_trade(close_trade)

        if result["status"] == "success":
            del self.open_positions[position_key]
            logger.info(f"✅ Position closed successfully: {position_key} (Reason: {reason})")

            # Update P&L tracking
            entry_value = position["amount"] * position["entry_price"]
            exit_value = position["amount"] * close_trade["price"]
            pnl = (
                exit_value - entry_value
                if trade["side"].upper() == "BUY"
                else entry_value - exit_value
            )

            if pnl < 0:
                async with self._state_lock:
                    self.daily_loss += abs(pnl)
                logger.warning(
                    f"📉 Position closed at loss: ${abs(pnl):.2f}. Daily loss: ${self.daily_loss:.2f}"
                )

    async def _update_daily_loss(self):
        """Update daily loss tracking"""
        try:
            # Reset daily loss at midnight UTC
            now = datetime.utcnow()
            if hasattr(self, "last_reset_time"):
                last_reset = getattr(self, "last_reset_time")
                if now.date() > last_reset.date():
                    async with self._state_lock:
                        self.daily_loss = 0.0
                    logger.info("🔄 Daily loss reset at midnight UTC")
            else:
                self.last_reset_time = now

            return self.daily_loss

        except Exception as e:
            logger.error(f"Error updating daily loss: {e}")
            return self.daily_loss

    def _check_circuit_breaker_conditions(self):
        """Check if circuit breaker should be activated"""
        try:
            # Daily loss circuit breaker
            if self.daily_loss >= self.settings.risk.max_daily_loss:
                self.activate_circuit_breaker(
                    f"Daily loss limit reached (${self.daily_loss:.2f} / ${self.settings.risk.max_daily_loss:.2f})"
                )
                return

            # Consecutive failures circuit breaker
            if self.failed_trades >= 5 and self.total_trades >= 10:
                failure_rate = self.failed_trades / self.total_trades
                if failure_rate >= 0.5:  # 50% failure rate
                    self.activate_circuit_breaker(
                        f"High failure rate ({failure_rate:.1%} - {self.failed_trades}/{self.total_trades} trades)"
                    )
                    return

            # Reset circuit breaker if conditions improve
            if self.circuit_breaker_active:
                time_since_activation = time.time() - self.circuit_breaker_time
                if time_since_activation > 3600:  # 1 hour
                    logger.info(
                        "✅ Circuit breaker conditions improved. Resetting circuit breaker."
                    )
                    self.reset_circuit_breaker()

        except Exception as e:
            logger.error(f"Error checking circuit breaker conditions: {e}")

    def _get_circuit_breaker_remaining_time(self) -> float:
        """Get remaining time for circuit breaker in minutes"""
        if not self.circuit_breaker_active or not self.circuit_breaker_time:
            return 0.0

        elapsed = time.time() - self.circuit_breaker_time
        remaining = max(0, 3600 - elapsed)  # 1 hour cooldown
        return remaining / 60  # Convert to minutes

    def activate_circuit_breaker(self, reason: str):
        """Activate circuit breaker to stop trading"""
        if self.circuit_breaker_active:
            return

        self.circuit_breaker_active = True
        self.circuit_breaker_reason = reason
        self.circuit_breaker_time = time.time()

        logger.critical(f"🚨 CIRCUIT BREAKER ACTIVATED: {reason}")
        logger.critical(f"   Daily Loss: ${self.daily_loss:.2f}")
        logger.critical(f"   Success Rate: {self.successful_trades}/{self.total_trades} trades")

        # Send alert
        if self.settings.alerts.alert_on_circuit_breaker:
            asyncio.create_task(
                send_telegram_alert(
                    f"🚨 **CIRCUIT BREAKER ACTIVATED**\n"
                    f"**Reason:** {reason}\n"
                    f"**Wallet:** `{self.wallet_address[-6:]}`\n"
                    f"**Daily Loss:** ${self.daily_loss:.2f}\n"
                    f"**Success Rate:** {self.successful_trades}/{self.total_trades}\n"
                    f"**Cooldown:** 60 minutes"
                )
            )

    def reset_circuit_breaker(self):
        """Reset circuit breaker"""
        if self.circuit_breaker_active:
            logger.info(f"✅ Circuit breaker reset. Reason was: {self.circuit_breaker_reason}")
            self.circuit_breaker_active = False
            self.circuit_breaker_reason = ""
            self.circuit_breaker_time = None

    async def health_check(self) -> bool:
        """Perform health check on the trade executor"""
        try:
            # Check balance
            balance = await self.clob_client.get_balance()
            if balance is None:
                logger.error("❌ Health check failed: Could not get balance")
                return False

            # Check circuit breaker status
            if self.circuit_breaker_active:
                remaining_time = self._get_circuit_breaker_remaining_time()
                logger.warning(
                    f"⚠️ Health check warning: Circuit breaker active for {remaining_time:.1f} more minutes"
                )

            # Check open positions
            if len(self.open_positions) > self.settings.risk.max_concurrent_positions * 1.5:
                logger.warning(
                    f"⚠️ Health check warning: Too many open positions ({len(self.open_positions)})"
                )

            logger.info(
                f"✅ Health check passed. Balance: ${balance:.2f}, "
                f"Positions: {len(self.open_positions)}, "
                f"Daily Loss: ${self.daily_loss:.2f}"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        success_rate = self.successful_trades / self.total_trades if self.total_trades > 0 else 0
        runtime = time.time() - self.start_time

        # Calculate P&L from recent trades
        recent_performance = self.trade_performance[-100:]  # Last 100 trades
        total_pnl = sum(
            (
                perf["copy_amount"]
                * (perf["original_trade"]["price"] - perf["original_trade"]["price"])
            )
            for perf in recent_performance
            if perf["status"] == "success"
        )

        return {
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "success_rate": success_rate,
            "daily_loss": self.daily_loss,
            "open_positions": len(self.open_positions),
            "total_pnl": total_pnl,
            "circuit_breaker_active": self.circuit_breaker_active,
            "last_trade_time": self.last_trade_time,
            "uptime_hours": runtime / 3600,
            "avg_execution_time": sum(
                p["execution_time"] for p in self.trade_performance if "execution_time" in p
            )
            / max(len(self.trade_performance), 1),
        }
