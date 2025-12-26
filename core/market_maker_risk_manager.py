"""
Market Maker Risk Management System
====================================

Specialized risk management strategies for copying market maker wallets.
Implements adaptive position sizing, trade filtering, and profit capture
algorithms optimized for market maker behavior patterns.

Features:
- Wallet-type-specific risk parameters
- Real-time trade quality scoring
- Adaptive position sizing algorithms
- Market maker-aware circuit breakers
- Volatility-adjusted profit targets
- Comprehensive backtesting framework
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config.settings import settings
from core.market_maker_detector import MarketMakerDetector

logger = logging.getLogger(__name__)


class MarketMakerRiskManager:
    """
    Advanced risk management system specialized for market maker copying.

    Provides wallet-type-specific strategies for position sizing, trade filtering,
    loss limitation, and profit capture optimized for different trader behaviors.
    """

    def __init__(self, market_maker_detector: MarketMakerDetector):
        self.detector = market_maker_detector

        # Risk management configuration by wallet type
        self.wallet_type_configs = {
            "market_maker": {
                "position_size_multiplier": 0.05,  # 5% of normal position size
                "max_trades_per_hour": 20,
                "max_daily_loss_pct": 2.0,  # 2% daily loss limit
                "stop_loss_pct": 0.5,  # 0.5% stop loss
                "take_profit_pct": 1.0,  # 1% take profit
                "max_position_age_hours": 2,  # Close after 2 hours
                "min_trade_quality_score": 0.6,
                "gas_price_multiplier_limit": 1.5,
                "volatility_multiplier": 0.8,  # Reduce size in high volatility
                "correlation_limit": 0.7,  # Avoid highly correlated MMs
            },
            "arbitrage_trader": {
                "position_size_multiplier": 0.1,  # 10% of normal
                "max_trades_per_hour": 15,
                "max_daily_loss_pct": 3.0,
                "stop_loss_pct": 1.0,
                "take_profit_pct": 2.0,
                "max_position_age_hours": 4,
                "min_trade_quality_score": 0.5,
                "gas_price_multiplier_limit": 2.0,
                "volatility_multiplier": 0.9,
                "correlation_limit": 0.6,
            },
            "high_frequency_trader": {
                "position_size_multiplier": 0.15,  # 15% of normal
                "max_trades_per_hour": 30,
                "max_daily_loss_pct": 5.0,
                "stop_loss_pct": 1.5,
                "take_profit_pct": 1.5,
                "max_position_age_hours": 1,
                "min_trade_quality_score": 0.4,
                "gas_price_multiplier_limit": 1.2,
                "volatility_multiplier": 1.0,
                "correlation_limit": 0.5,
            },
            "directional_trader": {
                "position_size_multiplier": 1.0,  # 100% of normal (baseline)
                "max_trades_per_hour": 5,
                "max_daily_loss_pct": 15.0,
                "stop_loss_pct": 15.0,
                "take_profit_pct": 25.0,
                "max_position_age_hours": 48,
                "min_trade_quality_score": 0.3,
                "gas_price_multiplier_limit": 3.0,
                "volatility_multiplier": 1.0,
                "correlation_limit": 0.3,
            },
            "mixed_trader": {
                "position_size_multiplier": 0.5,  # 50% of normal
                "max_trades_per_hour": 10,
                "max_daily_loss_pct": 8.0,
                "stop_loss_pct": 5.0,
                "take_profit_pct": 10.0,
                "max_position_age_hours": 12,
                "min_trade_quality_score": 0.4,
                "gas_price_multiplier_limit": 2.0,
                "volatility_multiplier": 0.95,
                "correlation_limit": 0.4,
            },
            "low_activity": {
                "position_size_multiplier": 0.02,  # 2% of normal (very conservative)
                "max_trades_per_hour": 2,
                "max_daily_loss_pct": 1.0,
                "stop_loss_pct": 0.3,
                "take_profit_pct": 0.8,
                "max_position_age_hours": 6,
                "min_trade_quality_score": 0.7,  # Higher quality threshold
                "gas_price_multiplier_limit": 1.0,
                "volatility_multiplier": 0.7,
                "correlation_limit": 0.8,  # Stricter correlation limits
            },
        }

        # Global risk limits
        self.global_limits = {
            "max_concurrent_positions": 50,
            "max_daily_loss_usd": 500.0,
            "max_single_position_usd": 100.0,
            "circuit_breaker_trigger_pct": 5.0,  # Trigger circuit breaker at 5% loss
            "circuit_breaker_duration_hours": 2,
        }

        # Market condition tracking
        self.market_conditions = {
            "volatility_index": 1.0,  # Rolling volatility measure
            "gas_price_multiplier": 1.0,  # Current gas price relative to average
            "market_liquidity_score": 1.0,  # Overall market liquidity
            "last_update": datetime.now(),
        }

        # Position tracking
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        self.daily_stats = {
            "trades_today": 0,
            "loss_today_usd": 0.0,
            "profit_today_usd": 0.0,
            "last_reset": datetime.now().date(),
        }

        # Circuit breaker state
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None

        # Performance tracking
        self.performance_history: List[Dict[str, Any]] = []
        self.max_performance_history = 1000

        logger.info("🎯 Market maker risk manager initialized")

    async def evaluate_trade_risk(
        self,
        wallet_address: str,
        trade_data: Dict[str, Any],
        market_conditions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate comprehensive risk for a potential market maker trade.

        Args:
            wallet_address: Wallet to copy from
            trade_data: Trade details (amount, side, market, etc.)
            market_conditions: Current market conditions

        Returns:
            Risk evaluation with position sizing and trade decision
        """

        evaluation = {
            "wallet_address": wallet_address,
            "should_execute": False,
            "position_size_usd": 0.0,
            "stop_loss_usd": 0.0,
            "take_profit_usd": 0.0,
            "risk_score": 1.0,  # Higher = more risky
            "quality_score": 0.0,
            "rejection_reason": None,
            "risk_metrics": {},
            "recommendations": [],
        }

        try:
            # Update market conditions if provided
            if market_conditions:
                self._update_market_conditions(market_conditions)

            # Get wallet classification
            wallet_info = await self.detector.get_wallet_classification_report(wallet_address)
            if "error" in wallet_info:
                evaluation["rejection_reason"] = (
                    f"Wallet classification error: {wallet_info['error']}"
                )
                return evaluation

            wallet_type = wallet_info.get("classification", "unknown")
            config = self.wallet_type_configs.get(
                wallet_type, self.wallet_type_configs["directional_trader"]
            )

            # Check circuit breaker
            if self._is_circuit_breaker_active():
                evaluation["rejection_reason"] = "Circuit breaker active"
                return evaluation

            # Calculate trade quality score
            quality_score = await self._calculate_trade_quality_score(
                wallet_address, trade_data, wallet_info
            )
            evaluation["quality_score"] = quality_score

            # Apply quality threshold filter
            if quality_score < config["min_trade_quality_score"]:
                evaluation["rejection_reason"] = (
                    f"Trade quality score {quality_score:.2f} below threshold"
                )
                return evaluation

            # Check trade frequency limits
            if not self._check_trade_frequency_limits(wallet_address, config):
                evaluation["rejection_reason"] = "Trade frequency limit exceeded"
                return evaluation

            # Calculate adaptive position size
            position_size = await self._calculate_adaptive_position_size(
                wallet_address, trade_data, config, quality_score
            )
            evaluation["position_size_usd"] = position_size

            # Check position size limits
            if position_size <= 0:
                evaluation["rejection_reason"] = "Position size calculation failed"
                return evaluation

            if position_size > self.global_limits["max_single_position_usd"]:
                evaluation["rejection_reason"] = (
                    f"Position size {position_size:.2f} exceeds maximum"
                )
                return evaluation

            # Calculate stop loss and take profit levels
            stop_loss, take_profit = self._calculate_risk_levels(trade_data, position_size, config)
            evaluation["stop_loss_usd"] = stop_loss
            evaluation["take_profit_usd"] = take_profit

            # Calculate overall risk score
            risk_score = self._calculate_overall_risk_score(
                position_size, stop_loss, take_profit, config, quality_score
            )
            evaluation["risk_score"] = risk_score

            # Check correlation limits
            if await self._check_correlation_limits(wallet_address, trade_data):
                evaluation["rejection_reason"] = "Correlation limit exceeded"
                return evaluation

            # Final risk assessment
            evaluation["should_execute"] = True
            evaluation["risk_metrics"] = {
                "wallet_type": wallet_type,
                "quality_score": quality_score,
                "position_size_pct": position_size / self._get_base_position_size() * 100,
                "stop_loss_pct": config["stop_loss_pct"],
                "take_profit_pct": config["take_profit_pct"],
                "risk_reward_ratio": (take_profit / position_size) / (stop_loss / position_size),
                "volatility_adjustment": self.market_conditions["volatility_index"],
                "gas_price_multiplier": self.market_conditions["gas_price_multiplier"],
            }

            evaluation["recommendations"] = self._generate_risk_recommendations(evaluation, config)

            logger.info(f"🎯 Risk evaluation for {wallet_address[:8]}...: " ".2f")

        except Exception as e:
            logger.error(f"Error evaluating trade risk for {wallet_address}: {e}")
            evaluation["rejection_reason"] = f"Risk evaluation error: {e}"

        return evaluation

    async def _calculate_trade_quality_score(
        self, wallet_address: str, trade_data: Dict[str, Any], wallet_info: Dict[str, Any]
    ) -> float:
        """
        Calculate comprehensive trade quality score (0-1).

        Factors:
        - Wallet confidence score
        - Trade amount vs typical position size
        - Gas price efficiency
        - Market liquidity
        - Timing quality
        - Profitability potential
        """

        score = 0.0
        factors = 0

        # Wallet confidence factor (30% weight)
        confidence = wallet_info.get("confidence_score", 0.5)
        score += confidence * 0.3
        factors += 0.3

        # Trade size appropriateness (20% weight)
        trade_amount = abs(float(trade_data.get("amount", 0)))
        metrics = wallet_info.get("metrics_snapshot", {}).get("position_metrics", {})
        avg_position_size = metrics.get("avg_position_size", trade_amount)

        if avg_position_size > 0:
            size_ratio = min(trade_amount / avg_position_size, 2.0)  # Cap at 2x
            size_score = 1.0 - abs(size_ratio - 1.0)  # Perfect score at 1:1 ratio
            score += size_score * 0.2
            factors += 0.2

        # Gas price efficiency (15% weight)
        gas_price = trade_data.get("gas_price", 0)
        if gas_price > 0:
            gas_multiplier = self.market_conditions["gas_price_multiplier"]
            gas_efficiency = max(0, 1.0 - (gas_multiplier - 1.0) / 2.0)  # Penalty for high gas
            score += gas_efficiency * 0.15
            factors += 0.15

        # Market liquidity factor (15% weight)
        market_liquidity = self.market_conditions["market_liquidity_score"]
        score += market_liquidity * 0.15
        factors += 0.15

        # Timing quality (10% weight)
        # Prefer trades during normal market hours, avoid extreme times
        timestamp = trade_data.get("timestamp")
        if timestamp:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            hour = timestamp.hour
            # Optimal trading hours: 8:00-20:00 UTC (16 hours)
            if 8 <= hour <= 20:
                timing_score = 1.0
            elif 6 <= hour <= 22:
                timing_score = 0.8
            else:
                timing_score = 0.6
            score += timing_score * 0.1
            factors += 0.1

        # Market impact assessment (10% weight)
        # Estimate market impact based on trade size and market conditions
        market_cap = trade_data.get("market_cap", 100000)  # Default $100k market
        market_impact = min(trade_amount / market_cap, 0.1)  # Cap at 10%
        impact_score = 1.0 - market_impact * 10  # Lower impact = higher score
        score += impact_score * 0.1
        factors += 0.1

        # Normalize score
        final_score = score / factors if factors > 0 else 0.0
        return min(final_score, 1.0)

    def _check_trade_frequency_limits(self, wallet_address: str, config: Dict[str, Any]) -> bool:
        """Check if trade frequency limits are exceeded for this wallet."""

        max_trades_per_hour = config["max_trades_per_hour"]

        # Count trades in last hour for this wallet
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_trades = [
            pos
            for pos in self.active_positions.values()
            if pos.get("wallet_address") == wallet_address
            and pos.get("entry_time", datetime.min) > one_hour_ago
        ]

        return len(recent_trades) < max_trades_per_hour

    async def _calculate_adaptive_position_size(
        self,
        wallet_address: str,
        trade_data: Dict[str, Any],
        config: Dict[str, Any],
        quality_score: float,
    ) -> float:
        """
        Calculate adaptive position size based on wallet type and conditions.

        Factors:
        - Base position size from settings
        - Wallet type multiplier
        - Quality score adjustment
        - Volatility adjustment
        - Account balance and risk limits
        """

        try:
            # Get base position size from settings
            base_size = self._get_base_position_size()

            # Apply wallet type multiplier
            wallet_multiplier = config["position_size_multiplier"]

            # Quality score adjustment (higher quality = larger size)
            quality_multiplier = 0.5 + (quality_score * 0.5)  # 0.5-1.0 range

            # Volatility adjustment (higher volatility = smaller size)
            volatility_multiplier = (
                config["volatility_multiplier"] * self.market_conditions["volatility_index"]
            )

            # Calculate final position size
            position_size = (
                base_size * wallet_multiplier * quality_multiplier * volatility_multiplier
            )

            # Apply global limits
            position_size = min(position_size, self.global_limits["max_single_position_usd"])

            # Ensure minimum trade size
            min_trade_size = 1.0  # $1 minimum
            position_size = max(position_size, min_trade_size)

            # Check account balance
            available_balance = await self._get_available_balance()
            position_size = min(
                position_size, available_balance * 0.1
            )  # Max 10% of available balance

            return position_size

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0

    def _calculate_risk_levels(
        self, trade_data: Dict[str, Any], position_size: float, config: Dict[str, Any]
    ) -> Tuple[float, float]:
        """Calculate stop loss and take profit levels."""

        trade_data.get("price", 1.0)  # Default $1 if not provided

        # Stop loss calculation
        stop_loss_pct = config["stop_loss_pct"] / 100.0
        stop_loss_amount = position_size * stop_loss_pct

        # Take profit calculation
        take_profit_pct = config["take_profit_pct"] / 100.0
        take_profit_amount = position_size * take_profit_pct

        return stop_loss_amount, take_profit_amount

    def _calculate_overall_risk_score(
        self,
        position_size: float,
        stop_loss: float,
        take_profit: float,
        config: Dict[str, Any],
        quality_score: float,
    ) -> float:
        """Calculate overall risk score for the trade."""

        risk_score = 0.0

        # Position size risk (larger position = higher risk)
        base_size = self._get_base_position_size()
        size_ratio = position_size / base_size if base_size > 0 else 1.0
        risk_score += min(size_ratio * 0.3, 0.5)  # Cap at 0.5

        # Stop loss risk (tighter stop = lower risk)
        stop_loss_pct = config["stop_loss_pct"]
        stop_loss_score = max(0, (5.0 - stop_loss_pct) / 5.0)  # Prefer tighter stops
        risk_score += stop_loss_score * 0.2

        # Quality score contribution (lower quality = higher risk)
        quality_risk = (1.0 - quality_score) * 0.2
        risk_score += quality_risk

        # Market condition risk
        volatility_risk = (self.market_conditions["volatility_index"] - 1.0) * 0.1
        risk_score += max(volatility_risk, 0)

        return min(risk_score, 1.0)

    async def _check_correlation_limits(
        self, wallet_address: str, trade_data: Dict[str, Any]
    ) -> bool:
        """Check if adding this position would exceed correlation limits."""

        # Get market/condition ID
        market_id = trade_data.get("market_id") or trade_data.get("condition_id", "unknown")

        # Count positions in same market
        market_positions = [
            pos for pos in self.active_positions.values() if pos.get("market_id") == market_id
        ]

        if len(market_positions) >= 3:  # Limit to 3 positions per market
            return True

        # Check wallet correlation (simplified - would need more sophisticated correlation analysis)
        wallet_positions = [
            pos
            for pos in self.active_positions.values()
            if pos.get("wallet_address") == wallet_address
        ]

        return len(wallet_positions) >= 2  # Limit to 2 positions per wallet

    def _generate_risk_recommendations(
        self, evaluation: Dict[str, Any], config: Dict[str, Any]
    ) -> List[str]:
        """Generate risk management recommendations."""

        recommendations = []

        risk_score = evaluation.get("risk_score", 1.0)
        quality_score = evaluation.get("quality_score", 0.0)

        if risk_score > 0.7:
            recommendations.append("⚠️ High risk trade - consider reducing position size")
        elif risk_score < 0.3:
            recommendations.append("✅ Low risk trade - suitable for position sizing")

        if quality_score > 0.8:
            recommendations.append("🎯 High quality trade from reliable wallet")
        elif quality_score < 0.5:
            recommendations.append("⚠️ Lower quality trade - monitor closely")

        if config["position_size_multiplier"] < 0.1:
            recommendations.append("📏 Very small position size due to market maker behavior")

        if config["max_position_age_hours"] < 4:
            recommendations.append("⏰ Short holding period expected - quick profit taking")

        return recommendations

    def _get_base_position_size(self) -> float:
        """Get base position size from settings."""
        return settings.risk.max_position_size

    async def _get_available_balance(self) -> float:
        """Get available account balance (placeholder - implement based on your wallet integration)."""
        # This should be implemented based on your wallet balance checking logic
        return 1000.0  # Default placeholder

    def _is_circuit_breaker_active(self) -> bool:
        """Check if circuit breaker is currently active."""
        if not self.circuit_breaker_active:
            return False

        if self.circuit_breaker_until and datetime.now() > self.circuit_breaker_until:
            self.circuit_breaker_active = False
            self.circuit_breaker_until = None
            logger.info("🔄 Circuit breaker deactivated")
            return False

        return True

    def _update_market_conditions(self, conditions: Dict[str, Any]):
        """Update current market conditions."""

        # Update volatility index (rolling average)
        new_volatility = conditions.get("volatility", 1.0)
        self.market_conditions["volatility_index"] = (
            self.market_conditions["volatility_index"] * 0.9 + new_volatility * 0.1
        )

        # Update gas price multiplier
        new_gas_multiplier = conditions.get("gas_price_multiplier", 1.0)
        self.market_conditions["gas_price_multiplier"] = new_gas_multiplier

        # Update liquidity score
        new_liquidity = conditions.get("liquidity_score", 1.0)
        self.market_conditions["market_liquidity_score"] = new_liquidity

        self.market_conditions["last_update"] = datetime.now()

    def activate_circuit_breaker(self, reason: str, duration_hours: int = None):
        """Activate circuit breaker to pause trading."""

        if duration_hours is None:
            duration_hours = self.global_limits["circuit_breaker_duration_hours"]

        self.circuit_breaker_active = True
        self.circuit_breaker_until = datetime.now() + timedelta(hours=duration_hours)

        logger.warning(
            f"🚨 Circuit breaker activated: {reason} (until {self.circuit_breaker_until})"
        )

    def update_position_status(self, position_id: str, status_update: Dict[str, Any]):
        """Update position status and check for risk limit breaches."""

        if position_id not in self.active_positions:
            return

        position = self.active_positions[position_id]
        position.update(status_update)

        # Check for stop loss or take profit triggers
        current_pnl = position.get("current_pnl", 0.0)

        if current_pnl <= -position["stop_loss_usd"]:
            logger.warning(f"🛑 Stop loss triggered for position {position_id}")
            # Implement position closure logic here

        elif current_pnl >= position["take_profit_usd"]:
            logger.info(f"💰 Take profit triggered for position {position_id}")
            # Implement position closure logic here

        # Check daily loss limits
        if current_pnl < 0:
            self.daily_stats["loss_today_usd"] += abs(current_pnl)

            if self.daily_stats["loss_today_usd"] > self.global_limits["max_daily_loss_usd"]:
                self.activate_circuit_breaker("Daily loss limit exceeded")

    def record_trade_performance(self, trade_result: Dict[str, Any]):
        """Record trade performance for analysis."""

        performance_entry = {
            "timestamp": datetime.now().isoformat(),
            "wallet_address": trade_result.get("wallet_address", "unknown"),
            "wallet_type": trade_result.get("wallet_type", "unknown"),
            "position_size_usd": trade_result.get("position_size_usd", 0.0),
            "pnl_usd": trade_result.get("pnl_usd", 0.0),
            "holding_time_hours": trade_result.get("holding_time_hours", 0.0),
            "quality_score": trade_result.get("quality_score", 0.0),
            "risk_score": trade_result.get("risk_score", 0.0),
            "exit_reason": trade_result.get("exit_reason", "unknown"),
        }

        self.performance_history.append(performance_entry)

        # Maintain history size
        if len(self.performance_history) > self.max_performance_history:
            self.performance_history = self.performance_history[-self.max_performance_history :]

        # Update daily stats
        if trade_result.get("pnl_usd", 0) > 0:
            self.daily_stats["profit_today_usd"] += trade_result["pnl_usd"]
        else:
            self.daily_stats["loss_today_usd"] += abs(trade_result.get("pnl_usd", 0))

        self.daily_stats["trades_today"] += 1

    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get comprehensive risk metrics."""

        # Calculate performance metrics
        total_trades = len(self.performance_history)
        if total_trades > 0:
            profitable_trades = sum(1 for t in self.performance_history if t["pnl_usd"] > 0)
            win_rate = profitable_trades / total_trades

            total_pnl = sum(t["pnl_usd"] for t in self.performance_history)
            avg_win = sum(t["pnl_usd"] for t in self.performance_history if t["pnl_usd"] > 0) / max(
                profitable_trades, 1
            )
            avg_loss = abs(
                sum(t["pnl_usd"] for t in self.performance_history if t["pnl_usd"] < 0)
            ) / max(total_trades - profitable_trades, 1)

            profit_factor = avg_win / avg_loss if avg_loss > 0 else float("inf")
        else:
            win_rate = 0.0
            total_pnl = 0.0
            profit_factor = 0.0

        return {
            "circuit_breaker_active": self.circuit_breaker_active,
            "active_positions": len(self.active_positions),
            "daily_stats": self.daily_stats.copy(),
            "market_conditions": self.market_conditions.copy(),
            "performance_metrics": {
                "total_trades": total_trades,
                "win_rate": win_rate,
                "total_pnl_usd": total_pnl,
                "profit_factor": profit_factor,
                "avg_trade_size": (
                    np.mean([t["position_size_usd"] for t in self.performance_history])
                    if self.performance_history
                    else 0
                ),
            },
            "risk_limits": self.global_limits.copy(),
        }

    def update_risk_parameters(self, wallet_type: str, parameters: Dict[str, Any]):
        """Update risk parameters for a specific wallet type."""

        if wallet_type in self.wallet_type_configs:
            self.wallet_type_configs[wallet_type].update(parameters)
            logger.info(f"Updated risk parameters for {wallet_type}: {parameters}")
        else:
            logger.warning(f"Unknown wallet type: {wallet_type}")

    def reset_daily_stats(self):
        """Reset daily statistics."""
        self.daily_stats = {
            "trades_today": 0,
            "loss_today_usd": 0.0,
            "profit_today_usd": 0.0,
            "last_reset": datetime.now().date(),
        }
        logger.info("📊 Daily statistics reset")

    # ===== POSITION SIZING STRATEGIES =====

    async def calculate_kelly_position_size(
        self,
        win_probability: float,
        win_loss_ratio: float,
        wallet_type: str,
        base_position_size: float,
    ) -> float:
        """
        Calculate position size using Kelly Criterion adapted for wallet types.

        Kelly Criterion: f = (bp - q) / b
        Where:
        - f = fraction of capital to invest
        - b = odds received (win_loss_ratio)
        - p = probability of winning
        - q = probability of losing (1-p)
        """

        # Adjust win probability based on wallet type confidence
        type_multipliers = {
            "market_maker": 0.7,  # Conservative adjustment for MMs
            "arbitrage_trader": 0.8,  # Slightly more aggressive
            "high_frequency_trader": 0.6,  # Very conservative
            "directional_trader": 1.0,  # No adjustment
            "mixed_trader": 0.8,
            "low_activity": 0.5,  # Very conservative
        }

        adjusted_win_prob = win_probability * type_multipliers.get(wallet_type, 0.7)

        # Ensure reasonable bounds
        adjusted_win_prob = max(0.1, min(0.9, adjusted_win_prob))
        win_loss_ratio = max(0.1, min(5.0, win_loss_ratio))

        # Calculate Kelly fraction
        kelly_fraction = (
            adjusted_win_prob * win_loss_ratio - (1 - adjusted_win_prob)
        ) / win_loss_ratio

        # Apply half-Kelly for risk management (more conservative)
        kelly_fraction *= 0.5

        # Ensure positive and reasonable fraction
        kelly_fraction = max(0.01, min(0.25, kelly_fraction))  # 1% to 25% of capital

        position_size = base_position_size * kelly_fraction

        logger.debug(".3f")
        return position_size

    async def calculate_volatility_adjusted_size(
        self,
        base_size: float,
        market_volatility: float,
        position_volatility: float,
        wallet_type: str,
    ) -> float:
        """
        Calculate position size adjusted for market and position volatility.

        Uses a volatility-adjusted formula that reduces size in high volatility conditions.
        """

        # Base volatility adjustment (higher volatility = smaller size)
        volatility_ratio = (
            market_volatility / position_volatility if position_volatility > 0 else 1.0
        )
        volatility_multiplier = 1.0 / max(1.0, volatility_ratio)

        # Wallet type specific volatility sensitivity
        type_sensitivity = {
            "market_maker": 1.5,  # More sensitive to volatility
            "arbitrage_trader": 1.2,
            "high_frequency_trader": 1.8,  # Very sensitive
            "directional_trader": 0.8,  # Less sensitive
            "mixed_trader": 1.0,
            "low_activity": 2.0,  # Extremely sensitive
        }

        sensitivity = type_sensitivity.get(wallet_type, 1.0)
        adjusted_multiplier = volatility_multiplier**sensitivity

        # Apply bounds
        adjusted_multiplier = max(0.1, min(2.0, adjusted_multiplier))

        position_size = base_size * adjusted_multiplier

        return position_size

    async def calculate_correlation_diversified_size(
        self, base_size: float, wallet_address: str, market_id: str, max_correlation: float = 0.7
    ) -> float:
        """
        Calculate position size considering portfolio correlation diversification.

        Reduces size when portfolio becomes too concentrated in correlated positions.
        """

        # Count existing positions in same market
        market_positions = [
            pos
            for pos in self.active_positions.values()
            if pos.get("market_id") == market_id and pos.get("wallet_address") != wallet_address
        ]

        # Count positions from same wallet
        wallet_positions = [
            pos
            for pos in self.active_positions.values()
            if pos.get("wallet_address") == wallet_address
        ]

        # Apply diversification penalties
        market_diversity_penalty = 1.0 / (1.0 + len(market_positions) * 0.2)
        wallet_diversity_penalty = 1.0 / (1.0 + len(wallet_positions) * 0.3)

        # Correlation penalty (simplified - would use actual correlation matrix)
        correlation_penalty = 1.0
        if len(market_positions) > 2:
            correlation_penalty = max_correlation

        diversification_multiplier = (
            market_diversity_penalty * wallet_diversity_penalty * correlation_penalty
        )

        position_size = base_size * diversification_multiplier

        return position_size

    # ===== TRADE FILTERING LOGIC =====

    async def apply_comprehensive_trade_filters(
        self, wallet_address: str, trade_data: Dict[str, Any], wallet_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply comprehensive filtering logic to determine if trade should be executed.

        Returns filter results with detailed reasoning.
        """

        filter_results = {
            "passed_all_filters": True,
            "failed_filters": [],
            "filter_scores": {},
            "recommendations": [],
        }

        wallet_type = wallet_info.get("classification", "unknown")
        config = self.wallet_type_configs.get(
            wallet_type, self.wallet_type_configs["directional_trader"]
        )

        # 1. Minimum Profitability Filter
        profitability_score = await self._calculate_profitability_score(trade_data, wallet_info)
        filter_results["filter_scores"]["profitability"] = profitability_score

        if profitability_score < 0.4:  # Minimum 40% profitability score
            filter_results["passed_all_filters"] = False
            filter_results["failed_filters"].append("minimum_profitability")
            filter_results["recommendations"].append("Trade profitability below threshold")

        # 2. Inventory Rebalancing Detection
        if await self._detect_inventory_rebalancing(wallet_address, trade_data, wallet_info):
            filter_results["passed_all_filters"] = False
            filter_results["failed_filters"].append("inventory_rebalancing")
            filter_results["recommendations"].append(
                "Detected potential inventory rebalancing trade"
            )

        # 3. Gas Price Efficiency Filter
        gas_efficiency = self._calculate_gas_efficiency(trade_data)
        filter_results["filter_scores"]["gas_efficiency"] = gas_efficiency

        if gas_efficiency < config["gas_price_multiplier_limit"]:
            filter_results["passed_all_filters"] = False
            filter_results["failed_filters"].append("gas_price_too_high")
            filter_results["recommendations"].append("Gas price too high for profitable execution")

        # 4. Market Liquidity Filter
        liquidity_score = await self._assess_market_liquidity(trade_data)
        filter_results["filter_scores"]["liquidity"] = liquidity_score

        if liquidity_score < 0.3:  # Minimum liquidity score
            filter_results["passed_all_filters"] = False
            filter_results["failed_filters"].append("insufficient_liquidity")
            filter_results["recommendations"].append("Market liquidity too low for safe execution")

        # 5. Market Impact Filter
        market_impact = self._calculate_market_impact(trade_data)
        filter_results["filter_scores"]["market_impact"] = market_impact

        if market_impact > 0.05:  # Maximum 5% market impact
            filter_results["passed_all_filters"] = False
            filter_results["failed_filters"].append("excessive_market_impact")
            filter_results["recommendations"].append(
                "Trade size would cause excessive market impact"
            )

        # 6. Timing Quality Filter
        timing_score = self._assess_timing_quality(trade_data)
        filter_results["filter_scores"]["timing"] = timing_score

        if timing_score < 0.5:  # Minimum timing quality
            filter_results["passed_all_filters"] = False
            filter_results["failed_filters"].append("poor_timing")
            filter_results["recommendations"].append("Trade timing suboptimal for execution")

        # 7. Wallet Behavior Consistency Filter
        consistency_score = self._assess_wallet_behavior_consistency(
            wallet_address, trade_data, wallet_info
        )
        filter_results["filter_scores"]["consistency"] = consistency_score

        if consistency_score < 0.6:  # Minimum consistency score
            filter_results["passed_all_filters"] = False
            filter_results["failed_filters"].append("inconsistent_behavior")
            filter_results["recommendations"].append(
                "Wallet behavior inconsistent with historical patterns"
            )

        return filter_results

    async def _calculate_profitability_score(
        self, trade_data: Dict[str, Any], wallet_info: Dict[str, Any]
    ) -> float:
        """
        Calculate expected profitability score for the trade.

        Factors:
        - Historical win rate of wallet type
        - Trade size vs typical profitable trades
        - Market conditions
        - Gas costs vs expected returns
        """

        wallet_type = wallet_info.get("classification", "directional_trader")

        # Base win rates by wallet type (would be calculated from historical data)
        base_win_rates = {
            "market_maker": 0.55,  # Slightly above 50% due to edge
            "arbitrage_trader": 0.65,  # Higher win rate for arbitrage
            "high_frequency_trader": 0.52,  # Close to 50/50
            "directional_trader": 0.45,  # Lower for directional
            "mixed_trader": 0.50,
            "low_activity": 0.60,  # Higher for selective trading
        }

        win_rate = base_win_rates.get(wallet_type, 0.50)

        # Adjust for trade size (larger trades tend to be more profitable for MMs)
        trade_amount = abs(float(trade_data.get("amount", 0)))
        avg_position = (
            wallet_info.get("metrics_snapshot", {})
            .get("position_metrics", {})
            .get("avg_position_size", trade_amount)
        )

        size_factor = min(trade_amount / avg_position, 2.0) if avg_position > 0 else 1.0
        size_adjustment = 0.05 * (size_factor - 1.0)  # ±5% adjustment

        # Adjust for market conditions
        market_condition_factor = (
            self.market_conditions["market_liquidity_score"] * 0.1 - 0.05
        )  # ±5% adjustment

        # Gas cost adjustment
        gas_multiplier = self.market_conditions["gas_price_multiplier"]
        gas_adjustment = -0.1 * (gas_multiplier - 1.0)  # -10% per unit gas increase

        profitability_score = win_rate + size_adjustment + market_condition_factor + gas_adjustment
        profitability_score = max(0.1, min(0.9, profitability_score))  # Bound between 10% and 90%

        return profitability_score

    async def _detect_inventory_rebalancing(
        self, wallet_address: str, trade_data: Dict[str, Any], wallet_info: Dict[str, Any]
    ) -> bool:
        """
        Detect potential inventory rebalancing trades.

        Market makers often make small trades to adjust inventory without
        expecting profit, which should be avoided for copying.
        """

        # Check trade size relative to typical profitable trades
        trade_amount = abs(float(trade_data.get("amount", 0)))
        avg_position = (
            wallet_info.get("metrics_snapshot", {})
            .get("position_metrics", {})
            .get("avg_position_size", 0)
        )

        if avg_position > 0 and trade_amount / avg_position < 0.3:
            # Very small trade relative to typical size
            return True

        # Check for rapid alternation (buy then sell quickly)
        # This would require analyzing recent trade history

        # Check for trades at market edges (potential inventory management)
        price = trade_data.get("price", 0)
        if price > 0:
            # Simplified check - trades far from midpoint might be inventory management
            # In practice, this would use order book data
            pass

        # Check timing patterns (end of day inventory adjustment)
        timestamp = trade_data.get("timestamp")
        if timestamp:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            hour = timestamp.hour
            if hour in [23, 0, 1]:  # Late night trades
                return True

        return False

    def _calculate_gas_efficiency(self, trade_data: Dict[str, Any]) -> float:
        """Calculate gas efficiency score."""

        gas_price = trade_data.get("gas_price", 0)
        if gas_price == 0:
            return 1.0  # No gas data = assume efficient

        gas_multiplier = self.market_conditions["gas_price_multiplier"]

        # Efficiency score (lower gas = higher score)
        efficiency = 1.0 / max(1.0, gas_multiplier)

        return efficiency

    async def _assess_market_liquidity(self, trade_data: Dict[str, Any]) -> float:
        """
        Assess market liquidity for safe trade execution.

        Returns liquidity score from 0-1 (higher = more liquid).
        """

        # Get market data (would integrate with actual market data)
        trade_data.get("market_id") or trade_data.get("condition_id", "unknown")
        market_cap = trade_data.get("market_cap", 100000)  # Default $100k
        daily_volume = trade_data.get("daily_volume", market_cap * 0.1)  # Default 10% of market cap

        # Liquidity metrics
        volume_ratio = daily_volume / market_cap  # Volume as % of market cap
        trade_amount = abs(float(trade_data.get("amount", 0)))
        trade_impact = trade_amount / market_cap

        # Composite liquidity score
        liquidity_score = (
            min(volume_ratio * 10, 1.0) * 0.6  # Volume ratio (60% weight)
            + max(0, 1.0 - trade_impact * 20) * 0.4  # Trade impact (40% weight)
        )

        return min(liquidity_score, 1.0)

    def _calculate_market_impact(self, trade_data: Dict[str, Any]) -> float:
        """Calculate estimated market impact of the trade."""

        trade_amount = abs(float(trade_data.get("amount", 0)))
        market_cap = trade_data.get("market_cap", 100000)

        # Simple market impact model
        # Impact = (Trade Size / Market Cap) ^ 0.5 * volatility adjustment
        base_impact = (trade_amount / market_cap) ** 0.5
        volatility_adjustment = self.market_conditions["volatility_index"]

        market_impact = base_impact * volatility_adjustment

        return market_impact

    def _assess_timing_quality(self, trade_data: Dict[str, Any]) -> float:
        """Assess timing quality for trade execution."""

        timestamp = trade_data.get("timestamp")
        if not timestamp:
            return 0.5  # Neutral score if no timestamp

        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        hour = timestamp.hour
        weekday = timestamp.weekday()

        # Optimal trading hours and days
        if weekday < 5:  # Monday-Friday
            if 9 <= hour <= 17:  # Business hours UTC
                timing_score = 1.0
            elif 6 <= hour <= 21:  # Extended hours
                timing_score = 0.8
            else:  # Off-hours
                timing_score = 0.4
        else:  # Weekend
            timing_score = 0.6  # Reduced activity

        return timing_score

    def _assess_wallet_behavior_consistency(
        self, wallet_address: str, trade_data: Dict[str, Any], wallet_info: Dict[str, Any]
    ) -> float:
        """
        Assess how consistent this trade is with wallet's historical behavior.
        """

        # Compare trade amount to typical position size
        trade_amount = abs(float(trade_data.get("amount", 0)))
        metrics = wallet_info.get("metrics_snapshot", {}).get("position_metrics", {})
        avg_position_size = metrics.get("avg_position_size", trade_amount)
        position_std = metrics.get("position_size_std", avg_position_size)

        if avg_position_size > 0:
            size_zscore = abs(trade_amount - avg_position_size) / max(
                position_std, avg_position_size * 0.1
            )
            size_consistency = 1.0 / (1.0 + size_zscore * 0.5)  # Convert z-score to 0-1 scale
        else:
            size_consistency = 0.5

        # Compare trade frequency to typical patterns
        # This would require more historical analysis

        return size_consistency

    # ===== LOSS LIMITATION STRATEGIES =====

    def apply_wallet_specific_circuit_breakers(
        self, wallet_address: str, wallet_type: str, current_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply specialized circuit breakers based on wallet type and performance.

        Returns circuit breaker decision and reasoning.
        """

        config = self.wallet_type_configs.get(
            wallet_type, self.wallet_type_configs["directional_trader"]
        )

        decision = {
            "activate_circuit_breaker": False,
            "circuit_breaker_type": None,
            "reason": "",
            "duration_hours": config.get("circuit_breaker_duration_hours", 2),
            "severity": "low",
        }

        # 1. Daily Loss Limit Circuit Breaker
        daily_loss_pct = current_stats.get("daily_loss_pct", 0)
        max_daily_loss = config["max_daily_loss_pct"]

        if daily_loss_pct >= max_daily_loss:
            decision.update(
                {
                    "activate_circuit_breaker": True,
                    "circuit_breaker_type": "daily_loss_limit",
                    "reason": ".1f",
                    "severity": "high" if daily_loss_pct >= max_daily_loss * 1.5 else "medium",
                }
            )
            return decision

        # 2. Win Rate Circuit Breaker (for market makers)
        if wallet_type == "market_maker":
            recent_win_rate = current_stats.get("recent_win_rate", 0.5)
            if recent_win_rate < 0.45:  # Below 45% win rate
                decision.update(
                    {
                        "activate_circuit_breaker": True,
                        "circuit_breaker_type": "win_rate_below_threshold",
                        "reason": ".1f",
                        "severity": "medium",
                        "duration_hours": 4,  # Longer cooldown for MMs
                    }
                )
                return decision

        # 3. Trade Frequency Circuit Breaker
        trades_last_hour = current_stats.get("trades_last_hour", 0)
        max_trades_hour = config["max_trades_per_hour"]

        if trades_last_hour >= max_trades_hour * 1.5:  # 50% over limit
            decision.update(
                {
                    "activate_circuit_breaker": True,
                    "circuit_breaker_type": "excessive_trade_frequency",
                    "reason": f"Wallet exceeded trade frequency limit ({trades_last_hour}/{max_trades_hour} trades/hour)",
                    "severity": "medium",
                    "duration_hours": 1,
                }
            )
            return decision

        # 4. Drawdown Circuit Breaker
        current_drawdown = current_stats.get("current_drawdown_pct", 0)
        if current_drawdown >= 5.0:  # 5% drawdown
            decision.update(
                {
                    "activate_circuit_breaker": True,
                    "circuit_breaker_type": "portfolio_drawdown",
                    "reason": ".1f",
                    "severity": "high",
                    "duration_hours": 6,
                }
            )
            return decision

        # 5. Correlation Risk Circuit Breaker
        correlation_risk = current_stats.get("correlation_risk_score", 0)
        if correlation_risk >= 0.8:  # High correlation risk
            decision.update(
                {
                    "activate_circuit_breaker": True,
                    "circuit_breaker_type": "high_correlation_risk",
                    "reason": ".2f",
                    "severity": "medium",
                    "duration_hours": 3,
                }
            )
            return decision

        # 6. Time-based Circuit Breaker (end of day for market makers)
        current_hour = datetime.now().hour
        if wallet_type in ["market_maker", "high_frequency_trader"] and current_hour >= 22:
            decision.update(
                {
                    "activate_circuit_breaker": True,
                    "circuit_breaker_type": "end_of_trading_day",
                    "reason": f"End of trading day circuit breaker for {wallet_type} wallet",
                    "severity": "low",
                    "duration_hours": 10,  # Until next morning
                }
            )
            return decision

        return decision

    def calculate_adaptive_stop_loss(
        self,
        wallet_type: str,
        position_size: float,
        entry_price: float,
        market_volatility: float,
        wallet_confidence: float,
    ) -> float:
        """
        Calculate adaptive stop loss based on wallet type and market conditions.

        Returns stop loss amount in USD.
        """

        config = self.wallet_type_configs.get(
            wallet_type, self.wallet_type_configs["directional_trader"]
        )
        base_stop_loss_pct = config["stop_loss_pct"]

        # Volatility adjustment (higher volatility = wider stops)
        volatility_multiplier = 1.0 + (market_volatility - 1.0) * 0.5
        volatility_multiplier = max(0.5, min(2.0, volatility_multiplier))

        # Wallet confidence adjustment (higher confidence = tighter stops)
        confidence_multiplier = 2.0 - wallet_confidence  # Inverted: high confidence = tighter stops
        confidence_multiplier = max(0.5, min(1.5, confidence_multiplier))

        # Calculate final stop loss percentage
        adjusted_stop_loss_pct = base_stop_loss_pct * volatility_multiplier * confidence_multiplier
        adjusted_stop_loss_pct = max(
            0.1, min(5.0, adjusted_stop_loss_pct)
        )  # Bound between 0.1% and 5%

        # Convert to dollar amount
        stop_loss_amount = position_size * (adjusted_stop_loss_pct / 100.0)

        return stop_loss_amount

    def implement_correlation_based_position_limits(
        self, wallet_address: str, market_id: str, proposed_position_size: float
    ) -> float:
        """
        Implement correlation-based position size limits.

        Reduces position size when portfolio becomes too correlated.
        """

        # Get existing positions
        existing_positions = [
            pos
            for pos in self.active_positions.values()
            if pos.get("wallet_address") != wallet_address  # Exclude current wallet
        ]

        if not existing_positions:
            return proposed_position_size

        # Calculate market concentration
        market_positions = [pos for pos in existing_positions if pos.get("market_id") == market_id]
        market_exposure = sum(pos.get("position_size_usd", 0) for pos in market_positions)

        # Calculate wallet concentration
        wallet_positions = [
            pos for pos in existing_positions if pos.get("wallet_address") == wallet_address
        ]
        wallet_exposure = sum(pos.get("position_size_usd", 0) for pos in wallet_positions)

        # Apply concentration limits
        max_market_concentration = 0.3  # Max 30% in single market
        max_wallet_concentration = 0.4  # Max 40% from single wallet

        market_limit = self._get_available_limit(
            market_exposure, proposed_position_size, max_market_concentration
        )
        wallet_limit = self._get_available_limit(
            wallet_exposure, proposed_position_size, max_wallet_concentration
        )

        # Take the more restrictive limit
        final_limit = min(market_limit, wallet_limit, proposed_position_size)

        if final_limit < proposed_position_size:
            logger.info(
                f"📏 Reduced position size from ${proposed_position_size:.2f} to ${final_limit:.2f} "
                ".2f"
            )

        return final_limit

    def _get_available_limit(
        self, current_exposure: float, proposed_size: float, max_concentration: float
    ) -> float:
        """Calculate available limit based on current exposure and max concentration."""

        total_portfolio_value = self._get_total_portfolio_value()
        if total_portfolio_value <= 0:
            return proposed_size

        max_allowed = total_portfolio_value * max_concentration
        available_capacity = max(0, max_allowed - current_exposure)

        return min(proposed_size, available_capacity)

    def _get_total_portfolio_value(self) -> float:
        """Get total portfolio value (simplified - would integrate with actual balance tracking)."""
        # This should be implemented based on your portfolio tracking
        return 10000.0  # Default placeholder

    def detect_unusual_patterns(
        self, wallet_address: str, trade_data: Dict[str, Any], wallet_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect unusual trading patterns that may indicate risk.

        Returns anomaly detection results.
        """

        anomalies = {"detected_anomalies": [], "risk_level": "low", "recommendations": []}

        wallet_type = wallet_info.get("classification", "unknown")
        metrics = wallet_info.get("metrics_snapshot", {})

        # 1. Sudden Volume Spike Detection
        trade_amount = abs(float(trade_data.get("amount", 0)))
        avg_volume = metrics.get("position_metrics", {}).get("avg_position_size", trade_amount)

        if avg_volume > 0:
            volume_ratio = trade_amount / avg_volume
            if volume_ratio > 3.0:  # 3x normal volume
                anomalies["detected_anomalies"].append("volume_spike")
                anomalies["recommendations"].append(
                    "Unusual volume spike detected - reduce position size"
                )

        # 2. Timing Anomaly Detection
        timestamp = trade_data.get("timestamp")
        if timestamp:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            # Check for trades outside normal hours for wallet type
            hour = timestamp.hour
            if wallet_type == "market_maker" and hour in [2, 3, 4, 5, 6]:  # Very early morning
                anomalies["detected_anomalies"].append("unusual_timing")
                anomalies["recommendations"].append("Trade at unusual hour for market maker")

        # 3. Price Anomaly Detection
        price = trade_data.get("price", 0)
        if price > 0:
            # Simplified price anomaly check (would use statistical analysis)
            # Check if price is at extreme percentiles
            pass

        # 4. Frequency Anomaly Detection
        recent_trades = len(
            [
                pos
                for pos in self.active_positions.values()
                if pos.get("wallet_address") == wallet_address
                and pos.get("entry_time", datetime.min) > datetime.now() - timedelta(hours=1)
            ]
        )

        max_hourly = self.wallet_type_configs.get(wallet_type, {}).get("max_trades_per_hour", 10)
        if recent_trades >= max_hourly:
            anomalies["detected_anomalies"].append("frequency_anomaly")
            anomalies["recommendations"].append("Excessive trading frequency detected")

        # Determine overall risk level
        anomaly_count = len(anomalies["detected_anomalies"])
        if anomaly_count >= 3:
            anomalies["risk_level"] = "high"
        elif anomaly_count >= 1:
            anomalies["risk_level"] = "medium"

        return anomalies

    # ===== PROFIT CAPTURE STRATEGIES =====

    def calculate_adaptive_take_profit(
        self,
        wallet_type: str,
        position_size: float,
        entry_price: float,
        market_volatility: float,
        time_held_hours: float = 0,
    ) -> Dict[str, Any]:
        """
        Calculate adaptive take profit levels based on wallet type and conditions.

        Returns take profit configuration with multiple targets.
        """

        config = self.wallet_type_configs.get(
            wallet_type, self.wallet_type_configs["directional_trader"]
        )
        base_take_profit_pct = config["take_profit_pct"]

        # Time-based adjustment (longer holding = higher targets for some types)
        time_multiplier = 1.0
        if wallet_type in ["directional_trader", "mixed_trader"]:
            time_multiplier = 1.0 + (time_held_hours * 0.01)  # +1% per hour held
            time_multiplier = min(time_multiplier, 1.5)  # Cap at 50% increase

        # Volatility adjustment (higher volatility = higher targets for MMs)
        volatility_multiplier = 1.0
        if wallet_type == "market_maker":
            volatility_multiplier = (
                1.0 + (market_volatility - 1.0) * 0.3
            )  # +30% per unit volatility
        else:
            volatility_multiplier = max(
                0.8, 2.0 - market_volatility
            )  # Lower targets in high volatility

        # Calculate final take profit percentage
        adjusted_tp_pct = base_take_profit_pct * time_multiplier * volatility_multiplier
        adjusted_tp_pct = max(0.1, min(10.0, adjusted_tp_pct))  # Bound between 0.1% and 10%

        # Convert to dollar amount
        take_profit_amount = position_size * (adjusted_tp_pct / 100.0)

        # Calculate multiple profit targets for scaling out
        profit_targets = self._calculate_scaled_profit_targets(position_size, adjusted_tp_pct)

        return {
            "take_profit_pct": adjusted_tp_pct,
            "take_profit_amount": take_profit_amount,
            "profit_targets": profit_targets,
            "time_based_exit": config["max_position_age_hours"],
            "trailing_stop_enabled": wallet_type in ["market_maker", "high_frequency_trader"],
            "scaling_strategy": "scale_out" if len(profit_targets) > 1 else "all_out",
        }

    def _calculate_scaled_profit_targets(
        self, position_size: float, target_pct: float
    ) -> List[Dict[str, Any]]:
        """
        Calculate scaled profit targets for partial position exits.

        Returns list of profit targets with size and price levels.
        """

        # For smaller positions, use single target
        if position_size < 10:  # $10 threshold
            return [{"percentage": 100.0, "amount": position_size, "target_price_pct": target_pct}]

        # Scale out strategy: 25% at 40% target, 25% at 60% target, 50% at 100% target
        targets = [
            {
                "percentage": 25.0,
                "amount": position_size * 0.25,
                "target_price_pct": target_pct * 0.4,
            },
            {
                "percentage": 25.0,
                "amount": position_size * 0.25,
                "target_price_pct": target_pct * 0.6,
            },
            {"percentage": 50.0, "amount": position_size * 0.5, "target_price_pct": target_pct},
        ]

        return targets

    def implement_trailing_stop_logic(
        self, position_data: Dict[str, Any], current_price: float, highest_price: float
    ) -> Dict[str, Any]:
        """
        Implement trailing stop logic for profit protection.

        Returns trailing stop update decision.
        """

        wallet_type = position_data.get("wallet_type", "directional_trader")
        config = self.wallet_type_configs.get(
            wallet_type, self.wallet_type_configs["directional_trader"]
        )

        decision = {
            "adjust_trailing_stop": False,
            "new_stop_price": position_data.get("trailing_stop_price", 0),
            "reason": "",
            "exit_signal": False,
        }

        entry_price = position_data.get("entry_price", current_price)
        position_side = position_data.get("side", "BUY")

        # Calculate profit percentage
        if position_side == "BUY":
            profit_pct = (current_price - entry_price) / entry_price * 100
        else:  # SELL position
            profit_pct = (entry_price - current_price) / entry_price * 100

        # Minimum profit threshold for trailing stop activation
        min_profit_threshold = config["take_profit_pct"] * 0.5  # 50% of take profit target

        if profit_pct >= min_profit_threshold:
            # Calculate trailing stop distance based on profit level
            trailing_pct = max(0.5, profit_pct * 0.2)  # 0.5% to 20% trailing stop

            if position_side == "BUY":
                new_stop_price = current_price * (1 - trailing_pct / 100)
                # Move stop up if price has moved higher
                if new_stop_price > decision["new_stop_price"]:
                    decision.update(
                        {
                            "adjust_trailing_stop": True,
                            "new_stop_price": new_stop_price,
                            "reason": ".2f",
                        }
                    )
            else:  # SELL position
                new_stop_price = current_price * (1 + trailing_pct / 100)
                # Move stop down if price has moved lower
                if new_stop_price < decision["new_stop_price"] or decision["new_stop_price"] == 0:
                    decision.update(
                        {
                            "adjust_trailing_stop": True,
                            "new_stop_price": new_stop_price,
                            "reason": ".2f",
                        }
                    )

        # Check for exit signal
        current_stop = decision["new_stop_price"]
        if current_stop > 0:
            if position_side == "BUY" and current_price <= current_stop:
                decision["exit_signal"] = True
                decision["reason"] = f"Trailing stop triggered at ${current_stop:.4f}"
            elif position_side == "SELL" and current_price >= current_stop:
                decision["exit_signal"] = True
                decision["reason"] = f"Trailing stop triggered at ${current_stop:.4f}"

        return decision

    def calculate_time_based_exit_probability(
        self, wallet_type: str, time_held_hours: float, position_profit_pct: float
    ) -> float:
        """
        Calculate probability of time-based exit based on wallet behavior.

        Market makers tend to exit positions quickly, while directional traders hold longer.
        """

        config = self.wallet_type_configs.get(
            wallet_type, self.wallet_type_configs["directional_trader"]
        )
        max_age_hours = config["max_position_age_hours"]

        # Base probability increases with time held
        time_factor = time_held_hours / max_age_hours
        time_factor = min(time_factor, 1.0)

        # Profit factor (higher profit = higher exit probability)
        profit_factor = max(0, position_profit_pct / config["take_profit_pct"])
        profit_factor = min(profit_factor, 1.0)

        # Wallet-specific behavior
        if wallet_type == "market_maker":
            # Market makers exit quickly, especially at small profits
            exit_probability = time_factor * 0.8 + profit_factor * 0.2
        elif wallet_type == "high_frequency_trader":
            exit_probability = time_factor * 0.9 + profit_factor * 0.1
        elif wallet_type == "directional_trader":
            # Directional traders hold longer for larger moves
            exit_probability = time_factor * 0.3 + profit_factor * 0.7
        else:
            exit_probability = time_factor * 0.5 + profit_factor * 0.5

        return min(exit_probability, 1.0)
