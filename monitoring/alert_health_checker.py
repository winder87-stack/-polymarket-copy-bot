#!/usr/bin/env python3
"""
Alert System Health Checker
============================

Monitors the health and reliability of alert systems including:
- Telegram bot connectivity and responsiveness
- Alert delivery success rates
- Alert system latency and performance
- Configuration validation
- Fallback alert mechanisms

Generates health reports and alerts about alert system issues.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

from monitoring.monitoring_config import monitoring_config
from utils.alerts import send_telegram_alert

logger = logging.getLogger(__name__)


class AlertHealthChecker:
    """Health checker for alert systems"""

    def __init__(self) -> None:
        self.config = monitoring_config.alerts
        self.health_history = []
        self.alerts = []

    async def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive alert system health check"""
        logger.info("🚨 Starting alert system health check")

        check_start = datetime.now()

        results = {
            "timestamp": check_start.isoformat(),
            "checks": {},
            "overall_health": "unknown",
            "issues": [],
            "recommendations": [],
        }

        # Run health checks
        checks = []

        if self.config.telegram_health_check:
            checks.append(("telegram", self._check_telegram_health()))

        if self.config.email_health_check:
            checks.append(("email", self._check_email_health()))

        if self.config.webhook_health_check:
            checks.append(("webhook", self._check_webhook_health()))

        # Execute checks
        for check_name, check_coro in checks:
            try:
                logger.info(f"Checking {check_name} alert system...")
                check_result = await check_coro
                results["checks"][check_name] = check_result
                logger.info(f"✅ {check_name} health check completed")
            except Exception as e:
                logger.error(f"❌ {check_name} health check failed: {e}")
                results["checks"][check_name] = {"error": str(e), "status": "failed"}

        # Analyze results
        results["overall_health"] = self._analyze_overall_health(results)
        results["issues"] = self._identify_issues(results)
        results["recommendations"] = self._generate_recommendations(results)

        # Generate alerts for issues
        if results["issues"]:
            self.alerts.extend(results["issues"])

        # Save health check results
        await self._save_health_results(results)

        # Send test alert if configured
        if self.config.alert_test_enabled:
            await self._send_test_alert(results)

        check_duration = (datetime.now() - check_start).total_seconds()
        logger.info(f"🚨 Alert system health check completed in {check_duration:.1f}s")

        return results

    async def _check_telegram_health(self) -> Dict[str, Any]:
        """Check Telegram bot health and responsiveness"""
        result = {
            "status": "unknown",
            "response_time_ms": None,
            "bot_info": None,
            "test_message_sent": False,
            "test_message_delivered": False,
            "error": None,
        }

        try:
            # Test bot connectivity
            start_time = time.time()

            # Try to get bot info (this tests API connectivity)
            from telegram import Bot

            from config.settings import settings

            if not settings.alerts.telegram_bot_token:
                result["status"] = "not_configured"
                result["error"] = "Telegram bot token not configured"
                return result

            bot = Bot(token=settings.alerts.telegram_bot_token)

            # Get bot info
            bot_info = await bot.get_me()
            result["bot_info"] = {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
                "can_join_groups": bot_info.can_join_groups,
                "can_read_all_group_messages": bot_info.can_read_all_group_messages,
                "supports_inline_queries": bot_info.supports_inline_queries,
            }

            response_time = (time.time() - start_time) * 1000
            result["response_time_ms"] = response_time

            # Check response time threshold
            if response_time > self.config.max_alert_delay_seconds * 1000:
                result["status"] = "slow"
                self.alerts.append(
                    {
                        "level": "medium",
                        "component": "telegram",
                        "message": f"Telegram API response time {response_time:.1f}ms exceeds threshold {self.config.max_alert_delay_seconds * 1000}ms",
                        "details": {"response_time_ms": response_time},
                    }
                )
            else:
                result["status"] = "healthy"

            # Send test message if configured
            if settings.alerts.telegram_chat_id and self.config.test_alert_enabled:
                test_message = f"🔍 Alert System Health Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                try:
                    message = await bot.send_message(
                        chat_id=settings.alerts.telegram_chat_id,
                        text=test_message,
                        disable_notification=True,  # Don't notify for test messages
                    )
                    result["test_message_sent"] = True
                    result["test_message_delivered"] = True
                    result["message_id"] = message.message_id
                except Exception as e:
                    result["test_message_sent"] = False
                    result["error"] = f"Failed to send test message: {str(e)}"
                    result["status"] = "degraded"

                    self.alerts.append(
                        {
                            "level": "high",
                            "component": "telegram",
                            "message": "Failed to send test message to Telegram",
                            "details": {"error": str(e)},
                        }
                    )

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)

            self.alerts.append(
                {
                    "level": "critical",
                    "component": "telegram",
                    "message": "Telegram health check completely failed",
                    "details": {"error": str(e)},
                }
            )

        return result

    async def _check_email_health(self) -> Dict[str, Any]:
        """Check email alert system health"""
        result = {
            "status": "not_implemented",
            "note": "Email alerting not currently implemented",
        }

        # Placeholder for future email health checking
        # Would include SMTP connectivity tests, delivery confirmation, etc.

        return result

    async def _check_webhook_health(self) -> Dict[str, Any]:
        """Check webhook alert system health"""
        result = {
            "status": "not_implemented",
            "note": "Webhook alerting not currently implemented",
        }

        # Placeholder for future webhook health checking
        # Would include HTTP connectivity tests, response validation, etc.

        return result

    def _analyze_overall_health(self, results: Dict[str, Any]) -> str:
        """Analyze overall alert system health"""
        checks = results.get("checks", {})

        if not checks:
            return "no_checks"

        healthy_count = 0
        total_count = len(checks)

        for check_name, check_result in checks.items():
            status = check_result.get("status", "unknown")
            if status in ["healthy", "not_configured", "not_implemented"]:
                healthy_count += 1
            elif status == "slow":
                healthy_count += 0.5  # Partial credit for slow but working

        health_ratio = healthy_count / total_count

        if health_ratio == 1.0:
            return "healthy"
        elif health_ratio >= 0.8:
            return "mostly_healthy"
        elif health_ratio >= 0.5:
            return "degraded"
        else:
            return "critical"

    def _identify_issues(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify specific issues with alert systems"""
        issues = []
        checks = results.get("checks", {})

        for check_name, check_result in checks.items():
            status = check_result.get("status", "unknown")
            error = check_result.get("error")

            if status == "failed":
                issues.append(
                    {
                        "component": check_name,
                        "severity": "critical",
                        "issue": "complete_failure",
                        "description": f"{check_name.capitalize()} alert system completely failed",
                        "details": {"error": error},
                    }
                )

            elif status == "degraded":
                issues.append(
                    {
                        "component": check_name,
                        "severity": "high",
                        "issue": "degraded_performance",
                        "description": f"{check_name.capitalize()} alert system is degraded",
                        "details": {"error": error},
                    }
                )

            elif status == "slow":
                response_time = check_result.get("response_time_ms")
                issues.append(
                    {
                        "component": check_name,
                        "severity": "medium",
                        "issue": "slow_response",
                        "description": f"{check_name.capitalize()} alert system response is slow",
                        "details": {"response_time_ms": response_time},
                    }
                )

        return issues

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on health check results"""
        recommendations = []
        checks = results.get("checks", {})
        overall_health = results.get("overall_health", "unknown")

        if overall_health in ["critical", "degraded"]:
            recommendations.append(
                "🚨 Address critical alert system issues immediately"
            )

        # Check individual components
        telegram_result = checks.get("telegram", {})
        if telegram_result.get("status") == "failed":
            recommendations.append("🔧 Fix Telegram bot configuration and connectivity")
        elif telegram_result.get("status") == "slow":
            recommendations.append(
                "⚡ Investigate and optimize Telegram API response times"
            )

        if not any(
            check.get("status") in ["healthy", "not_configured"]
            for check in checks.values()
        ):
            recommendations.append(
                "📱 Consider implementing backup alert mechanisms (email, SMS)"
            )

        # General recommendations
        if not recommendations:
            recommendations.append("✅ Alert systems are functioning properly")

        return recommendations

    async def _save_health_results(self, results: Dict[str, Any]) -> None:
        """Save health check results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"monitoring/alert_health/health_check_{timestamp}.json"

        # Ensure directory exists
        import os

        os.makedirs("monitoring/alert_health", exist_ok=True)

        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"💾 Alert health check results saved to {results_file}")

        # Also save latest results
        latest_file = "monitoring/alert_health/latest_health_check.json"
        with open(latest_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

    async def _send_test_alert(self, results: Dict[str, Any]) -> None:
        """Send periodic test alert to verify system is working"""
        try:
            overall_health = results.get("overall_health", "unknown")
            issues_count = len(results.get("issues", []))

            # Determine alert level based on health
            if overall_health == "critical":
                alert_level = "🚨 CRITICAL"
            elif overall_health == "degraded":
                alert_level = "⚠️ DEGRADED"
            elif issues_count > 0:
                alert_level = "ℹ️ ISSUES DETECTED"
            else:
                alert_level = "✅ HEALTHY"

            test_message = f"{alert_level} Alert System Health Check\n"
            test_message += f"Status: {overall_health.upper()}\n"
            test_message += f"Issues: {issues_count}\n"
            test_message += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # Send via our alert system
            success = await send_telegram_alert(test_message)

            if success:
                logger.info("✅ Test alert sent successfully")
            else:
                logger.error("❌ Failed to send test alert")

        except Exception as e:
            logger.error(f"Error sending test alert: {e}")

    async def get_health_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alert system health history"""
        # Load recent health check results
        history = []
        health_dir = "monitoring/alert_health"

        if os.path.exists(health_dir):
            import glob

            health_files = glob.glob(f"{health_dir}/health_check_*.json")
            health_files.sort(reverse=True)  # Most recent first

            cutoff_time = datetime.now() - timedelta(hours=hours)

            for health_file in health_files[:50]:  # Limit to last 50 checks
                try:
                    with open(health_file, "r") as f:
                        result = json.load(f)

                    check_time = datetime.fromisoformat(result["timestamp"])
                    if check_time >= cutoff_time:
                        history.append(result)

                except Exception as e:
                    logger.debug(f"Error loading health file {health_file}: {e}")

        return history

    async def get_health_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summarized health statistics"""
        history = await self.get_health_history(hours)

        if not history:
            return {"error": "No health history available"}

        summary = {
            "period_hours": hours,
            "total_checks": len(history),
            "health_distribution": {},
            "average_response_time_ms": 0,
            "success_rate": 0,
            "most_common_issues": [],
        }

        total_response_time = 0
        successful_checks = 0
        all_issues = []

        for check in history:
            # Count health statuses
            health = check.get("overall_health", "unknown")
            summary["health_distribution"][health] = (
                summary["health_distribution"].get(health, 0) + 1
            )

            # Calculate response times
            telegram_check = check.get("checks", {}).get("telegram", {})
            if telegram_check.get("response_time_ms"):
                total_response_time += telegram_check["response_time_ms"]
                successful_checks += 1

            # Collect issues
            issues = check.get("issues", [])
            all_issues.extend([issue["issue"] for issue in issues])

        # Calculate averages
        if successful_checks > 0:
            summary["average_response_time_ms"] = (
                total_response_time / successful_checks
            )
            summary["success_rate"] = successful_checks / len(history)

        # Find most common issues
        if all_issues:
            from collections import Counter

            issue_counts = Counter(all_issues)
            summary["most_common_issues"] = issue_counts.most_common(5)

        return summary


async def run_alert_health_check() -> Dict[str, Any]:
    """Run the alert system health check"""
    checker = AlertHealthChecker()
    results = await checker.run_health_check()

    # Log summary
    overall_health = results.get("overall_health", "unknown")
    issues_count = len(results.get("issues", []))

    logger.info("🚨 Alert System Health Check Summary:")
    logger.info(f"   Overall Health: {overall_health.upper()}")
    logger.info(f"   Issues Found: {issues_count}")

    return results


if __name__ == "__main__":
    # Run alert health check
    asyncio.run(run_alert_health_check())
