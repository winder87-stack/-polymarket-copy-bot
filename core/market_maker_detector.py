"""
Market Maker Detection System
============================

Advanced behavioral analysis system for identifying market maker wallets
among Polymarket traders. Uses multiple statistical and pattern-based
techniques to classify trading behavior.

Key Features:
- Multi-dimensional behavior scoring
- Adaptive classification thresholds
- Cross-market correlation analysis
- Real-time pattern recognition
- False positive mitigation strategies
"""

import logging
import math
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np

if TYPE_CHECKING:
    pass

from core.wallet_behavior_store import WalletBehaviorStore
from utils.helpers import BoundedCache, normalize_address
from utils.time_utils import get_current_time_utc

logger = logging.getLogger(__name__)


class MarketMakerDetector:
    """
    Advanced market maker detection system using behavioral pattern analysis.

    Analyzes wallet trading patterns to distinguish between:
    - Market Makers: High-frequency, balanced, multi-market traders
    - Directional Traders: Lower frequency, directional bias traders
    - Noise: Low activity, inconsistent behavior
    """

    def __init__(self, settings: Any) -> None:
        self.settings = settings

        # Initialize storage system
        self.storage = WalletBehaviorStore()

        # Analysis parameters
        self.analysis_window_days = 7  # Days to analyze for classification
        self.min_trades_for_analysis = 10  # Minimum trades for reliable analysis
        self.classification_threshold = 0.7  # Market maker probability threshold

        # Behavior metrics tracking - bounded caches with proper cleanup
        self.wallet_behaviors = BoundedCache(
            max_size=100,  # Reasonable limit for tracking wallets
            ttl_seconds=3600,  # 1 hour TTL
            memory_threshold_mb=10.0,
            cleanup_interval_seconds=300,  # Cleanup every 5 minutes
        )
        self.market_correlations = BoundedCache(
            max_size=2500,  # Up to 50 wallets × 50 correlations
            ttl_seconds=3600,  # 1 hour TTL
            memory_threshold_mb=20.0,
            cleanup_interval_seconds=300,
        )

        # Classification thresholds (configurable)
        self.thresholds = {
            "high_frequency_threshold": 5.0,  # Trades per hour
            "balance_ratio_threshold": 0.3,  # Buy/sell balance deviation
            "holding_time_threshold": 3600,  # Max holding time in seconds (1 hour)
            "spread_tightness_threshold": 0.02,  # Max spread as fraction
            "multi_market_threshold": 3,  # Min markets traded in
            "consistency_threshold": 0.8,  # Volume consistency score
        }

        # Performance optimization
        self.cache_ttl = 300  # 5 minutes
        self.behavior_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}

        # Load existing data into memory for fast access
        self._load_existing_data()

        logger.info("🎯 Market maker detector initialized")

    def _load_existing_data(self) -> None:
        """Load existing wallet classifications and behavior history"""
        try:
            # Load classifications from storage
            self.wallet_behaviors = self.storage.get_all_classifications()
            logger.info(
                f"📊 Loaded {len(self.wallet_behaviors)} wallet classifications"
            )

            # Behavior history is loaded on-demand from storage
            logger.info("📈 Behavior history will be loaded on-demand from storage")

        except Exception as e:
            logger.error(f"Error loading existing data: {e}", exc_info=True)
            self.wallet_behaviors = {}
            self.market_correlations = {}

    def save_data(self) -> None:
        """Save wallet classifications and behavior data"""
        try:
            # Save all wallet classifications
            saved_count = 0
            behavior_keys = list(self.wallet_behaviors._cache.keys())
            for wallet_address in behavior_keys:
                behavior_data = self.wallet_behaviors.get(wallet_address)
                if behavior_data:
                    success = self.storage.store_wallet_classification(
                        wallet_address, behavior_data
                    )
                    if success:
                        saved_count += 1

            # Behavior history is saved incrementally in _store_behavior_history
            logger.info(
                f"💾 Saved {saved_count}/{len(behavior_keys)} wallet classifications"
            )

        except Exception as e:
            logger.error(f"Error saving data: {e}", exc_info=True)

    async def analyze_wallet_behavior(
        self,
        wallet_address: str,
        trades: List[Dict[str, Any]],
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze wallet behavior and calculate market maker probability score.

        Args:
            wallet_address: Wallet address to analyze
            trades: List of trade transactions
            market_data: Optional market context data

        Returns:
            Comprehensive behavior analysis with classification
        """

        normalized_wallet = normalize_address(wallet_address)

        # Check cache first
        cache_key = f"{normalized_wallet}_{len(trades)}"
        now = time.time()

        if cache_key in self.behavior_cache:
            cached_data, cache_time = self.behavior_cache[cache_key]
            if now - cache_time < self.cache_ttl:
                return cached_data

        # Filter trades for analysis window
        analysis_cutoff = get_current_time_utc() - timedelta(
            days=self.analysis_window_days
        )
        recent_trades = [
            trade
            for trade in trades
            if datetime.fromisoformat(
                trade.get("timestamp", datetime.now().isoformat())
            )
            > analysis_cutoff
        ]

        if len(recent_trades) < self.min_trades_for_analysis:
            # Insufficient data for reliable analysis
            analysis = {
                "wallet_address": normalized_wallet,
                "analysis_timestamp": get_current_time_utc().isoformat(),
                "classification": "insufficient_data",
                "market_maker_probability": 0.0,
                "confidence_score": 0.0,
                "trade_count": len(recent_trades),
                "analysis_window_days": self.analysis_window_days,
                "min_trades_required": self.min_trades_for_analysis,
                "metrics": {},
                "recommendation": "Need more trading data for reliable classification",
            }

            self.behavior_cache[cache_key] = (analysis, now)
            return analysis

        # Calculate behavioral metrics
        metrics = await self._calculate_behavioral_metrics(recent_trades, market_data)

        # Calculate market maker probability
        mm_probability = self._calculate_market_maker_probability(metrics)

        # Determine classification
        classification = self._classify_wallet(mm_probability, metrics)

        # Calculate confidence score
        confidence = self._calculate_confidence_score(metrics, recent_trades)

        # Generate insights and recommendations
        insights = self._generate_behavioral_insights(metrics, classification)

        analysis = {
            "wallet_address": normalized_wallet,
            "analysis_timestamp": get_current_time_utc().isoformat(),
            "classification": classification,
            "market_maker_probability": round(mm_probability, 4),
            "confidence_score": round(confidence, 4),
            "trade_count": len(recent_trades),
            "analysis_window_days": self.analysis_window_days,
            "metrics": metrics,
            "insights": insights,
            "risk_assessment": self._assess_trading_risks(metrics),
            "performance_comparison": self._compare_to_benchmarks(metrics),
        }

        # Store analysis in behavior history
        self._store_behavior_history(normalized_wallet, analysis)

        # Update wallet behaviors
        cache_key = f"{normalized_wallet}_{len(trades)}"
        self.wallet_behaviors.set(
            cache_key,
            {
                "last_analysis": get_current_time_utc().isoformat(),
                "classification": classification,
                "market_maker_probability": mm_probability,
                "confidence_score": confidence,
                "trade_count": len(recent_trades),
                "metrics_snapshot": metrics,
            },
        )

        # Cache result
        now = time.time()
        self.behavior_cache.set(cache_key, now)

        logger.info(
            f"🎯 Analyzed {normalized_wallet}: {classification} "
            f"(MM: {mm_probability:.2f}, Conf: {confidence:.2f})"
        )

        return analysis

    async def _calculate_behavioral_metrics(
        self, trades: List[Dict[str, Any]], market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculate comprehensive behavioral metrics"""

        metrics = {
            "temporal_metrics": {},
            "directional_metrics": {},
            "position_metrics": {},
            "market_metrics": {},
            "risk_metrics": {},
            "consistency_metrics": {},
        }

        # Sort trades by timestamp
        sorted_trades = sorted(trades, key=lambda x: x.get("timestamp", ""))

        # 1. Temporal Analysis
        metrics["temporal_metrics"] = self._analyze_temporal_patterns(sorted_trades)

        # 2. Directional Analysis
        metrics["directional_metrics"] = self._analyze_directional_patterns(
            sorted_trades
        )

        # 3. Position Analysis
        metrics["position_metrics"] = self._analyze_position_patterns(sorted_trades)

        # 4. Market Analysis
        metrics["market_metrics"] = self._analyze_market_patterns(sorted_trades)

        # 5. Risk Analysis
        metrics["risk_metrics"] = self._analyze_risk_patterns(
            sorted_trades, market_data
        )

        # 6. Consistency Analysis
        metrics["consistency_metrics"] = self._analyze_consistency_patterns(
            sorted_trades
        )

        return metrics

    def _analyze_temporal_patterns(
        self, trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze temporal trading patterns"""

        if not trades:
            return {}

        timestamps = [
            datetime.fromisoformat(
                trade.get("timestamp", get_current_time_utc().isoformat())
            )
            for trade in trades
        ]

        # Calculate time intervals between trades
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i - 1]).total_seconds()
            intervals.append(interval)

        # Trading frequency metrics
        total_duration = (timestamps[-1] - timestamps[0]).total_seconds()
        trades_per_hour = len(trades) / max(total_duration / 3600, 1)

        # Burst trading detection (trades within short timeframes)
        burst_threshold = 300  # 5 minutes
        bursts = 0
        current_burst = 1

        for interval in intervals:
            if interval <= burst_threshold:
                current_burst += 1
            else:
                if current_burst >= 3:  # 3+ trades in burst window
                    bursts += 1
                current_burst = 1

        if current_burst >= 3:
            bursts += 1

        # Session analysis (trading hours)
        hourly_distribution = defaultdict(int)
        for ts in timestamps:
            hour = ts.hour
            hourly_distribution[hour] += 1

        # Calculate entropy of trading hours (uniformity)
        total_hours = sum(hourly_distribution.values())
        hour_entropy = 0
        if total_hours > 0:
            for count in hourly_distribution.values():
                p = count / total_hours
                if p > 0:
                    hour_entropy -= p * math.log2(p)

        max_possible_entropy = math.log2(24)  # 24 hours
        hour_uniformity = (
            hour_entropy / max_possible_entropy if max_possible_entropy > 0 else 0
        )

        return {
            "trades_per_hour": trades_per_hour,
            "avg_interval_seconds": np.mean(intervals) if intervals else 0,
            "median_interval_seconds": np.median(intervals) if intervals else 0,
            "burst_trading_events": bursts,
            "hourly_distribution": dict(hourly_distribution),
            "trading_hour_uniformity": hour_uniformity,
            "trading_span_hours": total_duration / 3600,
            "interval_std_dev": np.std(intervals) if intervals else 0,
        }

    def _analyze_directional_patterns(
        self, trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze buy/sell directional patterns"""

        buy_count = sum(1 for trade in trades if trade.get("side", "").upper() == "BUY")
        sell_count = sum(
            1 for trade in trades if trade.get("side", "").upper() == "SELL"
        )

        total_trades = len(trades)
        buy_ratio = buy_count / total_trades if total_trades > 0 else 0
        sell_ratio = sell_count / total_trades if total_trades > 0 else 0

        # Balance score (how close buy/sell ratio is to 50/50)
        balance_score = (
            1 - abs(buy_ratio - 0.5) * 2
        )  # 0 = completely unbalanced, 1 = perfectly balanced

        # Alternation analysis (buy-sell-buy-sell pattern)
        directions = [trade.get("side", "").upper() for trade in trades]
        alternations = 0
        for i in range(1, len(directions)):
            if directions[i] != directions[i - 1] and directions[i - 1] in [
                "BUY",
                "SELL",
            ]:
                alternations += 1

        alternation_ratio = alternations / max(len(directions) - 1, 1)

        # Directional persistence (how long positions are held in one direction)
        direction_streaks = []
        current_streak = 1
        for i in range(1, len(directions)):
            if directions[i] == directions[i - 1]:
                current_streak += 1
            else:
                direction_streaks.append(current_streak)
                current_streak = 1
        direction_streaks.append(current_streak)

        avg_direction_streak = np.mean(direction_streaks) if direction_streaks else 0

        return {
            "buy_count": buy_count,
            "sell_count": sell_count,
            "buy_ratio": buy_ratio,
            "sell_ratio": sell_ratio,
            "balance_score": balance_score,
            "alternation_ratio": alternation_ratio,
            "avg_direction_streak": avg_direction_streak,
            "max_direction_streak": max(direction_streaks) if direction_streaks else 0,
        }

    def _analyze_position_patterns(
        self, trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze position sizing and holding patterns"""

        amounts = [
            abs(float(trade.get("amount", 0)))
            for trade in trades
            if trade.get("amount")
        ]
        holding_times = []

        # Calculate holding times between opposite trades (simplified position tracking)
        position_stack = []  # (amount, timestamp, direction)

        for trade in trades:
            amount = abs(float(trade.get("amount", 0)))
            timestamp = datetime.fromisoformat(
                trade.get("timestamp", datetime.now().isoformat())
            )
            direction = trade.get("side", "").upper()

            if not amount or direction not in ["BUY", "SELL"]:
                continue

            # Simplified position matching (this is a basic approximation)
            # In production, this would use actual position tracking from exchange
            if direction == "BUY":
                position_stack.append((amount, timestamp, "BUY"))
            elif direction == "SELL" and position_stack:
                # Match with oldest unfilled position
                buy_amount, buy_time, _ = position_stack.pop(0)
                holding_time = (timestamp - buy_time).total_seconds()
                holding_times.append(holding_time)

        # Position size analysis
        if amounts:
            avg_position_size = np.mean(amounts)
            median_position_size = np.median(amounts)
            position_size_std = np.std(amounts)
            position_size_cv = (
                position_size_std / avg_position_size if avg_position_size > 0 else 0
            )

            # Size consistency (coefficient of variation)
            size_consistency = 1 / (1 + position_size_cv)  # Higher = more consistent
        else:
            avg_position_size = median_position_size = position_size_std = (
                position_size_cv
            ) = size_consistency = 0

        # Holding time analysis
        if holding_times:
            avg_holding_time = np.mean(holding_times)
            median_holding_time = np.median(holding_times)
            holding_time_std = np.std(holding_times)
        else:
            avg_holding_time = median_holding_time = holding_time_std = 0

        return {
            "avg_position_size": avg_position_size,
            "median_position_size": median_position_size,
            "position_size_std": position_size_std,
            "position_size_consistency": size_consistency,
            "avg_holding_time_seconds": avg_holding_time,
            "median_holding_time_seconds": median_holding_time,
            "holding_time_std": holding_time_std,
            "positions_closed": len(holding_times),
            "total_trades": len(trades),
        }

    def _analyze_market_patterns(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze cross-market trading patterns"""

        markets_traded = set()
        market_volumes = defaultdict(float)

        for trade in trades:
            market_id = (
                trade.get("market_id")
                or trade.get("condition_id")
                or trade.get("contract_address", "unknown")
            )
            amount = abs(float(trade.get("amount", 0)))

            markets_traded.add(market_id)
            market_volumes[market_id] += amount

        num_markets = len(markets_traded)

        # Market concentration (Herfindahl-Hirschman Index for market distribution)
        total_volume = sum(market_volumes.values())
        market_concentration = 0
        if total_volume > 0:
            for volume in market_volumes.values():
                share = volume / total_volume
                market_concentration += share**2

        # Market diversity score (lower concentration = higher diversity)
        market_diversity = 1 - market_concentration

        # Simultaneous trading detection (trades in multiple markets within short timeframes)
        simultaneous_events = 0

        if num_markets > 1:
            # Group trades by time windows
            time_groups = defaultdict(list)
            for trade in trades:
                ts = datetime.fromisoformat(
                    trade.get("timestamp", datetime.now().isoformat())
                )
                window_start = ts.replace(minute=0, second=0, microsecond=0)
                time_groups[window_start].append(trade)

            for trades_in_window in time_groups.values():
                markets_in_window = set()
                for trade in trades_in_window:
                    market_id = (
                        trade.get("market_id")
                        or trade.get("condition_id")
                        or trade.get("contract_address", "unknown")
                    )
                    markets_in_window.add(market_id)

                if len(markets_in_window) > 1:
                    simultaneous_events += 1

        return {
            "markets_traded_count": num_markets,
            "market_list": list(markets_traded),
            "market_concentration": market_concentration,
            "market_diversity": market_diversity,
            "simultaneous_trading_events": simultaneous_events,
            "market_volume_distribution": dict(market_volumes),
            "avg_markets_per_hour": num_markets
            / max(len(trades) / 10, 1),  # Rough estimate
        }

    def _analyze_risk_patterns(
        self, trades: List[Dict[str, Any]], market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze risk-related trading patterns"""

        # Price impact analysis (simplified - would need market depth data)
        price_impacts = []
        for trade in trades:
            amount = abs(float(trade.get("amount", 0)))
            # Simplified price impact calculation
            # In production, this would use actual market depth and slippage data
            if amount > 0:
                # Estimate impact based on trade size relative to typical market size
                estimated_impact = min(amount / 1000, 0.1)  # Cap at 10%
                price_impacts.append(estimated_impact)

        # Spread analysis (bid-ask spread maintenance)
        spreads_maintained = 0
        for i in range(1, len(trades), 2):
            if i + 1 < len(trades):
                trade1 = trades[i - 1]
                trade2 = trades[i]

                # Check for potential spread maintenance (buy then sell, or vice versa)
                if (
                    trade1.get("side", "").upper() == "BUY"
                    and trade2.get("side", "").upper() == "SELL"
                ):
                    spreads_maintained += 1
                elif (
                    trade1.get("side", "").upper() == "SELL"
                    and trade2.get("side", "").upper() == "BUY"
                ):
                    spreads_maintained += 1

        # Loss absorption analysis (trades against adverse price movements)
        if market_data:
            # This would require price feed data to detect trades against market direction
            pass

        # Position limit adherence (staying within size limits)
        position_limit_breaches = 0
        max_position_limit = self.settings.risk.max_position_size

        # Simplified position tracking
        net_position = 0
        for trade in trades:
            amount = float(trade.get("amount", 0))
            if trade.get("side", "").upper() == "BUY":
                net_position += amount
            elif trade.get("side", "").upper() == "SELL":
                net_position -= amount

            if abs(net_position) > max_position_limit:
                position_limit_breaches += 1

        return {
            "avg_price_impact": np.mean(price_impacts) if price_impacts else 0,
            "max_price_impact": max(price_impacts) if price_impacts else 0,
            "spread_maintenance_actions": spreads_maintained,
            "position_limit_breaches": position_limit_breaches,
            "net_position_drift": net_position,
            "risk_adjusted_volume": sum(abs(float(t.get("amount", 0))) for t in trades)
            / max(len(trades), 1),
        }

    def _analyze_consistency_patterns(
        self, trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze trading consistency and predictability"""

        # Volume consistency over time
        daily_volumes = defaultdict(float)
        for trade in trades:
            ts = datetime.fromisoformat(
                trade.get("timestamp", datetime.now().isoformat())
            )
            day_key = ts.date().isoformat()
            amount = abs(float(trade.get("amount", 0)))
            daily_volumes[day_key] += amount

        if daily_volumes:
            volume_values = list(daily_volumes.values())
            volume_std = np.std(volume_values)
            volume_mean = np.mean(volume_values)
            volume_cv = volume_std / volume_mean if volume_mean > 0 else 0

            # Volume predictability (lower CV = more predictable)
            volume_consistency = 1 / (1 + volume_cv)
        else:
            volume_consistency = 0

        # Trading schedule consistency
        trading_days = set()
        for trade in trades:
            ts = datetime.fromisoformat(
                trade.get("timestamp", datetime.now().isoformat())
            )
            trading_days.add(ts.date())

        total_days = len(trading_days)
        analysis_days = self.analysis_window_days
        trading_frequency = total_days / analysis_days

        # Activity pattern consistency (coefficient of variation of trades per day)
        trades_per_day = defaultdict(int)
        for trade in trades:
            ts = datetime.fromisoformat(
                trade.get("timestamp", datetime.now().isoformat())
            )
            day_key = ts.date().isoformat()
            trades_per_day[day_key] += 1

        if trades_per_day:
            activity_values = list(trades_per_day.values())
            activity_std = np.std(activity_values)
            activity_mean = np.mean(activity_values)
            activity_cv = activity_std / activity_mean if activity_mean > 0 else 0

            activity_consistency = 1 / (1 + activity_cv)
        else:
            activity_consistency = 0

        return {
            "volume_consistency": volume_consistency,
            "activity_consistency": activity_consistency,
            "trading_frequency": trading_frequency,  # Days per week with trades
            "daily_volume_stats": {
                "mean": np.mean(list(daily_volumes.values())) if daily_volumes else 0,
                "std": np.std(list(daily_volumes.values())) if daily_volumes else 0,
                "days_traded": total_days,
            },
            "daily_activity_stats": {
                "mean": np.mean(list(trades_per_day.values())) if trades_per_day else 0,
                "std": np.std(list(trades_per_day.values())) if trades_per_day else 0,
                "max_trades_per_day": max(trades_per_day.values())
                if trades_per_day
                else 0,
            },
        }

    def _calculate_market_maker_probability(self, metrics: Dict[str, Any]) -> float:
        """Calculate market maker probability score using weighted behavioral factors"""

        score = 0.0
        total_weight = 0.0

        # High-frequency trading (weight: 0.25)
        trades_per_hour = metrics.get("temporal_metrics", {}).get("trades_per_hour", 0)
        freq_score = min(
            trades_per_hour / self.thresholds["high_frequency_threshold"], 1.0
        )
        score += freq_score * 0.25
        total_weight += 0.25

        # Buy/sell balance (weight: 0.20)
        balance_score = metrics.get("directional_metrics", {}).get("balance_score", 0)
        balance_threshold = (
            1 - self.thresholds["balance_ratio_threshold"]
        )  # 0.7 minimum balance score
        balance_contribution = max(
            0, (balance_score - balance_threshold) / (1 - balance_threshold)
        )
        score += balance_contribution * 0.20
        total_weight += 0.20

        # Short holding periods (weight: 0.15)
        avg_holding_time = metrics.get("position_metrics", {}).get(
            "avg_holding_time_seconds", 0
        )
        if avg_holding_time > 0:
            holding_score = max(
                0, 1 - (avg_holding_time / self.thresholds["holding_time_threshold"])
            )
            score += holding_score * 0.15
            total_weight += 0.15

        # Multi-market trading (weight: 0.15)
        markets_count = metrics.get("market_metrics", {}).get("markets_traded_count", 0)
        market_score = min(
            markets_count / self.thresholds["multi_market_threshold"], 1.0
        )
        score += market_score * 0.15
        total_weight += 0.15

        # Volume consistency (weight: 0.10)
        volume_consistency = metrics.get("consistency_metrics", {}).get(
            "volume_consistency", 0
        )
        consistency_threshold = self.thresholds["consistency_threshold"]
        consistency_contribution = max(
            0,
            (volume_consistency - consistency_threshold) / (1 - consistency_threshold),
        )
        score += consistency_contribution * 0.10
        total_weight += 0.10

        # Spread maintenance patterns (weight: 0.10)
        spread_actions = metrics.get("risk_metrics", {}).get(
            "spread_maintenance_actions", 0
        )
        total_trades = len(
            metrics.get("temporal_metrics", {}).get("trades_per_hour", 0) * 24
        )  # Rough estimate
        if total_trades > 0:
            spread_score = min(
                spread_actions / (total_trades * 0.1), 1.0
            )  # Expect 10% spread trades
            score += spread_score * 0.10
            total_weight += 0.10

        # Burst trading patterns (weight: 0.05)
        burst_events = metrics.get("temporal_metrics", {}).get(
            "burst_trading_events", 0
        )
        burst_score = min(
            burst_events / 5, 1.0
        )  # 5+ burst events = high MM probability
        score += burst_score * 0.05
        total_weight += 0.05

        # Normalize score
        final_score = score / total_weight if total_weight > 0 else 0.0

        return min(final_score, 1.0)

    def _classify_wallet(self, mm_probability: float, metrics: Dict[str, Any]) -> str:
        """Classify wallet based on market maker probability and behavioral metrics"""

        if mm_probability >= self.classification_threshold:
            return "market_maker"

        # Check for other patterns
        trades_per_hour = metrics.get("temporal_metrics", {}).get("trades_per_hour", 0)
        balance_score = metrics.get("directional_metrics", {}).get("balance_score", 0)
        markets_count = metrics.get("market_metrics", {}).get("markets_traded_count", 0)

        # High frequency but unbalanced = potential scalper/arbitrageur
        if trades_per_hour >= self.thresholds["high_frequency_threshold"] * 0.5:
            if balance_score < 0.6:  # Unbalanced
                return "high_frequency_trader"
            elif markets_count >= self.thresholds["multi_market_threshold"]:
                return "arbitrage_trader"

        # Low frequency, directional trading
        if trades_per_hour < 1.0 and balance_score < 0.6:
            return "directional_trader"

        # Moderate activity, somewhat balanced
        if 0.4 <= mm_probability < self.classification_threshold:
            return "mixed_trader"

        # Very low activity or insufficient data
        return "low_activity"

    def _calculate_confidence_score(
        self, metrics: Dict[str, Any], trades: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score for the classification"""

        confidence_factors = []

        # Sample size confidence
        trade_count = len(trades)
        sample_confidence = min(trade_count / 50, 1.0)  # 50 trades = full confidence
        confidence_factors.append(sample_confidence)

        # Time span confidence
        temporal = metrics.get("temporal_metrics", {})
        time_span_hours = temporal.get("trading_span_hours", 0)
        time_confidence = min(time_span_hours / 168, 1.0)  # 1 week = full confidence
        confidence_factors.append(time_confidence)

        # Metric consistency confidence
        consistency = metrics.get("consistency_metrics", {})
        volume_consistency = consistency.get("volume_consistency", 0)
        activity_consistency = consistency.get("activity_consistency", 0)
        consistency_confidence = (volume_consistency + activity_consistency) / 2
        confidence_factors.append(consistency_confidence)

        # Market diversity confidence
        market = metrics.get("market_metrics", {})
        market_diversity = market.get("market_diversity", 0)
        diversity_confidence = market_diversity
        confidence_factors.append(diversity_confidence)

        # Overall confidence (weighted average)
        weights = [
            0.3,
            0.3,
            0.25,
            0.15,
        ]  # Sample size, time span, consistency, diversity
        confidence = sum(f * w for f, w in zip(confidence_factors, weights))

        return min(confidence, 1.0)

    def _generate_behavioral_insights(
        self, metrics: Dict[str, Any], classification: str
    ) -> List[str]:
        """Generate human-readable insights about wallet behavior"""

        insights = []

        temporal = metrics.get("temporal_metrics", {})
        directional = metrics.get("directional_metrics", {})
        position = metrics.get("position_metrics", {})
        market = metrics.get("market_metrics", {})
        consistency = metrics.get("consistency_metrics", {})

        # Trading frequency insights
        trades_per_hour = temporal.get("trades_per_hour", 0)
        if trades_per_hour >= 5:
            insights.append(
                f"Very high trading frequency: {trades_per_hour:.2f} trades/hour"
            )
        elif trades_per_hour >= 1:
            insights.append(
                f"Moderate trading frequency: {trades_per_hour:.2f} trades/hour"
            )
        else:
            insights.append(f"Low trading frequency: {trades_per_hour:.2f} trades/hour")
        # Balance insights
        balance_score = directional.get("balance_score", 0)
        if balance_score >= 0.8:
            insights.append(
                f"Highly balanced trading: {balance_score:.2f} balance score"
            )
        elif balance_score <= 0.3:
            insights.append(
                f"Strong directional bias: {balance_score:.2f} balance score"
            )
        # Holding time insights
        avg_holding_time = position.get("avg_holding_time_seconds", 0)
        if avg_holding_time <= 3600:  # 1 hour
            insights.append(
                f"Average position holding time: {avg_holding_time / 60:.1f} minutes"
            )
        elif avg_holding_time <= 86400:  # 1 day
            insights.append(
                f"Average position holding time: {avg_holding_time / 3600:.1f} hours"
            )
        else:
            insights.append(
                f"Average position holding time: {avg_holding_time / 86400:.1f} days"
            )

        # Market diversity insights
        markets_count = market.get("markets_traded_count", 0)
        if markets_count >= 5:
            insights.append(f"Actively trades in {markets_count} different markets")
        elif markets_count >= 2:
            insights.append(f"Trades in {markets_count} different markets")

        # Consistency insights
        volume_consistency = consistency.get("volume_consistency", 0)
        if volume_consistency >= 0.8:
            insights.append("Highly consistent trading volume across time periods")
        elif volume_consistency <= 0.4:
            insights.append("Variable trading volume with significant fluctuations")

        # Classification-specific insights
        if classification == "market_maker":
            insights.append("Behavior strongly indicates market making activities")
            if temporal.get("burst_trading_events", 0) >= 3:
                insights.append(
                    "Frequent burst trading patterns typical of market makers"
                )
        elif classification == "high_frequency_trader":
            insights.append("High-frequency trading with directional bias")
        elif classification == "directional_trader":
            insights.append("Primarily directional trading with longer-term positions")

        return insights

    def _assess_trading_risks(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Assess trading risks based on behavioral patterns"""

        risk_factors = {
            "position_concentration": "low",
            "market_exposure": "low",
            "liquidity_risk": "low",
            "volatility_exposure": "medium",
            "overall_risk": "low",
        }

        market = metrics.get("market_metrics", {})
        position = metrics.get("position_metrics", {})
        consistency = metrics.get("consistency_metrics", {})

        # Market concentration risk
        concentration = market.get("market_concentration", 0)
        if concentration >= 0.8:
            risk_factors["market_exposure"] = "high"
            risk_factors["position_concentration"] = "high"
        elif concentration >= 0.5:
            risk_factors["market_exposure"] = "medium"
            risk_factors["position_concentration"] = "medium"

        # Position size consistency risk
        size_consistency = position.get("position_size_consistency", 0)
        if size_consistency <= 0.5:
            risk_factors["volatility_exposure"] = "high"

        # Volume consistency risk
        volume_consistency = consistency.get("volume_consistency", 0)
        if volume_consistency <= 0.4:
            risk_factors["liquidity_risk"] = "medium"

        # Overall risk assessment
        high_risks = sum(1 for risk in risk_factors.values() if risk == "high")
        medium_risks = sum(1 for risk in risk_factors.values() if risk == "medium")

        if high_risks >= 2:
            risk_factors["overall_risk"] = "high"
        elif high_risks >= 1 or medium_risks >= 2:
            risk_factors["overall_risk"] = "medium"

        return risk_factors

    def _compare_to_benchmarks(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Compare wallet metrics to benchmark averages"""

        # These would be calculated from historical data in production
        benchmarks = {
            "avg_trades_per_hour": 2.5,
            "avg_balance_score": 0.65,
            "avg_holding_time_hours": 12,
            "avg_markets_traded": 2.8,
            "avg_volume_consistency": 0.7,
        }

        comparisons = {}

        temporal = metrics.get("temporal_metrics", {})
        directional = metrics.get("directional_metrics", {})
        position = metrics.get("position_metrics", {})
        metrics.get("market_metrics", {})
        metrics.get("consistency_metrics", {})

        # Trading frequency comparison
        actual_freq = temporal.get("trades_per_hour", 0)
        comparisons["trading_frequency"] = {
            "actual": actual_freq,
            "benchmark": benchmarks["avg_trades_per_hour"],
            "percentile": min(actual_freq / benchmarks["avg_trades_per_hour"], 2.0),
        }

        # Balance score comparison
        actual_balance = directional.get("balance_score", 0)
        comparisons["balance_score"] = {
            "actual": actual_balance,
            "benchmark": benchmarks["avg_balance_score"],
            "percentile": (
                actual_balance / benchmarks["avg_balance_score"]
                if benchmarks["avg_balance_score"] > 0
                else 0
            ),
        }

        # Holding time comparison
        actual_holding = (
            position.get("avg_holding_time_seconds", 0) / 3600
        )  # Convert to hours
        comparisons["holding_time"] = {
            "actual": actual_holding,
            "benchmark": benchmarks["avg_holding_time_hours"],
            "percentile": benchmarks["avg_holding_time_hours"]
            / max(actual_holding, 0.1),
        }

        return comparisons

    def _store_behavior_history(
        self, wallet_address: str, analysis: Dict[str, Any]
    ) -> None:
        """Store behavior analysis in history for trend tracking"""

        history_entry = {
            "timestamp": get_current_time_utc().isoformat(),
            "classification": analysis["classification"],
            "market_maker_probability": analysis["market_maker_probability"],
            "confidence_score": analysis["confidence_score"],
            "trade_count": analysis["trade_count"],
            "key_metrics": {
                "trades_per_hour": analysis["metrics"]["temporal_metrics"].get(
                    "trades_per_hour", 0
                ),
                "balance_score": analysis["metrics"]["directional_metrics"].get(
                    "balance_score", 0
                ),
                "markets_traded": analysis["metrics"]["market_metrics"].get(
                    "markets_traded_count", 0
                ),
                "volume_consistency": analysis["metrics"]["consistency_metrics"].get(
                    "volume_consistency", 0
                ),
            },
        }

        # Store using the storage system
        self.storage.store_behavior_history(wallet_address, history_entry)

    async def get_wallet_classification_report(
        self, wallet_address: str
    ) -> Dict[str, Any]:
        """Generate detailed classification report for a wallet"""

        normalized_wallet = normalize_address(wallet_address)

        # Get current classification from storage
        behavior = self.storage.get_wallet_classification(normalized_wallet)

        if not behavior:
            return {
                "error": "Wallet not found in classification database",
                "wallet_address": normalized_wallet,
            }

        # Get behavior history for trends
        history = self.storage.get_wallet_behavior_history(normalized_wallet, limit=10)
        recent_history = history  # Storage returns most recent first

        # Calculate trends
        trends = self._calculate_classification_trends(recent_history)

        report = {
            "wallet_address": normalized_wallet,
            "current_classification": behavior["classification"],
            "market_maker_probability": behavior["market_maker_probability"],
            "confidence_score": behavior["confidence_score"],
            "last_analysis": behavior["last_analysis"],
            "trade_count": behavior["trade_count"],
            "trends": trends,
            "behavior_summary": self._generate_behavior_summary(
                behavior["metrics_snapshot"]
            ),
            "recommendations": self._generate_trading_recommendations(behavior),
        }

        return report

    def _calculate_classification_trends(
        self, history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate classification trends from behavior history"""

        if not history:
            return {"trend": "insufficient_data", "confidence": 0.0}

        # Calculate trend in market maker probability
        probabilities = [entry["market_maker_probability"] for entry in history]
        if len(probabilities) >= 2:
            recent_avg = np.mean(probabilities[-3:])  # Last 3 entries
            earlier_avg = (
                np.mean(probabilities[:-3])
                if len(probabilities) > 3
                else probabilities[0]
            )

            if recent_avg > earlier_avg + 0.1:
                trend = "increasing_mm_probability"
            elif recent_avg < earlier_avg - 0.1:
                trend = "decreasing_mm_probability"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Classification stability
        classifications = [entry["classification"] for entry in history]
        most_common = max(set(classifications), key=classifications.count)
        stability = classifications.count(most_common) / len(classifications)

        return {
            "trend": trend,
            "stability": stability,
            "most_common_classification": most_common,
            "recent_probability_avg": np.mean(probabilities[-3:])
            if probabilities
            else 0,
            "overall_probability_avg": np.mean(probabilities) if probabilities else 0,
        }

    def _generate_behavior_summary(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate human-readable behavior summary"""

        summary = {
            "trading_style": "",
            "key_characteristics": [],
            "strengths": [],
            "risk_factors": [],
        }

        temporal = metrics.get("temporal_metrics", {})
        directional = metrics.get("directional_metrics", {})
        market = metrics.get("market_metrics", {})

        trades_per_hour = temporal.get("trades_per_hour", 0)
        balance_score = directional.get("balance_score", 0)
        markets_count = market.get("markets_traded_count", 0)

        # Determine trading style
        if trades_per_hour >= 5 and balance_score >= 0.7:
            summary["trading_style"] = "Professional Market Maker"
        elif trades_per_hour >= 3 and markets_count >= 3:
            summary["trading_style"] = "Active Arbitrage Trader"
        elif trades_per_hour >= 1 and balance_score < 0.6:
            summary["trading_style"] = "High-Frequency Directional Trader"
        elif balance_score < 0.5 and markets_count <= 2:
            summary["trading_style"] = "Long-term Directional Trader"
        else:
            summary["trading_style"] = "Mixed Strategy Trader"

        # Key characteristics
        if trades_per_hour >= 5:
            summary["key_characteristics"].append("Very high trading frequency")
        elif trades_per_hour >= 1:
            summary["key_characteristics"].append("Moderate to high trading frequency")

        if balance_score >= 0.8:
            summary["key_characteristics"].append("Highly balanced buy/sell activity")
        elif balance_score <= 0.4:
            summary["key_characteristics"].append("Strong directional bias")

        if markets_count >= 5:
            summary["key_characteristics"].append("Multi-market participant")
        elif markets_count <= 1:
            summary["key_characteristics"].append("Single-market focus")

        return summary

    def _generate_trading_recommendations(self, behavior: Dict[str, Any]) -> List[str]:
        """Generate trading recommendations based on wallet behavior"""

        recommendations = []
        classification = behavior["classification"]
        mm_probability = behavior["market_maker_probability"]

        if classification == "market_maker":
            recommendations.extend(
                [
                    "Consider copying trades with tight stop-losses due to high volatility",
                    "Monitor for spread opportunities when this wallet is active",
                    "Be prepared for quick position reversals",
                    "Consider smaller position sizes to match market maker behavior",
                ]
            )
        elif classification == "directional_trader":
            recommendations.extend(
                [
                    "This wallet shows strong directional conviction",
                    "Consider following larger trades for trend confirmation",
                    "Longer holding periods may be appropriate",
                    "Monitor for breakout signals when this wallet trades heavily",
                ]
            )
        elif classification == "high_frequency_trader":
            recommendations.extend(
                [
                    "High-frequency activity suggests scalping strategy",
                    "Use tight stop-losses and quick profit taking",
                    "Monitor for momentum signals",
                    "Consider automated execution for similar trade timing",
                ]
            )

        if mm_probability >= 0.8:
            recommendations.append(
                "High market maker probability - excellent for arbitrage opportunities"
            )

        return recommendations

    async def get_market_maker_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all classified wallets"""

        # Use storage system for comprehensive summary
        summary = self.storage.get_behavior_summary_stats()

        # Add timestamp
        summary["last_updated"] = get_current_time_utc().isoformat()

        return summary

    def update_classification_thresholds(
        self, new_thresholds: Dict[str, float]
    ) -> None:
        """Update classification thresholds for fine-tuning"""

        self.thresholds.update(new_thresholds)
        logger.info(f"Updated classification thresholds: {self.thresholds}")

        # Clear cache to force re-analysis with new thresholds
        self.behavior_cache.clear()

    async def detect_classification_changes(self) -> List[Dict[str, Any]]:
        """Detect wallets whose classifications have changed recently"""

        # Use storage system to detect changes
        return self.storage.detect_classification_changes(hours_back=24)
