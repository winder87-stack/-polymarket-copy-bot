#!/usr/bin/env python3
"""
Production Health Check Script
==============================

Comprehensive health check for the Polymarket Copy Trading Bot
in production environments. Checks all critical systems and
provides detailed status reporting.

Usage:
    python scripts/health_check.py [--ci] [--verbose] [--json]

Options:
    --ci        CI/CD mode - exit with code on failure
    --verbose   Detailed output
    --json      JSON output format
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

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings

logger = logging.getLogger(__name__)

class HealthChecker:
    """Comprehensive health checker for the trading bot"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {}
        self.warnings = []
        self.errors = []

    async def run_full_check(self) -> Dict[str, Any]:
        """Run comprehensive health check"""
        logger.info("🏥 Starting comprehensive health check")

        start_time = datetime.now()

        # Run all health checks
        checks = [
            ("configuration", self._check_configuration()),
            ("dependencies", self._check_dependencies()),
            ("network", self._check_network_connectivity()),
            ("wallet", self._check_wallet_status()),
            ("service", self._check_service_status()),
            ("performance", self._check_performance_metrics()),
            ("security", self._check_security_status()),
            ("monitoring", self._check_monitoring_system()),
        ]

        # Execute checks concurrently where possible
        for check_name, check_coro in checks:
            try:
                if self.verbose:
                    logger.info(f"🔍 Checking {check_name}...")
                result = await check_coro
                self.results[check_name] = result

                if result.get("status") == "error":
                    self.errors.append(f"{check_name}: {result.get('message', 'Unknown error')}")
                elif result.get("status") == "warning":
                    self.warnings.append(f"{check_name}: {result.get('message', 'Unknown warning')}")

                if self.verbose:
                    logger.info(f"✅ {check_name} check completed")

            except Exception as e:
                logger.error(f"❌ {check_name} check failed: {e}")
                self.results[check_name] = {
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                self.errors.append(f"{check_name}: {str(e)}")

        # Calculate overall health
        overall_health = self._calculate_overall_health()

        # Prepare final report
        report = {
            "timestamp": start_time.isoformat(),
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
            "overall_health": overall_health,
            "results": self.results,
            "warnings": self.warnings,
            "errors": self.errors,
            "recommendations": self._generate_recommendations()
        }

        logger.info(f"🏥 Health check completed: {overall_health.upper()}")
        return report

    async def _check_configuration(self) -> Dict[str, Any]:
        """Check configuration validity"""
        result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Test configuration loading
            test_settings = settings

            # Validate critical settings
            test_settings.validate_critical_settings()

            # Check required files exist
            required_files = [
                ".env",
                "config/settings.py",
                "config/wallets.json",
                "requirements.txt"
            ]

            missing_files = []
            for file_path in required_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)

            if missing_files:
                result["status"] = "error"
                result["message"] = f"Missing required files: {', '.join(missing_files)}"
            else:
                result["message"] = "All configuration files present and valid"

        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Configuration error: {str(e)}"

        return result

    async def _check_dependencies(self) -> Dict[str, Any]:
        """Check Python dependencies"""
        result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Check critical imports
            critical_imports = [
                "web3",
                "polymarket",
                "telegram",
                "psutil",
                "aiohttp"
            ]

            failed_imports = []
            for module in critical_imports:
                try:
                    __import__(module)
                except ImportError:
                    failed_imports.append(module)

            if failed_imports:
                result["status"] = "error"
                result["message"] = f"Missing critical dependencies: {', '.join(failed_imports)}"
            else:
                result["message"] = "All critical dependencies available"

        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Dependency check failed: {str(e)}"

        return result

    async def _check_network_connectivity(self) -> Dict[str, Any]:
        """Check network connectivity to required services"""
        result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {}
        }

        services_to_check = [
            ("polygon_rpc", settings.network.polygon_rpc_url, 443),
            ("polymarket_clob", settings.network.clob_host.replace("https://", ""), 443),
        ]

        all_healthy = True

        for service_name, host, port in services_to_check:
            try:
                # Simple connectivity check
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result_check = sock.connect_ex((host.replace("https://", "").replace("http://", ""), port))
                sock.close()

                if result_check == 0:
                    result["services"][service_name] = "connected"
                else:
                    result["services"][service_name] = "failed"
                    all_healthy = False

            except Exception as e:
                result["services"][service_name] = f"error: {str(e)}"
                all_healthy = False

        if not all_healthy:
            result["status"] = "error"
            result["message"] = "Some network services unreachable"
        else:
            result["message"] = "All network services reachable"

        return result

    async def _check_wallet_status(self) -> Dict[str, Any]:
        """Check wallet connectivity and balance"""
        result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }

        try:
            from web3 import Web3

            # Connect to RPC
            w3 = Web3(Web3.HTTPProvider(settings.network.polygon_rpc_url))

            if not w3.is_connected():
                result["status"] = "error"
                result["message"] = "Cannot connect to Polygon RPC"
                return result

            # Check wallet balance
            balance_wei = w3.eth.get_balance(settings.trading.wallet_address)
            balance_usdc = balance_wei / 10**18  # Convert to POL

            result["wallet_address"] = settings.trading.wallet_address
            result["balance_pol"] = balance_usdc
            result["current_block"] = w3.eth.block_number

            # Check minimum balance (0.1 POL for gas)
            if balance_usdc < 0.1:
                result["status"] = "warning"
                result["message"] = f"Low wallet balance: {balance_usdc:.4f} POL (recommended: >0.1 POL)"
            else:
                result["message"] = f"Wallet balance healthy: {balance_usdc:.4f} POL"

        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Wallet check failed: {str(e)}"

        return result

    async def _check_service_status(self) -> Dict[str, Any]:
        """Check systemd service status"""
        result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }

        try:
            import subprocess

            # Check service status
            cmd = ["systemctl", "is-active", "polymarket-bot"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            service_status = stdout.decode().strip()

            if service_status == "active":
                result["service_status"] = "running"
                result["message"] = "Service is running"
            elif service_status == "inactive":
                result["service_status"] = "stopped"
                result["status"] = "warning"
                result["message"] = "Service is stopped"
            else:
                result["service_status"] = service_status
                result["status"] = "error"
                result["message"] = f"Service status: {service_status}"

        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Service check failed: {str(e)}"

        return result

    async def _check_performance_metrics(self) -> Dict[str, Any]:
        """Check current performance metrics"""
        result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }

        try:
            import psutil

            process = psutil.Process()

            # Get system metrics
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent(interval=1)

            result["memory_mb"] = memory_mb
            result["cpu_percent"] = cpu_percent

            # Check thresholds
            issues = []
            if memory_mb > 512:  # 512MB limit
                issues.append(f"High memory usage: {memory_mb:.1f}MB")
            if cpu_percent > 80:  # 80% CPU limit
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")

            if issues:
                result["status"] = "warning"
                result["message"] = "; ".join(issues)
            else:
                result["message"] = f"Performance healthy (CPU: {cpu_percent:.1f}%, Memory: {memory_mb:.1f}MB)"

        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Performance check failed: {str(e)}"

        return result

    async def _check_security_status(self) -> Dict[str, Any]:
        """Check basic security status"""
        result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }

        issues = []

        try:
            # Check .env file permissions
            if os.path.exists(".env"):
                stat_info = os.stat(".env")
                permissions = oct(stat_info.st_mode)[-3:]
                if permissions != "600":
                    issues.append(f"Insecure .env permissions: {permissions} (should be 600)")

            # Check for obvious security issues
            env_file = Path(".env")
            if env_file.exists():
                content = env_file.read_text()
                if "PRIVATE_KEY" in content and "0x" in content:
                    # This is expected, but ensure it's not world-readable
                    pass

            # Check if running as root (not recommended)
            if os.geteuid() == 0:
                issues.append("Running as root - not recommended for security")

        except Exception as e:
            issues.append(f"Security check error: {str(e)}")

        if issues:
            result["status"] = "warning"
            result["message"] = "; ".join(issues)
        else:
            result["message"] = "Security checks passed"

        return result

    async def _check_monitoring_system(self) -> Dict[str, Any]:
        """Check monitoring system status"""
        result = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Check if monitoring components exist
            monitoring_components = [
                "monitoring/monitor_all.py",
                "monitoring/security_scanner.py",
                "monitoring/performance_benchmark.py"
            ]

            missing_components = []
            for component in monitoring_components:
                if not os.path.exists(component):
                    missing_components.append(component)

            if missing_components:
                result["status"] = "warning"
                result["message"] = f"Missing monitoring components: {', '.join(missing_components)}"
            else:
                result["message"] = "Monitoring system components present"

        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Monitoring check failed: {str(e)}"

        return result

    def _calculate_overall_health(self) -> str:
        """Calculate overall health status"""
        if self.errors:
            return "critical"
        elif self.warnings:
            return "warning"
        else:
            return "healthy"

    def _generate_recommendations(self) -> List[str]:
        """Generate health check recommendations"""
        recommendations = []

        if self.errors:
            recommendations.append("🚨 Address critical errors immediately")

        if self.warnings:
            recommendations.append("⚠️ Review and address warnings")

        # Specific recommendations based on results
        if "configuration" in self.results and self.results["configuration"].get("status") == "error":
            recommendations.append("🔧 Fix configuration issues before proceeding")

        if "network" in self.results and self.results["network"].get("status") == "error":
            recommendations.append("🌐 Resolve network connectivity issues")

        if "wallet" in self.results and self.results["wallet"].get("status") == "error":
            recommendations.append("💰 Check wallet configuration and balance")

        if not recommendations:
            recommendations.append("✅ System health is good")

        return recommendations

async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Production Health Check")
    parser.add_argument("--ci", action="store_true", help="CI mode - exit with code")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="JSON output format")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        checker = HealthChecker(verbose=args.verbose)
        report = await checker.run_full_check()

        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            # Pretty console output
            health_emoji = {
                "healthy": "✅",
                "warning": "⚠️",
                "critical": "🚨"
            }

            print(f"\n{health_emoji.get(report['overall_health'], '❓')} Health Check Results")
            print("=" * 50)
            print(f"Status: {report['overall_health'].upper()}")
            print(f"Duration: {report['duration_seconds']:.1f}s")
            print(f"Timestamp: {report['timestamp'][:19].replace('T', ' ')}")

            if report['errors']:
                print(f"\n🚨 Errors ({len(report['errors'])}):")
                for error in report['errors']:
                    print(f"  • {error}")

            if report['warnings']:
                print(f"\n⚠️ Warnings ({len(report['warnings'])}):")
                for warning in report['warnings']:
                    print(f"  • {warning}")

            if report['recommendations']:
                print(f"\n💡 Recommendations:")
                for rec in report['recommendations']:
                    print(f"  • {rec}")

        # Exit codes for CI
        if args.ci:
            if report['overall_health'] == "critical":
                sys.exit(2)
            elif report['overall_health'] == "warning":
                sys.exit(1)
            else:
                sys.exit(0)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        if args.ci:
            sys.exit(2)
        else:
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
