"""
Market Maker Alert System
=========================

Real-time monitoring and alerting system for market maker detection,
classification changes, and behavioral pattern anomalies.

Features:
- Classification change alerts
- Market maker probability threshold alerts
- Behavioral anomaly detection
- Risk-based alert prioritization
- Multi-channel notification support
- Alert fatigue prevention
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from config.settings import settings
from core.market_maker_detector import MarketMakerDetector
from utils.helpers import format_currency
from utils.security import secure_log

logger = logging.getLogger(__name__)


class MarketMakerAlertSystem:
    """
    Advanced alert system for market maker detection and monitoring.

    Monitors wallet behavior changes, classification updates, and
    trading pattern anomalies with intelligent alert prioritization.
    """

    def __init__(self, market_maker_detector: MarketMakerDetector):
        self.detector = market_maker_detector

        # Alert configuration
        self.alert_thresholds = {
            "classification_change": True,
            "mm_probability_threshold": 0.8,  # Alert when MM probability exceeds this
            "confidence_drop_threshold": 0.2,  # Alert when confidence drops significantly
            "high_frequency_alert": 10,  # Trades per hour threshold
            "anomaly_detection": True,
            "risk_alerts": True
        }

        # Alert state tracking
        self.recent_alerts: Set[str] = set()  # Track recent alerts to prevent spam
        self.alert_cooldown_hours = 6  # Minimum hours between similar alerts
        self.max_alerts_per_hour = 10  # Rate limiting

        # Alert history for trend analysis
        self.alert_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000

        # Telegram integration (if configured)
        self.telegram_enabled = bool(settings.alerts.telegram_bot_token and settings.alerts.telegram_chat_id)

        logger.info("🚨 Market maker alert system initialized")

    async def check_for_alerts(self) -> List[Dict[str, Any]]:
        """
        Check for all types of market maker alerts.

        Returns:
            List of alert dictionaries
        """

        alerts = []

        try:
            # 1. Check for classification changes
            classification_alerts = await self._check_classification_changes()
            alerts.extend(classification_alerts)

            # 2. Check for market maker probability thresholds
            probability_alerts = await self._check_probability_thresholds()
            alerts.extend(probability_alerts)

            # 3. Check for behavioral anomalies
            if self.alert_thresholds["anomaly_detection"]:
                anomaly_alerts = await self._check_behavioral_anomalies()
                alerts.extend(anomaly_alerts)

            # 4. Check for risk-based alerts
            if self.alert_thresholds["risk_alerts"]:
                risk_alerts = await self._check_risk_alerts()
                alerts.extend(risk_alerts)

            # 5. Check for high-frequency trading alerts
            frequency_alerts = await self._check_high_frequency_alerts()
            alerts.extend(frequency_alerts)

            # Filter and prioritize alerts
            filtered_alerts = self._filter_and_prioritize_alerts(alerts)

            # Store alert history
            self._store_alert_history(filtered_alerts)

            # Send notifications
            await self._send_notifications(filtered_alerts)

            logger.info(f"🚨 Generated {len(filtered_alerts)} market maker alerts")

        except Exception as e:
            logger.error(f"Error checking for alerts: {e}")
            alerts.append({
                "level": "error",
                "type": "system_error",
                "title": "Alert System Error",
                "message": f"Failed to check for market maker alerts: {e}",
                "timestamp": datetime.now().isoformat()
            })

        return filtered_alerts

    async def _check_classification_changes(self) -> List[Dict[str, Any]]:
        """Check for wallet classification changes"""

        alerts = []

        try:
            changes = await self.detector.detect_classification_changes()

            for change in changes:
                alert_key = f"classification_change_{change['wallet_address']}_{change['current_classification']}"

                if not self._is_alert_on_cooldown(alert_key):
                    alert_level = self._determine_change_alert_level(change)

                    alerts.append({
                        "level": alert_level,
                        "type": "classification_change",
                        "title": f"Wallet Classification Changed: {change['wallet_address'][:10]}...",
                        "message": f"Changed from '{change['previous_classification'].replace('_', ' ')}' to '{change['current_classification'].replace('_', ' ')}'",
                        "details": {
                            "wallet_address": change['wallet_address'],
                            "previous_classification": change['previous_classification'],
                            "current_classification": change['current_classification'],
                            "mm_probability_change": round(change['mm_probability_change'], 3),
                            "hours_since_change": round(change['hours_since_change'], 1),
                            "confidence_current": round(change['confidence_current'], 3)
                        },
                        "timestamp": datetime.now().isoformat(),
                        "alert_key": alert_key
                    })

        except Exception as e:
            logger.error(f"Error checking classification changes: {e}")

        return alerts

    async def _check_probability_thresholds(self) -> List[Dict[str, Any]]:
        """Check for market maker probability threshold crossings"""

        alerts = []

        try:
            all_classifications = self.detector.storage.get_all_classifications()
            threshold = self.alert_thresholds["mm_probability_threshold"]

            for wallet_address, classification_data in all_classifications.items():
                mm_probability = classification_data.get('market_maker_probability', 0)

                if mm_probability >= threshold:
                    alert_key = f"mm_probability_{wallet_address}_{threshold}"

                    if not self._is_alert_on_cooldown(alert_key):
                        alerts.append({
                            "level": "info",
                            "type": "probability_threshold",
                            "title": f"High Market Maker Probability: {wallet_address[:10]}...",
                            "message": f"Market maker probability: {mm_probability:.3f} (threshold: {threshold})",
                            "details": {
                                "wallet_address": wallet_address,
                                "mm_probability": mm_probability,
                                "classification": classification_data.get('classification'),
                                "confidence_score": classification_data.get('confidence_score'),
                                "threshold": threshold
                            },
                            "timestamp": datetime.now().isoformat(),
                            "alert_key": alert_key
                        })

        except Exception as e:
            logger.error(f"Error checking probability thresholds: {e}")

        return alerts

    async def _check_behavioral_anomalies(self) -> List[Dict[str, Any]]:
        """Check for behavioral anomalies in wallet trading patterns"""

        alerts = []

        try:
            all_classifications = self.detector.storage.get_all_classifications()

            for wallet_address, classification_data in all_classifications.items():
                metrics = classification_data.get('metrics_snapshot', {})
                temporal = metrics.get('temporal_metrics', {})
                directional = metrics.get('directional_metrics', {})

                anomalies = []

                # Check for sudden frequency changes
                trades_per_hour = temporal.get('trades_per_hour', 0)
                if trades_per_hour > 20:  # Extremely high frequency
                    anomalies.append("extremely_high_frequency")

                # Check for perfect balance (suspicious)
                balance_score = directional.get('balance_score', 0)
                if balance_score > 0.95 and trades_per_hour > 2:
                    anomalies.append("suspiciously_balanced")

                # Check for burst trading patterns
                burst_events = temporal.get('burst_trading_events', 0)
                if burst_events > 10:
                    anomalies.append("excessive_burst_trading")

                # Generate alerts for detected anomalies
                for anomaly in anomalies:
                    alert_key = f"anomaly_{anomaly}_{wallet_address}"

                    if not self._is_alert_on_cooldown(alert_key):
                        alert_level, title, message = self._format_anomaly_alert(anomaly, wallet_address, metrics)

                        alerts.append({
                            "level": alert_level,
                            "type": "behavioral_anomaly",
                            "title": title,
                            "message": message,
                            "details": {
                                "wallet_address": wallet_address,
                                "anomaly_type": anomaly,
                                "metrics": metrics,
                                "classification": classification_data.get('classification')
                            },
                            "timestamp": datetime.now().isoformat(),
                            "alert_key": alert_key
                        })

        except Exception as e:
            logger.error(f"Error checking behavioral anomalies: {e}")

        return alerts

    async def _check_risk_alerts(self) -> List[Dict[str, Any]]:
        """Check for risk-based alerts"""

        alerts = []

        try:
            all_classifications = self.detector.storage.get_all_classifications()

            for wallet_address, classification_data in all_classifications.items():
                metrics = classification_data.get('metrics_snapshot', {})
                risk_metrics = metrics.get('risk_metrics', {})

                # Check for high position limit breaches
                breaches = risk_metrics.get('position_limit_breaches', 0)
                if breaches > 5:
                    alert_key = f"risk_breaches_{wallet_address}"

                    if not self._is_alert_on_cooldown(alert_key):
                        alerts.append({
                            "level": "warning",
                            "type": "risk_alert",
                            "title": f"Risk Alert: Position Limit Breaches - {wallet_address[:10]}...",
                            "message": f"Wallet exceeded position limits {breaches} times",
                            "details": {
                                "wallet_address": wallet_address,
                                "breach_count": breaches,
                                "net_position_drift": risk_metrics.get('net_position_drift', 0),
                                "risk_assessment": classification_data.get('risk_assessment', {})
                            },
                            "timestamp": datetime.now().isoformat(),
                            "alert_key": alert_key
                        })

                # Check for high price impact
                price_impact = risk_metrics.get('avg_price_impact', 0)
                if price_impact > 0.05:  # 5% average price impact
                    alert_key = f"risk_price_impact_{wallet_address}"

                    if not self._is_alert_on_cooldown(alert_key):
                        alerts.append({
                            "level": "warning",
                            "type": "risk_alert",
                            "title": f"Risk Alert: High Price Impact - {wallet_address[:10]}...",
                            "message": f"Average price impact: {price_impact:.1%}",
                            "details": {
                                "wallet_address": wallet_address,
                                "avg_price_impact": price_impact,
                                "max_price_impact": risk_metrics.get('max_price_impact', 0),
                                "classification": classification_data.get('classification')
                            },
                            "timestamp": datetime.now().isoformat(),
                            "alert_key": alert_key
                        })

        except Exception as e:
            logger.error(f"Error checking risk alerts: {e}")

        return alerts

    async def _check_high_frequency_alerts(self) -> List[Dict[str, Any]]:
        """Check for high-frequency trading alerts"""

        alerts = []

        try:
            threshold = self.alert_thresholds["high_frequency_alert"]
            all_classifications = self.detector.storage.get_all_classifications()

            for wallet_address, classification_data in all_classifications.items():
                metrics = classification_data.get('metrics_snapshot', {})
                temporal = metrics.get('temporal_metrics', {})
                trades_per_hour = temporal.get('trades_per_hour', 0)

                if trades_per_hour >= threshold:
                    alert_key = f"high_frequency_{wallet_address}"

                    if not self._is_alert_on_cooldown(alert_key):
                        alerts.append({
                            "level": "info",
                            "type": "high_frequency",
                            "title": f"High-Frequency Trading: {wallet_address[:10]}...",
                            "message": f"Trading at {trades_per_hour:.1f} trades per hour",
                            "details": {
                                "wallet_address": wallet_address,
                                "trades_per_hour": trades_per_hour,
                                "threshold": threshold,
                                "classification": classification_data.get('classification'),
                                "burst_events": temporal.get('burst_trading_events', 0)
                            },
                            "timestamp": datetime.now().isoformat(),
                            "alert_key": alert_key
                        })

        except Exception as e:
            logger.error(f"Error checking high frequency alerts: {e}")

        return alerts

    def _determine_change_alert_level(self, change: Dict[str, Any]) -> str:
        """Determine alert level for classification changes"""

        mm_change = abs(change['mm_probability_change'])

        if change['current_classification'] == 'market_maker' and mm_change > 0.2:
            return "critical"  # New market maker detected
        elif change['previous_classification'] == 'market_maker' and mm_change > 0.2:
            return "warning"  # Market maker classification lost
        elif mm_change > 0.3:
            return "warning"  # Significant probability change
        else:
            return "info"  # Minor change

    def _format_anomaly_alert(self, anomaly: str, wallet_address: str, metrics: Dict[str, Any]) -> tuple:
        """Format anomaly alert details"""

        wallet_short = wallet_address[:10] + "..."

        if anomaly == "extremely_high_frequency":
            temporal = metrics.get('temporal_metrics', {})
            freq = temporal.get('trades_per_hour', 0)
            return ("warning", f"Extreme Trading Frequency: {wallet_short}",
                   f"Trading at {freq:.1f} trades/hour - potential HFT activity")

        elif anomaly == "suspiciously_balanced":
            directional = metrics.get('directional_metrics', {})
            balance = directional.get('balance_score', 0)
            return ("warning", f"Suspicious Balance: {wallet_short}",
                   f"Near-perfect balance score ({balance:.3f}) with high frequency")

        elif anomaly == "excessive_burst_trading":
            temporal = metrics.get('temporal_metrics', {})
            bursts = temporal.get('burst_trading_events', 0)
            return ("info", f"Burst Trading: {wallet_short}",
                   f"Detected {bursts} burst trading events - typical market maker behavior")

        else:
            return ("info", f"Trading Anomaly: {wallet_short}",
                   f"Unusual trading pattern detected: {anomaly}")

    def _filter_and_prioritize_alerts(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter and prioritize alerts to prevent spam"""

        # Remove alerts that are on cooldown
        filtered_alerts = [
            alert for alert in alerts
            if not self._is_alert_on_cooldown(alert.get('alert_key', ''))
        ]

        # Rate limiting: max alerts per hour
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        recent_alerts_this_hour = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert['timestamp']) >= current_hour
        ]

        if len(recent_alerts_this_hour) >= self.max_alerts_per_hour:
            # Keep only critical alerts if rate limit exceeded
            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert['level'] == 'critical'
            ]

        # Sort by priority (critical > warning > error > info)
        priority_order = {'critical': 0, 'error': 1, 'warning': 2, 'info': 3}
        filtered_alerts.sort(key=lambda x: priority_order.get(x['level'], 99))

        return filtered_alerts[:self.max_alerts_per_hour]  # Hard limit

    def _is_alert_on_cooldown(self, alert_key: str) -> bool:
        """Check if alert is on cooldown to prevent spam"""

        if not alert_key:
            return False

        # Check recent alerts
        cutoff_time = datetime.now() - timedelta(hours=self.alert_cooldown_hours)

        for alert in self.alert_history:
            if (alert.get('alert_key') == alert_key and
                datetime.fromisoformat(alert['timestamp']) >= cutoff_time):
                return True

        return False

    def _store_alert_history(self, alerts: List[Dict[str, Any]]):
        """Store alerts in history for cooldown and trend analysis"""

        for alert in alerts:
            self.alert_history.append(alert)

            # Update recent alerts set
            alert_key = alert.get('alert_key', '')
            if alert_key:
                self.recent_alerts.add(alert_key)

        # Maintain history size limit
        if len(self.alert_history) > self.max_history_size:
            self.alert_history = self.alert_history[-self.max_history_size:]

        # Clean up old recent alerts (older than cooldown period)
        cutoff_time = datetime.now() - timedelta(hours=self.alert_cooldown_hours)
        self.alert_history = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert['timestamp']) >= cutoff_time
        ]

    async def _send_notifications(self, alerts: List[Dict[str, Any]]):
        """Send alert notifications through configured channels"""

        if not alerts:
            return

        try:
            # Telegram notifications
            if self.telegram_enabled:
                await self._send_telegram_alerts(alerts)

            # Log all alerts
            for alert in alerts:
                level = alert['level'].upper()
                title = alert['title']
                message = alert['message']

                if level == 'CRITICAL':
                    logger.critical(f"🚨 {title}: {message}")
                elif level == 'ERROR':
                    logger.error(f"❌ {title}: {message}")
                elif level == 'WARNING':
                    logger.warning(f"⚠️ {title}: {message}")
                else:
                    logger.info(f"ℹ️ {title}: {message}")

        except Exception as e:
            logger.error(f"Error sending notifications: {e}")

    async def _send_telegram_alerts(self, alerts: List[Dict[str, Any]]):
        """Send alerts via Telegram"""

        if not self.telegram_enabled:
            return

        try:
            import aiohttp

            bot_token = settings.alerts.telegram_bot_token
            chat_id = settings.alerts.telegram_chat_id
            base_url = f"https://api.telegram.org/bot{bot_token}"

            # Group alerts by level for cleaner messages
            alerts_by_level = {}
            for alert in alerts:
                level = alert['level']
                if level not in alerts_by_level:
                    alerts_by_level[level] = []
                alerts_by_level[level].append(alert)

            async with aiohttp.ClientSession() as session:
                for level, level_alerts in alerts_by_level.items():
                    if len(level_alerts) == 1:
                        # Single alert
                        alert = level_alerts[0]
                        message = self._format_telegram_message(alert)
                    else:
                        # Multiple alerts of same level
                        emoji = self._get_level_emoji(level)
                        message = f"{emoji} <b>{len(level_alerts)} {level.upper()} Alerts</b>\n\n"
                        for i, alert in enumerate(level_alerts[:5], 1):  # Max 5 alerts in summary
                            message += f"{i}. {alert['title']}: {alert['message']}\n"

                        if len(level_alerts) > 5:
                            message += f"\n... and {len(level_alerts) - 5} more alerts"

                    # Send message
                    payload = {
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True
                    }

                    async with session.post(f"{base_url}/sendMessage", json=payload) as response:
                        if response.status != 200:
                            logger.error(f"Failed to send Telegram alert: {response.status}")

        except Exception as e:
            logger.error(f"Error sending Telegram alerts: {e}")

    def _format_telegram_message(self, alert: Dict[str, Any]) -> str:
        """Format alert for Telegram message"""

        emoji = self._get_level_emoji(alert['level'])
        title = alert['title']
        message = alert['message']

        telegram_message = f"{emoji} <b>{title}</b>\n{message}"

        # Add details for critical/warning alerts
        if alert['level'] in ['critical', 'warning']:
            details = alert.get('details', {})
            if details:
                telegram_message += "\n\n<i>Details:</i>"
                for key, value in list(details.items())[:3]:  # Max 3 details
                    if isinstance(value, float):
                        telegram_message += f"\n{key}: {value:.3f}"
                    else:
                        telegram_message += f"\n{key}: {value}"

        return telegram_message

    def _get_level_emoji(self, level: str) -> str:
        """Get emoji for alert level"""

        emoji_map = {
            'critical': '🚨',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }

        return emoji_map.get(level, '📢')

    def get_alert_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get alert summary for specified time period"""

        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        recent_alerts = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert['timestamp']) >= cutoff_time
        ]

        # Count by level
        level_counts = {}
        for alert in recent_alerts:
            level = alert['level']
            level_counts[level] = level_counts.get(level, 0) + 1

        # Count by type
        type_counts = {}
        for alert in recent_alerts:
            alert_type = alert['type']
            type_counts[alert_type] = type_counts.get(alert_type, 0) + 1

        return {
            "total_alerts": len(recent_alerts),
            "alerts_by_level": level_counts,
            "alerts_by_type": type_counts,
            "period_hours": hours_back,
            "most_recent_alert": recent_alerts[-1] if recent_alerts else None,
            "critical_alerts": [alert for alert in recent_alerts if alert['level'] == 'critical']
        }

    def update_alert_thresholds(self, new_thresholds: Dict[str, Any]):
        """Update alert thresholds"""

        self.alert_thresholds.update(new_thresholds)
        logger.info(f"Updated alert thresholds: {self.alert_thresholds}")

    async def run_alert_monitoring_loop(self, check_interval_minutes: int = 15):
        """Run continuous alert monitoring loop"""

        logger.info(f"Starting alert monitoring loop (check every {check_interval_minutes} minutes)")

        while True:
            try:
                alerts = await self.check_for_alerts()

                if alerts:
                    logger.info(f"Generated {len(alerts)} alerts in monitoring cycle")
                else:
                    logger.debug("No alerts generated in monitoring cycle")

                await asyncio.sleep(check_interval_minutes * 60)

            except Exception as e:
                logger.error(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying


async def run_market_maker_alerts(detector: MarketMakerDetector):
    """Run market maker alert system"""
    alert_system = MarketMakerAlertSystem(detector)

    # Run one-time alert check
    alerts = await alert_system.check_for_alerts()

    if alerts:
        print(f"🚨 Generated {len(alerts)} market maker alerts:")
        for alert in alerts:
            print(f"  {alert['level'].upper()}: {alert['title']}")
    else:
        print("✅ No market maker alerts at this time")

    return alerts


if __name__ == "__main__":
    import asyncio

    async def main():
        detector = MarketMakerDetector(settings)
        await run_market_maker_alerts(detector)

    asyncio.run(main())
