import asyncio
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from config.settings import settings
from core.circuit_breaker import CircuitBreaker
from core.clob_client import PolymarketClient
from core.exceptions import APIError, PolymarketAPIError, TradingError
from utils.alerts import send_error_alert, send_telegram_alert
from utils.exception_handler import exception_handler, safe_execute
from utils.helpers import BoundedCache, normalize_address
from utils.logging_security import SecureLogger
from utils.validation import InputValidator, ValidationError

# Configure Decimal for financial calculations
getcontext().prec = 28  # High precision for financial calculations
getcontext().rounding = ROUND_HALF_UP  # Banker's rounding for accuracy


# Helper for timezone-aware datetime operations
def get_current_time_utc() -> datetime:
    """Get current time in UTC timezone (thread-safe)"""
    return datetime.now(timezone.utc)


logger = logging.getLogger(__name__)


class TradeExecutor:
    """
    Executes copy trades on Polymarket with comprehensive risk management.

    This class handles the complete trade execution workflow including:
    - Position sizing calculations based on account balance and risk
    - Circuit breaker protection against excessive losses
    - Order placement and execution monitoring
    - Stop-loss and take-profit order management
    - Performance tracking and alerting

    Attributes:
        clob_client: Polymarket CLOB API client
        wallet_address: Trading wallet address
        daily_loss: Accumulated losses for the current day
        total_trades: Total number of trades executed
        successful_trades: Number of profitable trades
        failed_trades: Number of failed trades
        circuit_breaker_active: Whether circuit breaker is currently active
        open_positions: Dictionary of currently open positions

    Thread Safety:
        Uses asyncio locks to prevent race conditions in concurrent operations
    """

    def __init__(self, clob_client: PolymarketClient) -> None:
        """
        Initialize the trade executor with Polymarket client.

        Args:
            clob_client: Configured Polymarket CLOB API client for order execution
        """
        self.settings = settings
        self.clob_client = clob_client
        self.wallet_address: str = self.clob_client.wallet_address

        # Thread safety
        self._state_lock: asyncio.Lock = asyncio.Lock()
        # Position locks with 30-minute TTL and memory threshold monitoring
        self._position_locks: BoundedCache = BoundedCache(
            max_size=1000,
            ttl_seconds=1800,  # 30 minutes max TTL
            memory_threshold_mb=50.0,  # Alert if cache exceeds 50MB
            cleanup_interval_seconds=60,  # Background cleanup every minute
        )

        # State tracking with explicit types
        self.total_trades: int = 0
        self.successful_trades: int = 0
        self.failed_trades: int = 0
        # Open positions tracking (bounded with proper cleanup)
        self.open_positions: BoundedCache(
            max_size=100,  # Reasonable limit for concurrent positions
            ttl_seconds=86400,  # 24 hours max TTL
            memory_threshold_mb=10.0,
            cleanup_interval_seconds=300,  # Cleanup every 5 minutes
        )
        self.last_trade_time: Optional[float] = None
        self.start_time: float = time.time()

        # Circuit breaker (handles daily_loss internally)
        from pathlib import Path

        state_file = Path("data/circuit_breaker_state.json")
        self.circuit_breaker = CircuitBreaker(
            max_daily_loss=self.settings.risk.max_daily_loss,
            wallet_address=self.wallet_address,
            state_file=state_file,
            cooldown_seconds=3600,  # 1 hour
            alert_on_activation=self.settings.alerts.alert_on_circuit_breaker,
        )

        # Performance tracking
        self.trade_performance: List[Dict[str, Any]] = []
        self.max_performance_history: int = 1000

        SecureLogger.log(
            "info",
            "Initialized trade executor",
            {
                "wallet_address_masked": f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"
            },
        )

    @property
    def daily_loss(self) -> Decimal:
        """Backward compatibility: get daily loss from circuit breaker"""
        return Decimal(str(self.circuit_breaker.get_state()["daily_loss"]))

    @property
    def circuit_breaker_active(self) -> bool:
        """Backward compatibility: get circuit breaker active status"""
        return self.circuit_breaker.get_state()["active"]

    @property
    def circuit_breaker_reason(self) -> str:
        """Backward compatibility: get circuit breaker reason"""
        return self.circuit_breaker.get_state()["reason"]

    def _get_position_lock(self, position_key: str) -> asyncio.Lock:
        """Get or create a lock for position-specific operations."""
        existing_lock = self._position_locks.get(position_key)
        if existing_lock is None:
            lock = asyncio.Lock()
            self._position_locks.set(position_key, lock)
            return lock
        return existing_lock

    async def execute_copy_trade(
        self, original_trade: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a copy trade based on an original trade"""
        trade_id = None
        try:
            trade_id = self._generate_trade_id(original_trade)

            # Check circuit breaker
            circuit_breaker_result = await self._check_circuit_breaker_for_trade(
                trade_id
            )
            if circuit_breaker_result:
                return circuit_breaker_result

            # Validate and apply risk management
            validation_result = await self._validate_and_apply_risk_management(
                original_trade, trade_id
            )
            if validation_result:
                return validation_result

            # Get market data and calculate position
            market_data = await self._get_market_and_calculate_position(
                original_trade, trade_id
            )
            if not market_data["success"]:
                return market_data["result"]

            # Place order and track performance
            return await self._place_order_and_track_performance(
                original_trade, trade_id, market_data
            )

        except (ValidationError, ValueError, TypeError, KeyError) as e:
            # Validation errors - don't retry, return error immediately
            return await exception_handler.handle_exception(
                e,
                context={"trade_id": trade_id, "original_trade": original_trade},
                component="TradeExecutor",
                operation="execute_copy_trade",
                default_return={
                    "status": "error",
                    "error": f"Validation error: {str(e)[:100]}",
                    "trade_id": trade_id or "unknown",
                },
            )
        except (
            ConnectionError,
            TimeoutError,
            aiohttp.ClientError,
            APIError,
            PolymarketAPIError,
        ) as e:
            # Network/API errors - may retry
            return await exception_handler.handle_exception(
                e,
                context={"trade_id": trade_id, "original_trade": original_trade},
                component="TradeExecutor",
                operation="execute_copy_trade",
                default_return=await self._handle_trade_execution_error(
                    e, original_trade
                ),
                max_retries=2,
            )
        except TradingError as e:
            # Trading errors - don't retry
            return await exception_handler.handle_exception(
                e,
                context={"trade_id": trade_id, "original_trade": original_trade},
                component="TradeExecutor",
                operation="execute_copy_trade",
                default_return=await self._handle_trade_execution_error(
                    e, original_trade
                ),
            )
        except Exception as e:
            # Unknown errors - log as critical but don't crash
            return await exception_handler.handle_exception(
                e,
                context={"trade_id": trade_id, "original_trade": original_trade},
                component="TradeExecutor",
                operation="execute_copy_trade",
                default_return=await self._handle_trade_execution_error(
                    e, original_trade
                ),
            )

    def _generate_trade_id(self, original_trade: Dict[str, Any]) -> str:
        """Generate a unique trade ID"""
        return f"{original_trade['tx_hash']}_{original_trade['wallet_address'][-6:]}"

    async def _check_circuit_breaker_for_trade(
        self, trade_id: str
    ) -> Optional[Dict[str, Any]]:
        """Check circuit breaker status and return skip result if active"""
        return await safe_execute(
            self.circuit_breaker.check_trade_allowed,
            trade_id,
            context={"trade_id": trade_id},
            component="TradeExecutor",
            operation="check_circuit_breaker",
            default_return=None,  # Continue with trade if check fails (graceful degradation)
        )

    async def _validate_and_apply_risk_management(
        self, original_trade: Dict[str, Any], trade_id: str
    ) -> Optional[Dict[str, Any]]:
        """Validate trade data and apply risk management rules"""
        # Validate trade
        if not self._validate_trade(original_trade):
            return {
                "status": "invalid",
                "reason": "Invalid trade data",
                "trade_id": trade_id,
            }

        # Apply risk management
        risk_check = self._apply_risk_management(original_trade)
        if not risk_check["approved"]:
            logger.warning(
                f"⚠️ Trade rejected by risk management: {risk_check['reason']}"
            )
            return {
                "status": "rejected",
                "reason": risk_check["reason"],
                "trade_id": trade_id,
            }

        return None

    async def _get_market_and_calculate_position(
        self, original_trade: Dict[str, Any], trade_id: str
    ) -> Dict[str, Any]:
        """Get market data and calculate position size"""
        # Get market details
        market = await self.clob_client.get_market(original_trade["condition_id"])
        if not market:
            logger.error(
                f"❌ Could not get market details for {original_trade['condition_id']}"
            )
            return {
                "success": False,
                "result": {
                    "status": "failed",
                    "reason": "Market not found",
                    "trade_id": trade_id,
                },
            }

        # Calculate copy amount
        copy_amount = await self._calculate_copy_amount(original_trade, market)
        min_trade_amount_dec = Decimal(str(self.settings.risk.min_trade_amount))
        if copy_amount <= min_trade_amount_dec:
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
            await self._send_trade_alert(
                original_trade, copy_amount, result, execution_time
            )

        return success_result

    async def _handle_order_result(
        self,
        result: Any,
        original_trade: Dict[str, Any],
        copy_amount: Decimal,
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
        copy_amount: Decimal,
        execution_time: float,
        trade_id: str,
    ) -> Dict[str, Any]:
        """Handle successful order placement"""
        self.successful_trades += 1
        self.last_trade_time = time.time()

        # Record successful trade in circuit breaker
        await self.circuit_breaker.record_trade_result(success=True, trade_id=trade_id)

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

        # Maintain history size limit
        if len(self.trade_performance) > self.max_performance_history:
            self.trade_performance = self.trade_performance[
                -self.max_performance_history :
            ]

        # Track position
        position_key = f"{original_trade['condition_id']}_{original_trade['side']}"
        position_data = {
            "amount": copy_amount,
            "entry_price": original_trade["price"],
            "timestamp": time.time(),
            "original_trade": original_trade,
            "order_id": result["orderID"],
        }
        self.open_positions.set(position_key, position_data)

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
        copy_amount: Decimal,
        execution_time: float,
        trade_id: str,
    ) -> Dict[str, Any]:
        """Handle failed order placement"""
        self.failed_trades += 1

        # Record failed trade in circuit breaker
        await self.circuit_breaker.record_trade_result(success=False, trade_id=trade_id)

        # Track failed performance
        performance = {
            "timestamp": time.time(),
            "original_trade": original_trade,
            "copy_amount": copy_amount,
            "execution_time": execution_time,
            "status": "failed",
        }
        self.trade_performance.append(performance)

        # Maintain history size limit
        if len(self.trade_performance) > self.max_performance_history:
            self.trade_performance = self.trade_performance[
                -self.max_performance_history :
            ]

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
        copy_amount: Decimal,
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
            logger.error(
                f"❌ Data validation error executing copy trade: {str(error)[:100]}"
            )
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
                    "timestamp": datetime.now(timezone.utc).isoformat(),
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
            InputValidator.validate_hex_string(
                trade["tx_hash"], min_length=66, max_length=66
            )

            return True

        except ValidationError as e:
            exception_handler.log_exception(
                e,
                context={"trade": trade},
                component="TradeExecutor",
                operation="validate_trade",
                include_stack_trace=False,
            )
            return False
        except (ValueError, TypeError, KeyError) as e:
            exception_handler.log_exception(
                e,
                context={"trade": trade},
                component="TradeExecutor",
                operation="validate_trade",
                include_stack_trace=False,
            )
            return False
        except Exception as e:
            exception_handler.log_exception(
                e,
                context={"trade": trade},
                component="TradeExecutor",
                operation="validate_trade",
            )
            return False

        # Validate timestamp (not too old)
        trade_age = (datetime.now(timezone.utc) - trade["timestamp"]).total_seconds()
        if trade_age > 300:  # 5 minutes
            logger.warning(f"⚠️ Trade is {trade_age:.1f} seconds old. May be stale.")

        return True

    def _apply_risk_management(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Apply risk management rules to a trade"""
        # Daily loss circuit breaker check (circuit breaker module handles this, but check here too for early rejection)
        cb_state = self.circuit_breaker.get_state()
        if cb_state["active"]:
            return {
                "approved": False,
                "reason": f"Circuit breaker active: {cb_state['reason']}",
            }

        # Position size limit
        if trade["amount"] > self.settings.risk.max_position_size:
            return {
                "approved": False,
                "reason": f"Position size too large (${trade['amount']:.2f} > ${self.settings.risk.max_position_size:.2f})",
            }

        # Minimum trade amount
        if trade["amount"] < self.settings.risk.min_trade_amount:
            return {
                "approved": False,
                "reason": f"Trade amount below minimum (${trade['amount']:.2f} < ${self.settings.risk.min_trade_amount:.2f})",
            }

        # Maximum concurrent positions
        positions_count = self.open_positions.get_stats()["size"]
        if positions_count >= self.settings.risk.max_concurrent_positions:
            return {
                "approved": False,
                "reason": f"Max concurrent positions reached ({positions_count} / {self.settings.risk.max_concurrent_positions})",
            }

        # Confidence score check
        if trade["confidence_score"] < self.settings.monitoring.min_confidence_score:
            return {
                "approved": False,
                "reason": f"Low confidence score ({trade['confidence_score']:.2f} < {self.settings.monitoring.min_confidence_score:.2f})",
            }

        return {"approved": True}

    async def _calculate_copy_amount(
        self, original_trade: Dict[str, Any], market: Dict[str, Any]
    ) -> Decimal:
        """Calculate how much to trade based on risk management rules with Decimal precision"""
        try:
            # Get current balance and price concurrently (already optimized)
            balance_task = self.clob_client.get_balance()
            current_price_task = self.clob_client.get_current_price(
                original_trade["condition_id"]
            )

            balance, current_price = await asyncio.gather(
                balance_task, current_price_task
            )

            if balance is None:
                logger.warning("⚠️ Could not get balance. Using conservative amount.")
                return min(
                    Decimal(str(original_trade["amount"])) * Decimal("0.1"),
                    Decimal(str(self.settings.risk.max_position_size)),
                )

            if current_price is None:
                current_price = original_trade["price"]

            # High precision financial calculations using Decimal
            try:
                # Convert all monetary values to Decimal for precision
                account_balance_dec = Decimal(str(balance))
                current_price_dec = Decimal(str(current_price))
                entry_price_dec = Decimal(str(original_trade["price"]))
                risk_percentage_dec = Decimal("0.01")  # 1% risk per trade
                original_amount_dec = Decimal(str(original_trade["amount"]))

                # Calculate price risk with minimum threshold
                price_risk_dec = abs(current_price_dec - entry_price_dec)
                min_price_risk = Decimal("0.0001")
                price_risk_dec = max(price_risk_dec, min_price_risk)

                # Calculate account risk (1% of balance)
                account_risk_dec = account_balance_dec * risk_percentage_dec

                # Calculate position size with multiple safeguards
                position_size_dec = account_risk_dec / price_risk_dec

                # Apply safeguards using Decimal
                max_position_dec = Decimal(str(self.settings.risk.max_position_size))
                max_account_risk_dec = account_balance_dec * Decimal(
                    "0.1"
                )  # Never risk more than 10%

                position_size_dec = min(
                    position_size_dec, max_position_dec, max_account_risk_dec
                )

                # Ensure minimum trade amount
                min_trade_dec = Decimal(str(self.settings.risk.min_trade_amount))
                position_size_dec = max(position_size_dec, min_trade_dec)

                # Round to 4 decimal places for precision
                copy_amount = position_size_dec.quantize(Decimal("0.0001"))

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
                # Fallback to conservative sizing using Decimal
                original_amount_dec = Decimal(str(original_trade["amount"]))
                max_position_dec = Decimal(str(self.settings.risk.max_position_size))
                copy_amount = min(
                    original_amount_dec * Decimal("0.1"), max_position_dec
                )

            return copy_amount

        except (ConnectionError, TimeoutError, aiohttp.ClientError, APIError) as e:
            fallback_amount = min(
                Decimal(str(original_trade["amount"])) * Decimal("0.1"),
                Decimal(str(self.settings.risk.max_position_size)),
            )
            return await exception_handler.handle_exception(
                e,
                context={
                    "original_trade": original_trade,
                    "fallback_amount": fallback_amount,
                },
                component="TradeExecutor",
                operation="calculate_copy_amount",
                default_return=fallback_amount,
            )
        except (ValueError, TypeError, KeyError, InvalidOperation) as e:
            fallback_amount = min(
                Decimal(str(original_trade["amount"])) * Decimal("0.1"),
                Decimal(str(self.settings.risk.max_position_size)),
            )
            return await exception_handler.handle_exception(
                e,
                context={
                    "original_trade": original_trade,
                    "fallback_amount": fallback_amount,
                },
                component="TradeExecutor",
                operation="calculate_copy_amount",
                default_return=fallback_amount,
            )
        except Exception as e:
            fallback_amount = min(
                Decimal(str(original_trade["amount"])) * Decimal("0.1"),
                Decimal(str(self.settings.risk.max_position_size)),
            )
            return await exception_handler.handle_exception(
                e,
                context={
                    "original_trade": original_trade,
                    "fallback_amount": fallback_amount,
                },
                component="TradeExecutor",
                operation="calculate_copy_amount",
                default_return=fallback_amount,
            )

    def _get_token_id_for_outcome(
        self, market: Dict[str, Any], trade: Dict[str, Any]
    ) -> Optional[str]:
        """Get the correct token ID for the trade outcome"""
        try:
            # This depends on the market structure
            if (
                "tokens" in market
                and isinstance(market["tokens"], list)
                and market["tokens"]
            ):
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
            exception_handler.log_exception(
                e,
                context={"market": market, "trade": trade},
                component="TradeExecutor",
                operation="get_token_id_for_outcome",
                include_stack_trace=False,
            )
            return None
        except Exception as e:
            exception_handler.log_exception(
                e,
                context={"market": market, "trade": trade},
                component="TradeExecutor",
                operation="get_token_id_for_outcome",
            )
            return None

    async def manage_positions(self) -> None:
        """Main position management orchestrator"""
        if not await self._should_manage_positions():
            return

        try:
            current_prices = await self._get_current_prices_for_positions()
            positions_to_close = await self._evaluate_positions_for_closure(
                current_prices
            )
            await self._close_positions(positions_to_close)
            await self._update_daily_loss_tracking()
            await self._perform_periodic_cleanup()
        except (ConnectionError, TimeoutError, aiohttp.ClientError, APIError) as e:
            # Network/API errors - log and continue
            await exception_handler.handle_exception(
                e,
                context={"position_count": self.open_positions.get_stats()["size"]},
                component="TradeExecutor",
                operation="manage_positions",
                default_return=None,
            )
            await self._handle_position_management_failure(e)
        except (ValueError, TypeError, KeyError) as e:
            # Data errors - log and continue
            await exception_handler.handle_exception(
                e,
                context={"position_count": self.open_positions.get_stats()["size"]},
                component="TradeExecutor",
                operation="manage_positions",
                default_return=None,
            )
            await self._handle_position_management_failure(e)
        except Exception as e:
            # Unknown errors - log as critical but don't crash
            await exception_handler.handle_exception(
                e,
                context={"position_count": self.open_positions.get_stats()["size"]},
                component="TradeExecutor",
                operation="manage_positions",
                default_return=None,
            )
            await self._handle_position_management_failure(e)

    async def _should_manage_positions(self) -> bool:
        """Determine if position management should proceed"""
        position_count = self.open_positions.get_stats()["size"]
        if position_count == 0:
            logger.debug("No open positions to manage")
            return False

        if position_count > 10:
            logger.info(f"📊 Managing {position_count} open positions")
        else:
            logger.debug(f"Managing {position_count} positions")

        return True

    async def _get_current_prices_for_positions(self) -> Dict[str, float]:
        """Get current market prices for all open positions"""
        unique_condition_ids = set(
            position["original_trade"]["condition_id"]
            for position in self.open_positions._cache.keys()
        )

        # Get prices for all unique conditions concurrently
        price_tasks = [
            self.clob_client.get_current_price(condition_id)
            for condition_id in unique_condition_ids
        ]
        price_results = await asyncio.gather(*price_tasks, return_exceptions=True)

        # Create price lookup map
        price_map = {
            condition_id: price_result
            for condition_id, price_result in zip(unique_condition_ids, price_results)
            if isinstance(price_result, float)
        }

        # Log warnings for failed price fetches
        for condition_id, price_result in zip(unique_condition_ids, price_results):
            if not isinstance(price_result, float):
                logger.warning(
                    f"Failed to get price for condition {condition_id}: {price_result}"
                )

        return price_map

    async def _evaluate_positions_for_closure(
        self, price_map: Dict[str, float]
    ) -> List[Tuple[str, str]]:
        """Evaluate which positions should be closed based on current prices"""
        positions_to_close = []
        current_time = time.time()

        for position_key in self.open_positions._cache.keys():
            position = self.open_positions.get(position_key)
            if position is None:
                continue
            try:
                close_reason = await self._evaluate_single_position(
                    position_key, position, price_map, current_time
                )
                if close_reason:
                    positions_to_close.append((position_key, close_reason))
            except (ValueError, TypeError, KeyError, ZeroDivisionError) as e:
                exception_handler.log_exception(
                    e,
                    context={"position_key": position_key, "position": position},
                    component="TradeExecutor",
                    operation="evaluate_position",
                    include_stack_trace=False,
                )
                continue
            except Exception as e:
                exception_handler.log_exception(
                    e,
                    context={"position_key": position_key, "position": position},
                    component="TradeExecutor",
                    operation="evaluate_position",
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
        self, entry_price: float, current_price: float, side: str, amount: Decimal
    ) -> Tuple[float, Decimal]:
        """Calculate profit percentage and unrealized P&L for a position using Decimal"""
        # Convert prices to Decimal for precise calculation
        entry_price_dec = Decimal(str(entry_price))
        current_price_dec = Decimal(str(current_price))

        if side == "BUY":
            # For long positions: profit when price increases
            price_diff_dec = current_price_dec - entry_price_dec
            profit_pct = (
                float(price_diff_dec / entry_price_dec)
                if entry_price_dec != Decimal("0")
                else 0.0
            )
            unrealized_pnl = price_diff_dec * amount
        elif side == "SELL":
            # For short positions: profit when price decreases
            price_diff_dec = entry_price_dec - current_price_dec
            profit_pct = (
                float(price_diff_dec / entry_price_dec)
                if entry_price_dec != Decimal("0")
                else 0.0
            )
            unrealized_pnl = price_diff_dec * amount
        else:
            return 0.0, Decimal("0")

        return profit_pct, unrealized_pnl

    def _check_position_exit_conditions(
        self,
        position_key: str,
        position: Dict[str, Any],
        profit_pct: float,
        unrealized_pnl: Decimal,
        current_time: float,
    ) -> Optional[str]:
        """Check if a position meets exit criteria"""
        amount = position["amount"]

        # Take profit check
        if profit_pct >= self.settings.risk.take_profit_percentage:
            if (
                amount > self.settings.risk.min_trade_amount * 5
            ):  # Only log significant positions
                logger.info(
                    f"🎉 Take profit: {position_key} {profit_pct:.2%} (${unrealized_pnl:.2f})"
                )
            return "TAKE_PROFIT"

        # Stop loss check
        if profit_pct <= -self.settings.risk.stop_loss_percentage:
            logger.warning(
                f"🛑 Stop loss: {position_key} {profit_pct:.2%} (${unrealized_pnl:.2f})"
            )
            return "STOP_LOSS"

        # Time-based exit (after 24 hours)
        position_age = current_time - position["timestamp"]
        if position_age > 86400:  # 24 hours
            if amount > self.settings.risk.min_trade_amount * 5:
                logger.info(
                    f"⏰ Time exit: {position_key} ({position_age / 3600:.1f}h)"
                )
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
        # Circuit breaker handles daily loss tracking internally
        await self.circuit_breaker.periodic_check()

    async def _perform_periodic_cleanup(self) -> None:
        """Perform periodic cleanup tasks"""
        position_count = self.open_positions.get_stats()["size"]
        current_time = time.time()

        if position_count > 0 and current_time % 60 < 1:  # Roughly every minute
            # Circuit breaker handles its own periodic checks
            await self.circuit_breaker.periodic_check()

        if position_count > 0 and current_time % 300 < 1:  # Every 5 minutes
            await self._cleanup_stale_locks()

    async def _handle_position_management_failure(self, error: Exception) -> None:
        """Handle failures in position management"""
        logger.exception(f"Position management failed: {error}")

    async def _close_position(self, position_key: str, reason: str) -> None:
        """Close a specific position and clean up associated resources"""
        position = self.open_positions.get(position_key)
        if position is None:
            return

        try:
            trade = position["original_trade"]

            # Create opposite trade to close position
            close_trade = trade.copy()
            close_trade["side"] = "SELL" if trade["side"].upper() == "BUY" else "BUY"
            close_trade["amount"] = position["amount"]
            close_trade["price"] = (
                await self.clob_client.get_current_price(trade["condition_id"])
                or trade["price"]
            )
            close_trade["confidence_score"] = 0.99  # High confidence for closing

            logger.info(
                f"CloseOperation for {position_key}: {close_trade['side']} {close_trade['amount']:.4f} shares (Reason: {reason})"
            )

            result = await self.execute_copy_trade(close_trade)

            if result["status"] == "success":
                self.open_positions.delete(position_key)
                logger.info(
                    f"✅ Position closed successfully: {position_key} (Reason: {reason})"
                )

                # Update P&L tracking using Decimal for precision
                entry_value_dec = position["amount"] * Decimal(
                    str(position["entry_price"])
                )
                exit_value_dec = position["amount"] * Decimal(str(close_trade["price"]))
                pnl_dec = (
                    exit_value_dec - entry_value_dec
                    if trade["side"].upper() == "BUY"
                    else entry_value_dec - exit_value_dec
                )

                if pnl_dec < Decimal("0"):
                    # Record loss in circuit breaker (convert to float for backward compatibility)
                    pnl_float = float(pnl_dec)
                    await self.circuit_breaker.record_loss(abs(pnl_float))
                    cb_state = self.circuit_breaker.get_state()
                    logger.warning(
                        f"📉 Position closed at loss: ${abs(pnl_dec):.2f}. Daily loss: ${cb_state['daily_loss']:.2f}"
                    )
                elif pnl_dec > Decimal("0"):
                    # Record profit in circuit breaker (resets consecutive losses)
                    await self.circuit_breaker.record_profit(float(pnl_dec))
        finally:
            # Explicitly remove position lock when position is closed
            # BoundedCache TTL will also handle cleanup, but explicit removal prevents leaks
            self._position_locks.delete(position_key)

    async def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker"""
        await self.circuit_breaker.reset("Manual reset")

    async def _cleanup_stale_locks(self) -> None:
        """Position locks are automatically cleaned up by BoundedCache with TTL"""
        # BoundedCache handles automatic cleanup - this method kept for compatibility

        # Monitor lock usage for memory leak detection
        lock_count = self._position_locks.get_stats()["size"]
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
                exception_handler.log_exception(
                    ValueError("Could not get balance"),
                    component="TradeExecutor",
                    operation="health_check",
                    include_stack_trace=False,
                )
                return False

            # Check circuit breaker status
            cb_state = self.circuit_breaker.get_state()
            if cb_state["active"]:
                logger.warning(
                    f"⚠️ Health check warning: Circuit breaker active for {cb_state['remaining_minutes']:.1f} more minutes"
                )

            # Check open positions
            position_count = self.open_positions.get_stats()["size"]
            if position_count > self.settings.risk.max_concurrent_positions * 1.5:
                logger.warning(
                    f"⚠️ Health check warning: Too many open positions ({position_count})"
                )

            cb_state = self.circuit_breaker.get_state()
            position_count = self.open_positions.get_stats()["size"]
            logger.info(
                f"✅ Health check passed. Balance: ${balance:.2f}, "
                f"Positions: {position_count}, "
                f"Daily Loss: ${cb_state['daily_loss']:.2f}"
            )
            return True
        except (ConnectionError, TimeoutError, aiohttp.ClientError, APIError) as e:
            return await exception_handler.handle_exception(
                e,
                component="TradeExecutor",
                operation="health_check",
                default_return=False,
            )
        except (ValueError, TypeError, KeyError) as e:
            return await exception_handler.handle_exception(
                e,
                component="TradeExecutor",
                operation="health_check",
                default_return=False,
            )
        except Exception as e:
            return await exception_handler.handle_exception(
                e,
                component="TradeExecutor",
                operation="health_check",
                default_return=False,
            )

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        success_rate = (
            self.successful_trades / self.total_trades if self.total_trades > 0 else 0
        )
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

        cb_state = self.circuit_breaker.get_state()
        return {
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "success_rate": success_rate,
            "daily_loss": cb_state["daily_loss"],
            "open_positions": len(self.open_positions),
            "total_pnl": total_pnl,
            "circuit_breaker_active": cb_state["active"],
            "circuit_breaker_reason": cb_state["reason"],
            "runtime_seconds": runtime,
            "uptime_hours": runtime / 3600,
        }

    async def monitor_risk_parameters(self) -> Dict[str, Any]:
        """
        Monitor risk parameters via MCP monitoring server.

        This method is called by MCP monitoring server to track:
        - Component memory usage
        - Risk parameter changes
        - Performance metrics

        Returns:
            Dictionary with risk parameter monitoring results
        """
        try:
            # Get memory usage
            memory_mb = 0.0
            try:
                import psutil

                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
            except ImportError:
                logger.warning("psutil not available, memory monitoring disabled")

            # Get cache memory usage
            position_cache_memory = self._position_locks.get_memory_usage_mb()
            open_positions_memory = self.open_positions.get_memory_usage_mb()

            # Risk parameter exposure (read-only)
            risk_parameters = {
                "max_position_size": self.settings.risk.max_position_size,
                "max_daily_loss": self.settings.risk.max_daily_loss,
                "min_trade_amount": self.settings.risk.min_trade_amount,
                "max_concurrent_positions": self.settings.risk.max_concurrent_positions,
                "stop_loss_percentage": self.settings.risk.stop_loss_percentage,
                "take_profit_percentage": self.settings.risk.take_profit_percentage,
                "max_slippage": self.settings.risk.max_slippage,
            }

            # Performance metrics
            performance = await self.get_performance_metrics()

            # Build monitoring result
            result = {
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component": "trade_executor",
                "memory_mb": {
                    "total": memory_mb,
                    "position_cache": position_cache_memory,
                    "open_positions": open_positions_memory,
                },
                "risk_parameters": risk_parameters,
                "performance": {
                    "total_trades": performance["total_trades"],
                    "success_rate": performance["success_rate"],
                    "daily_loss": performance["daily_loss"],
                    "circuit_breaker_active": performance["circuit_breaker_active"],
                    "uptime_hours": performance["uptime_hours"],
                },
                "warnings": [],
            }

            # Add warnings for memory thresholds
            memory_threshold = 200  # Default threshold from monitoring config
            if memory_mb > memory_threshold * 0.9:
                result["warnings"].append(
                    f"Memory usage {memory_mb:.1f}MB near limit {memory_threshold}MB"
                )
            if memory_mb > memory_threshold:
                result["warnings"].append(
                    f"Memory usage {memory_mb:.1f}MB exceeds limit {memory_threshold}MB"
                )

            return result

        except Exception as e:
            logger.error(f"Error monitoring risk parameters: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def check_mcp_test_coverage_impact(self, coverage: float) -> Dict[str, Any]:
        """
        Check impact of MCP test coverage on trade executor.

        This is called by MCP testing server to verify that test coverage
        thresholds don't impact trading operations.

        Args:
            coverage: Current test coverage percentage (0.0 to 1.0)

        Returns:
            Dictionary with impact assessment
        """
        try:
            # Get current performance
            performance = await self.get_performance_metrics()

            # Impact assessment
            impact = {
                "status": "ok",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "test_coverage": coverage,
                "trade_executor_status": {
                    "circuit_breaker_active": performance["circuit_breaker_active"],
                    "total_trades": performance["total_trades"],
                    "success_rate": performance["success_rate"],
                },
                "impact_analysis": {
                    "test_coverage_acceptable": coverage >= 0.85,  # 85% threshold
                    "trading_affected": performance["circuit_breaker_active"],
                    "performance_degraded": performance["success_rate"] < 0.9,
                },
            }

            # Warnings
            if coverage < 0.85:
                impact["warnings"] = [
                    f"Test coverage {coverage:.1%} below 85% threshold"
                ]
            elif performance["circuit_breaker_active"]:
                impact["warnings"] = [
                    "Circuit breaker is active - trading may be degraded"
                ]
            else:
                impact["warnings"] = []

            return impact

        except Exception as e:
            logger.error(f"Error checking MCP test coverage impact: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def get_risk_parameter_usage_report(self) -> Dict[str, Any]:
        """
        Generate report of risk parameter usage patterns.

        This integrates with MCP codebase_search server to find all
        usages of risk parameters throughout the codebase.

        Returns:
            Dictionary with risk parameter usage report
        """
        try:
            # Import MCP codebase search
            from mcp.codebase_search import CodebaseSearchServer

            search_server = CodebaseSearchServer()

            # Search patterns for risk parameters
            patterns = {
                "max_position_size": r"max_position_size",
                "max_daily_loss": r"max_daily_loss|daily_loss_limit",
                "stop_loss": r"stop_loss_percentage|SL_PERCENTAGE",
                "take_profit": r"take_profit_percentage|TP_PERCENTAGE",
                "max_slippage": r"max_slippage|SLIPPAGE_THRESHOLD",
                "circuit_breaker": r"circuit_breaker\.activate|\.is_active",
            }

            report = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component": "trade_executor",
                "parameter_usage": {},
                "total_occurrences": 0,
            }

            # Search for each pattern
            for param_name, pattern in patterns.items():
                try:
                    result = await search_server.search_pattern(pattern, max_results=50)

                    report["parameter_usage"][param_name] = {
                        "pattern": pattern,
                        "occurrences": len(result.get("matches", [])),
                        "locations": result.get("matches", [])[:10],  # Top 10
                    }

                    report["total_occurrences"] += len(result.get("matches", []))

                except Exception as e:
                    logger.error(f"Error searching for '{param_name}': {e}")
                    report["parameter_usage"][param_name] = {
                        "pattern": pattern,
                        "error": str(e),
                    }

            return report

        except ImportError as e:
            logger.warning(f"⚠️ Codebase search server not available: {e}")
            return {
                "status": "unavailable",
                "error": "Codebase search server not available",
            }
        except Exception as e:
            logger.error(
                f"Error generating risk parameter usage report: {e}", exc_info=True
            )
            return {
                "status": "error",
                "error": str(e),
            }

    async def execute_endgame_trade(
        self, condition_id: str, token_id: str, side: str, amount: Decimal, price: float
    ) -> Dict[str, Any]:
        """
        Execute an endgame sweeper trade with enhanced risk management.

        This method is specifically designed for the endgame strategy and includes:
        - Additional validation for high-probability trades
        - Enhanced logging for endgame-specific metrics
        - Proper integration with circuit breaker for daily loss tracking
        - Position tracking with endgame-specific metadata

        Args:
            condition_id: Market condition ID
            token_id: Token ID for the outcome
            side: Trade side ("BUY" or "SELL")
            amount: Position size in USDC (Decimal)
            price: Entry price (float)

        Returns:
            Dictionary with execution result:
            {
                "status": "success" | "failed" | "error",
                "order_id": str (if successful),
                "position_key": str (if successful),
                "error": str (if failed)
            }

        Raises:
            TradingError: If trade execution fails
            ValidationError: If inputs are invalid
        """
        try:
            # Validate inputs
            InputValidator.validate_condition_id(condition_id)
            InputValidator.validate_price(price)
            InputValidator.validate_trade_amount(float(amount))

            # Generate trade ID
            trade_id = f"endgame_{condition_id[-8:]}_{int(time.time())}"

            logger.info(
                f"🎯 Executing endgame trade: {side} ${amount:.2f} at ${price:.4f} "
                f"({condition_id[-8:]})"
            )

            # Check circuit breaker before execution
            cb_result = await self.circuit_breaker.check_trade_allowed(trade_id)
            if cb_result:
                logger.warning(
                    f"⚠️ Endgame trade blocked by circuit breaker: {cb_result['reason']}"
                )
                return {
                    "status": "blocked",
                    "reason": cb_result["reason"],
                    "trade_id": trade_id,
                }

            # Additional risk checks for endgame trades
            if not self._validate_endgame_trade(amount, price):
                return {
                    "status": "rejected",
                    "reason": "Endgame trade validation failed",
                    "trade_id": trade_id,
                }

            # Place order
            result = await self.clob_client.place_order(
                condition_id=condition_id,
                side=side,
                amount=amount,
                price=price,
                token_id=token_id,
            )

            if not result or "orderID" not in result:
                logger.error(f"❌ Endgame trade failed: {result}")
                await self.circuit_breaker.record_trade_result(
                    success=False, trade_id=trade_id
                )
                return {
                    "status": "failed",
                    "reason": "Order placement failed",
                    "trade_id": trade_id,
                }

            # Track position
            position_key = f"{condition_id}_{side}_endgame"
            position_data = {
                "amount": amount,
                "entry_price": Decimal(str(price)),
                "timestamp": time.time(),
                "condition_id": condition_id,
                "token_id": token_id,
                "side": side,
                "is_endgame": True,
                "order_id": result["orderID"],
            }

            self.open_positions.set(position_key, position_data)

            # Record successful trade
            await self.circuit_breaker.record_trade_result(
                success=True, trade_id=trade_id
            )

            logger.info(
                f"✅ Endgame trade executed: {result['orderID']} "
                f"({condition_id[-8:]}) | Position: ${amount:.2f}"
            )

            return {
                "status": "success",
                "order_id": result["orderID"],
                "position_key": position_key,
                "condition_id": condition_id,
                "amount": amount,
                "price": price,
                "trade_id": trade_id,
            }

        except (ValidationError, ValueError) as e:
            # Validation errors - don't retry
            logger.error(f"❌ Endgame trade validation error: {e}")
            return {
                "status": "invalid",
                "error": str(e)[:100],
                "trade_id": trade_id,
            }

        except TradingError as e:
            # Trading errors - don't retry
            logger.error(f"❌ Endgame trading error: {e}")
            await self.circuit_breaker.record_trade_result(
                success=False, trade_id=trade_id
            )
            return {
                "status": "error",
                "error": str(e)[:100],
                "trade_id": trade_id,
            }

        except Exception as e:
            # Unexpected errors - log and return error
            logger.exception(f"❌ Unexpected error executing endgame trade: {e}")
            await self.circuit_breaker.record_trade_result(
                success=False, trade_id=trade_id
            )
            return {
                "status": "error",
                "error": str(e)[:100],
                "trade_id": trade_id,
            }

    def _validate_endgame_trade(self, amount: Decimal, price: float) -> bool:
        """
        Additional validation for endgame trades.

        Args:
            amount: Position size in USDC
            price: Entry price

        Returns:
            True if trade passes validation, False otherwise
        """
        # Check position size limits
        max_position = Decimal(str(self.settings.risk.max_position_size))
        if amount > max_position:
            logger.warning(
                f"⚠️ Endgame trade amount ${amount:.2f} exceeds max ${max_position:.2f}"
            )
            return False

        # Check price is reasonable (between 0.01 and 0.99 for endgame)
        if not (0.01 <= price <= 0.99):
            logger.warning(f"⚠️ Endgame trade price ${price:.4f} outside valid range")
            return False

        # Check minimum trade amount
        min_trade = Decimal(str(self.settings.risk.min_trade_amount))
        if amount < min_trade:
            logger.warning(
                f"⚠️ Endgame trade amount ${amount:.2f} below minimum ${min_trade:.2f}"
            )
            return False

        # Check price makes sense for endgame strategy (should be > 0.95)
        if price < 0.95:
            logger.warning(
                f"⚠️ Endgame trade probability {price:.1%} below 95% threshold"
            )
            return False

        return True
