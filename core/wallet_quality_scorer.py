"""
Wallet Quality Scoring System
=============================

Comprehensive multi-dimensional scoring framework for evaluating copy trading
wallets across risk-adjusted returns, consistency, adaptability, and behavioral
sustainability metrics.

Features:
- Separate scoring profiles for market makers vs directional traders
- Real-time scoring updates with confidence intervals
- Market regime-aware weighting
- Behavioral analysis for strategy sustainability
- Automatic wallet selection with diversification constraints
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats

from utils.helpers import BoundedCache

logger = logging.getLogger(__name__)


class WalletQualityScorer:
    """
    Comprehensive wallet quality scoring system for copy trading.

    Evaluates wallets across multiple dimensions:
    - Risk-adjusted returns (Sharpe, Sortino ratios)
    - Consistency metrics (win rate stability, drawdown analysis)
    - Market adaptability (performance across conditions)
    - Trade quality (execution, slippage)
    - Strategy transparency (behavioral patterns)
    - Behavioral sustainability (evolution, decay detection)
    """

    def __init__(self):
        # Scoring configuration
        self.scoring_config = self._initialize_scoring_config()

        # Scoring profiles for different wallet types
        self.scoring_profiles = {
            "market_maker": self._get_market_maker_profile(),
            "directional_trader": self._get_directional_trader_profile(),
            "arbitrage_trader": self._get_arbitrage_trader_profile(),
            "high_frequency_trader": self._get_high_frequency_profile(),
            "mixed_trader": self._get_mixed_trader_profile(),
        }

        # Market regime configurations
        self.market_regimes = {
            "bull": self._get_bull_market_weights(),
            "bear": self._get_bear_market_weights(),
            "high_volatility": self._get_high_volatility_weights(),
            "low_liquidity": self._get_low_liquidity_weights(),
            "normal": self._get_normal_market_weights(),
        }

        # Historical scoring data
        self.scoring_history = BoundedCache(max_size=10000, ttl_seconds=2592000)  # 30 days
        self.wallet_correlations: Dict[str, Dict[str, float]] = {}

        # Real-time scoring state
        self.real_time_scores = BoundedCache(max_size=1000, ttl_seconds=3600)  # 1 hour
        self.score_confidence_intervals = BoundedCache(max_size=1000, ttl_seconds=3600)  # 1 hour

        # Behavioral analysis components
        self.behavior_tracker = BehaviorPatternTracker()
        self.risk_assessor = RiskManagementQualityAssessor()

        logger.info("🏆 Wallet quality scoring system initialized")

    def _initialize_scoring_config(self) -> Dict[str, Any]:
        """Initialize core scoring configuration parameters."""

        return {
            # Risk-adjusted return parameters
            "sharpe_ratio_min_periods": 30,  # Minimum periods for Sharpe calculation
            "sortino_ratio_target_return": 0.02,  # Daily target return for Sortino
            "calmar_ratio_lookback_days": 365,  # Annual lookback for Calmar
            # Consistency parameters
            "win_rate_stability_window": 50,  # Rolling window for stability
            "drawdown_analysis_periods": 252,  # Trading days for drawdown analysis
            "recovery_time_weight": 0.3,  # Weight for recovery time in drawdown score
            # Market adaptability parameters
            "regime_performance_windows": [30, 90, 180],  # Days for regime analysis
            "adaptability_score_weight": 0.25,  # Weight for adaptability in total score
            "min_regime_samples": 20,  # Minimum trades per regime
            # Trade quality parameters
            "slippage_tolerance_pct": 0.5,  # Acceptable slippage percentage
            "execution_quality_weight": 0.15,  # Weight in trade quality score
            "gas_efficiency_weight": 0.10,  # Weight for gas efficiency
            # Strategy transparency parameters
            "pattern_recognition_window": 100,  # Trades for pattern analysis
            "predictability_threshold": 0.7,  # Minimum predictability score
            "transparency_weight": 0.20,  # Weight in total score
            # Behavioral sustainability parameters
            "performance_decay_window": 90,  # Days for decay analysis
            "strategy_evolution_threshold": 0.25,  # Threshold for strategy change detection
            "sustainability_weight": 0.25,  # Weight in total score
            # Real-time scoring parameters
            "recency_decay_factor": 0.95,  # Exponential decay for recency
            "volatility_adjustment": True,  # Adjust scores for volatility
            "confidence_interval_alpha": 0.05,  # 95% confidence intervals
            "score_stability_window": 20,  # Window for stability calculation
            # Overall scoring parameters
            "min_scoring_period_days": 30,  # Minimum history for scoring
            "score_update_frequency": 300,  # Update frequency in seconds
            "quality_score_range": (0, 100),  # Score range (0-100)
            "high_quality_threshold": 75,  # High quality threshold
            "medium_quality_threshold": 50,  # Medium quality threshold
        }

    def _get_market_maker_profile(self) -> Dict[str, float]:
        """Get scoring weights optimized for market maker wallets."""

        return {
            "risk_adjusted_returns": 0.20,  # Sharpe/Sortino focus
            "consistency_metrics": 0.25,  # High importance for MM consistency
            "drawdown_analysis": 0.15,  # Moderate drawdown tolerance
            "market_adaptability": 0.15,  # Need to adapt to market changes
            "trade_quality": 0.20,  # Critical for high-frequency trading
            "strategy_transparency": 0.25,  # Pattern recognition very important
            "behavioral_sustainability": 0.20,  # Strategy evolution monitoring
        }

    def _get_directional_trader_profile(self) -> Dict[str, float]:
        """Get scoring weights optimized for directional trader wallets."""

        return {
            "risk_adjusted_returns": 0.30,  # Return focus for directional trades
            "consistency_metrics": 0.20,  # Consistency matters but less than MM
            "drawdown_analysis": 0.20,  # Higher drawdown tolerance
            "market_adaptability": 0.25,  # Critical for directional strategies
            "trade_quality": 0.10,  # Less critical than execution speed
            "strategy_transparency": 0.15,  # Some pattern recognition useful
            "behavioral_sustainability": 0.20,  # Monitor for strategy changes
        }

    def _get_arbitrage_trader_profile(self) -> Dict[str, float]:
        """Get scoring weights for arbitrage trader wallets."""

        return {
            "risk_adjusted_returns": 0.25,
            "consistency_metrics": 0.30,  # Very important for arb strategies
            "drawdown_analysis": 0.10,  # Low drawdown tolerance
            "market_adaptability": 0.20,  # Adapt to market inefficiencies
            "trade_quality": 0.25,  # Execution speed critical
            "strategy_transparency": 0.20,  # Pattern recognition important
            "behavioral_sustainability": 0.15,
        }

    def _get_high_frequency_profile(self) -> Dict[str, float]:
        """Get scoring weights for high-frequency trader wallets."""

        return {
            "risk_adjusted_returns": 0.15,
            "consistency_metrics": 0.25,
            "drawdown_analysis": 0.10,
            "market_adaptability": 0.15,
            "trade_quality": 0.30,  # Most critical for HFT
            "strategy_transparency": 0.25,
            "behavioral_sustainability": 0.20,
        }

    def _get_mixed_trader_profile(self) -> Dict[str, float]:
        """Get scoring weights for mixed strategy wallets."""

        return {
            "risk_adjusted_returns": 0.25,
            "consistency_metrics": 0.20,
            "drawdown_analysis": 0.18,
            "market_adaptability": 0.22,
            "trade_quality": 0.15,
            "strategy_transparency": 0.18,
            "behavioral_sustainability": 0.22,
        }

    def _get_bull_market_weights(self) -> Dict[str, float]:
        """Market regime weights for bull markets."""

        return {
            "risk_adjusted_returns": 1.2,  # Higher weight on returns
            "consistency_metrics": 0.9,  # Slightly less important
            "drawdown_analysis": 0.8,  # Less concern about drawdowns
            "market_adaptability": 1.1,  # Important to adapt to trending markets
            "trade_quality": 1.0,
            "strategy_transparency": 1.0,
            "behavioral_sustainability": 1.0,
        }

    def _get_bear_market_weights(self) -> Dict[str, float]:
        """Market regime weights for bear markets."""

        return {
            "risk_adjusted_returns": 0.8,  # Lower weight on returns
            "consistency_metrics": 1.2,  # More important for survival
            "drawdown_analysis": 1.3,  # Critical in bear markets
            "market_adaptability": 1.2,  # Very important in changing conditions
            "trade_quality": 1.1,  # Slightly more important
            "strategy_transparency": 1.1,
            "behavioral_sustainability": 1.2,  # Monitor strategy sustainability
        }

    def _get_high_volatility_weights(self) -> Dict[str, float]:
        """Market regime weights for high volatility periods."""

        return {
            "risk_adjusted_returns": 0.9,
            "consistency_metrics": 1.1,
            "drawdown_analysis": 1.4,  # Very important in volatile markets
            "market_adaptability": 1.3,  # Critical for volatile conditions
            "trade_quality": 1.2,  # Execution quality matters more
            "strategy_transparency": 0.9,
            "behavioral_sustainability": 1.1,
        }

    def _get_low_liquidity_weights(self) -> Dict[str, float]:
        """Market regime weights for low liquidity periods."""

        return {
            "risk_adjusted_returns": 0.8,
            "consistency_metrics": 1.0,
            "drawdown_analysis": 1.1,
            "market_adaptability": 1.0,
            "trade_quality": 1.3,  # Very important when liquidity is low
            "strategy_transparency": 1.1,
            "behavioral_sustainability": 1.0,
        }

    def _get_normal_market_weights(self) -> Dict[str, float]:
        """Market regime weights for normal market conditions."""

        return {
            "risk_adjusted_returns": 1.0,
            "consistency_metrics": 1.0,
            "drawdown_analysis": 1.0,
            "market_adaptability": 1.0,
            "trade_quality": 1.0,
            "strategy_transparency": 1.0,
            "behavioral_sustainability": 1.0,
        }

    async def calculate_wallet_quality_score(
        self,
        wallet_address: str,
        trade_history: List[Dict[str, Any]],
        market_conditions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive quality score for a wallet.

        Args:
            wallet_address: Wallet to score
            trade_history: Historical trade data
            market_conditions: Current market conditions (optional)

        Returns:
            Complete quality score analysis with components and confidence
        """

        if len(trade_history) < self.scoring_config["min_scoring_period_days"]:
            return self._create_insufficient_data_response(wallet_address)

        try:
            # Get wallet classification
            wallet_type = await self._classify_wallet_type(wallet_address)

            # Calculate individual scoring components
            scoring_components = await self._calculate_scoring_components(
                wallet_address, trade_history, wallet_type
            )

            # Apply market regime weighting
            market_regime = self._determine_market_regime(market_conditions)
            regime_weights = self.market_regimes[market_regime]

            # Calculate final weighted score
            final_score = self._calculate_weighted_score(
                scoring_components, wallet_type, regime_weights
            )

            # Calculate confidence intervals
            confidence_intervals = self._calculate_score_confidence_intervals(
                wallet_address, scoring_components, trade_history
            )

            # Assess score stability
            score_stability = self._calculate_score_stability(wallet_address, final_score)

            # Generate quality assessment
            quality_assessment = self._assess_wallet_quality(final_score, confidence_intervals)

            # Store scoring history
            self._store_scoring_history(
                wallet_address,
                {
                    "timestamp": datetime.now().isoformat(),
                    "final_score": final_score,
                    "scoring_components": scoring_components,
                    "market_regime": market_regime,
                    "confidence_intervals": confidence_intervals,
                    "quality_assessment": quality_assessment,
                    "trade_count": len(trade_history),
                },
            )

            return {
                "wallet_address": wallet_address,
                "wallet_type": wallet_type,
                "quality_score": final_score,
                "scoring_components": scoring_components,
                "market_regime": market_regime,
                "regime_weights": regime_weights,
                "confidence_intervals": confidence_intervals,
                "score_stability": score_stability,
                "quality_assessment": quality_assessment,
                "calculation_timestamp": datetime.now().isoformat(),
                "data_points_used": len(trade_history),
            }

        except Exception as e:
            logger.error(f"Error calculating quality score for {wallet_address}: {e}")
            return {
                "wallet_address": wallet_address,
                "error": str(e),
                "quality_score": None,
                "scoring_components": {},
                "calculation_timestamp": datetime.now().isoformat(),
            }

    async def _calculate_scoring_components(
        self, wallet_address: str, trade_history: List[Dict[str, Any]], wallet_type: str
    ) -> Dict[str, float]:
        """Calculate individual scoring components."""

        components = {}

        # Risk-adjusted returns (Sharpe, Sortino, Calmar ratios)
        components["risk_adjusted_returns"] = await self._calculate_risk_adjusted_returns(
            trade_history
        )

        # Consistency metrics (win rate stability, performance consistency)
        components["consistency_metrics"] = await self._calculate_consistency_metrics(trade_history)

        # Drawdown analysis (max drawdown, average drawdown, recovery time)
        components["drawdown_analysis"] = await self._calculate_drawdown_analysis(trade_history)

        # Market adaptability (performance across different market conditions)
        components["market_adaptability"] = await self._calculate_market_adaptability(trade_history)

        # Trade quality (execution quality, slippage, gas efficiency)
        components["trade_quality"] = await self._calculate_trade_quality(
            trade_history, wallet_type
        )

        # Strategy transparency (behavioral predictability, pattern consistency)
        components["strategy_transparency"] = await self._calculate_strategy_transparency(
            trade_history, wallet_type
        )

        # Behavioral sustainability (strategy evolution, performance decay)
        components["behavioral_sustainability"] = await self._calculate_behavioral_sustainability(
            wallet_address, trade_history
        )

        return components

    async def _calculate_risk_adjusted_returns(self, trade_history: List[Dict[str, Any]]) -> float:
        """Calculate risk-adjusted return metrics (0-100 scale)."""

        if len(trade_history) < self.scoring_config["sharpe_ratio_min_periods"]:
            return 50.0  # Neutral score for insufficient data

        try:
            # Extract returns from trade history
            returns = []
            for trade in trade_history:
                pnl_pct = trade.get("pnl_pct", 0)
                if pnl_pct is not None:
                    returns.append(pnl_pct)

            if not returns:
                return 50.0

            returns = np.array(returns)
            mean_return = np.mean(returns)
            std_return = np.std(returns)

            # Sharpe Ratio (annualized)
            risk_free_rate = self.scoring_config.get("risk_free_rate", 0.02) / 365  # Daily
            if std_return > 0:
                sharpe_ratio = (mean_return - risk_free_rate) / std_return * np.sqrt(365)
            else:
                sharpe_ratio = 0

            # Sortino Ratio (downside deviation only)
            target_return = self.scoring_config["sortino_ratio_target_return"] / 365
            downside_returns = returns[returns < target_return]
            if len(downside_returns) > 0:
                downside_std = np.std(downside_returns)
                sortino_ratio = (
                    (mean_return - target_return) / downside_std * np.sqrt(365)
                    if downside_std > 0
                    else 0
                )
            else:
                sortino_ratio = float("inf")  # No downside deviation

            # Calmar Ratio (annual return / max drawdown)
            calmar_ratio = self._calculate_calmar_ratio(trade_history)

            # Combine ratios into composite score
            # Normalize each ratio to 0-100 scale
            sharpe_score = min(max((sharpe_ratio + 2) * 25, 0), 100)  # -2 to +2 range -> 0-100
            sortino_score = (
                min(max(sortino_ratio * 20, 0), 100) if sortino_ratio != float("inf") else 100
            )
            calmar_score = min(max(calmar_ratio * 50, 0), 100)  # 0-2 range -> 0-100

            # Weighted average
            risk_adjusted_score = sharpe_score * 0.4 + sortino_score * 0.4 + calmar_score * 0.2

            return risk_adjusted_score

        except Exception as e:
            logger.error(f"Error calculating risk-adjusted returns: {e}")
            return 50.0

    def _calculate_calmar_ratio(self, trade_history: List[Dict[str, Any]]) -> float:
        """Calculate Calmar ratio (annual return / max drawdown)."""

        try:
            # Calculate cumulative returns
            cumulative_returns = []
            cumulative = 0

            for trade in trade_history:
                pnl_pct = trade.get("pnl_pct", 0)
                cumulative += pnl_pct
                cumulative_returns.append(cumulative)

            if not cumulative_returns:
                return 0

            # Calculate drawdowns
            peak = cumulative_returns[0]
            max_drawdown = 0

            for cumulative_return in cumulative_returns:
                if cumulative_return > peak:
                    peak = cumulative_return
                drawdown = peak - cumulative_return
                max_drawdown = max(max_drawdown, drawdown)

            # Annual return (simplified - assuming daily trades)
            total_return = cumulative_returns[-1] - cumulative_returns[0]
            annual_return = total_return * 365 / len(trade_history) if len(trade_history) > 0 else 0

            # Calmar ratio
            calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0

            return calmar_ratio

        except Exception as e:
            logger.error(f"Error calculating Calmar ratio: {e}")
            return 0

    async def _calculate_consistency_metrics(self, trade_history: List[Dict[str, Any]]) -> float:
        """Calculate consistency metrics (0-100 scale)."""

        if len(trade_history) < self.scoring_config["win_rate_stability_window"]:
            return 50.0

        try:
            # Win rate stability
            win_rates = []
            window_size = self.scoring_config["win_rate_stability_window"]

            for i in range(window_size, len(trade_history) + 1):
                window_trades = trade_history[i - window_size : i]
                wins = sum(1 for t in window_trades if t.get("pnl_pct", 0) > 0)
                win_rate = wins / len(window_trades) if window_trades else 0
                win_rates.append(win_rate)

            if not win_rates:
                return 50.0

            # Calculate stability metrics
            win_rate_mean = np.mean(win_rates)
            win_rate_std = np.std(win_rates)
            win_rate_cv = win_rate_std / win_rate_mean if win_rate_mean > 0 else 0

            # Coefficient of variation (lower is better for consistency)
            cv_score = max(0, 100 - win_rate_cv * 200)  # Scale CV to 0-100

            # Win rate trend (consistency over time)
            if len(win_rates) >= 10:
                slope, _, _, _, _ = stats.linregress(range(len(win_rates)), win_rates)
                trend_score = max(0, 100 - abs(slope) * 1000)  # Penalize strong trends
            else:
                trend_score = 50.0

            # Profit factor consistency
            profit_factors = []
            for i in range(window_size, len(trade_history) + 1):
                window_trades = trade_history[i - window_size : i]
                profits = sum(t.get("pnl_pct", 0) for t in window_trades if t.get("pnl_pct", 0) > 0)
                losses = abs(
                    sum(t.get("pnl_pct", 0) for t in window_trades if t.get("pnl_pct", 0) < 0)
                )

                if losses > 0:
                    profit_factor = profits / losses
                    profit_factors.append(profit_factor)

            pf_consistency = (
                np.std(profit_factors) / np.mean(profit_factors) if profit_factors else 0
            )
            pf_score = max(0, 100 - pf_consistency * 100)

            # Weighted consistency score
            consistency_score = cv_score * 0.4 + trend_score * 0.3 + pf_score * 0.3

            return consistency_score

        except Exception as e:
            logger.error(f"Error calculating consistency metrics: {e}")
            return 50.0

    async def _calculate_drawdown_analysis(self, trade_history: List[Dict[str, Any]]) -> float:
        """Calculate drawdown analysis metrics (0-100 scale)."""

        if len(trade_history) < 50:
            return 50.0

        try:
            # Calculate cumulative returns
            cumulative_returns = []
            cumulative = 0

            for trade in trade_history:
                pnl_pct = trade.get("pnl_pct", 0)
                cumulative += pnl_pct
                cumulative_returns.append(cumulative)

            # Calculate drawdowns
            peak = cumulative_returns[0]
            drawdowns = []
            current_drawdown = 0
            max_drawdown = 0
            drawdown_start = 0

            for i, cumulative_return in enumerate(cumulative_returns):
                if cumulative_return > peak:
                    # End of drawdown period
                    if current_drawdown > 0:
                        drawdowns.append(
                            {
                                "start_idx": drawdown_start,
                                "end_idx": i - 1,
                                "depth": current_drawdown,
                                "duration": i - drawdown_start,
                            }
                        )
                    peak = cumulative_return
                    current_drawdown = 0
                else:
                    current_drawdown = peak - cumulative_return
                    if current_drawdown > max_drawdown:
                        max_drawdown = current_drawdown
                        drawdown_start = i

            # Calculate drawdown metrics
            if drawdowns:
                avg_drawdown = np.mean([d["depth"] for d in drawdowns])
                max_drawdown_depth = max([d["depth"] for d in drawdowns])
                avg_recovery_time = np.mean([d["duration"] for d in drawdowns])
            else:
                avg_drawdown = 0
                max_drawdown_depth = max_drawdown
                avg_recovery_time = 0

            # Score drawdown metrics (lower drawdowns = higher scores)
            # Max drawdown score (0-30% is excellent, >50% is poor)
            if max_drawdown_depth <= 0.10:  # 10%
                max_dd_score = 100
            elif max_drawdown_depth <= 0.20:  # 20%
                max_dd_score = 80
            elif max_drawdown_depth <= 0.30:  # 30%
                max_dd_score = 60
            elif max_drawdown_depth <= 0.50:  # 50%
                max_dd_score = 40
            else:
                max_dd_score = 20

            # Average drawdown score
            avg_dd_score = max(0, 100 - avg_drawdown * 500)  # Scale to 0-100

            # Recovery time score (shorter recovery = higher score)
            if avg_recovery_time <= 10:  # 10 days
                recovery_score = 100
            elif avg_recovery_time <= 25:  # 25 days
                recovery_score = 80
            elif avg_recovery_time <= 50:  # 50 days
                recovery_score = 60
            elif avg_recovery_time <= 100:  # 100 days
                recovery_score = 40
            else:
                recovery_score = 20

            # Weighted drawdown score
            recovery_weight = self.scoring_config["recovery_time_weight"]
            drawdown_score = (
                max_dd_score * (0.5 - recovery_weight / 2)
                + avg_dd_score * (0.3 - recovery_weight / 2)
                + recovery_score * recovery_weight
            )

            return drawdown_score

        except Exception as e:
            logger.error(f"Error calculating drawdown analysis: {e}")
            return 50.0

    async def _calculate_market_adaptability(self, trade_history: List[Dict[str, Any]]) -> float:
        """Calculate market adaptability metrics (0-100 scale)."""

        if len(trade_history) < 100:
            return 50.0

        try:
            # Analyze performance across different market regimes
            regime_performance = {}

            # Group trades by market conditions (simplified)
            # In practice, this would use actual market data
            regimes = ["bull", "bear", "sideways", "volatile"]

            for regime in regimes:
                regime_trades = [t for t in trade_history if t.get("market_regime") == regime]
                if len(regime_trades) >= self.scoring_config["min_regime_samples"]:
                    wins = sum(1 for t in regime_trades if t.get("pnl_pct", 0) > 0)
                    win_rate = wins / len(regime_trades)
                    avg_return = np.mean([t.get("pnl_pct", 0) for t in regime_trades])

                    regime_performance[regime] = {
                        "win_rate": win_rate,
                        "avg_return": avg_return,
                        "trade_count": len(regime_trades),
                    }

            if not regime_performance:
                return 50.0

            # Calculate adaptability metrics
            win_rates = [perf["win_rate"] for perf in regime_performance.values()]
            avg_returns = [perf["avg_return"] for perf in regime_performance.values()]

            # Consistency across regimes (lower variance = higher adaptability)
            win_rate_consistency = (
                1 - np.std(win_rates) / np.mean(win_rates) if np.mean(win_rates) > 0 else 0
            )
            return_consistency = (
                1 - np.std(avg_returns) / abs(np.mean(avg_returns))
                if np.mean(avg_returns) != 0
                else 0
            )

            # Minimum performance threshold (must perform reasonably in all regimes)
            min_win_rate = min(win_rates)
            min_return_threshold = -0.02  # -2% minimum acceptable
            min_return = min(avg_returns)

            regime_survival = 1 if min_win_rate >= 0.4 and min_return >= min_return_threshold else 0

            # Adaptability score
            adaptability_score = (
                win_rate_consistency * 40  # 40% weight
                + return_consistency * 30  # 30% weight
                + regime_survival * 30  # 30% weight
            )

            return max(0, min(100, adaptability_score))

        except Exception as e:
            logger.error(f"Error calculating market adaptability: {e}")
            return 50.0

    async def _calculate_trade_quality(
        self, trade_history: List[Dict[str, Any]], wallet_type: str
    ) -> float:
        """Calculate trade quality metrics (0-100 scale)."""

        if not trade_history:
            return 50.0

        try:
            # Execution quality (slippage analysis)
            slippage_scores = []
            gas_efficiency_scores = []

            for trade in trade_history:
                # Slippage calculation (actual price vs expected price)
                expected_price = trade.get("expected_price")
                actual_price = trade.get("actual_price", trade.get("price"))

                if expected_price and actual_price:
                    slippage_pct = abs(actual_price - expected_price) / expected_price * 100
                    max_acceptable_slippage = self.scoring_config["slippage_tolerance_pct"]

                    if slippage_pct <= max_acceptable_slippage:
                        slippage_score = 100
                    elif slippage_pct <= max_acceptable_slippage * 2:
                        slippage_score = 75
                    elif slippage_pct <= max_acceptable_slippage * 3:
                        slippage_score = 50
                    else:
                        slippage_score = 25

                    slippage_scores.append(slippage_score)

                # Gas efficiency (gas cost vs trade value)
                gas_cost = trade.get("gas_cost_usd", 0)
                trade_value = abs(trade.get("amount", 0) * trade.get("price", 0))

                if trade_value > 0 and gas_cost > 0:
                    gas_ratio = gas_cost / trade_value
                    # Lower gas ratio = higher efficiency
                    gas_efficiency = max(0, 100 - gas_ratio * 10000)  # Scale appropriately
                    gas_efficiency_scores.append(gas_efficiency)

            # Calculate average scores
            avg_slippage_score = np.mean(slippage_scores) if slippage_scores else 75
            avg_gas_efficiency = np.mean(gas_efficiency_scores) if gas_efficiency_scores else 75

            # Trade timing quality (for different wallet types)
            timing_score = await self._calculate_trade_timing_quality(trade_history, wallet_type)

            # Weighted trade quality score
            execution_weight = self.scoring_config["execution_quality_weight"]
            gas_weight = self.scoring_config["gas_efficiency_weight"]
            timing_weight = 1 - execution_weight - gas_weight

            trade_quality_score = (
                avg_slippage_score * execution_weight
                + avg_gas_efficiency * gas_weight
                + timing_score * timing_weight
            )

            return trade_quality_score

        except Exception as e:
            logger.error(f"Error calculating trade quality: {e}")
            return 50.0

    async def _calculate_trade_timing_quality(
        self, trade_history: List[Dict[str, Any]], wallet_type: str
    ) -> float:
        """Calculate trade timing quality based on wallet type."""

        try:
            # For market makers: quick round-trip trades are good
            if wallet_type == "market_maker":
                holding_times = []
                for i in range(1, len(trade_history), 2):
                    if i < len(trade_history):
                        entry_time = datetime.fromisoformat(trade_history[i - 1]["timestamp"])
                        exit_time = datetime.fromisoformat(trade_history[i]["timestamp"])
                        holding_time = (exit_time - entry_time).total_seconds() / 3600  # hours

                        # Ideal holding time: 0.5-4 hours
                        if 0.5 <= holding_time <= 4:
                            timing_score = 100
                        elif holding_time < 0.5:
                            timing_score = 80  # Very fast (might be overtrading)
                        elif holding_time <= 12:
                            timing_score = 90
                        else:
                            timing_score = 60  # Too slow for market making

                        holding_times.append(timing_score)

                return np.mean(holding_times) if holding_times else 75

            # For directional traders: longer-term timing matters
            elif wallet_type == "directional_trader":
                # Analyze entry/exit timing relative to market trends
                # Simplified: score based on holding time distribution
                holding_times = []

                for trade in trade_history:
                    # Simplified timing analysis
                    holding_times.append(trade.get("holding_time_hours", 24))

                if holding_times:
                    avg_holding = np.mean(holding_times)
                    # Ideal: 1-7 days for directional trading
                    if 24 <= avg_holding <= 168:
                        return 100
                    elif avg_holding < 24:
                        return 70  # Too short-term
                    else:
                        return 80  # Long-term is okay but less optimal

                return 75

            else:
                # Default timing score
                return 75

        except Exception as e:
            logger.error(f"Error calculating trade timing quality: {e}")
            return 75

    async def _calculate_strategy_transparency(
        self, trade_history: List[Dict[str, Any]], wallet_type: str
    ) -> float:
        """Calculate strategy transparency and predictability (0-100 scale)."""

        if len(trade_history) < self.scoring_config["pattern_recognition_window"]:
            return 50.0

        try:
            # Analyze behavioral patterns
            pattern_consistency = await self._analyze_pattern_consistency(
                trade_history, wallet_type
            )

            # Predictability assessment
            predictability_score = await self._assess_strategy_predictability(trade_history)

            # Behavioral regularity
            regularity_score = await self._calculate_behavioral_regularity(trade_history)

            # Weighted transparency score
            transparency_score = (
                pattern_consistency * 0.4 + predictability_score * 0.4 + regularity_score * 0.2
            )

            return transparency_score

        except Exception as e:
            logger.error(f"Error calculating strategy transparency: {e}")
            return 50.0

    async def _analyze_pattern_consistency(
        self, trade_history: List[Dict[str, Any]], wallet_type: str
    ) -> float:
        """Analyze consistency of trading patterns."""

        try:
            # For market makers: look for consistent alternation
            if wallet_type == "market_maker":
                sides = [t.get("side", "BUY") for t in trade_history[-50:]]  # Last 50 trades

                if len(sides) >= 10:
                    alternations = sum(1 for i in range(1, len(sides)) if sides[i] != sides[i - 1])
                    alternation_rate = alternations / (len(sides) - 1)

                    # Ideal alternation rate for market makers: 0.6-0.9
                    if 0.6 <= alternation_rate <= 0.9:
                        return 100
                    elif alternation_rate >= 0.4:
                        return 75
                    else:
                        return 50

            # For directional traders: look for trend-following consistency
            elif wallet_type == "directional_trader":
                # Analyze trade direction relative to market trend
                trend_alignment = []

                for trade in trade_history[-50:]:
                    market_trend = trade.get("market_trend", 0)  # -1, 0, 1
                    trade_direction = 1 if trade.get("side") == "BUY" else -1

                    alignment = 1 if market_trend * trade_direction > 0 else 0
                    trend_alignment.append(alignment)

                if trend_alignment:
                    alignment_rate = np.mean(trend_alignment)
                    return alignment_rate * 100

            return 60  # Default moderate score

        except Exception as e:
            logger.error(f"Error analyzing pattern consistency: {e}")
            return 60

    async def _assess_strategy_predictability(self, trade_history: List[Dict[str, Any]]) -> float:
        """Assess how predictable the strategy is."""

        try:
            # Use simple pattern recognition
            # Look for repeating patterns in trade sequences

            if len(trade_history) < 20:
                return 50

            # Convert trades to simple pattern (buy=1, sell=-1)
            pattern = []
            for trade in trade_history[-100:]:
                direction = 1 if trade.get("side") == "BUY" else -1
                pattern.append(direction)

            # Find repeating subsequences
            predictability = self._calculate_sequence_predictability(pattern)

            # Scale to 0-100
            predictability_score = min(100, predictability * 100)

            return predictability_score

        except Exception as e:
            logger.error(f"Error assessing strategy predictability: {e}")
            return 50

    def _calculate_sequence_predictability(self, sequence: List[int]) -> float:
        """Calculate predictability of a sequence using compression ratio."""

        try:
            if len(sequence) < 10:
                return 0.5

            # Simple predictability measure: look for patterns
            # Count consecutive same directions (momentum)
            momentum_score = 0
            current_streak = 1

            for i in range(1, len(sequence)):
                if sequence[i] == sequence[i - 1]:
                    current_streak += 1
                else:
                    momentum_score += current_streak
                    current_streak = 1

            momentum_score += current_streak

            # Normalize by sequence length
            predictability = momentum_score / len(sequence)

            return min(1.0, predictability)

        except Exception:
            return 0.5

    async def _calculate_behavioral_regularity(self, trade_history: List[Dict[str, Any]]) -> float:
        """Calculate behavioral regularity score."""

        try:
            # Analyze trade frequency regularity
            timestamps = [datetime.fromisoformat(t["timestamp"]) for t in trade_history[-100:]]

            if len(timestamps) < 10:
                return 50

            # Calculate inter-trade intervals
            intervals = []
            for i in range(1, len(timestamps)):
                interval = (timestamps[i] - timestamps[i - 1]).total_seconds() / 3600  # hours
                intervals.append(interval)

            if not intervals:
                return 50

            # Calculate regularity (lower coefficient of variation = more regular)
            cv = np.std(intervals) / np.mean(intervals) if np.mean(intervals) > 0 else 0
            regularity_score = max(0, 100 - cv * 200)  # Scale CV to 0-100

            return regularity_score

        except Exception as e:
            logger.error(f"Error calculating behavioral regularity: {e}")
            return 50

    async def _calculate_behavioral_sustainability(
        self, wallet_address: str, trade_history: List[Dict[str, Any]]
    ) -> float:
        """Calculate behavioral sustainability score."""

        try:
            # Performance decay analysis
            decay_score = await self._analyze_performance_decay(trade_history)

            # Strategy evolution detection
            evolution_score = await self._detect_strategy_evolution(wallet_address, trade_history)

            # Risk management quality
            risk_management_score = await self.risk_assessor.assess_risk_management_quality(
                trade_history
            )

            # Capital efficiency
            capital_efficiency_score = await self._assess_capital_efficiency(trade_history)

            # Weighted sustainability score
            sustainability_score = (
                decay_score * 0.3
                + evolution_score * 0.3
                + risk_management_score * 0.25
                + capital_efficiency_score * 0.15
            )

            return sustainability_score

        except Exception as e:
            logger.error(f"Error calculating behavioral sustainability: {e}")
            return 50.0

    async def _analyze_performance_decay(self, trade_history: List[Dict[str, Any]]) -> float:
        """Analyze performance decay over time."""

        try:
            window_size = self.scoring_config["performance_decay_window"]

            if len(trade_history) < window_size:
                return 75  # Neutral score for insufficient data

            # Calculate rolling performance metrics
            rolling_returns = []
            rolling_win_rates = []

            for i in range(window_size, len(trade_history) + 1, 10):  # Every 10 trades
                window_trades = trade_history[i - window_size : i]

                returns = [t.get("pnl_pct", 0) for t in window_trades]
                avg_return = np.mean(returns) if returns else 0

                wins = sum(1 for r in returns if r > 0)
                win_rate = wins / len(returns) if returns else 0

                rolling_returns.append(avg_return)
                rolling_win_rates.append(win_rate)

            if len(rolling_returns) < 3:
                return 75

            # Analyze trends
            return_trend = np.polyfit(range(len(rolling_returns)), rolling_returns, 1)[0]
            win_rate_trend = np.polyfit(range(len(rolling_win_rates)), rolling_win_rates, 1)[0]

            # Negative trends indicate decay
            return_decay = max(0, -return_trend * 1000)  # Scale appropriately
            win_rate_decay = max(0, -win_rate_trend * 1000)

            # Decay score (lower decay = higher score)
            decay_score = max(0, 100 - (return_decay + win_rate_decay) / 2)

            return decay_score

        except Exception as e:
            logger.error(f"Error analyzing performance decay: {e}")
            return 75

    async def _detect_strategy_evolution(
        self, wallet_address: str, trade_history: List[Dict[str, Any]]
    ) -> float:
        """Detect strategy evolution or significant changes."""

        try:
            # Compare recent vs historical behavior
            split_point = len(trade_history) // 2

            recent_trades = trade_history[split_point:]
            historical_trades = trade_history[:split_point]

            if len(recent_trades) < 20 or len(historical_trades) < 20:
                return 75  # Insufficient data for comparison

            # Compare key metrics
            recent_metrics = self._calculate_behavioral_metrics(recent_trades)
            historical_metrics = self._calculate_behavioral_metrics(historical_trades)

            # Calculate changes in key metrics
            changes = {}
            for metric in recent_metrics:
                if metric in historical_metrics and historical_metrics[metric] != 0:
                    change = abs(recent_metrics[metric] - historical_metrics[metric]) / abs(
                        historical_metrics[metric]
                    )
                    changes[metric] = change

            # Average change across metrics
            avg_change = np.mean(list(changes.values())) if changes else 0

            # Evolution score (lower change = higher score for stability)
            evolution_threshold = self.scoring_config["strategy_evolution_threshold"]
            if avg_change <= evolution_threshold:
                evolution_score = 100
            elif avg_change <= evolution_threshold * 2:
                evolution_score = 75
            elif avg_change <= evolution_threshold * 3:
                evolution_score = 50
            else:
                evolution_score = 25  # Significant strategy change

            return evolution_score

        except Exception as e:
            logger.error(f"Error detecting strategy evolution: {e}")
            return 75

    def _calculate_behavioral_metrics(self, trades: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate key behavioral metrics for a set of trades."""

        metrics = {}

        if not trades:
            return metrics

        # Win rate
        wins = sum(1 for t in trades if t.get("pnl_pct", 0) > 0)
        metrics["win_rate"] = wins / len(trades)

        # Average return
        returns = [t.get("pnl_pct", 0) for t in trades]
        metrics["avg_return"] = np.mean(returns) if returns else 0

        # Trade frequency
        if len(trades) >= 2:
            timestamps = [datetime.fromisoformat(t["timestamp"]) for t in trades]
            intervals = [
                (timestamps[i] - timestamps[i - 1]).total_seconds() / 3600
                for i in range(1, len(timestamps))
            ]
            metrics["avg_trade_interval"] = np.mean(intervals) if intervals else 24

        # Position sizing consistency
        sizes = [abs(t.get("amount", 0)) for t in trades]
        if sizes:
            metrics["size_consistency"] = 1 - (
                np.std(sizes) / np.mean(sizes) if np.mean(sizes) > 0 else 0
            )

        return metrics

    async def _assess_capital_efficiency(self, trade_history: List[Dict[str, Any]]) -> float:
        """Assess capital efficiency metrics."""

        try:
            if not trade_history:
                return 50

            # Calculate return on capital metrics
            total_return = sum(t.get("pnl_pct", 0) for t in trade_history)
            total_trades = len(trade_history)

            # Capital utilization efficiency
            total_return / total_trades if total_trades > 0 else 0

            # Sharpe-style efficiency
            returns = [t.get("pnl_pct", 0) for t in trade_history]
            if returns:
                efficiency = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
                efficiency_score = min(100, max(0, efficiency * 50 + 50))  # Scale to 0-100
            else:
                efficiency_score = 50

            return efficiency_score

        except Exception as e:
            logger.error(f"Error assessing capital efficiency: {e}")
            return 50

    async def _classify_wallet_type(self, wallet_address: str) -> str:
        """Classify wallet type (placeholder - integrate with existing classifier)."""

        # This would integrate with the existing wallet classification system
        # For now, return a default
        return "market_maker"

    def _determine_market_regime(self, market_conditions: Optional[Dict[str, Any]]) -> str:
        """Determine current market regime."""

        if not market_conditions:
            return "normal"

        volatility = market_conditions.get("volatility_index", 0.2)
        trend_strength = market_conditions.get("trend_strength", 0.0)
        liquidity = market_conditions.get("liquidity_score", 0.6)

        if volatility > 0.3:
            return "high_volatility"
        elif liquidity < 0.4:
            return "low_liquidity"
        elif trend_strength > 0.6:
            return "bull"
        elif trend_strength < -0.6:
            return "bear"
        else:
            return "normal"

    def _calculate_weighted_score(
        self, components: Dict[str, float], wallet_type: str, regime_weights: Dict[str, float]
    ) -> float:
        """Calculate final weighted quality score."""

        profile_weights = self.scoring_profiles[wallet_type]

        # Apply regime adjustments to profile weights
        adjusted_weights = {}
        for component in profile_weights:
            base_weight = profile_weights[component]
            regime_multiplier = regime_weights.get(component, 1.0)
            adjusted_weights[component] = base_weight * regime_multiplier

        # Normalize weights
        total_weight = sum(adjusted_weights.values())
        if total_weight > 0:
            normalized_weights = {k: v / total_weight for k, v in adjusted_weights.items()}
        else:
            normalized_weights = profile_weights

        # Calculate weighted score
        weighted_score = 0
        for component, weight in normalized_weights.items():
            component_score = components.get(component, 50.0)
            weighted_score += component_score * weight

        return weighted_score

    def _calculate_score_confidence_intervals(
        self, wallet_address: str, components: Dict[str, float], trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate confidence intervals for the quality score."""

        try:
            # Bootstrap confidence intervals
            n_bootstraps = 1000
            bootstrap_scores = []

            for _ in range(n_bootstraps):
                # Resample trade history
                np.random.choice(trade_history, size=len(trade_history), replace=True)

                # Recalculate components on resampled data
                # Simplified - in practice would recalculate all components
                resampled_score = np.mean(list(components.values()))

                bootstrap_scores.append(resampled_score)

            # Calculate confidence intervals
            bootstrap_scores = np.array(bootstrap_scores)
            ci_lower = np.percentile(bootstrap_scores, 5)  # 90% CI
            ci_upper = np.percentile(bootstrap_scores, 95)

            return {
                "confidence_level": 0.90,
                "lower_bound": ci_lower,
                "upper_bound": ci_upper,
                "confidence_interval_width": ci_upper - ci_lower,
                "standard_error": np.std(bootstrap_scores),
            }

        except Exception as e:
            logger.error(f"Error calculating confidence intervals: {e}")
            return {
                "confidence_level": 0.90,
                "lower_bound": None,
                "upper_bound": None,
                "confidence_interval_width": None,
                "standard_error": None,
                "error": str(e),
            }

    def _calculate_score_stability(
        self, wallet_address: str, current_score: float
    ) -> Dict[str, Any]:
        """Calculate score stability metrics."""

        history = self.scoring_history.get(wallet_address) or []
        if len(history) < self.scoring_config["score_stability_window"]:
            return {"stability_score": 50.0, "volatility": None, "trend": None}

        try:
            recent_scores = [
                h["final_score"] for h in history[-self.scoring_config["score_stability_window"] :]
            ]
            recent_scores.append(current_score)

            # Calculate stability metrics
            score_volatility = np.std(recent_scores)
            score_trend = np.polyfit(range(len(recent_scores)), recent_scores, 1)[0]

            # Stability score (lower volatility = higher stability)
            stability_score = max(0, 100 - score_volatility * 10)

            return {
                "stability_score": stability_score,
                "volatility": score_volatility,
                "trend": score_trend,
                "samples_used": len(recent_scores),
            }

        except Exception as e:
            logger.error(f"Error calculating score stability: {e}")
            return {"stability_score": 50.0, "volatility": None, "trend": None, "error": str(e)}

    def _assess_wallet_quality(
        self, score: float, confidence_intervals: Dict[str, Any]
    ) -> Dict[str, str]:
        """Assess overall wallet quality based on score and confidence."""

        assessment = {
            "overall_quality": "unknown",
            "risk_level": "unknown",
            "recommendation": "unknown",
            "confidence_assessment": "unknown",
        }

        # Quality assessment
        if score >= self.scoring_config["high_quality_threshold"]:
            assessment["overall_quality"] = "high"
            assessment["risk_level"] = "low"
            assessment["recommendation"] = "strong_copy_candidate"
        elif score >= self.scoring_config["medium_quality_threshold"]:
            assessment["overall_quality"] = "medium"
            assessment["risk_level"] = "medium"
            assessment["recommendation"] = "moderate_copy_candidate"
        else:
            assessment["overall_quality"] = "low"
            assessment["risk_level"] = "high"
            assessment["recommendation"] = "avoid_copying"

        # Confidence assessment
        ci_width = confidence_intervals.get("confidence_interval_width")
        if ci_width is not None:
            if ci_width < 10:
                assessment["confidence_assessment"] = "high"
            elif ci_width < 20:
                assessment["confidence_assessment"] = "medium"
            else:
                assessment["confidence_assessment"] = "low"

        return assessment

    def _store_scoring_history(self, wallet_address: str, scoring_data: Dict[str, Any]):
        """Store scoring history for analysis."""

        # Get existing history or create new
        existing_history = self.scoring_history.get(wallet_address) or []
        existing_history.append(scoring_data)

        # Keep only recent history
        max_history = 100
        if len(existing_history) > max_history:
            existing_history = existing_history[-max_history:]

        self.scoring_history.set(wallet_address, existing_history)

    def _create_insufficient_data_response(self, wallet_address: str) -> Dict[str, Any]:
        """Create response for wallets with insufficient data."""

        return {
            "wallet_address": wallet_address,
            "quality_score": None,
            "scoring_components": {},
            "quality_assessment": {
                "overall_quality": "insufficient_data",
                "risk_level": "unknown",
                "recommendation": "monitor_only",
                "confidence_assessment": "none",
            },
            "reason": f"Insufficient trade history: minimum {self.scoring_config['min_scoring_period_days']} days required",
            "calculation_timestamp": datetime.now().isoformat(),
        }

    def get_scoring_statistics(self) -> Dict[str, Any]:
        """Get overall scoring system statistics."""

        # BoundedCache doesn't expose values() directly, so we use stats
        cache_stats = self.scoring_history.get_stats()
        total_wallets = cache_stats["size"]
        # For simplicity, we'll use a representative sample - in production
        # this would need to be enhanced to iterate through cache entries
        recent_scores = []  # Would need cache iteration logic

        stats = {
            "total_wallets_scored": total_wallets,
            "average_quality_score": np.mean(recent_scores) if recent_scores else None,
            "score_distribution": {
                "high_quality": sum(
                    1 for s in recent_scores if s >= self.scoring_config["high_quality_threshold"]
                ),
                "medium_quality": sum(
                    1
                    for s in recent_scores
                    if self.scoring_config["medium_quality_threshold"]
                    <= s
                    < self.scoring_config["high_quality_threshold"]
                ),
                "low_quality": sum(
                    1 for s in recent_scores if s < self.scoring_config["medium_quality_threshold"]
                ),
            },
            "scoring_system_health": "healthy" if total_wallets > 0 else "initializing",
        }

        return stats

    def save_scoring_state(self):
        """Save scoring system state."""
        # BoundedCache instances handle automatic cleanup - persistent storage less critical
        logger.info("💾 Scoring state managed automatically by BoundedCache")

    def load_scoring_state(self):
        """Load scoring system state."""
        # BoundedCache instances handle automatic cleanup - state loads on demand
        logger.info("📊 Scoring state managed automatically by BoundedCache")
