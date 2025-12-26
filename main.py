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

Key Features:
- Real-time wallet monitoring with caching and rate limiting
- Automated risk management (position sizing, stop-loss, take-profit)
- Circuit breaker protection against excessive losses
- Performance monitoring and alerting
- Graceful error handling and recovery

Environment Variables Required:
- PRIVATE_KEY: Ethereum private key for trading
- POLYGON_RPC_URL: Polygon RPC endpoint
- TELEGRAM_BOT_TOKEN: Telegram bot token for alerts
- TELEGRAM_CHAT_ID: Telegram chat ID for notifications
- POLYGONSCAN_API_KEY: PolygonScan API key for transaction monitoring

Author: Polymarket Bot Team
Version: 1.0.0
License: MIT
"""

import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiohttp

# Configure logging first
from utils.logging_config import setup_logging

# Initialize logging
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir="logs",
    json_logging=os.getenv("JSON_LOGGING", "true").lower() == "true",
)

logger = logging.getLogger(__name__)

# Import after logging is configured
from config.settings import settings
from core.clob_client import PolymarketClient
from core.trade_executor import TradeExecutor
from core.wallet_monitor import WalletMonitor
from utils.alerts import (
    send_error_alert,
    send_performance_report,
    send_telegram_alert,
)
from utils.helpers import get_environment_info
from utils.security import generate_session_id


class PolymarketCopyBot:
    """
    Main bot controller for Polymarket copy trading operations.

    This class orchestrates the entire copy trading workflow:
    1. Monitors target wallets for trading activity
    2. Applies risk management rules to trade signals
    3. Executes copy trades on Polymarket
    4. Manages open positions (stop-loss, take-profit)
    5. Provides monitoring, alerting, and performance reporting

    Attributes:
        settings: Application configuration settings
        running: Flag indicating if the bot is actively running
        start_time: Timestamp when the bot was started
        session_id: Unique identifier for this bot session
        performance_stats: Real-time performance metrics

    Components:
        clob_client: Interface to Polymarket's Conditional Order Book
        wallet_monitor: Blockchain transaction monitoring service
        trade_executor: Trade execution and position management engine
    """

    def __init__(self) -> None:
        """
        Initialize the Polymarket Copy Trading Bot.

        Sets up all core components, performance monitoring, and configuration.
        The bot is initialized in a stopped state and must be started with start().
        """
        self.settings = settings
        self.running = False
        self.start_time = datetime.now()
        self.last_health_check: Optional[datetime] = None
        self.session_id = generate_session_id()

        # Core components - initialized during startup
        self.clob_client: Optional[PolymarketClient] = None
        self.wallet_monitor: Optional[WalletMonitor] = None
        self.trade_executor: Optional[TradeExecutor] = None

        # Performance monitoring and optimization
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
        self.max_concurrent_health_checks = 3  # Limit concurrent health checks
        self.performance_report_interval = 300  # 5 minutes between reports
        self.last_performance_report = time.time()

        logger.info(f"🚀 Initialized Polymarket Copy Bot (Session ID: {self.session_id})")

    async def initialize(self) -> bool:
        """
        Initialize all bot components and perform startup checks.

        This method sets up the core components (CLOB client, wallet monitor,
        trade executor) and performs initial health checks to ensure the bot
        can operate properly.

        Returns:
            bool: True if initialization successful, False otherwise

        Raises:
            Exception: If critical components fail to initialize
        """
        try:
            logger.info("🚀 Initializing Polymarket Copy Bot components...")

            # Validate settings
            self.settings.validate_critical_settings()

            # Initialize CLOB client
            self.clob_client = PolymarketClient()

            # Initialize wallet monitor
            self.wallet_monitor = WalletMonitor()

            # Initialize trade executor
            self.trade_executor = TradeExecutor(self.clob_client)

            # Health check
            if not await self.health_check():
                logger.error("❌ Health check failed. Aborting initialization.")
                return False

            logger.info("✅ All components initialized successfully")
            return True

        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.critical(
                f"❌ Network error during initialization: {str(e)[:100]}", exc_info=True
            )
            await send_error_alert(f"Initialization network error: {str(e)[:100]}")
            return False
        except (ValueError, TypeError, KeyError) as e:
            logger.critical(
                f"❌ Configuration error during initialization: {str(e)[:100]}", exc_info=True
            )
            await send_error_alert(f"Initialization config error: {str(e)[:100]}")
            return False
        except Exception as e:
            logger.critical(f"❌ Unexpected error during initialization: {str(e)}", exc_info=True)
            await send_error_alert(f"Initialization unexpected error: {str(e)[:100]}")
            return False

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
        if not self.last_health_check or (datetime.now() - self.last_health_check) > timedelta(
            minutes=5
        ):
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

        return health_checks

    async def _execute_health_checks(self, health_checks: List[Tuple[str, Any]]) -> List[Any]:
        """Execute health checks with concurrency control"""
        if len(health_checks) <= self.max_concurrent_health_checks:
            # Run all concurrently for small numbers
            tasks = [check for _, check in health_checks]
            return await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # Run in batches for larger numbers (future-proofing)
            results = []
            for i in range(0, len(health_checks), self.max_concurrent_health_checks):
                batch = health_checks[i : i + self.max_concurrent_health_checks]
                batch_tasks = [check for _, check in batch]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                results.extend(batch_results)
            return results

    async def _analyze_health_check_results(
        self, health_checks: List[Tuple[str, Any]], results: List[Any]
    ) -> bool:
        """Analyze health check results and determine overall health"""
        all_healthy = True
        failed_components = []

        for (component_name, _), result in zip(health_checks, results):
            if isinstance(result, Exception):
                all_healthy = False
                failed_components.append(f"{component_name} (exception)")
                logger.warning(f"⚠️ {component_name} health check exception: {result}")
            elif result is not True:
                all_healthy = False
                failed_components.append(component_name)
                logger.warning(f"⚠️ {component_name} health check failed")

        if all_healthy:
            logger.info("✅ All health checks passed")
            self.last_health_check = datetime.now()
            return True
        else:
            return await self._handle_health_check_failure(results, failed_components)

    async def _handle_health_check_failure(
        self, results: List[Any], failed_components: List[str]
    ) -> bool:
        """Handle and alert on health check failures"""
        logger.error("❌ Health check failed")

        error_details = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_details.append(f"Component {i}: {str(result)}")
            elif result is not True:
                error_details.append(f"Component {i}: Failed health check")

        # Send alert on health check failure
        await send_error_alert(
            "Health check failed",
            {
                "results": error_details,
                "timestamp": datetime.now().isoformat(),
                "session_id": self.session_id,
            },
        )

        return False

    async def monitor_loop(self) -> None:
        """
        Main monitoring loop - core bot operation orchestrator.

        This method coordinates the main trading loop components:
        1. Health checks before processing
        2. Wallet monitoring and trade execution
        3. Position management
        4. Maintenance and cleanup tasks
        5. Performance monitoring and reporting
        """
        logger.info(
            f"🔍 Starting monitoring loop. Checking every {self.settings.monitoring.monitor_interval} seconds"
        )

        while self.running:
            cycle_start = time.time()

            try:
                # Pre-cycle health check
                if not await self._perform_health_check():
                    await asyncio.sleep(5)
                    continue

                # Main cycle operations
                await self._monitor_wallets_and_execute_trades()
                await self._manage_positions()
                await self._perform_maintenance_tasks()

                # Calculate sleep time to maintain consistent interval
                cycle_time = time.time() - cycle_start
                sleep_time = max(0, self.settings.monitoring.monitor_interval - cycle_time)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                logger.info("🛑 Monitoring loop cancelled")
                break
            except Exception as e:
                await self._handle_monitoring_cycle_error(e, cycle_start)

    async def _perform_health_check(self) -> bool:
        """Perform health check before proceeding with monitoring cycle"""
        if not await self.health_check():
            logger.warning("⚠️ Health check failed. Skipping this monitoring cycle.")
            return False
        return True

    async def _monitor_wallets_and_execute_trades(self) -> None:
        """Monitor wallets for new trades and execute copy trades"""
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
        max_concurrent_trades = min(10, len(detected_trades))  # Max 10 concurrent trades

        if trade_count <= max_concurrent_trades:
            # Execute all trades concurrently for small batches
            results = await self._execute_trade_batch(detected_trades)
        else:
            # Execute in batches for large numbers of trades
            results = await self._execute_trade_batches(detected_trades, max_concurrent_trades)

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

    def _analyze_trade_results(self, results: List[Any], trade_count: int) -> Tuple[int, int]:
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

        return success_count, error_count

    async def _manage_positions(self) -> None:
        """Manage open positions (stop loss/take profit)"""
        await self.trade_executor.manage_positions()

    async def _perform_maintenance_tasks(self) -> None:
        """Perform maintenance tasks like cleanup and reporting"""
        # Clean up old processed transactions
        await self.wallet_monitor.clean_processed_transactions()

        # Periodic performance report
        if time.time() - self.last_performance_report > self.performance_report_interval:
            await self._periodic_performance_report()

    async def _handle_monitoring_cycle_error(self, error: Exception, cycle_start: float) -> None:
        """Handle errors that occur during monitoring cycles"""
        cycle_time = time.time() - cycle_start

        if isinstance(error, (ConnectionError, TimeoutError, aiohttp.ClientError)):
            logger.error(f"❌ Network error in monitoring loop: {str(error)[:100]}", exc_info=True)
            await send_error_alert(
                f"Monitoring loop network error: {str(error)[:100]}",
                {"cycle_time": cycle_time, "session_id": self.session_id},
            )
        elif isinstance(error, (ValueError, TypeError, KeyError)):
            logger.error(f"❌ Data error in monitoring loop: {str(error)[:100]}", exc_info=True)
            await send_error_alert(
                f"Monitoring loop data error: {str(error)[:100]}",
                {"cycle_time": cycle_time, "session_id": self.session_id},
            )
        else:
            logger.critical(f"❌ Unexpected error in monitoring loop: {str(error)}", exc_info=True)
            await send_error_alert(
                f"Monitoring loop unexpected error: {str(error)[:100]}",
                {"cycle_time": cycle_time, "session_id": self.session_id},
            )

        # Wait before retrying
        await asyncio.sleep(5)

    async def start(self):
        """Start the bot"""
        if not await self.initialize():
            logger.critical("❌ Failed to initialize bot. Exiting.")
            sys.exit(1)

        self.running = True
        self.start_time = datetime.now()

        logger.info("🚀 Starting Polymarket Copy Bot")
        logger.info(f"Session ID: {self.session_id}")
        logger.info(f"Monitoring {len(self.settings.monitoring.target_wallets)} wallets")
        logger.info(
            f"Risk parameters: Max position=${self.settings.risk.max_position_size:.2f}, Max daily loss=${self.settings.risk.max_daily_loss:.2f}"
        )

        # Send startup alert
        env_info = get_environment_info()
        await send_telegram_alert(
            f"🚀 **BOT STARTED**\n"
            f"Session ID: `{self.session_id}`\n"
            f"Version: 1.0.0\n"
            f"Wallet: `{self.clob_client.wallet_address[-6:]}`\n"
            f"Monitored wallets: {len(self.settings.monitoring.target_wallets)}\n"
            f"Environment: {env_info['system']} {env_info['machine']}\n"
            f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Max Daily Loss: ${self.settings.risk.max_daily_loss:.2f}"
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

        # Wait for tasks to complete with timeout
        await asyncio.gather(*tasks, return_exceptions=True)

        # Send shutdown alert
        runtime = datetime.now() - self.start_time if self.start_time else timedelta(0)
        metrics = self.trade_executor.get_performance_metrics() if self.trade_executor else {}

        await send_telegram_alert(
            f"🛑 **BOT STOPPED**\n"
            f"Session ID: `{self.session_id}`\n"
            f"Runtime: {runtime}\n"
            f"Total trades: {metrics.get('total_trades', 0)}\n"
            f"Successful trades: {metrics.get('successful_trades', 0)}\n"
            f"Success rate: {metrics.get('success_rate', 0):.1%}\n"
            f"Daily loss: ${metrics.get('daily_loss', 0):.2f}"
        )

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
        self.performance_stats["avg_cycle_time"] = (
            self.performance_stats["total_cycle_time"] / self.performance_stats["cycles_completed"]
        )
        self.performance_stats["uptime_seconds"] = (
            datetime.now() - self.start_time
        ).total_seconds()

        # Memory usage tracking (optional, for advanced monitoring)
        try:
            import psutil

            process = psutil.Process()
            self.performance_stats["memory_usage_mb"] = process.memory_info().rss / 1024 / 1024
        except ImportError:
            self.performance_stats["memory_usage_mb"] = 0.0

    async def _periodic_performance_report(self):
        """
        Generate and send periodic performance report.

        This method was consolidated from a duplicate definition to maintain
        a single source of truth for performance reporting logic. The previous
        duplicate definition (lines 463-504) was removed as this version is
        more comprehensive and includes detailed performance metrics.
        """
        try:
            self.last_performance_report = time.time()

            # Get component performance stats
            wallet_stats = (
                self.wallet_monitor.get_performance_stats() if self.wallet_monitor else {}
            )
            trade_stats = (
                self.trade_executor.get_performance_metrics() if self.trade_executor else {}
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
                > self.settings.monitoring.monitor_interval * 1.5
            ):
                performance_health = "🟡 SLOW"
            elif (
                self.performance_stats["avg_cycle_time"]
                > self.settings.monitoring.monitor_interval * 2
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
                    "circuit_breaker_active": trade_stats.get("circuit_breaker_active", False),
                }
            )

            logger.info(f"📊 Performance report sent - Health: {performance_health}")

        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"Network error generating performance report: {str(e)[:100]}")
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error generating performance report: {str(e)[:100]}")
        except Exception as e:
            logger.critical(
                f"Unexpected error generating performance report: {str(e)}", exc_info=True
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
    except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
        logger.critical(f"❌ Network fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
    except (ValueError, TypeError, KeyError, ImportError) as e:
        logger.critical(f"❌ Configuration fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.critical(f"❌ Unexpected fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
