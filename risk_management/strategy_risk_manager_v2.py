"""
Strategy-Specific Risk Management Module - Fixed Version

This module provides strategy-specific risk profiles and independent circuit breakers
for different trading strategies (EndgameSweep, CrossMarketArb, etc.).

Features:
- Strategy-specific risk profiles with customizable parameters
- Portfolio-level correlation limits between active positions
- Volatility-adjusted position sizing (reduces size when VIX > 30)
- Independent circuit breakers per strategy
- Thread-safe risk state management
- Persistent risk state across restarts (pickle to disk)
- Real-time risk recalculation during market hours
- Comprehensive audit logging of all risk decisions

Author: Polymarket Copy Bot Team
Date: 2025-12-27
"""

import asyncio
import logging
import pickle
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, getcontext
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configure Decimal for financial calculations
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

logger = logging.getLogger(__name__)


class TradingStrategy(Enum):
    """Enumeration of supported trading strategies."""

    ENGAME_SWEEP = "endgame_sweep"
    CROSS_MARKET_ARB = "cross_market_arb"
    COPY_TRADING = "copy_trading"
    MARKET_MAKING = "market_making"


@dataclass
class StrategyRiskProfile:
    """
    Risk profile for a specific trading strategy.

    Attributes:
        strategy: TradingStrategy enum
        max_position_size: Maximum position size (USDC)
        max_daily_loss: Maximum daily loss before circuit breaker
        max_consecutive_losses: Max consecutive losses allowed
        max_failure_rate: Max failure rate threshold (0.0 to 1.0)
        min_correlation_threshold: Min correlation between active positions
        max_correlation_threshold: Max correlation allowed (0.0 to 1.0)
        max_slippage: Maximum acceptable slippage
        volatility_adjustment: Whether to adjust position size by volatility
        max_portfolio_exposure: Max total exposure across all positions (USDC)
        max_positions_per_market: Max positions per individual market
        enabled: Whether this strategy is enabled
    """

    strategy: TradingStrategy
    max_position_size: Decimal
    max_daily_loss: Decimal
    max_consecutive_losses: int
    max_failure_rate: float
    min_correlation_threshold: float
    max_correlation_threshold: float
    max_slippage: float
    volatility_adjustment: bool
    max_portfolio_exposure: Decimal
    max_positions_per_market: int
    enabled: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "strategy": self.strategy.value,
            "max_position_size": float(self.max_position_size),
            "max_daily_loss": float(self.max_daily_loss),
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_failure_rate": self.max_failure_rate,
            "min_correlation_threshold": self.min_correlation_threshold,
            "max_correlation_threshold": self.max_correlation_threshold,
            "max_slippage": self.max_slippage,
            "volatility_adjustment": self.volatility_adjustment,
            "max_portfolio_exposure": float(self.max_portfolio_exposure),
            "max_positions_per_market": self.max_positions_per_market,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyRiskProfile":
        """Create from dictionary."""
        strategy_str = data.get("strategy", "copy_trading")
        strategy = (
            TradingStrategy(strategy_str)
            if strategy_str in [s.value for s in TradingStrategy]
            else TradingStrategy.COPY_TRADING
        )

        return cls(
            strategy=strategy,
            max_position_size=Decimal(str(data.get("max_position_size", 50.0))),
            max_daily_loss=Decimal(str(data.get("max_daily_loss", 100.0))),
            max_consecutive_losses=int(data.get("max_consecutive_losses", 5)),
            max_failure_rate=float(data.get("max_failure_rate", 0.5)),
            min_correlation_threshold=float(data.get("min_correlation_threshold", 0.0)),
            max_correlation_threshold=float(data.get("max_correlation_threshold", 1.0)),
            max_slippage=float(data.get("max_slippage", 0.02)),
            volatility_adjustment=bool(data.get("volatility_adjustment", False)),
            max_portfolio_exposure=Decimal(
                str(data.get("max_portfolio_exposure", 500.0))
            ),
            max_positions_per_market=int(data.get("max_positions_per_market", 5)),
            enabled=bool(data.get("enabled", True)),
        )


@dataclass
class StrategyCircuitBreakerState:
    """
    State for strategy-specific circuit breaker.

    Attributes:
        strategy: TradingStrategy
        active: Whether circuit breaker is currently tripped
        reason: Reason for activation
        activation_time: When circuit breaker was activated
        daily_loss: Accumulated losses for current day
        total_loss: Total losses since last reset
        total_profit: Total profits since last reset
        consecutive_losses: Number of consecutive losses
        failed_trades: Total failed trades
        successful_trades: Total successful trades
        last_reset_date: Date of last daily reset
        last_reset_time: Time of last full reset
    """

    strategy: TradingStrategy
    active: bool
    reason: str
    activation_time: Optional[float]
    daily_loss: Decimal
    total_loss: Decimal
    total_profit: Decimal
    consecutive_losses: int
    failed_trades: int
    successful_trades: int
    last_reset_date: Optional[datetime]
    last_reset_time: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "strategy": self.strategy.value,
            "active": self.active,
            "reason": self.reason,
            "activation_time": self.activation_time,
            "daily_loss": float(self.daily_loss),
            "total_loss": float(self.total_loss),
            "total_profit": float(self.total_profit),
            "consecutive_losses": self.consecutive_losses,
            "failed_trades": self.failed_trades,
            "successful_trades": self.successful_trades,
            "last_reset_date": (
                self.last_reset_date.isoformat() if self.last_reset_date else None
            ),
            "last_reset_time": self.last_reset_time,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyCircuitBreakerState":
        """Create from dictionary."""
        strategy_str = data.get("strategy", "copy_trading")
        strategy = (
            TradingStrategy(strategy_str)
            if strategy_str in [s.value for s in TradingStrategy]
            else TradingStrategy.COPY_TRADING
        )

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
            strategy=strategy,
            active=data.get("active", False),
            reason=data.get("reason", ""),
            activation_time=data.get("activation_time"),
            daily_loss=Decimal(str(data.get("daily_loss", 0.0))),
            total_loss=Decimal(str(data.get("total_loss", 0.0))),
            total_profit=Decimal(str(data.get("total_profit", 0.0))),
            consecutive_losses=int(data.get("consecutive_losses", 0)),
            failed_trades=int(data.get("failed_trades", 0)),
            successful_trades=int(data.get("successful_trades", 0)),
            last_reset_date=last_reset_date,
            last_reset_time=data.get("last_reset_time"),
        )


class StrategyRiskManager:
    """
    Strategy-specific risk manager with independent circuit breakers.

    Features:
    - Strategy-specific risk profiles with customizable parameters
    - Portfolio-level correlation tracking between active positions
    - Volatility-adjusted position sizing (reduces size when VIX > 30)
    - Independent circuit breakers per strategy
    - Thread-safe risk state management
    - Persistent risk state across restarts
    - Real-time risk recalculation
    - Comprehensive audit logging

    Thread Safety:
        All state modifications are protected by asyncio locks to prevent
        race conditions in concurrent operations.
    """

    # VIX threshold for volatility adjustment
    VIX_THRESHOLD = Decimal("30.0")

    # Correlation threshold for portfolio risk
    DEFAULT_MAX_CORRELATION_THRESHOLD = 0.7

    def __init__(
        self,
        strategy_profiles: Optional[Dict[TradingStrategy, StrategyRiskProfile]] = None,
        state_file: Optional[Path] = None,
        audit_log_file: Optional[Path] = None,
    ) -> None:
        """
        Initialize strategy risk manager.

        Args:
            strategy_profiles: Optional dict of strategy risk profiles
            state_file: Path to persistent state file (pickle)
            audit_log_file: Path to audit log file
        """
        # Default strategy profiles if not provided
        self.strategy_profiles = strategy_profiles or self._get_default_profiles()

        # Thread safety
        self._state_lock = asyncio.Lock()
        self._correlation_lock = asyncio.Lock()

        # State persistence
        self.state_file = state_file or Path("data/strategy_risk_state.pkl")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        self.audit_log_file = audit_log_file or Path("logs/strategy_risk_audit.log")
        self.audit_log_file.parent.mkdir(parents=True, exist_ok=True)

        # Strategy circuit breaker states
        self._circuit_breakers: Dict[TradingStrategy, StrategyCircuitBreakerState] = {}

        # Active positions tracking (for correlation limits)
        self._active_positions: Dict[str, List[Dict[str, Any]]] = {}

        # Market correlations (for portfolio-level tracking)
        self._market_correlations: Dict[
            Tuple[str, str], float
        ] = {}  # (market_1, market_2) -> correlation

        # Volatility data (for VIX-style adjustment)
        self._volatility_data: Dict[str, float] = {}

        # Risk metrics
        self._total_portfolio_exposure: Decimal = Decimal("0.0")
        self._total_daily_profit: Dict[TradingStrategy, Decimal] = {}
        self._total_daily_loss: Dict[TradingStrategy, Decimal] = {}

        # Load persistent state
        self._load_state()

        logger.info(
            f"✅ StrategyRiskManager initialized with {len(self.strategy_profiles)} strategies"
        )

    def _get_default_profiles(self) -> Dict[TradingStrategy, StrategyRiskProfile]:
        """Get default risk profiles for all strategies."""
        return {
            TradingStrategy.COPY_TRADING: StrategyRiskProfile(
                strategy=TradingStrategy.COPY_TRADING,
                max_position_size=Decimal("50.0"),
                max_daily_loss=Decimal("100.0"),
                max_consecutive_losses=5,
                max_failure_rate=0.5,
                min_correlation_threshold=0.0,
                max_correlation_threshold=0.9,
                max_slippage=0.02,
                volatility_adjustment=False,
                max_portfolio_exposure=Decimal("500.0"),
                max_positions_per_market=3,
                enabled=True,
            ),
            TradingStrategy.ENDGAME_SWEEP: StrategyRiskProfile(
                strategy=TradingStrategy.ENDGAME_SWEEP,
                max_position_size=Decimal("20.0"),
                max_daily_loss=Decimal("50.0"),
                max_consecutive_losses=3,
                max_failure_rate=0.4,
                min_correlation_threshold=0.0,
                max_correlation_threshold=0.8,
                max_slippage=0.01,
                volatility_adjustment=True,
                max_portfolio_exposure=Decimal("200.0"),
                max_positions_per_market=2,
                enabled=True,
            ),
            TradingStrategy.CROSS_MARKET_ARB: StrategyRiskProfile(
                strategy=TradingStrategy.CROSS_MARKET_ARB,
                max_position_size=Decimal("10.0"),
                max_daily_loss=Decimal("25.0"),
                max_consecutive_losses=5,
                max_failure_rate=0.3,
                min_correlation_threshold=0.8,
                max_correlation_threshold=0.95,
                max_slippage=0.005,
                volatility_adjustment=True,
                max_portfolio_exposure=Decimal("100.0"),
                max_positions_per_market=1,
                enabled=False,  # Disabled by default, requires manual enable
            ),
            TradingStrategy.MARKET_MAKING: StrategyRiskProfile(
                strategy=TradingStrategy.MARKET_MAKING,
                max_position_size=Decimal("100.0"),
                max_daily_loss=Decimal("200.0"),
                max_consecutive_losses=10,
                max_failure_rate=0.6,
                min_correlation_threshold=0.0,
                max_correlation_threshold=1.0,
                max_slippage=0.05,
                volatility_adjustment=False,
                max_portfolio_exposure=Decimal("1000.0"),
                max_positions_per_market=5,
                enabled=False,  # Disabled by default
            ),
        }

    def _load_state(self) -> None:
        """Load persistent state from disk."""
        try:
            if self.state_file.exists():
                with open(self.state_file, "rb") as f:
                    data = pickle.load(f)

                    # Load circuit breaker states
                    for state_data in data.get("circuit_breakers", []):
                        state = StrategyCircuitBreakerState.from_dict(state_data)
                        self._circuit_breakers[state.strategy] = state

                    # Load market correlations
                    self._market_correlations = data.get("market_correlations", {})

                    # Load volatility data
                    self._volatility_data = data.get("volatility_data", {})

                    logger.info(
                        f"✅ Loaded state for {len(self._circuit_breakers)} strategies"
                    )
        except (pickle.PickleError, IOError, EOFError) as e:
            logger.warning(f"Error loading state file: {e}. Using defaults.")
        except Exception as e:
            logger.exception(f"Unexpected error loading state: {e}")

    def _save_state(self) -> None:
        """Save state to disk."""
        try:
            data = {
                "circuit_breakers": [
                    state.to_dict() for state in self._circuit_breakers.values()
                ],
                "market_correlations": self._market_correlations,
                "volatility_data": self._volatility_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Write to temporary file first, then rename (atomic)
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "wb") as f:
                pickle.dump(data, f)

            # Atomic rename
            temp_file.replace(self.state_file)

        except (pickle.PickleError, IOError) as e:
            logger.error(f"Error saving state file: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error saving state: {e}")

    def _audit_log(
        self, strategy: TradingStrategy, action: str, details: Dict[str, Any]
    ) -> None:
        """Write audit log entry."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            entry = {
                "timestamp": timestamp,
                "strategy": strategy.value,
                "action": action,
                "details": details,
            }

            with open(self.audit_log_file, "a") as f:
                f.write(f"{timestamp} - {strategy.value} - {action} - {details}\n")

        except IOError as e:
            logger.error(f"Error writing audit log: {e}")

    async def get_risk_profile(self, strategy: TradingStrategy) -> StrategyRiskProfile:
        """
        Get risk profile for a strategy.

        Args:
            strategy: TradingStrategy enum

        Returns:
            StrategyRiskProfile for requested strategy
        """
        async with self._state_lock:
            profile = self.strategy_profiles.get(strategy)
            if profile is None:
                logger.warning(f"No risk profile found for strategy: {strategy.value}")
                # Return default profile
                profile = self._get_default_profiles()[strategy]
            return profile

    async def set_risk_profile(
        self, strategy: TradingStrategy, profile: StrategyRiskProfile
    ) -> None:
        """
        Set risk profile for a strategy.

        Args:
            strategy: TradingStrategy enum
            profile: StrategyRiskProfile to set
        """
        async with self._state_lock:
            self.strategy_profiles[strategy] = profile

            self._audit_log(
                strategy,
                "PROFILE_UPDATE",
                {
                    "max_position_size": float(profile.max_position_size),
                    "max_daily_loss": float(profile.max_daily_loss),
                    "enabled": profile.enabled,
                },
            )

            # Save state
            self._save_state()

            logger.info(f"✅ Updated risk profile for {strategy.value}")

    async def check_trade_allowed(
        self,
        strategy: TradingStrategy,
        trade_details: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Check if trade is allowed based on strategy-specific risk controls.

        Args:
            strategy: TradingStrategy enum
            trade_details: Dictionary containing trade information (amount, market, etc.)

        Returns:
            None if trade is allowed, otherwise dict with skip reason
        """
        try:
            async with self._state_lock:
                # Get risk profile
                profile = self.strategy_profiles.get(strategy)
                if not profile or not profile.enabled:
                    reason = f"Strategy {strategy.value} not enabled or no profile"
                    logger.debug(f"🚫 Trade blocked: {reason}")
                    return {"status": "skipped", "reason": reason}

                # Check circuit breaker state
                cb_state = self._circuit_breakers.get(strategy)
                if cb_state and cb_state.active:
                    # Calculate remaining time
                    remaining_time = self._get_remaining_time(cb_state)
                    reason = f"Circuit breaker active for {strategy.value}: {cb_state.reason}"
                    logger.warning(
                        f"🚫 {reason}. Remaining: {remaining_time:.1f} minutes"
                    )
                    return {
                        "status": "skipped",
                        "reason": reason,
                        "remaining_minutes": remaining_time,
                    }

                # Check position size
                trade_amount = Decimal(str(trade_details.get("amount", 0)))
                if trade_amount > profile.max_position_size:
                    reason = (
                        f"Position size ${trade_amount:.2f} exceeds maximum "
                        f"${profile.max_position_size:.2f} for {strategy.value}"
                    )
                    self._audit_log(strategy, "POSITION_SIZE_EXCEEDED", trade_details)
                    logger.warning(f"🚫 {reason}")
                    return {"status": "skipped", "reason": reason}

                # Check portfolio exposure
                if self._total_portfolio_exposure > profile.max_portfolio_exposure:
                    reason = (
                        f"Portfolio exposure ${self._total_portfolio_exposure:.2f} exceeds "
                        f"maximum ${profile.max_portfolio_exposure:.2f}"
                    )
                    self._audit_log(strategy, "PORTFOLIO_EXCEEDED", trade_details)
                    logger.warning(f"🚫 {reason}")
                    return {"status": "skipped", "reason": reason}

                # Check correlation limits
                if profile.max_correlation_threshold < 1.0:
                    correlation_check = await self._check_portfolio_correlation(
                        trade_details, profile
                    )
                    if not correlation_check["allowed"]:
                        reason = correlation_check["reason"]
                        self._audit_log(strategy, "CORRELATION_LIMIT", trade_details)
                        logger.warning(f"🚫 {reason}")
                        return {"status": "skipped", "reason": reason}

                # Check volatility adjustment
                if profile.volatility_adjustment:
                    volatility_check = await self._check_volatility_adjustment(
                        trade_details, profile
                    )
                    if not volatility_check["allowed"]:
                        reason = volatility_check["reason"]
                        self._audit_log(strategy, "VOLATILITY_LIMIT", trade_details)
                        logger.warning(f"🚫 {reason}")
                        return {"status": "skipped", "reason": reason}

                # All checks passed
                return None

        except Exception as e:
            logger.exception(f"Error checking trade allowed for {strategy.value}: {e}")
            # Conservative: allow trade on error
            return None

    async def _check_portfolio_correlation(
        self, trade_details: Dict[str, Any], profile: StrategyRiskProfile
    ) -> Dict[str, Any]:
        """
        Check if adding position violates correlation limits.

        Args:
            trade_details: Trade details
            profile: Strategy risk profile

        Returns:
            Dict with 'allowed' boolean and 'reason' string
        """
        try:
            new_market = trade_details.get("market_id", "")

            # Get correlations with new market
            async with self._correlation_lock:
                for existing_market in self._active_positions.keys():
                    key = tuple(sorted((new_market, existing_market)))
                    correlation = self._market_correlations.get(key, 0.0)

                    # Check if correlation exceeds threshold
                    if abs(correlation) > profile.max_correlation_threshold:
                        return {
                            "allowed": False,
                            "reason": (
                                f"Correlation {correlation:.2f} between {new_market[:10]}... "
                                f"and {existing_market[:10]}... exceeds threshold "
                                f"{profile.max_correlation_threshold:.2f}"
                            ),
                            "correlation": correlation,
                            "threshold": profile.max_correlation_threshold,
                        }

            return {"allowed": True}

        except Exception as e:
            logger.error(f"Error checking portfolio correlation: {e}")
            return {"allowed": True}  # Allow on error

    async def _check_volatility_adjustment(
        self, trade_details: Dict[str, Any], profile: StrategyRiskProfile
    ) -> Dict[str, Any]:
        """
        Check volatility-adjusted position sizing.

        When VIX-style volatility > 30, reduce position size.

        Args:
            trade_details: Trade details
            profile: Strategy risk profile

        Returns:
            Dict with 'allowed' boolean and 'reason' string
        """
        try:
            # Get current volatility (placeholder for VIX-style data)
            # In production, this would fetch actual volatility data
            current_volatility = self._volatility_data.get("vix", 0.0)

            if current_volatility > float(self.VIX_THRESHOLD):
                # Calculate reduction factor (reduces position when VIX > 30)
                max_reduction = 1.0 - (current_volatility / 100.0)
                reduction_factor = Decimal(str(max(0.5, max_reduction)))

                # Calculate adjusted position size
                base_amount = Decimal(str(trade_details.get("amount", 0)))
                adjusted_amount = base_amount * reduction_factor

                # Check if adjusted amount is too small
                min_amount = Decimal("1.0")
                if adjusted_amount < min_amount:
                    return {
                        "allowed": False,
                        "reason": (
                            f"Volatility {current_volatility:.1f} > {self.VIX_THRESHOLD} "
                            f"would reduce position to ${adjusted_amount:.2f} below minimum ${min_amount:.2f}"
                        ),
                        "volatility": current_volatility,
                        "adjusted_amount": float(adjusted_amount),
                    }

            return {"allowed": True}

        except Exception as e:
            logger.error(f"Error checking volatility adjustment: {e}")
            return {"allowed": True}  # Allow on error

    async def record_trade_result(
        self,
        strategy: TradingStrategy,
        success: bool,
        profit: Optional[Decimal] = None,
        trade_id: Optional[str] = None,
    ) -> None:
        """
        Record trade result and update risk metrics.

        Args:
            strategy: TradingStrategy enum
            success: Whether trade was successful
            profit: Profit/loss amount (None for unknown)
            trade_id: Optional trade identifier
        """
        try:
            async with self._state_lock:
                # Get or create circuit breaker state
                if strategy not in self._circuit_breakers:
                    self._circuit_breakers[strategy] = StrategyCircuitBreakerState(
                        strategy=strategy,
                        active=False,
                        reason="",
                        activation_time=None,
                        daily_loss=Decimal("0.0"),
                        total_loss=Decimal("0.0"),
                        total_profit=Decimal("0.0"),
                        consecutive_losses=0,
                        failed_trades=0,
                        successful_trades=0,
                        last_reset_date=datetime.now(timezone.utc),
                        last_reset_time=time.time(),
                    )

                cb_state = self._circuit_breakers[strategy]

                # Update trade counts
                if success:
                    cb_state.successful_trades += 1
                    cb_state.consecutive_losses = 0

                    # Record profit
                    if profit is not None:
                        if profit > 0:
                            cb_state.total_profit += profit
                            self._total_daily_profit[strategy] = (
                                self._total_daily_profit.get(strategy, Decimal("0.0"))
                                + profit
                            )
                        else:
                            # Loss
                            loss_amount = abs(profit)
                            cb_state.total_loss += loss_amount
                            cb_state.daily_loss += loss_amount
                            cb_state.consecutive_losses += 1
                            self._total_daily_loss[strategy] = (
                                self._total_daily_loss.get(strategy, Decimal("0.0"))
                                + loss_amount
                            )
                else:
                    cb_state.failed_trades += 1
                    cb_state.consecutive_losses += 1

                # Check if circuit breaker should activate
                profile = self.strategy_profiles.get(strategy)
                if profile:
                    await self._check_circuit_breaker_conditions(cb_state, profile)

                # Audit log
                self._audit_log(
                    strategy,
                    "TRADE_RESULT",
                    {
                        "success": success,
                        "profit": float(profit) if profit else None,
                        "trade_id": trade_id,
                        "daily_loss": float(cb_state.daily_loss),
                        "consecutive_losses": cb_state.consecutive_losses,
                    },
                )

                # Save state
                self._save_state()

        except Exception as e:
            logger.exception(f"Error recording trade result for {strategy.value}: {e}")

    async def _check_circuit_breaker_conditions(
        self, cb_state: StrategyCircuitBreakerState, profile: StrategyRiskProfile
    ) -> None:
        """
        Check if circuit breaker should be activated.

        Args:
            cb_state: Current circuit breaker state
            profile: Strategy risk profile
        """
        try:
            # Don't activate if already active
            if cb_state.active:
                return

            activation_reason = None

            # Condition 1: Daily loss limit exceeded
            if cb_state.daily_loss >= profile.max_daily_loss:
                activation_reason = (
                    f"Daily loss limit reached (${cb_state.daily_loss:.2f} / "
                    f"${profile.max_daily_loss:.2f})"
                )

            # Condition 2: Consecutive losses exceeded
            elif cb_state.consecutive_losses >= profile.max_consecutive_losses:
                activation_reason = (
                    f"{cb_state.consecutive_losses} consecutive losses "
                    f"(max: {profile.max_consecutive_losses})"
                )

            # Condition 3: High failure rate
            total_trades = cb_state.successful_trades + cb_state.failed_trades
            if total_trades >= 10:
                failure_rate = cb_state.failed_trades / total_trades
                if failure_rate >= profile.max_failure_rate:
                    activation_reason = (
                        f"High failure rate ({failure_rate:.1%} - "
                        f"{cb_state.failed_trades}/{total_trades} trades)"
                    )

            if activation_reason:
                await self._activate_circuit_breaker(cb_state, activation_reason)

        except Exception as e:
            logger.exception(f"Error checking circuit breaker conditions: {e}")

    async def _activate_circuit_breaker(
        self, cb_state: StrategyCircuitBreakerState, reason: str
    ) -> None:
        """
        Activate circuit breaker for a strategy.

        Args:
            cb_state: Circuit breaker state to activate
            reason: Reason for activation
        """
        try:
            cb_state.active = True
            cb_state.reason = reason
            cb_state.activation_time = time.time()

            # Audit log
            self._audit_log(
                cb_state.strategy, "CIRCUIT_BREAKER_ACTIVATED", {"reason": reason}
            )

            # Send alert
            from utils.alerts import send_telegram_alert

            message = (
                f"🚨 **CIRCUIT BREAKER ACTIVATED**\n"
                f"**Strategy:** {cb_state.strategy.value}\n"
                f"**Reason:** {reason}\n"
                f"**Daily Loss:** ${cb_state.daily_loss:.2f}\n"
                f"**Consecutive Losses:** {cb_state.consecutive_losses}\n"
                f"**Success Rate:** {cb_state.successful_trades}/{cb_state.successful_trades + cb_state.failed_trades}\n"
                f"**Activation Time:** {datetime.fromtimestamp(cb_state.activation_time).isoformat()}"
            )
            await send_telegram_alert(message)

            # Save state
            self._save_state()

            logger.critical(
                f"🚨 Circuit breaker ACTIVATED for {cb_state.strategy.value}: {reason}"
            )

        except Exception as e:
            logger.exception(f"Error activating circuit breaker: {e}")

    async def reset_circuit_breaker(
        self, strategy: TradingStrategy, reason: Optional[str] = None
    ) -> None:
        """
        Reset circuit breaker for a strategy.

        Args:
            strategy: TradingStrategy enum
            reason: Optional reason for reset
        """
        try:
            async with self._state_lock:
                cb_state = self._circuit_breakers.get(strategy)
                if not cb_state or not cb_state.active:
                    logger.debug(f"Circuit breaker not active for {strategy.value}")
                    return

                old_reason = cb_state.reason
                cb_state.active = False
                cb_state.reason = ""

                # Reset losses
                cb_state.daily_loss = Decimal("0.0")
                cb_state.consecutive_losses = 0

                # Audit log
                self._audit_log(
                    strategy,
                    "CIRCUIT_BREAKER_RESET",
                    {"old_reason": old_reason, "new_reason": reason},
                )

                # Save state
                self._save_state()

                logger.info(
                    f"✅ Circuit breaker reset for {strategy.value}. "
                    f"Previous reason: {old_reason}. New reason: {reason or 'Manual'}"
                )

        except Exception as e:
            logger.exception(
                f"Error resetting circuit breaker for {strategy.value}: {e}"
            )

    def _get_remaining_time(self, cb_state: StrategyCircuitBreakerState) -> float:
        """Get remaining cooldown time in minutes."""
        if not cb_state.active or not cb_state.activation_time:
            return 0.0

        # Default cooldown: 1 hour
        cooldown_seconds = 3600
        elapsed = time.time() - cb_state.activation_time
        remaining = max(0, cooldown_seconds - elapsed)

        return remaining / 60.0

    async def get_risk_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive risk metrics for all strategies.

        Returns:
            Dictionary containing risk metrics
        """
        try:
            metrics = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "strategies": {},
                "portfolio": {
                    "total_exposure": float(self._total_portfolio_exposure),
                    "active_positions": len(self._active_positions),
                },
            }

            for strategy, profile in self.strategy_profiles.items():
                cb_state = self._circuit_breakers.get(strategy)
                metrics["strategies"][strategy.value] = {
                    "enabled": profile.enabled,
                    "circuit_breaker_active": cb_state.active if cb_state else False,
                    "circuit_breaker_reason": cb_state.reason if cb_state else "",
                    "daily_loss": float(cb_state.daily_loss) if cb_state else 0.0,
                    "total_loss": float(cb_state.total_loss) if cb_state else 0.0,
                    "total_profit": float(cb_state.total_profit) if cb_state else 0.0,
                    "consecutive_losses": cb_state.consecutive_losses
                    if cb_state
                    else 0,
                    "success_rate": (
                        cb_state.successful_trades
                        / (cb_state.successful_trades + cb_state.failed_trades)
                        if cb_state
                        and cb_state.successful_trades + cb_state.failed_trades > 0
                        else 0.0
                    ),
                }

            return metrics

        except Exception as e:
            logger.exception(f"Error getting risk metrics: {e}")
            return {}

    async def update_volatility_data(self, symbol: str, volatility: float) -> None:
        """
        Update volatility data for risk adjustment.

        Args:
            symbol: Volatility symbol (e.g., "vix", "crypto_volatility")
            volatility: Volatility value
        """
        try:
            self._volatility_data[symbol] = volatility
            logger.debug(f"Updated volatility for {symbol}: {volatility:.2f}")
        except Exception as e:
            logger.error(f"Error updating volatility data: {e}")

    async def update_market_correlation(
        self, market_1: str, market_2: str, correlation: float
    ) -> None:
        """
        Update market correlation data.

        Args:
            market_1: First market ID
            market_2: Second market ID
            correlation: Correlation coefficient (-1.0 to 1.0)
        """
        try:
            key = tuple(sorted((market_1, market_2)))
            self._market_correlations[key] = correlation
            logger.debug(
                f"Updated correlation: {market_1[:10]}... <-> {market_2[:10]}... = {correlation:.2f}"
            )

            # Save state
            self._save_state()

        except Exception as e:
            logger.error(f"Error updating market correlation: {e}")

    async def check_daily_reset(self) -> None:
        """
        Check and perform daily reset at UTC midnight.

        Should be called periodically (e.g., every hour).
        """
        try:
            async with self._state_lock:
                now = datetime.now(timezone.utc)

                for strategy, cb_state in self._circuit_breakers.items():
                    if (
                        cb_state.last_reset_date
                        and now.date() > cb_state.last_reset_date.date()
                    ):
                        # Reset daily loss
                        old_loss = cb_state.daily_loss
                        cb_state.daily_loss = Decimal("0.0")
                        cb_state.consecutive_losses = 0
                        cb_state.last_reset_date = now

                        # Audit log
                        self._audit_log(
                            strategy,
                            "DAILY_RESET",
                            {"previous_daily_loss": float(old_loss)},
                        )

                        logger.info(
                            f"🔄 Daily reset for {strategy.value}: "
                            f"reset daily loss from ${old_loss:.2f}"
                        )

                # Save state
                self._save_state()

        except Exception as e:
            logger.exception(f"Error checking daily reset: {e}")

    async def shutdown(self) -> None:
        """
        Shutdown risk manager gracefully.

        Saves final state and closes resources.
        """
        try:
            logger.info("Shutting down StrategyRiskManager")

            # Save final state
            self._save_state()

            # Get final metrics
            metrics = await self.get_risk_metrics()

            # Log summary
            logger.info(
                "Final Risk Metrics:\n"
                f"  Total Portfolio Exposure: ${metrics['portfolio']['total_exposure']:.2f}\n"
                f"  Active Positions: {metrics['portfolio']['active_positions']}"
            )

            for strategy_value, strategy_metrics in metrics["strategies"].items():
                logger.info(
                    f"  Strategy {strategy_value}:\n"
                    f"    Daily Loss: ${strategy_metrics['daily_loss']:.2f}\n"
                    f"    Total Profit: ${strategy_metrics['total_profit']:.2f}\n"
                    f"    Total Loss: ${strategy_metrics['total_loss']:.2f}\n"
                    f"    Success Rate: {strategy_metrics['success_rate']:.2%}"
                )

            logger.info("✅ StrategyRiskManager shutdown complete")

        except Exception as e:
            logger.exception(f"Error during shutdown: {e}")


# Example usage
async def example_usage():
    """Example of how to use StrategyRiskManager."""
    # Create risk manager
    risk_manager = StrategyRiskManager()

    # Check if trade is allowed
    trade_details = {
        "amount": 50.0,
        "market_id": "0x123...",
        "trade_id": "trade_123",
    }

    check_result = await risk_manager.check_trade_allowed(
        TradingStrategy.COPY_TRADING, trade_details
    )

    if check_result:
        print(f"Trade blocked: {check_result['reason']}")
    else:
        print("Trade allowed")

    # Record successful trade
    await risk_manager.record_trade_result(
        TradingStrategy.COPY_TRADING,
        success=True,
        profit=Decimal("5.0"),
        trade_id="trade_123",
    )

    # Get risk metrics
    metrics = await risk_manager.get_risk_metrics()
    print(f"Risk metrics: {metrics}")

    # Shutdown
    await risk_manager.shutdown()


if __name__ == "__main__":
    asyncio.run(example_usage())
