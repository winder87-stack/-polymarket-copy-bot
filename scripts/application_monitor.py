#!/usr/bin/env python3
"""
Application Metrics Monitor for Polymarket Copy Bot

Tracks application-level performance metrics including:
- Trade execution latency and success rates
- API rate limit usage and violations
- Order book synchronization status
- Circuit breaker activation status
- Wallet balance and transaction monitoring
"""

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TradeMetrics:
    """Trade execution metrics"""

    timestamp: datetime
    total_trades: int
    successful_trades: int
    failed_trades: int
    pending_trades: int
    average_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    success_rate_percent: float
    trades_per_minute: float


@dataclass
class APIMetrics:
    """API usage metrics"""

    timestamp: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    rate_limited_requests: int
    average_response_time_ms: float
    current_rate_limit_usage: int
    rate_limit_remaining: int
    rate_limit_reset_time: Optional[datetime]


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker status"""

    timestamp: datetime
    is_active: bool
    activation_count: int
    last_activation_time: Optional[datetime]
    deactivation_count: int
    last_deactivation_time: Optional[datetime]
    failure_threshold_breaches: int


@dataclass
class WalletMetrics:
    """Wallet balance and transaction metrics"""

    timestamp: datetime
    wallet_address: str
    balance_matic: float
    balance_usdc: float
    total_transactions: int
    pending_transactions: int
    failed_transactions: int
    gas_used_24h: int


class ApplicationMonitor:
    """Application-level performance monitoring"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Metrics history
        self.trade_metrics: List[TradeMetrics] = []
        self.api_metrics: List[APIMetrics] = []
        self.circuit_breaker_metrics: List[CircuitBreakerMetrics] = []
        self.wallet_metrics: List[WalletMetrics] = []

        # Current metrics state
        self.current_trade_counts = {"total": 0, "successful": 0, "failed": 0, "pending": 0}
        self.trade_latencies: List[float] = []
        self.api_call_counts = {"total": 0, "successful": 0, "failed": 0, "rate_limited": 0}
        self.api_response_times: List[float] = []

        # Circuit breaker state
        self.circuit_breaker_active = False
        self.circuit_breaker_activations = 0
        self.circuit_breaker_last_activation: Optional[datetime] = None

        # Max history size
        self.max_history = 1000

    def start_monitoring(self, interval: float = 10.0) -> None:
        """Start application monitoring"""
        if self.monitoring_active:
            logger.warning("Application monitoring already active")
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, args=(interval,), daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Application monitoring started with {interval}s interval")

    def stop_monitoring(self) -> None:
        """Stop monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("Application monitoring stopped")

    def record_trade_execution(
        self, success: bool, latency_ms: float, pending: bool = False
    ) -> None:
        """Record a trade execution"""
        self.current_trade_counts["total"] += 1

        if success:
            self.current_trade_counts["successful"] += 1
        else:
            self.current_trade_counts["failed"] += 1

        if pending:
            self.current_trade_counts["pending"] += 1
        elif success:
            self.current_trade_counts["pending"] = max(0, self.current_trade_counts["pending"] - 1)

        if latency_ms > 0:
            self.trade_latencies.append(latency_ms)
            # Keep only recent latencies (last 1000)
            if len(self.trade_latencies) > 1000:
                self.trade_latencies = self.trade_latencies[-1000:]

    def record_api_call(
        self, success: bool, response_time_ms: float, rate_limited: bool = False
    ) -> None:
        """Record an API call"""
        self.api_call_counts["total"] += 1

        if rate_limited:
            self.api_call_counts["rate_limited"] += 1
        elif success:
            self.api_call_counts["successful"] += 1
        else:
            self.api_call_counts["failed"] += 1

        if response_time_ms > 0:
            self.api_response_times.append(response_time_ms)
            # Keep only recent response times (last 1000)
            if len(self.api_response_times) > 1000:
                self.api_response_times = self.api_response_times[-1000:]

    def activate_circuit_breaker(self) -> None:
        """Record circuit breaker activation"""
        if not self.circuit_breaker_active:
            self.circuit_breaker_active = True
            self.circuit_breaker_activations += 1
            self.circuit_breaker_last_activation = datetime.now()
            logger.warning("Circuit breaker activated")

    def deactivate_circuit_breaker(self) -> None:
        """Record circuit breaker deactivation"""
        if self.circuit_breaker_active:
            self.circuit_breaker_active = False
            logger.info("Circuit breaker deactivated")

    def get_current_trade_metrics(self) -> TradeMetrics:
        """Get current trade metrics"""
        total_trades = self.current_trade_counts["total"]
        successful_trades = self.current_trade_counts["successful"]

        # Calculate success rate
        success_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0.0

        # Calculate latency statistics
        avg_latency = (
            sum(self.trade_latencies) / len(self.trade_latencies) if self.trade_latencies else 0.0
        )
        min_latency = min(self.trade_latencies) if self.trade_latencies else 0.0
        max_latency = max(self.trade_latencies) if self.trade_latencies else 0.0

        # Calculate trades per minute (rough estimate)
        trades_per_minute = total_trades / max(
            1,
            (
                datetime.now() - datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
            ).seconds
            / 60,
        )

        return TradeMetrics(
            timestamp=datetime.now(),
            total_trades=total_trades,
            successful_trades=successful_trades,
            failed_trades=self.current_trade_counts["failed"],
            pending_trades=self.current_trade_counts["pending"],
            average_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            success_rate_percent=success_rate,
            trades_per_minute=trades_per_minute,
        )

    def get_current_api_metrics(self) -> APIMetrics:
        """Get current API metrics"""
        total_requests = self.api_call_counts["total"]

        # Calculate average response time
        avg_response_time = (
            sum(self.api_response_times) / len(self.api_response_times)
            if self.api_response_times
            else 0.0
        )

        # Mock rate limit data (would come from actual API client)
        current_rate_limit_usage = min(100, int((self.api_call_counts["total"] % 100)))
        rate_limit_remaining = 100 - current_rate_limit_usage

        return APIMetrics(
            timestamp=datetime.now(),
            total_requests=total_requests,
            successful_requests=self.api_call_counts["successful"],
            failed_requests=self.api_call_counts["failed"],
            rate_limited_requests=self.api_call_counts["rate_limited"],
            average_response_time_ms=avg_response_time,
            current_rate_limit_usage=current_rate_limit_usage,
            rate_limit_remaining=rate_limit_remaining,
            rate_limit_reset_time=None,  # Would be set by API client
        )

    def get_current_circuit_breaker_metrics(self) -> CircuitBreakerMetrics:
        """Get current circuit breaker metrics"""
        return CircuitBreakerMetrics(
            timestamp=datetime.now(),
            is_active=self.circuit_breaker_active,
            activation_count=self.circuit_breaker_activations,
            last_activation_time=self.circuit_breaker_last_activation,
            deactivation_count=self.circuit_breaker_activations,  # Simplified
            last_deactivation_time=None,  # Would track separately
            failure_threshold_breaches=self.circuit_breaker_activations,
        )

    def get_wallet_metrics(self, wallet_address: str) -> WalletMetrics:
        """Get wallet metrics (mock implementation)"""
        # This would integrate with actual wallet monitoring
        return WalletMetrics(
            timestamp=datetime.now(),
            wallet_address=wallet_address,
            balance_matic=1.5,  # Mock data
            balance_usdc=100.0,  # Mock data
            total_transactions=150,
            pending_transactions=2,
            failed_transactions=3,
            gas_used_24h=50000,
        )

    def get_performance_alerts(self) -> Dict[str, str]:
        """Check for performance alerts"""
        alerts = {}
        trade_metrics = self.get_current_trade_metrics()
        api_metrics = self.get_current_api_metrics()

        # Trade success rate alerts
        if trade_metrics.success_rate_percent < 80:
            alerts["trade_success"] = (
                f"CRITICAL: Trade success rate at {trade_metrics.success_rate_percent:.1f}%"
            )
        elif trade_metrics.success_rate_percent < 90:
            alerts["trade_success"] = (
                f"WARNING: Trade success rate at {trade_metrics.success_rate_percent:.1f}%"
            )

        # Trade latency alerts
        if trade_metrics.average_latency_ms > 10000:  # 10 seconds
            alerts["trade_latency"] = (
                f"CRITICAL: Average trade latency {trade_metrics.average_latency_ms:.0f}ms"
            )
        elif trade_metrics.average_latency_ms > 5000:  # 5 seconds
            alerts["trade_latency"] = (
                f"WARNING: Average trade latency {trade_metrics.average_latency_ms:.0f}ms"
            )

        # API rate limit alerts
        if api_metrics.current_rate_limit_usage > 90:
            alerts["api_rate_limit"] = (
                f"CRITICAL: API rate limit at {api_metrics.current_rate_limit_usage}%"
            )
        elif api_metrics.current_rate_limit_usage > 75:
            alerts["api_rate_limit"] = (
                f"WARNING: API rate limit at {api_metrics.current_rate_limit_usage}%"
            )

        # Circuit breaker alerts
        if self.circuit_breaker_active:
            alerts["circuit_breaker"] = "CRITICAL: Circuit breaker is active"

        return alerts

    def _monitoring_loop(self, interval: float) -> None:
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Collect metrics
                trade_metrics = self.get_current_trade_metrics()
                api_metrics = self.get_current_api_metrics()
                cb_metrics = self.get_current_circuit_breaker_metrics()

                # Store in history
                self.trade_metrics.append(trade_metrics)
                self.api_metrics.append(api_metrics)
                self.circuit_breaker_metrics.append(cb_metrics)

                # Maintain history size
                for history_list in [
                    self.trade_metrics,
                    self.api_metrics,
                    self.circuit_breaker_metrics,
                ]:
                    if len(history_list) > self.max_history:
                        history_list[:] = history_list[-self.max_history :]

                # Check for alerts
                alerts = self.get_performance_alerts()
                if alerts:
                    for alert_type, message in alerts.items():
                        logger.warning(f"APPLICATION ALERT: {message}")

            except Exception as e:
                logger.error(f"Error in application monitoring loop: {e}")

            time.sleep(interval)


def main():
    """CLI interface for application monitoring"""
    import argparse

    parser = argparse.ArgumentParser(description="Application Monitor for Polymarket Copy Bot")
    parser.add_argument(
        "action", choices=["snapshot", "monitor", "alerts", "trades", "api", "circuit-breaker"]
    )
    parser.add_argument(
        "--interval", type=float, default=10.0, help="Monitoring interval in seconds"
    )
    parser.add_argument("--wallet", help="Wallet address for wallet metrics")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    monitor = ApplicationMonitor()

    if args.action == "snapshot":
        trade_metrics = monitor.get_current_trade_metrics()
        api_metrics = monitor.get_current_api_metrics()
        cb_metrics = monitor.get_current_circuit_breaker_metrics()

        if args.json:
            output = {
                "trade_metrics": asdict(trade_metrics),
                "api_metrics": asdict(api_metrics),
                "circuit_breaker": asdict(cb_metrics),
            }
            print(json.dumps(output, default=str, indent=2))
        else:
            print("Application Metrics Snapshot:")
            print(
                f"  Trades: {trade_metrics.total_trades} total, {trade_metrics.success_rate_percent:.1f}% success"
            )
            print(f"  Latency: {trade_metrics.average_latency_ms:.0f}ms avg")
            print(
                f"  API: {api_metrics.total_requests} requests, {api_metrics.current_rate_limit_usage}% rate limit"
            )
            print(f"  Circuit Breaker: {'ACTIVE' if cb_metrics.is_active else 'INACTIVE'}")

    elif args.action == "monitor":
        print("Starting application monitoring... (Ctrl+C to stop)")
        monitor.start_monitoring(args.interval)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping monitoring...")
            monitor.stop_monitoring()

    elif args.action == "alerts":
        alerts = monitor.get_performance_alerts()
        if args.json:
            print(json.dumps(alerts, indent=2))
        else:
            if alerts:
                print("Active Performance Alerts:")
                for alert_type, message in alerts.items():
                    print(f"  {message}")
            else:
                print("No active performance alerts")

    elif args.action == "trades":
        metrics = monitor.get_current_trade_metrics()
        if args.json:
            print(json.dumps(asdict(metrics), default=str, indent=2))
        else:
            print("Trade Metrics:")
            print(f"  Total Trades: {metrics.total_trades}")
            print(f"  Success Rate: {metrics.success_rate_percent:.1f}%")
            print(f"  Average Latency: {metrics.average_latency_ms:.0f}ms")
            print(f"  Trades/Minute: {metrics.trades_per_minute:.1f}")

    elif args.action == "api":
        metrics = monitor.get_current_api_metrics()
        if args.json:
            print(json.dumps(asdict(metrics), default=str, indent=2))
        else:
            print("API Metrics:")
            print(f"  Total Requests: {metrics.total_requests}")
            print(
                f"  Success Rate: {(metrics.successful_requests/metrics.total_requests*100):.1f}%"
                if metrics.total_requests > 0
                else 0
            )
            print(f"  Rate Limit Usage: {metrics.current_rate_limit_usage}%")
            print(f"  Average Response Time: {metrics.average_response_time_ms:.0f}ms")

    elif args.action == "circuit-breaker":
        metrics = monitor.get_current_circuit_breaker_metrics()
        if args.json:
            print(json.dumps(asdict(metrics), default=str, indent=2))
        else:
            print("Circuit Breaker Status:")
            print(f"  Active: {metrics.is_active}")
            print(f"  Activation Count: {metrics.activation_count}")
            if metrics.last_activation_time:
                print(f"  Last Activation: {metrics.last_activation_time}")


if __name__ == "__main__":
    main()
