"""
Market Maker Analysis Dashboard
===============================

Specialized dashboard for market maker detection and analysis,
providing comprehensive visualization of wallet behavior patterns,
classification confidence, and trading strategy insights.

Features:
- Market maker probability heatmaps
- Classification confidence distributions
- Behavioral pattern analysis
- Risk assessment summaries
- Performance comparison charts
- Real-time classification alerts
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.settings import settings
from core.market_maker_detector import MarketMakerDetector


class MarketMakerDashboard:
    """
    Comprehensive dashboard for market maker analysis and visualization.

    Provides interactive charts, classification summaries, and behavioral
    insights for trading strategy optimization.
    """

    def __init__(self, market_maker_detector: MarketMakerDetector) -> None:
        self.detector = market_maker_detector
        self.dashboard_dir = Path("monitoring/dashboard")
        self.market_maker_dir = self.dashboard_dir / "market_maker"
        self.market_maker_dir.mkdir(parents=True, exist_ok=True)

        # Chart styling
        self.colors = {
            "market_maker": "#e74c3c",  # Red
            "directional_trader": "#27ae60",  # Green
            "high_frequency_trader": "#f39c12",  # Orange
            "arbitrage_trader": "#9b59b6",  # Purple
            "mixed_trader": "#3498db",  # Blue
            "low_activity": "#95a5a6",  # Gray
            "unknown": "#34495e",  # Dark gray
        }

    async def generate_comprehensive_dashboard(self) -> Dict[str, Any]:
        """
        Generate comprehensive market maker analysis dashboard.

        Returns:
            Dashboard data with charts and insights
        """

        dashboard_data = {
            "generated_at": datetime.now().isoformat(),
            "charts": {},
            "summary_stats": {},
            "insights": [],
            "alerts": [],
        }

        try:
            # Generate summary statistics
            dashboard_data[
                "summary_stats"
            ] = await self.detector.get_market_maker_summary()

            # Generate all charts
            dashboard_data["charts"] = await self._generate_all_charts()

            # Generate insights and alerts
            dashboard_data["insights"] = await self._generate_market_insights()
            dashboard_data["alerts"] = await self._generate_classification_alerts()

            # Save dashboard data
            self._save_dashboard_data(dashboard_data)

            # Generate HTML dashboard
            html_content = self._generate_html_dashboard(dashboard_data)
            html_file = self.market_maker_dir / "market_maker_dashboard.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"🎯 Market maker dashboard generated: {html_file}")

        except Exception as e:
            print(f"Error generating market maker dashboard: {e}")
            dashboard_data["error"] = str(e)

        return dashboard_data

    async def _generate_all_charts(self) -> Dict[str, Any]:
        """Generate all dashboard charts"""

        charts = {}

        try:
            # Get all classifications
            all_classifications = self.detector.storage.get_all_classifications()

            if not all_classifications:
                return charts

            # Convert to DataFrame for analysis
            df = pd.DataFrame.from_dict(all_classifications, orient="index")
            df["wallet_address"] = df.index

            # 1. Classification Distribution Pie Chart
            charts["classification_distribution"] = (
                self._create_classification_pie_chart(df)
            )

            # 2. Market Maker Probability Histogram
            charts["mm_probability_histogram"] = self._create_mm_probability_histogram(
                df
            )

            # 3. Confidence Score Distribution
            charts["confidence_distribution"] = (
                self._create_confidence_distribution_chart(df)
            )

            # 4. Trading Frequency vs Balance Score Scatter
            charts["frequency_balance_scatter"] = (
                self._create_frequency_balance_scatter(df)
            )

            # 5. Classification Confidence Heatmap
            charts["classification_heatmap"] = self._create_classification_heatmap(df)

            # 6. Market Maker Probability Trends (if historical data available)
            charts["probability_trends"] = await self._create_probability_trends_chart()

            # 7. Risk Assessment Summary
            charts["risk_assessment"] = self._create_risk_assessment_chart(df)

        except Exception as e:
            print(f"Error generating charts: {e}")

        return charts

    def _create_classification_pie_chart(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create classification distribution pie chart"""

        classification_counts = df["classification"].value_counts()

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=classification_counts.index,
                    values=classification_counts.values,
                    marker_colors=[
                        self.colors.get(cls, "#95a5a6")
                        for cls in classification_counts.index
                    ],
                    title="Wallet Classification Distribution",
                )
            ]
        )

        fig.update_layout(
            title="Market Maker Classification Distribution", font=dict(size=12)
        )

        return {
            "data": fig.to_json(),
            "summary": {
                "total_wallets": len(df),
                "market_makers": classification_counts.get("market_maker", 0),
                "mm_percentage": (
                    classification_counts.get("market_maker", 0) / len(df) * 100
                    if len(df) > 0
                    else 0
                ),
            },
        }

    def _create_mm_probability_histogram(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create market maker probability histogram"""

        fig = go.Figure()

        # Add histogram
        fig.add_trace(
            go.Histogram(
                x=df["market_maker_probability"],
                nbinsx=20,
                name="Market Maker Probability",
                marker_color="#3498db",
                opacity=0.7,
            )
        )

        # Add vertical lines for thresholds
        fig.add_vline(
            x=0.7,
            line_dash="dash",
            line_color="red",
            annotation_text="Market Maker Threshold (0.7)",
        )
        fig.add_vline(
            x=0.4,
            line_dash="dot",
            line_color="orange",
            annotation_text="Mixed Trader Threshold (0.4)",
        )

        fig.update_layout(
            title="Market Maker Probability Distribution",
            xaxis_title="Market Maker Probability",
            yaxis_title="Number of Wallets",
            bargap=0.1,
        )

        # Calculate statistics
        probs = df["market_maker_probability"]
        stats = {
            "mean": probs.mean(),
            "median": probs.median(),
            "std": probs.std(),
            "high_probability_count": (probs >= 0.7).sum(),
            "high_probability_percentage": (
                (probs >= 0.7).sum() / len(probs) * 100 if len(probs) > 0 else 0
            ),
        }

        return {"data": fig.to_json(), "statistics": stats}

    def _create_confidence_distribution_chart(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create confidence score distribution chart"""

        fig = go.Figure()

        # Create confidence distribution by classification
        for classification in df["classification"].unique():
            class_data = df[df["classification"] == classification]
            fig.add_trace(
                go.Box(
                    y=class_data["confidence_score"],
                    name=classification.replace("_", " ").title(),
                    marker_color=self.colors.get(classification, "#95a5a6"),
                    boxpoints="all",
                    jitter=0.3,
                    pointpos=-1.8,
                )
            )

        fig.update_layout(
            title="Confidence Score Distribution by Classification",
            yaxis_title="Confidence Score",
            xaxis_title="Classification Type",
            showlegend=False,
        )

        # Calculate confidence statistics
        confidence_stats = (
            df.groupby("classification")["confidence_score"]
            .agg(["mean", "std", "min", "max"])
            .round(3)
        )

        return {"data": fig.to_json(), "statistics": confidence_stats.to_dict()}

    def _create_frequency_balance_scatter(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create trading frequency vs balance score scatter plot"""

        fig = go.Figure()

        # Extract metrics from nested data
        plot_data = []
        for idx, row in df.iterrows():
            metrics = row.get("metrics_snapshot", {})
            temporal = metrics.get("temporal_metrics", {})
            directional = metrics.get("directional_metrics", {})

            plot_data.append(
                {
                    "wallet": idx[:10] + "...",  # Truncate for display
                    "frequency": temporal.get("trades_per_hour", 0),
                    "balance": directional.get("balance_score", 0),
                    "classification": row.get("classification", "unknown"),
                    "mm_probability": row.get("market_maker_probability", 0),
                }
            )

        if plot_data:
            plot_df = pd.DataFrame(plot_data)

            for classification in plot_df["classification"].unique():
                class_data = plot_df[plot_df["classification"] == classification]
                fig.add_trace(
                    go.Scatter(
                        x=class_data["frequency"],
                        y=class_data["balance"],
                        mode="markers",
                        name=classification.replace("_", " ").title(),
                        marker=dict(
                            size=8,
                            color=self.colors.get(classification, "#95a5a6"),
                            opacity=0.7,
                        ),
                        text=class_data["wallet"],
                        hovertemplate="<b>Wallet:</b> %{text}<br>"
                        + "<b>Trades/Hour:</b> %{x:.2f}<br>"
                        + "<b>Balance Score:</b> %{y:.3f}<br>"
                        + "<b>MM Probability:</b> "
                        + class_data["mm_probability"].astype(str)
                        + "<extra></extra>",
                    )
                )

        # Add reference lines
        fig.add_hline(
            y=0.7,
            line_dash="dash",
            line_color="red",
            opacity=0.5,
            annotation_text="High Balance Threshold",
        )
        fig.add_vline(
            x=5,
            line_dash="dash",
            line_color="orange",
            opacity=0.5,
            annotation_text="High Frequency Threshold",
        )

        fig.update_layout(
            title="Trading Frequency vs Balance Score",
            xaxis_title="Trades per Hour",
            yaxis_title="Buy/Sell Balance Score",
            xaxis=dict(
                range=[
                    0,
                    max(plot_df["frequency"].max() * 1.1, 10) if plot_data else 10,
                ]
            ),
        )

        return {
            "data": fig.to_json(),
            "insights": self._analyze_scatter_plot_insights(plot_data)
            if plot_data
            else [],
        }

    def _create_classification_heatmap(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create classification confidence heatmap"""

        # Create pivot table for heatmap
        heatmap_data = df.pivot_table(
            values="confidence_score",
            index="classification",
            aggfunc=["count", "mean", "std"],
        ).round(3)

        # Flatten column names
        heatmap_data.columns = [
            "_".join(col).strip() for col in heatmap_data.columns.values
        ]
        heatmap_data = heatmap_data.reset_index()

        fig = go.Figure(
            data=go.Heatmap(
                z=heatmap_data["mean_confidence_score"],
                x=heatmap_data["classification"],
                y=["Average Confidence"],
                colorscale="RdYlGn",
                text=heatmap_data["mean_confidence_score"].round(3),
                texttemplate="%{text}",
                textfont={"size": 12},
                hoverongaps=False,
            )
        )

        fig.update_layout(
            title="Classification Confidence Heatmap",
            xaxis_title="Classification Type",
            yaxis_title="",
            height=300,
        )

        return {"data": fig.to_json(), "statistics": heatmap_data.to_dict("records")}

    async def _create_probability_trends_chart(self) -> Dict[str, Any]:
        """Create market maker probability trends chart"""

        fig = go.Figure()

        # Get recent behavior history for top market makers
        all_classifications = self.detector.storage.get_all_classifications()
        market_makers = [
            wallet
            for wallet, data in all_classifications.items()
            if data.get("classification") == "market_maker"
        ][:5]  # Top 5 market makers

        for wallet in market_makers:
            history = self.detector.storage.get_wallet_behavior_history(
                wallet, limit=20
            )

            if len(history) >= 2:
                timestamps = [
                    datetime.fromisoformat(entry["timestamp"]) for entry in history
                ]
                probabilities = [entry["market_maker_probability"] for entry in history]

                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=probabilities,
                        mode="lines+markers",
                        name=f"{wallet[:8]}...",
                        line=dict(width=2),
                        marker=dict(size=6),
                    )
                )

        if fig.data:
            fig.update_layout(
                title="Market Maker Probability Trends (Top 5)",
                xaxis_title="Time",
                yaxis_title="Market Maker Probability",
                xaxis=dict(tickformat="%m/%d %H:%M"),
            )

        return {"data": fig.to_json()}

    def _create_risk_assessment_chart(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create risk assessment summary chart"""

        # Extract risk data from classifications
        risk_data = []
        for idx, row in df.iterrows():
            behavior = row.get("metrics_snapshot", {})
            risk = behavior.get("risk_metrics", {})

            risk_data.append(
                {
                    "classification": row.get("classification", "unknown"),
                    "price_impact": risk.get("avg_price_impact", 0),
                    "position_breaches": risk.get("position_limit_breaches", 0),
                    "net_position": abs(risk.get("net_position_drift", 0)),
                }
            )

        if risk_data:
            risk_df = pd.DataFrame(risk_data)

            fig = make_subplots(
                rows=1,
                cols=3,
                subplot_titles=(
                    "Average Price Impact",
                    "Position Limit Breaches",
                    "Net Position Drift",
                ),
            )

            # Price impact by classification
            impact_by_class = risk_df.groupby("classification")["price_impact"].mean()
            fig.add_trace(
                go.Bar(
                    x=impact_by_class.index,
                    y=impact_by_class.values,
                    name="Price Impact",
                    marker_color="lightblue",
                ),
                row=1,
                col=1,
            )

            # Position breaches by classification
            breaches_by_class = risk_df.groupby("classification")[
                "position_breaches"
            ].mean()
            fig.add_trace(
                go.Bar(
                    x=breaches_by_class.index,
                    y=breaches_by_class.values,
                    name="Position Breaches",
                    marker_color="lightcoral",
                ),
                row=1,
                col=2,
            )

            # Net position drift by classification
            drift_by_class = risk_df.groupby("classification")["net_position"].mean()
            fig.add_trace(
                go.Bar(
                    x=drift_by_class.index,
                    y=drift_by_class.values,
                    name="Position Drift",
                    marker_color="lightgreen",
                ),
                row=1,
                col=3,
            )

            fig.update_layout(
                title="Risk Assessment by Classification Type",
                showlegend=False,
                height=400,
            )

        return {"data": fig.to_json() if risk_data else None}

    def _analyze_scatter_plot_insights(
        self, plot_data: List[Dict[str, Any]]
    ) -> List[str]:
        """Analyze scatter plot data for insights"""

        insights = []
        df = pd.DataFrame(plot_data)

        if len(df) < 5:
            return insights

        # High frequency, high balance = likely market makers
        mm_candidates = df[
            (df["frequency"] >= 5)
            & (df["balance"] >= 0.7)
            & (df["mm_probability"] >= 0.7)
        ]

        if len(mm_candidates) > 0:
            insights.append(
                f"🎯 Identified {len(mm_candidates)} strong market maker candidates with high frequency and balanced trading"
            )

        # Low frequency, low balance = directional traders
        directional = df[(df["frequency"] < 1) & (df["balance"] < 0.5)]

        if len(directional) > 0:
            insights.append(
                f"📈 Found {len(directional)} directional traders with low frequency and imbalanced trading"
            )

        # High frequency, low balance = scalpers/arbitrageurs
        scalpers = df[(df["frequency"] >= 3) & (df["balance"] < 0.6)]

        if len(scalpers) > 0:
            insights.append(
                f"⚡ Detected {len(scalpers)} high-frequency traders with directional bias (potential scalpers)"
            )

        return insights

    async def _generate_market_insights(self) -> List[str]:
        """Generate comprehensive market insights"""

        insights = []

        try:
            summary = await self.detector.get_market_maker_summary()

            if summary.get("total_wallets_analyzed", 0) == 0:
                return ["No wallet analysis data available yet"]

            total_wallets = summary["total_wallets_analyzed"]
            mm_percentage = summary.get("market_maker_percentage", 0) * 100
            avg_confidence = summary.get("average_confidence", 0)

            insights.append(
                f"📊 Analyzed {total_wallets} wallets with {mm_percentage:.1f}% classified as market makers"
            )
            insights.append(
                f"🎯 Average classification confidence: {avg_confidence:.2f}"
            )

            # Classification distribution insights
            distribution = summary.get("classification_distribution", {})
            if distribution:
                top_classification = max(distribution.items(), key=lambda x: x[1])
                insights.append(
                    f"🏆 Most common classification: {top_classification[0].replace('_', ' ')} ({top_classification[1]} wallets)"
                )

            # Risk insights
            high_confidence_count = summary.get("high_confidence_classifications", 0)
            if high_confidence_count > 0:
                confidence_percentage = high_confidence_count / total_wallets * 100
                insights.append(
                    f"✅ {high_confidence_count} wallets ({confidence_percentage:.1f}%) have high confidence classifications"
                )

            # Market maker concentration analysis
            if mm_percentage > 20:
                insights.append(
                    "⚠️ High market maker concentration detected - potential market manipulation concerns"
                )
            elif mm_percentage < 5:
                insights.append(
                    "📉 Low market maker activity - limited liquidity provision"
                )

        except Exception as e:
            insights.append(f"Error generating insights: {e}")

        return insights

    async def _generate_classification_alerts(self) -> List[Dict[str, Any]]:
        """Generate classification change alerts"""

        alerts = []

        try:
            changes = await self.detector.detect_classification_changes()

            for change in changes:
                alert_level = "warning"
                if change["mm_probability_change"] > 0.3:
                    alert_level = "critical"
                elif change["mm_probability_change"] > 0.1:
                    alert_level = "info"

                alerts.append(
                    {
                        "level": alert_level,
                        "title": f"Classification Change: {change['wallet_address'][:10]}...",
                        "message": f"Changed from '{change['previous_classification']}' to '{change['current_classification']}'",
                        "details": {
                            "mm_probability_change": change["mm_probability_change"],
                            "hours_since_change": change["hours_since_change"],
                            "confidence_current": change["confidence_current"],
                        },
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        except Exception as e:
            alerts.append(
                {
                    "level": "error",
                    "title": "Alert Generation Error",
                    "message": f"Could not generate classification alerts: {e}",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        return alerts

    def _generate_html_dashboard(self, dashboard_data: Dict[str, Any]) -> str:
        """Generate HTML dashboard with embedded charts"""

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Market Maker Analysis Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }}
        .section {{ background: white; padding: 25px; margin-bottom: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.07); }}
        .chart-container {{ margin: 20px 0; min-height: 400px; }}
        .metric-card {{ display: inline-block; background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 8px; border-left: 4px solid #007bff; min-width: 200px; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        .metric-label {{ font-size: 0.9em; color: #6c757d; text-transform: uppercase; }}
        .insights-list {{ background: #e8f4fd; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff; }}
        .alert {{ padding: 15px; margin: 10px 0; border-radius: 6px; border-left: 4px solid; }}
        .alert-critical {{ background: #f8d7da; border-left-color: #dc3545; }}
        .alert-warning {{ background: #fff3cd; border-left-color: #ffc107; }}
        .alert-info {{ background: #d1ecf1; border-left-color: #17a2b8; }}
        .alert-error {{ background: #f5c6cb; border-left-color: #dc3545; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
        .summary-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }}
        @media (max-width: 768px) {{ .grid, .summary-stats {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Market Maker Analysis Dashboard</h1>
            <p>Advanced behavioral analysis of Polymarket trading patterns</p>
            <p style="opacity: 0.9; font-size: 0.9em;">Generated: {dashboard_data["generated_at"][:19].replace("T", " ")}</p>
        </div>

        <!-- Summary Statistics -->
        <div class="section">
            <h2>📊 Summary Statistics</h2>
            <div class="summary-stats">
"""

        summary = dashboard_data.get("summary_stats", {})

        # Key metrics cards
        metrics = [
            ("Total Wallets", summary.get("total_wallets_analyzed", 0), "wallets"),
            (
                "Market Makers",
                f"{summary.get('market_maker_percentage', 0) * 100:.1f}%",
                "of total",
            ),
            (
                "Avg MM Probability",
                f"{summary.get('average_mm_probability', 0):.2f}",
                "score",
            ),
            (
                "High Confidence",
                summary.get("high_confidence_classifications", 0),
                "wallets",
            ),
        ]

        for label, value, unit in metrics:
            html += f"""
                <div class="metric-card">
                    <div class="metric-value">{value}</div>
                    <div class="metric-label">{label}<br><small>{unit}</small></div>
                </div>
            """

        html += """
            </div>
        </div>

        <!-- Charts Grid -->
        <div class="section">
            <h2>📈 Analysis Charts</h2>
            <div class="grid">
        """

        # Add charts
        charts = dashboard_data.get("charts", {})

        chart_configs = [
            ("classification_distribution", "Classification Distribution", "pie"),
            ("mm_probability_histogram", "Market Maker Probability", "histogram"),
            ("confidence_distribution", "Confidence Distribution", "box"),
            ("frequency_balance_scatter", "Trading Patterns", "scatter"),
            ("classification_heatmap", "Confidence Heatmap", "heatmap"),
            ("probability_trends", "Probability Trends", "line"),
            ("risk_assessment", "Risk Assessment", "bar"),
        ]

        for chart_key, title, chart_type in chart_configs:
            if chart_key in charts and charts[chart_key].get("data"):
                chart_data = charts[chart_key]["data"]
                html += f"""
                <div class="chart-container">
                    <h3>{title}</h3>
                    <div id="{chart_key}" style="width:100%; height:400px;"></div>
                    <script>
                        var data_{chart_key} = {chart_data};
                        Plotly.newPlot('{chart_key}', data_{chart_key}.data, data_{chart_key}.layout || {{}});
                    </script>
                </div>
                """

        html += """
            </div>
        </div>

        <!-- Insights and Alerts -->
        <div class="section">
            <h2>💡 Insights & Alerts</h2>
            <div class="insights-list">
                <h3>Key Insights</h3>
                <ul>
        """

        for insight in dashboard_data.get("insights", []):
            html += f"<li>{insight}</li>"

        html += """
                </ul>
            </div>

            <h3 style="margin-top: 30px;">🚨 Classification Alerts</h3>
        """

        for alert in dashboard_data.get("alerts", []):
            alert_class = f"alert-{alert['level']}"
            html += f"""
            <div class="{alert_class} alert">
                <strong>{alert["title"]}</strong><br>
                {alert["message"]}
            </div>
            """

        html += """
        </div>
    </div>

    <script>
        // Auto-refresh functionality (optional)
        function refreshDashboard() {
            if (confirm('Refresh dashboard with latest data?')) {
                location.reload();
            }
        }

        // Add refresh button to header
        document.querySelector('.header').innerHTML += '<button onclick="refreshDashboard()" style="background: rgba(255,255,255,0.2); color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-top: 10px;">🔄 Refresh</button>';
    </script>
</body>
</html>
        """

        return html

    def _save_dashboard_data(self, dashboard_data: Dict[str, Any]):
        """Save dashboard data to JSON file"""

        try:
            dashboard_file = self.market_maker_dir / "dashboard_data.json"
            with open(dashboard_file, "w", encoding="utf-8") as f:
                # Convert datetime objects to strings for JSON serialization
                serializable_data = json.loads(json.dumps(dashboard_data, default=str))
                json.dump(serializable_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"Error saving dashboard data: {e}")


async def generate_market_maker_dashboard(detector: MarketMakerDetector):
    """Generate market maker analysis dashboard"""
    dashboard = MarketMakerDashboard(detector)
    return await dashboard.generate_comprehensive_dashboard()


if __name__ == "__main__":
    import asyncio

    async def main():
        detector = MarketMakerDetector(settings)
        dashboard = MarketMakerDashboard(detector)
        await dashboard.generate_comprehensive_dashboard()

    asyncio.run(main())
