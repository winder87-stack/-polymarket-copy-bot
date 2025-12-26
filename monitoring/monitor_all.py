#!/usr/bin/env python3
"""
Comprehensive Monitoring Runner
================================

Orchestrates all monitoring activities:
- Security scanning
- Performance benchmarking
- Alert system health checks
- Report generation
- Alert notifications

Can be run manually or scheduled via cron/systemd.
"""

import asyncio
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
import sys

from monitoring.monitoring_config import monitoring_config
from monitoring.security_scanner import run_daily_security_scan
from monitoring.performance_benchmark import run_performance_benchmark
from monitoring.alert_health_checker import run_alert_health_check

logger = logging.getLogger(__name__)

class MonitoringOrchestrator:
    """Orchestrates all monitoring activities"""

    def __init__(self):
        self.config = monitoring_config
        self.results = {}

    async def run_all_checks(self, check_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run all monitoring checks"""
        logger.info("🚀 Starting comprehensive monitoring run")

        start_time = datetime.now()
        results = {
            "timestamp": start_time.isoformat(),
            "checks_run": [],
            "summary": {},
            "alerts": [],
            "recommendations": []
        }

        # Determine which checks to run
        if check_types is None:
            check_types = []
            if self.config.security.daily_scan_enabled:
                check_types.append("security")
            if self.config.performance.benchmark_enabled:
                check_types.append("performance")
            if self.config.alerts.health_check_enabled:
                check_types.append("alerts")

        # Run security scan
        if "security" in check_types:
            logger.info("🔒 Running security scan...")
            try:
                security_results = await run_daily_security_scan()
                results["security"] = security_results
                results["checks_run"].append("security")
                results["alerts"].extend(security_results.get("alerts", []))
                logger.info("✅ Security scan completed")
            except Exception as e:
                logger.error(f"❌ Security scan failed: {e}")
                results["security"] = {"error": str(e), "status": "failed"}

        # Run performance benchmark
        if "performance" in check_types:
            logger.info("📊 Running performance benchmark...")
            try:
                perf_results = await run_performance_benchmark()
                results["performance"] = perf_results
                results["checks_run"].append("performance")
                results["alerts"].extend(perf_results.get("alerts", []))
                logger.info("✅ Performance benchmark completed")
            except Exception as e:
                logger.error(f"❌ Performance benchmark failed: {e}")
                results["performance"] = {"error": str(e), "status": "failed"}

        # Run alert health check
        if "alerts" in check_types:
            logger.info("🚨 Running alert health check...")
            try:
                alert_results = await run_alert_health_check()
                results["alerts_health"] = alert_results
                results["checks_run"].append("alerts")
                results["alerts"].extend(alert_results.get("issues", []))
                logger.info("✅ Alert health check completed")
            except Exception as e:
                logger.error(f"❌ Alert health check failed: {e}")
                results["alerts_health"] = {"error": str(e), "status": "failed"}

        # Generate summary
        results["summary"] = self._generate_summary(results)

        # Generate recommendations
        results["recommendations"] = self._generate_recommendations(results)

        # Save results
        await self._save_results(results)

        # Send alerts if there are issues
        await self._send_monitoring_alerts(results)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"🚀 Comprehensive monitoring completed in {duration:.1f}s")

        return results

    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall monitoring summary"""
        summary = {
            "checks_completed": len(results.get("checks_run", [])),
            "total_alerts": len(results.get("alerts", [])),
            "overall_status": "healthy",
            "critical_issues": 0,
            "high_issues": 0,
            "medium_issues": 0
        }

        # Count alerts by severity
        for alert in results.get("alerts", []):
            level = alert.get("level", "info").lower()
            if level == "critical":
                summary["critical_issues"] += 1
            elif level == "high":
                summary["high_issues"] += 1
            elif level == "medium":
                summary["medium_issues"] += 1

        # Determine overall status
        if summary["critical_issues"] > 0:
            summary["overall_status"] = "critical"
        elif summary["high_issues"] > 0:
            summary["overall_status"] = "high"
        elif summary["medium_issues"] > 0:
            summary["overall_status"] = "medium"
        elif summary["total_alerts"] > 0:
            summary["overall_status"] = "info"

        return summary

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on monitoring results"""
        recommendations = []

        summary = results.get("summary", {})

        # Check for critical issues
        if summary.get("critical_issues", 0) > 0:
            recommendations.append("🚨 Address critical issues immediately - system may be compromised or unstable")

        # Check security issues
        security = results.get("security", {})
        if security.get("summary", {}).get("critical_issues", 0) > 0:
            recommendations.append("🔒 Fix critical security vulnerabilities before continuing")

        # Check performance issues
        performance = results.get("performance", {})
        regressions = performance.get("comparison", {}).get("regressions", [])
        if regressions:
            recommendations.append("📊 Investigate performance regressions and optimize bottlenecks")

        # Check alert system issues
        alerts_health = results.get("alerts_health", {})
        if alerts_health.get("overall_health") in ["critical", "degraded"]:
            recommendations.append("🚨 Fix alert system issues to ensure proper monitoring")

        # General recommendations
        if not recommendations:
            recommendations.append("✅ All monitoring checks passed - system is healthy")

        return recommendations

    async def _save_results(self, results: Dict[str, Any]) -> None:
        """Save monitoring results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"monitoring/reports/monitoring_run_{timestamp}.json"

        # Ensure directory exists
        import os
        os.makedirs("monitoring/reports", exist_ok=True)

        with open(results_file, 'w') as f:
            # Convert to JSON-serializable format
            json_results = self._make_json_serializable(results)
            import json
            json.dump(json_results, f, indent=2, default=str)

        logger.info(f"💾 Monitoring results saved to {results_file}")

        # Also save latest results
        latest_file = "monitoring/reports/latest_monitoring_run.json"
        with open(latest_file, 'w') as f:
            json.dump(json_results, f, indent=2, default=str)

    def _make_json_serializable(self, obj):
        """Convert objects to JSON-serializable format"""
        if isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    async def _send_monitoring_alerts(self, results: Dict[str, Any]) -> None:
        """Send alerts about monitoring results"""
        try:
            summary = results.get("summary", {})
            alerts = results.get("alerts", [])
            recommendations = results.get("recommendations", [])

            # Only send alert if there are significant issues
            critical_issues = summary.get("critical_issues", 0)
            high_issues = summary.get("high_issues", 0)

            if critical_issues > 0 or high_issues > 0:
                alert_message = f"🚨 MONITORING ALERT\n"
                alert_message += f"Status: {summary.get('overall_status', 'unknown').upper()}\n"
                alert_message += f"Critical Issues: {critical_issues}\n"
                alert_message += f"High Issues: {high_issues}\n"
                alert_message += f"Total Alerts: {summary.get('total_alerts', 0)}\n\n"

                if recommendations:
                    alert_message += "Recommendations:\n"
                    for rec in recommendations[:3]:  # Limit to top 3
                        alert_message += f"• {rec}\n"

                # Send alert
                from utils.alerts import send_telegram_alert
                await send_telegram_alert(alert_message)

                logger.info("🚨 Monitoring alert sent")

        except Exception as e:
            logger.error(f"Error sending monitoring alert: {e}")

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Comprehensive Monitoring Runner")
    parser.add_argument(
        "--checks",
        nargs="*",
        choices=["security", "performance", "alerts"],
        help="Specific checks to run (default: all enabled)"
    )
    parser.add_argument(
        "--schedule",
        choices=["daily", "weekly", "manual"],
        default="manual",
        help="Run type for logging purposes"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info(f"🚀 Starting monitoring run (schedule: {args.schedule})")

    try:
        orchestrator = MonitoringOrchestrator()
        results = await orchestrator.run_all_checks(args.checks)

        # Print summary
        summary = results.get("summary", {})
        logger.info("📊 Monitoring Summary:")
        logger.info(f"   Checks Completed: {summary.get('checks_completed', 0)}")
        logger.info(f"   Overall Status: {summary.get('overall_status', 'unknown').upper()}")
        logger.info(f"   Total Alerts: {summary.get('total_alerts', 0)}")

        # Exit with appropriate code
        if summary.get("overall_status") == "critical":
            sys.exit(2)  # Critical
        elif summary.get("overall_status") in ["high", "medium"]:
            sys.exit(1)  # Warning
        else:
            sys.exit(0)  # Success

    except Exception as e:
        logger.error(f"❌ Monitoring run failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
