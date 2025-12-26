import asyncio
import logging
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation, getcontext
from typing import Any, Dict, List, Optional, Union

import aiohttp
from tenacity import (
    after_log,
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from web3.exceptions import BadFunctionCallOutput, ContractLogicError, Web3ValidationError

from config.settings import settings
from core.clob_client import PolymarketClient
from utils.alerts import send_error_alert, send_telegram_alert
from utils.helpers import calculate_position_size, format_currency, get_time_ago, normalize_address
from utils.security import secure_log
from utils.validation import InputValidator, ValidationError

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

        SecureLogger.log(
            "info",
            "Initialized trade executor",
            {"wallet_address_masked": f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"},
        )

    def _get_position_lock(self, position_key: str) -> asyncio.Lock:
        """Get or create a lock for position-specific operations."""
        if position_key not in self._position_locks:
            self._position_locks[position_key] = asyncio.Lock()
        return self._position_locks[position_key]

    async def execute_copy_trade(self, original_trade: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a copy trade based on an original trade"""
        try:
            trade_id = self._generate_trade_id(original_trade)

            # Check circuit breaker
            circuit_breaker_result = await self._check_circuit_breaker_for_trade(trade_id)
            if circuit_breaker_result:
                return circuit_breaker_result

            # Validate and apply risk management
            validation_result = await self._validate_and_apply_risk_management(
                original_trade, trade_id
            )
            if validation_result:
                return validation_result

            # Get market data and calculate position
            market_data = await self._get_market_and_calculate_position(original_trade, trade_id)
            if not market_data["success"]:
                return market_data["result"]

            # Place order and track performance
            return await self._place_order_and_track_performance(
                original_trade, trade_id, market_data
            )

        except Exception as e:
            return await self._handle_trade_execution_error(e, original_trade)

    def _generate_trade_id(self, original_trade: Dict[str, Any]) -> str:
        """Generate a unique trade ID"""
        return f"{original_trade['tx_hash']}_{original_trade['wallet_address'][-6:]}"

    async def _check_circuit_breaker_for_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Check circuit breaker status and return skip result if active"""
        async with self._state_lock:
            if not self.circuit_breaker_active:
                return None

            try:
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
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"Data error checking circuit breaker: {str(e)[:100]}")
                return None  # Continue with trade if circuit breaker check fails
            except Exception as e:
                logger.error(f"Unexpected error checking circuit breaker: {str(e)}")
                return None  # Continue with trade if circuit breaker check fails

    async def _validate_and_apply_risk_management(
        self, original_trade: Dict[str, Any], trade_id: str
    ) -> Optional[Dict[str, Any]]:
        """Validate trade data and apply risk management rules"""
        # Validate trade
        if not self._validate_trade(original_trade):
            return {"status": "invalid", "reason": "Invalid trade data", "trade_id": trade_id}

        # Apply risk management
        risk_check = self._apply_risk_management(original_trade)
        if not risk_check["approved"]:
            logger.warning(f"⚠️ Trade rejected by risk management: {risk_check['reason']}")
            return {"status": "rejected", "reason": risk_check["reason"], "trade_id": trade_id}

        return None

    async def _get_market_and_calculate_position(
        self, original_trade: Dict[str, Any], trade_id: str
    ) -> Dict[str, Any]:
        """Get market data and calculate position size"""
        # Get market details
        market = await self.clob_client.get_market(original_trade["condition_id"])
        if not market:
            logger.error(f"❌ Could not get market details for {original_trade['condition_id']}")
            return {
                "success": False,
                "result": {"status": "failed", "reason": "Market not found", "trade_id": trade_id},
            }

        # Calculate copy amount
        copy_amount = await self._calculate_copy_amount(original_trade, market)
        if copy_amount <= self.settings.risk.min_trade_amount:
            logger.warning(
                f"⚠️ Copy amount {copy_amount:.4f} below minimum {self.settings.risk.min_trade_amount}. Skipping trade."
            )
            return {
                "success": False,
                "result": {
                    "status": "skipped",
                    "reason": f"Amount too small ({copy_amount:.4f} < {self.settings.risk.min_trade_amount})",
                    "trade_id": trade_id,
                },
            }

        # Get token ID
        token_id = self._get_token_id_for_outcome(market, original_trade)
        if not token_id:
            logger.error(f"❌ Could not determine token ID for trade: {original_trade}")
            return {
                "success": False,
                "result": {
                    "status": "failed",
                    "reason": "Token ID not found",
                    "trade_id": trade_id,
                },
            }

        return {
            "success": True,
            "market": market,
            "copy_amount": copy_amount,
            "token_id": token_id,
        }

    async def _place_order_and_track_performance(
        self, original_trade: Dict[str, Any], trade_id: str, market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Place the order and track performance"""
        copy_amount = market_data["copy_amount"]
        token_id = market_data["token_id"]

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

        # Update state and track performance
        success_result = await self._handle_order_result(
            result, original_trade, copy_amount, execution_time, trade_id
        )

        if success_result["status"] == "success":
            await self._send_trade_alert(original_trade, copy_amount, result, execution_time)

        return success_result

    async def _handle_order_result(
        self,
        result: Any,
        original_trade: Dict[str, Any],
        copy_amount: float,
        execution_time: float,
        trade_id: str,
    ) -> Dict[str, Any]:
        """Handle the order placement result and update state"""
        async with self._state_lock:
            self.total_trades += 1
            if result and "orderID" in result:
                return await self._handle_successful_order(
                    result, original_trade, copy_amount, execution_time, trade_id
                )
            else:
                return await self._handle_failed_order(
                    original_trade, copy_amount, execution_time, trade_id
                )

    async def _handle_successful_order(
        self,
        result: Dict[str, Any],
        original_trade: Dict[str, Any],
        copy_amount: float,
        execution_time: float,
        trade_id: str,
    ) -> Dict[str, Any]:
        """Handle successful order placement"""
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

        logger.info(
            f"✅ Copy trade executed successfully: {result['orderID']} (Execution time: {execution_time:.2f}s)"
        )

        return {
            "status": "success",
            "order_id": result["orderID"],
            "copy_amount": copy_amount,
            "execution_time": execution_time,
            "trade_id": trade_id,
            "position_key": position_key,
        }

    async def _handle_failed_order(
        self,
        original_trade: Dict[str, Any],
        copy_amount: float,
        execution_time: float,
        trade_id: str,
    ) -> Dict[str, Any]:
        """Handle failed order placement"""
        self.failed_trades += 1

        # Track failed performance
        performance = {
            "timestamp": time.time(),
            "original_trade": original_trade,
            "copy_amount": copy_amount,
            "execution_time": execution_time,
            "status": "failed",
        }
        self.trade_performance.append(performance)

        logger.error("❌ Copy trade failed to execute")

        return {
            "status": "failed",
            "reason": "Order placement failed",
            "execution_time": execution_time,
            "trade_id": trade_id,
        }

    async def _send_trade_alert(
        self,
        original_trade: Dict[str, Any],
        copy_amount: float,
        result: Dict[str, Any],
        execution_time: float,
    ) -> None:
        """Send success alert for completed trade"""
        if not self.settings.alerts.alert_on_trade:
            return

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

    async def _handle_trade_execution_error(
        self, error: Exception, original_trade: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle various types of trade execution errors"""
        self.failed_trades += 1

        trade_id = (
            original_trade.get("tx_hash", "unknown")
            if isinstance(original_trade, dict)
            else "unknown"
        )

        if isinstance(error, (ConnectionError, TimeoutError, aiohttp.ClientError)):
            logger.error(f"❌ Network error executing copy trade: {str(error)[:100]}")
            error_type = "Network error"
        elif isinstance(error, (ValueError, TypeError, KeyError, InvalidOperation)):
            logger.error(f"❌ Data validation error executing copy trade: {str(error)[:100]}")
            error_type = "Data validation error"
        else:
            logger.critical(
                f"❌ Unexpected error executing copy trade: {str(error)}", exc_info=True
            )
            error_type = "Unexpected error"

        # Send error alert
        if self.settings.alerts.alert_on_error:
            await send_error_alert(
                f"Trade execution {error_type.lower()}: {str(error)[:100]}",
                context={
                    "trade": original_trade if isinstance(original_trade, dict) else {},
                    "wallet": self.wallet_address[-6:],
                    "timestamp": datetime.now().isoformat(),
                },
            )

        return {
            "status": "error",
            "error": f"{error_type}: {str(error)[:100]}",
            "trade_id": trade_id,
        }

    def _validate_trade(self, trade: Dict[str, Any]) -> bool:
        """Validate trade data before execution using comprehensive validation"""
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

        try:
            # Use comprehensive validation for all trade inputs
            InputValidator.validate_wallet_address(trade["wallet_address"])
            InputValidator.validate_condition_id(trade["condition_id"])

            # Validate side
            side = trade["side"].upper()
            if side not in ["BUY", "SELL"]:
                logger.error(f"❌ Invalid side: {trade['side']}")
                return False

            # Validate price and amount with comprehensive validation
            InputValidator.validate_price(trade["price"])
            InputValidator.validate_trade_amount(trade["amount"])

            # Validate transaction hash format
            InputValidator.validate_hex_string(trade["tx_hash"], min_length=66, max_length=66)

            return True

        except ValidationError as e:
            logger.error(f"❌ Trade validation failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error during trade validation: {e}")
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

            # Robust position size calculation with Decimal precision
            getcontext().prec = 28  # High precision for financial calculations

            try:
                # Convert to Decimal for precision
                account_balance_dec = Decimal(str(balance))
                current_price_dec = Decimal(str(current_price))
                entry_price_dec = Decimal(str(original_trade["price"]))
                risk_percentage_dec = Decimal("0.01")  # 1% risk per trade

                # Calculate price risk with minimum threshold
                price_risk_dec = abs(current_price_dec - entry_price_dec)
                MIN_PRICE_RISK = Decimal("0.0001")
                price_risk_dec = max(price_risk_dec, MIN_PRICE_RISK)

                # Calculate account risk (1% of balance)
                account_risk_dec = account_balance_dec * risk_percentage_dec

                # Calculate position size with multiple safeguards
                position_size_dec = account_risk_dec / price_risk_dec

                # Apply safeguards
                position_size_dec = min(
                    position_size_dec,
                    Decimal(str(self.settings.risk.max_position_size)),
                    Decimal(
                        str(account_balance_dec * Decimal("0.1"))
                    ),  # Never risk more than 10% of account
                )

                # Ensure minimum trade amount
                position_size_dec = max(
                    position_size_dec, Decimal(str(self.settings.risk.min_trade_amount))
                )

                # Convert back to float with proper rounding
                copy_amount = float(position_size_dec.quantize(Decimal("0.0001")))

                # Add detailed logging for debugging
                logger.info(
                    f"💰 Position size calculation: Account risk ${account_risk_dec:.4f}, "
                    f"Price risk {price_risk_dec:.6f}, Raw size {position_size_dec:.4f}, "
                    f"Final size ${copy_amount:.4f}"
                )

            except (InvalidOperation, TypeError, ValueError) as e:
                logger.error(f"Error in position size calculation: {e}")
                logger.error(
                    f"Balance: {balance}, Current price: {current_price}, "
                    f"Entry price: {original_trade['price']}, Risk %: 0.01"
                )
                # Fallback to conservative sizing
                copy_amount = min(
                    original_trade["amount"] * 0.1, self.settings.risk.max_position_size
                )

            return copy_amount

        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"Network error calculating copy amount: {str(e)[:100]}")
            # Performance optimization: Pre-calculate fallback value
            return min(original_trade["amount"] * 0.1, self.settings.risk.max_position_size)
        except (ValueError, TypeError, KeyError, InvalidOperation) as e:
            logger.error(f"Data error calculating copy amount: {str(e)[:100]}")
            # Performance optimization: Pre-calculate fallback value
            return min(original_trade["amount"] * 0.1, self.settings.risk.max_position_size)
        except Exception as e:
            logger.critical(f"Unexpected error calculating copy amount: {str(e)}", exc_info=True)
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

        except (ValueError, TypeError, KeyError, IndexError) as e:
            logger.error(f"Data error getting token ID: {str(e)[:100]}")
            return None
        except Exception as e:
            logger.critical(f"Unexpected error getting token ID: {str(e)}", exc_info=True)
            return None

    async def manage_positions(self) -> None:
        """Main position management orchestrator"""
        if not await self._should_manage_positions():
            return

        try:
            current_prices = await self._get_current_prices_for_positions()
            positions_to_close = await self._evaluate_positions_for_closure(current_prices)
            await self._close_positions(positions_to_close)
            await self._update_daily_loss_tracking()
            self._check_circuit_breaker_conditions()
            await self._perform_periodic_cleanup()
        except Exception as e:
            logger.error(f"Error managing positions: {e}", exc_info=True)
            await self._handle_position_management_failure(e)

    async def _should_manage_positions(self) -> bool:
        """Determine if position management should proceed"""
        if not self.open_positions:
            logger.debug("No open positions to manage")
            return False

        position_count = len(self.open_positions)
        if position_count > 10:
            logger.info(f"📊 Managing {position_count} open positions")
        else:
            logger.debug(f"Managing {position_count} positions")

        return True

    async def _get_current_prices_for_positions(self) -> Dict[str, float]:
        """Get current market prices for all open positions"""
        unique_condition_ids = set(
            position["original_trade"]["condition_id"] for position in self.open_positions.values()
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
            else:
                logger.warning(f"Failed to get price for condition {condition_id}: {price_result}")

        return price_map

    async def _evaluate_positions_for_closure(
        self, price_map: Dict[str, float]
    ) -> List[Tuple[str, str]]:
        """Evaluate which positions should be closed based on current prices"""
        positions_to_close = []
        current_time = time.time()

        for position_key, position in self.open_positions.items():
            try:
                close_reason = await self._evaluate_single_position(
                    position_key, position, price_map, current_time
                )
                if close_reason:
                    positions_to_close.append((position_key, close_reason))
            except (ValueError, TypeError, KeyError, ZeroDivisionError) as e:
                logger.error(f"Data error evaluating position {position_key}: {str(e)[:100]}")
                continue
            except Exception as e:
                logger.critical(
                    f"Unexpected error evaluating position {position_key}: {str(e)}",
                    exc_info=True,
                )
                continue

        return positions_to_close

    async def _evaluate_single_position(
        self,
        position_key: str,
        position: Dict[str, Any],
        price_map: Dict[str, float],
        current_time: float,
    ) -> Optional[str]:
        """Evaluate a single position for closure criteria"""
        condition_id = position["original_trade"]["condition_id"]
        current_price = price_map.get(condition_id)

        if current_price is None:
            return None  # Skip positions where we can't get current price

        entry_price = position["entry_price"]
        side = position["original_trade"]["side"].upper()
        amount = position["amount"]

        # Calculate profit metrics
        profit_pct, unrealized_pnl = self._calculate_position_profit(
            entry_price, current_price, side, amount
        )

        # Check exit conditions
        return self._check_position_exit_conditions(
            position_key, position, profit_pct, unrealized_pnl, current_time
        )

    def _calculate_position_profit(
        self, entry_price: float, current_price: float, side: str, amount: float
    ) -> Tuple[float, float]:
        """Calculate profit percentage and unrealized P&L for a position"""
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
            return 0.0, 0.0

        return profit_pct, unrealized_pnl

    def _check_position_exit_conditions(
        self,
        position_key: str,
        position: Dict[str, Any],
        profit_pct: float,
        unrealized_pnl: float,
        current_time: float,
    ) -> Optional[str]:
        """Check if a position meets exit criteria"""
        amount = position["amount"]

        # Take profit check
        if profit_pct >= self.settings.risk.take_profit_percentage:
            if amount > self.settings.risk.min_trade_amount * 5:  # Only log significant positions
                logger.info(
                    f"🎉 Take profit: {position_key} {profit_pct:.2%} (${unrealized_pnl:.2f})"
                )
            return "TAKE_PROFIT"

        # Stop loss check
        if profit_pct <= -self.settings.risk.stop_loss_percentage:
            logger.warning(f"🛑 Stop loss: {position_key} {profit_pct:.2%} (${unrealized_pnl:.2f})")
            return "STOP_LOSS"

        # Time-based exit (after 24 hours)
        position_age = current_time - position["timestamp"]
        if position_age > 86400:  # 24 hours
            if amount > self.settings.risk.min_trade_amount * 5:
                logger.info(f"⏰ Time exit: {position_key} ({position_age/3600:.1f}h)")
            return "TIME_EXIT"

        return None

    async def _close_positions(self, positions_to_close: List[Tuple[str, str]]) -> None:
        """Close positions that meet closure criteria"""
        if not positions_to_close:
            return

        # Batch close positions
        close_tasks = [
            self._close_position(position_key, reason)
            for position_key, reason in positions_to_close
        ]
        await asyncio.gather(*close_tasks, return_exceptions=True)

        logger.info(f"Closed {len(positions_to_close)} positions")

    async def _update_daily_loss_tracking(self) -> None:
        """Update daily loss tracking (called periodically)"""
        position_count = len(self.open_positions)
        if position_count > 0 and position_count % 5 == 0:  # Every 5th cycle
            await self._update_daily_loss()

    async def _perform_periodic_cleanup(self) -> None:
        """Perform periodic cleanup tasks"""
        position_count = len(self.open_positions)
        current_time = time.time()

        if position_count > 0 and current_time % 60 < 1:  # Roughly every minute
            self._check_circuit_breaker_conditions()

        if position_count > 0 and current_time % 300 < 1:  # Every 5 minutes
            await self._cleanup_stale_locks()

    async def _handle_position_management_failure(self, error: Exception) -> None:
        """Handle failures in position management"""
        logger.error(f"Position management failed: {error}", exc_info=True)

    async def _close_position(self, position_key: str, reason: str) -> None:
        """Close a specific position and clean up associated resources"""
        if position_key not in self.open_positions:
            return

        try:
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
        finally:
            # Always clean up the lock, even if position closing fails
            if position_key in self._position_locks:
                del self._position_locks[position_key]
                logger.debug(f"🧹 Cleaned up lock for position: {position_key}")

    async def _update_daily_loss(self) -> float:
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

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error updating daily loss: {str(e)[:100]}")
            return self.daily_loss
        except Exception as e:
            logger.critical(f"Unexpected error updating daily loss: {str(e)}", exc_info=True)
            return self.daily_loss

    def _check_circuit_breaker_conditions(self) -> None:
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

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error checking circuit breaker conditions: {str(e)[:100]}")
        except Exception as e:
            logger.critical(
                f"Unexpected error checking circuit breaker conditions: {str(e)}", exc_info=True
            )

    def _get_circuit_breaker_remaining_time(self) -> float:
        """Get remaining time for circuit breaker in minutes"""
        if not self.circuit_breaker_active or not self.circuit_breaker_time:
            return 0.0

        elapsed = time.time() - self.circuit_breaker_time
        remaining = max(0, 3600 - elapsed)  # 1 hour cooldown
        return remaining / 60  # Convert to minutes

    def activate_circuit_breaker(self, reason: str) -> None:
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

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker"""
        if self.circuit_breaker_active:
            logger.info(f"✅ Circuit breaker reset. Reason was: {self.circuit_breaker_reason}")
            self.circuit_breaker_active = False
            self.circuit_breaker_reason = ""
            self.circuit_breaker_time = None

    async def _cleanup_stale_locks(self) -> None:
        """Periodically clean up locks for positions that no longer exist"""
        stale_keys = [key for key in self._position_locks if key not in self.open_positions]
        for key in stale_keys:
            del self._position_locks[key]
            logger.debug(f"🧹 Cleaned up stale lock: {key}")
        if stale_keys:
            logger.info(f"🧹 Cleaned up {len(stale_keys)} stale position locks")

        # Monitor lock usage for memory leak detection
        lock_count = len(self._position_locks)
        position_count = len(self.open_positions)
        if lock_count > position_count + 10:  # Allow some buffer
            logger.warning(
                f"⚠️ High lock count detected: {lock_count} locks vs {position_count} positions"
            )
        elif lock_count > 1000:  # Absolute threshold
            logger.error(
                f"🚨 Excessive lock count: {lock_count} position locks may indicate memory leak"
            )

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
        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"❌ Network error during health check: {str(e)[:100]}")
            return False
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"❌ Data error during health check: {str(e)[:100]}")
            return False
        except Exception as e:
            logger.critical(f"❌ Unexpected error during health check: {str(e)}", exc_info=True)
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
