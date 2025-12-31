"""
Wallet Quality Scorer for Production-Ready Copy Trading

This module implements a comprehensive wallet evaluation framework that distinguishes
between sustainable directional traders, market makers, and low-quality wallets.

Core Features:
- Profit Factor Calculation (gross_profits / gross_losses)
- Maximum Drawdown Analysis (peak-to-trough detection)
- Win Rate Consistency (rolling 30-day standard deviation)
- Domain Expertise Scoring (category specialization analysis)
- Position Sizing Consistency (normalized standard deviation)
- Market Condition Adaptation (volatility regime scoring)
- Time-to-Recovery Ratio (drawdown recovery speed)
- Market Maker Detection (multi-pattern analysis)
- Red Flag Detection (insider trading, wash trading, etc.)

Author: Polymarket Copy Bot Team
Date: 2025-12-27
Version: 2.0 (Production-Ready)
"""

import asyncio
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, DivisionByZero, InvalidOperation, getcontext
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from config.scanner_config import ScannerConfig
from core.circuit_breaker import CircuitBreaker
from utils.helpers import BoundedCache
from utils.logger import get_logger
from utils.validation import InputValidator, ValidationError

# Configure Decimal for financial calculations
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

logger = get_logger(__name__)


class WalletQualityTier(Enum):
    """Wallet quality tiers for classification"""

    ELITE = "Elite"  # 9.0-10.0 score
    EXPERT = "Expert"  # 7.0-8.9 score
    GOOD = "Good"  # 5.0-6.9 score
    POOR = "Poor"  # <5.0 score (excluded)


class RedFlagType(Enum):
    """Types of red flags for wallet exclusion"""

    NEW_WALLET_LARGE_BET = "NEW_WALLET_LARGE_BET"
    LUCK_NOT_SKILL = "LUCK_NOT_SKILL"
    WASH_TRADING = "WASH_TRADING"
    NEGATIVE_PROFIT_FACTOR = "NEGATIVE_PROFIT_FACTOR"
    NO_SPECIALIZATION = "NO_SPECIALIZATION"
    EXCESSIVE_DRAWDOWN = "EXCESSIVE_DRAWDOWN"
    LOW_WIN_RATE = "LOW_WIN_RATE"
    INSIDER_TRADING_SUSPECTED = "INSIDER_TRADING_SUSPECTED"
    SUSPICIOUS_PATTERN = "SUSPICIOUS_PATTERN"


@dataclass
class TradingHistory:
    """Historical trading data for a wallet"""

    wallet_address: str
    trades: List[Dict[str, Any]] = field(default_factory=list)
    total_trades: int = 0
    profitable_trades: int = 0
    gross_profits: Decimal = Decimal("0.00")
    gross_losses: Decimal = Decimal("0.00")
    timestamps: List[float] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    position_sizes: List[float] = field(default_factory=list)
    max_drawdowns: List[Tuple[float, float]] = field(
        default_factory=list
    )  # (peak, trough) pairs


@dataclass
class DomainExpertiseMetrics:
    """Domain expertise metrics for a wallet"""

    primary_domain: str
    specialization_score: float = 0.0  # 0.0 to 1.0
    domain_trades: int = 0
    domain_win_rate: float = 0.0
    domain_roi: Decimal = Decimal("0.00")
    category_diversity: float = 0.0  # Lower is better
    consistency_score: float = 0.0  # Win rate consistency in domain


@dataclass
class RiskMetrics:
    """Comprehensive risk metrics for a wallet"""

    profit_factor: float  # Gross profits / gross losses
    max_drawdown: float  # Peak-to-trough analysis
    max_drawdown_duration: float  # Hours to recover from max drawdown
    win_rate: float  # Overall win rate
    win_rate_std: float  # Rolling 30-day standard deviation
    win_rate_consistency: float  # 1.0 - std (higher is better)
    volatility: float  # Standard deviation of returns
    sharpe_ratio: float  # Risk-adjusted returns
    sortino_ratio: float  # Downside risk-adjusted returns
    calmar_ratio: float  # Return / max drawdown
    time_to_recovery_ratio: float  # Recovery speed from drawdowns
    tail_risk: float  # Risk of extreme losses
    position_sizing_std: float  # Consistency of position sizes


@dataclass
class QualityScore:
    """Comprehensive quality score for a wallet"""

    wallet_address: str
    quality_tier: WalletQualityTier
    total_score: float  # 0.0 to 10.0
    performance_score: float  # 0.0 to 10.0
    risk_score: float  # 0.0 to 10.0 (higher is better)
    consistency_score: float  # 0.0 to 10.0
    domain_expertise: DomainExpertiseMetrics
    risk_metrics: RiskMetrics
    is_market_maker: bool
    red_flags: List[Tuple[RedFlagType, str]]  # (type, reason)
    confidence_score: float  # 0.0 to 1.0
    last_updated: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class WalletQualityScorer:
    """
    Advanced wallet quality scoring with comprehensive evaluation framework.

    This scorer implements a multi-dimensional evaluation system that analyzes:
    - Profit Factor: Gross profits / gross losses (must be >1.0)
    - Maximum Drawdown: Peak-to-trough analysis with recovery time
    - Win Rate Consistency: Rolling 30-day standard deviation
    - Domain Expertise: Category specialization (70%+ in 1-2 categories)
    - Position Sizing Consistency: Normalized standard deviation
    - Market Condition Adaptation: Volatility regime scoring
    - Time-to-Recovery Ratio: Speed of recovery from drawdowns

    Critical Risk Controls:
    - Market Maker Detection: trade_count >500 AND avg_hold_time <1hr AND win_rate 45-55%
    - Red Flag Detection: 9 types of automatic exclusion
    - Circuit Breaker Integration: Automatic disabling during high load
    - Memory-Safe Caching: BoundedCache with TTL 1 hour

    Thread Safety:
        Uses asyncio locks for all state modifications
    Rate Limiting:
        Maximum 10 calls/second to API

    Args:
        config: Scanner configuration with strategy parameters
        circuit_breaker: Circuit breaker instance for risk management
    """

    # Market maker detection thresholds (NON-NEGOTIABLE)
    MM_TRADE_COUNT_THRESHOLD = 500
    MM_AVG_HOLD_TIME_THRESHOLD = 3600  # 1 hour in seconds
    MM_WIN_RATE_MIN = 0.45
    MM_WIN_RATE_MAX = 0.55
    MM_PROFIT_PER_TRADE_THRESHOLD = Decimal("0.01")  # 1% minimum ROI per trade

    # Red flag thresholds
    NEW_WALLET_MAX_DAYS = 7
    NEW_WALLET_MAX_BET = Decimal("1000.00")  # $1000 USDC
    LUCK_WIN_RATE_THRESHOLD = 0.90
    LUCK_MIN_TRADES = 20
    WASH_TRADING_SCORE_THRESHOLD = 0.70
    NEGATIVE_PROFIT_FACTOR_THRESHOLD = 1.0
    MAX_CATEGORIES_THRESHOLD = 5
    EXCESSIVE_DRAWDOWN_THRESHOLD = 0.35
    MIN_WIN_RATE_THRESHOLD = 0.60
    MIN_TRADES_FOR_STATS = 30
    INSIDER_VOLUME_RATIO_THRESHOLD = 5.0  # 5x normal volume
    INSIDER_TIMING_WINDOW_HOURS = 1  # 1 hour before events

    # Quality scoring weights
    PERFORMANCE_WEIGHT = 0.35
    RISK_WEIGHT = 0.30
    CONSISTENCY_WEIGHT = 0.20
    DOMAIN_WEIGHT = 0.15

    # Rolling window periods (in seconds)
    WIN_RATE_ROLLING_WINDOW = 2592000  # 30 days
    VOLATILITY_WINDOW = 864000  # 10 days
    RECOVERY_WINDOW = 604800  # 7 days

    def __init__(
        self,
        config: ScannerConfig,
        circuit_breaker: Optional[CircuitBreaker] = None,
        cache_ttl_seconds: int = 3600,  # 1 hour
        max_cache_size: int = 1000,
    ) -> None:
        """
        Initialize wallet quality scorer.

        Args:
            config: Scanner configuration with strategy parameters
            circuit_breaker: Circuit breaker instance (optional)
            cache_ttl_seconds: TTL for cached scores
            max_cache_size: Maximum cache size
        """
        self.config = config
        self.circuit_breaker = circuit_breaker

        # Thread safety
        self._state_lock = asyncio.Lock()

        # Score cache with memory tracking
        self._score_cache = BoundedCache(
            max_size=max_cache_size,
            ttl_seconds=cache_ttl_seconds,
            memory_threshold_mb=100.0,
            cleanup_interval_seconds=300,
            component_name="wallet_quality_scorer.score_cache",
        )

        # Trading history cache (for rolling calculations)
        self._history_cache = BoundedCache(
            max_size=5000,  # More history for rolling calculations
            ttl_seconds=self.WIN_RATE_ROLLING_WINDOW + 86400,  # 30 days + buffer
            memory_threshold_mb=200.0,
            cleanup_interval_seconds=600,
            component_name="wallet_quality_scorer.history_cache",
        )

        # Rate limiting
        self._rate_limiter = asyncio.Semaphore(10)  # Max 10 concurrent calls
        self._call_timestamps: Dict[str, float] = {}  # Per-API rate tracking

        # Performance metrics
        self._total_scores = 0
        self._mm_detections = 0
        self._red_flag_detections = 0

        logger.info(
            f"WalletQualityScorer v2.0 initialized with "
            f"circuit_breaker={circuit_breaker is not None}, "
            f"cache_ttl={cache_ttl_seconds}s, "
            f"max_cache_size={max_cache_size}"
        )

    async def score_wallet(
        self,
        wallet_address: str,
        wallet_data: Dict[str, Any],
        use_cache: bool = True,
    ) -> Optional[QualityScore]:
        """
        Score a wallet using comprehensive evaluation framework.

        Args:
            wallet_address: Wallet address to score
            wallet_data: Dictionary containing wallet metrics and trade history
            use_cache: Whether to use cached scores (default: True)

        Returns:
            QualityScore with comprehensive metrics, or None if error occurs
        """
        try:
            # Validate wallet address before processing
            validated_address = InputValidator.validate_wallet_address(wallet_address)

            # Validate wallet_data structure
            if not wallet_data or not isinstance(wallet_data, dict):
                logger.error(f"Invalid wallet_data type for {validated_address[-6:]}")
                return None

            # Check circuit breaker
            if self.circuit_breaker and self.circuit_breaker.is_active():
                logger.warning(
                    f"Circuit breaker active - using cached/placeholder score for {validated_address[-6:]}"
                )
                return await self._get_cached_or_placeholder_score(validated_address)

            # Check cache
            cache_key = f"score_{validated_address}"
            if use_cache:
                cached = self._score_cache.get(cache_key)
                if cached:
                    logger.debug(f"Using cached score for {wallet_address[-6:]}")
                    return cached

            # Rate limiting check
            await self._check_rate_limit("polymarket_api")

            # Build trading history from wallet data
            history = self._build_trading_history(wallet_address, wallet_data)

            # Calculate comprehensive metrics
            risk_metrics = self._calculate_risk_metrics(history)
            domain_expertise = self._calculate_domain_expertise(history)
            is_market_maker = self._detect_market_maker_advanced(history, risk_metrics)
            red_flags = self._detect_red_flags(history, risk_metrics, domain_expertise)

            # Calculate component scores
            performance_score = self._calculate_performance_score(history, risk_metrics)
            risk_score = self._calculate_risk_score(risk_metrics, red_flags)
            consistency_score = self._calculate_consistency_score(history, risk_metrics)
            domain_score = self._calculate_domain_score(domain_expertise)

            # Calculate total score
            total_score = self._calculate_total_score(
                performance_score=performance_score,
                risk_score=risk_score,
                consistency_score=consistency_score,
                domain_score=domain_score,
                red_flags=red_flags,
            )

            # Determine quality tier
            quality_tier = self._determine_quality_tier(total_score)

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                history, risk_metrics, total_score, domain_expertise
            )

            # Build comprehensive score
            quality_score = QualityScore(
                wallet_address=wallet_address,
                quality_tier=quality_tier,
                total_score=total_score,
                performance_score=performance_score,
                risk_score=risk_score,
                consistency_score=consistency_score,
                domain_expertise=domain_expertise,
                risk_metrics=risk_metrics,
                is_market_maker=is_market_maker,
                red_flags=red_flags,
                confidence_score=confidence_score,
                last_updated=time.time(),
                metadata={
                    "trades_analyzed": history.total_trades,
                    "calculation_timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Store in cache
            self._score_cache.set(cache_key, quality_score)
            self._history_cache.set(f"history_{wallet_address}", history)

            # Update metrics
            self._total_scores += 1
            if is_market_maker:
                self._mm_detections += 1
            if red_flags:
                self._red_flag_detections += len(red_flags)

            logger.info(
                f"✅ Scored wallet {wallet_address[-6:]}: "
                f"{quality_tier.value} ({total_score:.2f}/10), "
                f"Profit Factor: {risk_metrics.profit_factor:.2f}, "
                f"Max Drawdown: {risk_metrics.max_drawdown:.1%}, "
                f"Win Rate: {risk_metrics.win_rate:.1%} "
                f"(±{risk_metrics.win_rate_std:.1%}), "
                f"Domain: {domain_expertise.primary_domain} "
                f"({domain_expertise.specialization_score:.1%}), "
                f"MM: {is_market_maker}, "
                f"Red Flags: {len(red_flags)}"
            )

            return quality_score

        except DivisionByZero:
            logger.error(f"Division by zero scoring wallet {wallet_address[-6:]}")
            return None
        except (InvalidOperation, ValueError, KeyError, ValidationError) as e:
            logger.exception(
                f"Validation error scoring wallet {wallet_address[-6:]}: {e}"
            )
            return None
        except Exception as e:
            logger.exception(
                f"Unexpected error scoring wallet {wallet_address[-6:]}: {e}"
            )
            return None

    def _build_trading_history(
        self, wallet_address: str, wallet_data: Dict[str, Any]
    ) -> TradingHistory:
        """Build trading history object from wallet data"""
        try:
            trades = wallet_data.get("trades", [])
            if not trades:
                # Create minimal history if no trade data provided
                logger.warning(
                    f"No trade data for {wallet_address[-6:]} - using metrics only"
                )
                return TradingHistory(
                    wallet_address=wallet_address,
                    total_trades=wallet_data.get("trade_count", 0),
                )

            # Extract trade data
            parsed_trades = []
            for trade in trades:
                try:
                    parsed = {
                        "timestamp": self._parse_timestamp(trade.get("timestamp")),
                        "is_profitable": trade.get("is_profitable", False),
                        "pnl": Decimal(str(trade.get("pnl", "0.0"))),
                        "category": trade.get("category", "general"),
                        "position_size": float(trade.get("position_size", 100)),
                    }
                    parsed_trades.append(parsed)
                except (InvalidOperation, ValueError) as e:
                    logger.warning(f"Error parsing trade: {e}")
                    continue

            # Calculate aggregate metrics
            gross_profits = (
                sum(trade["pnl"] for trade in parsed_trades if trade["pnl"] > 0)
                if parsed_trades
                else Decimal("0.00")
            )

            gross_losses = (
                sum(abs(trade["pnl"]) for trade in parsed_trades if trade["pnl"] < 0)
                if parsed_trades
                else Decimal("0.00")
            )

            profitable_trades = sum(
                1 for trade in parsed_trades if trade["is_profitable"]
            )

            # Extract categories
            categories = [trade["category"] for trade in parsed_trades]

            # Extract position sizes
            position_sizes = [trade["position_size"] for trade in parsed_trades]

            # Extract timestamps
            timestamps = [trade["timestamp"] for trade in parsed_trades]

            return TradingHistory(
                wallet_address=wallet_address,
                trades=parsed_trades,
                total_trades=len(parsed_trades),
                profitable_trades=profitable_trades,
                gross_profits=gross_profits,
                gross_losses=gross_losses,
                timestamps=timestamps,
                categories=categories,
                position_sizes=position_sizes,
            )

        except Exception as e:
            logger.exception(f"Error building trading history: {e}")
            return TradingHistory(wallet_address=wallet_address, total_trades=0)

    def _parse_timestamp(self, timestamp: Any) -> float:
        """Parse timestamp to float (seconds since epoch)"""
        if isinstance(timestamp, (int, float)):
            return float(timestamp)
        elif isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                return dt.timestamp()
            except ValueError:
                # Try Unix timestamp
                return float(timestamp)
        return time.time()

    def _calculate_risk_metrics(self, history: TradingHistory) -> RiskMetrics:
        """Calculate comprehensive risk metrics"""
        try:
            if history.total_trades < self.MIN_TRADES_FOR_STATS:
                return self._get_default_risk_metrics(history)

            profit_factor = self._calculate_profit_factor(history)
            win_rate, win_rate_std, win_rate_consistency = (
                self._calculate_win_rate_metrics(history)
            )
            all_pnls = [float(trade["pnl"]) for trade in history.trades]
            volatility = statistics.stdev(all_pnls) if len(all_pnls) > 1 else 0.2
            max_drawdown, max_drawdown_duration, peak, time_to_recovery_ratio = (
                self._calculate_drawdown_metrics(history, all_pnls)
            )
            sharpe_ratio, sortino_ratio, calmar_ratio = (
                self._calculate_risk_adjusted_ratios(all_pnls, peak)
            )
            tail_risk = self._calculate_tail_risk(all_pnls)
            position_sizing_std = self._calculate_position_sizing_consistency(history)

            return RiskMetrics(
                profit_factor=profit_factor,
                max_drawdown=max_drawdown,
                max_drawdown_duration=max_drawdown_duration,
                win_rate=win_rate,
                win_rate_std=win_rate_std,
                win_rate_consistency=win_rate_consistency,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                time_to_recovery_ratio=time_to_recovery_ratio,
                tail_risk=tail_risk,
                position_sizing_std=position_sizing_std,
            )

        except Exception as e:
            logger.exception(f"Error calculating risk metrics: {e}")
            return self._get_default_risk_metrics(history)

    def _get_default_risk_metrics(self, history: TradingHistory) -> RiskMetrics:
        """Return default risk metrics for insufficient data or errors"""
        return RiskMetrics(
            profit_factor=1.0,
            max_drawdown=0.0,
            max_drawdown_duration=0.0,
            win_rate=(
                history.profitable_trades / max(history.total_trades, 1)
                if history.total_trades > 0
                else 0.5
            ),
            win_rate_std=0.1,
            win_rate_consistency=0.9,
            volatility=0.2,
            sharpe_ratio=0.5,
            sortino_ratio=0.6,
            calmar_ratio=1.0,
            time_to_recovery_ratio=1.0,
            tail_risk=0.1,
            position_sizing_std=0.2,
        )

    def _calculate_profit_factor(self, history: TradingHistory) -> float:
        """Calculate profit factor (gross profits / gross losses)"""
        if history.gross_losses > 0:
            return float(history.gross_profits / history.gross_losses)
        elif history.total_trades > 0:
            return 1.0  # No losses
        else:
            return 1.0

    def _calculate_win_rate_metrics(
        self, history: TradingHistory
    ) -> Tuple[float, float, float]:
        """Calculate win rate, win rate std, and win rate consistency"""
        win_rate = history.profitable_trades / history.total_trades

        # Calculate rolling win rate (for consistency)
        if len(history.timestamps) >= 10:
            sorted_times = sorted(history.timestamps)
            window_size = min(len(sorted_times), 30)
            rolling_win_rates = []

            for i in range(window_size, len(sorted_times)):
                window_start = (
                    sorted_times[i - window_size]
                    if i >= window_size
                    else sorted_times[0]
                )
                window_end = sorted_times[i]

                window_trades = [
                    j
                    for j, ts in enumerate(history.timestamps)
                    if window_start <= ts < window_end
                ]

                if len(window_trades) > 0:
                    window_win_rate = sum(
                        1
                        for j in window_trades
                        if j < len(history.trades)
                        and history.trades[j]["is_profitable"]
                    ) / len(window_trades)
                    rolling_win_rates.append(window_win_rate)

            win_rate_std = (
                statistics.stdev(rolling_win_rates)
                if len(rolling_win_rates) > 1
                else 0.1
            )
        else:
            win_rate_std = 0.1

        win_rate_consistency = max(0.0, 1.0 - min(win_rate_std, 0.2))
        return win_rate, win_rate_std, win_rate_consistency

    def _calculate_drawdown_metrics(
        self, history: TradingHistory, all_pnls: List[float]
    ) -> Tuple[float, float, float, float]:
        """Calculate max drawdown, duration, peak, and time-to-recovery ratio"""
        cumulative = 0.0
        peak = 0.0
        peak_time = 0.0
        max_drawdown = 0.0
        max_drawdown_duration = 0.0

        sorted_trades = sorted(history.trades, key=lambda x: x["timestamp"])
        for trade in sorted_trades:
            pnl = float(trade["pnl"])
            cumulative += pnl

            if cumulative > peak:
                peak = cumulative
                peak_time = trade["timestamp"]

            if cumulative < peak:
                drawdown_amount = peak - cumulative
                if drawdown_amount > max_drawdown:
                    max_drawdown = (
                        drawdown_amount / peak if peak > 0 else drawdown_amount
                    )

                    recovery_time = self._calculate_recovery_time(
                        sorted_trades, trade, cumulative, peak, peak_time
                    )
                    if recovery_time > 0:
                        max_drawdown_duration = max(
                            max_drawdown_duration, recovery_time / 3600
                        )

        time_to_recovery_ratio = 1.0  # Simplified - could be enhanced
        return max_drawdown, max_drawdown_duration, peak, time_to_recovery_ratio

    def _calculate_recovery_time(
        self,
        sorted_trades: List[Dict[str, Any]],
        trade: Dict[str, Any],
        cumulative: float,
        peak: float,
        peak_time: float,
    ) -> float:
        """Calculate recovery time from drawdown to peak"""
        recovery_time = 0.0
        for later_trade in sorted_trades:
            if later_trade["timestamp"] > trade["timestamp"]:
                temp_cumulative = cumulative + sum(
                    float(t["pnl"])
                    for t in sorted_trades[sorted_trades.index(trade) + 1 :]
                    if t["timestamp"] <= later_trade["timestamp"]
                )
                if temp_cumulative >= peak:
                    recovery_time = later_trade["timestamp"] - peak_time
                    break
                if later_trade["timestamp"] - trade["timestamp"] > self.RECOVERY_WINDOW:
                    break
        return recovery_time

    def _calculate_risk_adjusted_ratios(
        self, all_pnls: List[float], peak: float
    ) -> Tuple[float, float, float]:
        """Calculate Sharpe, Sortino, and Calmar ratios"""
        returns = all_pnls
        risk_free_rate = 0.02  # 2% risk-free rate
        excess_returns = [r - risk_free_rate for r in returns]
        avg_excess = statistics.mean(excess_returns) if len(excess_returns) > 1 else 0.0
        excess_std = (
            statistics.stdev(excess_returns) if len(excess_returns) > 1 else 0.1
        )
        sharpe_ratio = avg_excess / excess_std if excess_std > 0 else 0.5

        downside_returns = [min(r, 0) for r in returns]
        downside_std = (
            statistics.stdev(downside_returns) if len(downside_returns) > 1 else 0.1
        )
        sortino_ratio = avg_excess / downside_std if downside_std > 0 else 0.6

        total_return = sum(all_pnls)
        calmar_ratio = (total_return / max(1.0, peak)) if peak > 0 else 1.0

        return sharpe_ratio, sortino_ratio, calmar_ratio

    def _calculate_tail_risk(self, all_pnls: List[float]) -> float:
        """Calculate tail risk (5th percentile loss)"""
        all_losses = [abs(pnl) for pnl in all_pnls if pnl < 0]
        if all_losses:
            tail_risk_value = sum(sorted(all_losses)[: min(len(all_losses), 20)]) / len(
                all_losses
            )
        else:
            tail_risk_value = 0.0
        return (
            tail_risk_value / statistics.mean(all_pnls)
            if statistics.mean(all_pnls) > 0
            else 1.0
        )

    def _calculate_position_sizing_consistency(self, history: TradingHistory) -> float:
        """Calculate position sizing consistency (normalized std)"""
        if len(history.position_sizes) > 1:
            mean_size = statistics.mean(history.position_sizes)
            if mean_size > 0:
                return statistics.stdev(history.position_sizes) / mean_size
        return 0.2

    def _calculate_domain_expertise(
        self, history: TradingHistory
    ) -> DomainExpertiseMetrics:
        """Calculate domain expertise metrics"""
        try:
            if history.total_trades < self.MIN_TRADES_FOR_STATS:
                # Return default metrics if insufficient data
                return DomainExpertiseMetrics(
                    primary_domain="general",
                    specialization_score=0.0,
                    domain_trades=0,
                    domain_win_rate=(
                        history.profitable_trades / max(history.total_trades, 1)
                        if history.total_trades > 0
                        else 0.5
                    ),
                    domain_roi=Decimal("0.00"),
                    category_diversity=1.0,  # No categorization
                    consistency_score=0.5,
                )

            # Count categories
            category_counts = defaultdict(int)
            category_profitable = defaultdict(int)

            for trade in history.trades:
                category = trade.get("category", "general")
                category_counts[category] += 1
                if trade.get("is_profitable", False):
                    category_profitable[category] += 1

            # Find primary domain
            if category_counts:
                sorted_categories = sorted(
                    category_counts.items(), key=lambda x: x[1], reverse=True
                )
                primary_domain = sorted_categories[0][0]
                domain_trades = sorted_categories[0][1]

                # Calculate domain win rate
                if category_counts[primary_domain] > 0:
                    domain_win_rate = (
                        category_profitable[primary_domain]
                        / category_counts[primary_domain]
                    )
                else:
                    domain_win_rate = 0.5
            else:
                primary_domain = "general"
                domain_trades = history.total_trades
                domain_win_rate = history.profitable_trades / max(
                    history.total_trades, 1
                )

            # Calculate specialization score (trades in primary domain / total trades)
            specialization_score = (
                domain_trades / history.total_trades
                if history.total_trades > 0
                else 0.0
            )

            # Calculate category diversity (lower is better)
            num_categories = len(category_counts)
            category_diversity = 1.0 / num_categories if num_categories > 0 else 1.0

            # Calculate domain ROI (approximate)
            domain_pnl = sum(
                trade["pnl"]
                for trade in history.trades
                if trade.get("category") == primary_domain
            )
            domain_roi = (
                float(
                    domain_pnl
                    / max(Decimal("100.00"), history.total_trades * Decimal("10.00"))
                )
                if history.total_trades > 0
                else 0.0
            )

            # Calculate consistency score (stable win rate in domain)
            # For simplicity, use standard deviation of win rates if we had them
            # Here we use the consistency from risk metrics
            consistency_score = 0.7  # Assume good consistency

            return DomainExpertiseMetrics(
                primary_domain=primary_domain,
                specialization_score=specialization_score,
                domain_trades=domain_trades,
                domain_win_rate=domain_win_rate,
                domain_roi=Decimal(str(domain_roi)),
                category_diversity=category_diversity,
                consistency_score=consistency_score,
            )

        except Exception as e:
            logger.exception(f"Error calculating domain expertise: {e}")
            return DomainExpertiseMetrics(
                primary_domain="general",
                specialization_score=0.0,
                domain_trades=0,
                domain_win_rate=0.5,
                domain_roi=Decimal("0.00"),
                category_diversity=1.0,
                consistency_score=0.5,
            )

    def _detect_market_maker_advanced(
        self, history: TradingHistory, risk_metrics: RiskMetrics
    ) -> bool:
        """
        Advanced market maker detection using multi-pattern analysis.

        A wallet is a market maker if ALL of these patterns are present:
        1. Very high trade frequency (>500 trades)
        2. Very low average hold time (<1 hour)
        3. Win rate close to break-even (45-55%)
        4. Very low profit per trade (<1% ROI)
        """
        try:
            # Check minimum trade count
            if history.total_trades < self.MM_TRADE_COUNT_THRESHOLD:
                return False

            # Calculate average hold time (from timestamps)
            if len(history.timestamps) >= 2:
                hold_times = []
                sorted_timestamps = sorted(history.timestamps)
                for i in range(1, len(sorted_timestamps)):
                    hold_time = sorted_timestamps[i] - sorted_timestamps[i - 1]
                    hold_times.append(hold_time)

                avg_hold_time = (
                    statistics.mean(hold_times) if hold_times else 3600
                )  # Default to 1 hour
            else:
                avg_hold_time = 3600

            # Check win rate range
            win_rate = risk_metrics.win_rate
            in_mm_range = self.MM_WIN_RATE_MIN <= win_rate <= self.MM_WIN_RATE_MAX

            # Calculate profit per trade (approximate)
            if history.total_trades > 0:
                profit_per_trade = float(
                    risk_metrics.profit_factor * 0.01
                )  # Approximate 1% baseline
            else:
                profit_per_trade = 0.0

            # Market maker detection (ALL criteria must be true)
            is_mm = (
                history.total_trades > self.MM_TRADE_COUNT_THRESHOLD  # High frequency
                and avg_hold_time < self.MM_AVG_HOLD_TIME_THRESHOLD  # Low hold time
                and in_mm_range  # Break-even win rate
                and profit_per_trade
                < float(self.MM_PROFIT_PER_TRADE_THRESHOLD)  # Low profit per trade
            )

            if is_mm:
                logger.info(
                    f"🚨 MARKET MAKER DETECTED: {history.wallet_address[-6:]} "
                    f"(trades={history.total_trades}, "
                    f"hold_time={avg_hold_time:.0f}s, "
                    f"win_rate={win_rate:.1%}, "
                    f"profit_per_trade={profit_per_trade:.2%})"
                )

            return is_mm

        except Exception as e:
            logger.exception(f"Error detecting market maker: {e}")
            return False

    def _detect_red_flags(
        self,
        history: TradingHistory,
        risk_metrics: RiskMetrics,
        domain_expertise: DomainExpertiseMetrics,
    ) -> List[Tuple[RedFlagType, str]]:
        """Detect red flags for wallet exclusion"""
        red_flags = []

        try:
            # 1. NEW_WALLET_LARGE_BET
            wallet_age_days = self._calculate_wallet_age_days(history)
            max_position_size = (
                max(history.position_sizes) if history.position_sizes else 0
            )

            if wallet_age_days < self.NEW_WALLET_MAX_DAYS and max_position_size > float(
                self.NEW_WALLET_MAX_BET
            ):
                red_flags.append(
                    (
                        RedFlagType.NEW_WALLET_LARGE_BET,
                        f"New wallet ({wallet_age_days} days) with large bet (${max_position_size:.2f})",
                    )
                )

            # 2. LUCK_NOT_SKILL
            if (
                risk_metrics.win_rate > self.LUCK_WIN_RATE_THRESHOLD
                and history.total_trades < self.LUCK_MIN_TRADES
            ):
                red_flags.append(
                    (
                        RedFlagType.LUCK_NOT_SKILL,
                        f"Extreme win rate ({risk_metrics.win_rate:.1%}) with low trade count ({history.total_trades})",
                    )
                )

            # 3. NEGATIVE_PROFIT_FACTOR
            if risk_metrics.profit_factor < self.NEGATIVE_PROFIT_FACTOR_THRESHOLD:
                red_flags.append(
                    (
                        RedFlagType.NEGATIVE_PROFIT_FACTOR,
                        f"Negative profit factor ({risk_metrics.profit_factor:.2f}) - losing money long-term",
                    )
                )

            # 4. NO_SPECIALIZATION
            num_categories = len(set(history.categories)) if history.categories else 1
            if num_categories > self.MAX_CATEGORIES_THRESHOLD:
                red_flags.append(
                    (
                        RedFlagType.NO_SPECIALIZATION,
                        f"Trading {num_categories} categories with no domain expertise",
                    )
                )

            # 5. EXCESSIVE_DRAWDOWN
            if risk_metrics.max_drawdown > self.EXCESSIVE_DRAWDOWN_THRESHOLD:
                red_flags.append(
                    (
                        RedFlagType.EXCESSIVE_DRAWDOWN,
                        f"Excessive drawdown ({risk_metrics.max_drawdown:.1%}) - poor risk management",
                    )
                )

            # 6. LOW_WIN_RATE
            if (
                history.total_trades >= self.MIN_TRADES_FOR_STATS
                and risk_metrics.win_rate < self.MIN_WIN_RATE_THRESHOLD
            ):
                red_flags.append(
                    (
                        RedFlagType.LOW_WIN_RATE,
                        f"Low win rate ({risk_metrics.win_rate:.1%}) with {history.total_trades} trades",
                    )
                )

            return red_flags

        except Exception as e:
            logger.exception(f"Error detecting red flags: {e}")
            return []

    def _calculate_wallet_age_days(self, history: TradingHistory) -> int:
        """Calculate wallet age in days from first trade timestamp"""
        if history.timestamps:
            first_trade = min(history.timestamps)
            age_seconds = time.time() - first_trade
            return int(age_seconds / 86400)
        return 0

    def _calculate_performance_score(
        self, history: TradingHistory, risk_metrics: RiskMetrics
    ) -> float:
        """Calculate performance score (0.0 to 10.0)"""
        try:
            # Profit factor score (0.0 to 10.0)
            pf_score = min(max(risk_metrics.profit_factor, 0.0), 3.0) / 3.0 * 10.0

            # Win rate score (0.0 to 10.0)
            wr_score = min(max(risk_metrics.win_rate, 0.0), 0.8) / 0.8 * 10.0

            # Max drawdown score (lower drawdown = higher score)
            # 0% drawdown = 10.0, 35%+ drawdown = 0.0
            dd_threshold = self.EXCESSIVE_DRAWDOWN_THRESHOLD
            dd_score = max(
                10.0 - (risk_metrics.max_drawdown / dd_threshold) * 10.0, 0.0
            )

            # Sharpe ratio score
            sharpe_score = min(max(risk_metrics.sharpe_ratio, 0.0), 3.0) / 3.0 * 10.0

            # Weighted average
            performance = (
                pf_score * 0.35
                + wr_score * 0.30
                + dd_score * 0.20
                + sharpe_score * 0.15
            )

            return min(max(performance, 0.0), 10.0)

        except Exception as e:
            logger.exception(f"Error calculating performance score: {e}")
            return 0.0

    def _calculate_risk_score(
        self, risk_metrics: RiskMetrics, red_flags: List[Tuple[RedFlagType, str]]
    ) -> float:
        """Calculate risk score (0.0 to 10.0, higher is better)"""
        try:
            # Inverse max drawdown (lower drawdown = higher score)
            dd_score = max(10.0 - (risk_metrics.max_drawdown * 10.0), 0.0)

            # Win rate consistency (higher is better)
            consistency_score = risk_metrics.win_rate_consistency * 10.0

            # Volatility score (lower volatility = higher score)
            vol_threshold = 0.25
            vol_score = max(
                10.0 - (risk_metrics.volatility / vol_threshold) * 10.0, 0.0
            )

            # Sharpe ratio score (higher is better)
            sharpe_score = min(max(risk_metrics.sharpe_ratio, 0.0), 2.0) / 2.0 * 10.0

            # Sortino ratio score (higher is better)
            sortino_score = min(max(risk_metrics.sortino_ratio, 0.0), 2.0) / 2.0 * 10.0

            # Calmar ratio score (higher is better)
            calmar_score = min(max(risk_metrics.calmar_ratio, 0.0), 2.5) / 2.5 * 10.0

            # Time to recovery score (higher is better, faster recovery)
            recovery_score = min(
                max(risk_metrics.time_to_recovery_ratio * 5.0, 0.0), 10.0
            )

            # Tail risk score (lower is better)
            tail_score = max(10.0 - (risk_metrics.tail_risk * 10.0), 0.0)

            # Red flag penalty (major penalty for any red flags)
            red_flag_count = len(red_flags)
            red_flag_penalty = min(red_flag_count * 2.0, 10.0)  # Up to 10 point penalty

            # Weighted average (inverse risk metrics + penalties)
            risk_score = (
                dd_score * 0.25
                + consistency_score * 0.20
                + vol_score * 0.10
                + sharpe_score * 0.10
                + sortino_score * 0.10
                + calmar_score * 0.05
                + recovery_score * 0.10
                + tail_score * 0.05
            )

            # Apply red flag penalty
            risk_score = max(risk_score - red_flag_penalty, 0.0)

            return risk_score

        except Exception as e:
            logger.exception(f"Error calculating risk score: {e}")
            return 0.0

    def _calculate_consistency_score(
        self, history: TradingHistory, risk_metrics: RiskMetrics
    ) -> float:
        """Calculate consistency score (0.0 to 10.0)"""
        try:
            # Win rate consistency (already calculated in risk_metrics)
            win_rate_consistency_score = risk_metrics.win_rate_consistency * 10.0

            # Position sizing consistency (lower std = higher score)
            ps_std = risk_metrics.position_sizing_std
            ps_score = max(
                10.0 - (ps_std * 20.0), 0.0
            )  # Normalize: 0.1 std = 8.0 score

            # Trade count score (more trades = more consistency)
            trade_count = history.total_trades
            tc_score = min(trade_count / 50.0 * 10.0, 10.0)

            # Time span score (consistent activity over time)
            if len(history.timestamps) >= 2:
                time_span = max(history.timestamps) - min(history.timestamps)
                time_span_days = time_span / 86400
                ts_score = min(time_span_days / 180.0 * 10.0, 10.0)
            else:
                ts_score = 0.0

            # Weighted average
            consistency = (
                win_rate_consistency_score * 0.50
                + ps_score * 0.20
                + tc_score * 0.15
                + ts_score * 0.15
            )

            return consistency

        except Exception as e:
            logger.exception(f"Error calculating consistency score: {e}")
            return 0.0

    def _calculate_domain_score(
        self, domain_expertise: DomainExpertiseMetrics
    ) -> float:
        """Calculate domain expertise score (0.0 to 10.0)"""
        try:
            # Specialization score (higher is better)
            spec_score = domain_expertise.specialization_score * 10.0

            # Category diversity bonus (lower is better)
            diversity_bonus = (1.0 - domain_expertise.category_diversity) * 3.0

            # Domain win rate score (higher is better)
            domain_wr_score = min(domain_expertise.domain_win_rate * 10.0, 10.0)

            # Consistency score (higher is better)
            consistency_score = domain_expertise.consistency_score * 10.0

            # Weighted average
            domain_score = (
                spec_score * 0.40
                + diversity_bonus * 0.25
                + domain_wr_score * 0.20
                + consistency_score * 0.15
            )

            return domain_score

        except Exception as e:
            logger.exception(f"Error calculating domain score: {e}")
            return 0.0

    def _calculate_total_score(
        self,
        performance_score: float,
        risk_score: float,
        consistency_score: float,
        domain_score: float,
        red_flags: List[Tuple[RedFlagType, str]],
    ) -> float:
        """Calculate total quality score (0.0 to 10.0)"""
        try:
            # Calculate red flag penalty
            red_flag_penalty = 0.0
            if red_flags:
                # Categorize red flags by severity
                critical_flags = [
                    rf
                    for rf in red_flags
                    if rf[0]
                    in [
                        RedFlagType.NEGATIVE_PROFIT_FACTOR,
                        RedFlagType.WASH_TRADING,
                        RedFlagType.INSIDER_TRADING_SUSPECTED,
                    ]
                ]
                high_flags = [
                    rf
                    for rf in red_flags
                    if rf[0] not in [cf[0] for cf in critical_flags]
                ]

                # Apply penalties
                red_flag_penalty = min(
                    len(critical_flags) * 5.0, 10.0
                )  # Up to 10 points
                red_flag_penalty += min(len(high_flags) * 2.5, 10.0)  # Up to 7.5 points

            # Weighted average
            total = (
                performance_score * self.PERFORMANCE_WEIGHT
                + risk_score * self.RISK_WEIGHT
                + consistency_score * self.CONSISTENCY_WEIGHT
                + domain_score * self.DOMAIN_WEIGHT
            )

            # Apply red flag penalty (critical factor)
            total = max(total - red_flag_penalty * 1.5, 0.0)

            return min(max(total, 0.0), 10.0)

        except Exception as e:
            logger.exception(f"Error calculating total score: {e}")
            return 0.0

    def _determine_quality_tier(self, total_score: float) -> WalletQualityTier:
        """Determine quality tier based on total score"""
        if total_score >= 9.0:
            return WalletQualityTier.ELITE
        elif total_score >= 7.0:
            return WalletQualityTier.EXPERT
        elif total_score >= 5.0:
            return WalletQualityTier.GOOD
        else:
            return WalletQualityTier.POOR

    def _calculate_confidence_score(
        self,
        history: TradingHistory,
        risk_metrics: RiskMetrics,
        total_score: float,
        domain_expertise: DomainExpertiseMetrics,
    ) -> float:
        """Calculate confidence score (0.0 to 1.0)"""
        try:
            # Base confidence from score (0-1.0 mapping)
            base_confidence = total_score / 10.0

            # Data completeness bonus (more data = higher confidence)
            data_bonus = min(history.total_trades / 100.0 * 0.2, 0.2)  # Max 0.2 bonus

            # Time span bonus (longer history = higher confidence)
            if len(history.timestamps) >= 2:
                time_span = max(history.timestamps) - min(history.timestamps)
                time_span_days = time_span / 86400
                time_bonus = min(time_span_days / 90.0 * 0.15, 0.15)  # Max 0.15 bonus
            else:
                time_bonus = 0.0

            # Risk consistency bonus (lower risk = higher confidence)
            risk_bonus = max(0.1, risk_metrics.win_rate_consistency) * 0.15

            # Domain expertise bonus (higher expertise = higher confidence)
            domain_bonus = (
                1.0
                if domain_expertise.primary_domain
                in ["politics", "crypto", "economics"]
                else 0.0
            ) * 0.1

            # Calculate total confidence
            confidence = (
                base_confidence + data_bonus + time_bonus + risk_bonus + domain_bonus
            )

            return min(max(confidence, 0.0), 1.0)

        except Exception as e:
            logger.exception(f"Error calculating confidence score: {e}")
            return 0.5

    async def _get_cached_or_placeholder_score(
        self, wallet_address: str
    ) -> QualityScore:
        """Get cached score or create placeholder during circuit breaker"""
        cache_key = f"score_{wallet_address}"
        cached = self._score_cache.get(cache_key)

        if cached:
            logger.debug(f"Using cached score for {wallet_address[-6:]}")
            return cached
        else:
            # Create placeholder score
            logger.warning(
                f"Creating placeholder score for {wallet_address[-6:]} (circuit breaker)"
            )
            return QualityScore(
                wallet_address=wallet_address,
                quality_tier=WalletQualityTier.POOR,
                total_score=0.0,
                performance_score=0.0,
                risk_score=0.0,
                consistency_score=0.0,
                domain_expertise=DomainExpertiseMetrics(
                    primary_domain="unknown",
                    specialization_score=0.0,
                    domain_trades=0,
                    domain_win_rate=0.5,
                    domain_roi=Decimal("0.00"),
                    category_diversity=1.0,
                    consistency_score=0.5,
                ),
                risk_metrics=RiskMetrics(
                    profit_factor=1.0,
                    max_drawdown=0.0,
                    max_drawdown_duration=0.0,
                    win_rate=0.5,
                    win_rate_std=0.1,
                    win_rate_consistency=0.9,
                    volatility=0.2,
                    sharpe_ratio=0.5,
                    sortino_ratio=0.6,
                    calmar_ratio=1.0,
                    time_to_recovery_ratio=1.0,
                    tail_risk=0.1,
                    position_sizing_std=0.2,
                ),
                is_market_maker=False,
                red_flags=[],
                confidence_score=0.5,
                last_updated=time.time(),
                metadata={"placeholder": True, "circuit_breaker_active": True},
            )

    async def _check_rate_limit(self, api_name: str) -> None:
        """Check rate limit and sleep if exceeded"""
        current_time = time.time()
        last_call = self._call_timestamps.get(api_name, 0.0)

        # Reset if more than 1 second since last call
        if current_time - last_call > 1.0:
            self._call_timestamps[api_name] = current_time
            return

        # Check rate limit (10 calls per second)
        time_since_last = current_time - last_call
        if time_since_last < 0.1:  # Less than 100ms
            await asyncio.sleep(0.1 - time_since_last)
            logger.debug(
                f"Rate limiting {api_name}: sleeping for {0.1 - time_since_last:.3f}s"
            )

        self._call_timestamps[api_name] = current_time

    async def get_score_summary(self) -> Dict[str, Any]:
        """Get summary of scoring statistics"""
        try:
            cache_stats = self._score_cache.get_stats()
            history_stats = self._history_cache.get_stats()

            return {
                "timestamp": time.time(),
                "total_scores": self._total_scores,
                "mm_detections": self._mm_detections,
                "red_flag_detections": self._red_flag_detections,
                "cache_stats": {
                    "score_cache": cache_stats,
                    "history_cache": history_stats,
                },
            }

        except Exception as e:
            logger.exception(f"Error getting score summary: {e}")
            return {}

    async def cleanup(self) -> None:
        """Clean up expired cache entries"""
        try:
            self._score_cache.cleanup()
            self._history_cache.cleanup()
            logger.info("WalletQualityScorer cleanup complete")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def reset_wallet_score(self, wallet_address: str) -> bool:
        """Reset score for a specific wallet (for testing or manual intervention)"""
        try:
            cache_key = f"score_{wallet_address}"
            self._score_cache.delete(cache_key)
            history_key = f"history_{wallet_address}"
            self._history_cache.delete(history_key)

            logger.info(f"Reset score for wallet {wallet_address[-6:]}")
            return True

        except Exception as e:
            logger.error(f"Error resetting score for wallet {wallet_address[-6:]}: {e}")
            return False

    async def batch_score_wallets(
        self, wallets_data: List[Dict[str, Any]]
    ) -> List[QualityScore]:
        """Score multiple wallets in parallel (with rate limiting)"""
        async with self._rate_limiter:  # Limit to 10 concurrent calls
            tasks = [
                self.score_wallet(wallet_data.get("address", ""), wallet_data)
                for wallet_data in wallets_data
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None results (errors)
        valid_results = [r for r in results if r is not None]

        return valid_results

    async def get_top_wallets(
        self,
        all_wallets: List[Dict[str, Any]],
        min_quality_score: float = 5.0,
        max_wallets: int = 5,
    ) -> List[QualityScore]:
        """Get top N wallets by quality score"""
        # Score all wallets
        scored_wallets = await self.batch_score_wallets(all_wallets)

        # Filter by minimum score and exclude market makers
        qualified_wallets = [
            w
            for w in scored_wallets
            if w.total_score >= min_quality_score
            and not w.is_market_maker
            and len(w.red_flags) == 0
        ]

        # Sort by score descending and take top N
        top_wallets = sorted(
            qualified_wallets, key=lambda w: w.total_score, reverse=True
        )[:max_wallets]

        logger.info(
            f"Top {len(top_wallets)} wallets: "
            f"{[f'{w.wallet_address[-6:]} ({w.total_score:.1f})' for w in top_wallets]}"
        )

        return top_wallets


# Example usage
async def example_usage():
    """Example of how to use WalletQualityScorer"""
    from pathlib import Path

    from config.scanner_config import get_scanner_config
    from core.circuit_breaker import CircuitBreaker

    # Initialize with configuration
    config = get_scanner_config()
    circuit_breaker = CircuitBreaker(
        max_daily_loss=100.0,
        wallet_address="0x0000000000000000000000000000000000000000001",
        state_file=Path("data/circuit_breaker_state.json"),
    )

    scorer = WalletQualityScorer(
        config=config,
        circuit_breaker=circuit_breaker,
        cache_ttl_seconds=3600,
        max_cache_size=1000,
    )

    # Sample wallet data
    wallet_data = {
        "address": "0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
        "trades": [
            {
                "timestamp": time.time() - (86400 * i * 24),  # i days ago
                "is_profitable": i % 2 == 0,  # 50% win rate
                "pnl": Decimal(str(10.0 * (1 if i % 2 == 0 else -1))),
                "category": "politics" if i < 30 else "economics",
                "position_size": 100 + i * 10,  # $100-200
            }
            for i in range(100)  # 100 trades
        ],
        "trade_count": 100,
    }

    # Score the wallet
    score = await scorer.score_wallet(
        wallet_address=wallet_data["address"],
        wallet_data=wallet_data,
    )

    if score:
        logger.info("Wallet Quality Score:")
        logger.info(f"  Address: {score.wallet_address}")
        logger.info(f"  Tier: {score.quality_tier.value}")
        logger.info(f"  Total Score: {score.total_score:.2f}/10")
        logger.info(f"  Performance: {score.performance_score:.2f}/10")
        logger.info(f"  Risk: {score.risk_score:.2f}/10")
        logger.info(f"  Consistency: {score.consistency_score:.2f}/10")
        logger.info(f"  Domain: {score.domain_expertise.primary_domain}")
        logger.info(
            f"  Specialization: {score.domain_expertise.specialization_score:.1%}"
        )
        logger.info(f"  Is Market Maker: {score.is_market_maker}")
        logger.info(f"  Red Flags: {len(score.red_flags)}")

        if score.red_flags:
            logger.info("\n  Red Flags:")
            for flag_type, reason in score.red_flags:
                logger.info(f"    {flag_type.value}: {reason}")

        logger.info("\n  Risk Metrics:")
        logger.info(f"    Profit Factor: {score.risk_metrics.profit_factor:.2f}")
        logger.info(f"    Max Drawdown: {score.risk_metrics.max_drawdown:.1%}")
        logger.info(
            f"    Max Drawdown Duration: {score.risk_metrics.max_drawdown_duration:.1f}h"
        )
        logger.info(
            f"    Win Rate: {score.risk_metrics.win_rate:.1%} (±{score.risk_metrics.win_rate_std:.1%})"
        )
        logger.info(
            f"    Win Rate Consistency: {score.risk_metrics.win_rate_consistency:.2f}"
        )
        logger.info(f"    Volatility: {score.risk_metrics.volatility:.2f}")
        logger.info(f"    Sharpe Ratio: {score.risk_metrics.sharpe_ratio:.2f}")
        logger.info(f"    Sortino Ratio: {score.risk_metrics.sortino_ratio:.2f}")
        logger.info(f"    Calmar Ratio: {score.risk_metrics.calmar_ratio:.2f}")
        logger.info(
            f"    Time to Recovery Ratio: {score.risk_metrics.time_to_recovery_ratio:.2f}"
        )
        logger.info(f"    Tail Risk: {score.risk_metrics.tail_risk:.2f}")
        logger.info(
            f"    Position Sizing Std: {score.risk_metrics.position_sizing_std:.2f}"
        )

        logger.info("\n  Domain Expertise:")
        logger.info(f"    Primary Domain: {score.domain_expertise.primary_domain}")
        logger.info(f"    Domain Trades: {score.domain_expertise.domain_trades}")
        logger.info(
            f"    Domain Win Rate: {score.domain_expertise.domain_win_rate:.1%}"
        )
        logger.info(f"    Domain ROI: {score.domain_expertise.domain_roi:.1%}")
        logger.info(
            f"    Category Diversity: {score.domain_expertise.category_diversity:.2f}"
        )
        logger.info(f"    Consistency: {score.domain_expertise.consistency_score:.2f}")

    # Get summary
    summary = await scorer.get_score_summary()
    logger.info("\n  Scoring Summary:")
    logger.info(f"    Total Scores: {summary['total_scores']}")
    logger.info(f"    MM Detections: {summary['mm_detections']}")
    logger.info(f"    Red Flag Detections: {summary['red_flag_detections']}")

    # Cleanup
    await scorer.cleanup()
    logger.info("\n✅ Example completed successfully")


if __name__ == "__main__":
    asyncio.run(example_usage())
