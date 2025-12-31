"""
Dynamic Position Sizer for Quality-Based Trading

This module implements advanced position sizing based on wallet quality,
risk metrics, and portfolio constraints.

Key Features:
- Quality multiplier based on wallet score
- Trade size adjustment based on original trade
- Risk adjustment during high volatility
- Per-wallet exposure limits
- Portfolio-level constraints

Author: Polymarket Copy Bot Team
Date: 2025-12-27
"""

import asyncio
import time
from dataclasses import dataclass
from decimal import Decimal, getcontext, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, Optional

from core.wallet_quality_scorer import WalletQualityScore
from utils.logger import get_logger
from utils.helpers import BoundedCache

# Configure Decimal for financial calculations
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

logger = get_logger(__name__)


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation"""

    position_size_usdc: Decimal
    shares: int
    confidence_score: float
    wallet_quality_score: float
    quality_multiplier: float
    risk_adjustment: float
    trade_adjustment: float
    final_multiplier: float
    max_size_hit: bool
    risk_limit_hit: bool
    reason: str


@dataclass
class PortfolioConstraints:
    """Portfolio-level constraints"""

    max_portfolio_percent: float
    max_position_size_usdc: Decimal
    max_daily_trades: int
    max_concurrent_positions: int
    max_wallet_exposure_percent: Dict[str, float]  # By quality tier
    max_daily_loss_usdc: Decimal


class DynamicPositionSizer:
    """
    Dynamic position sizer with quality-based adjustments.

    This sizer implements production-ready strategy for calculating
    optimal position sizes based on wallet quality, risk,
    and portfolio constraints.

    Thread Safety:
        Uses asyncio locks for thread-safe operations
    """

    # Position sizing constants
    BASE_POSITION_PERCENT = Decimal("0.02")  # 2% of portfolio per trade
    MIN_POSITION_SIZE_USDC = Decimal("1.00")
    MAX_POSITION_SIZE_USDC = Decimal("500.00")
    MIN_SHARES = 1

    # Quality multipliers
    ELITE_QUALITY_MULTIPLIER_MIN = Decimal("1.5")
    ELITE_QUALITY_MULTIPLIER_MAX = Decimal("2.0")
    EXPERT_QUALITY_MULTIPLIER_MIN = Decimal("1.2")
    EXPERT_QUALITY_MULTIPLIER_MAX = Decimal("1.5")
    GOOD_QUALITY_MULTIPLIER_MIN = Decimal("0.8")
    GOOD_QUALITY_MULTIPLIER_MAX = Decimal("1.2")
    POOR_QUALITY_MULTIPLIER = Decimal("0.0")  # Don't trade with poor wallets

    # Risk adjustments
    HIGH_VOLATILITY_THRESHOLD = 0.30  # 30%
    MODERATE_VOLATILITY_THRESHOLD = 0.20  # 20%
    HIGH_VOLATILITY_REDUCTION = Decimal("0.5")  # 50% reduction
    MODERATE_VOLATILITY_REDUCTION = Decimal("0.8")  # 20% reduction

    # Trade size adjustments
    MAX_TRADE_ADJUSTMENT = Decimal("1.5")  # 1.5x max for large trades
    NORMAL_TRADE_SIZE = Decimal("1000.00")

    # Per-wallet exposure limits
    ELITE_MAX_PORTFOLIO_PERCENT = 0.15  # 15%
    EXPERT_MAX_PORTFOLIO_PERCENT = 0.10  # 10%
    GOOD_MAX_PORTFOLIO_PERCENT = 0.07  # 7%
    POOR_MAX_PORTFOLIO_PERCENT = 0.0  # 0%

    def __init__(
        self,
        portfolio_value: Decimal,
        constraints: Optional[PortfolioConstraints] = None,
        cache_ttl_seconds: int = 3600,
        max_cache_size: int = 1000,
    ) -> None:
        """
        Initialize dynamic position sizer.

        Args:
            portfolio_value: Total portfolio value in USDC
            constraints: Portfolio constraints (uses defaults if None)
            cache_ttl_seconds: Time-to-live for cached calculations
            max_cache_size: Maximum number of cached calculations
        """
        self.portfolio_value = Decimal(str(portfolio_value))
        self.constraints = constraints or self._default_constraints()

        # Track exposure per wallet
        self._wallet_exposure: BoundedCache = BoundedCache(
            max_size=500,
            ttl_seconds=86400,  # 24 hours
            memory_threshold_mb=50.0,
            cleanup_interval_seconds=300,
        )

        # Track daily trade counts
        self._daily_trade_counts: BoundedCache = BoundedCache(
            max_size=100,
            ttl_seconds=86400,  # 24 hours
            memory_threshold_mb=10.0,
            cleanup_interval_seconds=60,
        )

        # Track portfolio exposure
        self._portfolio_exposure: BoundedCache = BoundedCache(
            max_size=100,
            ttl_seconds=86400,  # 24 hours
            memory_threshold_mb=20.0,
            cleanup_interval_seconds=300,
        )

        self._state_lock = asyncio.Lock()

        logger.info(
            f"DynamicPositionSizer initialized with portfolio value: ${self.portfolio_value:.2f}"
        )

    def _default_constraints(self) -> PortfolioConstraints:
        """Create default portfolio constraints"""
        return PortfolioConstraints(
            max_portfolio_percent=0.05,  # 5% per trade
            max_position_size_usdc=self.MAX_POSITION_SIZE_USDC,
            max_daily_trades=50,
            max_concurrent_positions=10,
            max_wallet_exposure_percent={
                "Elite": self.ELITE_MAX_PORTFOLIO_PERCENT,
                "Expert": self.EXPERT_MAX_PORTFOLIO_PERCENT,
                "Good": self.GOOD_MAX_PORTFOLIO_PERCENT,
                "Poor": self.POOR_MAX_PORTFOLIO_PERCENT,
            },
            max_daily_loss_usdc=Decimal("100.00"),
        )

    async def calculate_position_size(
        self,
        wallet_score: WalletQualityScore,
        original_trade_amount: Decimal,
        current_volatility: float = 0.0,
        account_balance: Optional[Decimal] = None,
    ) -> PositionSizeResult:
        """
        Calculate optimal position size based on wallet quality and risk.

        Args:
            wallet_score: Wallet quality score
            original_trade_amount: Original trade amount from copied wallet
            current_volatility: Current market volatility (0.0 to 1.0)
            account_balance: Current account balance (uses portfolio value if None)

        Returns:
            PositionSizeResult with calculated size and metadata
        """
        try:
            async with self._state_lock:
                # Use account balance or portfolio value
                balance = (
                    Decimal(str(account_balance))
                    if account_balance
                    else self.portfolio_value
                )

                # Check if wallet quality is acceptable
                if wallet_score.quality_tier == "Poor":
                    return PositionSizeResult(
                        position_size_usdc=Decimal("0.00"),
                        shares=0,
                        confidence_score=wallet_score.total_score,
                        wallet_quality_score=wallet_score.total_score,
                        quality_multiplier=0.0,
                        risk_adjustment=1.0,
                        trade_adjustment=1.0,
                        final_multiplier=0.0,
                        max_size_hit=False,
                        risk_limit_hit=False,
                        reason="Poor quality wallet - not trading",
                    )

                # Calculate base position size (2% of portfolio)
                base_size = balance * self.BASE_POSITION_PERCENT

                # Calculate quality multiplier
                quality_multiplier = self._calculate_quality_multiplier(wallet_score)

                # Calculate trade size adjustment
                trade_adjustment = self._calculate_trade_adjustment(
                    original_trade_amount
                )

                # Calculate risk adjustment based on volatility
                risk_adjustment = self._calculate_risk_adjustment(current_volatility)

                # Calculate final multiplier
                final_multiplier = (
                    quality_multiplier * trade_adjustment * risk_adjustment
                )

                # Calculate final position size
                final_size = base_size * final_multiplier

                # Apply wallet exposure limits
                final_size = await self._apply_wallet_exposure_limit(
                    wallet_score.wallet_address,
                    wallet_score.quality_tier,
                    final_size,
                    balance,
                )

                # Apply portfolio constraints
                final_size = self._apply_portfolio_constraints(final_size, balance)

                # Apply hard limits
                final_size = self._apply_hard_limits(final_size)

                # Round to 2 decimal places
                final_size = final_size.quantize(Decimal("0.01"))

                # Calculate number of shares (assuming $1 per share for simplicity)
                shares = int(final_size)

                # Check if limits were hit
                max_size_hit = final_size >= self.MAX_POSITION_SIZE_USDC
                risk_limit_hit = (
                    risk_adjustment < Decimal("1.0")
                    and final_size < base_size * quality_multiplier * trade_adjustment
                )

                # Build result
                result = PositionSizeResult(
                    position_size_usdc=final_size,
                    shares=max(shares, self.MIN_SHARES),
                    confidence_score=wallet_score.total_score,
                    wallet_quality_score=wallet_score.total_score,
                    quality_multiplier=float(quality_multiplier),
                    risk_adjustment=float(risk_adjustment),
                    trade_adjustment=float(trade_adjustment),
                    final_multiplier=float(final_multiplier),
                    max_size_hit=max_size_hit,
                    risk_limit_hit=risk_limit_hit,
                    reason="Position sized successfully",
                )

                logger.info(
                    f"📏 Position sized: ${final_size:.2f} "
                    f"(Base: ${base_size:.2f}, Quality: {float(quality_multiplier):.2f}x, "
                    f"Trade: {float(trade_adjustment):.2f}x, Risk: {float(risk_adjustment):.2f}x) "
                    f"for {wallet_score.wallet_address[-6:]} ({wallet_score.quality_tier})"
                )

                return result

        except (InvalidOperation, ValueError, TypeError) as e:
            logger.error(f"Error calculating position size: {e}")
            return PositionSizeResult(
                position_size_usdc=self.MIN_POSITION_SIZE_USDC,
                shares=1,
                confidence_score=0.0,
                wallet_quality_score=0.0,
                quality_multiplier=1.0,
                risk_adjustment=1.0,
                trade_adjustment=1.0,
                final_multiplier=1.0,
                max_size_hit=False,
                risk_limit_hit=False,
                reason=f"Calculation error: {str(e)[:50]}",
            )
        except Exception as e:
            logger.exception(f"Unexpected error calculating position size: {e}")
            return PositionSizeResult(
                position_size_usdc=self.MIN_POSITION_SIZE_USDC,
                shares=1,
                confidence_score=0.0,
                wallet_quality_score=0.0,
                quality_multiplier=1.0,
                risk_adjustment=1.0,
                trade_adjustment=1.0,
                final_multiplier=1.0,
                max_size_hit=False,
                risk_limit_hit=False,
                reason=f"Unexpected error: {str(e)[:50]}",
            )

    def _calculate_quality_multiplier(
        self, wallet_score: WalletQualityScore
    ) -> Decimal:
        """
        Calculate quality multiplier based on wallet score and tier.

        Args:
            wallet_score: Wallet quality score

        Returns:
            Quality multiplier (0.0 to 2.0)
        """
        try:
            quality_tier = wallet_score.quality_tier
            total_score = wallet_score.total_score

            if quality_tier == "Elite":
                # Interpolate within elite range (9.0-10.0)
                score_range = total_score - 9.0
                multiplier_range = (
                    self.ELITE_QUALITY_MULTIPLIER_MAX
                    - self.ELITE_QUALITY_MULTIPLIER_MIN
                )
                interpolated = (score_range / 1.0) * multiplier_range
                return self.ELITE_QUALITY_MULTIPLIER_MIN + interpolated

            elif quality_tier == "Expert":
                # Interpolate within expert range (7.0-8.9)
                score_range = total_score - 7.0
                multiplier_range = (
                    self.EXPERT_QUALITY_MULTIPLIER_MAX
                    - self.EXPERT_QUALITY_MULTIPLIER_MIN
                )
                interpolated = (score_range / 1.9) * multiplier_range
                return self.EXPERT_QUALITY_MULTIPLIER_MIN + interpolated

            elif quality_tier == "Good":
                # Interpolate within good range (5.0-6.9)
                score_range = total_score - 5.0
                multiplier_range = (
                    self.GOOD_QUALITY_MULTIPLIER_MAX - self.GOOD_QUALITY_MULTIPLIER_MIN
                )
                interpolated = (score_range / 1.9) * multiplier_range
                return self.GOOD_QUALITY_MULTIPLIER_MIN + interpolated

            else:  # Poor
                return self.POOR_QUALITY_MULTIPLIER

        except Exception as e:
            logger.error(f"Error calculating quality multiplier: {e}")
            return Decimal("1.0")

    def _calculate_trade_adjustment(self, original_trade_amount: Decimal) -> Decimal:
        """
        Calculate trade size adjustment based on original trade size.

        Don't copy huge positions blindly - adjust based on relative size.

        Args:
            original_trade_amount: Original trade amount

        Returns:
            Trade adjustment factor (0.5 to 1.5)
        """
        try:
            # Normalize trade amount relative to normal size
            ratio = original_trade_amount / self.NORMAL_TRADE_SIZE

            # Cap ratio at max adjustment
            ratio = min(ratio, self.MAX_TRADE_ADJUSTMENT)

            # Ensure minimum adjustment
            ratio = max(ratio, Decimal("0.5"))

            return ratio

        except Exception as e:
            logger.error(f"Error calculating trade adjustment: {e}")
            return Decimal("1.0")

    def _calculate_risk_adjustment(self, current_volatility: float) -> Decimal:
        """
        Calculate risk adjustment based on market volatility.

        Reduce position sizes during high volatility.

        Args:
            current_volatility: Current market volatility (0.0 to 1.0)

        Returns:
            Risk adjustment factor (0.5 to 1.0)
        """
        try:
            if current_volatility >= self.HIGH_VOLATILITY_THRESHOLD:
                return self.HIGH_VOLATILITY_REDUCTION
            elif current_volatility >= self.MODERATE_VOLATILITY_THRESHOLD:
                return self.MODERATE_VOLATILITY_REDUCTION
            else:
                return Decimal("1.0")

        except Exception as e:
            logger.error(f"Error calculating risk adjustment: {e}")
            return Decimal("1.0")

    async def _apply_wallet_exposure_limit(
        self,
        wallet_address: str,
        quality_tier: str,
        position_size: Decimal,
        portfolio_value: Decimal,
    ) -> Decimal:
        """
        Apply per-wallet exposure limits.

        Args:
            wallet_address: Wallet address
            quality_tier: Quality tier of wallet
            position_size: Calculated position size
            portfolio_value: Total portfolio value

        Returns:
            Adjusted position size
        """
        try:
            # Get max exposure for this wallet tier
            max_exposure_percent = self.constraints.max_wallet_exposure_percent.get(
                quality_tier, 0.0
            )

            if max_exposure_percent == 0.0:
                return Decimal("0.00")  # No exposure allowed

            # Get current exposure for this wallet
            exposure_key = f"exposure_{wallet_address}"
            current_exposure = self._wallet_exposure.get(exposure_key, Decimal("0.00"))

            # Calculate max additional exposure
            max_additional_exposure = (
                portfolio_value * Decimal(str(max_exposure_percent)) - current_exposure
            )

            # If adding this position would exceed limit, reduce size
            if position_size > max_additional_exposure:
                logger.info(
                    f"🔒 Exposure limit for {wallet_address[-6:]}: "
                    f"Current: ${current_exposure:.2f}, "
                    f"Max: ${portfolio_value * Decimal(str(max_exposure_percent)):.2f}, "
                    f"Request: ${position_size:.2f}, "
                    f"Limited to: ${max_additional_exposure:.2f}"
                )
                return max(max_additional_exposure, Decimal("0.00"))

            return position_size

        except Exception as e:
            logger.error(f"Error applying wallet exposure limit: {e}")
            return position_size

    def _apply_portfolio_constraints(
        self, position_size: Decimal, portfolio_value: Decimal
    ) -> Decimal:
        """
        Apply portfolio-level constraints.

        Args:
            position_size: Calculated position size
            portfolio_value: Total portfolio value

        Returns:
            Adjusted position size
        """
        try:
            # Max percent of portfolio per trade
            max_percent_size = portfolio_value * Decimal(
                str(self.constraints.max_portfolio_percent)
            )
            position_size = min(position_size, max_percent_size)

            # Max position size absolute limit
            position_size = min(position_size, self.constraints.max_position_size_usdc)

            return position_size

        except Exception as e:
            logger.error(f"Error applying portfolio constraints: {e}")
            return position_size

    def _apply_hard_limits(self, position_size: Decimal) -> Decimal:
        """
        Apply hard limits to position size.

        Args:
            position_size: Calculated position size

        Returns:
            Adjusted position size
        """
        try:
            # Ensure minimum size
            position_size = max(position_size, self.MIN_POSITION_SIZE_USDC)

            # Ensure maximum size
            position_size = min(position_size, self.MAX_POSITION_SIZE_USDC)

            return position_size

        except Exception as e:
            logger.error(f"Error applying hard limits: {e}")
            return position_size

    async def record_trade(self, wallet_address: str, position_size: Decimal) -> bool:
        """
        Record a trade for exposure and daily count tracking.

        Args:
            wallet_address: Wallet address
            position_size: Position size

        Returns:
            True if recorded successfully, False otherwise
        """
        try:
            async with self._state_lock:
                # Update wallet exposure
                exposure_key = f"exposure_{wallet_address}"
                current_exposure = self._wallet_exposure.get(
                    exposure_key, Decimal("0.00")
                )
                self._wallet_exposure.set(
                    exposure_key, current_exposure + position_size
                )

                # Update daily trade count
                today_key = f"trades_{time.strftime('%Y-%m-%d')}_{wallet_address}"
                current_count = self._daily_trade_counts.get(today_key, 0)
                self._daily_trade_counts.set(today_key, current_count + 1)

                return True

        except Exception as e:
            logger.error(f"Error recording trade: {e}")
            return False

    async def record_position_closure(
        self, wallet_address: str, position_size: Decimal
    ) -> bool:
        """
        Record position closure to update exposure.

        Args:
            wallet_address: Wallet address
            position_size: Position size

        Returns:
            True if recorded successfully, False otherwise
        """
        try:
            async with self._state_lock:
                # Update wallet exposure
                exposure_key = f"exposure_{wallet_address}"
                current_exposure = self._wallet_exposure.get(
                    exposure_key, Decimal("0.00")
                )
                new_exposure = max(current_exposure - position_size, Decimal("0.00"))
                self._wallet_exposure.set(exposure_key, new_exposure)

                return True

        except Exception as e:
            logger.error(f"Error recording position closure: {e}")
            return False

    async def get_wallet_exposure(self, wallet_address: str) -> Decimal:
        """
        Get current exposure for a specific wallet.

        Args:
            wallet_address: Wallet address

        Returns:
            Current exposure in USDC
        """
        try:
            exposure_key = f"exposure_{wallet_address}"
            return self._wallet_exposure.get(exposure_key, Decimal("0.00"))
        except Exception as e:
            logger.error(f"Error getting wallet exposure: {e}")
            return Decimal("0.00")

    async def get_daily_trade_count(self, wallet_address: Optional[str] = None) -> int:
        """
        Get daily trade count for wallet or total.

        Args:
            wallet_address: Wallet address (None for total)

        Returns:
            Daily trade count
        """
        try:
            today = time.strftime("%Y-%m-%d")

            if wallet_address:
                key = f"trades_{today}_{wallet_address}"
                return self._daily_trade_counts.get(key, 0)
            else:
                # Count all trades for today
                total = 0
                for cache_key in self._daily_trade_counts._cache.keys():
                    if cache_key.startswith(f"trades_{today}_"):
                        total += self._daily_trade_counts.get(cache_key, 0)
                return total

        except Exception as e:
            logger.error(f"Error getting daily trade count: {e}")
            return 0

    async def check_daily_limits(
        self, wallet_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if daily limits have been reached.

        Args:
            wallet_address: Wallet address (None for portfolio-wide)

        Returns:
            Dictionary with limit status
        """
        try:
            daily_count = await self.get_daily_trade_count(wallet_address)
            max_trades = (
                self.constraints.max_daily_trades
                if wallet_address
                else self.constraints.max_daily_trades * 5
            )  # 5x for portfolio-wide

            wallet_exceeded = daily_count >= max_trades
            reason = (
                f"Wallet daily limit reached ({daily_count}/{max_trades})"
                if wallet_exceeded
                else "Within limits"
            )

            return {
                "wallet_address": wallet_address,
                "daily_count": daily_count,
                "max_trades": max_trades,
                "exceeded": wallet_exceeded,
                "reason": reason,
            }

        except Exception as e:
            logger.error(f"Error checking daily limits: {e}")
            return {
                "exceeded": False,
                "reason": f"Error checking limits: {str(e)[:50]}",
            }

    async def get_position_summary(self) -> Dict[str, Any]:
        """
        Get summary of position sizing statistics.

        Returns:
            Dictionary with sizing statistics
        """
        try:
            # Calculate total exposure
            total_exposure = Decimal("0.00")
            wallet_count = 0

            for cache_key in self._wallet_exposure._cache.keys():
                if cache_key.startswith("exposure_"):
                    exposure = self._wallet_exposure.get(cache_key, Decimal("0.00"))
                    if exposure > Decimal("0.00"):
                        total_exposure += exposure
                        wallet_count += 1

            # Get daily trade counts
            today = time.strftime("%Y-%m-%d")
            today_trades = 0
            for cache_key in self._daily_trade_counts._cache.keys():
                if cache_key.startswith(f"trades_{today}_"):
                    today_trades += self._daily_trade_counts.get(cache_key, 0)

            return {
                "portfolio_value": float(self.portfolio_value),
                "total_exposure": float(total_exposure),
                "exposure_percent": float(total_exposure / self.portfolio_value)
                if self.portfolio_value > 0
                else 0.0,
                "active_wallets": wallet_count,
                "today_trades": today_trades,
                "portfolio_utilization": float(total_exposure / self.portfolio_value)
                if self.portfolio_value > 0
                else 0.0,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Error getting position summary: {e}")
            return {}

    async def cleanup(self) -> None:
        """Clean up expired cache entries"""
        try:
            self._wallet_exposure.cleanup()
            self._daily_trade_counts.cleanup()
            self._portfolio_exposure.cleanup()
            logger.info("DynamicPositionSizer cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Example usage
async def example_usage():
    """Example of how to use DynamicPositionSizer"""
    # Create sizer with $10,000 portfolio
    sizer = DynamicPositionSizer(portfolio_value=Decimal("10000.00"))

    # Create sample wallet score
    from core.wallet_quality_scorer import (
        WalletQualityScore,
        WalletDomainExpertise,
        WalletRiskMetrics,
    )

    wallet_score = WalletQualityScore(
        wallet_address="0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
        total_score=8.5,
        performance_score=7.8,
        risk_score=9.2,
        consistency_score=8.0,
        domain_expertise=WalletDomainExpertise(
            primary_domain="politics",
            specialization_score=0.85,
            domain_win_rate=0.72,
            total_trades_in_domain=128,
            domain_roi=28.0,
        ),
        risk_metrics=WalletRiskMetrics(
            volatility=0.15,
            max_drawdown=0.18,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            calmar_ratio=1.8,
            tail_risk=0.1,
        ),
        is_market_maker=False,
        red_flags=[],
        quality_tier="Expert",
    )

    # Calculate position size
    result = await sizer.calculate_position_size(
        wallet_score=wallet_score,
        original_trade_amount=Decimal("500.00"),
        current_volatility=0.15,  # 15% volatility
    )

    logger.info("Position Size Calculation:")
    logger.info(f"  Position Size: ${result.position_size_usdc:.2f}")
    logger.info(f"  Shares: {result.shares}")
    logger.info(f"  Quality Score: {result.wallet_quality_score:.2f}/10")
    logger.info(f"  Quality Multiplier: {result.quality_multiplier:.2f}x")
    logger.info(f"  Risk Adjustment: {result.risk_adjustment:.2f}x")
    logger.info(f"  Trade Adjustment: {result.trade_adjustment:.2f}x")
    logger.info(f"  Final Multiplier: {result.final_multiplier:.2f}x")
    logger.info(f"  Reason: {result.reason}")

    # Record the trade
    await sizer.record_trade(wallet_score.wallet_address, result.position_size_usdc)

    # Get position summary
    summary = await sizer.get_position_summary()
    logger.info(f"\nPosition Summary: {summary}")

    # Cleanup
    await sizer.cleanup()


if __name__ == "__main__":
    asyncio.run(example_usage())
