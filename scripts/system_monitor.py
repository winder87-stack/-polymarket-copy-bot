#!/usr/bin/env python3
"""
System Metrics Monitor for Polymarket Copy Bot

Provides comprehensive system-level monitoring including:
- CPU usage and load averages
- Memory utilization and swap
- Disk I/O and space monitoring
- Network interface statistics
- File descriptor usage
- Process tree monitoring
"""

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import psutil

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System metrics snapshot"""

    timestamp: datetime
    cpu_percent: float
    cpu_load_1m: float
    cpu_load_5m: float
    cpu_load_15m: float
    memory_percent: float
    memory_used_gb: float
    memory_available_gb: float
    swap_percent: float
    swap_used_gb: float
    disk_usage_percent: float
    disk_used_gb: float
    disk_free_gb: float
    disk_read_mb: float
    disk_write_mb: float
    network_rx_mb: float
    network_tx_mb: float
    file_descriptors_used: int
    file_descriptors_limit: int
    process_count: int
    thread_count: int
    uptime_seconds: int


@dataclass
class ProcessMetrics:
    """Process-specific metrics"""

    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    memory_rss_mb: float
    memory_vms_mb: float
    threads: int
    file_descriptors: int
    connections: int
    status: str
    create_time: float
    cmdline: List[str]


class SystemMonitor:
    """Comprehensive system monitoring"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.metrics_history: List[SystemMetrics] = []
        self.max_history = 1000
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Previous values for rate calculations
        self.prev_disk_io = psutil.disk_io_counters()
        self.prev_net_io = psutil.net_io_counters()

    def start_monitoring(self, interval: float = 5.0) -> None:
        """Start continuous monitoring"""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, args=(interval,), daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"System monitoring started with {interval}s interval")

    def stop_monitoring(self) -> None:
        """Stop monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("System monitoring stopped")

    def get_current_metrics(self) -> SystemMetrics:
        """Get current system metrics snapshot"""
        return self._collect_system_metrics()

    def get_process_metrics(self, process_name: str = "python") -> List[ProcessMetrics]:
        """Get metrics for specific processes"""
        metrics = []

        for proc in psutil.process_iter(
            [
                "pid",
                "name",
                "cpu_percent",
                "memory_percent",
                "memory_info",
                "num_threads",
                "status",
                "create_time",
            ]
        ):
            try:
                if process_name.lower() in proc.info["name"].lower():
                    # Get additional process info
                    try:
                        cmdline = proc.cmdline()
                        num_fds = proc.num_fds() if hasattr(proc, "num_fds") else 0
                        connections = len(proc.connections())
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        cmdline = []
                        num_fds = 0
                        connections = 0

                    mem_info = proc.info["memory_info"]
                    metrics.append(
                        ProcessMetrics(
                            pid=proc.info["pid"],
                            name=proc.info["name"],
                            cpu_percent=proc.info["cpu_percent"] or 0.0,
                            memory_percent=proc.info["memory_percent"] or 0.0,
                            memory_rss_mb=mem_info.rss / (1024 * 1024) if mem_info else 0.0,
                            memory_vms_mb=mem_info.vms / (1024 * 1024) if mem_info else 0.0,
                            threads=proc.info["num_threads"] or 0,
                            file_descriptors=num_fds,
                            connections=connections,
                            status=proc.info["status"] or "unknown",
                            create_time=proc.info["create_time"] or 0.0,
                            cmdline=cmdline,
                        )
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return metrics

    def get_metrics_history(self, minutes: int = 60) -> List[SystemMetrics]:
        """Get metrics history for specified time period"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [m for m in self.metrics_history if m.timestamp > cutoff_time]

    def get_resource_alerts(self) -> Dict[str, str]:
        """Check for resource alerts based on thresholds"""
        alerts = {}
        metrics = self.get_current_metrics()

        # CPU alerts
        if metrics.cpu_percent > 90:
            alerts["cpu"] = f"CRITICAL: CPU usage at {metrics.cpu_percent:.1f}%"
        elif metrics.cpu_percent > 80:
            alerts["cpu"] = f"WARNING: CPU usage at {metrics.cpu_percent:.1f}%"

        # Memory alerts
        if metrics.memory_percent > 95:
            alerts["memory"] = f"CRITICAL: Memory usage at {metrics.memory_percent:.1f}%"
        elif metrics.memory_percent > 85:
            alerts["memory"] = f"WARNING: Memory usage at {metrics.memory_percent:.1f}%"

        # Disk alerts
        if metrics.disk_usage_percent > 95:
            alerts["disk"] = f"CRITICAL: Disk usage at {metrics.disk_usage_percent:.1f}%"
        elif metrics.disk_usage_percent > 90:
            alerts["disk"] = f"WARNING: Disk usage at {metrics.disk_usage_percent:.1f}%"

        # File descriptor alerts
        if metrics.file_descriptors_used / metrics.file_descriptors_limit > 0.9:
            alerts["fds"] = (
                f"WARNING: File descriptors at {metrics.file_descriptors_used}/{metrics.file_descriptors_limit}"
            )

        return alerts

    def _monitoring_loop(self, interval: float) -> None:
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                metrics = self._collect_system_metrics()
                self.metrics_history.append(metrics)

                # Maintain history size
                if len(self.metrics_history) > self.max_history:
                    self.metrics_history = self.metrics_history[-self.max_history :]

                # Check for alerts
                alerts = self.get_resource_alerts()
                if alerts:
                    for alert_type, message in alerts.items():
                        logger.warning(f"SYSTEM ALERT: {message}")

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            time.sleep(interval)

    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect comprehensive system metrics"""
        timestamp = datetime.now()

        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        load_avg = os.getloadavg()

        # Memory metrics
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disk metrics
        disk = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()

        # Network metrics
        net_io = psutil.net_io_counters()

        # File descriptors
        try:
            with open("/proc/sys/fs/file-nr", "r") as f:
                fd_line = f.read().strip().split()
                fds_used = int(fd_line[0])
                fds_limit = int(fd_line[2])
        except (FileNotFoundError, ValueError, IndexError):
            fds_used = 0
            fds_limit = 0

        # Process counts
        process_count = len(psutil.pids())
        thread_count = sum(1 for p in psutil.process_iter(["num_threads"]) if p.info["num_threads"])

        # Calculate rates (MB/s)
        time_diff = 1.0  # Assuming 1 second interval
        disk_read_mb = (
            (disk_io.read_bytes - self.prev_disk_io.read_bytes) / (1024 * 1024) / time_diff
            if self.prev_disk_io
            else 0
        )
        disk_write_mb = (
            (disk_io.write_bytes - self.prev_disk_io.write_bytes) / (1024 * 1024) / time_diff
            if self.prev_disk_io
            else 0
        )

        network_rx_mb = (
            (net_io.bytes_recv - self.prev_net_io.bytes_recv) / (1024 * 1024) / time_diff
            if self.prev_net_io
            else 0
        )
        network_tx_mb = (
            (net_io.bytes_sent - self.prev_net_io.bytes_sent) / (1024 * 1024) / time_diff
            if self.prev_net_io
            else 0
        )

        # Update previous values
        self.prev_disk_io = disk_io
        self.prev_net_io = net_io

        return SystemMetrics(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            cpu_load_1m=load_avg[0],
            cpu_load_5m=load_avg[1],
            cpu_load_15m=load_avg[2],
            memory_percent=mem.percent,
            memory_used_gb=mem.used / (1024**3),
            memory_available_gb=mem.available / (1024**3),
            swap_percent=swap.percent,
            swap_used_gb=swap.used / (1024**3),
            disk_usage_percent=disk.percent,
            disk_used_gb=disk.used / (1024**3),
            disk_free_gb=disk.free / (1024**3),
            disk_read_mb=disk_read_mb,
            disk_write_mb=disk_write_mb,
            network_rx_mb=network_rx_mb,
            network_tx_mb=network_tx_mb,
            file_descriptors_used=fds_used,
            file_descriptors_limit=fds_limit,
            process_count=process_count,
            thread_count=thread_count,
            uptime_seconds=int(time.time() - psutil.boot_time()),
        )


def main():
    """CLI interface for system monitoring"""
    import argparse

    parser = argparse.ArgumentParser(description="System Monitor for Polymarket Copy Bot")
    parser.add_argument("action", choices=["snapshot", "monitor", "processes", "alerts"])
    parser.add_argument(
        "--interval", type=float, default=5.0, help="Monitoring interval in seconds"
    )
    parser.add_argument("--process", default="python", help="Process name to monitor")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    monitor = SystemMonitor()

    if args.action == "snapshot":
        metrics = monitor.get_current_metrics()
        if args.json:
            print(json.dumps(asdict(metrics), default=str, indent=2))
        else:
            print(f"System Metrics Snapshot ({metrics.timestamp}):")
            print(f"  CPU: {metrics.cpu_percent:.1f}% (Load: {metrics.cpu_load_1m:.2f})")
            print(f"  Memory: {metrics.memory_percent:.1f}% ({metrics.memory_used_gb:.1f}GB used)")
            print(f"  Disk: {metrics.disk_usage_percent:.1f}% ({metrics.disk_used_gb:.1f}GB used)")
            print(
                f"  Network: RX {metrics.network_rx_mb:.2f}MB/s, TX {metrics.network_tx_mb:.2f}MB/s"
            )
            print(
                f"  File Descriptors: {metrics.file_descriptors_used}/{metrics.file_descriptors_limit}"
            )
            print(f"  Processes: {metrics.process_count}, Threads: {metrics.thread_count}")

    elif args.action == "monitor":
        print("Starting system monitoring... (Ctrl+C to stop)")
        monitor.start_monitoring(args.interval)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping monitoring...")
            monitor.stop_monitoring()

    elif args.action == "processes":
        processes = monitor.get_process_metrics(args.process)
        if args.json:
            print(json.dumps([asdict(p) for p in processes], indent=2))
        else:
            print(f"Found {len(processes)} {args.process} processes:")
            for proc in processes:
                print(
                    f"  PID {proc.pid}: {proc.cpu_percent:.1f}% CPU, {proc.memory_percent:.1f}% MEM, {proc.threads} threads"
                )

    elif args.action == "alerts":
        alerts = monitor.get_resource_alerts()
        if args.json:
            print(json.dumps(alerts, indent=2))
        else:
            if alerts:
                print("Active Alerts:")
                for alert_type, message in alerts.items():
                    print(f"  {message}")
            else:
                print("No active alerts")


if __name__ == "__main__":
    main()
