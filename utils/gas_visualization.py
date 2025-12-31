"""
Gas Optimization Visualization for Performance Reports

Creates visualizations for:
- Gas price trends over time
- Cost savings comparison
- MEV risk analysis
- Execution timing analysis
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import matplotlib.pyplot as plt
    import numpy as np

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("Matplotlib not available - gas visualizations will be disabled")


class GasVisualization:
    """
    Creates visualizations for gas optimization performance.

    Generates charts showing:
    - Gas price trends and predictions
    - Cost savings over time
    - MEV risk distribution
    - Execution timing analysis
    """

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        """
        Initialize gas visualization.

        Args:
            output_dir: Directory to save visualization files
        """
        self.output_dir = output_dir or Path("data/gas_visualizations")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib not available - visualizations disabled")

    def create_gas_price_trend_chart(
        self,
        gas_history: List[float],
        timestamps: List[float],
        predictions: Optional[List[Dict[str, Any]]] = None,
        save_path: Optional[Path] = None,
    ) -> Optional[Figure]:
        """
        Create gas price trend chart with predictions.

        Args:
            gas_history: Historical gas prices
            timestamps: Unix timestamps for each price
            predictions: Optional prediction data
            save_path: Path to save chart

        Returns:
            Matplotlib figure or None if matplotlib unavailable
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            fig, ax = plt.subplots(figsize=(12, 6))

            # Convert timestamps to datetime
            times = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts in timestamps]

            # Plot historical data
            ax.plot(
                times,
                gas_history,
                label="Historical Gas Price",
                color="blue",
                linewidth=2,
            )

            # Plot predictions if available
            if predictions:
                pred_times = [
                    datetime.fromtimestamp(p["timestamp"], tz=timezone.utc)
                    for p in predictions
                ]
                pred_prices = [p["predicted_price_gwei"] for p in predictions]
                pred_lower = [
                    p.get("lower_bound", p["predicted_price_gwei"]) for p in predictions
                ]
                pred_upper = [
                    p.get("upper_bound", p["predicted_price_gwei"]) for p in predictions
                ]

                ax.plot(
                    pred_times,
                    pred_prices,
                    label="Predicted Gas Price",
                    color="green",
                    linestyle="--",
                )
                ax.fill_between(
                    pred_times,
                    pred_lower,
                    pred_upper,
                    alpha=0.2,
                    color="green",
                    label="Prediction Range",
                )

            # Add spike detection markers
            if len(gas_history) > 10:
                avg_gas = (
                    np.mean(gas_history[-50:])
                    if len(gas_history) >= 50
                    else np.mean(gas_history)
                )
                spikes = [
                    (times[i], gas_history[i])
                    for i in range(len(gas_history))
                    if gas_history[i] > avg_gas * 2.0
                ]
                if spikes:
                    spike_times, spike_prices = zip(*spikes)
                    ax.scatter(
                        spike_times,
                        spike_prices,
                        color="red",
                        marker="^",
                        s=100,
                        label="Gas Spikes",
                        zorder=5,
                    )

            ax.set_xlabel("Time (UTC)")
            ax.set_ylabel("Gas Price (gwei)")
            ax.set_title("Gas Price Trends and Predictions")
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.xticks(rotation=45)
            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=150, bbox_inches="tight")
                logger.info(f"💾 Saved gas trend chart to {save_path}")

            return fig

        except Exception as e:
            logger.exception(f"❌ Error creating gas trend chart: {e}")
            return None

    def create_cost_savings_chart(
        self,
        savings_data: List[Dict[str, Any]],
        save_path: Optional[Path] = None,
    ) -> Optional[Figure]:
        """
        Create cost savings comparison chart.

        Args:
            savings_data: List of savings records with timestamps and amounts
            save_path: Path to save chart

        Returns:
            Matplotlib figure or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

            # Extract data
            timestamps = [s["timestamp"] for s in savings_data]
            times = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts in timestamps]
            savings_usd = [s["savings_usd"] for s in savings_data]
            cumulative_savings = np.cumsum(savings_usd)

            # Plot individual savings
            ax1.bar(times, savings_usd, width=0.8, color="green", alpha=0.7)
            ax1.set_xlabel("Time (UTC)")
            ax1.set_ylabel("Savings per Trade ($)")
            ax1.set_title("Gas Cost Savings per Trade")
            ax1.grid(True, alpha=0.3)
            ax1.axhline(y=0, color="black", linestyle="-", linewidth=0.5)

            # Plot cumulative savings
            ax2.plot(times, cumulative_savings, color="blue", linewidth=2, marker="o")
            ax2.fill_between(times, cumulative_savings, alpha=0.3, color="blue")
            ax2.set_xlabel("Time (UTC)")
            ax2.set_ylabel("Cumulative Savings ($)")
            ax2.set_title(f"Total Gas Cost Savings: ${cumulative_savings[-1]:.2f}")
            ax2.grid(True, alpha=0.3)

            plt.xticks(rotation=45)
            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=150, bbox_inches="tight")
                logger.info(f"💾 Saved cost savings chart to {save_path}")

            return fig

        except Exception as e:
            logger.exception(f"❌ Error creating cost savings chart: {e}")
            return None

    def create_mev_risk_chart(
        self,
        mev_data: List[Dict[str, Any]],
        save_path: Optional[Path] = None,
    ) -> Optional[Figure]:
        """
        Create MEV risk distribution chart.

        Args:
            mev_data: List of MEV risk scores
            save_path: Path to save chart

        Returns:
            Matplotlib figure or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

            risk_scores = [d["risk_score"] for d in mev_data]

            # Histogram of risk scores
            ax1.hist(risk_scores, bins=20, color="orange", alpha=0.7, edgecolor="black")
            ax1.set_xlabel("MEV Risk Score")
            ax1.set_ylabel("Frequency")
            ax1.set_title("MEV Risk Score Distribution")
            ax1.axvline(x=40, color="green", linestyle="--", label="Low Risk Threshold")
            ax1.axvline(x=70, color="red", linestyle="--", label="High Risk Threshold")
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Risk categories pie chart
            low_risk = sum(1 for r in risk_scores if r < 40)
            medium_risk = sum(1 for r in risk_scores if 40 <= r < 70)
            high_risk = sum(1 for r in risk_scores if r >= 70)

            sizes = [low_risk, medium_risk, high_risk]
            labels = ["Low Risk", "Medium Risk", "High Risk"]
            colors = ["green", "yellow", "red"]
            explode = (0.05, 0.05, 0.1) if high_risk > 0 else (0.05, 0.05, 0)

            ax2.pie(
                sizes,
                labels=labels,
                colors=colors,
                autopct="%1.1f%%",
                explode=explode,
                startangle=90,
            )
            ax2.set_title("MEV Risk Categories")

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=150, bbox_inches="tight")
                logger.info(f"💾 Saved MEV risk chart to {save_path}")

            return fig

        except Exception as e:
            logger.exception(f"❌ Error creating MEV risk chart: {e}")
            return None

    def create_execution_timing_chart(
        self,
        timing_analysis: Dict[str, Any],
        save_path: Optional[Path] = None,
    ) -> Optional[Figure]:
        """
        Create execution timing cost-benefit chart.

        Args:
            timing_analysis: Cost-benefit analysis data
            save_path: Path to save chart

        Returns:
            Matplotlib figure or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            fig, ax = plt.subplots(figsize=(12, 6))

            timing_data = timing_analysis.get("timing_analysis", [])
            if not timing_data:
                return None

            minutes = [t["minutes"] for t in timing_data]
            costs = [t["gas_cost_usd"] for t in timing_data]
            confidences = [t["confidence"] for t in timing_data]

            # Plot cost vs wait time
            ax.plot(
                minutes, costs, marker="o", linewidth=2, markersize=8, label="Gas Cost"
            )
            ax.fill_between(minutes, costs, alpha=0.3)

            # Highlight optimal timing
            optimal_idx = min(range(len(costs)), key=lambda i: costs[i])
            ax.scatter(
                minutes[optimal_idx],
                costs[optimal_idx],
                color="green",
                s=200,
                marker="*",
                label="Optimal Timing",
                zorder=5,
            )

            # Add confidence bars
            for i, (m, c, conf) in enumerate(zip(minutes, costs, confidences)):
                height = costs[0] * 0.05  # 5% of max cost
                ax.bar(
                    m, height, bottom=c - height / 2, alpha=conf, color="blue", width=2
                )

            ax.set_xlabel("Wait Time (minutes)")
            ax.set_ylabel("Gas Cost ($)")
            ax.set_title(
                f"Execution Timing Analysis - "
                f"Savings: ${timing_analysis.get('savings_usd', 0):.2f} "
                f"({timing_analysis.get('savings_pct', 0):.1f}%)"
            )
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=150, bbox_inches="tight")
                logger.info(f"💾 Saved execution timing chart to {save_path}")

            return fig

        except Exception as e:
            logger.exception(f"❌ Error creating execution timing chart: {e}")
            return None

    def create_performance_summary(
        self,
        metrics: Dict[str, Any],
        save_path: Optional[Path] = None,
    ) -> Optional[Figure]:
        """
        Create comprehensive performance summary visualization.

        Args:
            metrics: Gas optimizer metrics
            save_path: Path to save chart

        Returns:
            Matplotlib figure or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))

            # 1. Optimization mode distribution
            mode = metrics.get("mode", "balanced")
            modes = ["Conservative", "Balanced", "Aggressive"]
            mode_values = [1 if m.lower() == mode else 0 for m in modes]
            axes[0, 0].bar(modes, mode_values, color=["blue", "green", "red"])
            axes[0, 0].set_title("Optimization Mode")
            axes[0, 0].set_ylabel("Active")

            # 2. Gas savings
            total_savings = metrics.get("gas_savings_usd", 0)
            total_optimizations = metrics.get("total_optimizations", 0)
            avg_savings = (
                total_savings / total_optimizations if total_optimizations > 0 else 0
            )

            axes[0, 1].bar(
                ["Total Savings", "Avg per Trade"],
                [total_savings, avg_savings],
                color="green",
            )
            axes[0, 1].set_title("Gas Cost Savings")
            axes[0, 1].set_ylabel("USD")

            # 3. Spike detections
            spike_detections = metrics.get("spike_detections", 0)
            deferred = metrics.get("deferred_trades", 0)
            batched = metrics.get("batched_trades", 0)

            axes[1, 0].bar(
                ["Spikes Detected", "Deferred", "Batched"],
                [spike_detections, deferred, batched],
                color=["red", "yellow", "blue"],
            )
            axes[1, 0].set_title("Gas Spike Handling")
            axes[1, 0].set_ylabel("Count")

            # 4. Current gas price and volatility
            current_gas = metrics.get("current_gas_price_gwei", 0)
            volatility = metrics.get("volatility", 0)

            axes[1, 1].barh(
                ["Current Gas", "Volatility"],
                [current_gas, volatility * 10],  # Scale volatility for visibility
                color=["blue", "orange"],
            )
            axes[1, 1].set_title("Current Gas Metrics")
            axes[1, 1].set_xlabel("Value")

            plt.suptitle("Gas Optimization Performance Summary", fontsize=16, y=0.995)
            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=150, bbox_inches="tight")
                logger.info(f"💾 Saved performance summary to {save_path}")

            return fig

        except Exception as e:
            logger.exception(f"❌ Error creating performance summary: {e}")
            return None
