import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

from config.scanner_config import ScannerConfig, WalletScore
from scanners.wallet_analyzer import WalletAnalyzer
from utils.alerts import send_error_alert, send_telegram_alert
from utils.logger import get_logger

logger = get_logger(__name__)


class SimpleErrorCounter:
    """Simple error counter for scanner circuit breaker functionality"""

    def __init__(self, max_errors: int, reset_period_hours: int = 24) -> None:
        self.max_errors = max_errors
        self.reset_period_seconds = reset_period_hours * 3600
        self.error_count = 0
        self.last_reset_time = time.time()
        self._lock = threading.Lock()

    def record_error(self) -> None:
        """Record an error"""
        with self._lock:
            self.error_count += 1

    def reset(self) -> None:
        """Reset error count"""
        with self._lock:
            self.error_count = 0
            self.last_reset_time = time.time()

    def is_tripped(self) -> bool:
        """Check if circuit breaker is tripped"""
        with self._lock:
            # Auto-reset after reset period
            if time.time() - self.last_reset_time > self.reset_period_seconds:
                self.reset()
            return self.error_count >= self.max_errors

    @property
    def reset_time(self) -> float:
        """Get reset time"""
        return self.last_reset_time


class LeaderboardScanner:
    """Production-grade leaderboard scanner with circuit breakers and monitoring"""

    def __init__(self, config: ScannerConfig) -> None:
        self.config = config
        # Pass API failure callback to wallet analyzer
        self.wallet_analyzer = WalletAnalyzer(
            config, api_failure_callback=self._handle_api_failure
        )
        self.circuit_breaker = SimpleErrorCounter(
            max_errors=self.config.MAX_DAILY_SCANNER_ERRORS, reset_period_hours=24
        )

        # API failure tracking for intelligent degradation
        self.api_failure_count = 0
        self.fallback_mode = False
        self.fallback_mode_until = 0.0
        self.fallback_start_time = 0.0

        self.last_scan_results: List[WalletScore] = []
        self.last_scan_time = 0.0
        self.scan_lock = threading.Lock()
        self.is_running = False
        self.scan_thread = None

    def start_scanning(self) -> None:
        """Start continuous scanning in background thread"""
        if self.is_running:
            logger.warning("Scanner already running")
            return

        self.is_running = True
        self.scan_thread = threading.Thread(
            target=self._scan_loop, name="LeaderboardScanner", daemon=True
        )
        self.scan_thread.start()
        logger.info("Leaderboard scanner started successfully")

    def stop_scanning(self) -> None:
        """Stop the scanner gracefully"""
        self.is_running = False
        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join(timeout=5.0)
        logger.info("Leaderboard scanner stopped")

    def _scan_loop(self) -> None:
        """Main scanning loop with error handling and backoff"""
        while self.is_running:
            try:
                if self.circuit_breaker.is_tripped():
                    logger.warning(
                        "Scanner circuit breaker tripped. Waiting for reset..."
                    )
                    time.sleep(300)  # Wait 5 minutes before checking again
                    continue

                self.run_scan()

                # Wait for next scan interval
                time.sleep(self.config.SCAN_INTERVAL_HOURS * 3600)

            except Exception as e:
                logger.error(f"Critical error in scan loop: {e}")
                self.circuit_breaker.record_error()

                # Exponential backoff on errors
                error_count = self.circuit_breaker.error_count
                backoff_time = min(300, 30 * (2**error_count))  # Max 5 minutes
                logger.warning(f"Backing off for {backoff_time} seconds after error")
                time.sleep(backoff_time)

    def run_scan(self) -> List[WalletScore]:
        """Execute a single scan with locks and error handling"""
        with self.scan_lock:
            try:
                # Check if we should recover from fallback mode
                self._check_fallback_mode_recovery()

                logger.info("Starting leaderboard scan...")
                if self.fallback_mode:
                    logger.info("🔄 Operating in fallback mode due to API failures")
                start_time = time.time()

                # Run analysis
                results = self.wallet_analyzer.analyze_leaderboard_wallets()

                # Check if we're in fallback mode due to API issues
                if (
                    hasattr(self.wallet_analyzer, "polymarket_api")
                    and self.fallback_mode
                ):
                    logger.info(
                        "✅ Scan successful while in fallback mode - API may have recovered"
                    )

                # Store results
                self.last_scan_results = results
                self.last_scan_time = time.time()
                scan_duration = time.time() - start_time

                # Log results
                logger.info(f"Scan completed in {scan_duration:.2f} seconds")
                logger.info(f"Found {len(results)} qualified wallets:")
                for i, wallet in enumerate(results[:10], 1):  # Log top 10
                    logger.info(
                        f"{i}. {wallet.address[:8]}... - Score: {wallet.total_score:.3f}, "
                        f"ROI: {wallet.metrics.get('roi_30d', 0):.1f}%, "
                        f"Risk: {wallet.risk_score:.2f}"
                    )

                # Reset circuit breaker and API failure count on success
                self.circuit_breaker.reset()
                if not self.fallback_mode:
                    self.api_failure_count = max(
                        0, self.api_failure_count - 1
                    )  # Gradually reduce on success

                return results

            except Exception as e:
                logger.error(f"Scan failed: {e}")

                # Handle API-specific failures
                self._handle_scan_failure(e)

                # Also record general circuit breaker error
                self.circuit_breaker.record_error()
                raise

    def get_top_wallets(self) -> List[Dict[str, Any]]:
        """Get top wallets in format compatible with trading bot"""
        if not self.last_scan_results:
            logger.warning("No scan results available. Running scan now...")
            self.run_scan()

        top_wallets = []

        for wallet in self.last_scan_results[: self.config.MAX_WALLETS_TO_MONITOR]:
            top_wallets.append(
                {
                    "address": wallet.address,
                    "confidence_score": wallet.confidence_score,
                    "risk_score": wallet.risk_score,
                    "position_size_factor": self._calculate_position_size_factor(
                        wallet
                    ),
                    "metrics": wallet.metrics,
                }
            )

        return top_wallets

    def _calculate_position_size_factor(self, wallet_score: WalletScore) -> float:
        """Calculate position size factor based on wallet reliability"""
        # Base factor from confidence score
        base_factor = wallet_score.confidence_score

        # Risk adjustment
        risk_penalty = max(0, wallet_score.risk_score - 0.3) * 2  # Penalize high risk

        # Performance bonus
        performance_bonus = min(wallet_score.performance_score * 0.2, 0.1)

        final_factor = max(
            0.1, base_factor - risk_penalty + performance_bonus
        )  # Min 0.1x

        logger.debug(
            f"Position size factor for {wallet_score.address[:8]}: "
            f"base={base_factor:.2f}, risk_penalty={risk_penalty:.2f}, "
            f"performance_bonus={performance_bonus:.2f}, final={final_factor:.2f}"
        )

        return final_factor

    def _handle_api_failure(
        self, endpoint: str, error: Exception, attempt: int, max_attempts: int
    ) -> None:
        """Comprehensive API failure handling with escalation"""
        error_msg = str(error)[:200]
        logger.error(
            f"❌ API endpoint {endpoint} failed (attempt {attempt}/{max_attempts}): {error_msg}"
        )

        # Circuit breaker escalation
        self.api_failure_count += 1
        failure_severity = (
            "HIGH"
            if self.api_failure_count >= 3
            else "MEDIUM"
            if self.api_failure_count >= 2
            else "LOW"
        )

        # Send appropriate alert based on severity
        if self.api_failure_count == 1:
            asyncio.create_task(
                send_telegram_alert(
                    f"⚠️ API Warning: Endpoint {endpoint} failed\n"
                    f"Attempt: {attempt}/{max_attempts}\n"
                    f"Error: {error_msg[:50]}..."
                )
            )

        elif self.api_failure_count >= 3:
            asyncio.create_task(
                send_error_alert(
                    f"🚨 CRITICAL API FAILURE - {failure_severity} SEVERITY",
                    {
                        "endpoint": endpoint,
                        "error": error_msg,
                        "failure_count": self.api_failure_count,
                        "fallback_mode_activated": self.fallback_mode,
                        "scanner_status": self.get_scan_status(),
                        "recommended_action": "Investigate Polymarket API status and update endpoint configuration",
                    },
                )
            )

        # Auto-escalation to fallback mode
        if self.api_failure_count >= 3 and not self.fallback_mode:
            logger.critical(
                "🔥 Activating fallback mode due to persistent API failures"
            )
            self.fallback_mode = True
            self.fallback_start_time = time.time()
            asyncio.create_task(
                send_telegram_alert(
                    f"🔥 FALLBACK MODE ACTIVATED\n"
                    f"Reason: {self.api_failure_count} consecutive API failures\n"
                    f"Fallback wallets: {len(self._get_community_wallets())}\n"
                    f"Estimated duration: {self.config.FALLBACK_MODE_DURATION_HOURS} hours"
                )
            )

    def _handle_scan_failure(self, error: Exception) -> None:
        """Handle scan failures with intelligent degradation"""
        self.api_failure_count += 1

        if self.api_failure_count >= self.config.MAX_API_FAILURES:
            logger.warning(
                "🚨 API failure threshold exceeded. Activating fallback mode."
            )
            self.fallback_mode = True
            self.fallback_mode_until = time.time() + (
                self.config.FALLBACK_MODE_DURATION_HOURS * 3600
            )

            # Alert operations team
            asyncio.create_task(
                self.send_error_alert(
                    "API FAILURE THRESHOLD EXCEEDED",
                    {
                        "failure_count": self.api_failure_count,
                        "fallback_mode": True,
                        "estimated_recovery": datetime.now()
                        + timedelta(hours=self.config.FALLBACK_MODE_DURATION_HOURS),
                    },
                )
            )

    def _get_community_wallets(self) -> List[Dict[str, Any]]:
        """Get community-curated wallets for fallback mode"""
        try:
            # Use the wallet analyzer's community wallet method
            return self.wallet_analyzer._get_community_wallets()
        except Exception as e:
            logger.error(f"Error getting community wallets: {e}")
            # Return emergency fallback if community wallets fail
            return self.wallet_analyzer.polymarket_api._get_emergency_wallets()

    def _check_fallback_mode_recovery(self) -> None:
        """Check if fallback mode should be deactivated"""
        if self.fallback_mode and time.time() > self.fallback_mode_until:
            logger.info(
                "⏰ Fallback mode duration expired. Attempting to resume normal operations."
            )
            self.fallback_mode = False
            self.api_failure_count = 0  # Reset failure count to try again

    async def send_error_alert(self, title: str, details: Dict[str, Any]) -> None:
        """Send error alert (placeholder for actual alerting system)"""
        try:
            logger.error(f"ALERT: {title}")
            logger.error(f"Details: {details}")

            # TODO: Integrate with actual alerting system (Telegram, Slack, etc.)
            # await telegram_bot.send_message(f"🚨 {title}\n{json.dumps(details, indent=2, default=str)}")

        except Exception as e:
            logger.error(f"Failed to send error alert: {e}")

    def health_check(self) -> bool:
        """✅ Comprehensive health check for scanner"""
        try:
            # Check if scanner is running
            is_running = self.is_running

            # Check circuit breaker status
            circuit_ok = not self.circuit_breaker.is_tripped()

            # Check last scan was recent (within 2x scan interval)
            recent_scan = (time.time() - self.last_scan_time) < (
                self.config.SCAN_INTERVAL_HOURS * 3600 * 2
            )

            # Check we have valid scan results
            has_results = len(self.last_scan_results) > 0

            # Check memory usage (if available)
            memory_ok = True
            if hasattr(self, "get_memory_usage"):
                memory_usage = self.get_memory_usage()
                memory_ok = memory_usage < self.config.MEMORY_LIMIT_MB

            # Determine overall health
            healthy = (
                is_running and circuit_ok and recent_scan and has_results and memory_ok
            )

            # Log detailed status
            status_details = {
                "running": is_running,
                "circuit_ok": circuit_ok,
                "recent_scan": recent_scan,
                "has_results": has_results,
                "memory_ok": memory_ok,
            }

            logger.debug(
                f"Scanner Health: {'✅ HEALTHY' if healthy else '❌ UNHEALTHY'} - Details: {status_details}"
            )

            if not healthy:
                # Send alert if critical components are failing
                if not (circuit_ok and has_results):
                    from utils.alerts import send_error_alert

                    asyncio.create_task(
                        send_error_alert(
                            "Scanner Health Check Failed",
                            {
                                "status": "UNHEALTHY",
                                "details": status_details,
                                "last_scan_time": self.last_scan_time,
                                "error_count": self.circuit_breaker.error_count,
                            },
                        )
                    )

            return healthy

        except Exception as e:
            logger.error(f"Scanner health check failed: {str(e)[:150]}")
            return False

    def get_scan_status(self) -> Dict[str, Any]:
        """Get current scanner status for monitoring"""
        return {
            "is_running": self.is_running,
            "last_scan_time": time.time() if self.last_scan_results else 0,
            "wallet_count": len(self.last_scan_results),
            "circuit_breaker": {
                "tripped": self.circuit_breaker.is_tripped(),
                "error_count": self.circuit_breaker.error_count,
                "reset_time": self.circuit_breaker.reset_time,
            },
            "api_failure_tracking": {
                "api_failure_count": self.api_failure_count,
                "fallback_mode": self.fallback_mode,
                "fallback_mode_until": self.fallback_mode_until,
                "time_until_recovery": (
                    max(0, self.fallback_mode_until - time.time())
                    if self.fallback_mode
                    else 0
                ),
            },
            "top_wallets": [w.address for w in self.last_scan_results[:5]],
        }
