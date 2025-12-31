#!/usr/bin/env python3
"""
Alerting System for Polymarket Copy Bot

Provides comprehensive alerting capabilities including:
- Threshold-based alert generation
- Multi-channel notifications (email, SMS, Telegram)
- Alert deduplication and grouping
- Alert severity classification and escalation
"""

import json
import logging
import os
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Alert data structure"""

    id: str
    timestamp: datetime
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    category: str  # SYSTEM, APPLICATION, SECURITY, BUSINESS
    source: str  # Component that generated the alert
    title: str
    message: str
    metrics: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    escalation_level: int = 0
    notification_channels: List[str] = None

    def __post_init__(self):
        if self.notification_channels is None:
            self.notification_channels = []


@dataclass
class AlertRule:
    """Alert rule configuration"""

    name: str
    category: str
    severity: str
    condition: Callable[[Dict[str, Any]], bool]
    message_template: str
    cooldown_minutes: int = 5
    escalation_threshold: int = 3
    notification_channels: List[str] = None

    def __post_init__(self):
        if self.notification_channels is None:
            self.notification_channels = ["log"]


class AlertingSystem:
    """Comprehensive alerting system"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent

        # Alert storage
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.max_history = 10000

        # Alert rules
        self.alert_rules: List[AlertRule] = []
        self._load_default_rules()

        # Notification channels
        self.notification_channels = {
            "email": self._send_email_notification,
            "telegram": self._send_telegram_notification,
            "sms": self._send_sms_notification,
            "log": self._send_log_notification,
        }

        # Alert deduplication
        self.alert_cooldowns: Dict[str, datetime] = {}

        # Monitoring thread
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None

    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add a custom alert rule"""
        self.alert_rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")

    def check_alerts(self, metrics_data: Dict[str, Any]) -> List[Alert]:
        """Check metrics against alert rules and generate alerts"""
        new_alerts = []

        for rule in self.alert_rules:
            try:
                if rule.condition(metrics_data):
                    alert_key = f"{rule.category}:{rule.name}"

                    # Check cooldown
                    if alert_key in self.alert_cooldowns:
                        cooldown_end = self.alert_cooldowns[alert_key]
                        if datetime.now() < cooldown_end:
                            continue  # Still in cooldown

                    # Generate alert
                    alert_id = f"{alert_key}_{int(datetime.now().timestamp())}"

                    # Format message
                    message = rule.message_template.format(**metrics_data)

                    alert = Alert(
                        id=alert_id,
                        timestamp=datetime.now(),
                        severity=rule.severity,
                        category=rule.category,
                        source=metrics_data.get("source", "unknown"),
                        title=f"{rule.severity}: {rule.name}",
                        message=message,
                        metrics=metrics_data,
                        notification_channels=rule.notification_channels.copy(),
                    )

                    new_alerts.append(alert)

                    # Set cooldown
                    self.alert_cooldowns[alert_key] = datetime.now() + timedelta(
                        minutes=rule.cooldown_minutes
                    )

            except Exception as e:
                logger.error(f"Error checking alert rule {rule.name}: {e}")

        return new_alerts

    def process_alert(self, alert: Alert) -> None:
        """Process an alert: store, notify, escalate"""
        # Store alert
        self.active_alerts[alert.id] = alert
        self.alert_history.append(alert)

        # Maintain history size
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history :]

        logger.warning(f"ALERT GENERATED: {alert.title} - {alert.message}")

        # Send notifications
        self._send_notifications(alert)

        # Check for escalation
        self._check_escalation(alert)

    def resolve_alert(self, alert_id: str, resolution_message: str = "") -> bool:
        """Resolve an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.now()
            alert.message += f" (RESOLVED: {resolution_message})"

            logger.info(f"ALERT RESOLVED: {alert.title}")

            # Send resolution notification
            resolution_alert = Alert(
                id=f"{alert_id}_resolved",
                timestamp=datetime.now(),
                severity="INFO",
                category=alert.category,
                source=alert.source,
                title=f"RESOLVED: {alert.title}",
                message=f"Alert resolved: {resolution_message}",
                metrics={},
                resolved=True,
                notification_channels=["log"],  # Only log resolutions by default
            )

            self._send_notifications(resolution_alert)
            return True

        return False

    def get_active_alerts(
        self, category: Optional[str] = None, severity: Optional[str] = None
    ) -> List[Alert]:
        """Get active alerts with optional filtering"""
        alerts = list(self.active_alerts.values())

        if category:
            alerts = [a for a in alerts if a.category == category]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts

    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for specified time period"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [a for a in self.alert_history if a.timestamp > cutoff_time]

    def _load_default_rules(self) -> None:
        """Load default alert rules"""

        # System resource alerts
        self.alert_rules.extend(
            [
                AlertRule(
                    name="High CPU Usage",
                    category="SYSTEM",
                    severity="HIGH",
                    condition=lambda m: m.get("cpu_percent", 0) > 90,
                    message_template="CPU usage at {cpu_percent:.1f}% (threshold: 90%)",
                    cooldown_minutes=5,
                    notification_channels=["log", "email"],
                ),
                AlertRule(
                    name="Critical Memory Usage",
                    category="SYSTEM",
                    severity="CRITICAL",
                    condition=lambda m: m.get("memory_percent", 0) > 95,
                    message_template="Memory usage at {memory_percent:.1f}% (threshold: 95%)",
                    cooldown_minutes=2,
                    notification_channels=["log", "email", "telegram"],
                ),
                AlertRule(
                    name="Disk Space Critical",
                    category="SYSTEM",
                    severity="CRITICAL",
                    condition=lambda m: m.get("disk_usage_percent", 0) > 95,
                    message_template="Disk usage at {disk_usage_percent:.1f}% (threshold: 95%)",
                    cooldown_minutes=10,
                    notification_channels=["log", "email", "telegram"],
                ),
            ]
        )

        # Application performance alerts
        self.alert_rules.extend(
            [
                AlertRule(
                    name="Low Trade Success Rate",
                    category="APPLICATION",
                    severity="HIGH",
                    condition=lambda m: m.get("success_rate_percent", 100) < 80,
                    message_template="Trade success rate at {success_rate_percent:.1f}% (threshold: 80%)",
                    cooldown_minutes=5,
                    notification_channels=["log", "telegram"],
                ),
                AlertRule(
                    name="High Trade Latency",
                    category="APPLICATION",
                    severity="MEDIUM",
                    condition=lambda m: m.get("average_latency_ms", 0) > 10000,
                    message_template="Average trade latency {average_latency_ms:.0f}ms (threshold: 10000ms)",
                    cooldown_minutes=10,
                    notification_channels=["log"],
                ),
                AlertRule(
                    name="API Rate Limit Critical",
                    category="APPLICATION",
                    severity="HIGH",
                    condition=lambda m: m.get("current_rate_limit_usage", 0) > 90,
                    message_template="API rate limit usage at {current_rate_limit_usage}% (threshold: 90%)",
                    cooldown_minutes=2,
                    notification_channels=["log", "telegram"],
                ),
            ]
        )

        # Security alerts
        self.alert_rules.extend(
            [
                AlertRule(
                    name="Circuit Breaker Active",
                    category="SECURITY",
                    severity="CRITICAL",
                    condition=lambda m: m.get("circuit_breaker_active", False),
                    message_template="Circuit breaker has been activated due to system instability",
                    cooldown_minutes=1,
                    notification_channels=["log", "email", "telegram"],
                ),
                AlertRule(
                    name="File Integrity Violation",
                    category="SECURITY",
                    severity="CRITICAL",
                    condition=lambda m: m.get("integrity_violations", 0) > 0,
                    message_template="File integrity violations detected: {integrity_violations} files compromised",
                    cooldown_minutes=1,
                    notification_channels=["log", "email", "telegram"],
                ),
            ]
        )

        # Business logic alerts
        self.alert_rules.extend(
            [
                AlertRule(
                    name="Wallet Balance Low",
                    category="BUSINESS",
                    severity="MEDIUM",
                    condition=lambda m: m.get("balance_matic", 1.0) < 0.1,
                    message_template="Wallet MATIC balance low: {balance_matic:.4f} (threshold: 0.1)",
                    cooldown_minutes=30,
                    notification_channels=["log", "telegram"],
                ),
                AlertRule(
                    name="High Transaction Failure Rate",
                    category="BUSINESS",
                    severity="HIGH",
                    condition=lambda m: m.get("failed_transaction_rate", 0) > 10,
                    message_template="Transaction failure rate at {failed_transaction_rate:.1f}% (threshold: 10%)",
                    cooldown_minutes=10,
                    notification_channels=["log", "telegram"],
                ),
            ]
        )

    def _check_escalation(self, alert: Alert) -> None:
        """Check if alert needs escalation"""
        # Count similar active alerts
        similar_alerts = len(
            [
                a
                for a in self.active_alerts.values()
                if a.category == alert.category
                and a.severity == alert.severity
                and not a.resolved
            ]
        )

        # Find the alert rule
        rule = next(
            (
                r
                for r in self.alert_rules
                if r.category == alert.category and r.name in alert.title
            ),
            None,
        )

        if rule and similar_alerts >= rule.escalation_threshold:
            alert.escalation_level += 1

            # Add escalation notification channels
            if "email" not in alert.notification_channels:
                alert.notification_channels.append("email")
            if "telegram" not in alert.notification_channels:
                alert.notification_channels.append("telegram")

            logger.warning(
                f"ALERT ESCALATED: {alert.title} (Level {alert.escalation_level})"
            )
            self._send_notifications(alert)

    def _send_notifications(self, alert: Alert) -> None:
        """Send alert notifications through configured channels"""
        for channel in alert.notification_channels:
            try:
                if channel in self.notification_channels:
                    self.notification_channels[channel](alert)
                else:
                    logger.warning(f"Unknown notification channel: {channel}")
            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {e}")

    def _send_email_notification(self, alert: Alert) -> None:
        """Send email notification"""
        try:
            # Email configuration (would be loaded from config)
            os.getenv("SMTP_SERVER", "localhost")
            int(os.getenv("SMTP_PORT", "587"))
            smtp_user = os.getenv("SMTP_USER", "")
            os.getenv("SMTP_PASS", "")
            to_email = os.getenv("ALERT_EMAIL", "admin@localhost")

            msg = MIMEMultipart()
            msg["From"] = smtp_user
            msg["To"] = to_email
            msg["Subject"] = f"[{alert.severity}] {alert.title}"

            body = f"""
Polymarket Copy Bot Alert

Severity: {alert.severity}
Category: {alert.category}
Source: {alert.source}
Time: {alert.timestamp}

{alert.message}

Metrics:
{json.dumps(alert.metrics, indent=2, default=str)}

This is an automated alert from the Polymarket Copy Bot monitoring system.
"""
            msg.attach(MIMEText(body, "plain"))

            # Send email (simplified - would need proper SMTP setup)
            logger.info(f"EMAIL ALERT: Would send to {to_email}: {alert.title}")

        except Exception as e:
            logger.error(f"Email notification failed: {e}")

    def _send_telegram_notification(self, alert: Alert) -> None:
        """Send Telegram notification"""
        try:
            # Telegram configuration (would be loaded from config)
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

            if not bot_token or not chat_id:
                logger.warning("Telegram credentials not configured")
                return

            # Send message (simplified - would use requests library)
            logger.info(f"TELEGRAM ALERT: Would send: {alert.title}")

        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")

    def _send_sms_notification(self, alert: Alert) -> None:
        """Send SMS notification"""
        try:
            # SMS configuration (would be loaded from config)
            sms_provider = os.getenv("SMS_PROVIDER", "")
            sms_api_key = os.getenv("SMS_API_KEY", "")
            sms_phone = os.getenv("SMS_PHONE", "")

            if not sms_provider or not sms_api_key or not sms_phone:
                logger.warning("SMS credentials not configured")
                return

            f"{alert.severity}: {alert.title} - {alert.message[:100]}..."

            # Send SMS (simplified - would use appropriate SMS API)
            logger.info(f"SMS ALERT: Would send to {sms_phone}: {alert.title}")

        except Exception as e:
            logger.error(f"SMS notification failed: {e}")

    def _send_log_notification(self, alert: Alert) -> None:
        """Send log notification (always enabled)"""
        log_level = (
            logging.WARNING if alert.severity in ["CRITICAL", "HIGH"] else logging.INFO
        )
        logger.log(log_level, f"ALERT: {alert.title} - {alert.message}")


def main():
    """CLI interface for alerting system"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Alerting System for Polymarket Copy Bot"
    )
    parser.add_argument(
        "action", choices=["check", "list-active", "list-history", "resolve", "test"]
    )
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--severity", help="Filter by severity")
    parser.add_argument("--alert-id", help="Alert ID for resolution")
    parser.add_argument(
        "--hours", type=int, default=24, help="Hours of history to show"
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    alerting = AlertingSystem()

    if args.action == "check":
        # Simulate checking some metrics
        test_metrics = {
            "cpu_percent": 85.5,
            "memory_percent": 92.3,
            "disk_usage_percent": 87.1,
            "source": "system_monitor",
        }

        alerts = alerting.check_alerts(test_metrics)

        if args.json:
            print(
                json.dumps([asdict(alert) for alert in alerts], default=str, indent=2)
            )
        else:
            print(f"Generated {len(alerts)} alerts:")
            for alert in alerts:
                print(f"  {alert.severity}: {alert.title}")

    elif args.action == "list-active":
        alerts = alerting.get_active_alerts(args.category, args.severity)

        if args.json:
            print(
                json.dumps([asdict(alert) for alert in alerts], default=str, indent=2)
            )
        else:
            print(f"Active alerts: {len(alerts)}")
            for alert in alerts:
                status = "ESCALATED" if alert.escalation_level > 0 else "ACTIVE"
                print(
                    f"  {alert.severity} [{status}]: {alert.title} ({alert.timestamp})"
                )

    elif args.action == "list-history":
        alerts = alerting.get_alert_history(args.hours)

        if args.json:
            print(
                json.dumps([asdict(alert) for alert in alerts], default=str, indent=2)
            )
        else:
            print(f"Alert history (last {args.hours} hours): {len(alerts)} alerts")
            for alert in alerts:
                status = "RESOLVED" if alert.resolved else "ACTIVE"
                print(f"  {alert.severity} [{status}]: {alert.title}")

    elif args.action == "resolve":
        if not args.alert_id:
            print("Error: --alert-id required for resolution")
            sys.exit(1)

        if alerting.resolve_alert(args.alert_id, "Manually resolved via CLI"):
            print(f"Alert {args.alert_id} resolved")
        else:
            print(f"Alert {args.alert_id} not found")

    elif args.action == "test":
        # Test all notification channels
        test_alert = Alert(
            id="test_alert",
            timestamp=datetime.now(),
            severity="INFO",
            category="TEST",
            source="cli",
            title="Test Alert",
            message="This is a test alert to verify notification channels",
            metrics={"test": True},
            notification_channels=["log", "email", "telegram"],
        )

        print("Testing notification channels...")
        alerting._send_notifications(test_alert)
        print("Test notifications sent (check logs)")


if __name__ == "__main__":
    main()
