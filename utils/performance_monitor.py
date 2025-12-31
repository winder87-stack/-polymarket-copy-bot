"""
Performance monitoring utilities for high-performance wallet scanning
"""

import time
import statistics
from typing import Dict, Any
from datetime import datetime
from collections import deque


class PerformanceMonitor:
    """
    Real-time performance monitoring for wallet scanning operations
    """

    def __init__(self, window_size: int = 100) -> None:
        """
        Initialize performance monitor

        Args:
            window_size: Number of samples to keep for moving averages
        """
        self.window_size = window_size
        self.scan_durations = deque(maxlen=window_size)
        self.wallet_processing_times = deque(maxlen=window_size)
        self.api_call_times = deque(maxlen=window_size)
        self.memory_snapshots = deque(maxlen=window_size)
        self.start_time = time.time()
        self.total_wallets_processed = 0
        self.total_scans = 0

    def record_scan_duration(self, duration: float) -> None:
        """Record scan duration in seconds"""
        self.scan_durations.append(duration)
        self.total_scans += 1

    def record_wallet_processing_time(self, duration: float) -> None:
        """Record wallet processing time in seconds"""
        self.wallet_processing_times.append(duration)
        self.total_wallets_processed += 1

    def record_api_call_time(self, duration: float) -> None:
        """Record API call duration in seconds"""
        self.api_call_times.append(duration)

    def record_memory_usage(self, memory_mb: float) -> None:
        """Record memory usage in MB"""
        self.memory_snapshots.append(memory_mb)

    def get_scan_metrics(self) -> Dict[str, float]:
        """Get scan performance metrics"""
        if not self.scan_durations:
            return {}

        durations = list(self.scan_durations)
        return {
            "avg_scan_duration": statistics.mean(durations),
            "min_scan_duration": min(durations),
            "max_scan_duration": max(durations),
            "scan_count": self.total_scans,
            "wallets_per_second": self.total_wallets_processed
            / (time.time() - self.start_time)
            if self.total_wallets_processed > 0
            else 0,
        }

    def get_wallet_metrics(self) -> Dict[str, float]:
        """Get wallet processing metrics"""
        if not self.wallet_processing_times:
            return {}

        times = list(self.wallet_processing_times)
        return {
            "avg_wallet_time": statistics.mean(times),
            "min_wallet_time": min(times),
            "max_wallet_time": max(times),
            "p95_wallet_time": sorted(times)[int(len(times) * 0.95)]
            if len(times) > 1
            else times[0],
            "total_wallets": self.total_wallets_processed,
        }

    def get_api_metrics(self) -> Dict[str, float]:
        """Get API performance metrics"""
        if not self.api_call_times:
            return {}

        times = list(self.api_call_times)
        return {
            "avg_api_time": statistics.mean(times),
            "min_api_time": min(times),
            "max_api_time": max(times),
            "api_call_count": len(times),
        }

    def get_memory_metrics(self) -> Dict[str, float]:
        """Get memory usage metrics"""
        if not self.memory_snapshots:
            return {}

        memory = list(self.memory_snapshots)
        return {
            "current_memory_mb": memory[-1] if memory else 0,
            "avg_memory_mb": statistics.mean(memory),
            "max_memory_mb": max(memory),
            "min_memory_mb": min(memory),
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all performance metrics"""
        return {
            "scan_metrics": self.get_scan_metrics(),
            "wallet_metrics": self.get_wallet_metrics(),
            "api_metrics": self.get_api_metrics(),
            "memory_metrics": self.get_memory_metrics(),
            "uptime_seconds": time.time() - self.start_time,
            "timestamp": datetime.utcnow().isoformat(),
        }


class AsyncPerformanceMonitor(PerformanceMonitor):
    """
    Async version of PerformanceMonitor for async/await patterns
    """

    async def record_scan_duration_async(self, duration: float):
        """Async scan duration recording"""
        self.record_scan_duration(duration)

    async def record_wallet_processing_time_async(self, duration: float):
        """Async wallet processing time recording"""
        self.record_wallet_processing_time(duration)

    async def record_api_call_time_async(self, duration: float):
        """Async API call time recording"""
        self.record_api_call_time(duration)

    async def record_memory_usage_async(self, memory_mb: float):
        """Async memory usage recording"""
        self.record_memory_usage(memory_mb)

    async def get_all_metrics_async(self) -> Dict[str, Any]:
        """Async metrics retrieval"""
        return self.get_all_metrics()


# Global performance monitor instance
PERFORMANCE_MONITOR = PerformanceMonitor(window_size=1000)
