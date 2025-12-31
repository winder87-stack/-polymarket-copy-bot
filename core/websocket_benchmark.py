"""
Performance Benchmarking System for WebSocket vs Polling

Compares latency and performance between:
- WebSocket-based real-time monitoring
- Traditional polling-based monitoring

Provides detailed metrics and reporting for migration decision-making.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WebSocketBenchmark:
    """
    Performance benchmarking system for WebSocket vs polling comparison.

    Tracks:
    - Trade detection latency (time from transaction to detection)
    - System resource usage (CPU, memory)
    - Network overhead (messages, API calls)
    - Reliability metrics (uptime, errors, reconnects)
    - Cost comparison (API calls vs WebSocket subscription)
    """

    def __init__(self) -> None:
        """Initialize benchmark system"""
        self.start_time: Optional[float] = None
        self.benchmark_data: List[Dict[str, Any]] = []

        # Metrics tracking
        self.websocket_metrics = {
            "trade_detections": [],
            "latencies": [],
            "errors": 0,
            "reconnects": 0,
            "uptime_start": None,
            "uptime_end": None,
        }

        self.polling_metrics = {
            "trade_detections": [],
            "latencies": [],
            "errors": 0,
            "cycles": 0,
            "uptime_start": None,
            "uptime_end": None,
        }

        logger.info("Performance benchmark system initialized")

    def start_benchmark(self) -> None:
        """Start benchmark period"""
        self.start_time = time.time()
        logger.info("📊 Benchmark started")

    def record_websocket_detection(
        self, trade: Dict[str, Any], detection_latency: float
    ) -> None:
        """
        Record WebSocket trade detection.

        Args:
            trade: Detected trade data
            detection_latency: Time from transaction to detection (seconds)
        """
        if not self.websocket_metrics["uptime_start"]:
            self.websocket_metrics["uptime_start"] = time.time()

        self.websocket_metrics["trade_detections"].append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trade_id": trade.get("tx_hash", "unknown"),
                "latency_ms": detection_latency * 1000,
            }
        )
        self.websocket_metrics["latencies"].append(detection_latency)

        logger.debug(
            f"📊 WebSocket detection recorded: {detection_latency * 1000:.1f}ms"
        )

    def record_polling_detection(
        self, trade: Dict[str, Any], detection_latency: float
    ) -> None:
        """
        Record polling trade detection.

        Args:
            trade: Detected trade data
            detection_latency: Time from transaction to detection (seconds)
        """
        if not self.polling_metrics["uptime_start"]:
            self.polling_metrics["uptime_start"] = time.time()

        self.polling_metrics["trade_detections"].append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trade_id": trade.get("tx_hash", "unknown"),
                "latency_ms": detection_latency * 1000,
            }
        )
        self.polling_metrics["latencies"].append(detection_latency)

        logger.debug(f"📊 Polling detection recorded: {detection_latency * 1000:.1f}ms")

    def record_websocket_error(self, error: Exception) -> None:
        """Record WebSocket error"""
        self.websocket_metrics["errors"] += 1
        logger.debug(f"📊 WebSocket error recorded: {error}")

    def record_polling_error(self, error: Exception) -> None:
        """Record polling error"""
        self.polling_metrics["errors"] += 1
        logger.debug(f"📊 Polling error recorded: {error}")

    def record_websocket_reconnect(self) -> None:
        """Record WebSocket reconnection"""
        self.websocket_metrics["reconnects"] += 1
        logger.debug("📊 WebSocket reconnect recorded")

    def record_polling_cycle(self) -> None:
        """Record polling cycle completion"""
        self.polling_metrics["cycles"] += 1

    def stop_benchmark(self) -> Dict[str, Any]:
        """
        Stop benchmark and generate report.

        Returns:
            Comprehensive benchmark report
        """
        if not self.start_time:
            return {"error": "Benchmark not started"}

        end_time = time.time()
        duration = end_time - self.start_time

        # Calculate WebSocket metrics
        ws_uptime = 0.0
        if self.websocket_metrics["uptime_start"]:
            ws_uptime = (
                end_time - self.websocket_metrics["uptime_start"]
                if not self.websocket_metrics["uptime_end"]
                else self.websocket_metrics["uptime_end"]
                - self.websocket_metrics["uptime_start"]
            )

        ws_avg_latency = (
            sum(self.websocket_metrics["latencies"])
            / len(self.websocket_metrics["latencies"])
            if self.websocket_metrics["latencies"]
            else 0.0
        )
        ws_min_latency = (
            min(self.websocket_metrics["latencies"])
            if self.websocket_metrics["latencies"]
            else 0.0
        )
        ws_max_latency = (
            max(self.websocket_metrics["latencies"])
            if self.websocket_metrics["latencies"]
            else 0.0
        )

        # Calculate polling metrics
        polling_uptime = 0.0
        if self.polling_metrics["uptime_start"]:
            polling_uptime = (
                end_time - self.polling_metrics["uptime_start"]
                if not self.polling_metrics["uptime_end"]
                else self.polling_metrics["uptime_end"]
                - self.polling_metrics["uptime_start"]
            )

        polling_avg_latency = (
            sum(self.polling_metrics["latencies"])
            / len(self.polling_metrics["latencies"])
            if self.polling_metrics["latencies"]
            else 0.0
        )
        polling_min_latency = (
            min(self.polling_metrics["latencies"])
            if self.polling_metrics["latencies"]
            else 0.0
        )
        polling_max_latency = (
            max(self.polling_metrics["latencies"])
            if self.polling_metrics["latencies"]
            else 0.0
        )

        # Calculate improvements
        latency_improvement_ms = (polling_avg_latency - ws_avg_latency) * 1000
        latency_improvement_percent = (
            (latency_improvement_ms / (polling_avg_latency * 1000) * 100)
            if polling_avg_latency > 0
            else 0
        )

        report = {
            "benchmark_duration_seconds": duration,
            "start_time": datetime.fromtimestamp(
                self.start_time, tz=timezone.utc
            ).isoformat(),
            "end_time": datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat(),
            "websocket": {
                "trade_detections": len(self.websocket_metrics["trade_detections"]),
                "avg_latency_ms": ws_avg_latency * 1000,
                "min_latency_ms": ws_min_latency * 1000,
                "max_latency_ms": ws_max_latency * 1000,
                "errors": self.websocket_metrics["errors"],
                "reconnects": self.websocket_metrics["reconnects"],
                "uptime_seconds": ws_uptime,
                "uptime_percent": (ws_uptime / duration * 100) if duration > 0 else 0,
            },
            "polling": {
                "trade_detections": len(self.polling_metrics["trade_detections"]),
                "avg_latency_ms": polling_avg_latency * 1000,
                "min_latency_ms": polling_min_latency * 1000,
                "max_latency_ms": polling_max_latency * 1000,
                "errors": self.polling_metrics["errors"],
                "cycles": self.polling_metrics["cycles"],
                "uptime_seconds": polling_uptime,
                "uptime_percent": (polling_uptime / duration * 100)
                if duration > 0
                else 0,
            },
            "improvement": {
                "latency_reduction_ms": latency_improvement_ms,
                "latency_reduction_percent": latency_improvement_percent,
                "faster_detections": len(
                    [
                        d
                        for d in self.websocket_metrics["trade_detections"]
                        if d["latency_ms"] < polling_avg_latency * 1000
                    ]
                )
                if polling_avg_latency > 0
                else 0,
            },
            "recommendation": self._generate_recommendation(
                latency_improvement_ms, latency_improvement_percent
            ),
        }

        logger.info("📊 Benchmark completed")
        return report

    def _generate_recommendation(
        self, latency_improvement_ms: float, latency_improvement_percent: float
    ) -> str:
        """Generate migration recommendation based on metrics"""
        if latency_improvement_ms > 5000:  # >5 second improvement
            return (
                "STRONG RECOMMENDATION: WebSocket provides significant latency improvement "
                f"({latency_improvement_ms:.0f}ms, {latency_improvement_percent:.1f}%). "
                "Proceed with full migration."
            )
        elif latency_improvement_ms > 2000:  # >2 second improvement
            return (
                "RECOMMENDATION: WebSocket provides moderate latency improvement "
                f"({latency_improvement_ms:.0f}ms, {latency_improvement_percent:.1f}%). "
                "Consider phased migration."
            )
        elif latency_improvement_ms > 0:
            return (
                "MARGINAL IMPROVEMENT: WebSocket provides small latency improvement "
                f"({latency_improvement_ms:.0f}ms, {latency_improvement_percent:.1f}%). "
                "Evaluate other factors (cost, reliability) before migration."
            )
        else:
            return (
                "NO IMPROVEMENT: WebSocket does not provide latency improvement. "
                "Stick with polling or investigate WebSocket implementation."
            )

    def get_live_metrics(self) -> Dict[str, Any]:
        """Get current benchmark metrics (without stopping benchmark)"""
        if not self.start_time:
            return {"error": "Benchmark not started"}

        current_time = time.time()
        duration = current_time - self.start_time

        ws_avg = (
            sum(self.websocket_metrics["latencies"])
            / len(self.websocket_metrics["latencies"])
            if self.websocket_metrics["latencies"]
            else 0.0
        )
        polling_avg = (
            sum(self.polling_metrics["latencies"])
            / len(self.polling_metrics["latencies"])
            if self.polling_metrics["latencies"]
            else 0.0
        )

        return {
            "duration_seconds": duration,
            "websocket": {
                "detections": len(self.websocket_metrics["trade_detections"]),
                "avg_latency_ms": ws_avg * 1000,
                "errors": self.websocket_metrics["errors"],
                "reconnects": self.websocket_metrics["reconnects"],
            },
            "polling": {
                "detections": len(self.polling_metrics["trade_detections"]),
                "avg_latency_ms": polling_avg * 1000,
                "errors": self.polling_metrics["errors"],
                "cycles": self.polling_metrics["cycles"],
            },
            "improvement_ms": (polling_avg - ws_avg) * 1000,
        }
