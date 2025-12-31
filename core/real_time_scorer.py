"""
Real-Time Scoring Engine
========================

Streaming scoring system for continuous wallet quality evaluation.

Features:
- Incremental score updates with minimal computation
- Real-time confidence interval calculations
- Score stability and trend analysis
- Market regime-aware score adjustments
- Streaming data processing with buffering
- Score prediction and forecasting
"""

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats

from core.behavioral_analyzer import BehaviorPatternTracker
from core.wallet_quality_scorer import WalletQualityScorer

logger = logging.getLogger(__name__)


class RealTimeScoringEngine:
    """
    Real-time scoring engine for continuous wallet quality evaluation.

    Processes streaming trade data to provide live quality scores with
    confidence intervals and stability metrics.
    """

    def __init__(self, wallet_quality_scorer: WalletQualityScorer):
        self.quality_scorer = wallet_quality_scorer
        self.behavior_tracker = BehaviorPatternTracker()

        # Real-time scoring parameters
        self.scoring_params = {
            "update_interval_seconds": 300,  # 5 minutes between full updates
            "incremental_update_threshold": 5,  # New trades trigger incremental update
            "confidence_interval_samples": 100,  # Bootstrap samples for CI calculation
            "score_stability_window": 20,  # Scores for stability calculation
            "trend_analysis_window": 50,  # Scores for trend analysis
            "market_regime_check_interval": 3600,  # 1 hour market regime updates
            "score_decay_factor": 0.95,  # Exponential decay for old scores
            "prediction_horizon_hours": 24,  # Hours to predict score trends
            "alert_threshold_change": 0.1,  # 10% score change triggers alert
            "stability_threshold": 0.15,  # Score volatility threshold
        }

        # Real-time state
        self.active_wallets: Dict[str, Dict[str, Any]] = {}
        self.score_streams: Dict[str, deque] = {}
        self.market_regime_state: Dict[str, Any] = {}
        self.pending_updates: Dict[str, List[Dict[str, Any]]] = {}

        # Prediction models
        self.score_predictors: Dict[str, Any] = {}
        self.trend_models: Dict[str, Any] = {}

        # Alert system
        self.score_alerts: List[Dict[str, Any]] = []
        self.stability_alerts: List[Dict[str, Any]] = []

        # Performance monitoring
        self.update_times: List[float] = []
        self.score_accuracy_history: List[Dict[str, Any]] = []

        logger.info("⚡ Real-time scoring engine initialized")

    async def initialize_wallet_stream(
        self, wallet_address: str, initial_history: List[Dict[str, Any]] = None
    ):
        """
        Initialize real-time scoring stream for a wallet.

        Args:
            wallet_address: Wallet to monitor
            initial_history: Initial trade history for baseline scoring
        """

        try:
            # Initialize wallet state
            self.active_wallets[wallet_address] = {
                "initialized_at": datetime.now().isoformat(),
                "last_full_update": None,
                "last_incremental_update": None,
                "current_score": None,
                "score_confidence": None,
                "trade_count": 0,
                "pending_trades": 0,
                "stability_metrics": {},
                "trend_analysis": {},
                "alert_status": "normal",
            }

            # Initialize score stream buffer
            self.score_streams[wallet_address] = deque(
                maxlen=self.scoring_params["trend_analysis_window"]
            )

            # Initialize pending updates buffer
            self.pending_updates[wallet_address] = []

            # Perform initial scoring if history provided
            if initial_history and len(initial_history) >= 30:
                await self._perform_full_score_update(wallet_address, initial_history)

                # Initialize prediction models
                await self._initialize_score_prediction(wallet_address, initial_history)

            logger.info(f"📊 Initialized real-time scoring for wallet {wallet_address}")

        except Exception as e:
            logger.error(f"Error initializing wallet stream for {wallet_address}: {e}")

    async def process_trade_update(
        self, wallet_address: str, trade_data: Dict[str, Any]
    ):
        """
        Process a new trade for real-time scoring update.

        Args:
            trade_data: New trade information
        """

        try:
            if wallet_address not in self.active_wallets:
                logger.warning(
                    f"Received trade for uninitialized wallet {wallet_address}"
                )
                return

            # Add to pending updates
            self.pending_updates[wallet_address].append(trade_data)
            self.active_wallets[wallet_address]["pending_trades"] += 1

            # Check if incremental update is needed
            pending_count = len(self.pending_updates[wallet_address])

            if pending_count >= self.scoring_params["incremental_update_threshold"]:
                await self._perform_incremental_update(wallet_address)

            # Update wallet trade count
            self.active_wallets[wallet_address]["trade_count"] += 1

        except Exception as e:
            logger.error(f"Error processing trade update for {wallet_address}: {e}")

    async def get_real_time_score(
        self, wallet_address: str, market_conditions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get current real-time quality score for a wallet.

        Returns score with confidence intervals and stability metrics.
        """

        try:
            if wallet_address not in self.active_wallets:
                return {
                    "error": f"Wallet {wallet_address} not initialized for real-time scoring"
                }

            wallet_state = self.active_wallets[wallet_address]

            # Check if we need a market regime update
            await self._check_market_regime_update(market_conditions)

            # Apply market regime adjustments if needed
            regime_adjusted_score = await self._apply_market_regime_adjustment(
                wallet_address, wallet_state.get("current_score")
            )

            # Calculate real-time confidence intervals
            confidence_intervals = await self._calculate_real_time_confidence_intervals(
                wallet_address
            )

            # Calculate score stability metrics
            stability_metrics = await self._calculate_score_stability(wallet_address)

            # Generate score prediction
            score_prediction = await self._predict_score_trend(wallet_address)

            # Check for score alerts
            alerts = await self._check_score_alerts(
                wallet_address, regime_adjusted_score, stability_metrics
            )

            return {
                "wallet_address": wallet_address,
                "current_score": regime_adjusted_score,
                "confidence_intervals": confidence_intervals,
                "stability_metrics": stability_metrics,
                "score_prediction": score_prediction,
                "alerts": alerts,
                "last_update": wallet_state.get("last_incremental_update")
                or wallet_state.get("last_full_update"),
                "trade_count": wallet_state["trade_count"],
                "data_freshness": self._calculate_data_freshness(wallet_address),
            }

        except Exception as e:
            logger.error(f"Error getting real-time score for {wallet_address}: {e}")
            return {"error": str(e), "wallet_address": wallet_address}

    async def _perform_full_score_update(
        self, wallet_address: str, trade_history: List[Dict[str, Any]]
    ):
        """Perform complete quality score recalculation."""

        start_time = time.time()

        try:
            # Get current market conditions (placeholder)
            market_conditions = await self._get_current_market_conditions()

            # Calculate full quality score
            score_result = await self.quality_scorer.calculate_wallet_quality_score(
                wallet_address, trade_history, market_conditions
            )

            if (
                "quality_score" in score_result
                and score_result["quality_score"] is not None
            ):
                # Update wallet state
                wallet_state = self.active_wallets[wallet_address]
                wallet_state["current_score"] = score_result["quality_score"]
                wallet_state["score_confidence"] = score_result.get(
                    "confidence_intervals", {}
                )
                wallet_state["last_full_update"] = datetime.now().isoformat()

                # Add to score stream
                score_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "score": score_result["quality_score"],
                    "confidence_lower": score_result.get(
                        "confidence_intervals", {}
                    ).get("lower_bound"),
                    "confidence_upper": score_result.get(
                        "confidence_intervals", {}
                    ).get("upper_bound"),
                    "market_regime": score_result.get("market_regime"),
                    "update_type": "full",
                }

                self.score_streams[wallet_address].append(score_entry)

                # Clear pending updates (they're now incorporated)
                self.pending_updates[wallet_address].clear()
                wallet_state["pending_trades"] = 0

            update_time = time.time() - start_time
            self.update_times.append(update_time)

            logger.debug(
                f"✅ Full score update for {wallet_address}: {score_result.get('quality_score', 'N/A')} ({update_time:.2f}s)"
            )

        except Exception as e:
            logger.error(
                f"Error performing full score update for {wallet_address}: {e}"
            )

    async def _perform_incremental_update(self, wallet_address: str):
        """Perform incremental score update using pending trades."""

        start_time = time.time()

        try:
            wallet_state = self.active_wallets[wallet_address]
            pending_trades = self.pending_updates[wallet_address]

            if not pending_trades:
                return

            # Get current score
            current_score = wallet_state.get("current_score")
            if current_score is None:
                # Fall back to full update if no current score
                await self._perform_full_score_update(wallet_address, pending_trades)
                return

            # Calculate incremental score adjustment
            score_adjustment = await self._calculate_incremental_score_adjustment(
                wallet_address, pending_trades
            )

            # Apply adjustment with damping
            damping_factor = 0.3  # Conservative updates
            new_score = current_score + (score_adjustment * damping_factor)

            # Ensure score stays within bounds
            new_score = max(0, min(100, new_score))

            # Update wallet state
            wallet_state["current_score"] = new_score
            wallet_state["last_incremental_update"] = datetime.now().isoformat()

            # Add to score stream
            score_entry = {
                "timestamp": datetime.now().isoformat(),
                "score": new_score,
                "incremental_adjustment": score_adjustment,
                "damping_factor": damping_factor,
                "update_type": "incremental",
                "trades_processed": len(pending_trades),
            }

            self.score_streams[wallet_address].append(score_entry)

            # Clear pending updates
            self.pending_updates[wallet_address].clear()
            wallet_state["pending_trades"] = 0

            update_time = time.time() - start_time
            self.update_times.append(update_time)

            logger.debug(
                f"🔄 Incremental update for {wallet_address}: {current_score:.1f} → {new_score:.1f} ({update_time:.2f}s)"
            )

        except Exception as e:
            logger.error(
                f"Error performing incremental update for {wallet_address}: {e}"
            )

    async def _calculate_incremental_score_adjustment(
        self, wallet_address: str, new_trades: List[Dict[str, Any]]
    ) -> float:
        """Calculate score adjustment based on new trades."""

        try:
            if not new_trades:
                return 0.0

            # Simple incremental adjustment based on recent trade performance
            # In practice, this would use more sophisticated incremental learning

            # Calculate recent performance metrics
            recent_returns = [t.get("pnl_pct", 0) for t in new_trades]
            recent_win_rate = (
                sum(1 for r in recent_returns if r > 0) / len(recent_returns)
                if recent_returns
                else 0
            )

            # Compare to expected performance (simplified)
            expected_win_rate = 0.55  # Baseline expectation
            win_rate_deviation = recent_win_rate - expected_win_rate

            # Calculate adjustment magnitude
            # Positive deviation = positive adjustment, negative = negative
            adjustment_magnitude = win_rate_deviation * 10  # Scale factor

            # Apply bounds to prevent extreme adjustments
            adjustment_magnitude = max(-5, min(5, adjustment_magnitude))

            return adjustment_magnitude

        except Exception as e:
            logger.error(
                f"Error calculating incremental adjustment for {wallet_address}: {e}"
            )
            return 0.0

    async def _calculate_real_time_confidence_intervals(
        self, wallet_address: str
    ) -> Dict[str, Any]:
        """Calculate real-time confidence intervals for current score."""

        try:
            score_stream = self.score_streams.get(wallet_address, deque())
            if len(score_stream) < 3:
                return {"error": "Insufficient score history for confidence intervals"}

            # Extract recent scores
            recent_scores = [
                entry["score"] for entry in list(score_stream)[-10:]
            ]  # Last 10 scores

            if len(recent_scores) < 3:
                return {"error": "Need at least 3 scores for confidence calculation"}

            # Calculate bootstrap confidence intervals
            n_bootstrap = self.scoring_params["confidence_interval_samples"]
            bootstrap_means = []

            for _ in range(n_bootstrap):
                # Bootstrap resample
                bootstrap_sample = np.random.choice(
                    recent_scores, size=len(recent_scores), replace=True
                )
                bootstrap_means.append(np.mean(bootstrap_sample))

            # Calculate confidence intervals
            ci_lower = np.percentile(bootstrap_means, 5)  # 90% CI
            ci_upper = np.percentile(bootstrap_means, 95)
            ci_mean = np.mean(bootstrap_means)
            ci_std = np.std(bootstrap_means)

            # Calculate confidence level based on interval width
            interval_width = ci_upper - ci_lower
            confidence_level = max(
                0.1, 1 - (interval_width / 20)
            )  # Wider interval = lower confidence

            return {
                "confidence_level": confidence_level,
                "lower_bound": ci_lower,
                "upper_bound": ci_upper,
                "mean_estimate": ci_mean,
                "standard_error": ci_std,
                "interval_width": interval_width,
                "samples_used": len(recent_scores),
            }

        except Exception as e:
            logger.error(
                f"Error calculating confidence intervals for {wallet_address}: {e}"
            )
            return {"error": str(e)}

    async def _calculate_score_stability(self, wallet_address: str) -> Dict[str, Any]:
        """Calculate score stability and trend metrics."""

        try:
            score_stream = self.score_streams.get(wallet_address, deque())
            if len(score_stream) < self.scoring_params["score_stability_window"]:
                return {"stability_score": 0.5, "trend": "insufficient_data"}

            # Extract scores for stability analysis
            recent_scores = [entry["score"] for entry in list(score_stream)]

            # Calculate stability metrics
            score_volatility = np.std(recent_scores)
            score_range = max(recent_scores) - min(recent_scores)

            # Stability score (lower volatility = higher stability)
            max_reasonable_volatility = 15  # Scores typically vary by 15 points
            stability_score = max(0, 1 - (score_volatility / max_reasonable_volatility))

            # Calculate trend
            if len(recent_scores) >= 5:
                # Linear trend
                x = np.arange(len(recent_scores))
                slope, intercept, r_value, p_value, std_err = stats.linregress(
                    x, recent_scores
                )

                # Classify trend
                if abs(slope) < 0.01:  # Very flat
                    trend = "stable"
                    trend_strength = 0
                elif slope > 0.05:
                    trend = "improving"
                    trend_strength = slope
                elif slope < -0.05:
                    trend = "declining"
                    trend_strength = abs(slope)
                else:
                    trend = "stable"
                    trend_strength = abs(slope)

                # Trend significance
                trend_significant = p_value < 0.05
            else:
                trend = "insufficient_data"
                trend_strength = 0
                trend_significant = False

            # Calculate momentum (recent trend vs overall)
            if len(recent_scores) >= 10:
                recent_half = recent_scores[-5:]  # Last 5 scores
                earlier_half = recent_scores[:-5]  # Earlier scores

                recent_avg = np.mean(recent_half)
                earlier_avg = np.mean(earlier_half)

                momentum = (recent_avg - earlier_avg) / max(abs(earlier_avg), 0.1)
            else:
                momentum = 0

            return {
                "stability_score": stability_score,
                "volatility": score_volatility,
                "score_range": score_range,
                "trend": trend,
                "trend_strength": trend_strength,
                "trend_significant": trend_significant,
                "momentum": momentum,
                "samples_used": len(recent_scores),
            }

        except Exception as e:
            logger.error(f"Error calculating score stability for {wallet_address}: {e}")
            return {"stability_score": 0.5, "trend": "error", "error": str(e)}

    async def _predict_score_trend(self, wallet_address: str) -> Dict[str, Any]:
        """Predict future score trends using time series forecasting."""

        try:
            score_stream = self.score_streams.get(wallet_address, deque())
            if len(score_stream) < 10:
                return {"prediction_available": False, "reason": "insufficient_data"}

            # Extract score time series
            scores = [entry["score"] for entry in score_stream]
            timestamps = [
                datetime.fromisoformat(entry["timestamp"]) for entry in score_stream
            ]

            # Convert to hours since first observation
            base_time = timestamps[0]
            hours_elapsed = [(t - base_time).total_seconds() / 3600 for t in timestamps]

            if len(scores) < 5:
                return {
                    "prediction_available": False,
                    "reason": "insufficient_data_points",
                }

            # Fit trend line
            try:
                # Linear trend
                z = np.polyfit(hours_elapsed, scores, 1)
                linear_trend = np.poly1d(z)

                # Predict future scores
                future_hours = np.arange(
                    max(hours_elapsed) + 1,
                    max(hours_elapsed)
                    + self.scoring_params["prediction_horizon_hours"]
                    + 1,
                )

                predicted_scores = linear_trend(future_hours)

                # Calculate prediction confidence
                residuals = scores - linear_trend(hours_elapsed)
                rmse = np.sqrt(np.mean(residuals**2))

                # Prediction intervals (simplified)
                prediction_std = rmse * np.sqrt(1 + 1 / len(scores))
                confidence_interval = 1.96 * prediction_std  # 95% CI

                # Calculate trend direction and strength
                trend_slope = z[0]  # Points per hour
                trend_daily = trend_slope * 24  # Points per day

                if abs(trend_daily) < 0.1:
                    trend_direction = "stable"
                elif trend_daily > 0.5:
                    trend_direction = "strongly_improving"
                elif trend_daily > 0.1:
                    trend_direction = "improving"
                elif trend_daily < -0.5:
                    trend_direction = "strongly_declining"
                elif trend_daily < -0.1:
                    trend_direction = "declining"
                else:
                    trend_direction = "stable"

                return {
                    "prediction_available": True,
                    "predicted_scores": predicted_scores.tolist(),
                    "prediction_hours": future_hours.tolist(),
                    "trend_direction": trend_direction,
                    "trend_slope_daily": trend_daily,
                    "confidence_interval": confidence_interval,
                    "rmse": rmse,
                    "prediction_horizon_hours": self.scoring_params[
                        "prediction_horizon_hours"
                    ],
                }

            except np.RankWarning:
                return {
                    "prediction_available": False,
                    "reason": "insufficient_data_variance",
                }

        except Exception as e:
            logger.error(f"Error predicting score trend for {wallet_address}: {e}")
            return {"prediction_available": False, "reason": str(e)}

    async def _initialize_score_prediction(
        self, wallet_address: str, initial_history: List[Dict[str, Any]]
    ):
        """Initialize score prediction models for a wallet."""

        try:
            # This would train initial prediction models
            # For now, placeholder implementation

            self.score_predictors[wallet_address] = {
                "initialized": True,
                "model_type": "linear_trend",
                "training_samples": len(initial_history),
            }

        except Exception as e:
            logger.error(
                f"Error initializing score prediction for {wallet_address}: {e}"
            )

    async def _check_market_regime_update(
        self, market_conditions: Optional[Dict[str, Any]]
    ):
        """Check if market regime needs updating."""

        try:
            current_time = datetime.now()

            # Check if we need to update market regime
            last_update = self.market_regime_state.get("last_update")
            if last_update:
                last_update_time = datetime.fromisoformat(last_update)
                time_since_update = (current_time - last_update_time).total_seconds()

                if (
                    time_since_update
                    < self.scoring_params["market_regime_check_interval"]
                ):
                    return  # No update needed

            # Update market regime
            if market_conditions:
                regime = self.quality_scorer._determine_market_regime(market_conditions)
            else:
                regime = "normal"  # Default

            self.market_regime_state = {
                "current_regime": regime,
                "last_update": current_time.isoformat(),
                "conditions": market_conditions,
            }

        except Exception as e:
            logger.error(f"Error checking market regime update: {e}")

    async def _apply_market_regime_adjustment(
        self, wallet_address: str, base_score: Optional[float]
    ) -> Optional[float]:
        """Apply market regime adjustments to scores."""

        try:
            if base_score is None:
                return None

            current_regime = self.market_regime_state.get("current_regime", "normal")

            # Get regime-specific adjustments
            # In practice, this would use historical regime performance data
            regime_adjustments = {
                "bull": 1.05,  # Slightly higher scores in bull markets
                "bear": 0.95,  # Slightly lower scores in bear markets
                "high_volatility": 0.98,  # Conservative adjustment for volatility
                "low_liquidity": 0.97,  # Conservative for low liquidity
                "normal": 1.0,  # No adjustment
            }

            adjustment_factor = regime_adjustments.get(current_regime, 1.0)

            return base_score * adjustment_factor

        except Exception as e:
            logger.error(
                f"Error applying market regime adjustment for {wallet_address}: {e}"
            )
            return base_score

    async def _check_score_alerts(
        self,
        wallet_address: str,
        current_score: Optional[float],
        stability_metrics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Check for score alerts that require attention."""

        alerts = []

        try:
            if current_score is None:
                return alerts

            score_stream = self.score_streams.get(wallet_address, deque())
            if not score_stream:
                return alerts

            # Check for significant score changes
            if len(score_stream) >= 2:
                previous_score = score_stream[-2]["score"]
                score_change = current_score - previous_score
                change_pct = abs(score_change) / max(abs(previous_score), 0.1)

                if change_pct >= self.scoring_params["alert_threshold_change"]:
                    alerts.append(
                        {
                            "type": "score_change",
                            "severity": "high" if change_pct >= 0.2 else "medium",
                            "message": f"Score changed by {change_pct:.1%} ({previous_score:.1f} → {current_score:.1f})",
                            "direction": "increased"
                            if score_change > 0
                            else "decreased",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            # Check for score instability
            stability_score = stability_metrics.get("stability_score", 1.0)
            volatility = stability_metrics.get("volatility", 0)

            if (
                stability_score < 0.5
                or volatility > self.scoring_params["stability_threshold"]
            ):
                alerts.append(
                    {
                        "type": "score_instability",
                        "severity": "medium",
                        "message": f"Score instability detected (stability: {stability_score:.2f}, volatility: {volatility:.2f})",
                        "recommendation": "Monitor score closely for stabilization",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Check for trend alerts
            trend = stability_metrics.get("trend", "stable")
            trend_strength = stability_metrics.get("trend_strength", 0)

            if trend in ["strongly_declining", "declining"] and trend_strength > 0.1:
                alerts.append(
                    {
                        "type": "negative_trend",
                        "severity": "high",
                        "message": f"Score trending {trend} (strength: {trend_strength:.3f})",
                        "recommendation": "Investigate causes of score deterioration",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        except Exception as e:
            logger.error(f"Error checking score alerts for {wallet_address}: {e}")

        return alerts

    def _calculate_data_freshness(self, wallet_address: str) -> Dict[str, Any]:
        """Calculate how fresh the scoring data is."""

        try:
            wallet_state = self.active_wallets.get(wallet_address, {})
            last_update = wallet_state.get(
                "last_incremental_update"
            ) or wallet_state.get("last_full_update")

            if last_update:
                last_update_time = datetime.fromisoformat(last_update)
                time_since_update = (datetime.now() - last_update_time).total_seconds()

                # Classify freshness
                if time_since_update < 600:  # 10 minutes
                    freshness = "very_fresh"
                elif time_since_update < 1800:  # 30 minutes
                    freshness = "fresh"
                elif time_since_update < 3600:  # 1 hour
                    freshness = "stale"
                else:
                    freshness = "very_stale"

                return {
                    "freshness_level": freshness,
                    "seconds_since_update": time_since_update,
                    "last_update": last_update,
                }
            else:
                return {
                    "freshness_level": "no_data",
                    "seconds_since_update": None,
                    "last_update": None,
                }

        except Exception as e:
            logger.error(f"Error calculating data freshness for {wallet_address}: {e}")
            return {"freshness_level": "error", "error": str(e)}

    async def _get_current_market_conditions(self) -> Dict[str, Any]:
        """Get current market conditions (placeholder)."""

        # In practice, this would fetch real market data
        return {"volatility_index": 0.2, "liquidity_score": 0.6, "trend_strength": 0.0}

    def get_engine_status(self) -> Dict[str, Any]:
        """Get comprehensive engine status."""

        try:
            total_wallets = len(self.active_wallets)
            active_streams = sum(1 for stream in self.score_streams.values() if stream)

            # Calculate performance metrics
            avg_update_time = np.mean(self.update_times) if self.update_times else None

            # Alert summary
            recent_alerts = [
                alert
                for alert in self.score_alerts
                if (datetime.now() - datetime.fromisoformat(alert["timestamp"])).seconds
                < 3600
            ]

            return {
                "total_wallets": total_wallets,
                "active_streams": active_streams,
                "average_update_time": avg_update_time,
                "total_updates_processed": len(self.update_times),
                "recent_alerts_count": len(recent_alerts),
                "market_regime": self.market_regime_state.get(
                    "current_regime", "unknown"
                ),
                "engine_health": "healthy" if total_wallets > 0 else "idle",
            }

        except Exception as e:
            logger.error(f"Error getting engine status: {e}")
            return {"error": str(e)}

    def save_real_time_state(self):
        """Save real-time scoring state."""

        try:
            state_dir = Path("data/real_time_scoring")
            state_dir.mkdir(parents=True, exist_ok=True)

            # Save active wallets
            with open(state_dir / "active_wallets.json", "w") as f:
                json.dump(self.active_wallets, f, indent=2, default=str)

            # Save score streams (last 50 entries per wallet)
            score_streams_data = {}
            for wallet, stream in self.score_streams.items():
                score_streams_data[wallet] = list(stream)[-50:]  # Last 50 scores

            with open(state_dir / "score_streams.json", "w") as f:
                json.dump(score_streams_data, f, indent=2, default=str)

            # Save market regime state
            with open(state_dir / "market_regime.json", "w") as f:
                json.dump(self.market_regime_state, f, indent=2, default=str)

            logger.info(f"💾 Real-time scoring state saved to {state_dir}")

        except Exception as e:
            logger.error(f"Error saving real-time scoring state: {e}")

    def load_real_time_state(self):
        """Load real-time scoring state."""

        try:
            state_dir = Path("data/real_time_scoring")

            # Load active wallets
            wallets_file = state_dir / "active_wallets.json"
            if wallets_file.exists():
                with open(wallets_file, "r") as f:
                    self.active_wallets = json.load(f)

            # Load score streams
            streams_file = state_dir / "score_streams.json"
            if streams_file.exists():
                with open(streams_file, "r") as f:
                    streams_data = json.load(f)
                    for wallet, stream_data in streams_data.items():
                        self.score_streams[wallet] = deque(
                            stream_data,
                            maxlen=self.scoring_params["trend_analysis_window"],
                        )

            # Load market regime
            regime_file = state_dir / "market_regime.json"
            if regime_file.exists():
                with open(regime_file, "r") as f:
                    self.market_regime_state = json.load(f)

            logger.info(f"📊 Real-time scoring state loaded from {state_dir}")

        except Exception as e:
            logger.error(f"Error loading real-time scoring state: {e}")

    async def run_scoring_loop(self, update_interval_seconds: int = 60):
        """Run continuous real-time scoring updates."""

        logger.info(
            f"🔄 Starting real-time scoring loop (update interval: {update_interval_seconds}s)"
        )

        while True:
            try:
                # Process any pending updates
                for wallet_address in list(self.active_wallets.keys()):
                    pending_count = len(self.pending_updates.get(wallet_address, []))
                    if pending_count > 0:
                        await self._perform_incremental_update(wallet_address)

                # Check for wallets needing full updates
                current_time = datetime.now()
                for wallet_address, wallet_state in self.active_wallets.items():
                    last_full_update = wallet_state.get("last_full_update")
                    if last_full_update:
                        last_update_time = datetime.fromisoformat(last_full_update)
                        time_since_update = (
                            current_time - last_update_time
                        ).total_seconds()

                        if (
                            time_since_update
                            >= self.scoring_params["update_interval_seconds"]
                        ):
                            # Trigger full update (would need trade history)
                            logger.debug(f"Due for full update: {wallet_address}")

                await asyncio.sleep(update_interval_seconds)

            except Exception as e:
                logger.error(f"Error in scoring loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
