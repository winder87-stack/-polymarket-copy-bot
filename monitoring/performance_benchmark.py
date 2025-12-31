#!/usr/bin/env python3
"""
Performance Benchmarking System
================================

Automated performance benchmarking including:
- Trade execution latency measurement
- Memory usage monitoring
- API call performance tracking
- System resource utilization
- Comparative analysis against baselines

Generates performance reports and alerts on regressions.
"""

import asyncio
import json
import logging
import os
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from monitoring.monitoring_config import monitoring_config

logger = logging.getLogger(__name__)


class PerformanceBenchmark:
    """Performance benchmarking system"""

    def __init__(self) -> None:
        self.config = monitoring_config.performance
        self.baseline_data = {}
        self.current_results = {}
        self.alerts = []

        # Load baseline data
        self._load_baseline()

    def _load_baseline(self) -> None:
        """Load performance baseline data"""
        if os.path.exists(self.config.baseline_file):
            try:
                with open(self.config.baseline_file, "r") as f:
                    self.baseline_data = json.load(f)
                logger.info(
                    f"✅ Loaded performance baseline from {self.config.baseline_file}"
                )
            except Exception as e:
                logger.error(f"❌ Failed to load baseline: {e}")
                self.baseline_data = {}
        else:
            logger.warning(f"⚠️ No baseline file found at {self.config.baseline_file}")
            self.baseline_data = {}

    async def run_full_benchmark(self) -> Dict[str, Any]:
        """Run comprehensive performance benchmark"""
        logger.info("📊 Starting comprehensive performance benchmark")

        benchmark_start = datetime.now()

        results = {
            "timestamp": benchmark_start.isoformat(),
            "duration_minutes": self.config.benchmark_duration_minutes,
            "scenarios": {},
            "system_metrics": {},
            "comparison": {},
            "alerts": [],
        }

        # Run benchmark scenarios
        scenarios = []

        if self.config.trade_execution_benchmark:
            scenarios.append(("trade_execution", self._benchmark_trade_execution()))

        if self.config.wallet_scanning_benchmark:
            scenarios.append(("wallet_scanning", self._benchmark_wallet_scanning()))

        if self.config.api_call_benchmark:
            scenarios.append(("api_calls", self._benchmark_api_calls()))

        if self.config.memory_usage_benchmark:
            scenarios.append(("memory_usage", self._benchmark_memory_usage()))

        # Execute scenarios
        for scenario_name, scenario_coro in scenarios:
            try:
                logger.info(f"Running {scenario_name} benchmark...")
                scenario_result = await scenario_coro
                results["scenarios"][scenario_name] = scenario_result
                logger.info(f"✅ {scenario_name} benchmark completed")
            except Exception as e:
                logger.error(f"❌ {scenario_name} benchmark failed: {e}")
                results["scenarios"][scenario_name] = {
                    "error": str(e),
                    "status": "failed",
                }

        # Collect system metrics
        results["system_metrics"] = await self._collect_system_metrics()

        # Compare against baseline
        results["comparison"] = self._compare_against_baseline(results)

        # Generate alerts
        results["alerts"] = self.alerts

        # Save results
        await self._save_results(results)

        # Update baseline if needed
        await self._update_baseline_if_improved(results)

        benchmark_duration = (datetime.now() - benchmark_start).total_seconds()
        logger.info(f"📊 Performance benchmark completed in {benchmark_duration:.1f}s")

        return results

    async def _benchmark_trade_execution(self) -> Dict[str, Any]:
        """Benchmark trade execution performance"""
        result = {
            "latency_samples": [],
            "throughput_tps": 0,
            "error_rate": 0,
            "memory_delta_mb": 0,
            "status": "completed",
        }

        try:
            # Mock trade execution for benchmarking
            # In real implementation, this would use actual trade execution
            # but with mock data to avoid real transactions

            start_memory = psutil.Process().memory_info().rss / 1024 / 1024
            start_time = time.time()

            # Simulate multiple trade executions
            latencies = []
            for i in range(50):  # Simulate 50 trades
                trade_start = time.time()

                # Simulate trade execution logic
                await asyncio.sleep(0.01)  # Mock processing time

                trade_latency = time.time() - trade_start
                latencies.append(trade_latency)

            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024

            # Calculate metrics
            total_time = end_time - start_time
            result["latency_samples"] = latencies
            result["avg_latency_ms"] = statistics.mean(latencies) * 1000
            result["p95_latency_ms"] = (
                sorted(latencies)[int(len(latencies) * 0.95)] * 1000
            )
            result["throughput_tps"] = len(latencies) / total_time
            result["memory_delta_mb"] = end_memory - start_memory

            # Check thresholds
            if result["throughput_tps"] < self.config.min_throughput_tps:
                self.alerts.append(
                    {
                        "level": "high",
                        "metric": "trade_throughput",
                        "message": f"Trade throughput {result['throughput_tps']:.1f} TPS below threshold {self.config.min_throughput_tps} TPS",
                        "value": result["throughput_tps"],
                        "threshold": self.config.min_throughput_tps,
                    }
                )

            logger.info(f"Trade execution benchmark completed in {total_time:.2f}s")
        except Exception as e:
            logger.error(f"Trade execution benchmark failed: {e}")
            result["error"] = str(e)
            result["status"] = "failed"

        return result

    async def _benchmark_wallet_scanning(self) -> Dict[str, Any]:
        """Benchmark wallet scanning performance"""
        result = {
            "scan_times": [],
            "wallets_per_second": 0,
            "memory_usage_mb": 0,
            "status": "completed",
        }

        try:
            # Mock wallet scanning benchmark
            from config.settings import settings

            wallet_count = (
                len(settings.monitoring.target_wallets) or 25
            )  # Default to 25 if not loaded
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024
            start_time = time.time()

            scan_times = []
            for i in range(min(wallet_count, 10)):  # Scan subset for benchmarking
                scan_start = time.time()

                # Simulate wallet scanning logic
                await asyncio.sleep(0.05)  # Mock API call time

                scan_time = time.time() - scan_start
                scan_times.append(scan_time)

            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024

            # Calculate metrics
            total_time = end_time - start_time
            result["scan_times"] = scan_times
            result["avg_scan_time_ms"] = statistics.mean(scan_times) * 1000
            result["wallets_per_second"] = len(scan_times) / total_time
            result["memory_usage_mb"] = end_memory - start_memory

            logger.info(f"Wallet scanning benchmark completed in {total_time:.2f}s")
        except Exception as e:
            logger.error(f"Wallet scanning benchmark failed: {e}")
            result["error"] = str(e)
            result["status"] = "failed"

        return result

    async def _benchmark_api_calls(self) -> Dict[str, Any]:
        """Benchmark API call performance"""
        result = {
            "response_times": [],
            "success_rate": 0.0,
            "avg_response_time_ms": 0,
            "status": "completed",
        }

        try:
            # Mock API call benchmarking
            api_calls = [
                ("polygonscan", "https://api.polygonscan.com/api"),
                ("clob", "https://clob.polymarket.com"),
                ("polygon_rpc", "https://polygon-rpc.com"),
            ]

            response_times = []
            success_count = 0

            for api_name, api_url in api_calls:
                for i in range(5):  # 5 calls per API
                    try:
                        start_time = time.time()

                        # Mock API call (in real implementation, make actual calls)
                        await asyncio.sleep(0.02)  # Mock network latency

                        response_time = time.time() - start_time
                        response_times.append(response_time)
                        success_count += 1

                    except Exception as e:
                        logger.debug(f"API call to {api_name} failed: {e}")

            # Calculate metrics
            result["response_times"] = response_times
            result["success_rate"] = (
                success_count / len(response_times) if response_times else 0
            )
            result["avg_response_time_ms"] = (
                statistics.mean(response_times) * 1000 if response_times else 0
            )

            # Check thresholds
            if result["avg_response_time_ms"] > self.config.max_response_time_ms:
                self.alerts.append(
                    {
                        "level": "medium",
                        "metric": "api_response_time",
                        "message": f"Average API response time {result['avg_response_time_ms']:.1f}ms exceeds threshold {self.config.max_response_time_ms}ms",
                        "value": result["avg_response_time_ms"],
                        "threshold": self.config.max_response_time_ms,
                    }
                )

            logger.info(
                f"API call benchmark completed - avg response time: {result['avg_response_time_ms']:.1f}ms"
            )
        except Exception as e:
            logger.error(f"API call benchmark failed: {e}")
            result["error"] = str(e)
            result["status"] = "failed"

        return result

    async def _benchmark_memory_usage(self) -> Dict[str, Any]:
        """Benchmark memory usage patterns"""
        result = {
            "peak_memory_mb": 0,
            "avg_memory_mb": 0,
            "memory_samples": [],
            "memory_leaks_detected": False,
            "status": "completed",
        }

        try:
            # Monitor memory usage over time
            process = psutil.Process()
            samples = []

            # Sample memory usage
            for i in range(60):  # 1 minute of sampling
                memory_mb = process.memory_info().rss / 1024 / 1024
                samples.append(memory_mb)
                await asyncio.sleep(1)

            # Analyze memory patterns
            result["memory_samples"] = samples
            result["peak_memory_mb"] = max(samples)
            result["avg_memory_mb"] = statistics.mean(samples)

            # Check for memory leaks (increasing trend)
            if len(samples) >= 10:
                first_half = samples[: len(samples) // 2]
                second_half = samples[len(samples) // 2 :]

                first_avg = statistics.mean(first_half)
                second_avg = statistics.mean(second_half)

                # If memory increased by more than 10% over time, flag as potential leak
                if second_avg > first_avg * 1.1:
                    result["memory_leaks_detected"] = True
                    self.alerts.append(
                        {
                            "level": "medium",
                            "metric": "memory_usage",
                            "message": f"Potential memory leak detected: {first_avg:.1f}MB → {second_avg:.1f}MB",
                            "details": {
                                "trend": "increasing",
                                "increase_percent": (
                                    (second_avg / first_avg - 1) * 100
                                ),
                            },
                        }
                    )

            # Check memory threshold
            if result["peak_memory_mb"] > self.config.max_memory_mb:
                self.alerts.append(
                    {
                        "level": "high",
                        "metric": "peak_memory",
                        "message": f"Peak memory usage {result['peak_memory_mb']:.1f}MB exceeds threshold {self.config.max_memory_mb}MB",
                        "value": result["peak_memory_mb"],
                        "threshold": self.config.max_memory_mb,
                    }
                )

            logger.info(
                f"Memory usage benchmark completed - peak memory: {result['peak_memory_mb']:.1f}MB"
            )
        except Exception as e:
            logger.error(f"Memory usage benchmark failed: {e}")
            result["error"] = str(e)
            result["status"] = "failed"

        return result

    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive system metrics"""
        try:
            process = psutil.Process()

            return {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "memory_used_mb": psutil.virtual_memory().used / 1024 / 1024,
                "memory_available_mb": psutil.virtual_memory().available / 1024 / 1024,
                "disk_usage_percent": psutil.disk_usage("/").percent,
                "process_memory_mb": process.memory_info().rss / 1024 / 1024,
                "process_cpu_percent": process.cpu_percent(interval=1),
                "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
                "network_connections": len(psutil.net_connections()),
                "open_files": len(process.open_files())
                if hasattr(process, "open_files")
                else None,
            }
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {"error": str(e)}

    def _compare_against_baseline(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Compare current results against baseline"""
        comparison = {
            "baseline_available": bool(self.baseline_data),
            "regressions": [],
            "improvements": [],
            "status": "completed",
        }

        if not self.baseline_data:
            return comparison

        try:
            # Compare key metrics
            comparisons = [
                ("trade_execution.avg_latency_ms", "trade_latency", "lower"),
                ("trade_execution.throughput_tps", "trade_throughput", "higher"),
                ("wallet_scanning.avg_scan_time_ms", "wallet_scan_time", "lower"),
                ("api_calls.avg_response_time_ms", "api_response_time", "lower"),
                ("memory_usage.avg_memory_mb", "memory_usage", "lower"),
            ]

            for result_path, metric_name, direction in comparisons:
                current_value = self._get_nested_value(results, result_path.split("."))
                baseline_value = self._get_nested_value(
                    self.baseline_data, result_path.split(".")
                )

                if current_value is not None and baseline_value is not None:
                    if direction == "lower" and current_value > baseline_value * (
                        1 + self.config.baseline_update_threshold
                    ):
                        comparison["regressions"].append(
                            {
                                "metric": metric_name,
                                "current": current_value,
                                "baseline": baseline_value,
                                "change_percent": ((current_value / baseline_value) - 1)
                                * 100,
                                "direction": "worse",
                            }
                        )
                    elif direction == "higher" and current_value < baseline_value * (
                        1 - self.config.baseline_update_threshold
                    ):
                        comparison["regressions"].append(
                            {
                                "metric": metric_name,
                                "current": current_value,
                                "baseline": baseline_value,
                                "change_percent": ((current_value / baseline_value) - 1)
                                * 100,
                                "direction": "worse",
                            }
                        )
                    elif (
                        abs(current_value / baseline_value - 1)
                        > self.config.baseline_update_threshold
                    ):
                        if (
                            direction == "lower" and current_value < baseline_value
                        ) or (direction == "higher" and current_value > baseline_value):
                            comparison["improvements"].append(
                                {
                                    "metric": metric_name,
                                    "current": current_value,
                                    "baseline": baseline_value,
                                    "change_percent": (
                                        (current_value / baseline_value) - 1
                                    )
                                    * 100,
                                    "direction": "better",
                                }
                            )

            # Generate alerts for regressions
            if comparison["regressions"]:
                self.alerts.append(
                    {
                        "level": "medium",
                        "title": "Performance Regressions Detected",
                        "message": f"Found {len(comparison['regressions'])} performance regressions vs baseline",
                        "details": comparison["regressions"],
                    }
                )

        except Exception as e:
            logger.error(f"Error comparing against baseline: {e}")
            comparison["error"] = str(e)
            comparison["status"] = "failed"

        return comparison

    def _get_nested_value(
        self, data: Dict[str, Any], keys: List[str]
    ) -> Optional[float]:
        """Get nested value from dictionary"""
        try:
            current = data
            for key in keys:
                if isinstance(current, dict):
                    current = current[key]
                else:
                    return None
            return float(current) if current is not None else None
        except (KeyError, ValueError, TypeError):
            return None

    async def _save_results(self, results: Dict[str, Any]) -> None:
        """Save benchmark results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"monitoring/performance/benchmark_{timestamp}.json"

        # Ensure directory exists
        Path("monitoring/performance").mkdir(parents=True, exist_ok=True)

        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"💾 Performance benchmark results saved to {results_file}")

        # Also save latest results
        latest_file = "monitoring/performance/latest_benchmark.json"
        with open(latest_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

    async def _update_baseline_if_improved(self, results: Dict[str, Any]) -> None:
        """Update baseline if performance improved significantly"""
        comparison = results.get("comparison", {})

        if not comparison.get("improvements"):
            return

        # Check if all key metrics improved
        key_improvements = [
            imp
            for imp in comparison["improvements"]
            if imp["metric"] in ["trade_latency", "trade_throughput", "memory_usage"]
        ]

        if len(key_improvements) >= 2:  # At least 2 key improvements
            logger.info(
                "🎉 Significant performance improvements detected, updating baseline"
            )

            # Create new baseline
            new_baseline = {
                "updated_at": datetime.now().isoformat(),
                "updated_from": self.baseline_data.get("updated_at", "initial"),
                "scenarios": results.get("scenarios", {}),
                "reason": "automatic_update_due_to_improvements",
            }

            # Save new baseline
            Path(self.config.baseline_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.config.baseline_file, "w") as f:
                json.dump(new_baseline, f, indent=2, default=str)

            logger.info(f"✅ Baseline updated at {self.config.baseline_file}")


async def run_performance_benchmark() -> Dict[str, Any]:
    """Run the performance benchmark"""
    benchmark = PerformanceBenchmark()
    results = await benchmark.run_full_benchmark()

    # Log summary
    scenarios = results.get("scenarios", {})
    comparison = results.get("comparison", {})

    logger.info("📊 Performance Benchmark Summary:")
    logger.info(f"   Scenarios run: {len(scenarios)}")
    logger.info(f"   Regressions: {len(comparison.get('regressions', []))}")
    logger.info(f"   Improvements: {len(comparison.get('improvements', []))}")

    return results


if __name__ == "__main__":
    # Run performance benchmark
    asyncio.run(run_performance_benchmark())
