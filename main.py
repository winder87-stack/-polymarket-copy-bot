#!/usr/bin/env python3
"""
Polymarket Copy Trading Bot - Main Application

This is the main entry point for the Polymarket automated copy trading bot.
The bot monitors specified wallet addresses for trading activity on Polymarket
and automatically executes copy trades based on configurable risk management rules.

Architecture:
- WalletMonitor: Scans blockchain transactions for trading activity
- TradeExecutor: Executes copy trades with risk management
- PolymarketClient: Interfaces with Polymarket's CLOB API
- AlertManager: Handles Telegram notifications and monitoring
- LeaderboardScanner: Automatically di                f"✅ Production monitoring server started"
                f"{' (dashboard: http://localhost:' + str(monitoring_config.dashboard_port) + ')' }"
                 if monitoring_config.dashboard_enabled else ''}"
                f"{' (metrics: http://localhost:' + str(monitoring_config.metrics_port) + ')' }"
                 if monitoring_config.metrics_enabled else ''}"
            )"ers top-performing wallets to copy

Key Features:
- Real-time wallet monitoring with caching and rate limiting
- Automated risk management (position sizing, stop-loss, take-profit)
- Circuit breaker protection against excessive losses
- Performance monitoring and alerting
- Graceful error handling and recovery
- Leaderboard scanner for automatic wallet discovery

Environment Variables Required:
- PRIVATE_KEY: Ethereum private key for trading
- POLYGON_RPC_URL: Polygon RPC endpoint
- TELEGRAM_BOT_TOKEN: Telegram bot token for alerts
- TELEGRAM_CHAT_ID: Telegram chat ID for notifications
- POLYGONSCAN_API_KEY: PolygonScan API key for transaction monitoring
- POLYMARKET_API_KEY: Polymarket API key for leaderboard data

Author: Polymarket Bot Team
Version: 1.0.1
License: MIT
"""

import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


from config import (
    get_settings,
    validate_settings,
    get_scanner_config,
    validate_scanner_config,
)
from core.clob_client import PolymarketClient
from core.endgame_sweeper import EndgameSweeper
from core.trade_executor import TradeExecutor
from core.wallet_monitor import WalletMonitor
from scanners.leaderboard_scanner import LeaderboardScanner
from utils.alerts import send_error_alert, send_performance_report, send_telegram_alert
from utils.helpers import get_environment_info
from utils.logging_config import setup_logging
from utils.security import generate_session_id

# Initialize logging
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir="logs",
    json_logging=os.getenv("JSON_LOGGING", "true").lower() == "true",
)

logger = logging.getLogger(__name__)


class PolymarketCopyBot:
    """
    Main bot controller for Polymarket copy trading operations.

    This class orchestrates the entire copy trading workflow:
    1. Scans leaderboard for top-performing wallets
    2. Monitors target wallets for trading activity
    3. Applies risk management rules to trade signals
    4. Executes copy trades on Polymarket
    5. Manages open positions (stop-loss, take-profit)
    6. Provides monitoring, alerting, and performance reporting

    Attributes:
        settings: Application configuration settings
        scanner_config: Leaderboard scanner configuration
        running: Flag indicating if the bot is actively running
        start_time: Timestamp when the bot was started
        session_id: Unique identifier for this bot session
        performance_stats: Real-time performance metrics

    Components:
        clob_client: Interface to Polymarket's Conditional Order Book
        wallet_monitor: Blockchain transaction monitoring service
        trade_executor: Trade execution and position management engine
        leaderboard_scanner: Automated wallet discovery system
    """

    def __init__(self) -> None:
        """
        Initialize the Polymarket Copy Trading Bot.

        Sets up all core components, performance monitoring, and configuration.
        The bot is initialized in a stopped state and must be started with start().
        """
        self.settings = get_settings()
        self.scanner_config = get_scanner_config()
        self.running = False
        self.start_time = datetime.now(timezone.utc)
        self.last_health_check: Optional[datetime] = None
        self.last_wallet_update: float = 0
        self.wallet_update_interval: float = 3600.0  # 1 hour
        self.session_id = generate_session_id()
        self.target_wallets: List[Dict[str, Any]] = []

        # Core components - initialized during startup
        self.clob_client: Optional[PolymarketClient] = None
        self.wallet_monitor: Optional[WalletMonitor] = None
        self.trade_executor: Optional[TradeExecutor] = None
        self.leaderboard_scanner: Optional[LeaderboardScanner] = None
        self.endgame_sweeper: Optional[EndgameSweeper] = None

        # Production monitoring server (MCP)
        self.monitoring_server: Optional[Any] = None
        self.monitoring_task: Optional[asyncio.Task] = None

        # Performance monitoring
        self.performance_stats: Dict[str, Any] = {
            "cycles_completed": 0,
            "trades_processed": 0,
            "trades_successful": 0,
            "total_cycle_time": 0.0,
            "avg_cycle_time": 0.0,
            "last_cycle_time": 0.0,
            "uptime_seconds": 0.0,
            "memory_usage_mb": 0.0,
        }

        # Performance optimization settings
        self.max_concurrent_health_checks = 3
        self.performance_report_interval = 300  # 5 minutes
        self.last_performance_report: float = time.time()
        self.last_daily_reset: Optional[datetime] = None

        logger.info(
            f"🚀 Initialized Polymarket Copy Bot (Session ID: {self.session_id})"
        )

    async def initialize(self) -> bool:
        """
        Initialize all bot components and perform startup checks.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            logger.info("🚀 Initializing Polymarket Copy Bot components...")

            # Validate settings
            validate_settings()
            validate_scanner_config()

            # Initialize CLOB client
            self.clob_client = PolymarketClient()
            logger.info("✅ CLOB client initialized")

            # Initialize trade executor
            self.trade_executor = TradeExecutor(self.clob_client, self.settings)
            logger.info("✅ Trade executor initialized")

            # Initialize endgame sweeper (if enabled)
            if self.settings.endgame.enabled:
                self.endgame_sweeper = EndgameSweeper(
                    clob_client=self.clob_client,
                    circuit_breaker=self.trade_executor.circuit_breaker,
                )
                logger.info("🎯 Endgame sweeper initialized and enabled")
            else:
                self.endgame_sweeper = None
                logger.info("🎯 Endgame sweeper disabled (ENDGAME_ENABLED=false)")

            # Run initial wallet scan to get target wallets
            await self.update_target_wallets()

            # Initialize wallet monitor with target wallets
            if self.target_wallets:
                self.wallet_monitor = WalletMonitor(
                    settings=self.settings,
                    trade_executor=self.trade_executor,
                    target_wallets=[w["address"] for w in self.target_wallets],
                )
                logger.info(
                    f"✅ Wallet monitor initialized with {len(self.target_wallets)} wallets"
                )
            else:
                logger.error(
                    "❌ Failed to initialize wallet monitor: no target wallets available"
                )
                return False

            # Start background cleanup tasks
            await self._start_background_cleanup_tasks()

            # Start production monitoring server (MCP)
            await self._start_monitoring_server()

            # Health check
            if not await self.health_check():
                logger.error("❌ Health check failed. Aborting initialization.")
                return False

            logger.info("✅ All components initialized successfully")
            return True

        except Exception as e:
            logger.critical(
                f"❌ Critical error during initialization: {str(e)}", exc_info=True
            )
            await send_error_alert(f"Initialization failed: {str(e)[:100]}")
            return False

    async def update_target_wallets(self):
        """Update target wallets from leaderboard scanner"""
        try:
            logger.info("🔍 Scanning leaderboard for top-performing wallets...")

            if not self.leaderboard_scanner:
                logger.error("❌ Leaderboard scanner not initialized")
                return

            # Get top wallets from scanner
            top_wallets = self.leaderboard_scanner.get_top_wallets()

            if not top_wallets:
                logger.warning("⚠️ No qualified wallets found in leaderboard scan")
                return

            # Extract wallet addresses and position size factors
            self.target_wallets = [
                {
                    "address": wallet["address"],
                    "position_size_factor": wallet.get("position_size_factor", 1.0),
                    "confidence_score": wallet.get("confidence_score", 0.0),
                    "risk_score": wallet.get("risk_score", 0.0),
                }
                for wallet in top_wallets
            ]

            logger.info(f"✅ Found {len(self.target_wallets)} qualified wallets:")
            for i, wallet in enumerate(self.target_wallets[:10], 1):
                logger.info(
                    f"  {i}. {wallet['address'][:8]}... - "
                    f"Confidence: {wallet['confidence_score']:.2f}, "
                    f"Risk: {wallet['risk_score']:.2f}, "
                    f"Size Factor: {wallet['position_size_factor']:.2f}"
                )

            # Update wallet monitor if it exists
            if self.wallet_monitor:
                position_size_factors = {
                    w["address"]: w["position_size_factor"] for w in self.target_wallets
                }
                await self.wallet_monitor.update_target_wallets(
                    [w["address"] for w in self.target_wallets], position_size_factors
                )

            self.last_wallet_update = time.time()

        except Exception as e:
            logger.error(f"❌ Error updating target wallets: {str(e)}", exc_info=True)
            await send_error_alert(f"Wallet update failed: {str(e)[:100]}")

    async def health_check(self) -> bool:
        """
        Perform comprehensive health check of all bot components.

        Returns:
            bool: True if all components are healthy, False if any component fails
        """
        if not await self._should_perform_health_check():
            return True

        logger.info("🏥 Performing health check...")

        try:
            health_checks = self._build_health_check_tasks()
            results = await self._execute_health_checks(health_checks)
            return await self._analyze_health_check_results(health_checks, results)
        except Exception as e:
            logger.error(f"Error performing health check: {e}", exc_info=True)
            return False

    async def _should_perform_health_check(self) -> bool:
        """Check if health check should be performed based on cache"""
        if not self.last_health_check or (
            datetime.now(timezone.utc) - self.last_health_check
        ) > timedelta(minutes=5):
            return True
        return False

    def _build_health_check_tasks(self) -> List[Tuple[str, Any]]:
        """Build the list of health check tasks"""
        health_checks = []

        if self.clob_client:
            health_checks.append(("CLOB Client", self.clob_client.health_check()))
        if self.wallet_monitor:
            health_checks.append(("Wallet Monitor", self.wallet_monitor.health_check()))
        if self.trade_executor:
            health_checks.append(("Trade Executor", self.trade_executor.health_check()))
        if self.leaderboard_scanner:
            health_checks.append(
                ("Leaderboard Scanner", self.leaderboard_scanner.health_check())
            )
        if self.endgame_sweeper:
            health_checks.append(
                ("Endgame Sweeper", self.endgame_sweeper.health_check())
            )

        return health_checks

    async def _execute_health_checks(
        self, health_checks: List[Tuple[str, Any]]
    ) -> List[Any]:
        """Execute health checks with concurrency control"""
        tasks = [check for _, check in health_checks]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _analyze_health_check_results(
        self, health_checks: List[Tuple[str, Any]], results: List[Any]
    ) -> bool:
        """Analyze health check results and determine overall health"""
        all_healthy = True
        failed_components = []

        for (component_name, _), result in zip(health_checks, results):
            if isinstance(result, Exception):
                all_healthy = False
                failed_components.append(
                    f"{component_name} (exception: {str(result)[:50]})"
                )
                logger.warning(f"⚠️ {component_name} health check exception: {result}")
            elif result is not True:
                all_healthy = False
                failed_components.append(f"{component_name} (returned: {result})")
                logger.warning(f"⚠️ {component_name} health check failed")

        if all_healthy:
            logger.info("✅ All health checks passed")
            self.last_health_check = datetime.now(timezone.utc)
            return True
        else:
            await self._handle_health_check_failure(failed_components)
            return False

    async def _handle_health_check_failure(self, failed_components: List[str]) -> None:
        """Handle and alert on health check failures"""
        error_msg = "Health check failed for components: " + ", ".join(
            failed_components
        )
        logger.error(f"❌ {error_msg}")

        await send_error_alert(
            "Health check failed",
            {
                "failed_components": failed_components,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": self.session_id,
            },
        )

    async def monitor_loop(self) -> None:
        """
        Main monitoring loop - core bot operation orchestrator.

        This method coordinates the main trading loop components:
        1. Periodic wallet updates from leaderboard scanner
        2. Health checks before processing
        3. Wallet monitoring and trade execution
        4. Position management
        5. Maintenance and cleanup tasks
        6. Performance monitoring and reporting
        """
        logger.info(
            f"🔍 Starting monitoring loop. Checking every {self.settings.monitor_interval} seconds"
        )

        while self.running:
            cycle_start = time.time()

            try:
                # Periodically update target wallets from scanner
                if time.time() - self.last_wallet_update > self.wallet_update_interval:
                    await self.update_target_wallets()

                # Pre-cycle health check
                if not await self._perform_health_check():
                    await asyncio.sleep(5)
                    continue

                # Main cycle operations
                await self._monitor_wallets_and_execute_trades()
                await self._manage_positions()
                await self._run_endgame_sweeper()
                await self._perform_maintenance_tasks()

                # Calculate sleep time to maintain consistent interval
                cycle_time = time.time() - cycle_start
                sleep_time = max(0, self.settings.monitor_interval - cycle_time)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                logger.info("🛑 Monitoring loop cancelled")
                break
            except Exception as e:
                await self._handle_monitoring_cycle_error(e, cycle_start)

    async def _perform_health_check(self) -> bool:
        """Perform health check before proceeding with monitoring cycle"""
        return await self.health_check()

    async def _monitor_wallets_and_execute_trades(self) -> None:
        """Monitor wallets for new trades and execute copy trades"""
        if not self.wallet_monitor:
            logger.error("❌ Wallet monitor not initialized")
            return

        wallet_start = time.time()
        detected_trades = await self.wallet_monitor.monitor_wallets()
        wallet_time = time.time() - wallet_start

        if not detected_trades:
            return

        trade_count = len(detected_trades)
        logger.info(
            f"🎯 Detected {trade_count} new trades to copy (wallet scan: {wallet_time:.3f}s)",
            extra={"trade_count": trade_count, "scan_time": wallet_time},
        )

        # Execute trades with performance optimizations
        success_count = await self._execute_detected_trades(
            detected_trades, wallet_start, wallet_time, trade_count
        )

        # Update performance stats
        cycle_time = time.time() - wallet_start
        await self._update_performance_stats(cycle_time, trade_count, success_count)

    async def _execute_detected_trades(
        self,
        detected_trades: List[Dict[str, Any]],
        wallet_start: float,
        wallet_time: float,
        trade_count: int,
    ) -> int:
        """Execute detected trades with batching and performance monitoring"""
        max_concurrent_trades = min(
            10, len(detected_trades)
        )  # Max 10 concurrent trades

        if trade_count <= max_concurrent_trades:
            # Execute all trades concurrently for small batches
            results = await self._execute_trade_batch(detected_trades)
        else:
            # Execute in batches for large numbers of trades
            results = await self._execute_trade_batches(
                detected_trades, max_concurrent_trades
            )

        # Analyze results
        success_count, error_count = self._analyze_trade_results(results, trade_count)

        # Performance monitoring
        trade_execution_time = time.time() - wallet_start - wallet_time
        if trade_count > 0:
            avg_time_per_trade = trade_execution_time / trade_count
            logger.debug(
                f"⏱️ Trade execution: {trade_execution_time:.3f}s total, {avg_time_per_trade:.3f}s per trade"
            )

        return success_count

    async def _execute_trade_batch(self, trades: List[Dict[str, Any]]) -> List[Any]:
        """Execute a batch of trades concurrently"""
        if not self.trade_executor:
            logger.error("❌ Trade executor not initialized")
            return [Exception("Trade executor not initialized") for _ in trades]

        tasks = [self.trade_executor.execute_copy_trade(trade) for trade in trades]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_trade_batches(
        self, trades: List[Dict[str, Any]], batch_size: int
    ) -> List[Any]:
        """Execute trades in batches to prevent overload"""
        results = []
        for i in range(0, len(trades), batch_size):
            batch = trades[i : i + batch_size]
            batch_results = await self._execute_trade_batch(batch)
            results.extend(batch_results)

            # Small delay between batches to prevent API overload
            if i + batch_size < len(trades):
                await asyncio.sleep(0.1)

        return results

    def _analyze_trade_results(
        self, results: List[Any], trade_count: int
    ) -> Tuple[int, int]:
        """Analyze trade execution results and log summary"""
        success_count = sum(
            1 for r in results if isinstance(r, dict) and r.get("status") == "success"
        )
        error_count = sum(1 for r in results if isinstance(r, Exception))

        if success_count > 0:
            logger.info(
                f"✅ Successfully copied {success_count}/{trade_count} trades",
                extra={"successful_trades": success_count, "total_trades": trade_count},
            )
        if error_count > 0:
            logger.warning(f"⚠️ {error_count} trades failed during execution")
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Trade {i} failed: {str(result)[:100]}")

        return success_count, error_count

    async def _manage_positions(self) -> None:
        """Manage open positions (stop loss/take profit)"""
        if self.trade_executor:
            await self.trade_executor.manage_positions()

    async def _run_endgame_sweeper(self) -> None:
        """Run endgame sweeper scan if enabled"""
        if not self.endgame_sweeper:
            return

        try:
            # Check if enough time has passed since last scan
            if self.endgame_sweeper.last_scan_time:
                time_since_scan = time.time() - self.endgame_sweeper.last_scan_time
                if time_since_scan < self.settings.endgame.scan_interval_seconds:
                    return

            # Run scan
            result = await self.endgame_sweeper.scan_and_execute()

            # Log results if any trades executed
            if result.get("trades_executed", 0) > 0:
                logger.info(
                    f"🎯 Endgame sweeper: {result['trades_executed']} trades executed, "
                    f"{result['open_positions']} positions open"
                )

        except Exception as e:
            logger.error(f"❌ Error running endgame sweeper: {e}", exc_info=True)

    async def _perform_maintenance_tasks(self) -> None:
        """Perform maintenance tasks like cleanup and reporting"""
        # Clean up old processed transactions
        if self.wallet_monitor:
            await self.wallet_monitor.clean_processed_transactions()

        # Periodic performance report
        if (
            time.time() - self.last_performance_report
            > self.performance_report_interval
        ):
            await self._periodic_performance_report()

        # Daily reset check
        await self._check_daily_reset()

    async def _check_daily_reset(self):
        """Check if we need to reset daily metrics"""
        now = datetime.now(timezone.utc)
        if not self.last_daily_reset or now.date() > self.last_daily_reset.date():
            logger.info("📅 Performing daily reset")
            if self.trade_executor:
                self.trade_executor.reset_daily_metrics()
            self.last_daily_reset = now

    async def _start_background_cleanup_tasks(self) -> None:
        """Start background cleanup tasks for all caches"""
        try:
            # Start scanner background tasks
            if self.leaderboard_scanner:
                self.leaderboard_scanner.start_scanning()
                logger.info("✅ Started leaderboard scanner background task")

            # Start cache cleanup tasks
            if self.trade_executor:
                await self.trade_executor.start_background_tasks()
            if self.wallet_monitor:
                await self.wallet_monitor.start_background_tasks()

            logger.info("✅ Started all background cleanup tasks")
        except Exception as e:
            logger.warning(f"⚠️ Failed to start some background tasks: {e}")

    async def _stop_background_cleanup_tasks(self) -> None:
        """Stop background cleanup tasks for all caches"""
        try:
            if self.leaderboard_scanner:
                self.leaderboard_scanner.stop_scanning()
            if self.trade_executor:
                await self.trade_executor.stop_background_tasks()
            if self.wallet_monitor:
                await self.wallet_monitor.stop_background_tasks()
            logger.info("✅ Stopped all background tasks")
        except Exception as e:
            logger.warning(f"⚠️ Error stopping background tasks: {e}")

    async def _start_monitoring_server(self) -> None:
        """Start production monitoring server as background task."""
        try:
            from config.mcp_config import get_monitoring_config

            monitoring_config = get_monitoring_config()

            if not monitoring_config.enabled:
                logger.info("ℹ️ Production monitoring server disabled in config")
                return

            logger.info("🔍 Starting production monitoring server...")

            # Import monitoring server (use enhanced version if available)
            try:
                from mcp.monitoring_server_enhanced import get_monitoring_server

                _ = get_monitoring_server  # Mark as used
            except ImportError:
                # Fallback to original monitoring server
                from mcp.monitoring_server import get_monitoring_server

                _ = get_monitoring_server  # Mark as used
                logger.info("Using original monitoring server")

            dashboard_msg = ""
            if monitoring_config.dashboard_enabled:
                dashboard_msg = (
                    f" (dashboard: http://localhost:{monitoring_config.dashboard_port})"
                )
            metrics_msg = ""
            if monitoring_config.metrics_enabled:
                metrics_msg = (
                    f" (metrics: http://localhost:{monitoring_config.metrics_port})"
                )
            logger.info(
                f"✅ Production monitoring server started{dashboard_msg}{metrics_msg}"
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to start monitoring server: {e}")
            logger.warning("Continuing without monitoring server")
            self.monitoring_server = None

    async def _stop_monitoring_server(self) -> None:
        """Stop production monitoring server."""
        if self.monitoring_server:
            try:
                await self.monitoring_server.stop()
                logger.info("✅ Stopped production monitoring server")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping monitoring server: {e}")

    async def _handle_monitoring_cycle_error(
        self, error: Exception, cycle_start: float
    ) -> None:
        """Handle errors that occur during monitoring cycles"""
        cycle_time = time.time() - cycle_start

        error_type = type(error).__name__
        error_msg = str(error)[:200]  # Limit error message length

        logger.error(f"❌ {error_type} in monitoring loop: {error_msg}", exc_info=True)

        await send_error_alert(
            f"Monitoring loop error: {error_type}",
            {
                "error_message": error_msg,
                "cycle_time": cycle_time,
                "session_id": self.session_id,
            },
        )

        # Wait before retrying
        await asyncio.sleep(5)

    async def start(self):
        """Start the bot"""
        if not await self.initialize():
            logger.critical("❌ Failed to initialize bot. Exiting.")
            raise InitializationError("Failed to initialize bot components")

        self.running = True
        self.start_time = datetime.now(timezone.utc)

        logger.info("🚀 Starting Polymarket Copy Bot")
        logger.info(f"Session ID: {self.session_id}")
        logger.info("Monitoring wallets from leaderboard scanner")
        logger.info(
            f"Risk parameters: Max position=${self.settings.max_position_size:.2f}, "
            f"Max daily loss=${self.settings.max_daily_loss:.2f}"
        )

        # Send startup alert
        env_info = get_environment_info()
        endgame_status = "✅ Enabled" if self.endgame_sweeper else "❌ Disabled"

        await send_telegram_alert(
            f"🚀 **BOT STARTED**\n"
            f"Session ID: `{self.session_id}`\n"
            f"Version: 1.0.1\n"
            f"Wallet: `{self.clob_client.wallet_address[-6:] if self.clob_client else 'N/A'}`\n"
            f"Scanner: Active (updating every {self.scanner_config.SCAN_INTERVAL_HOURS} hours)\n"
            f"Endgame Sweeper: {endgame_status}\n"
            f"Environment: {env_info['system']} {env_info['machine']}\n"
            f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Max Daily Loss: ${self.settings.max_daily_loss:.2f}"
        )

        # Start monitoring loop
        monitor_task = asyncio.create_task(self.monitor_loop())

        # Graceful shutdown handling
        def signal_handler():
            logger.info("🛑 Received shutdown signal. Stopping bot...")
            self.running = False

        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(sig, signal_handler)

        try:
            await monitor_task
        except asyncio.CancelledError:
            logger.info("🛑 Monitoring task cancelled during shutdown")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Gracefully shutdown the bot"""
        logger.info("🧹 Starting graceful shutdown...")

        if self.running:
            self.running = False

        # Cancel all pending tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.warning(f"Error during task cancellation: {e}")

        # Send shutdown alert
        runtime = (
            datetime.now(timezone.utc) - self.start_time
            if self.start_time
            else timedelta(0)
        )
        metrics = (
            self.trade_executor.get_performance_metrics() if self.trade_executor else {}
        )

        try:
            await send_telegram_alert(
                f"🛑 **BOT STOPPED**\n"
                f"Session ID: `{self.session_id}`\n"
                f"Runtime: {runtime}\n"
                f"Total trades: {metrics.get('total_trades', 0)}\n"
                f"Successful trades: {metrics.get('successful_trades', 0)}\n"
                f"Success rate: {metrics.get('success_rate', 0):.1%}\n"
                f"Daily loss: ${metrics.get('daily_loss', 0):.2f}"
            )
        except Exception as e:
            logger.error(f"Error sending shutdown alert: {e}")

        # Stop background tasks
        await self._stop_background_cleanup_tasks()

        # Stop monitoring server
        await self._stop_monitoring_server()

        # Stop endgame sweeper
        if self.endgame_sweeper:
            await self.endgame_sweeper.stop()
            logger.info("✅ Endgame sweeper stopped")

        logger.info("✅ Bot shutdown completed successfully")

    async def _update_performance_stats(
        self, cycle_time: float, trades_processed: int, trades_successful: int
    ):
        """Update performance statistics for monitoring"""
        self.performance_stats["cycles_completed"] += 1
        self.performance_stats["trades_processed"] += trades_processed
        self.performance_stats["trades_successful"] += trades_successful
        self.performance_stats["total_cycle_time"] += cycle_time
        self.performance_stats["last_cycle_time"] = cycle_time

        if self.performance_stats["cycles_completed"] > 0:
            self.performance_stats["avg_cycle_time"] = (
                self.performance_stats["total_cycle_time"]
                / self.performance_stats["cycles_completed"]
            )

        self.performance_stats["uptime_seconds"] = (
            datetime.now(timezone.utc) - self.start_time
        ).total_seconds()

        # Memory usage tracking (optional)
        try:
            import psutil

            process = psutil.Process()
            self.performance_stats["memory_usage_mb"] = (
                process.memory_info().rss / 1024 / 1024
            )
        except (ImportError, Exception):
            self.performance_stats["memory_usage_mb"] = 0.0

    async def _periodic_performance_report(self):
        """Generate and send periodic performance report"""
        try:
            self.last_performance_report = time.time()

            # Get component performance stats
            wallet_stats = (
                self.wallet_monitor.get_performance_stats()
                if self.wallet_monitor
                else {}
            )
            trade_stats = (
                self.trade_executor.get_performance_metrics()
                if self.trade_executor
                else {}
            )
            scanner_stats = (
                self.leaderboard_scanner.get_scan_status()
                if self.leaderboard_scanner
                else {}
            )

            # Calculate overall performance
            uptime_hours = self.performance_stats["uptime_seconds"] / 3600
            success_rate = (
                self.performance_stats["trades_successful"]
                / max(1, self.performance_stats["trades_processed"])
            ) * 100

            # Performance health assessment
            performance_health = "🟢 GOOD"
            if (
                self.performance_stats["avg_cycle_time"]
                > self.settings.monitor_interval * 1.5
            ):
                performance_health = "🟡 SLOW"
            elif (
                self.performance_stats["avg_cycle_time"]
                > self.settings.monitor_interval * 2
            ):
                performance_health = "🔴 CRITICAL"

            # Send performance report
            await send_performance_report(
                {
                    "uptime_hours": uptime_hours,
                    "cycles_completed": self.performance_stats["cycles_completed"],
                    "avg_cycle_time": self.performance_stats["avg_cycle_time"],
                    "performance_health": performance_health,
                    "trades_processed": self.performance_stats["trades_processed"],
                    "trades_successful": self.performance_stats["trades_successful"],
                    "success_rate": success_rate,
                    "memory_usage_mb": self.performance_stats["memory_usage_mb"],
                    "cache_hit_rate": wallet_stats.get("cache_hit_rate", 0),
                    "avg_api_call_time": wallet_stats.get("avg_api_call_time", 0),
                    "open_positions": trade_stats.get("open_positions", 0),
                    "daily_loss": trade_stats.get("daily_loss", 0),
                    "circuit_breaker_active": trade_stats.get(
                        "circuit_breaker_active", False
                    ),
                    "scanner_status": scanner_stats.get("is_running", False),
                    "scanner_wallets": scanner_stats.get("wallet_count", 0),
                }
            )

            logger.info(f"📊 Performance report sent - Health: {performance_health}")

        except Exception as e:
            logger.error(
                f"Error generating performance report: {str(e)[:100]}", exc_info=True
            )


async def main():
    """Main entry point"""
    bot = PolymarketCopyBot()
    await bot.start()


if __name__ == "__main__":
    try:
        # Set up event loop policy for better performance
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot terminated by user")
        sys.exit(0)
    except InitializationError as e:
        logger.critical(f"❌ Initialization failed: {str(e)}", exc_info=True)
        sys.exit(1)
    except GracefulShutdown:
        logger.info("🛑 Graceful shutdown completed")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"❌ Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
