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

# Configure logging first
from utils.logging_utils import setup_logging

logger = setup_logging()

# Import after logging is configured
from config.settings import Settings, settings
from core.clob_client import PolymarketClient
from core.trade_executor import TradeExecutor
from core.wallet_monitor import WalletMonitor
from utils.alerts import (
    alert_manager,
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
        """Initialize all components"""
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

        except Exception as e:
            logger.critical(f"❌ Initialization failed: {e}", exc_info=True)
            await send_error_alert(f"Initialization failed: {e}")
            return False

    async def health_check(self) -> bool:
        """
        Perform comprehensive health check of all bot components.

        Checks the operational status of:
        - CLOB client connectivity
        - Wallet monitor functionality
        - Trade executor state
        - API connectivity and rate limits

        Health checks are cached for 5 minutes to avoid excessive API calls.

        Returns:
            bool: True if all components are healthy, False if any component fails
        """
        """Perform comprehensive health check"""
        if not self.last_health_check or (datetime.now() - self.last_health_check) > timedelta(
            minutes=5
        ):
            logger.info("🏥 Performing health check...")

            # Performance optimization: Build health check tasks dynamically
            health_checks = []

            if self.clob_client:
                health_checks.append(("CLOB Client", self.clob_client.health_check()))
            if self.wallet_monitor:
                health_checks.append(("Wallet Monitor", self.wallet_monitor.health_check()))
            if self.trade_executor:
                health_checks.append(("Trade Executor", self.trade_executor.health_check()))

            # Execute health checks with concurrency control
            if len(health_checks) <= self.max_concurrent_health_checks:
                # Run all concurrently for small numbers
                tasks = [check for _, check in health_checks]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # Run in batches for larger numbers (future-proofing)
                results = []
                for i in range(0, len(health_checks), self.max_concurrent_health_checks):
                    batch = health_checks[i : i + self.max_concurrent_health_checks]
                    batch_tasks = [check for _, check in batch]
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    results.extend(batch_results)

            # Analyze results
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

        return True

    async def monitor_loop(self) -> None:
        """
        Main monitoring loop - core bot operation.

        This method implements the main trading loop that:
        1. Monitors target wallets for new trades
        2. Executes copy trades with risk management
        3. Manages open positions (stop-loss, take-profit)
        4. Performs periodic maintenance tasks
        5. Generates performance reports

        The loop runs at intervals defined by settings.monitoring.monitor_interval
        and includes comprehensive error handling and recovery mechanisms.

        The loop continues until self.running is set to False.
        """
        """Main monitoring loop"""
        logger.info(
            f"🔍 Starting monitoring loop. Checking every {self.settings.monitoring.monitor_interval} seconds"
        )

        while self.running:
            cycle_start = time.time()

            try:
                # Health check periodically
                if not await self.health_check():
                    logger.warning("⚠️ Health check failed. Skipping this monitoring cycle.")
                    await asyncio.sleep(5)
                    continue

                # Monitor wallets for new trades with performance optimization
                wallet_start = time.time()
                detected_trades = await self.wallet_monitor.monitor_wallets()
                wallet_time = time.time() - wallet_start

                if detected_trades:
                    trade_count = len(detected_trades)
                    logger.info(
                        f"🎯 Detected {trade_count} new trades to copy (wallet scan: {wallet_time:.3f}s)"
                    )

                    # Performance optimization: Limit concurrent trades to prevent overload
                    max_concurrent_trades = min(
                        10, len(detected_trades)
                    )  # Max 10 concurrent trades

                    if trade_count <= max_concurrent_trades:
                        # Execute all trades concurrently for small batches
                        tasks = [
                            self.trade_executor.execute_copy_trade(trade)
                            for trade in detected_trades
                        ]
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                    else:
                        # Execute in batches for large numbers of trades
                        results = []
                        for i in range(0, trade_count, max_concurrent_trades):
                            batch = detected_trades[i : i + max_concurrent_trades]
                            batch_tasks = [
                                self.trade_executor.execute_copy_trade(trade) for trade in batch
                            ]
                            batch_results = await asyncio.gather(
                                *batch_tasks, return_exceptions=True
                            )
                            results.extend(batch_results)

                            # Small delay between batches to prevent API overload
                            if i + max_concurrent_trades < trade_count:
                                await asyncio.sleep(0.1)

                    # Performance-optimized result logging
                    success_count = sum(
                        1 for r in results if isinstance(r, dict) and r.get("status") == "success"
                    )
                    error_count = sum(1 for r in results if isinstance(r, Exception))

                    if success_count > 0:
                        logger.info(f"✅ Successfully copied {success_count}/{trade_count} trades")
                    if error_count > 0:
                        logger.warning(f"⚠️ {error_count} trades failed during execution")

                    # Performance monitoring
                    trade_execution_time = time.time() - wallet_start - wallet_time
                    if trade_count > 0:
                        avg_time_per_trade = trade_execution_time / trade_count
                        logger.debug(
                            f"⏱️ Trade execution: {trade_execution_time:.3f}s total, {avg_time_per_trade:.3f}s per trade"
                        )

                # Manage positions (stop loss/take profit)
                await self.trade_executor.manage_positions()

                # Clean up old processed transactions
                await self.wallet_monitor.clean_processed_transactions()

                # Performance monitoring and reporting
                cycle_time = time.time() - cycle_start
                await self._update_performance_stats(
                    cycle_time,
                    len(detected_trades) if detected_trades else 0,
                    success_count if "success_count" in locals() else 0,
                )

                # Periodic performance report
                if time.time() - self.last_performance_report > self.performance_report_interval:
                    await self._periodic_performance_report()

                # Calculate sleep time to maintain consistent interval (performance optimization)
                sleep_time = max(0, self.settings.monitoring.monitor_interval - cycle_time)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                logger.info("🛑 Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}", exc_info=True)
                await send_error_alert(
                    f"Monitoring loop error: {e}",
                    {"cycle_time": time.time() - cycle_start, "session_id": self.session_id},
                )

                # Wait before retrying
                await asyncio.sleep(5)

    async def _periodic_performance_report(self):
        """Generate periodic performance reports"""
        now = time.time()
        if not hasattr(self, "last_report_time"):
            self.last_report_time = now

        # Report every hour
        if now - self.last_report_time > 3600:
            try:
                if self.trade_executor:
                    metrics = self.trade_executor.get_performance_metrics()
                    await send_performance_report(metrics)
                    logger.info("📈 Performance report sent")

                # Reset daily loss at midnight UTC
                current_time = datetime.utcnow()
                last_reset = getattr(
                    self,
                    "last_daily_reset",
                    datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
                )

                if current_time.date() > last_reset.date():
                    if self.trade_executor:
                        self.trade_executor.daily_loss = 0.0
                        logger.info("🔄 Daily loss reset at midnight UTC")
                    self.last_daily_reset = current_time

                self.last_report_time = now

            except Exception as e:
                logger.error(f"Error generating performance report: {e}", exc_info=True)

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
        """Generate and send periodic performance report"""
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

        except Exception as e:
            logger.error(f"Error generating performance report: {e}")


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
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
