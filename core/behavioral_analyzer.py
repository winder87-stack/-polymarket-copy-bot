"""
Behavioral Analysis for Wallet Quality Scoring
===============================================

Advanced behavioral analysis system for detecting strategy evolution,
performance decay, risk management quality, and sustainability metrics.

Features:
- Strategy evolution detection using change point analysis
- Performance decay analysis with statistical trend detection
- Risk management quality assessment
- Emotional trading pattern detection
- Behavioral sustainability scoring
- Early warning systems for strategy degradation
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from utils.helpers import BoundedCache

logger = logging.getLogger(__name__)


class BehaviorPatternTracker:
    """
    Tracks and analyzes behavioral patterns in wallet trading activity.

    Detects changes in strategy, performance trends, and behavioral consistency
    to assess wallet sustainability for copy trading.
    """

    def __init__(self):
        # Pattern tracking parameters
        self.pattern_params = {
            "change_point_detection_threshold": 0.15,  # Statistical significance threshold
            "performance_decay_window": 90,  # Days for decay analysis
            "strategy_stability_window": 60,  # Days for stability assessment
            "emotional_trading_threshold": 0.25,  # Threshold for emotional patterns
            "pattern_recognition_min_samples": 50,  # Minimum trades for pattern analysis
            "correlation_stability_periods": 30,  # Periods for correlation stability
        }

        # Behavioral state tracking
        self.wallet_patterns: Dict[str, Dict[str, Any]] = {}
        self.performance_trends = BoundedCache(max_size=5000, ttl_seconds=2592000)  # 30 days

        logger.info("🧠 Behavior pattern tracker initialized")

    async def analyze_behavioral_patterns(
        self,
        wallet_address: str,
        trade_history: List[Dict[str, Any]],
        analysis_period_days: int = 90,
    ) -> Dict[str, Any]:
        """
        Comprehensive behavioral pattern analysis for a wallet.

        Args:
            wallet_address: Wallet to analyze
            trade_history: Historical trade data
            analysis_period_days: Analysis period in days

        Returns:
            Complete behavioral analysis report
        """

        if len(trade_history) < self.pattern_params["pattern_recognition_min_samples"]:
            return self._create_insufficient_data_response(wallet_address)

        try:
            # Filter recent trades
            cutoff_date = datetime.now() - timedelta(days=analysis_period_days)
            recent_trades = [
                t for t in trade_history if datetime.fromisoformat(t["timestamp"]) > cutoff_date
            ]

            if len(recent_trades) < 20:
                return self._create_insufficient_data_response(
                    wallet_address, "insufficient_recent_data"
                )

            # Perform behavioral analyses
            analysis_results = {
                "wallet_address": wallet_address,
                "analysis_period_days": analysis_period_days,
                "trade_count_analyzed": len(recent_trades),
                "analysis_timestamp": datetime.now().isoformat(),
            }

            # Core behavioral metrics
            analysis_results["strategy_evolution"] = await self._detect_strategy_evolution(
                recent_trades
            )
            analysis_results["performance_decay"] = await self._analyze_performance_decay(
                recent_trades
            )
            analysis_results["behavioral_consistency"] = await self._assess_behavioral_consistency(
                recent_trades
            )
            analysis_results["emotional_trading"] = await self._detect_emotional_trading(
                recent_trades
            )
            analysis_results["risk_management_quality"] = (
                await self._assess_risk_management_quality(recent_trades)
            )
            analysis_results["capital_efficiency"] = await self._analyze_capital_efficiency(
                recent_trades
            )
            analysis_results["pattern_stability"] = await self._assess_pattern_stability(
                recent_trades
            )

            # Composite sustainability score
            analysis_results["sustainability_score"] = self._calculate_sustainability_score(
                analysis_results
            )

            # Early warning signals
            analysis_results["early_warnings"] = self._generate_early_warnings(analysis_results)

            # Store pattern data for future comparison
            self._store_behavioral_patterns(wallet_address, analysis_results)

            return analysis_results

        except Exception as e:
            logger.error(f"Error analyzing behavioral patterns for {wallet_address}: {e}")
            return {
                "wallet_address": wallet_address,
                "error": str(e),
                "analysis_timestamp": datetime.now().isoformat(),
            }

    async def _detect_strategy_evolution(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect significant changes in trading strategy using change point analysis.

        Uses statistical methods to identify when a wallet's strategy has evolved
        significantly, indicating potential changes in approach or conditions.
        """

        evolution_analysis = {
            "evolution_detected": False,
            "evolution_points": [],
            "evolution_magnitude": 0.0,
            "evolution_confidence": 0.0,
            "strategy_stability_score": 100.0,
            "evolution_timeline": [],
        }

        try:
            if len(trade_history) < 30:
                return evolution_analysis

            # Extract key metrics over time
            metrics_over_time = self._extract_temporal_metrics(trade_history)

            if not metrics_over_time:
                return evolution_analysis

            # Apply change point detection to each metric
            change_points = {}
            for metric_name, values in metrics_over_time.items():
                if len(values) >= 20:
                    cps = self._detect_change_points(values, metric_name)
                    if cps:
                        change_points[metric_name] = cps

            # Analyze change point significance
            if change_points:
                # Find most significant change points across all metrics
                significant_changes = self._analyze_change_point_significance(change_points)

                if significant_changes:
                    evolution_analysis["evolution_detected"] = True
                    evolution_analysis["evolution_points"] = significant_changes["change_points"]
                    evolution_analysis["evolution_magnitude"] = significant_changes["magnitude"]
                    evolution_analysis["evolution_confidence"] = significant_changes["confidence"]

                    # Calculate strategy stability score (lower evolution = higher stability)
                    stability_penalty = min(100, significant_changes["magnitude"] * 200)
                    evolution_analysis["strategy_stability_score"] = max(0, 100 - stability_penalty)

                    # Create evolution timeline
                    evolution_analysis["evolution_timeline"] = self._create_evolution_timeline(
                        significant_changes, trade_history
                    )

            return evolution_analysis

        except Exception as e:
            logger.error(f"Error detecting strategy evolution: {e}")
            evolution_analysis["error"] = str(e)
            return evolution_analysis

    def _extract_temporal_metrics(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, List[float]]:
        """Extract key metrics over time for change point analysis."""

        metrics = {
            "win_rate": [],
            "avg_return": [],
            "trade_frequency": [],
            "position_size": [],
            "holding_time": [],
        }

        # Sort trades by timestamp
        sorted_trades = sorted(trade_history, key=lambda x: x["timestamp"])

        # Calculate rolling metrics
        window_size = max(5, len(sorted_trades) // 10)  # Adaptive window size

        for i in range(window_size, len(sorted_trades) + 1):
            window_trades = sorted_trades[i - window_size : i]

            # Win rate
            wins = sum(1 for t in window_trades if t.get("pnl_pct", 0) > 0)
            win_rate = wins / len(window_trades) if window_trades else 0
            metrics["win_rate"].append(win_rate)

            # Average return
            returns = [t.get("pnl_pct", 0) for t in window_trades]
            avg_return = np.mean(returns) if returns else 0
            metrics["avg_return"].append(avg_return)

            # Trade frequency (trades per hour in window)
            if len(window_trades) >= 2:
                time_span = (
                    datetime.fromisoformat(window_trades[-1]["timestamp"])
                    - datetime.fromisoformat(window_trades[0]["timestamp"])
                ).total_seconds() / 3600
                frequency = len(window_trades) / max(time_span, 1)
            else:
                frequency = 0
            metrics["trade_frequency"].append(frequency)

            # Average position size
            sizes = [abs(t.get("amount", 0)) for t in window_trades]
            avg_size = np.mean(sizes) if sizes else 0
            metrics["position_size"].append(avg_size)

            # Average holding time
            holding_times = []
            for trade in window_trades:
                holding_time = trade.get("holding_time_hours", 24)  # Default 1 day
                holding_times.append(holding_time)
            avg_holding = np.mean(holding_times) if holding_times else 0
            metrics["holding_time"].append(avg_holding)

        return metrics

    def _detect_change_points(self, values: List[float], metric_name: str) -> List[Dict[str, Any]]:
        """Detect change points in a time series using statistical methods."""

        try:
            if len(values) < 10:
                return []

            values_array = np.array(values)

            # Method 1: CUSUM (Cumulative Sum) for change detection
            cusum_changes = self._cusum_change_detection(values_array)

            # Method 2: Variance change detection
            variance_changes = self._variance_change_detection(values_array)

            # Method 3: Trend change detection
            trend_changes = self._trend_change_detection(values_array)

            # Combine and filter change points
            all_changes = cusum_changes + variance_changes + trend_changes

            # Remove duplicates and sort
            unique_changes = self._filter_change_points(all_changes, len(values))

            change_points = []
            for cp in unique_changes:
                confidence = self._calculate_change_point_confidence(cp, values_array)

                if confidence > self.pattern_params["change_point_detection_threshold"]:
                    change_points.append(
                        {
                            "position": cp,
                            "confidence": confidence,
                            "method": "combined",
                            "metric": metric_name,
                        }
                    )

            return change_points

        except Exception as e:
            logger.error(f"Error detecting change points: {e}")
            return []

    def _cusum_change_detection(self, values: np.ndarray) -> List[int]:
        """CUSUM (Cumulative Sum Control Chart) change detection."""

        try:
            # Calculate CUSUM statistics
            mean_val = np.mean(values)
            cusum = np.cumsum(values - mean_val)

            # Find points where CUSUM changes significantly
            cusum_diff = np.diff(cusum)
            threshold = np.std(cusum_diff) * 2

            change_indices = np.where(np.abs(cusum_diff) > threshold)[0] + 1

            return change_indices.tolist()

        except Exception:
            return []

    def _variance_change_detection(self, values: np.ndarray) -> List[int]:
        """Detect changes in variance using rolling statistics."""

        try:
            window_size = max(5, len(values) // 5)
            rolling_var = pd.Series(values).rolling(window=window_size).var()

            # Find significant variance changes
            var_changes = np.where(np.abs(np.diff(rolling_var.values)) > np.std(rolling_var) * 1.5)[
                0
            ]

            return var_changes.tolist()

        except Exception:
            return []

    def _trend_change_detection(self, values: np.ndarray) -> List[int]:
        """Detect trend changes in the time series."""

        try:
            # Use local linear regression to detect trend changes
            window_size = max(10, len(values) // 4)

            trend_changes = []
            for i in range(window_size, len(values) - window_size):
                # Fit linear trend to segments before and after point
                before_segment = values[i - window_size : i]
                after_segment = values[i : i + window_size]

                if len(before_segment) >= 5 and len(after_segment) >= 5:
                    before_slope = np.polyfit(range(len(before_segment)), before_segment, 1)[0]
                    after_slope = np.polyfit(range(len(after_segment)), after_segment, 1)[0]

                    slope_change = abs(after_slope - before_slope)

                    if slope_change > np.std(values) * 0.5:  # Significant slope change
                        trend_changes.append(i)

            return trend_changes

        except Exception:
            return []

    def _filter_change_points(self, change_points: List[int], series_length: int) -> List[int]:
        """Filter and deduplicate change points."""

        if not change_points:
            return []

        # Sort and remove duplicates within 5 points
        sorted_cps = sorted(set(change_points))

        filtered_cps = []
        for cp in sorted_cps:
            # Check if too close to previously added points
            if not filtered_cps or min(abs(cp - prev_cp) for prev_cp in filtered_cps) >= 5:
                # Ensure within valid range
                if 0.1 * series_length <= cp <= 0.9 * series_length:
                    filtered_cps.append(cp)

        return filtered_cps

    def _calculate_change_point_confidence(self, change_point: int, values: np.ndarray) -> float:
        """Calculate confidence score for a change point."""

        try:
            if change_point <= 5 or change_point >= len(values) - 5:
                return 0.0

            # Compare means and variances before/after change point
            before_values = values[:change_point]
            after_values = values[change_point:]

            # T-test for mean difference
            t_stat, p_value = stats.ttest_ind(before_values, after_values)

            # F-test for variance difference
            f_stat = np.var(before_values) / np.var(after_values) if np.var(after_values) > 0 else 1
            f_p_value = stats.f.cdf(f_stat, len(before_values) - 1, len(after_values) - 1)

            # Combined confidence (lower p-values = higher confidence)
            mean_confidence = 1 - p_value
            variance_confidence = 1 - f_p_value

            confidence = (mean_confidence + variance_confidence) / 2

            return min(confidence, 1.0)

        except Exception:
            return 0.0

    def _analyze_change_point_significance(
        self, change_points: Dict[str, List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """Analyze the significance of detected change points across metrics."""

        try:
            all_changes = []
            for metric, cps in change_points.items():
                for cp in cps:
                    all_changes.append(
                        {
                            "metric": metric,
                            "position": cp["position"],
                            "confidence": cp["confidence"],
                        }
                    )

            if not all_changes:
                return None

            # Group change points by position (within 10% tolerance)
            grouped_changes = self._group_change_points_by_position(all_changes)

            # Find most significant cluster
            most_significant = max(grouped_changes, key=lambda x: x["total_confidence"])

            return {
                "change_points": most_significant["positions"],
                "magnitude": most_significant["magnitude"],
                "confidence": most_significant["total_confidence"],
                "affected_metrics": most_significant["metrics"],
            }

        except Exception as e:
            logger.error(f"Error analyzing change point significance: {e}")
            return None

    def _group_change_points_by_position(
        self, changes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Group change points by similar positions."""

        try:
            positions = np.array([c["position"] for c in changes])
            confidences = np.array([c["confidence"] for c in changes])

            # Use clustering to group similar positions
            if len(positions) >= 2:
                # Normalize positions
                scaler = StandardScaler()
                positions_scaled = scaler.fit_transform(positions.reshape(-1, 1))

                # Cluster positions
                kmeans = KMeans(n_clusters=min(3, len(positions)), random_state=42, n_init=10)
                clusters = kmeans.fit_predict(positions_scaled)

                # Group by cluster
                grouped = defaultdict(list)
                for i, cluster in enumerate(clusters):
                    grouped[cluster].append(
                        {
                            "position": positions[i],
                            "confidence": confidences[i],
                            "metric": changes[i]["metric"],
                        }
                    )

                # Calculate cluster statistics
                cluster_stats = []
                for cluster_id, cluster_changes in grouped.items():
                    np.mean([c["position"] for c in cluster_changes])
                    total_confidence = np.mean([c["confidence"] for c in cluster_changes])
                    magnitude = (
                        len(cluster_changes) * total_confidence
                    )  # Simple magnitude calculation
                    metrics_affected = list(set(c["metric"] for c in cluster_changes))

                    cluster_stats.append(
                        {
                            "positions": [int(c["position"]) for c in cluster_changes],
                            "magnitude": magnitude,
                            "total_confidence": total_confidence,
                            "metrics": metrics_affected,
                        }
                    )

                return cluster_stats

            else:
                # Single change point
                return [
                    {
                        "positions": [int(changes[0]["position"])],
                        "magnitude": changes[0]["confidence"],
                        "total_confidence": changes[0]["confidence"],
                        "metrics": [changes[0]["metric"]],
                    }
                ]

        except Exception as e:
            logger.error(f"Error grouping change points: {e}")
            return []

    def _create_evolution_timeline(
        self, significant_changes: Dict[str, Any], trade_history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create a timeline of strategy evolution events."""

        timeline = []

        try:
            for cp_position in significant_changes["change_points"]:
                # Convert position to trade index and then to timestamp
                trade_index = int(
                    cp_position * len(trade_history) / 100
                )  # Assuming percentage-based position

                if trade_index < len(trade_history):
                    trade = trade_history[trade_index]
                    timeline.append(
                        {
                            "timestamp": trade["timestamp"],
                            "change_point_position": cp_position,
                            "trade_index": trade_index,
                            "confidence": significant_changes["confidence"],
                            "affected_metrics": significant_changes["affected_metrics"],
                        }
                    )

        except Exception as e:
            logger.error(f"Error creating evolution timeline: {e}")

        return timeline

    async def _analyze_performance_decay(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze performance decay over time using statistical trend analysis.

        Detects if wallet performance is deteriorating, which could indicate
        strategy fatigue, changing market conditions, or other issues.
        """

        decay_analysis = {
            "decay_detected": False,
            "decay_rate": 0.0,
            "decay_confidence": 0.0,
            "performance_trend": "stable",
            "decay_magnitude": 0.0,
            "time_to_significance": 0,
        }

        try:
            if len(trade_history) < 30:
                return decay_analysis

            # Extract performance metrics over time
            performance_series = self._extract_performance_series(trade_history)

            if not performance_series or len(performance_series) < 10:
                return decay_analysis

            # Apply multiple decay detection methods
            trend_decay = self._detect_trend_decay(performance_series)
            volatility_decay = self._detect_volatility_decay(performance_series)
            consistency_decay = self._detect_consistency_decay(trade_history)

            # Combine decay signals
            decay_signals = [trend_decay, volatility_decay, consistency_decay]
            decay_scores = [d["decay_score"] for d in decay_signals if "decay_score" in d]

            if decay_scores:
                overall_decay_score = np.mean(decay_scores)
                decay_confidence = np.std(decay_scores)  # Lower std = higher confidence

                decay_analysis["decay_rate"] = overall_decay_score
                decay_analysis["decay_confidence"] = min(1.0, 1.0 / (1.0 + decay_confidence))

                # Determine if decay is significant
                threshold = 0.1  # 10% decay threshold
                if overall_decay_score > threshold and decay_analysis["decay_confidence"] > 0.7:
                    decay_analysis["decay_detected"] = True
                    decay_analysis["decay_magnitude"] = overall_decay_score

                    # Classify trend
                    if overall_decay_score > 0.2:
                        decay_analysis["performance_trend"] = "strong_decay"
                    elif overall_decay_score > 0.1:
                        decay_analysis["performance_trend"] = "moderate_decay"
                    else:
                        decay_analysis["performance_trend"] = "mild_decay"

                    # Estimate time to significance
                    decay_analysis["time_to_significance"] = self._estimate_decay_time_significance(
                        performance_series, overall_decay_score
                    )

            return decay_analysis

        except Exception as e:
            logger.error(f"Error analyzing performance decay: {e}")
            decay_analysis["error"] = str(e)
            return decay_analysis

    def _extract_performance_series(self, trade_history: List[Dict[str, Any]]) -> List[float]:
        """Extract rolling performance metrics for decay analysis."""

        try:
            # Sort trades by timestamp
            sorted_trades = sorted(trade_history, key=lambda x: x["timestamp"])

            # Calculate rolling win rates
            window_size = max(10, len(sorted_trades) // 10)
            performance_scores = []

            for i in range(window_size, len(sorted_trades) + 1):
                window_trades = sorted_trades[i - window_size : i]

                # Calculate composite performance score
                wins = sum(1 for t in window_trades if t.get("pnl_pct", 0) > 0)
                win_rate = wins / len(window_trades)

                avg_return = np.mean([t.get("pnl_pct", 0) for t in window_trades])

                # Normalize and combine
                normalized_win_rate = win_rate
                normalized_return = (avg_return + 0.05) / 0.1  # Assume -5% to +5% range
                normalized_return = max(0, min(1, normalized_return))

                composite_score = (normalized_win_rate + normalized_return) / 2
                performance_scores.append(composite_score)

            return performance_scores

        except Exception as e:
            logger.error(f"Error extracting performance series: {e}")
            return []

    def _detect_trend_decay(self, performance_series: List[float]) -> Dict[str, Any]:
        """Detect decay using trend analysis."""

        try:
            if len(performance_series) < 5:
                return {"decay_score": 0.0}

            # Linear regression trend
            x = np.arange(len(performance_series))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, performance_series)

            # Negative slope indicates decay
            decay_score = max(0, -slope)  # Only consider negative trends
            confidence = 1 - p_value  # Lower p-value = higher confidence

            return {
                "decay_score": decay_score,
                "confidence": confidence,
                "trend_slope": slope,
                "r_squared": r_value**2,
            }

        except Exception:
            return {"decay_score": 0.0}

    def _detect_volatility_decay(self, performance_series: List[float]) -> Dict[str, Any]:
        """Detect decay through increasing volatility."""

        try:
            if len(performance_series) < 10:
                return {"decay_score": 0.0}

            # Calculate rolling volatility
            window_size = max(5, len(performance_series) // 4)
            rolling_volatility = []

            for i in range(window_size, len(performance_series) + 1):
                window = performance_series[i - window_size : i]
                vol = np.std(window)
                rolling_volatility.append(vol)

            # Check if volatility is increasing
            if len(rolling_volatility) >= 3:
                vol_trend = np.polyfit(range(len(rolling_volatility)), rolling_volatility, 1)[0]
                decay_score = max(0, vol_trend * 10)  # Scale appropriately
            else:
                decay_score = 0.0

            return {"decay_score": decay_score}

        except Exception:
            return {"decay_score": 0.0}

    def _detect_consistency_decay(self, trade_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect decay in behavioral consistency."""

        try:
            # Split history into halves
            mid_point = len(trade_history) // 2
            first_half = trade_history[:mid_point]
            second_half = trade_history[mid_point:]

            if len(first_half) < 10 or len(second_half) < 10:
                return {"decay_score": 0.0}

            # Calculate consistency metrics for each half
            first_metrics = self._calculate_consistency_metrics(first_half)
            second_metrics = self._calculate_consistency_metrics(second_half)

            # Compare consistency between halves
            consistency_decay = 0
            for metric in first_metrics:
                if metric in second_metrics:
                    first_val = first_metrics[metric]
                    second_val = second_metrics[metric]

                    if first_val > 0:
                        change = abs(second_val - first_val) / first_val
                        consistency_decay += change

            decay_score = consistency_decay / len(first_metrics) if first_metrics else 0

            return {"decay_score": min(decay_score, 1.0)}

        except Exception:
            return {"decay_score": 0.0}

    def _calculate_consistency_metrics(self, trades: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate consistency metrics for a set of trades."""

        metrics = {}

        if not trades:
            return metrics

        # Win rate consistency
        wins = sum(1 for t in trades if t.get("pnl_pct", 0) > 0)
        metrics["win_rate"] = wins / len(trades)

        # Return consistency
        returns = [t.get("pnl_pct", 0) for t in trades]
        metrics["return_volatility"] = np.std(returns) if returns else 0

        # Trade frequency consistency
        timestamps = [datetime.fromisoformat(t["timestamp"]) for t in trades]
        if len(timestamps) >= 2:
            intervals = [
                (timestamps[i] - timestamps[i - 1]).total_seconds() / 3600
                for i in range(1, len(timestamps))
            ]
            metrics["frequency_volatility"] = np.std(intervals) if intervals else 0

        return metrics

    def _estimate_decay_time_significance(
        self, performance_series: List[float], decay_rate: float
    ) -> int:
        """Estimate time until performance decay becomes statistically significant."""

        try:
            if decay_rate <= 0 or len(performance_series) < 10:
                return 0

            # Simple extrapolation - how many more periods until performance reaches zero
            current_performance = performance_series[-1]
            periods_to_zero = int(current_performance / decay_rate) if decay_rate > 0 else 0

            return min(periods_to_zero, 365)  # Cap at 1 year

        except Exception:
            return 0

    async def _assess_behavioral_consistency(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess overall behavioral consistency of the wallet."""

        consistency_analysis = {
            "consistency_score": 0.0,
            "consistency_components": {},
            "consistency_trend": "stable",
            "inconsistency_events": [],
        }

        try:
            # Analyze different aspects of consistency
            temporal_consistency = await self._analyze_temporal_consistency(trade_history)
            strategy_consistency = await self._analyze_strategy_consistency(trade_history)
            risk_consistency = await self._analyze_risk_consistency(trade_history)

            consistency_components = {
                "temporal": temporal_consistency,
                "strategy": strategy_consistency,
                "risk": risk_consistency,
            }

            # Calculate overall consistency score
            component_scores = [c["score"] for c in consistency_components.values() if "score" in c]
            overall_score = np.mean(component_scores) if component_scores else 0.5

            consistency_analysis["consistency_score"] = overall_score
            consistency_analysis["consistency_components"] = consistency_components

            # Determine trend
            if overall_score >= 0.8:
                consistency_analysis["consistency_trend"] = "highly_consistent"
            elif overall_score >= 0.6:
                consistency_analysis["consistency_trend"] = "consistent"
            elif overall_score >= 0.4:
                consistency_analysis["consistency_trend"] = "moderately_consistent"
            else:
                consistency_analysis["consistency_trend"] = "inconsistent"

            # Identify inconsistency events
            inconsistency_events = []
            for component_name, component_data in consistency_components.items():
                if "anomalies" in component_data:
                    for anomaly in component_data["anomalies"]:
                        inconsistency_events.append(
                            {
                                "component": component_name,
                                "type": anomaly.get("type", "unknown"),
                                "severity": anomaly.get("severity", 0),
                                "timestamp": anomaly.get("timestamp"),
                            }
                        )

            consistency_analysis["inconsistency_events"] = inconsistency_events

            return consistency_analysis

        except Exception as e:
            logger.error(f"Error assessing behavioral consistency: {e}")
            consistency_analysis["error"] = str(e)
            return consistency_analysis

    async def _analyze_temporal_consistency(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze consistency in trading timing and frequency."""

        try:
            timestamps = [datetime.fromisoformat(t["timestamp"]) for t in trade_history]

            if len(timestamps) < 5:
                return {"score": 0.5}

            # Calculate inter-trade intervals
            intervals_hours = []
            for i in range(1, len(timestamps)):
                interval = (timestamps[i] - timestamps[i - 1]).total_seconds() / 3600
                intervals_hours.append(interval)

            if not intervals_hours:
                return {"score": 0.5}

            # Analyze interval consistency
            interval_mean = np.mean(intervals_hours)
            interval_std = np.std(intervals_hours)
            cv = interval_std / interval_mean if interval_mean > 0 else 0

            # Lower CV = more consistent timing
            consistency_score = max(0, 1 - cv * 2)  # Scale CV to 0-1

            # Detect anomalies
            anomalies = []
            threshold = interval_mean + 2 * interval_std

            for i, interval in enumerate(intervals_hours):
                if interval > threshold:
                    anomalies.append(
                        {
                            "type": "timing_gap",
                            "severity": min(1.0, interval / (interval_mean * 3)),
                            "timestamp": timestamps[i + 1].isoformat(),
                            "interval_hours": interval,
                        }
                    )

            return {
                "score": consistency_score,
                "coefficient_of_variation": cv,
                "average_interval_hours": interval_mean,
                "anomalies": anomalies,
            }

        except Exception as e:
            logger.error(f"Error analyzing temporal consistency: {e}")
            return {"score": 0.5, "error": str(e)}

    async def _analyze_strategy_consistency(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze consistency in trading strategy execution."""

        try:
            # Analyze key strategy metrics
            metrics_consistency = {}

            # Profit taking consistency
            take_profit_ratios = [
                t.get("take_profit_pct", 0)
                for t in trade_history
                if t.get("take_profit_pct", 0) > 0
            ]
            if take_profit_ratios:
                tp_cv = (
                    np.std(take_profit_ratios) / np.mean(take_profit_ratios)
                    if np.mean(take_profit_ratios) > 0
                    else 0
                )
                metrics_consistency["take_profit"] = max(0, 1 - tp_cv)

            # Stop loss consistency
            stop_loss_ratios = [
                abs(t.get("stop_loss_pct", 0))
                for t in trade_history
                if t.get("stop_loss_pct", 0) != 0
            ]
            if stop_loss_ratios:
                sl_cv = (
                    np.std(stop_loss_ratios) / np.mean(stop_loss_ratios)
                    if np.mean(stop_loss_ratios) > 0
                    else 0
                )
                metrics_consistency["stop_loss"] = max(0, 1 - sl_cv)

            # Position sizing consistency
            sizes = [abs(t.get("amount", 0)) for t in trade_history]
            if sizes:
                size_cv = np.std(sizes) / np.mean(sizes) if np.mean(sizes) > 0 else 0
                metrics_consistency["position_size"] = max(0, 1 - size_cv)

            # Holding time consistency
            holding_times = [t.get("holding_time_hours", 24) for t in trade_history]
            if holding_times:
                ht_cv = (
                    np.std(holding_times) / np.mean(holding_times)
                    if np.mean(holding_times) > 0
                    else 0
                )
                metrics_consistency["holding_time"] = max(0, 1 - ht_cv)

            # Overall strategy consistency
            if metrics_consistency:
                strategy_score = np.mean(list(metrics_consistency.values()))
            else:
                strategy_score = 0.5

            return {
                "score": strategy_score,
                "metric_consistency": metrics_consistency,
                "anomalies": [],  # Could add strategy anomaly detection
            }

        except Exception as e:
            logger.error(f"Error analyzing strategy consistency: {e}")
            return {"score": 0.5, "error": str(e)}

    async def _analyze_risk_consistency(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze consistency in risk management."""

        try:
            # Risk metrics consistency
            risk_metrics = {}

            # Return distribution consistency
            returns = [t.get("pnl_pct", 0) for t in trade_history]
            if returns:
                return_skewness = stats.skew(returns)
                stats.kurtosis(returns)
                risk_metrics["return_distribution"] = (
                    1 - abs(return_skewness) / 2
                )  # Penalize extreme skewness

            # Risk-adjusted return consistency
            if len(returns) >= 10:
                rolling_sharpe = []
                window_size = max(5, len(returns) // 5)

                for i in range(window_size, len(returns) + 1):
                    window_returns = returns[i - window_size : i]
                    if window_returns:
                        mean_ret = np.mean(window_returns)
                        std_ret = np.std(window_returns)
                        sharpe = mean_ret / std_ret if std_ret > 0 else 0
                        rolling_sharpe.append(sharpe)

                if rolling_sharpe:
                    sharpe_cv = (
                        np.std(rolling_sharpe) / abs(np.mean(rolling_sharpe))
                        if np.mean(rolling_sharpe) != 0
                        else 0
                    )
                    risk_metrics["sharpe_consistency"] = max(0, 1 - sharpe_cv)

            # Overall risk consistency score
            risk_scores = [score for score in risk_metrics.values() if score is not None]
            risk_consistency_score = np.mean(risk_scores) if risk_scores else 0.5

            return {
                "score": risk_consistency_score,
                "risk_metrics": risk_metrics,
                "anomalies": [],  # Could add risk anomaly detection
            }

        except Exception as e:
            logger.error(f"Error analyzing risk consistency: {e}")
            return {"score": 0.5, "error": str(e)}

    async def _detect_emotional_trading(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect patterns indicative of emotional trading behavior.

        Emotional trading often manifests as:
        - Revenge trading after losses
        - Overconfidence after wins
        - Panic selling during drawdowns
        - Size escalation during winning/losing streaks
        """

        emotional_analysis = {
            "emotional_trading_detected": False,
            "emotional_score": 0.0,
            "emotional_patterns": [],
            "risk_level": "low",
        }

        try:
            if len(trade_history) < 20:
                return emotional_analysis

            # Analyze trading patterns for emotional indicators
            revenge_trading = self._detect_revenge_trading(trade_history)
            overconfidence = self._detect_overconfidence(trade_history)
            panic_selling = self._detect_panic_selling(trade_history)
            size_escalation = self._detect_size_escalation(trade_history)

            emotional_patterns = [revenge_trading, overconfidence, panic_selling, size_escalation]
            emotional_scores = [p["score"] for p in emotional_patterns if "score" in p]

            if emotional_scores:
                overall_emotional_score = np.mean(emotional_scores)

                emotional_analysis["emotional_score"] = overall_emotional_score
                emotional_analysis["emotional_patterns"] = emotional_patterns

                # Determine if emotional trading is significant
                threshold = self.pattern_params["emotional_trading_threshold"]
                if overall_emotional_score > threshold:
                    emotional_analysis["emotional_trading_detected"] = True

                    if overall_emotional_score > threshold * 2:
                        emotional_analysis["risk_level"] = "high"
                    elif overall_emotional_score > threshold * 1.5:
                        emotional_analysis["risk_level"] = "medium"
                    else:
                        emotional_analysis["risk_level"] = "moderate"

            return emotional_analysis

        except Exception as e:
            logger.error(f"Error detecting emotional trading: {e}")
            emotional_analysis["error"] = str(e)
            return emotional_analysis

    def _detect_revenge_trading(self, trade_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect revenge trading patterns (increasing size after losses)."""

        try:
            revenge_score = 0
            revenge_instances = 0

            for i in range(2, len(trade_history)):
                prev_trade = trade_history[i - 2]
                current_trade = trade_history[i - 1]
                next_trade = trade_history[i]

                # Check for loss followed by larger position
                prev_pnl = prev_trade.get("pnl_pct", 0)
                next_size = abs(next_trade.get("amount", 0))
                current_size = abs(current_trade.get("amount", 0))

                if (
                    prev_pnl < -0.01 and next_size > current_size * 1.5
                ):  # Loss followed by 50%+ size increase
                    revenge_instances += 1
                    revenge_score += min(
                        1.0, (next_size / current_size - 1) / 2
                    )  # Cap at 2x size increase

            if len(trade_history) > 5:
                revenge_ratio = revenge_instances / (len(trade_history) - 2)
                revenge_score = (
                    revenge_score / max(1, revenge_instances) if revenge_instances > 0 else 0
                )

                return {
                    "pattern": "revenge_trading",
                    "score": min(revenue_score, 1.0),
                    "instances": revenge_instances,
                    "ratio": revenge_ratio,
                    "detected": revenge_ratio > 0.1,
                }

            return {"pattern": "revenge_trading", "score": 0.0}

        except Exception:
            return {"pattern": "revenge_trading", "score": 0.0}

    def _detect_overconfidence(self, trade_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect overconfidence patterns (increasing risk after wins)."""

        try:
            overconfidence_score = 0
            overconfidence_instances = 0

            for i in range(1, len(trade_history)):
                prev_trade = trade_history[i - 1]
                current_trade = trade_history[i]

                # Check for win followed by increased risk
                prev_pnl = prev_trade.get("pnl_pct", 0)
                prev_risk = abs(prev_trade.get("stop_loss_pct", 0) or 0.02)  # Default 2%
                current_risk = abs(current_trade.get("stop_loss_pct", 0) or 0.02)

                if (
                    prev_pnl > 0.01 and current_risk > prev_risk * 1.5
                ):  # Win followed by 50%+ risk increase
                    overconfidence_instances += 1
                    overconfidence_score += min(1.0, (current_risk / prev_risk - 1) / 2)

            if len(trade_history) > 5:
                overconfidence_ratio = overconfidence_instances / (len(trade_history) - 1)
                overconfidence_score = (
                    overconfidence_score / max(1, overconfidence_instances)
                    if overconfidence_instances > 0
                    else 0
                )

                return {
                    "pattern": "overconfidence",
                    "score": min(overconfidence_score, 1.0),
                    "instances": overconfidence_instances,
                    "ratio": overconfidence_ratio,
                    "detected": overconfidence_ratio > 0.15,
                }

            return {"pattern": "overconfidence", "score": 0.0}

        except Exception:
            return {"pattern": "overconfidence", "score": 0.0}

    def _detect_panic_selling(self, trade_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect panic selling patterns during drawdowns."""

        try:
            panic_score = 0
            panic_instances = 0

            # Calculate running drawdown
            cumulative_pnl = 0
            peak = 0

            for i, trade in enumerate(trade_history):
                pnl = trade.get("pnl_pct", 0)
                cumulative_pnl += pnl

                if cumulative_pnl > peak:
                    peak = cumulative_pnl

                drawdown = peak - cumulative_pnl

                # Check for panic selling (closing position at worst time during drawdown)
                if drawdown > 0.05 and i < len(trade_history) - 1:  # 5% drawdown
                    next_trade = trade_history[i + 1]
                    next_pnl = next_trade.get("pnl_pct", 0)

                    # If next trade also loses money, might indicate panic
                    if (
                        next_pnl < -0.02 and drawdown > 0.08
                    ):  # Additional 2% loss during >8% drawdown
                        panic_instances += 1
                        panic_score += min(1.0, drawdown / 0.2)  # Scale drawdown to 0-1

            if len(trade_history) > 5:
                panic_ratio = panic_instances / len(trade_history)
                panic_score = panic_score / max(1, panic_instances) if panic_instances > 0 else 0

                return {
                    "pattern": "panic_selling",
                    "score": min(panic_score, 1.0),
                    "instances": panic_instances,
                    "ratio": panic_ratio,
                    "detected": panic_ratio > 0.05,
                }

            return {"pattern": "panic_selling", "score": 0.0}

        except Exception:
            return {"pattern": "panic_selling", "score": 0.0}

    def _detect_size_escalation(self, trade_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect position size escalation during streaks."""

        try:
            escalation_instances = 0

            current_streak = 0
            streak_direction = 0

            for i in range(1, len(trade_history)):
                prev_trade = trade_history[i - 1]
                current_trade = trade_history[i]

                prev_pnl = prev_trade.get("pnl_pct", 0)
                prev_size = abs(prev_trade.get("amount", 0))
                current_size = abs(current_trade.get("amount", 0))

                # Update streak
                if prev_pnl > 0:
                    if streak_direction <= 0:
                        current_streak = 1
                        streak_direction = 1
                    else:
                        current_streak += 1
                elif prev_pnl < 0:
                    if streak_direction >= 0:
                        current_streak = 1
                        streak_direction = -1
                    else:
                        current_streak += 1
                else:
                    current_streak = 0
                    streak_direction = 0

                # Check for size escalation during streaks
                if current_streak >= 2 and current_size > prev_size * 1.3:  # 30% size increase
                    escalation_instances += 1
                    escalation_score += min(
                        1.0, (current_size / prev_size - 1) / 2
                    )  # Scale escalation

            if len(trade_history) > 5:
                escalation_ratio = escalation_instances / len(trade_history)
                escalation_score = (
                    escalation_score / max(1, escalation_instances)
                    if escalation_instances > 0
                    else 0
                )

                return {
                    "pattern": "size_escalation",
                    "score": min(escalation_score, 1.0),
                    "instances": escalation_instances,
                    "ratio": escalation_ratio,
                    "detected": escalation_ratio > 0.08,
                }

            return {"pattern": "size_escalation", "score": 0.0}

        except Exception:
            return {"pattern": "size_escalation", "score": 0.0}

    async def _assess_risk_management_quality(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Assess the quality of risk management practices.

        Evaluates stop loss usage, position sizing, diversification, etc.
        """

        risk_assessment = {
            "risk_management_score": 0.0,
            "risk_components": {},
            "risk_rating": "unknown",
            "improvement_areas": [],
        }

        try:
            # Analyze stop loss effectiveness
            stop_loss_analysis = self._analyze_stop_loss_effectiveness(trade_history)
            risk_assessment["risk_components"]["stop_loss"] = stop_loss_analysis

            # Analyze position sizing consistency
            position_sizing = self._analyze_position_sizing_quality(trade_history)
            risk_assessment["risk_components"]["position_sizing"] = position_sizing

            # Analyze drawdown management
            drawdown_management = self._analyze_drawdown_management(trade_history)
            risk_assessment["risk_components"]["drawdown_management"] = drawdown_management

            # Analyze diversification
            diversification = self._analyze_portfolio_diversification(trade_history)
            risk_assessment["risk_components"]["diversification"] = diversification

            # Calculate overall risk management score
            component_scores = []
            for component_data in risk_assessment["risk_components"].values():
                if "score" in component_data:
                    component_scores.append(component_data["score"])

            if component_scores:
                overall_score = np.mean(component_scores)
                risk_assessment["risk_management_score"] = overall_score

                # Determine risk rating
                if overall_score >= 0.8:
                    risk_assessment["risk_rating"] = "excellent"
                elif overall_score >= 0.6:
                    risk_assessment["risk_rating"] = "good"
                elif overall_score >= 0.4:
                    risk_assessment["risk_rating"] = "adequate"
                else:
                    risk_assessment["risk_rating"] = "poor"

                # Identify improvement areas
                for component_name, component_data in risk_assessment["risk_components"].items():
                    if component_data.get("score", 1.0) < 0.6:
                        risk_assessment["improvement_areas"].append(component_name)

            return risk_assessment

        except Exception as e:
            logger.error(f"Error assessing risk management quality: {e}")
            risk_assessment["error"] = str(e)
            return risk_assessment

    def _analyze_stop_loss_effectiveness(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze how effectively stop losses are used."""

        try:
            trades_with_stops = [t for t in trade_history if t.get("stop_loss_pct") is not None]
            total_trades = len(trade_history)

            if not trades_with_stops:
                return {"score": 0.0, "stop_loss_usage": 0.0, "reason": "No stop losses detected"}

            stop_usage_rate = len(trades_with_stops) / total_trades

            # Analyze stop loss distances
            stop_distances = [abs(t["stop_loss_pct"]) for t in trades_with_stops]
            avg_stop_distance = np.mean(stop_distances)

            # Analyze stop execution
            stops_hit = sum(1 for t in trades_with_stops if t.get("stop_executed", False))
            stop_execution_rate = stops_hit / len(trades_with_stops) if trades_with_stops else 0

            # Score based on reasonable stop distances (2-15% typically good)
            if 0.02 <= avg_stop_distance <= 0.15:
                distance_score = 1.0
            elif avg_stop_distance < 0.02:
                distance_score = 0.5  # Too tight
            else:
                distance_score = 0.3  # Too wide

            # Overall stop loss score
            stop_score = (
                stop_usage_rate * 0.4
                + distance_score * 0.4
                + min(stop_execution_rate * 2, 1.0)
                * 0.2  # Some execution is good, too much may indicate poor placement
            )

            return {
                "score": stop_score,
                "stop_loss_usage": stop_usage_rate,
                "average_stop_distance": avg_stop_distance,
                "stop_execution_rate": stop_execution_rate,
            }

        except Exception as e:
            logger.error(f"Error analyzing stop loss effectiveness: {e}")
            return {"score": 0.5, "error": str(e)}

    def _analyze_position_sizing_quality(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze quality of position sizing decisions."""

        try:
            sizes = [abs(t.get("amount", 0)) for t in trade_history if t.get("amount", 0) != 0]

            if not sizes:
                return {"score": 0.5, "reason": "No position size data"}

            # Analyze size distribution
            size_mean = np.mean(sizes)
            size_std = np.std(sizes)
            size_cv = size_std / size_mean if size_mean > 0 else 0

            # Ideal CV is moderate (not too consistent, not too volatile)
            if 0.3 <= size_cv <= 0.8:
                consistency_score = 1.0
            elif size_cv < 0.3:
                consistency_score = 0.7  # Too consistent (may indicate lack of adaptability)
            else:
                consistency_score = 0.4  # Too volatile (may indicate emotional trading)

            # Analyze size vs outcome relationship
            size_outcome_correlation = self._calculate_size_outcome_correlation(trade_history)

            # Good sizing should not have strong correlation with outcomes (avoids size escalation)
            sizing_adaptability = 1 - abs(size_outcome_correlation)

            # Overall position sizing score
            sizing_score = consistency_score * 0.6 + sizing_adaptability * 0.4

            return {
                "score": sizing_score,
                "size_coefficient_of_variation": size_cv,
                "size_outcome_correlation": size_outcome_correlation,
                "sizing_consistency": consistency_score,
            }

        except Exception as e:
            logger.error(f"Error analyzing position sizing quality: {e}")
            return {"score": 0.5, "error": str(e)}

    def _calculate_size_outcome_correlation(self, trade_history: List[Dict[str, Any]]) -> float:
        """Calculate correlation between position size and trade outcomes."""

        try:
            size_outcome_pairs = []

            for trade in trade_history:
                size = abs(trade.get("amount", 0))
                pnl = trade.get("pnl_pct", 0)

                if size > 0:
                    # Normalize size (log scale to handle wide ranges)
                    log_size = np.log(size)
                    size_outcome_pairs.append((log_size, pnl))

            if len(size_outcome_pairs) >= 5:
                sizes, outcomes = zip(*size_outcome_pairs)
                correlation, _ = stats.pearsonr(sizes, outcomes)
                return correlation

            return 0.0

        except Exception:
            return 0.0

    def _analyze_drawdown_management(self, trade_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze how well drawdowns are managed."""

        try:
            # Calculate drawdown periods
            cumulative_pnl = []
            running_total = 0

            for trade in trade_history:
                pnl = trade.get("pnl_pct", 0)
                running_total += pnl
                cumulative_pnl.append(running_total)

            if not cumulative_pnl:
                return {"score": 0.5}

            # Calculate drawdowns
            peak = cumulative_pnl[0]
            drawdowns = []

            for pnl in cumulative_pnl:
                if pnl > peak:
                    peak = pnl
                drawdown = peak - pnl
                drawdowns.append(drawdown)

            max_drawdown = max(drawdowns) if drawdowns else 0

            # Analyze drawdown recovery
            drawdown_periods = self._identify_drawdown_periods(cumulative_pnl)

            recovery_times = []
            for period in drawdown_periods:
                if period["recovered"]:
                    recovery_time = period["end_idx"] - period["start_idx"]
                    recovery_times.append(recovery_time)

            avg_recovery_time = np.mean(recovery_times) if recovery_times else 0

            # Score drawdown management
            # Lower max drawdown and faster recovery = higher score
            max_dd_score = max(0, 1 - max_drawdown / 0.25)  # 25% max drawdown threshold

            if avg_recovery_time > 0:
                recovery_score = max(0, 1 - avg_recovery_time / 50)  # 50 trades recovery target
            else:
                recovery_score = 1.0  # No drawdowns to recover from

            drawdown_score = max_dd_score * 0.6 + recovery_score * 0.4

            return {
                "score": drawdown_score,
                "max_drawdown": max_drawdown,
                "average_recovery_time": avg_recovery_time,
                "drawdown_periods": len(drawdown_periods),
            }

        except Exception as e:
            logger.error(f"Error analyzing drawdown management: {e}")
            return {"score": 0.5, "error": str(e)}

    def _identify_drawdown_periods(self, cumulative_pnl: List[float]) -> List[Dict[str, Any]]:
        """Identify distinct drawdown periods."""

        try:
            peak = cumulative_pnl[0]
            drawdown_periods = []
            in_drawdown = False
            drawdown_start = 0

            for i, pnl in enumerate(cumulative_pnl):
                if pnl > peak:
                    # End of drawdown period
                    if in_drawdown:
                        recovered = pnl >= peak  # Check if recovered to previous peak
                        drawdown_periods.append(
                            {
                                "start_idx": drawdown_start,
                                "end_idx": i,
                                "depth": peak - min(cumulative_pnl[drawdown_start : i + 1]),
                                "recovered": recovered,
                            }
                        )
                        in_drawdown = False

                    peak = pnl

                elif not in_drawdown:
                    # Start of new drawdown
                    in_drawdown = True
                    drawdown_start = i

            return drawdown_periods

        except Exception:
            return []

    def _analyze_portfolio_diversification(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze portfolio diversification quality."""

        try:
            # For copy trading, diversification means variety in copied strategies
            # This is a simplified analysis - in practice would analyze correlation between copied wallets

            # Analyze market exposure diversity
            market_exposure = defaultdict(int)

            for trade in trade_history:
                market = trade.get("market_id", "unknown")
                market_exposure[market] += 1

            # Calculate Herfindahl-Hirschman Index (HHI) for market concentration
            total_trades = len(trade_history)
            hhi_score = 0

            for count in market_exposure.values():
                market_share = count / total_trades
                hhi_score += market_share**2

            # Lower HHI = more diversified (better)
            diversification_score = 1 - hhi_score

            # Analyze strategy diversity (if available)
            strategy_diversity = self._calculate_strategy_diversity(trade_history)

            # Overall diversification score
            overall_diversification = (diversification_score + strategy_diversity) / 2

            return {
                "score": overall_diversification,
                "market_concentration": hhi_score,
                "markets_traded": len(market_exposure),
                "strategy_diversity": strategy_diversity,
            }

        except Exception as e:
            logger.error(f"Error analyzing portfolio diversification: {e}")
            return {"score": 0.5, "error": str(e)}

    def _calculate_strategy_diversity(self, trade_history: List[Dict[str, Any]]) -> float:
        """Calculate diversity in trading strategies used."""

        try:
            # This is a placeholder - in a real implementation, you would categorize
            # trades by strategy type (momentum, mean-reversion, breakout, etc.)

            # Simplified: assume all trades are the same strategy for basic analysis
            # In practice, this would analyze actual strategy classifications

            return 0.5  # Neutral diversity score

        except Exception:
            return 0.5

    async def _analyze_capital_efficiency(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze capital efficiency and utilization."""

        try:
            if not trade_history:
                return {"score": 0.5}

            # Calculate basic efficiency metrics
            total_return = sum(t.get("pnl_pct", 0) for t in trade_history)
            total_trades = len(trade_history)

            # Return per trade
            return_per_trade = total_return / total_trades if total_trades > 0 else 0

            # Capital utilization (simplified - assumes consistent position sizes)
            sizes = [abs(t.get("amount", 0)) for t in trade_history]
            avg_size = np.mean(sizes) if sizes else 1

            # Efficiency score based on risk-adjusted returns
            returns = [t.get("pnl_pct", 0) for t in trade_history]
            if returns:
                sharpe_like_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
                efficiency_score = min(1.0, max(0, sharpe_like_ratio * 25 + 0.5))  # Scale to 0-1
            else:
                efficiency_score = 0.5

            return {
                "score": efficiency_score,
                "total_return": total_return,
                "return_per_trade": return_per_trade,
                "average_position_size": avg_size,
                "capital_utilization_rate": len(
                    [t for t in trade_history if t.get("pnl_pct", 0) != 0]
                )
                / total_trades,
            }

        except Exception as e:
            logger.error(f"Error analyzing capital efficiency: {e}")
            return {"score": 0.5, "error": str(e)}

    async def _assess_pattern_stability(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess stability of trading patterns over time."""

        try:
            if len(trade_history) < 20:
                return {"score": 0.5, "stability": "insufficient_data"}

            # Divide into quarters and compare patterns
            quarter_size = len(trade_history) // 4
            quarters = []

            for i in range(4):
                start_idx = i * quarter_size
                end_idx = start_idx + quarter_size if i < 3 else len(trade_history)
                quarters.append(trade_history[start_idx:end_idx])

            # Calculate key metrics for each quarter
            quarter_metrics = []

            for quarter in quarters:
                if quarter:
                    wins = sum(1 for t in quarter if t.get("pnl_pct", 0) > 0)
                    win_rate = wins / len(quarter)

                    returns = [t.get("pnl_pct", 0) for t in quarter]
                    avg_return = np.mean(returns) if returns else 0

                    sizes = [abs(t.get("amount", 0)) for t in quarter]
                    avg_size = np.mean(sizes) if sizes else 0

                    quarter_metrics.append(
                        {"win_rate": win_rate, "avg_return": avg_return, "avg_size": avg_size}
                    )

            # Calculate stability across quarters
            if len(quarter_metrics) >= 2:
                win_rates = [m["win_rate"] for m in quarter_metrics]
                avg_returns = [m["avg_return"] for m in quarter_metrics]
                avg_sizes = [m["avg_size"] for m in quarter_metrics]

                win_rate_stability = (
                    1 - np.std(win_rates) / np.mean(win_rates) if np.mean(win_rates) > 0 else 0
                )
                return_stability = (
                    1 - np.std(avg_returns) / abs(np.mean(avg_returns))
                    if np.mean(avg_returns) != 0
                    else 0
                )
                size_stability = (
                    1 - np.std(avg_sizes) / np.mean(avg_sizes) if np.mean(avg_sizes) > 0 else 0
                )

                overall_stability = (win_rate_stability + return_stability + size_stability) / 3

                stability_rating = (
                    "high"
                    if overall_stability >= 0.8
                    else "medium" if overall_stability >= 0.6 else "low"
                )

                return {
                    "score": overall_stability,
                    "stability": stability_rating,
                    "win_rate_stability": win_rate_stability,
                    "return_stability": return_stability,
                    "size_stability": size_stability,
                }

            return {"score": 0.5, "stability": "insufficient_quarters"}

        except Exception as e:
            logger.error(f"Error assessing pattern stability: {e}")
            return {"score": 0.5, "stability": "error", "error": str(e)}

    def _calculate_sustainability_score(self, analysis_results: Dict[str, Any]) -> float:
        """Calculate overall behavioral sustainability score."""

        try:
            # Weight different components
            weights = {
                "strategy_evolution": 0.25,  # Strategy stability
                "performance_decay": 0.20,  # Performance trends
                "behavioral_consistency": 0.20,  # Overall consistency
                "emotional_trading": 0.15,  # Emotional control
                "risk_management_quality": 0.15,  # Risk management
                "pattern_stability": 0.05,  # Pattern stability
            }

            sustainability_score = 0
            total_weight = 0

            for component, weight in weights.items():
                if component in analysis_results:
                    component_data = analysis_results[component]

                    # Extract score from component
                    if component == "strategy_evolution":
                        score = component_data.get("strategy_stability_score", 50) / 100
                    elif component == "performance_decay":
                        # Lower decay = higher score
                        decay_rate = component_data.get("decay_rate", 0)
                        score = max(0, 1 - decay_rate * 2)
                    elif component == "behavioral_consistency":
                        score = component_data.get("consistency_score", 0.5)
                    elif component == "emotional_trading":
                        # Lower emotional score = higher sustainability
                        emotional_score = component_data.get("emotional_score", 0)
                        score = max(0, 1 - emotional_score)
                    elif component == "risk_management_quality":
                        score = component_data.get("risk_management_score", 50) / 100
                    elif component == "pattern_stability":
                        score = component_data.get("score", 0.5)
                    else:
                        score = 0.5

                    sustainability_score += score * weight
                    total_weight += weight

            if total_weight > 0:
                sustainability_score /= total_weight

            return sustainability_score

        except Exception as e:
            logger.error(f"Error calculating sustainability score: {e}")
            return 0.5

    def _generate_early_warnings(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate early warning signals based on analysis results."""

        warnings = []

        try:
            # Strategy evolution warnings
            evolution = analysis_results.get("strategy_evolution", {})
            if evolution.get("evolution_detected", False):
                warnings.append(
                    {
                        "type": "strategy_evolution",
                        "severity": (
                            "high" if evolution.get("evolution_magnitude", 0) > 0.3 else "medium"
                        ),
                        "message": f"Strategy evolution detected with {evolution.get('evolution_magnitude', 0):.1%} magnitude",
                        "recommendation": "Monitor strategy changes closely",
                    }
                )

            # Performance decay warnings
            decay = analysis_results.get("performance_decay", {})
            if decay.get("decay_detected", False):
                severity = "high" if decay.get("decay_magnitude", 0) > 0.2 else "medium"
                warnings.append(
                    {
                        "type": "performance_decay",
                        "severity": severity,
                        "message": f"Performance decay detected: {decay.get('decay_magnitude', 0):.1%} deterioration",
                        "recommendation": "Consider reducing allocation or investigating causes",
                    }
                )

            # Emotional trading warnings
            emotional = analysis_results.get("emotional_trading", {})
            if emotional.get("emotional_trading_detected", False):
                warnings.append(
                    {
                        "type": "emotional_trading",
                        "severity": emotional.get("risk_level", "medium"),
                        "message": f"Emotional trading patterns detected (score: {emotional.get('emotional_score', 0):.2f})",
                        "recommendation": "Monitor for emotional decision making",
                    }
                )

            # Consistency warnings
            consistency = analysis_results.get("behavioral_consistency", {})
            if consistency.get("consistency_score", 1.0) < 0.4:
                warnings.append(
                    {
                        "type": "low_consistency",
                        "severity": "medium",
                        "message": f"Low behavioral consistency (score: {consistency.get('consistency_score', 0):.2f})",
                        "recommendation": "Strategy may be unpredictable",
                    }
                )

            # Risk management warnings
            risk_mgmt = analysis_results.get("risk_management_quality", {})
            if risk_mgmt.get("risk_management_score", 100) < 40:
                warnings.append(
                    {
                        "type": "poor_risk_management",
                        "severity": "high",
                        "message": f"Poor risk management (score: {risk_mgmt.get('risk_management_score', 0):.1f})",
                        "recommendation": "High risk - consider avoiding",
                    }
                )

        except Exception as e:
            logger.error(f"Error generating early warnings: {e}")

        return warnings

    def _store_behavioral_patterns(self, wallet_address: str, analysis_results: Dict[str, Any]):
        """Store behavioral pattern analysis for future comparison."""

        try:
            key_metrics = {
                "sustainability_score": analysis_results.get("sustainability_score", 0),
                "consistency_score": analysis_results.get("behavioral_consistency", {}).get(
                    "consistency_score", 0
                ),
                "evolution_magnitude": analysis_results.get("strategy_evolution", {}).get(
                    "evolution_magnitude", 0
                ),
                "decay_rate": analysis_results.get("performance_decay", {}).get("decay_rate", 0),
                "emotional_score": analysis_results.get("emotional_trading", {}).get(
                    "emotional_score", 0
                ),
                "risk_management_score": analysis_results.get("risk_management_quality", {}).get(
                    "risk_management_score", 0
                ),
            }

            self.wallet_patterns[wallet_address] = {
                "last_analysis": analysis_results["analysis_timestamp"],
                "key_metrics": key_metrics,
                "early_warnings": analysis_results.get("early_warnings", []),
            }

        except Exception as e:
            logger.error(f"Error storing behavioral patterns for {wallet_address}: {e}")

    def _create_insufficient_data_response(
        self, wallet_address: str, reason: str = "insufficient_data"
    ) -> Dict[str, Any]:
        """Create response for insufficient data scenarios."""

        return {
            "wallet_address": wallet_address,
            "error": f"Insufficient data for behavioral analysis: {reason}",
            "analysis_timestamp": datetime.now().isoformat(),
            "sustainability_score": None,
            "early_warnings": [
                {
                    "type": "insufficient_data",
                    "severity": "info",
                    "message": "Not enough trading history for comprehensive behavioral analysis",
                    "recommendation": "Continue monitoring wallet activity",
                }
            ],
        }


class RiskManagementQualityAssessor:
    """
    Specialized assessor for risk management quality in trading strategies.

    Evaluates how well wallets manage risk across different dimensions.
    """

    def __init__(self):
        self.risk_metrics = {
            "stop_loss_effectiveness": 0.25,
            "position_sizing_quality": 0.20,
            "drawdown_management": 0.20,
            "diversification_quality": 0.15,
            "risk_adjustment_quality": 0.20,
        }

    async def assess_risk_management_quality(
        self, trade_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess overall risk management quality."""

        try:
            assessment = {
                "overall_score": 0,
                "component_scores": {},
                "strengths": [],
                "weaknesses": [],
                "recommendations": [],
            }

            # This would implement detailed risk management assessment
            # For now, return a placeholder implementation

            assessment["overall_score"] = 0.6  # Placeholder
            assessment["component_scores"] = {
                "stop_loss_usage": 0.7,
                "position_sizing": 0.5,
                "drawdown_control": 0.8,
                "diversification": 0.4,
            }

            return assessment

        except Exception as e:
            logger.error(f"Error assessing risk management quality: {e}")
            return {"overall_score": 0.5, "error": str(e)}
