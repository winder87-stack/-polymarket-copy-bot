#!/usr/bin/env python3
"""
Diagnostic Check Script
=======================

Advanced diagnostics for troubleshooting production issues.
Performs deep analysis of system state, logs, and performance
to identify root causes of problems.

Usage:
    python scripts/diagnostic_check.py [--component COMPONENT] [--hours HOURS] [--output FILE]
"""

import os
import sys
import json
import asyncio
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging
import re

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings

logger = logging.getLogger(__name__)

class DiagnosticChecker:
    """Advanced diagnostic checker"""

    def __init__(self):
        self.diagnostics = {}

    async def run_full_diagnostics(self, component: Optional[str] = None, hours: int = 24) -> Dict[str, Any]:
        """Run comprehensive diagnostics"""
        logger.info("🔍 Starting diagnostic analysis")

        start_time = datetime.now()
        cutoff_time = start_time - timedelta(hours=hours)

        diagnostics = {
            "timestamp": start_time.isoformat(),
            "analysis_period_hours": hours,
            "component_focus": component,
            "sections": {}
        }

        # Run diagnostic sections
        sections = [
            ("system_info", self._diagnose_system_info()),
            ("service_status", self._diagnose_service_status()),
            ("log_analysis", self._diagnose_log_analysis(cutoff_time)),
            ("performance_analysis", self._diagnose_performance_analysis(cutoff_time)),
            ("network_diagnostics", self._diagnose_network_diagnostics()),
            ("configuration_check", self._diagnose_configuration_check()),
        ]

        if component:
            # Focus on specific component
            sections = [(name, coro) for name, coro in sections if component in name]

        for section_name, section_coro in sections:
            try:
                logger.info(f"Analyzing {section_name}...")
                result = await section_coro
                diagnostics["sections"][section_name] = result
                logger.info(f"✅ {section_name} analysis completed")
            except Exception as e:
                logger.error(f"❌ {section_name} analysis failed: {e}")
                diagnostics["sections"][section_name] = {"error": str(e)}

        # Generate insights and recommendations
        diagnostics["insights"] = self._generate_insights(diagnostics)
        diagnostics["recommendations"] = self._generate_diagnostic_recommendations(diagnostics)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"🔍 Diagnostics completed in {duration:.1f}s")

        return diagnostics

    async def _diagnose_system_info(self) -> Dict[str, Any]:
        """Gather comprehensive system information"""
        info = {
            "hostname": os.uname().nodename,
            "platform": sys.platform,
            "python_version": sys.version,
            "timestamp": datetime.now().isoformat()
        }

        try:
            import psutil

            # CPU information
            info["cpu"] = {
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "usage_percent": psutil.cpu_percent(interval=1)
            }

            # Memory information
            memory = psutil.virtual_memory()
            info["memory"] = {
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "used_percent": memory.percent
            }

            # Disk information
            disk = psutil.disk_usage('/')
            info["disk"] = {
                "total_gb": disk.total / (1024**3),
                "free_gb": disk.free / (1024**3),
                "used_percent": disk.percent
            }

            # Network information
            net = psutil.net_io_counters()
            info["network"] = {
                "bytes_sent_mb": net.bytes_sent / (1024**2),
                "bytes_recv_mb": net.bytes_recv / (1024**2)
            }

        except ImportError:
            info["psutil"] = "not_available"

        return info

    async def _diagnose_service_status(self) -> Dict[str, Any]:
        """Analyze service status and recent activity"""
        status = {}

        try:
            import subprocess

            # Main service status
            result = await asyncio.create_subprocess_exec(
                "systemctl", "show", "polymarket-bot",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()

            service_info = {}
            for line in stdout.decode().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    service_info[key] = value

            status["main_service"] = {
                "active_state": service_info.get("ActiveState"),
                "sub_state": service_info.get("SubState"),
                "exec_main_pid": service_info.get("ExecMainPID"),
                "memory_current": service_info.get("MemoryCurrent"),
                "cpu_usage": service_info.get("CPUUsageNS")
            }

            # Monitoring service status
            result = await asyncio.create_subprocess_exec(
                "systemctl", "is-active", "polymarket-monitoring.timer",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            status["monitoring_service"] = stdout.decode().strip()

        except Exception as e:
            status["error"] = str(e)

        return status

    async def _diagnose_log_analysis(self, cutoff_time: datetime) -> Dict[str, Any]:
        """Analyze recent log entries for patterns and issues"""
        analysis = {
            "log_files_analyzed": [],
            "time_range": f"{cutoff_time.isoformat()} to {datetime.now().isoformat()}",
            "patterns": {}
        }

        log_files = [
            "logs/polymarket_bot.log",
            "/var/log/syslog"
        ]

        for log_file in log_files:
            if os.path.exists(log_file):
                analysis["log_files_analyzed"].append(log_file)

                try:
                    # Analyze log patterns
                    with open(log_file, 'r') as f:
                        lines = f.readlines()

                    # Filter by time (approximate)
                    recent_lines = []
                    for line in lines[-1000:]:  # Last 1000 lines
                        # Basic time filtering (this could be improved)
                        recent_lines.append(line.strip())

                    # Analyze error patterns
                    error_patterns = [
                        (r"ERROR|CRITICAL", "errors"),
                        (r"WARNING", "warnings"),
                        (r"TRADE.*EXECUTED", "successful_trades"),
                        (r"TRADE.*FAILED", "failed_trades"),
                        (r"ALERT", "alerts_sent")
                    ]

                    file_patterns = {}
                    for pattern, key in error_patterns:
                        matches = [line for line in recent_lines if re.search(pattern, line, re.IGNORECASE)]
                        file_patterns[key] = {
                            "count": len(matches),
                            "recent_examples": matches[-3:] if matches else []
                        }

                    analysis["patterns"][log_file] = file_patterns

                except Exception as e:
                    analysis["patterns"][log_file] = {"error": str(e)}

        return analysis

    async def _diagnose_performance_analysis(self, cutoff_time: datetime) -> Dict[str, Any]:
        """Analyze performance metrics and trends"""
        analysis = {
            "metrics_available": False,
            "performance_trends": {},
            "anomalies_detected": []
        }

        # Check for performance benchmark results
        perf_file = Path("monitoring/performance/latest_benchmark.json")
        if perf_file.exists():
            try:
                with open(perf_file, 'r') as f:
                    perf_data = json.load(f)

                analysis["metrics_available"] = True
                analysis["latest_benchmark"] = {
                    "timestamp": perf_data.get("timestamp"),
                    "scenarios_run": len(perf_data.get("scenarios", {})),
                    "duration_minutes": perf_data.get("duration_minutes")
                }

                # Check for performance regressions
                comparison = perf_data.get("comparison", {})
                if comparison.get("regressions"):
                    analysis["performance_trends"]["regressions"] = comparison["regressions"]
                    analysis["anomalies_detected"].extend([
                        f"Performance regression in {reg['metric']}: {reg['change_percent']:+.1f}%"
                        for reg in comparison["regressions"]
                    ])

            except Exception as e:
                analysis["performance_error"] = str(e)

        return analysis

    async def _diagnose_network_diagnostics(self) -> Dict[str, Any]:
        """Diagnose network connectivity and performance"""
        diagnostics = {
            "connectivity_tests": {},
            "latency_tests": {},
            "dns_resolution": {}
        }

        endpoints = [
            ("polygon-rpc.com", 443),
            ("clob.polymarket.com", 443),
            ("api.telegram.org", 443)
        ]

        for host, port in endpoints:
            try:
                # Connectivity test
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                start_time = time.time()
                result = sock.connect_ex((host, port))
                latency = time.time() - start_time
                sock.close()

                diagnostics["connectivity_tests"][f"{host}:{port}"] = {
                    "connected": result == 0,
                    "latency_seconds": latency
                }

            except Exception as e:
                diagnostics["connectivity_tests"][f"{host}:{port}"] = {
                    "error": str(e)
                }

        return diagnostics

    async def _diagnose_configuration_check(self) -> Dict[str, Any]:
        """Check configuration consistency and validity"""
        check = {
            "config_files": {},
            "validation_results": {},
            "security_issues": []
        }

        config_files = [
            ".env",
            "config/settings.py",
            "config/wallets.json",
            "pyproject.toml",
            "requirements.txt"
        ]

        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    stat_info = os.stat(config_file)
                    check["config_files"][config_file] = {
                        "exists": True,
                        "size_bytes": stat_info.st_size,
                        "permissions": oct(stat_info.st_mode)[-3:],
                        "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                    }

                    # Check for obvious security issues
                    if config_file == ".env":
                        if check["config_files"][config_file]["permissions"] != "600":
                            check["security_issues"].append(f"Insecure .env permissions: {check['config_files'][config_file]['permissions']}")

                except Exception as e:
                    check["config_files"][config_file] = {"error": str(e)}
            else:
                check["config_files"][config_file] = {"exists": False}

        # Validate configuration
        try:
            test_settings = settings
            test_settings.validate_critical_settings()
            check["validation_results"]["config_valid"] = True
        except Exception as e:
            check["validation_results"]["config_valid"] = False
            check["validation_results"]["config_error"] = str(e)

        return check

    def _generate_insights(self, diagnostics: Dict[str, Any]) -> List[str]:
        """Generate diagnostic insights"""
        insights = []

        # System insights
        system_info = diagnostics["sections"].get("system_info", {})
        if system_info.get("memory", {}).get("used_percent", 0) > 80:
            insights.append("High memory usage detected - consider optimizing memory usage")

        if system_info.get("cpu", {}).get("usage_percent", 0) > 80:
            insights.append("High CPU usage detected - investigate performance bottlenecks")

        # Log insights
        log_analysis = diagnostics["sections"].get("log_analysis", {})
        for log_file, patterns in log_analysis.get("patterns", {}).items():
            if patterns.get("errors", {}).get("count", 0) > 10:
                insights.append(f"High error rate in {log_file} - investigate error patterns")

        # Performance insights
        perf_analysis = diagnostics["sections"].get("performance_analysis", {})
        if perf_analysis.get("anomalies_detected"):
            insights.extend(perf_analysis["anomalies_detected"])

        # Network insights
        network_diag = diagnostics["sections"].get("network_diagnostics", {})
        for endpoint, result in network_diag.get("connectivity_tests", {}).items():
            if not result.get("connected", False):
                insights.append(f"Network connectivity issue with {endpoint}")

        if not insights:
            insights.append("No significant issues detected in diagnostic analysis")

        return insights

    def _generate_diagnostic_recommendations(self, diagnostics: Dict[str, Any]) -> List[str]:
        """Generate diagnostic recommendations"""
        recommendations = []

        # Based on insights
        insights = diagnostics.get("insights", [])
        for insight in insights:
            if "memory" in insight.lower():
                recommendations.append("Optimize memory usage - consider implementing memory pooling or reducing data retention")
            elif "cpu" in insight.lower():
                recommendations.append("Investigate CPU bottlenecks - profile code performance and optimize hot paths")
            elif "error" in insight.lower():
                recommendations.append("Review error patterns - implement better error handling and logging")
            elif "network" in insight.lower():
                recommendations.append("Check network configuration - consider using multiple RPC endpoints for redundancy")
            elif "performance" in insight.lower():
                recommendations.append("Address performance regressions - review recent code changes and optimize algorithms")

        # Configuration recommendations
        config_check = diagnostics["sections"].get("configuration_check", {})
        if config_check.get("security_issues"):
            recommendations.append("Fix configuration security issues - ensure proper file permissions")

        validation = config_check.get("validation_results", {})
        if not validation.get("config_valid", True):
            recommendations.append("Fix configuration validation errors - check environment variables and settings")

        if not recommendations:
            recommendations.append("System diagnostics show healthy state - continue monitoring")

        return recommendations

async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Diagnostic Check Script")
    parser.add_argument("--component", help="Focus on specific component")
    parser.add_argument("--hours", type=int, default=24, help="Analysis time window in hours")
    parser.add_argument("--output", help="Output file (default: stdout)")
    parser.add_argument("--json", action="store_true", help="JSON output format")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        checker = DiagnosticChecker()
        results = await checker.run_full_diagnostics(
            component=args.component,
            hours=args.hours
        )

        output = json.dumps(results, indent=2, default=str) if args.json else str(results)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            logger.info(f"Diagnostics saved to {args.output}")
        else:
            print(output)

    except Exception as e:
        logger.error(f"Diagnostic check failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
