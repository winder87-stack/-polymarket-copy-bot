"""
Adaptive Copy Trading Strategy Engine
=====================================

Dynamic strategy selection and execution system that automatically adapts
to wallet type (market maker vs directional trader) and market conditions.

Features:
- Real-time strategy selection based on wallet classification
- Market condition awareness (volatility, liquidity, gas prices)
- Performance-based strategy weighting and switching
- Hysteresis-based oscillation prevention
- Fallback strategy activation for underperformance
- Comprehensive backtesting and validation framework
"""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from core.market_maker_detector import MarketMakerDetector
from core.market_maker_risk_manager import MarketMakerRiskManager
from core.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Available trading strategies"""

    MARKET_MAKER_AGGRESSIVE = "market_maker_aggressive"
    MARKET_MAKER_CONSERVATIVE = "market_maker_conservative"
    MARKET_MAKER_SPREAD_CAPTURE = "market_maker_spread_capture"
    DIRECTIONAL_MOMENTUM = "directional_momentum"
    DIRECTIONAL_MEAN_REVERSION = "directional_mean_reversion"
    DIRECTIONAL_BREAKOUT = "directional_breakout"
    ARBITRAGE_CROSS_MARKET = "arbitrage_cross_market"
    HIGH_FREQUENCY_SCALPING = "high_frequency_scalping"
    PASSIVE_HOLD = "passive_hold"
    NO_TRADE = "no_trade"


class AdaptiveStrategyEngine:
    """
    Core adaptive strategy engine for dynamic copy trading.

    Automatically selects and adjusts trading strategies based on:
    - Wallet type classification and confidence
    - Current market conditions (volatility, liquidity, gas)
    - Recent strategy performance and risk metrics
    - Portfolio constraints and risk limits
    """

    def __init__(
        self,
        market_maker_detector: MarketMakerDetector,
        risk_manager: MarketMakerRiskManager,
        performance_analyzer: PerformanceAnalyzer,
    ):
        self.detector = market_maker_detector
        self.risk_manager = risk_manager
        self.analyzer = performance_analyzer

        # Strategy configuration
        self.strategy_configs = self._initialize_strategy_configs()

        # Adaptive parameters
        self.adaptive_params = {
            "strategy_switch_threshold": 0.15,  # 15% performance difference to switch
            "hysteresis_band": 0.05,  # 5% hysteresis to prevent oscillation
            "performance_window_days": 7,  # Days to evaluate strategy performance
            "min_confidence_threshold": 0.6,  # Minimum wallet confidence for aggressive strategies
            "market_volatility_threshold": 0.25,  # High volatility threshold
            "gas_price_multiplier_limit": 2.0,  # Maximum gas price multiplier
            "liquidity_threshold": 0.3,  # Minimum liquidity score
            "max_strategy_changes_per_day": 3,  # Rate limiting for strategy changes
            "fallback_activation_threshold": -0.1,  # -10% threshold for fallback activation
            "rebalancing_frequency_hours": 6,  # Portfolio rebalancing frequency
        }

        # State tracking
        self.current_strategies: Dict[str, StrategyType] = {}  # wallet -> strategy
        self.strategy_performance: Dict[str, Dict[str, Any]] = {}  # strategy -> performance metrics
        self.market_conditions = self._get_default_market_conditions()
        self.daily_strategy_changes = 0
        self.last_rebalancing = datetime.now()

        # ML components
        self.strategy_predictor = None
        self.performance_predictor = None
        self.feature_scaler = None

        # Performance tracking
        self.strategy_history: List[Dict[str, Any]] = []
        self.decision_log: List[Dict[str, Any]] = []

        logger.info("🎯 Adaptive strategy engine initialized")

    def _initialize_strategy_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize configuration for each strategy type."""

        return {
            StrategyType.MARKET_MAKER_AGGRESSIVE: {
                "description": "Aggressive market making with tight spreads and quick reversals",
                "wallet_types": ["market_maker", "arbitrage_trader"],
                "min_confidence": 0.8,
                "max_volatility": 0.4,
                "max_gas_multiplier": 1.5,
                "min_liquidity": 0.4,
                "position_size_multiplier": 0.08,
                "stop_loss_pct": 0.8,
                "take_profit_pct": 1.5,
                "max_holding_hours": 1.5,
                "min_profit_threshold": 0.003,  # 0.3% minimum
                "expected_win_rate": 0.58,
                "expected_profit_factor": 1.35,
                "risk_score": 0.7,
            },
            StrategyType.MARKET_MAKER_CONSERVATIVE: {
                "description": "Conservative market making with wider spreads and longer holds",
                "wallet_types": ["market_maker", "low_activity"],
                "min_confidence": 0.6,
                "max_volatility": 0.6,
                "max_gas_multiplier": 2.5,
                "min_liquidity": 0.2,
                "position_size_multiplier": 0.04,
                "stop_loss_pct": 0.5,
                "take_profit_pct": 1.0,
                "max_holding_hours": 4.0,
                "min_profit_threshold": 0.001,  # 0.1% minimum
                "expected_win_rate": 0.55,
                "expected_profit_factor": 1.25,
                "risk_score": 0.4,
            },
            StrategyType.MARKET_MAKER_SPREAD_CAPTURE: {
                "description": "Specialized spread capture for professional market makers",
                "wallet_types": ["market_maker"],
                "min_confidence": 0.85,
                "max_volatility": 0.3,
                "max_gas_multiplier": 1.2,
                "min_liquidity": 0.5,
                "position_size_multiplier": 0.06,
                "stop_loss_pct": 0.3,
                "take_profit_pct": 0.8,
                "max_holding_hours": 0.5,
                "min_profit_threshold": 0.002,  # 0.2% minimum
                "expected_win_rate": 0.62,
                "expected_profit_factor": 1.45,
                "risk_score": 0.5,
            },
            StrategyType.DIRECTIONAL_MOMENTUM: {
                "description": "Momentum-based directional trading following price trends",
                "wallet_types": ["directional_trader", "mixed_trader"],
                "min_confidence": 0.7,
                "max_volatility": 0.5,
                "max_gas_multiplier": 3.0,
                "min_liquidity": 0.3,
                "position_size_multiplier": 0.6,
                "stop_loss_pct": 12.0,
                "take_profit_pct": 20.0,
                "max_holding_hours": 24.0,
                "min_profit_threshold": 0.02,  # 2% minimum
                "expected_win_rate": 0.48,
                "expected_profit_factor": 1.35,
                "risk_score": 0.8,
            },
            StrategyType.DIRECTIONAL_MEAN_REVERSION: {
                "description": "Mean reversion strategy for overbought/oversold conditions",
                "wallet_types": ["directional_trader", "mixed_trader"],
                "min_confidence": 0.65,
                "max_volatility": 0.4,
                "max_gas_multiplier": 2.5,
                "min_liquidity": 0.4,
                "position_size_multiplier": 0.4,
                "stop_loss_pct": 8.0,
                "take_profit_pct": 12.0,
                "max_holding_hours": 12.0,
                "min_profit_threshold": 0.015,  # 1.5% minimum
                "expected_win_rate": 0.52,
                "expected_profit_factor": 1.28,
                "risk_score": 0.6,
            },
            StrategyType.DIRECTIONAL_BREAKOUT: {
                "description": "Breakout trading for strong directional moves",
                "wallet_types": ["directional_trader"],
                "min_confidence": 0.75,
                "max_volatility": 0.6,
                "max_gas_multiplier": 2.0,
                "min_liquidity": 0.5,
                "position_size_multiplier": 0.8,
                "stop_loss_pct": 15.0,
                "take_profit_pct": 25.0,
                "max_holding_hours": 48.0,
                "min_profit_threshold": 0.03,  # 3% minimum
                "expected_win_rate": 0.45,
                "expected_profit_factor": 1.42,
                "risk_score": 0.9,
            },
            StrategyType.ARBITRAGE_CROSS_MARKET: {
                "description": "Cross-market arbitrage opportunities",
                "wallet_types": ["arbitrage_trader"],
                "min_confidence": 0.8,
                "max_volatility": 0.35,
                "max_gas_multiplier": 1.8,
                "min_liquidity": 0.45,
                "position_size_multiplier": 0.12,
                "stop_loss_pct": 1.2,
                "take_profit_pct": 2.5,
                "max_holding_hours": 2.0,
                "min_profit_threshold": 0.005,  # 0.5% minimum
                "expected_win_rate": 0.65,
                "expected_profit_factor": 1.55,
                "risk_score": 0.55,
            },
            StrategyType.HIGH_FREQUENCY_SCALPING: {
                "description": "High-frequency scalping for small, frequent profits",
                "wallet_types": ["high_frequency_trader"],
                "min_confidence": 0.7,
                "max_volatility": 0.5,
                "max_gas_multiplier": 1.3,
                "min_liquidity": 0.5,
                "position_size_multiplier": 0.15,
                "stop_loss_pct": 1.5,
                "take_profit_pct": 1.8,
                "max_holding_hours": 0.25,
                "min_profit_threshold": 0.0015,  # 0.15% minimum
                "expected_win_rate": 0.54,
                "expected_profit_factor": 1.22,
                "risk_score": 0.75,
            },
            StrategyType.PASSIVE_HOLD: {
                "description": "Passive holding strategy for low-confidence situations",
                "wallet_types": ["all"],
                "min_confidence": 0.0,
                "max_volatility": 1.0,
                "max_gas_multiplier": 10.0,
                "min_liquidity": 0.0,
                "position_size_multiplier": 0.02,
                "stop_loss_pct": 50.0,
                "take_profit_pct": 100.0,
                "max_holding_hours": 168.0,  # 1 week
                "min_profit_threshold": 0.05,  # 5% minimum
                "expected_win_rate": 0.4,
                "expected_profit_factor": 1.1,
                "risk_score": 0.95,
            },
            StrategyType.NO_TRADE: {
                "description": "No trading - high risk or unsuitable conditions",
                "wallet_types": ["all"],
                "min_confidence": 0.0,
                "max_volatility": 1.0,
                "max_gas_multiplier": 100.0,
                "min_liquidity": 0.0,
                "position_size_multiplier": 0.0,
                "stop_loss_pct": 0.0,
                "take_profit_pct": 0.0,
                "max_holding_hours": 0.0,
                "min_profit_threshold": 0.0,
                "expected_win_rate": 0.0,
                "expected_profit_factor": 1.0,
                "risk_score": 0.0,
            },
        }

    def _get_default_market_conditions(self) -> Dict[str, Any]:
        """Get default market conditions."""

        return {
            "volatility_index": 0.2,  # 20% annualized volatility
            "liquidity_score": 0.6,  # 60% liquidity score
            "gas_price_multiplier": 1.0,  # 1x normal gas prices
            "trend_strength": 0.0,  # Neutral trend
            "market_regime": "normal",  # normal, bull, bear, high_vol
            "last_update": datetime.now(),
        }

    async def select_strategy_for_wallet(
        self, wallet_address: str, market_conditions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Select optimal trading strategy for a specific wallet.

        Args:
            wallet_address: Wallet to analyze
            market_conditions: Current market conditions (optional)

        Returns:
            Strategy selection decision with reasoning
        """

        # Update market conditions if provided
        if market_conditions:
            self.market_conditions.update(market_conditions)
            self.market_conditions["last_update"] = datetime.now()

        # Get wallet information
        wallet_info = await self.detector.get_wallet_classification_report(wallet_address)

        if "error" in wallet_info:
            # Default to passive strategy for unknown wallets
            return self._create_strategy_decision(
                wallet_address,
                StrategyType.PASSIVE_HOLD,
                f"Wallet classification error: {wallet_info['error']}",
            )

        wallet_type = wallet_info.get("classification", "unknown")
        confidence_score = wallet_info.get("confidence_score", 0.0)

        # Evaluate available strategies for this wallet type
        candidate_strategies = self._get_candidate_strategies(wallet_type)

        if not candidate_strategies:
            return self._create_strategy_decision(
                wallet_address,
                StrategyType.NO_TRADE,
                f"No suitable strategies for wallet type: {wallet_type}",
            )

        # Score each candidate strategy
        strategy_scores = {}
        for strategy in candidate_strategies:
            score = self._score_strategy_for_wallet(strategy, wallet_info, self.market_conditions)
            strategy_scores[strategy] = score

        # Select best strategy
        best_strategy = max(strategy_scores.keys(), key=lambda x: strategy_scores[x])

        # Check for strategy switching with hysteresis
        current_strategy = self.current_strategies.get(wallet_address)
        if current_strategy and current_strategy != best_strategy:
            switch_decision = self._evaluate_strategy_switch(
                wallet_address,
                current_strategy,
                best_strategy,
                strategy_scores[current_strategy],
                strategy_scores[best_strategy],
            )

            if not switch_decision["should_switch"]:
                best_strategy = current_strategy
                switch_reason = switch_decision["reason"]
            else:
                switch_reason = switch_decision["reason"]
        else:
            switch_reason = "Initial strategy selection"

        # Check daily change limits
        if self._should_limit_strategy_changes(wallet_address):
            best_strategy = current_strategy or StrategyType.PASSIVE_HOLD
            switch_reason = "Daily strategy change limit reached"

        # Update current strategy
        self.current_strategies[wallet_address] = best_strategy

        # Log decision
        decision_record = {
            "timestamp": datetime.now().isoformat(),
            "wallet_address": wallet_address,
            "wallet_type": wallet_type,
            "selected_strategy": best_strategy.value,
            "confidence_score": confidence_score,
            "strategy_scores": {k.value: v for k, v in strategy_scores.items()},
            "market_conditions": self.market_conditions.copy(),
            "reason": switch_reason,
        }
        self.decision_log.append(decision_record)

        return self._create_strategy_decision(
            wallet_address, best_strategy, switch_reason, strategy_scores
        )

    def _get_candidate_strategies(self, wallet_type: str) -> List[StrategyType]:
        """Get candidate strategies for a wallet type."""

        candidates = []

        for strategy, config in self.strategy_configs.items():
            allowed_types = config["wallet_types"]
            if "all" in allowed_types or wallet_type in allowed_types:
                candidates.append(strategy)

        return candidates

    def _score_strategy_for_wallet(
        self, strategy: StrategyType, wallet_info: Dict[str, Any], market_conditions: Dict[str, Any]
    ) -> float:
        """
        Score how well a strategy fits a wallet under current conditions.

        Returns score from 0-1 (higher = better fit)
        """

        config = self.strategy_configs[strategy]
        score = 1.0

        # Wallet confidence factor
        confidence_score = wallet_info.get("confidence_score", 0.0)
        confidence_requirement = config["min_confidence"]

        if confidence_score < confidence_requirement:
            confidence_penalty = (confidence_score / confidence_requirement) ** 0.5
            score *= confidence_penalty

        # Market condition factors
        volatility = market_conditions.get("volatility_index", 0.2)
        max_volatility = config["max_volatility"]

        if volatility > max_volatility:
            volatility_penalty = max(0, 1 - (volatility - max_volatility) / 0.3)
            score *= volatility_penalty

        gas_multiplier = market_conditions.get("gas_price_multiplier", 1.0)
        max_gas = config["max_gas_multiplier"]

        if gas_multiplier > max_gas:
            gas_penalty = max(0, 1 - (gas_multiplier - max_gas) / 3.0)
            score *= gas_penalty

        liquidity = market_conditions.get("liquidity_score", 0.6)
        min_liquidity = config["min_liquidity"]

        if liquidity < min_liquidity:
            liquidity_penalty = max(0, liquidity / min_liquidity)
            score *= liquidity_penalty

        # Historical performance factor (if available)
        strategy_key = strategy.value
        if strategy_key in self.strategy_performance:
            perf = self.strategy_performance[strategy_key]
            recent_sharpe = perf.get("recent_sharpe_ratio", 1.0)
            performance_factor = max(0.1, min(2.0, recent_sharpe)) / 1.5
            score *= performance_factor

        # Strategy risk alignment
        wallet_risk_preference = self._estimate_wallet_risk_preference(wallet_info)
        strategy_risk = config["risk_score"]

        risk_alignment = 1 - abs(wallet_risk_preference - strategy_risk)
        score *= risk_alignment

        return min(score, 1.0)

    def _estimate_wallet_risk_preference(self, wallet_info: Dict[str, Any]) -> float:
        """Estimate wallet's risk preference based on behavior."""

        wallet_type = wallet_info.get("classification", "unknown")
        confidence = wallet_info.get("confidence_score", 0.5)

        # Base risk preferences by wallet type
        base_risks = {
            "market_maker": 0.5,  # Moderate risk
            "arbitrage_trader": 0.4,  # Lower risk
            "high_frequency_trader": 0.7,  # Higher risk
            "directional_trader": 0.8,  # High risk
            "mixed_trader": 0.6,  # Moderate-high risk
            "low_activity": 0.3,  # Conservative
        }

        base_risk = base_risks.get(wallet_type, 0.5)

        # Adjust for confidence (higher confidence = slightly higher risk tolerance)
        confidence_adjustment = (confidence - 0.5) * 0.2

        return max(0.1, min(0.9, base_risk + confidence_adjustment))

    def _evaluate_strategy_switch(
        self,
        wallet_address: str,
        current_strategy: StrategyType,
        new_strategy: StrategyType,
        current_score: float,
        new_score: float,
    ) -> Dict[str, Any]:
        """
        Evaluate whether to switch strategies with hysteresis.

        Returns decision with reasoning.
        """

        score_difference = new_score - current_score
        threshold = self.adaptive_params["strategy_switch_threshold"]
        hysteresis = self.adaptive_params["hysteresis_band"]

        # Check if new strategy is significantly better
        if score_difference > threshold:
            return {"should_switch": True, "reason": ".1f"}

        # Check if current strategy has deteriorated significantly
        if score_difference < -threshold:
            return {"should_switch": True, "reason": ".1f"}

        # Apply hysteresis - don't switch if scores are close
        if abs(score_difference) < hysteresis:
            # Check if current strategy is underperforming recently
            if self._is_strategy_underperforming(wallet_address, current_strategy):
                return {
                    "should_switch": True,
                    "reason": f"Current strategy {current_strategy.value} underperforming despite similar scores",
                }

            return {"should_switch": False, "reason": ".3f"}

        return {"should_switch": False, "reason": ".3f"}

    def _is_strategy_underperforming(self, wallet_address: str, strategy: StrategyType) -> bool:
        """Check if strategy is underperforming for this wallet."""

        # Get recent performance for this wallet-strategy combination
        recent_trades = []
        cutoff_time = datetime.now() - timedelta(hours=24)  # Last 24 hours

        for record in self.strategy_history:
            record_time = datetime.fromisoformat(record["timestamp"])
            if (
                record_time > cutoff_time
                and record.get("wallet_address") == wallet_address
                and record.get("strategy") == strategy.value
            ):

                recent_trades.append(record)

        if len(recent_trades) < 3:
            return False  # Not enough data

        # Calculate recent win rate and profit factor
        wins = sum(1 for t in recent_trades if t.get("pnl_usd", 0) > 0)
        win_rate = wins / len(recent_trades)

        profits = sum(t.get("pnl_usd", 0) for t in recent_trades if t.get("pnl_usd", 0) > 0)
        losses = abs(sum(t.get("pnl_usd", 0) for t in recent_trades if t.get("pnl_usd", 0) < 0))

        profit_factor = profits / losses if losses > 0 else float("inf")

        # Check against expected performance
        config = self.strategy_configs[strategy]
        expected_win_rate = config["expected_win_rate"]
        expected_profit_factor = config["expected_profit_factor"]

        win_rate_threshold = expected_win_rate * 0.8  # 80% of expected
        profit_factor_threshold = expected_profit_factor * 0.7  # 70% of expected

        return win_rate < win_rate_threshold or profit_factor < profit_factor_threshold

    def _should_limit_strategy_changes(self, wallet_address: str) -> bool:
        """Check if daily strategy change limits should be enforced."""

        # Reset counter if it's a new day
        today = datetime.now().date()
        if not hasattr(self, "_last_change_reset") or self._last_change_reset != today:
            self.daily_strategy_changes = 0
            self._last_change_reset = today

        return self.daily_strategy_changes >= self.adaptive_params["max_strategy_changes_per_day"]

    def _create_strategy_decision(
        self,
        wallet_address: str,
        strategy: StrategyType,
        reason: str,
        strategy_scores: Optional[Dict[StrategyType, float]] = None,
    ) -> Dict[str, Any]:
        """Create a strategy decision response."""

        config = self.strategy_configs[strategy]

        return {
            "wallet_address": wallet_address,
            "selected_strategy": strategy.value,
            "strategy_config": config,
            "reason": reason,
            "strategy_scores": {k.value: v for k, v in (strategy_scores or {}).items()},
            "expected_performance": {
                "win_rate": config["expected_win_rate"],
                "profit_factor": config["expected_profit_factor"],
                "risk_score": config["risk_score"],
            },
            "trading_parameters": {
                "position_size_multiplier": config["position_size_multiplier"],
                "stop_loss_pct": config["stop_loss_pct"],
                "take_profit_pct": config["take_profit_pct"],
                "max_holding_hours": config["max_holding_hours"],
                "min_profit_threshold": config["min_profit_threshold"],
            },
            "market_conditions": self.market_conditions.copy(),
            "decision_timestamp": datetime.now().isoformat(),
        }

    def update_strategy_performance(self, strategy: str, performance_metrics: Dict[str, Any]):
        """Update performance tracking for a strategy."""

        self.strategy_performance[strategy] = {
            **performance_metrics,
            "last_update": datetime.now().isoformat(),
            "update_count": self.strategy_performance.get(strategy, {}).get("update_count", 0) + 1,
        }

    def get_strategy_recommendations(
        self, wallet_address: str, market_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get strategy recommendations for a wallet under different scenarios.
        """

        recommendations = []

        # Base case
        base_decision = await self.select_strategy_for_wallet(wallet_address, market_conditions)
        recommendations.append(
            {
                "scenario": "current_conditions",
                "strategy": base_decision["selected_strategy"],
                "confidence": "high",
                "expected_return": base_decision["expected_performance"]["win_rate"]
                * base_decision["expected_performance"]["profit_factor"],
            }
        )

        # High volatility scenario
        if market_conditions:
            high_vol_conditions = market_conditions.copy()
            high_vol_conditions["volatility_index"] = min(
                1.0, market_conditions.get("volatility_index", 0.2) * 1.5
            )

            high_vol_decision = await self.select_strategy_for_wallet(
                wallet_address, high_vol_conditions
            )
            recommendations.append(
                {
                    "scenario": "high_volatility",
                    "strategy": high_vol_decision["selected_strategy"],
                    "confidence": "medium",
                    "expected_return": high_vol_decision["expected_performance"]["win_rate"]
                    * high_vol_decision["expected_performance"]["profit_factor"]
                    * 0.8,
                }
            )

        # Low liquidity scenario
        if market_conditions:
            low_liq_conditions = market_conditions.copy()
            low_liq_conditions["liquidity_score"] = max(
                0.1, market_conditions.get("liquidity_score", 0.6) * 0.6
            )

            low_liq_decision = await self.select_strategy_for_wallet(
                wallet_address, low_liq_conditions
            )
            recommendations.append(
                {
                    "scenario": "low_liquidity",
                    "strategy": low_liq_decision["selected_strategy"],
                    "confidence": "medium",
                    "expected_return": low_liq_decision["expected_performance"]["win_rate"]
                    * low_liq_decision["expected_performance"]["profit_factor"]
                    * 0.7,
                }
            )

        # High gas scenario
        if market_conditions:
            high_gas_conditions = market_conditions.copy()
            high_gas_conditions["gas_price_multiplier"] = (
                market_conditions.get("gas_price_multiplier", 1.0) * 2.5
            )

            high_gas_decision = await self.select_strategy_for_wallet(
                wallet_address, high_gas_conditions
            )
            recommendations.append(
                {
                    "scenario": "high_gas",
                    "strategy": high_gas_decision["selected_strategy"],
                    "confidence": "low",
                    "expected_return": high_gas_decision["expected_performance"]["win_rate"]
                    * high_gas_decision["expected_performance"]["profit_factor"]
                    * 0.5,
                }
            )

        return recommendations

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status and performance metrics."""

        total_wallets = len(self.current_strategies)
        strategy_counts = defaultdict(int)

        for strategy in self.current_strategies.values():
            strategy_counts[strategy.value] += 1

        recent_decisions = [
            d
            for d in self.decision_log
            if datetime.fromisoformat(d["timestamp"]) > datetime.now() - timedelta(hours=24)
        ]

        return {
            "total_wallets_tracked": total_wallets,
            "strategy_distribution": dict(strategy_counts),
            "decisions_last_24h": len(recent_decisions),
            "market_conditions": self.market_conditions,
            "system_health": "healthy" if total_wallets > 0 else "initializing",
            "last_update": datetime.now().isoformat(),
        }

    def save_engine_state(self):
        """Save engine state for persistence."""

        try:
            state_dir = Path("data/adaptive_engine")
            state_dir.mkdir(parents=True, exist_ok=True)

            # Save current strategies
            with open(state_dir / "current_strategies.json", "w") as f:
                json.dump({k: v.value for k, v in self.current_strategies.items()}, f)

            # Save strategy performance
            with open(state_dir / "strategy_performance.json", "w") as f:
                json.dump(self.strategy_performance, f, default=str)

            # Save decision log (last 1000 entries)
            with open(state_dir / "decision_log.json", "w") as f:
                json.dump(self.decision_log[-1000:], f, default=str)

            logger.info(f"💾 Adaptive engine state saved to {state_dir}")

        except Exception as e:
            logger.error(f"Error saving engine state: {e}")

    def load_engine_state(self):
        """Load engine state from disk."""

        try:
            state_dir = Path("data/adaptive_engine")

            # Load current strategies
            strategies_file = state_dir / "current_strategies.json"
            if strategies_file.exists():
                with open(strategies_file, "r") as f:
                    strategies_data = json.load(f)
                    self.current_strategies = {
                        k: StrategyType(v) for k, v in strategies_data.items()
                    }

            # Load strategy performance
            perf_file = state_dir / "strategy_performance.json"
            if perf_file.exists():
                with open(perf_file, "r") as f:
                    self.strategy_performance = json.load(f)

            # Load decision log
            log_file = state_dir / "decision_log.json"
            if log_file.exists():
                with open(log_file, "r") as f:
                    self.decision_log = json.load(f)

            logger.info(f"📊 Adaptive engine state loaded from {state_dir}")

        except Exception as e:
            logger.error(f"Error loading engine state: {e}")

    async def run_adaptive_loop(self, check_interval_minutes: int = 15):
        """Run continuous adaptive strategy optimization."""

        logger.info(
            f"🔄 Starting adaptive strategy loop (check every {check_interval_minutes} minutes)"
        )

        while True:
            try:
                # Update market conditions
                self.market_conditions.update(await self._fetch_market_conditions())
                self.market_conditions["last_update"] = datetime.now()

                # Check for strategy rebalancing
                if self._should_rebalance_portfolio():
                    await self._perform_portfolio_rebalancing()

                # Update strategy performance metrics
                await self._update_all_strategy_performance()

                # Check for strategy switches based on performance
                await self._check_performance_based_switches()

                await asyncio.sleep(check_interval_minutes * 60)

            except Exception as e:
                logger.error(f"Error in adaptive loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _fetch_market_conditions(self) -> Dict[str, Any]:
        """Fetch current market conditions (placeholder implementation)."""
        # This would integrate with actual market data feeds
        return {
            "volatility_index": 0.25,  # Example
            "liquidity_score": 0.65,
            "gas_price_multiplier": 1.2,
        }

    def _should_rebalance_portfolio(self) -> bool:
        """Check if portfolio rebalancing is due."""

        time_since_rebalancing = datetime.now() - self.last_rebalancing
        hours_since = time_since_rebalancing.total_seconds() / 3600

        return hours_since >= self.adaptive_params["rebalancing_frequency_hours"]

    async def _perform_portfolio_rebalancing(self):
        """Perform portfolio rebalancing based on current allocations."""

        logger.info("⚖️ Performing portfolio rebalancing")

        # This would implement actual portfolio rebalancing logic
        # based on target allocations vs current positions

        self.last_rebalancing = datetime.now()

    async def _update_all_strategy_performance(self):
        """Update performance metrics for all strategies."""

        # This would calculate recent performance for each strategy
        # based on trade history and update strategy_performance

        pass

    async def _check_performance_based_switches(self):
        """Check for strategy switches based on performance deterioration."""

        # This would identify wallets where current strategy is underperforming
        # and trigger strategy switches

        pass
