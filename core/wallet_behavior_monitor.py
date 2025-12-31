"""
Wallet Behavior Monitor for Real-Time Adaptation

This module implements real-time wallet behavior tracking to detect
significant changes in trading patterns and adapt strategy accordingly.

Key Features:
- Win rate change detection
- Position size change detection
- Category shift detection
- Risk increase detection
- Automatic wallet rotation based on 7-day performance

Author: Polymarket Copy Bot Team
Date: 2025-12-27
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from utils.alerts import send_telegram_alert
from utils.helpers import BoundedCache

from loguru import logger


@dataclass
class BehaviorChange:
    """Detected behavior change for a wallet"""

    wallet_address: str
    change_type: str  # WIN_RATE_DROP, WIN_RATE_GAIN, RISK_INCREASE, CATEGORY_SHIFT, ETC
    previous_value: float
    current_value: float
    magnitude: float
    threshold: float
    detection_time: float
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    recommended_action: str
    context: Dict[str, Any]


@dataclass
class WalletPerformanceWindow:
    """Performance metrics over a time window"""

    window_start: float
    window_end: float
    trade_count: int
    total_profit: Decimal
    total_loss: Decimal
    win_rate: float
    avg_position_size: Decimal
    max_position_size: Decimal
    categories: Set[str]
    volatility: float
    sharpe_ratio: float


@dataclass
class WalletRotationDecision:
    """Decision to rotate wallet in or out of portfolio"""

    wallet_address: str
    action: str  # ADD, REMOVE, MAINTAIN
    reason: str
    current_score: float
    previous_score: float
    score_change: float
    performance_window: float  # Days
    timestamp: float


class WalletBehaviorMonitor:
    """
    Real-time wallet behavior monitor.

    This monitor implements production-ready strategy for tracking
    wallet behavior changes and automatically rotating wallets
    based on performance degradation.

    Thread Safety:
        Uses asyncio locks for thread-safe operations
    """

    # Behavior change thresholds
    WIN_RATE_CHANGE_THRESHOLD = 0.15  # 15% change
    POSITION_SIZE_CHANGE_THRESHOLD = 2.0  # 2x change
    RISK_INCREASE_THRESHOLD = 0.2  # 20% volatility increase
    VOLATILITY_THRESHOLD = 0.30  # 30% max volatility

    # Rotation thresholds
    SCORE_DECLINE_THRESHOLD = 1.0  # 1.0 point decline
    MIN_ROTATION_SCORE_THRESHOLD = 5.0  # Below this, consider removal
    PERFORMANCE_WINDOW_DAYS = 7  # 7-day performance window
    MIN_TRADES_FOR_ROTATION = 10  # Minimum trades before rotation
    COOLDOWN_DAYS = 7  # Days before reconsidering removed wallet

    # Alert thresholds
    ALERT_ON_CRITICAL_CHANGES = True
    ALERT_ON_HIGH_CHANGES = True
    ALERT_DEDUPLICATION_SECONDS = 3600  # 1 hour

    def __init__(
        self,
        cache_ttl_seconds: int = 86400 * 7,  # 7 days
        max_cache_size: int = 5000,
    ) -> None:
        """
        Initialize wallet behavior monitor.

        Args:
            cache_ttl_seconds: Time-to-live for cached behavior data
            max_cache_size: Maximum number of cached wallets
        """
        # Store historical behavior snapshots
        self._behavior_history: BoundedCache = BoundedCache(
            max_size=max_cache_size,
            ttl_seconds=cache_ttl_seconds,
            memory_threshold_mb=200.0,
            cleanup_interval_seconds=3600,
        )

        # Store performance windows
        self._performance_windows: BoundedCache = BoundedCache(
            max_size=max_cache_size,
            ttl_seconds=cache_ttl_seconds,
            memory_threshold_mb=200.0,
            cleanup_interval_seconds=3600,
        )

        # Track rotation decisions
        self._rotation_history: BoundedCache = BoundedCache(
            max_size=1000,
            ttl_seconds=86400 * 30,  # 30 days
            memory_threshold_mb=50.0,
            cleanup_interval_seconds=7200,
        )

        # Alert deduplication
        self._alert_history: BoundedCache = BoundedCache(
            max_size=500,
            ttl_seconds=self.ALERT_DEDUPLICATION_SECONDS,
            memory_threshold_mb=10.0,
            cleanup_interval_seconds=300,
        )

        # Track cooldown periods
        self._cooldown_periods: BoundedCache = BoundedCache(
            max_size=500,
            ttl_seconds=86400 * 14,  # 14 days
            memory_threshold_mb=20.0,
            cleanup_interval_seconds=3600,
        )

        self._state_lock = asyncio.Lock()

        logger.info("WalletBehaviorMonitor initialized")

    async def monitor_wallet(
        self, wallet_address: str, new_metrics: Dict[str, Any]
    ) -> List[BehaviorChange]:
        """
        Monitor wallet for significant behavior changes.

        Args:
            wallet_address: Wallet to monitor
            new_metrics: New performance metrics

        Returns:
            List of detected behavior changes
        """
        try:
            async with self._state_lock:
                detected_changes = []

                # Get historical baseline
                baseline_key = f"baseline_{wallet_address}"
                historical_metrics = self._behavior_history.get(baseline_key)

                if not historical_metrics:
                    # First time seeing this wallet - establish baseline
                    logger.info(
                        f"Establishing baseline for wallet {wallet_address[-6:]}"
                    )
                    self._behavior_history.set(baseline_key, new_metrics)

                    # Initialize performance window
                    await self._initialize_performance_window(
                        wallet_address, new_metrics
                    )

                    return detected_changes

                # Compare metrics and detect changes
                changes = self._compare_metrics(
                    wallet_address, historical_metrics, new_metrics
                )
                detected_changes.extend(changes)

                # Update baseline if significant changes detected
                if any(change.severity in ["HIGH", "CRITICAL"] for change in changes):
                    logger.info(
                        f"Updating baseline for {wallet_address[-6:]} due to significant changes"
                    )
                    self._behavior_history.set(baseline_key, new_metrics)

                # Update performance window
                await self._update_performance_window(wallet_address, new_metrics)

                # Send alerts for critical/high severity changes
                for change in changes:
                    if (
                        change.severity in ["CRITICAL", "HIGH"]
                        and self.ALERT_ON_CRITICAL_CHANGES
                    ):
                        await self._send_behavior_alert(change)
                    elif change.severity == "HIGH" and self.ALERT_ON_HIGH_CHANGES:
                        await self._send_behavior_alert(change)

                # Check for rotation eligibility
                rotation_decision = await self._evaluate_rotation_eligibility(
                    wallet_address, new_metrics
                )

                if rotation_decision:
                    await self._handle_rotation_decision(rotation_decision)

                return detected_changes

        except Exception as e:
            logger.exception(f"Error monitoring wallet {wallet_address}: {e}")
            return []

    def _compare_metrics(
        self,
        wallet_address: str,
        historical: Dict[str, Any],
        current: Dict[str, Any],
    ) -> List[BehaviorChange]:
        """
        Compare historical and current metrics to detect changes.

        Args:
            wallet_address: Wallet address
            historical: Historical baseline metrics
            current: Current metrics

        Returns:
            List of detected behavior changes
        """
        changes = []
        detection_time = time.time()

        try:
            # 1. Win rate change
            historical_win_rate = historical.get("win_rate", 0.5)
            current_win_rate = current.get("win_rate", 0.5)
            win_rate_change = current_win_rate - historical_win_rate

            if abs(win_rate_change) >= self.WIN_RATE_CHANGE_THRESHOLD:
                change_type = (
                    "WIN_RATE_GAIN" if win_rate_change > 0 else "WIN_RATE_DROP"
                )
                severity = (
                    "CRITICAL"
                    if abs(win_rate_change) >= 0.25
                    else "HIGH"
                    if abs(win_rate_change) >= 0.20
                    else "MEDIUM"
                )

                changes.append(
                    BehaviorChange(
                        wallet_address=wallet_address,
                        change_type=change_type,
                        previous_value=historical_win_rate,
                        current_value=current_win_rate,
                        magnitude=abs(win_rate_change),
                        threshold=self.WIN_RATE_CHANGE_THRESHOLD,
                        detection_time=detection_time,
                        severity=severity,
                        recommended_action=self._get_win_rate_action(
                            change_type, severity
                        ),
                        context={
                            "historical_win_rate": historical_win_rate,
                            "current_win_rate": current_win_rate,
                        },
                    )
                )

            # 2. Position size change
            historical_avg_size = Decimal(str(historical.get("avg_position_size", 100)))
            current_avg_size = Decimal(str(current.get("avg_position_size", 100)))

            if historical_avg_size > 0:
                size_change = float(current_avg_size / historical_avg_size)

                if size_change >= self.POSITION_SIZE_CHANGE_THRESHOLD:
                    severity = (
                        "CRITICAL"
                        if size_change >= 3.0
                        else "HIGH"
                        if size_change >= 2.5
                        else "MEDIUM"
                    )

                    changes.append(
                        BehaviorChange(
                            wallet_address=wallet_address,
                            change_type="RISK_INCREASE",
                            previous_value=float(historical_avg_size),
                            current_value=float(current_avg_size),
                            magnitude=size_change,
                            threshold=self.POSITION_SIZE_CHANGE_THRESHOLD,
                            detection_time=detection_time,
                            severity=severity,
                            recommended_action=self._get_position_size_action(severity),
                            context={
                                "historical_size": float(historical_avg_size),
                                "current_size": float(current_avg_size),
                            },
                        )
                    )

            # 3. Category shift
            historical_categories = set(historical.get("trade_categories", []))
            current_categories = set(current.get("trade_categories", []))
            category_shift = current_categories - historical_categories

            if category_shift:
                severity = "HIGH" if len(category_shift) > 2 else "MEDIUM"

                changes.append(
                    BehaviorChange(
                        wallet_address=wallet_address,
                        change_type="CATEGORY_SHIFT",
                        previous_value=len(historical_categories),
                        current_value=len(current_categories),
                        magnitude=len(category_shift),
                        threshold=1,
                        detection_time=detection_time,
                        severity=severity,
                        recommended_action=self._get_category_shift_action(
                            len(category_shift), severity
                        ),
                        context={
                            "historical_categories": list(historical_categories),
                            "current_categories": list(current_categories),
                            "new_categories": list(category_shift),
                        },
                    )
                )

            # 4. Volatility increase
            historical_volatility = historical.get("volatility", 0.15)
            current_volatility = current.get("volatility", 0.15)
            volatility_increase = current_volatility - historical_volatility

            if volatility_increase >= self.RISK_INCREASE_THRESHOLD:
                severity = (
                    "CRITICAL"
                    if current_volatility >= self.VOLATILITY_THRESHOLD
                    else "HIGH"
                    if volatility_increase >= 0.25
                    else "MEDIUM"
                )

                changes.append(
                    BehaviorChange(
                        wallet_address=wallet_address,
                        change_type="VOLATILITY_INCREASE",
                        previous_value=historical_volatility,
                        current_value=current_volatility,
                        magnitude=volatility_increase,
                        threshold=self.RISK_INCREASE_THRESHOLD,
                        detection_time=detection_time,
                        severity=severity,
                        recommended_action=self._get_volatility_action(severity),
                        context={
                            "historical_volatility": historical_volatility,
                            "current_volatility": current_volatility,
                        },
                    )
                )

            return changes

        except Exception as e:
            logger.error(f"Error comparing metrics for {wallet_address[-6:]}: {e}")
            return []

    def _get_win_rate_action(self, change_type: str, severity: str) -> str:
        """Get recommended action for win rate change"""
        if change_type == "WIN_RATE_DROP":
            if severity == "CRITICAL":
                return "Remove from portfolio immediately"
            elif severity == "HIGH":
                return "Reduce position sizes by 50%"
            else:
                return "Monitor closely for 24 hours"
        else:  # WIN_RATE_GAIN
            return "Consider increasing position sizes"

    def _get_position_size_action(self, severity: str) -> str:
        """Get recommended action for position size change"""
        if severity == "CRITICAL":
            return "Remove from portfolio immediately"
        elif severity == "HIGH":
            return "Reduce position sizes by 75%"
        else:
            return "Reduce position sizes by 50%"

    def _get_category_shift_action(self, shift_count: int, severity: str) -> str:
        """Get recommended action for category shift"""
        if severity == "HIGH":
            return "Monitor closely - potential strategy change"
        else:
            return "Note category expansion - reassess domain expertise"

    def _get_volatility_action(self, severity: str) -> str:
        """Get recommended action for volatility increase"""
        if severity == "CRITICAL":
            return "Remove from portfolio - excessive risk"
        elif severity == "HIGH":
            return "Reduce position sizes by 50%"
        else:
            return "Reduce position sizes by 25%"

    async def _initialize_performance_window(
        self, wallet_address: str, metrics: Dict[str, Any]
    ) -> None:
        """Initialize performance window for a wallet"""
        try:
            window = WalletPerformanceWindow(
                window_start=time.time(),
                window_end=time.time(),
                trade_count=metrics.get("trade_count", 0),
                total_profit=Decimal(str(metrics.get("total_profit", 0))),
                total_loss=Decimal(str(abs(metrics.get("total_loss", 0)))),
                win_rate=metrics.get("win_rate", 0.5),
                avg_position_size=Decimal(str(metrics.get("avg_position_size", 100))),
                max_position_size=Decimal(str(metrics.get("max_position_size", 100))),
                categories=set(metrics.get("trade_categories", [])),
                volatility=metrics.get("volatility", 0.15),
                sharpe_ratio=metrics.get("sharpe_ratio", 0.0),
            )

            window_key = f"window_{wallet_address}"
            self._performance_windows.set(window_key, window)

        except Exception as e:
            logger.error(f"Error initializing performance window: {e}")

    async def _update_performance_window(
        self, wallet_address: str, metrics: Dict[str, Any]
    ) -> None:
        """Update performance window with new metrics"""
        try:
            window_key = f"window_{wallet_address}"
            window = self._performance_windows.get(window_key)

            if not window:
                await self._initialize_performance_window(wallet_address, metrics)
                return

            # Update window with new metrics
            window.window_end = time.time()
            window.trade_count += metrics.get("new_trades", 0)
            window.total_profit += Decimal(str(metrics.get("new_profit", 0)))
            window.total_loss += Decimal(str(abs(metrics.get("new_loss", 0))))
            window.win_rate = metrics.get("win_rate", window.win_rate)
            window.avg_position_size = Decimal(
                str(metrics.get("avg_position_size", 100))
            )
            window.max_position_size = Decimal(
                str(
                    max(
                        float(window.max_position_size),
                        metrics.get("max_position_size", 100),
                    )
                )
            )
            window.categories.update(metrics.get("trade_categories", []))
            window.volatility = metrics.get("volatility", window.volatility)
            window.sharpe_ratio = metrics.get("sharpe_ratio", window.sharpe_ratio)

            # Update cache
            self._performance_windows.set(window_key, window)

        except Exception as e:
            logger.error(f"Error updating performance window: {e}")

    async def _evaluate_rotation_eligibility(
        self, wallet_address: str, current_metrics: Dict[str, Any]
    ) -> Optional[WalletRotationDecision]:
        """
        Evaluate if wallet should be rotated in or out.

        Args:
            wallet_address: Wallet to evaluate
            current_metrics: Current performance metrics

        Returns:
            RotationDecision if action needed, None otherwise
        """
        try:
            # Get current quality score
            current_score = current_metrics.get("total_score", 0)
            previous_score = current_metrics.get("previous_score", current_score)
            score_change = current_score - previous_score

            # Check cooldown period
            cooldown_key = f"cooldown_{wallet_address}"
            cooldown_until = self._cooldown_periods.get(cooldown_key, 0)

            if time.time() < cooldown_until:
                logger.debug(
                    f"Wallet {wallet_address[-6:]} in cooldown until "
                    f"{datetime.fromtimestamp(cooldown_until, tz=timezone.utc)}"
                )
                return None

            # Get performance window
            window_key = f"window_{wallet_address}"
            window = self._performance_windows.get(window_key)

            if not window:
                return None

            # Check minimum trades
            if window.trade_count < self.MIN_TRADES_FOR_ROTATION:
                return None

            # Calculate window duration in days
            window_duration = (window.window_end - window.window_start) / 86400

            # Check for score decline (removal criteria)
            if (
                score_change <= -self.SCORE_DECLINE_THRESHOLD
                and current_score < self.MIN_ROTATION_SCORE_THRESHOLD
            ):
                logger.warning(
                    f"🔄 REMOVING wallet {wallet_address[-6:]}: "
                    f"Score declined from {previous_score:.2f} to {current_score:.2f}"
                )

                decision = WalletRotationDecision(
                    wallet_address=wallet_address,
                    action="REMOVE",
                    reason=f"Score decline: {score_change:.2f}",
                    current_score=current_score,
                    previous_score=previous_score,
                    score_change=score_change,
                    performance_window=window_duration,
                    timestamp=time.time(),
                )

                # Set cooldown
                self._cooldown_periods.set(
                    cooldown_key,
                    time.time() + (self.COOLDOWN_DAYS * 86400),
                )

                return decision

            # Check for significant improvement (add-back criteria)
            rotation_key = f"rotation_{wallet_address}"
            last_rotation = self._rotation_history.get(rotation_key)

            if (
                last_rotation
                and last_rotation.action == "REMOVE"
                and score_change >= self.SCORE_DECLINE_THRESHOLD
                and current_score >= self.MIN_ROTATION_SCORE_THRESHOLD + 1.0
            ):
                logger.info(
                    f"🔄 RE-ADDING wallet {wallet_address[-6:]}: "
                    f"Score improved from {last_rotation.current_score:.2f} to {current_score:.2f}"
                )

                decision = WalletRotationDecision(
                    wallet_address=wallet_address,
                    action="ADD",
                    reason=f"Score recovery: {score_change:.2f}",
                    current_score=current_score,
                    previous_score=last_rotation.current_score,
                    score_change=score_change,
                    performance_window=window_duration,
                    timestamp=time.time(),
                )

                # Clear cooldown
                self._cooldown_periods.delete(cooldown_key)

                return decision

            return None

        except Exception as e:
            logger.error(f"Error evaluating rotation eligibility: {e}")
            return None

    async def _handle_rotation_decision(self, decision: WalletRotationDecision) -> None:
        """Handle wallet rotation decision"""
        try:
            # Store in rotation history
            rotation_key = f"rotation_{decision.wallet_address}"
            self._rotation_history.set(rotation_key, decision)

            # Send alert
            alert_message = self._format_rotation_alert(decision)
            await send_telegram_alert(alert_message)

            # Log decision
            logger.info(
                f"🔄 Rotation Decision: {decision.action} {decision.wallet_address[-6:]} - "
                f"{decision.reason}"
            )

        except Exception as e:
            logger.error(f"Error handling rotation decision: {e}")

    def _format_rotation_alert(self, decision: WalletRotationDecision) -> str:
        """Format rotation alert message"""
        emoji = "🔴" if decision.action == "REMOVE" else "🟢"

        return (
            f"{emoji} **Wallet Rotation Alert**\n"
            f"Action: {decision.action}\n"
            f"Wallet: `{decision.wallet_address[-6:]}`\n"
            f"Reason: {decision.reason}\n"
            f"Score: {decision.previous_score:.2f} → {decision.current_score:.2f} "
            f"({decision.score_change:+.2f})\n"
            f"Performance Window: {decision.performance_window:.1f} days"
        )

    async def _send_behavior_alert(self, change: BehaviorChange) -> None:
        """Send alert for behavior change"""
        try:
            # Deduplicate alerts
            alert_key = f"alert_{change.wallet_address}_{change.change_type}"
            last_alert = self._alert_history.get(alert_key, 0)

            if time.time() - last_alert < self.ALERT_DEDUPLICATION_SECONDS:
                return

            # Send alert
            alert_message = self._format_behavior_alert(change)
            await send_telegram_alert(alert_message)

            # Record alert
            self._alert_history.set(alert_key, time.time())

        except Exception as e:
            logger.error(f"Error sending behavior alert: {e}")

    def _format_behavior_alert(self, change: BehaviorChange) -> str:
        """Format behavior change alert message"""
        emoji = {
            "CRITICAL": "🚨",
            "HIGH": "⚠️",
            "MEDIUM": "ℹ️",
            "LOW": "💡",
        }.get(change.severity, "ℹ️")

        return (
            f"{emoji} **Wallet Behavior Alert**\n"
            f"Wallet: `{change.wallet_address[-6:]}`\n"
            f"Change: {change.change_type}\n"
            f"Severity: {change.severity}\n"
            f"Value: {change.previous_value:.3f} → {change.current_value:.3f} "
            f"({change.magnitude:+.3f})\n"
            f"Recommended: {change.recommended_action}"
        )

    async def get_wallet_summary(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive summary of wallet behavior.

        Args:
            wallet_address: Wallet to summarize

        Returns:
            Dictionary with wallet behavior summary
        """
        try:
            # Get performance window
            window_key = f"window_{wallet_address}"
            window = self._performance_windows.get(window_key)

            if not window:
                return None

            # Get rotation history
            rotation_key = f"rotation_{wallet_address}"
            last_rotation = self._rotation_history.get(rotation_key)

            # Check cooldown
            cooldown_key = f"cooldown_{wallet_address}"
            cooldown_until = self._cooldown_periods.get(cooldown_key, 0)
            in_cooldown = time.time() < cooldown_until

            # Calculate performance metrics
            window_duration_days = (window.window_end - window.window_start) / 86400
            profit_loss = window.total_profit - window.total_loss
            profit_loss_pct = float(profit_loss) if float(profit_loss) > 0 else 0.0

            return {
                "wallet_address": wallet_address,
                "performance_window_days": window_duration_days,
                "trade_count": window.trade_count,
                "win_rate": window.win_rate,
                "profit_loss_usdc": float(profit_loss),
                "profit_loss_pct": profit_loss_pct,
                "avg_position_size": float(window.avg_position_size),
                "max_position_size": float(window.max_position_size),
                "categories_traded": list(window.categories),
                "volatility": window.volatility,
                "sharpe_ratio": window.sharpe_ratio,
                "last_rotation": last_rotation.__dict__ if last_rotation else None,
                "in_cooldown": in_cooldown,
                "cooldown_until": (
                    datetime.fromtimestamp(cooldown_until, tz=timezone.utc).isoformat()
                    if in_cooldown
                    else None
                ),
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Error getting wallet summary: {e}")
            return None

    async def get_monitor_summary(self) -> Dict[str, Any]:
        """
        Get summary of all monitored wallets.

        Returns:
            Dictionary with monitoring statistics
        """
        try:
            # Count wallets by status
            total_wallets = 0
            in_cooldown = 0
            recent_rotations = 0

            # Performance statistics
            total_trades = 0
            total_profit_loss = Decimal("0.00")
            avg_win_rate = 0.0
            avg_volatility = 0.0

            # Scan all windows
            for cache_key in self._performance_windows._cache.keys():
                if cache_key.startswith("window_"):
                    total_wallets += 1
                    window = self._performance_windows.get(cache_key)

                    if window:
                        total_trades += window.trade_count
                        total_profit_loss += window.total_profit - window.total_loss
                        avg_win_rate += window.win_rate
                        avg_volatility += window.volatility

            # Check cooldowns and rotations
            for cache_key in self._cooldown_periods._cache.keys():
                if cache_key.startswith("cooldown_"):
                    cooldown_until = self._cooldown_periods.get(cache_key, 0)
                    if time.time() < cooldown_until:
                        in_cooldown += 1

            # Count recent rotations (last 7 days)
            cutoff_time = time.time() - (86400 * 7)
            for cache_key in self._rotation_history._cache.keys():
                if cache_key.startswith("rotation_"):
                    rotation = self._rotation_history.get(cache_key)
                    if rotation and rotation.timestamp > cutoff_time:
                        recent_rotations += 1

            # Calculate averages
            if total_wallets > 0:
                avg_win_rate /= total_wallets
                avg_volatility /= total_wallets

            return {
                "total_monitored_wallets": total_wallets,
                "wallets_in_cooldown": in_cooldown,
                "rotations_last_7_days": recent_rotations,
                "total_trades": total_trades,
                "total_profit_loss": float(total_profit_loss),
                "avg_win_rate": avg_win_rate,
                "avg_volatility": avg_volatility,
                "cache_stats": {
                    "behavior_history": self._behavior_history.get_stats(),
                    "performance_windows": self._performance_windows.get_stats(),
                    "rotation_history": self._rotation_history.get_stats(),
                },
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Error getting monitor summary: {e}")
            return {}

    async def cleanup(self) -> None:
        """Clean up expired cache entries"""
        try:
            self._behavior_history.cleanup()
            self._performance_windows.cleanup()
            self._rotation_history.cleanup()
            self._alert_history.cleanup()
            self._cooldown_periods.cleanup()
            logger.info("WalletBehaviorMonitor cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Example usage
async def example_usage():
    """Example of how to use WalletBehaviorMonitor"""
    monitor = WalletBehaviorMonitor()

    # Simulate monitoring a wallet
    wallet_address = "0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9"

    # First metrics (establish baseline)
    baseline_metrics = {
        "win_rate": 0.68,
        "avg_position_size": 150,
        "trade_categories": ["politics", "economics"],
        "volatility": 0.15,
        "trade_count": 50,
        "total_profit": 500,
        "total_loss": 200,
        "sharpe_ratio": 1.2,
    }

    changes = await monitor.monitor_wallet(wallet_address, baseline_metrics)
    logger.info(f"Baseline established. Changes detected: {len(changes)}")

    # Simulate performance degradation
    degraded_metrics = {
        "win_rate": 0.45,  # 23% drop
        "avg_position_size": 300,  # 2x increase
        "trade_categories": [
            "politics",
            "economics",
            "crypto",
            "sports",
        ],  # New categories
        "volatility": 0.25,  # 10% increase
        "new_trades": 20,
        "new_profit": 100,
        "new_loss": 150,
        "previous_score": 8.5,
        "total_score": 6.8,  # 1.7 point decline
    }

    changes = await monitor.monitor_wallet(wallet_address, degraded_metrics)
    logger.info(f"Degradation detected. Changes: {len(changes)}")

    for change in changes:
        logger.info(f"\n  Change: {change.change_type}")
        logger.info(f"    Severity: {change.severity}")
        logger.info(f"    Magnitude: {change.magnitude:.3f}")
        logger.info(f"    Action: {change.recommended_action}")

    # Get wallet summary
    summary = await monitor.get_wallet_summary(wallet_address)
    logger.info(f"\nWallet Summary: {summary}")

    # Get monitor summary
    monitor_summary = await monitor.get_monitor_summary()
    logger.info(f"\nMonitor Summary: {monitor_summary}")

    # Cleanup
    await monitor.cleanup()


if __name__ == "__main__":
    asyncio.run(example_usage())
