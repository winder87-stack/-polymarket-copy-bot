#!/usr/bin/env python3
"""
Terminal Dashboard for Polymarket Copy Bot

Provides real-time monitoring dashboard using curses including:
- System resource visualization
- Application metrics display
- Alert status and history
- Log streaming interface
- Interactive controls
"""

import curses
import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Setup logging
logging.basicConfig(level=logging.WARNING)  # Reduce log noise for dashboard
logger = logging.getLogger(__name__)


class DashboardData:
    """Data container for dashboard information"""

    def __init__(self):
        self.system_metrics = {}
        self.application_metrics = {}
        self.active_alerts = []
        self.recent_logs = []
        self.last_update = datetime.now()

    def update_system_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update system metrics"""
        self.system_metrics = metrics
        self.last_update = datetime.now()

    def update_application_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update application metrics"""
        self.application_metrics = metrics
        self.last_update = datetime.now()

    def update_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        """Update active alerts"""
        self.active_alerts = alerts

    def update_logs(self, logs: List[str]) -> None:
        """Update recent logs"""
        self.recent_logs = logs[-20:]  # Keep last 20 log lines


class TerminalDashboard:
    """Terminal-based monitoring dashboard"""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.data = DashboardData()
        self.running = True
        self.current_view = "overview"  # overview, system, application, alerts, logs
        self.update_interval = 2.0

        # Initialize curses
        curses.start_color()
        curses.use_default_colors()
        curses.curs_set(0)  # Hide cursor

        # Define color pairs
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # Success
        curses.init_pair(2, curses.COLOR_RED, -1)  # Critical
        curses.init_pair(3, curses.COLOR_YELLOW, -1)  # Warning
        curses.init_pair(4, curses.COLOR_BLUE, -1)  # Info
        curses.init_pair(5, curses.COLOR_CYAN, -1)  # Header
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)  # Accent

        # Color constants
        self.COLOR_SUCCESS = curses.color_pair(1)
        self.COLOR_CRITICAL = curses.color_pair(2)
        self.COLOR_WARNING = curses.color_pair(3)
        self.COLOR_INFO = curses.color_pair(4)
        self.COLOR_HEADER = curses.color_pair(5)
        self.COLOR_ACCENT = curses.color_pair(6)

    def run(self) -> None:
        """Main dashboard loop"""
        # Start data collection thread
        data_thread = threading.Thread(target=self._data_collection_loop, daemon=True)
        data_thread.start()

        try:
            while self.running:
                self._draw_dashboard()
                self._handle_input()

        except KeyboardInterrupt:
            pass
        finally:
            self.running = False

    def _data_collection_loop(self) -> None:
        """Background data collection"""
        while self.running:
            try:
                # Collect system metrics
                system_metrics = self._get_system_metrics()
                self.data.update_system_metrics(system_metrics)

                # Collect application metrics
                app_metrics = self._get_application_metrics()
                self.data.update_application_metrics(app_metrics)

                # Collect alerts
                alerts = self._get_active_alerts()
                self.data.update_alerts(alerts)

                # Collect recent logs
                logs = self._get_recent_logs()
                self.data.update_logs(logs)

            except Exception as e:
                logger.error(f"Data collection error: {e}")

            time.sleep(self.update_interval)

    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            # This would normally call the system monitor
            # For demo, return mock data
            return {
                "cpu_percent": 45.2,
                "cpu_load_1m": 1.25,
                "memory_percent": 67.8,
                "memory_used_gb": 5.4,
                "disk_usage_percent": 72.3,
                "disk_used_gb": 145.8,
                "network_rx_mb": 2.4,
                "network_tx_mb": 1.8,
                "file_descriptors_used": 245,
                "file_descriptors_limit": 1024,
                "process_count": 184,
                "uptime_seconds": 345600,
            }
        except Exception:
            return {}

    def _get_application_metrics(self) -> Dict[str, Any]:
        """Get current application metrics"""
        try:
            # This would normally call the application monitor
            return {
                "total_trades": 1247,
                "successful_trades": 1189,
                "success_rate_percent": 95.4,
                "average_latency_ms": 2340,
                "api_requests_total": 5672,
                "api_rate_limit_usage": 68,
                "circuit_breaker_active": False,
                "wallet_balance_matic": 1.234,
            }
        except Exception:
            return {}

    def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts"""
        try:
            # This would normally call the alerting system
            return [
                {
                    "severity": "WARNING",
                    "title": "High Memory Usage",
                    "message": "Memory usage at 67.8%",
                    "timestamp": datetime.now(),
                }
            ]
        except Exception:
            return []

    def _get_recent_logs(self) -> List[str]:
        """Get recent log entries"""
        try:
            log_file = Path(__file__).parent.parent / "logs" / "trade.log"
            if log_file.exists():
                with open(log_file, "r") as f:
                    lines = f.readlines()[-10:]
                    return [line.strip() for line in lines]
            else:
                return ["[INFO] Log file not found"] * 3
        except Exception:
            return ["[ERROR] Failed to read logs"]

    def _draw_dashboard(self) -> None:
        """Draw the dashboard"""
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()

        # Draw header
        self._draw_header(0, width)

        # Draw main content based on current view
        if self.current_view == "overview":
            self._draw_overview(2, width, height - 6)
        elif self.current_view == "system":
            self._draw_system_view(2, width, height - 6)
        elif self.current_view == "application":
            self._draw_application_view(2, width, height - 6)
        elif self.current_view == "alerts":
            self._draw_alerts_view(2, width, height - 6)
        elif self.current_view == "logs":
            self._draw_logs_view(2, width, height - 6)

        # Draw footer
        self._draw_footer(height - 3, width)

        self.stdscr.refresh()

    def _draw_header(self, y: int, width: int) -> None:
        """Draw dashboard header"""
        header = "🚀 Polymarket Copy Bot - Monitoring Dashboard"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.stdscr.addstr(y, 0, header.ljust(width - 20), self.COLOR_HEADER | curses.A_BOLD)
        self.stdscr.addstr(y, width - 19, timestamp, self.COLOR_INFO)

        # View indicator
        view_text = f"View: {self.current_view.upper()}"
        self.stdscr.addstr(y + 1, 0, view_text, self.COLOR_ACCENT)

        # Status indicator
        status = "🟢 HEALTHY"
        if self.data.active_alerts:
            critical_alerts = [
                a for a in self.data.active_alerts if a.get("severity") == "CRITICAL"
            ]
            if critical_alerts:
                status = "🔴 CRITICAL"
            else:
                status = "🟡 WARNING"

        self.stdscr.addstr(
            y + 1,
            width - len(status),
            status,
            self.COLOR_CRITICAL if "CRITICAL" in status else self.COLOR_WARNING,
        )

    def _draw_overview(self, y: int, width: int, height: int) -> None:
        """Draw overview dashboard"""
        # System metrics summary
        sys_metrics = self.data.system_metrics
        self._draw_box(y, 0, 8, width // 2 - 1, "System Resources")
        self._draw_metric(
            y + 1,
            2,
            "CPU",
            f"{sys_metrics.get('cpu_percent', 0):.1f}%",
            self._get_metric_color(sys_metrics.get("cpu_percent", 0), 80, 90),
        )
        self._draw_metric(
            y + 2,
            2,
            "Memory",
            f"{sys_metrics.get('memory_percent', 0):.1f}%",
            self._get_metric_color(sys_metrics.get("memory_percent", 0), 85, 95),
        )
        self._draw_metric(
            y + 3,
            2,
            "Disk",
            f"{sys_metrics.get('disk_usage_percent', 0):.1f}%",
            self._get_metric_color(sys_metrics.get("disk_usage_percent", 0), 85, 95),
        )
        self._draw_metric(
            y + 4,
            2,
            "Load",
            f"{sys_metrics.get('cpu_load_1m', 0):.2f}",
            self._get_metric_color(sys_metrics.get("cpu_load_1m", 0) * 25, 80, 90),
        )
        self._draw_metric(
            y + 5,
            2,
            "Network",
            f"↓{sys_metrics.get('network_rx_mb', 0):.1f} ↑{sys_metrics.get('network_tx_mb', 0):.1f} MB/s",
            self.COLOR_INFO,
        )
        self._draw_metric(
            y + 6, 2, "Processes", str(sys_metrics.get("process_count", 0)), self.COLOR_INFO
        )

        # Application metrics summary
        app_metrics = self.data.application_metrics
        self._draw_box(y, width // 2 + 1, 8, width // 2 - 2, "Trading Performance")
        self._draw_metric(
            y + 1,
            width // 2 + 3,
            "Total Trades",
            str(app_metrics.get("total_trades", 0)),
            self.COLOR_INFO,
        )
        self._draw_metric(
            y + 2,
            width // 2 + 3,
            "Success Rate",
            f"{app_metrics.get('success_rate_percent', 0):.1f}%",
            self._get_metric_color(100 - app_metrics.get("success_rate_percent", 100), 20, 10),
        )
        self._draw_metric(
            y + 3,
            width // 2 + 3,
            "Avg Latency",
            f"{app_metrics.get('average_latency_ms', 0):.0f}ms",
            self._get_metric_color(app_metrics.get("average_latency_ms", 0), 5000, 10000),
        )
        self._draw_metric(
            y + 4,
            width // 2 + 3,
            "API Usage",
            f"{app_metrics.get('api_rate_limit_usage', 0)}%",
            self._get_metric_color(app_metrics.get("api_rate_limit_usage", 0), 75, 90),
        )
        self._draw_metric(
            y + 5,
            width // 2 + 3,
            "Circuit Breaker",
            "ACTIVE" if app_metrics.get("circuit_breaker_active", False) else "INACTIVE",
            (
                self.COLOR_CRITICAL
                if app_metrics.get("circuit_breaker_active", False)
                else self.COLOR_SUCCESS
            ),
        )
        self._draw_metric(
            y + 6,
            width // 2 + 3,
            "Wallet Balance",
            f"{app_metrics.get('wallet_balance_matic', 0):.3f} MATIC",
            self.COLOR_INFO,
        )

        # Active alerts
        alert_y = y + 10
        self._draw_box(alert_y, 0, min(6, height - alert_y - 4), width, "Active Alerts")
        if self.data.active_alerts:
            for i, alert in enumerate(self.data.active_alerts[:4]):
                if alert_y + i + 1 < height - 4:
                    severity_color = self._get_severity_color(alert.get("severity", "INFO"))
                    alert_text = f"{alert.get('severity', 'INFO')}: {alert.get('title', 'Unknown')}"
                    self.stdscr.addstr(alert_y + i + 1, 2, alert_text[: width - 4], severity_color)
        else:
            self.stdscr.addstr(alert_y + 1, 2, "No active alerts", self.COLOR_SUCCESS)

    def _draw_system_view(self, y: int, width: int, height: int) -> None:
        """Draw detailed system metrics view"""
        sys_metrics = self.data.system_metrics

        self._draw_box(y, 0, 12, width, "Detailed System Metrics")

        metrics = [
            ("CPU Usage", f"{sys_metrics.get('cpu_percent', 0):.1f}%"),
            (
                "CPU Load (1m/5m/15m)",
                f"{sys_metrics.get('cpu_load_1m', 0):.2f}/{sys_metrics.get('cpu_load_5m', 0):.2f}/{sys_metrics.get('cpu_load_15m', 0):.2f}",
            ),
            (
                "Memory Usage",
                f"{sys_metrics.get('memory_percent', 0):.1f}% ({sys_metrics.get('memory_used_gb', 0):.1f}GB used)",
            ),
            ("Memory Available", f"{sys_metrics.get('memory_available_gb', 0):.1f}GB"),
            (
                "Swap Usage",
                f"{sys_metrics.get('swap_percent', 0):.1f}% ({sys_metrics.get('swap_used_gb', 0):.1f}GB used)",
            ),
            (
                "Disk Usage",
                f"{sys_metrics.get('disk_usage_percent', 0):.1f}% ({sys_metrics.get('disk_used_gb', 0):.1f}GB used)",
            ),
            ("Disk Available", f"{sys_metrics.get('disk_free_gb', 0):.1f}GB"),
            (
                "Network I/O",
                f"RX: {sys_metrics.get('network_rx_mb', 0):.2f} MB/s, TX: {sys_metrics.get('network_tx_mb', 0):.2f} MB/s",
            ),
            (
                "File Descriptors",
                f"{sys_metrics.get('file_descriptors_used', 0)} / {sys_metrics.get('file_descriptors_limit', 0)}",
            ),
            ("Process Count", str(sys_metrics.get("process_count", 0))),
            ("System Uptime", self._format_uptime(sys_metrics.get("uptime_seconds", 0))),
        ]

        for i, (label, value) in enumerate(metrics):
            if y + i + 1 < height - 4:
                self.stdscr.addstr(y + i + 1, 2, f"{label}:".ljust(25), self.COLOR_INFO)
                self.stdscr.addstr(y + i + 1, 28, value, self._get_metric_color_value(label, value))

    def _draw_application_view(self, y: int, width: int, height: int) -> None:
        """Draw detailed application metrics view"""
        app_metrics = self.data.application_metrics

        self._draw_box(y, 0, 10, width, "Detailed Application Metrics")

        metrics = [
            ("Total Trades", str(app_metrics.get("total_trades", 0))),
            ("Successful Trades", str(app_metrics.get("successful_trades", 0))),
            ("Failed Trades", str(app_metrics.get("failed_trades", 0))),
            ("Pending Trades", str(app_metrics.get("pending_trades", 0))),
            ("Success Rate", f"{app_metrics.get('success_rate_percent', 0):.1f}%"),
            ("Average Latency", f"{app_metrics.get('average_latency_ms', 0):.0f}ms"),
            ("Trades per Minute", f"{app_metrics.get('trades_per_minute', 0):.1f}"),
            ("API Total Requests", str(app_metrics.get("api_requests_total", 0))),
            ("API Rate Limit Usage", f"{app_metrics.get('api_rate_limit_usage', 0)}%"),
            (
                "Circuit Breaker Status",
                "ACTIVE" if app_metrics.get("circuit_breaker_active", False) else "INACTIVE",
            ),
        ]

        for i, (label, value) in enumerate(metrics):
            if y + i + 1 < height - 4:
                self.stdscr.addstr(y + i + 1, 2, f"{label}:".ljust(25), self.COLOR_INFO)
                color = (
                    self.COLOR_CRITICAL
                    if "ACTIVE" in value and "Circuit" in label
                    else self._get_metric_color_value(label, value)
                )
                self.stdscr.addstr(y + i + 1, 28, value, color)

    def _draw_alerts_view(self, y: int, width: int, height: int) -> None:
        """Draw alerts view"""
        self._draw_box(y, 0, height - 4, width, "Active Alerts & History")

        alerts = self.data.active_alerts
        if alerts:
            for i, alert in enumerate(alerts):
                if y + i + 1 >= height - 4:
                    break

                severity_color = self._get_severity_color(alert.get("severity", "INFO"))
                timestamp = alert.get("timestamp", datetime.now()).strftime("%H:%M:%S")
                alert_line = f"[{timestamp}] {alert.get('severity', 'INFO')}: {alert.get('title', 'Unknown')}"

                self.stdscr.addstr(y + i + 1, 2, alert_line[: width - 4], severity_color)

                # Show message on next line if space
                if y + i + 2 < height - 4 and alert.get("message"):
                    message = alert.get("message", "")[: width - 6]
                    self.stdscr.addstr(y + i + 2, 4, message, self.COLOR_INFO)
        else:
            self.stdscr.addstr(y + 1, 2, "No active alerts", self.COLOR_SUCCESS)

    def _draw_logs_view(self, y: int, width: int, height: int) -> None:
        """Draw logs streaming view"""
        self._draw_box(y, 0, height - 4, width, "Live Log Stream")

        logs = self.data.recent_logs
        for i, log_line in enumerate(logs[-min(len(logs), height - 6) :]):
            if y + i + 1 < height - 4:
                # Color code log levels
                color = self.COLOR_INFO
                if "[ERROR]" in log_line or "[CRITICAL]" in log_line:
                    color = self.COLOR_CRITICAL
                elif "[WARNING]" in log_line:
                    color = self.COLOR_WARNING
                elif "[INFO]" in log_line:
                    color = self.COLOR_SUCCESS

                self.stdscr.addstr(y + i + 1, 2, log_line[: width - 4], color)

    def _draw_footer(self, y: int, width: int) -> None:
        """Draw dashboard footer with controls"""
        controls = (
            "[O]verview [S]ystem [A]pplication [L]erts [G]ogs [Q]uit | Last Update: {}".format(
                self.data.last_update.strftime("%H:%M:%S")
            )
        )

        self.stdscr.addstr(y, 0, "─" * width, self.COLOR_ACCENT)
        self.stdscr.addstr(y + 1, 0, controls[:width], self.COLOR_INFO)
        self.stdscr.addstr(y + 2, 0, "─" * width, self.COLOR_ACCENT)

    def _draw_box(self, y: int, x: int, height: int, width: int, title: str) -> None:
        """Draw a bordered box with title"""
        # Top border
        self.stdscr.addstr(y, x, "┌" + "─" * (width - 2) + "┐", self.COLOR_ACCENT)

        # Title
        title_str = f" {title} "
        if len(title_str) < width - 2:
            self.stdscr.addstr(y, x + 1, title_str, self.COLOR_HEADER | curses.A_BOLD)

        # Side borders
        for i in range(1, height - 1):
            self.stdscr.addstr(y + i, x, "│", self.COLOR_ACCENT)
            self.stdscr.addstr(y + i, x + width - 1, "│", self.COLOR_ACCENT)

        # Bottom border
        self.stdscr.addstr(y + height - 1, x, "└" + "─" * (width - 2) + "┘", self.COLOR_ACCENT)

    def _draw_metric(self, y: int, x: int, label: str, value: str, color: int) -> None:
        """Draw a metric with label and value"""
        self.stdscr.addstr(y, x, f"{label}:", self.COLOR_INFO)
        self.stdscr.addstr(y, x + 15, value, color)

    def _handle_input(self) -> None:
        """Handle user input"""
        try:
            self.stdscr.timeout(1000)  # 1 second timeout
            key = self.stdscr.getch()

            if key == ord("q") or key == ord("Q"):
                self.running = False
            elif key == ord("o") or key == ord("O"):
                self.current_view = "overview"
            elif key == ord("s") or key == ord("S"):
                self.current_view = "system"
            elif key == ord("a") or key == ord("A"):
                self.current_view = "application"
            elif key == ord("l") or key == ord("L"):
                self.current_view = "alerts"
            elif key == ord("g") or key == ord("G"):
                self.current_view = "logs"
            elif key == curses.KEY_RESIZE:
                # Handle terminal resize
                curses.resizeterm(*self.stdscr.getmaxyx())

        except curses.error:
            pass  # Ignore curses errors

    def _get_metric_color(
        self, value: float, warning_threshold: float, critical_threshold: float
    ) -> int:
        """Get color based on metric value and thresholds"""
        if value >= critical_threshold:
            return self.COLOR_CRITICAL
        elif value >= warning_threshold:
            return self.COLOR_WARNING
        else:
            return self.COLOR_SUCCESS

    def _get_metric_color_value(self, label: str, value: str) -> int:
        """Get color for metric based on label and value"""
        try:
            if "CPU" in label or "Memory" in label or "Disk" in label:
                numeric_value = float(
                    "".join(filter(lambda x: x.isdigit() or x == ".", value.split("%")[0]))
                )
                if "CPU" in label:
                    return self._get_metric_color(numeric_value, 80, 90)
                elif "Memory" in label or "Disk" in label:
                    return self._get_metric_color(numeric_value, 85, 95)
            elif "Latency" in label:
                numeric_value = float("".join(filter(lambda x: x.isdigit() or x == ".", value)))
                return self._get_metric_color(numeric_value, 5000, 10000)
            elif "Rate" in label and "%" in value:
                numeric_value = float("".join(filter(lambda x: x.isdigit() or x == ".", value)))
                return self._get_metric_color(
                    100 - numeric_value, 20, 10
                )  # Invert for success rate
        except (ValueError, IndexError):
            pass

        return self.COLOR_INFO

    def _get_severity_color(self, severity: str) -> int:
        """Get color for alert severity"""
        severity_colors = {
            "CRITICAL": self.COLOR_CRITICAL,
            "HIGH": self.COLOR_CRITICAL,
            "ERROR": self.COLOR_CRITICAL,
            "WARNING": self.COLOR_WARNING,
            "MEDIUM": self.COLOR_WARNING,
            "LOW": self.COLOR_INFO,
            "INFO": self.COLOR_INFO,
        }
        return severity_colors.get(severity.upper(), self.COLOR_INFO)

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime seconds into readable string"""
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        else:
            return f"{minutes}m {seconds}s"


def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Terminal Dashboard for Polymarket Copy Bot")
        print("")
        print("Controls:")
        print("  O - Overview")
        print("  S - System metrics")
        print("  A - Application metrics")
        print("  L - Active alerts")
        print("  G - Live logs")
        print("  Q - Quit")
        print("")
        print("The dashboard updates automatically and shows real-time monitoring data.")
        return

    def run_dashboard(stdscr):
        dashboard = TerminalDashboard(stdscr)
        dashboard.run()

    try:
        curses.wrapper(run_dashboard)
    except KeyboardInterrupt:
        print("\nDashboard stopped by user")
    except Exception as e:
        print(f"Dashboard error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
