#!/usr/bin/env python3
"""
Web Dashboard for Polymarket Copy Bot

Provides web-based monitoring interface with:
- Real-time metrics visualization
- Historical performance charts
- Alert management interface
- Log viewing and search
- Configuration status display
"""

import json
import logging
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

# Flask and related imports
try:
    import pandas as pd
    import plotly.graph_objects as go
    from flask import Flask, Response, jsonify, render_template, request
    from flask_cors import CORS
    from plotly.subplots import make_subplots
except ImportError as e:
    print(f"Missing required packages: {e}")
    print("Install with: pip install flask flask-cors plotly pandas")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebDashboard:
    """Web-based monitoring dashboard"""

    def __init__(self, project_root: Optional[Path] = None, port: int = 8080):
        self.project_root = project_root or Path(__file__).parent.parent
        self.port = port
        self.app = Flask(
            __name__,
            template_folder=str(self.project_root / "templates"),
            static_folder=str(self.project_root / "static"),
        )
        CORS(self.app)

        # Data storage
        self.metrics_history = []
        self.alerts_history = []
        self.max_history = 1000

        # Setup routes
        self._setup_routes()

        # Start background data collection
        self.data_thread = threading.Thread(
            target=self._data_collection_loop, daemon=True
        )
        self.data_thread.start()

    def _setup_routes(self) -> None:
        """Setup Flask routes"""

        @self.app.route("/")
        def index():
            return render_template("dashboard.html")

        @self.app.route("/api/metrics/current")
        def get_current_metrics():
            """Get current metrics snapshot"""
            return jsonify(self._get_current_metrics())

        @self.app.route("/api/metrics/history")
        def get_metrics_history():
            """Get metrics history"""
            try:
                hours_str = request.args.get("hours", "1")
                hours = int(hours_str)
                # Validate reasonable bounds for hours
                if not (1 <= hours <= 168):  # 1 hour to 1 week
                    hours = 1
                return jsonify(self._get_metrics_history(hours))
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid hours parameter"}), 400

        @self.app.route("/api/alerts")
        def get_alerts():
            """Get alerts data"""
            active_only = request.args.get("active_only", "true").lower() == "true"
            return jsonify(self._get_alerts_data(active_only))

        @self.app.route("/api/logs")
        def get_logs():
            """Get log data"""
            try:
                lines_str = request.args.get("lines", "100")
                lines = int(lines_str)
                # Validate reasonable bounds for lines
                if not (10 <= lines <= 1000):
                    lines = 100

                level = request.args.get("level", "ALL")
                # Validate log level
                valid_levels = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                if level.upper() not in valid_levels:
                    level = "ALL"

                search = request.args.get("search", "")
                # Basic sanitization for search terms
                if len(search) > 100:  # Reasonable limit
                    search = search[:100]

                return jsonify(self._get_logs_data(lines, level, search))
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid parameters"}), 400

        @self.app.route("/api/charts/<chart_type>")
        def get_chart(chart_type: str):
            """Get chart data"""
            try:
                hours_str = request.args.get("hours", "24")
                hours = int(hours_str)
                # Validate reasonable bounds for hours
                if not (1 <= hours <= 168):  # 1 hour to 1 week
                    hours = 24

                # Validate chart type
                valid_chart_types = [
                    "performance",
                    "trades",
                    "api_usage",
                    "alerts_timeline",
                    "system_status",
                    "memory_usage",
                    "network_latency",
                ]
                if chart_type not in valid_chart_types:
                    return jsonify({"error": "Invalid chart type"}), 400

                chart_data = self._generate_chart(chart_type, hours)
                return jsonify(chart_data)
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid hours parameter"}), 400

        @self.app.route("/api/system/status")
        def get_system_status():
            """Get overall system status"""
            return jsonify(self._get_system_status())

        @self.app.route("/api/logs/stream")
        def stream_logs():
            """Stream logs in real-time"""
            return Response(self._stream_logs(), mimetype="text/plain")

    def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        try:
            # This would integrate with your actual monitoring systems
            return {
                "timestamp": datetime.now().isoformat(),
                "system": {
                    "cpu_percent": 45.2,
                    "memory_percent": 67.8,
                    "disk_percent": 72.3,
                    "load_average": 1.25,
                    "network_rx": 2.4,
                    "network_tx": 1.8,
                },
                "application": {
                    "total_trades": 1247,
                    "success_rate": 95.4,
                    "avg_latency": 2340,
                    "api_usage": 68,
                    "circuit_breaker": False,
                },
                "alerts": {"active_count": 1, "critical_count": 0, "warning_count": 1},
            }
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {"error": str(e)}

    def _get_metrics_history(self, hours: int) -> Dict[str, Any]:
        """Get metrics history for specified hours"""
        try:
            # Mock historical data
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)

            # Generate mock time series data
            timestamps = pd.date_range(start=start_time, end=end_time, freq="5min")

            data = {
                "timestamps": timestamps.strftime("%Y-%m-%d %H:%M:%S").tolist(),
                "cpu_percent": [45 + (i % 10) for i in range(len(timestamps))],
                "memory_percent": [65 + (i % 15) for i in range(len(timestamps))],
                "trade_success_rate": [
                    95 + (i % 5) - 2 for i in range(len(timestamps))
                ],
                "api_latency": [2000 + (i % 1000) for i in range(len(timestamps))],
            }

            return data
        except Exception as e:
            logger.error(f"Error getting metrics history: {e}")
            return {"error": str(e)}

    def _get_alerts_data(self, active_only: bool) -> Dict[str, Any]:
        """Get alerts data"""
        try:
            # Mock alerts data
            alerts = [
                {
                    "id": "alert_001",
                    "severity": "WARNING",
                    "category": "SYSTEM",
                    "title": "High Memory Usage",
                    "message": "Memory usage at 67.8%",
                    "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
                    "resolved": False,
                },
                {
                    "id": "alert_002",
                    "severity": "CRITICAL",
                    "category": "APPLICATION",
                    "title": "Circuit Breaker Activated",
                    "message": "Circuit breaker activated due to consecutive failures",
                    "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                    "resolved": True,
                },
            ]

            if active_only:
                alerts = [a for a in alerts if not a["resolved"]]

            return {
                "alerts": alerts,
                "total_count": len(alerts),
                "critical_count": len(
                    [a for a in alerts if a["severity"] == "CRITICAL"]
                ),
                "warning_count": len([a for a in alerts if a["severity"] == "WARNING"]),
            }
        except Exception as e:
            logger.error(f"Error getting alerts data: {e}")
            return {"error": str(e)}

    def _get_logs_data(self, lines: int, level: str, search: str) -> Dict[str, Any]:
        """Get logs data with filtering"""
        try:
            log_file = self.project_root / "logs" / "trade.log"
            if not log_file.exists():
                return {"logs": [], "total_lines": 0}

            with open(log_file, "r") as f:
                all_lines = f.readlines()

            # Apply filters
            filtered_lines = []
            for line in reversed(all_lines):  # Start from most recent
                line = line.strip()
                if not line:
                    continue

                # Level filter
                if level != "ALL":
                    if f"[{level}]" not in line.upper():
                        continue

                # Search filter
                if search and search.lower() not in line.lower():
                    continue

                filtered_lines.append(line)
                if len(filtered_lines) >= lines:
                    break

            return {
                "logs": list(
                    reversed(filtered_lines)
                ),  # Put back in chronological order
                "total_lines": len(all_lines),
                "filtered_lines": len(filtered_lines),
            }
        except Exception as e:
            logger.error(f"Error getting logs data: {e}")
            return {"error": str(e)}

    def _generate_chart(self, chart_type: str, hours: int) -> Dict[str, Any]:
        """Generate chart data for specified type"""
        try:
            if chart_type == "system_overview":
                return self._create_system_overview_chart(hours)
            elif chart_type == "trade_performance":
                return self._create_trade_performance_chart(hours)
            elif chart_type == "api_usage":
                return self._create_api_usage_chart(hours)
            elif chart_type == "alerts_timeline":
                return self._create_alerts_timeline_chart(hours)
            else:
                return {"error": f"Unknown chart type: {chart_type}"}
        except Exception as e:
            logger.error(f"Error generating chart {chart_type}: {e}")
            return {"error": str(e)}

    def _create_system_overview_chart(self, hours: int) -> Dict[str, Any]:
        """Create system overview chart"""
        # Mock data for demonstration
        timestamps = pd.date_range(end=datetime.now(), periods=20, freq="5min")

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=("CPU Usage", "Memory Usage", "Disk Usage", "Network I/O"),
            specs=[
                [{"secondary_y": False}, {"secondary_y": False}],
                [{"secondary_y": False}, {"secondary_y": True}],
            ],
        )

        # CPU Usage
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=[45 + (i % 10) for i in range(20)],
                name="CPU %",
                line=dict(color="red"),
            ),
            row=1,
            col=1,
        )

        # Memory Usage
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=[65 + (i % 15) for i in range(20)],
                name="Memory %",
                line=dict(color="blue"),
            ),
            row=1,
            col=2,
        )

        # Disk Usage
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=[70 + (i % 10) for i in range(20)],
                name="Disk %",
                line=dict(color="green"),
            ),
            row=2,
            col=1,
        )

        # Network I/O
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=[2.0 + (i % 1) for i in range(20)],
                name="RX MB/s",
                line=dict(color="orange"),
            ),
            row=2,
            col=2,
        )
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=[1.5 + (i % 0.5) for i in range(20)],
                name="TX MB/s",
                line=dict(color="purple"),
            ),
            row=2,
            col=2,
            secondary_y=False,
        )

        fig.update_layout(height=600, title_text="System Resource Overview")
        fig.update_xaxes(title_text="Time")
        fig.update_yaxes(title_text="Percentage", row=1, col=1)
        fig.update_yaxes(title_text="Percentage", row=1, col=2)
        fig.update_yaxes(title_text="Percentage", row=2, col=1)
        fig.update_yaxes(title_text="MB/s", row=2, col=2)

        return json.loads(fig.to_json())

    def _create_trade_performance_chart(self, hours: int) -> Dict[str, Any]:
        """Create trade performance chart"""
        timestamps = pd.date_range(end=datetime.now(), periods=20, freq="5min")

        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=("Trade Success Rate", "Trade Latency"),
            specs=[[{"secondary_y": False}], [{"secondary_y": False}]],
        )

        # Success Rate
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=[95 + (i % 5) - 2 for i in range(20)],
                name="Success Rate %",
                line=dict(color="green"),
            ),
            row=1,
            col=1,
        )

        # Add threshold line
        fig.add_hline(
            y=80,
            line_dash="dash",
            line_color="red",
            annotation_text="Warning Threshold",
            row=1,
            col=1,
        )

        # Latency
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=[2000 + (i % 1000) for i in range(20)],
                name="Latency (ms)",
                line=dict(color="orange"),
            ),
            row=2,
            col=1,
        )

        # Add threshold line
        fig.add_hline(
            y=5000,
            line_dash="dash",
            line_color="red",
            annotation_text="Warning Threshold",
            row=2,
            col=1,
        )

        fig.update_layout(height=600, title_text="Trade Performance Metrics")
        fig.update_xaxes(title_text="Time")
        fig.update_yaxes(title_text="Success Rate (%)", row=1, col=1)
        fig.update_yaxes(title_text="Latency (ms)", row=2, col=1)

        return json.loads(fig.to_json())

    def _create_api_usage_chart(self, hours: int) -> Dict[str, Any]:
        """Create API usage chart"""
        timestamps = pd.date_range(end=datetime.now(), periods=20, freq="5min")

        fig = go.Figure()

        # API Rate Limit Usage
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=[60 + (i % 20) for i in range(20)],
                name="Rate Limit Usage %",
                line=dict(color="blue"),
            )
        )

        # Add threshold lines
        fig.add_hline(
            y=75,
            line_dash="dash",
            line_color="orange",
            annotation_text="Warning Threshold",
        )
        fig.add_hline(
            y=90,
            line_dash="dash",
            line_color="red",
            annotation_text="Critical Threshold",
        )

        fig.update_layout(
            title="API Usage Monitoring",
            xaxis_title="Time",
            yaxis_title="Rate Limit Usage (%)",
            height=400,
        )

        return json.loads(fig.to_json())

    def _create_alerts_timeline_chart(self, hours: int) -> Dict[str, Any]:
        """Create alerts timeline chart"""
        # Mock alerts data
        alert_times = [
            datetime.now() - timedelta(hours=2),
            datetime.now() - timedelta(hours=1, minutes=30),
            datetime.now() - timedelta(minutes=30),
        ]

        alert_counts = [1, 0, 1]  # Critical, Warning, Info counts per time period

        fig = go.Figure()

        fig.add_trace(
            go.Bar(x=alert_times, y=alert_counts, name="Alerts", marker_color="red")
        )

        fig.update_layout(
            title="Alerts Timeline (Last 24 Hours)",
            xaxis_title="Time",
            yaxis_title="Alert Count",
            height=400,
        )

        return json.loads(fig.to_json())

    def _get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        try:
            current_metrics = self._get_current_metrics()
            alerts_data = self._get_alerts_data(True)

            # Determine overall status
            status = "healthy"
            if alerts_data.get("critical_count", 0) > 0:
                status = "critical"
            elif alerts_data.get("warning_count", 0) > 0:
                status = "warning"
            elif current_metrics.get("system", {}).get("cpu_percent", 0) > 80:
                status = "degraded"

            return {
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "uptime": "2 days, 4 hours",  # Would calculate from actual uptime
                "version": "1.0.0",
                "active_alerts": alerts_data.get("total_count", 0),
                "last_backup": (datetime.now() - timedelta(hours=6)).isoformat(),
                "services": {
                    "bot": "running",
                    "monitoring": "running",
                    "database": "healthy",
                },
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"error": str(e)}

    def _stream_logs(self):
        """Stream logs in real-time"""
        log_file = self.project_root / "logs" / "trade.log"

        def generate():
            if not log_file.exists():
                yield "data: Log file not found\n\n"
                return

            # Read existing lines
            with open(log_file, "r") as f:
                lines = f.readlines()
                for line in lines[-50:]:  # Last 50 lines
                    yield f"data: {line.strip()}\n\n"

            # Continue monitoring for new lines
            with open(log_file, "r") as f:
                f.seek(0, 2)  # Seek to end
                while True:
                    line = f.readline()
                    if line:
                        yield f"data: {line.strip()}\n\n"
                    else:
                        time.sleep(1)

        return generate()

    def _data_collection_loop(self) -> None:
        """Background data collection"""
        while True:
            try:
                # Collect metrics and alerts periodically
                metrics = self._get_current_metrics()
                self.metrics_history.append(metrics)

                # Maintain history size
                if len(self.metrics_history) > self.max_history:
                    self.metrics_history = self.metrics_history[-self.max_history :]

                time.sleep(30)  # Update every 30 seconds

            except Exception as e:
                logger.error(f"Data collection error: {e}")
                time.sleep(60)  # Wait longer on error

    def run(self, debug: bool = False) -> None:
        """Run the web dashboard"""
        logger.info(f"Starting web dashboard on port {self.port}")
        self.app.run(host="0.0.0.0", port=self.port, debug=debug, threaded=True)


def create_templates_and_static():
    """Create basic templates and static files"""
    project_root = Path(__file__).parent.parent

    # Create templates directory
    templates_dir = project_root / "templates"
    templates_dir.mkdir(exist_ok=True)

    # Create static directory
    static_dir = project_root / "static"
    static_dir.mkdir(exist_ok=True)
    (static_dir / "css").mkdir(exist_ok=True)
    (static_dir / "js").mkdir(exist_ok=True)

    # Create dashboard HTML template
    dashboard_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polymarket Copy Bot - Monitoring Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .status-healthy { color: #27ae60; }
        .status-warning { color: #f39c12; }
        .status-critical { color: #e74c3c; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .alerts-list { max-height: 300px; overflow-y: auto; }
        .alert-item { padding: 10px; margin: 5px 0; border-radius: 4px; }
        .alert-critical { background: #ffebee; border-left: 4px solid #e74c3c; }
        .alert-warning { background: #fff3e0; border-left: 4px solid #f39c12; }
        .logs-container { background: black; color: #00ff00; font-family: monospace; padding: 20px; border-radius: 8px; height: 400px; overflow-y: auto; }
        .tab-buttons { margin-bottom: 20px; }
        .tab-btn { padding: 10px 20px; margin: 0 5px; border: none; background: #3498db; color: white; border-radius: 4px; cursor: pointer; }
        .tab-btn.active { background: #2980b9; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Polymarket Copy Bot - Monitoring Dashboard</h1>
        <div id="system-status">Loading...</div>
    </div>

    <div class="tab-buttons">
        <button class="tab-btn active" onclick="showTab('overview')">Overview</button>
        <button class="tab-btn" onclick="showTab('system')">System</button>
        <button class="tab-btn" onclick="showTab('application')">Application</button>
        <button class="tab-btn" onclick="showTab('alerts')">Alerts</button>
        <button class="tab-btn" onclick="showTab('logs')">Logs</button>
    </div>

    <div id="overview" class="tab-content active">
        <div class="metrics-grid">
            <div class="metric-card">
                <h3>System Health</h3>
                <div id="system-health">Loading...</div>
            </div>
            <div class="metric-card">
                <h3>Trading Performance</h3>
                <div id="trading-performance">Loading...</div>
            </div>
            <div class="metric-card">
                <h3>API Status</h3>
                <div id="api-status">Loading...</div>
            </div>
            <div class="metric-card">
                <h3>Active Alerts</h3>
                <div id="alerts-count">Loading...</div>
            </div>
        </div>
    </div>

    <div id="system" class="tab-content">
        <div class="chart-container">
            <h3>System Resource Overview</h3>
            <div id="system-chart"></div>
        </div>
    </div>

    <div id="application" class="tab-content">
        <div class="chart-container">
            <h3>Trade Performance</h3>
            <div id="trade-chart"></div>
        </div>
        <div class="chart-container">
            <h3>API Usage</h3>
            <div id="api-chart"></div>
        </div>
    </div>

    <div id="alerts" class="tab-content">
        <div class="chart-container">
            <h3>Alerts Timeline</h3>
            <div id="alerts-chart"></div>
        </div>
        <div class="metric-card">
            <h3>Active Alerts</h3>
            <div class="alerts-list" id="alerts-list">Loading...</div>
        </div>
    </div>

    <div id="logs" class="tab-content">
        <div class="chart-container">
            <h3>Live Log Stream</h3>
            <div class="logs-container" id="logs-stream">Connecting...</div>
        </div>
    </div>

    <script>
        let currentMetrics = {};
        let updateInterval;

        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
        }

        async function updateDashboard() {
            try {
                const response = await fetch('/api/metrics/current');
                currentMetrics = await response.json();

                updateOverview();
                updateCharts();
            } catch (error) {
                console.error('Error updating dashboard:', error);
            }
        }

        function updateOverview() {
            // System Health
            const sys = currentMetrics.system || {};
            document.getElementById('system-health').innerHTML = `
                <div class="status-healthy">● CPU: ${sys.cpu_percent?.toFixed(1)}%</div>
                <div class="status-healthy">● Memory: ${sys.memory_percent?.toFixed(1)}%</div>
                <div class="status-healthy">● Disk: ${sys.disk_percent?.toFixed(1)}%</div>
                <div class="status-healthy">● Load: ${sys.load_average?.toFixed(2)}</div>
            `;

            // Trading Performance
            const app = currentMetrics.application || {};
            document.getElementById('trading-performance').innerHTML = `
                <div class="status-healthy">● Total Trades: ${app.total_trades || 0}</div>
                <div class="status-healthy">● Success Rate: ${app.success_rate?.toFixed(1)}%</div>
                <div class="status-healthy">● Avg Latency: ${app.avg_latency || 0}ms</div>
                <div class="status-healthy">● Circuit Breaker: ${app.circuit_breaker ? 'ACTIVE' : 'INACTIVE'}</div>
            `;

            // API Status
            document.getElementById('api-status').innerHTML = `
                <div class="status-healthy">● Rate Limit: ${app.api_usage || 0}%</div>
                <div class="status-healthy">● Status: Operational</div>
            `;

            // Alerts Count
            const alerts = currentMetrics.alerts || {};
            document.getElementById('alerts-count').innerHTML = `
                <div class="status-warning">● Active: ${alerts.active_count || 0}</div>
                <div class="status-critical">● Critical: ${alerts.critical_count || 0}</div>
                <div class="status-warning">● Warnings: ${alerts.warning_count || 0}</div>
            `;

            // Update system status
            document.getElementById('system-status').innerHTML = `Last update: ${new Date().toLocaleTimeString()}`;
        }

        async function updateCharts() {
            // System chart
            const systemData = await fetch('/api/charts/system_overview').then(r => r.json());
            if (systemData.data) {
                Plotly.newPlot('system-chart', systemData.data, systemData.layout);
            }

            // Trade chart
            const tradeData = await fetch('/api/charts/trade_performance').then(r => r.json());
            if (tradeData.data) {
                Plotly.newPlot('trade-chart', tradeData.data, tradeData.layout);
            }

            // API chart
            const apiData = await fetch('/api/charts/api_usage').then(r => r.json());
            if (apiData.data) {
                Plotly.newPlot('api-chart', apiData.data, apiData.layout);
            }

            // Alerts chart
            const alertsData = await fetch('/api/charts/alerts_timeline').then(r => r.json());
            if (alertsData.data) {
                Plotly.newPlot('alerts-chart', alertsData.data, alertsData.layout);
            }
        }

        async function updateAlerts() {
            try {
                const response = await fetch('/api/alerts');
                const alertsData = await response.json();

                const alertsList = document.getElementById('alerts-list');
                alertsList.innerHTML = '';

                alertsData.alerts.forEach(alert => {
                    const alertDiv = document.createElement('div');
                    alertDiv.className = `alert-item alert-${alert.severity.toLowerCase()}`;
                    alertDiv.innerHTML = `
                        <strong>${alert.severity}: ${alert.title}</strong><br>
                        <small>${alert.message}</small><br>
                        <small>${new Date(alert.timestamp).toLocaleString()}</small>
                    `;
                    alertsList.appendChild(alertDiv);
                });
            } catch (error) {
                console.error('Error updating alerts:', error);
            }
        }

        function connectLogStream() {
            const logsDiv = document.getElementById('logs-stream');

            const eventSource = new EventSource('/api/logs/stream');
            eventSource.onmessage = function(event) {
                const logLine = document.createElement('div');
                logLine.textContent = event.data;
                logsDiv.appendChild(logLine);
                logsDiv.scrollTop = logsDiv.scrollHeight;
            };

            eventSource.onerror = function(error) {
                logsDiv.innerHTML += '<div style="color: red;">Connection lost, reconnecting...</div>';
                setTimeout(() => {
                    logsDiv.innerHTML = 'Reconnecting...';
                    connectLogStream();
                }, 5000);
            };
        }

        // Initialize dashboard
        updateDashboard();
        updateAlerts();
        connectLogStream();

        // Update every 30 seconds
        updateInterval = setInterval(() => {
            updateDashboard();
            updateAlerts();
        }, 30000);

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (updateInterval) {
                clearInterval(updateInterval);
            }
        });
    </script>
</body>
</html>"""

    with open(templates_dir / "dashboard.html", "w") as f:
        f.write(dashboard_html)

    logger.info("Created dashboard template and static directories")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Web Dashboard for Polymarket Copy Bot"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port to run dashboard on"
    )
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument(
        "--create-templates", action="store_true", help="Create template files and exit"
    )

    args = parser.parse_args()

    if args.create_templates:
        create_templates_and_static()
        print("✅ Created dashboard templates and static files")
        return

    try:
        # Create templates if they don't exist
        templates_dir = Path(__file__).parent.parent / "templates"
        if not (templates_dir / "dashboard.html").exists():
            create_templates_and_static()

        dashboard = WebDashboard(port=args.port)
        dashboard.run(debug=args.debug)

    except KeyboardInterrupt:
        print("\nDashboard stopped by user")
    except Exception as e:
        print(f"Dashboard error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
