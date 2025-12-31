"""
Circuit Breaker Module for Trade Protection

Provides robust circuit breaker functionality with:
- Atomic state transitions (no race conditions)
- Proper exception handling during market volatility
- Graceful degradation when circuit opens
- Daily loss reset at UTC midnight with persistence
- Telegram alerts with recovery ETA

This module is thread-safe and designed for production use.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from utils.alerts import send_telegram_alert

logger = logging.getLogger(__name__)


class CircuitBreakerState:
    """Immutable state container for circuit breaker"""

    def __init__(
        self,
        active: bool = False,
        reason: str = "",
        activation_time: Optional[float] = None,
        daily_loss: float = 0.0,
        last_reset_date: Optional[datetime] = None,
        consecutive_losses: int = 0,
        failed_trades: int = 0,
        total_trades: int = 0,
    ) -> None:
        self.active = active
        self.reason = reason
        self.activation_time = activation_time
        self.daily_loss = daily_loss
        self.last_reset_date = (
            last_reset_date if last_reset_date else datetime.now(timezone.utc)
        )
        self.consecutive_losses = consecutive_losses
        self.failed_trades = failed_trades
        self.total_trades = total_trades

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for persistence"""
        return {
            "active": self.active,
            "reason": self.reason,
            "activation_time": self.activation_time,
            "daily_loss": self.daily_loss,
            "last_reset_date": (
                self.last_reset_date.isoformat() if self.last_reset_date else None
            ),
            "consecutive_losses": self.consecutive_losses,
            "failed_trades": self.failed_trades,
            "total_trades": self.total_trades,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CircuitBreakerState":
        """Create state from dictionary"""
        last_reset_date = None
        if data.get("last_reset_date"):
            try:
                last_reset_date = datetime.fromisoformat(data["last_reset_date"])
                if last_reset_date.tzinfo is None:
                    last_reset_date = last_reset_date.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing last_reset_date: {e}")
                last_reset_date = datetime.now(timezone.utc)

        return cls(
            active=data.get("active", False),
            reason=data.get("reason", ""),
            activation_time=data.get("activation_time"),
            daily_loss=data.get("daily_loss", 0.0),
            last_reset_date=last_reset_date,
            consecutive_losses=data.get("consecutive_losses", 0),
            failed_trades=data.get("failed_trades", 0),
            total_trades=data.get("total_trades", 0),
        )


class CircuitBreaker:
    """
    Thread-safe circuit breaker for trade protection.

    Features:
    - Atomic state transitions with asyncio locks
    - Daily loss tracking with UTC midnight reset
    - Consecutive loss tracking (5 losses trigger circuit)
    - Failure rate tracking (50%+ failure rate triggers circuit)
    - State persistence across restarts
    - Recovery ETA calculation and alerts
    - Graceful degradation during exceptions

    Thread Safety:
        All state modifications are protected by _state_lock to prevent race conditions.
    """

    # Default cooldown period: 1 hour
    DEFAULT_COOLDOWN_SECONDS = 3600

    # Consecutive loss threshold
    CONSECUTIVE_LOSS_THRESHOLD = 5

    # Failure rate threshold (50%)
    FAILURE_RATE_THRESHOLD = 0.5

    # Minimum trades before checking failure rate
    MIN_TRADES_FOR_FAILURE_RATE = 10

    def __init__(
        self,
        max_daily_loss: float,
        wallet_address: str,
        state_file: Optional[Path] = None,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
        alert_on_activation: bool = True,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            max_daily_loss: Maximum daily loss before circuit breaker activates
            wallet_address: Wallet address for logging/alerting
            state_file: Optional path to state persistence file
            cooldown_seconds: Cooldown period after activation (default: 1 hour)
            alert_on_activation: Whether to send Telegram alerts on activation
        """
        self.max_daily_loss = max_daily_loss
        self.wallet_address = wallet_address
        self.cooldown_seconds = cooldown_seconds
        self.alert_on_activation = alert_on_activation

        # Thread safety
        self._state_lock: asyncio.Lock = asyncio.Lock()

        # State persistence
        self.state_file = state_file or Path("data/circuit_breaker_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize state (load from disk if available)
        self._state = self._load_state()

        # Note: Daily loss reset check happens on first use (lazy initialization)
        # This avoids issues with asyncio.create_task during __init__

        logger.info(
            f"Circuit breaker initialized: max_daily_loss=${max_daily_loss:.2f}, "
            f"active={self._state.active}, daily_loss=${self._state.daily_loss:.2f}"
        )

    def _load_state(self) -> CircuitBreakerState:
        """Load state from disk if available"""
        try:
            if self.state_file.exists():
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    state = CircuitBreakerState.from_dict(data)

                    # Check if daily loss should be reset (crossed midnight UTC)
                    now = datetime.now(timezone.utc)
                    if (
                        state.last_reset_date
                        and now.date() > state.last_reset_date.date()
                    ):
                        logger.info(
                            f"Daily loss reset detected: last reset was {state.last_reset_date.date()}, "
                            f"today is {now.date()}"
                        )
                        state.daily_loss = 0.0
                        state.last_reset_date = now
                        state.consecutive_losses = 0

                    return state
        except (json.JSONDecodeError, IOError, ValueError, TypeError) as e:
            logger.warning(f"Error loading circuit breaker state: {e}. Using defaults.")
        except Exception as e:
            logger.exception(f"Unexpected error loading circuit breaker state: {e}")

        # Return default state
        return CircuitBreakerState()

    async def _save_state(self) -> None:
        """Save state to disk atomically"""
        try:
            # Write to temporary file first, then rename (atomic on most filesystems)
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(self._state.to_dict(), f, indent=2)

            # Atomic rename
            temp_file.replace(self.state_file)
        except (IOError, OSError) as e:
            logger.error(f"Error saving circuit breaker state: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error saving circuit breaker state: {e}")

    async def _check_and_reset_daily_loss(self) -> None:
        """Check if daily loss should be reset at UTC midnight"""
        try:
            async with self._state_lock:
                now = datetime.now(timezone.utc)

                # Check if we've crossed midnight UTC
                if (
                    self._state.last_reset_date
                    and now.date() > self._state.last_reset_date.date()
                ):
                    old_loss = self._state.daily_loss
                    self._state.daily_loss = 0.0
                    self._state.last_reset_date = now
                    self._state.consecutive_losses = 0

                    logger.info(
                        f"🔄 Daily loss reset at midnight UTC (was ${old_loss:.2f})"
                    )

                    # Save state after reset
                    await self._save_state()
        except Exception as e:
            logger.exception(f"Error checking daily loss reset: {e}")

    async def check_trade_allowed(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if trade is allowed (circuit breaker not active).

        Args:
            trade_id: Unique trade identifier

        Returns:
            None if trade is allowed, otherwise dict with skip reason
        """
        try:
            async with self._state_lock:
                # Check and reset daily loss if needed
                await self._check_and_reset_daily_loss()

                if not self._state.active:
                    return None

                # Circuit breaker is active - calculate remaining time
                remaining_time = self._get_remaining_time_seconds()
                remaining_minutes = remaining_time / 60.0

                logger.warning(
                    f"🚫 Circuit breaker active: {self._state.reason}. "
                    f"Remaining time: {remaining_minutes:.1f} minutes. Skipping trade {trade_id}."
                )

                return {
                    "status": "skipped",
                    "reason": f"Circuit breaker: {self._state.reason}",
                    "trade_id": trade_id,
                    "remaining_minutes": remaining_minutes,
                    "recovery_eta": self._calculate_recovery_eta(),
                }
        except Exception as e:
            # Graceful degradation: if circuit breaker check fails, allow trade
            # but log the error
            logger.exception(
                f"Error checking circuit breaker for trade {trade_id}: {e}"
            )
            return None

    async def record_loss(self, loss_amount: float) -> None:
        """
        Record a loss and update circuit breaker state.

        Args:
            loss_amount: Amount of loss (should be positive)
        """
        try:
            async with self._state_lock:
                # Check and reset daily loss if needed
                await self._check_and_reset_daily_loss()

                # Record loss
                self._state.daily_loss += abs(loss_amount)
                self._state.consecutive_losses += 1

                logger.info(
                    f"📉 Loss recorded: ${abs(loss_amount):.2f}. "
                    f"Daily loss: ${self._state.daily_loss:.2f}, "
                    f"Consecutive losses: {self._state.consecutive_losses}"
                )

                # Check if circuit breaker should activate
                await self._check_activation_conditions()

                # Save state
                await self._save_state()
        except Exception as e:
            logger.exception(f"Error recording loss: {e}")

    async def record_profit(self, profit_amount: float) -> None:
        """
        Record a profit and reset consecutive losses.

        Args:
            profit_amount: Amount of profit (should be positive)
        """
        try:
            async with self._state_lock:
                # Reset consecutive losses on profit
                if self._state.consecutive_losses > 0:
                    logger.info(
                        f"✅ Profit recorded: ${profit_amount:.2f}. "
                        f"Resetting consecutive losses (was {self._state.consecutive_losses})"
                    )
                    self._state.consecutive_losses = 0

                # Save state
                await self._save_state()
        except Exception as e:
            logger.exception(f"Error recording profit: {e}")

    async def record_trade_result(
        self, success: bool, trade_id: Optional[str] = None
    ) -> None:
        """
        Record trade result (success or failure).

        Args:
            success: True if trade was successful, False otherwise
            trade_id: Optional trade identifier for logging
        """
        try:
            async with self._state_lock:
                # Check and reset daily loss if needed
                await self._check_and_reset_daily_loss()

                self._state.total_trades += 1
                if not success:
                    self._state.failed_trades += 1

                # Check if circuit breaker should activate
                await self._check_activation_conditions()

                # Save state
                await self._save_state()
        except Exception as e:
            logger.exception(f"Error recording trade result: {e}")

    async def _check_activation_conditions(self) -> None:
        """Check if circuit breaker should be activated"""
        try:
            # Don't activate if already active
            if self._state.active:
                return

            # Condition 1: Daily loss limit exceeded
            if self._state.daily_loss >= self.max_daily_loss:
                await self._activate(
                    f"Daily loss limit reached (${self._state.daily_loss:.2f} / ${self.max_daily_loss:.2f})"
                )
                return

            # Condition 2: 5 consecutive losses
            if self._state.consecutive_losses >= self.CONSECUTIVE_LOSS_THRESHOLD:
                await self._activate(
                    f"{self._state.consecutive_losses} consecutive losses detected"
                )
                return

            # Condition 3: High failure rate (50%+ with at least 10 trades)
            if (
                self._state.total_trades >= self.MIN_TRADES_FOR_FAILURE_RATE
                and self._state.failed_trades > 0
            ):
                failure_rate = self._state.failed_trades / self._state.total_trades
                if failure_rate >= self.FAILURE_RATE_THRESHOLD:
                    await self._activate(
                        f"High failure rate ({failure_rate:.1%} - "
                        f"{self._state.failed_trades}/{self._state.total_trades} trades)"
                    )
                    return

            # Check if circuit breaker should auto-reset (cooldown expired)
            if self._state.active and self._state.activation_time:
                elapsed = time.time() - self._state.activation_time
                if elapsed > self.cooldown_seconds:
                    await self._reset("Cooldown period expired")
        except Exception as e:
            logger.exception(f"Error checking activation conditions: {e}")

    async def _activate(self, reason: str) -> None:
        """
        Activate circuit breaker (internal method, already holding lock).

        Args:
            reason: Reason for activation
        """
        # Double-check we're not already active (defensive programming)
        if self._state.active:
            return

        self._state.active = True
        self._state.reason = reason
        self._state.activation_time = time.time()

        logger.critical(f"🚨 CIRCUIT BREAKER ACTIVATED: {reason}")
        logger.critical(f"   Daily Loss: ${self._state.daily_loss:.2f}")
        logger.critical(
            f"   Success Rate: {self._state.total_trades - self._state.failed_trades}/{self._state.total_trades} trades"
        )
        logger.critical(f"   Consecutive Losses: {self._state.consecutive_losses}")

        # Send alert with recovery ETA
        if self.alert_on_activation:
            recovery_eta = self._calculate_recovery_eta()
            try:
                await send_telegram_alert(
                    f"🚨 **CIRCUIT BREAKER ACTIVATED**\n"
                    f"**Reason:** {reason}\n"
                    f"**Wallet:** `{self.wallet_address[-6:]}`\n"
                    f"**Daily Loss:** ${self._state.daily_loss:.2f}\n"
                    f"**Success Rate:** {self._state.total_trades - self._state.failed_trades}/{self._state.total_trades}\n"
                    f"**Consecutive Losses:** {self._state.consecutive_losses}\n"
                    f"**Cooldown:** {self.cooldown_seconds // 60} minutes\n"
                    f"**Recovery ETA:** {recovery_eta}"
                )
            except Exception as e:
                logger.error(f"Error sending circuit breaker alert: {e}")

        # Save state
        await self._save_state()

    async def reset(self, reason: Optional[str] = None) -> None:
        """
        Manually reset circuit breaker.

        Args:
            reason: Optional reason for reset
        """
        async with self._state_lock:
            await self._reset(reason or "Manual reset")

    async def _reset(self, reason: str) -> None:
        """
        Reset circuit breaker (internal method, already holding lock).

        Args:
            reason: Reason for reset
        """
        if not self._state.active:
            return

        old_reason = self._state.reason
        self._state.active = False
        self._state.reason = ""
        self._state.activation_time = None

        logger.info(
            f"✅ Circuit breaker reset. Previous reason: {old_reason}. New reason: {reason}"
        )

        # Save state
        await self._save_state()

    def _get_remaining_time_seconds(self) -> float:
        """Get remaining cooldown time in seconds"""
        if not self._state.active or not self._state.activation_time:
            return 0.0

        elapsed = time.time() - self._state.activation_time
        remaining = max(0, self.cooldown_seconds - elapsed)
        return remaining

    def _calculate_recovery_eta(self) -> str:
        """Calculate and format recovery ETA"""
        if not self._state.active or not self._state.activation_time:
            return "N/A"

        remaining_seconds = self._get_remaining_time_seconds()
        if remaining_seconds <= 0:
            return "Available now"

        remaining_minutes = remaining_seconds / 60.0
        if remaining_minutes < 60:
            return f"{int(remaining_minutes)} minutes"
        else:
            hours = int(remaining_minutes // 60)
            minutes = int(remaining_minutes % 60)
            return f"{hours}h {minutes}m"

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state (read-only)"""
        return {
            "active": self._state.active,
            "reason": self._state.reason,
            "daily_loss": self._state.daily_loss,
            "max_daily_loss": self.max_daily_loss,
            "consecutive_losses": self._state.consecutive_losses,
            "failed_trades": self._state.failed_trades,
            "total_trades": self._state.total_trades,
            "remaining_minutes": self._get_remaining_time_seconds() / 60.0,
            "recovery_eta": self._calculate_recovery_eta(),
        }

    async def periodic_check(self) -> None:
        """Periodic check for auto-reset and daily loss reset"""
        try:
            async with self._state_lock:
                # Check daily loss reset
                await self._check_and_reset_daily_loss()

                # Check auto-reset
                if self._state.active and self._state.activation_time:
                    elapsed = time.time() - self._state.activation_time
                    if elapsed > self.cooldown_seconds:
                        await self._reset("Cooldown period expired")
        except Exception as e:
            logger.exception(f"Error in periodic circuit breaker check: {e}")

    async def check_mcp_test_coverage(self, coverage: float, threshold: float) -> bool:
        """
        Check MCP test coverage and trip circuit breaker if needed.

        This is called by MCP testing server to verify test coverage.

        Args:
            coverage: Current test coverage (0.0 to 1.0)
            threshold: Minimum coverage threshold (0.0 to 1.0)

        Returns:
            True if coverage is acceptable, False if circuit breaker should trip
        """
        if coverage < threshold:
            logger.warning(
                f"⚠️ MCP test coverage {coverage:.1%} below threshold {threshold:.1%}"
            )

            # Trip circuit breaker if coverage is critically low
            if coverage < threshold * 0.8:  # More than 20% below threshold
                await self._activate(
                    f"MCP test coverage critically low: {coverage:.1%} < {threshold:.1%}"
                )
                return False

        return True

    async def check_mcp_resource_usage(
        self, cpu_percent: float, memory_mb: float, limit_mb: float
    ) -> bool:
        """
        Check MCP resource usage and trip circuit breaker if needed.

        This is called by MCP monitoring server to verify resource limits.

        Args:
            cpu_percent: Current CPU usage percentage
            memory_mb: Current memory usage in MB
            limit_mb: Memory limit threshold in MB

        Returns:
            True if resources are acceptable, False if circuit breaker should trip
        """
        # Check memory usage
        memory_critical = memory_mb >= limit_mb
        memory_warning = memory_mb >= limit_mb * 0.8

        if memory_critical:
            logger.error(
                f"🔴 MCP memory critical: {memory_mb:.1f}MB >= limit {limit_mb}MB"
            )

            # Trip circuit breaker
            await self._activate(f"MCP memory exceeded limit: {memory_mb:.1f}MB")
            return False
        elif memory_warning:
            logger.warning(f"⚠️ MCP memory warning: {memory_mb:.1f}MB")

        # Check CPU usage (should be minimal)
        if cpu_percent > 2.0:  # More than 2% is concerning
            logger.warning(f"⚠️ MCP CPU usage high: {cpu_percent:.1f}%")

            # Trip circuit breaker if CPU is very high
            if cpu_percent > 5.0:
                logger.error(f"🔴 MCP CPU critically high: {cpu_percent:.1f}%")
                await self._activate(f"MCP CPU exceeded limit: {cpu_percent:.1f}%")
                return False

        return True

    def get_mcp_integration_state(self) -> Dict[str, Any]:
        """
        Get MCP integration state for monitoring.

        Returns:
            Dictionary with MCP integration status
        """
        return {
            "enabled": hasattr(self, "_mcp_integrated"),
            "circuit_breaker_protected": getattr(self, "_mcp_protected", False),
            "test_coverage_monitored": getattr(self, "_test_coverage_monitored", False),
            "resource_usage_monitored": getattr(
                self, "_resource_usage_monitored", False
            ),
            "last_mcp_check": getattr(self, "_last_mcp_check", None),
        }

    async def enable_mcp_integration(
        self, test_coverage_threshold: float = 0.85
    ) -> None:
        """
        Enable MCP integration with circuit breaker protection.

        Args:
            test_coverage_threshold: Minimum test coverage threshold (default 85%)
        """
        async with self._state_lock:
            self._mcp_integrated = True
            self._mcp_protected = True
            self._test_coverage_monitored = True
            self._test_coverage_threshold = test_coverage_threshold
            self._resource_usage_monitored = True

        logger.info(
            f"✅ MCP integration enabled with circuit breaker protection"
            f"(test coverage threshold: {test_coverage_threshold:.0%})"
        )

    async def disable_mcp_integration(self) -> None:
        """Disable MCP integration with circuit breaker protection."""
        async with self._state_lock:
            self._mcp_integrated = False
            self._mcp_protected = False
            self._test_coverage_monitored = False
            self._resource_usage_monitored = False

        logger.info("ℹ️ MCP integration disabled")
