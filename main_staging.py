#!/usr/bin/env python3
"""
Polymarket Copy Trading Bot - STAGING ENVIRONMENT
=================================================

🚨 STAGING ENVIRONMENT - TESTNET ONLY 🚨

This is the staging version of the Polymarket copy trading bot that:
- Runs on Polygon Mumbai testnet
- Uses conservative risk parameters
- Has smaller position sizes
- Provides extensive logging and monitoring
- Is designed for 7-day validation testing

DO NOT USE MAINNET KEYS OR REAL FUNDS WITH THIS SCRIPT!

=================================================
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Optional

# Import staging configuration
from config.settings_staging import staging_settings
from core.clob_client import PolymarketClient
from core.trade_executor import TradeExecutor
from core.wallet_monitor import WalletMonitor
from utils.alerts import send_error_alert
from utils.logging_utils import setup_logging

# Setup staging logging
setup_logging(staging_settings.logging.log_level, staging_settings.logging.log_file)

logger = logging.getLogger(__name__)


class PolymarketStagingBot:
    """
    Staging version of the Polymarket copy trading bot.
    Optimized for testnet validation with conservative settings.
    """

    def __init__(self):
        self.settings = staging_settings
        self.running = False

        # Staging-specific counters
        self.staging_start_time = datetime.now()
        self.staging_trade_count = 0
        self.staging_daily_trades = 0
        self.staging_last_reset = datetime.now().date()

        # Core components
        self.clob_client: Optional[PolymarketClient] = None
        self.wallet_monitor: Optional[WalletMonitor] = None
        self.trade_executor: Optional[TradeExecutor] = None

        logger.info("🚨 STAGING BOT INITIALIZED 🚨")
        logger.info(f"Environment: {self.settings.staging.environment}")
        logger.info(f"Testnet Chain ID: {self.settings.network.chain_id}")
        logger.info(f"Max daily trades: {self.settings.staging.max_trades_per_day}")
        logger.info(f"Max position size: ${self.settings.risk.max_position_size}")
        logger.info(f"Paper trading: {self.settings.staging.enable_paper_trading}")

    async def initialize(self) -> bool:
        """Initialize staging bot components"""
        try:
            logger.info("🔧 Initializing staging bot components...")

            # Validate staging configuration
            self.settings.validate_critical_settings()

            # Initialize CLOB client (staging endpoint)
            self.clob_client = PolymarketClient(
                host=self.settings.network.clob_host, private_key=self.settings.trading.private_key
            )

            # Initialize wallet monitor (staging wallets)
            self.wallet_monitor = WalletMonitor(
                web3_provider=self.settings.network.polygon_rpc_url,
                clob_client=self.clob_client,
                target_wallets=self.settings.monitoring.target_wallets,
                min_confidence_score=self.settings.monitoring.min_confidence_score,
            )

            # Initialize trade executor (staging risk parameters)
            self.trade_executor = TradeExecutor(
                clob_client=self.clob_client,
                max_position_size=self.settings.risk.max_position_size,
                max_daily_loss=self.settings.risk.max_daily_loss,
                max_concurrent_positions=self.settings.risk.max_concurrent_positions,
                stop_loss_pct=self.settings.risk.stop_loss_percentage,
                take_profit_pct=self.settings.risk.take_profit_percentage,
            )

            # Test connections
            await self._test_staging_connections()

            logger.info("✅ Staging bot initialization completed")
            return True

        except Exception as e:
            logger.error(f"❌ Staging bot initialization failed: {e}")
            await self._send_staging_alert("INITIALIZATION_FAILED", str(e))
            return False

    async def _test_staging_connections(self):
        """Test staging environment connections"""
        logger.info("🔍 Testing staging environment connections...")

        # Test RPC connection
        try:
            from web3 import Web3

            web3 = Web3(Web3.HTTPProvider(self.settings.network.polygon_rpc_url))
            block_number = web3.eth.block_number
            logger.info(f"✅ Connected to Polygon Mumbai testnet (Block: {block_number})")
        except Exception as e:
            logger.warning(f"⚠️ RPC connection test failed: {e}")

        # Test CLOB connection
        try:
            # This would be a basic health check
            logger.info("✅ CLOB client initialized (staging endpoint)")
        except Exception as e:
            logger.warning(f"⚠️ CLOB connection test failed: {e}")

    async def start(self) -> bool:
        """Start the staging bot"""
        logger.info("🚀 Starting Polymarket Copy Trading Bot (STAGING)...")
        logger.info("==================================================")
        logger.info("🚨 STAGING ENVIRONMENT - TESTNET ONLY 🚨")
        logger.info("==================================================")

        if not await self.initialize():
            return False

        self.running = True

        # Set up signal handlers
        def signal_handler(signum, frame):
            logger.info(f"🛑 Received signal {signum}. Shutting down staging bot...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Send startup alert
            await self._send_staging_alert("STARTUP", "Staging bot started successfully")

            # Main monitoring loop
            await self.monitor_loop()

        except Exception as e:
            logger.error(f"❌ Fatal error in staging bot: {e}")
            await self._send_staging_alert("FATAL_ERROR", str(e))
            return False
        finally:
            await self.shutdown()

        return True

    async def monitor_loop(self):
        """Main monitoring loop for staging"""
        logger.info("🔄 Starting staging monitoring loop...")
        logger.info(f"Monitor interval: {self.settings.monitoring.monitor_interval}s")
        logger.info(f"Target wallets: {len(self.settings.monitoring.target_wallets)}")

        while self.running:
            try:
                cycle_start = datetime.now()

                # Check if we need to reset daily counters
                await self._check_daily_reset()

                # Monitor wallets for trades
                detected_trades = await self.wallet_monitor.monitor_wallets()

                if detected_trades:
                    logger.info(f"🎯 Staging: Detected {len(detected_trades)} potential trades")

                    # Filter trades based on staging limits
                    allowed_trades = await self._filter_staging_trades(detected_trades)

                    if allowed_trades:
                        # Execute trades
                        await self._execute_staging_trades(allowed_trades)
                    else:
                        logger.info(
                            "ℹ️ Staging: No trades allowed (daily limit reached or filtered)"
                        )

                # Periodic health check
                await self._periodic_staging_health_check()

                # Calculate cycle time
                cycle_time = (datetime.now() - cycle_start).total_seconds()
                logger.debug(f"Staging cycle completed in {cycle_time:.2f}s")

                # Wait for next cycle
                await asyncio.sleep(self.settings.monitoring.monitor_interval)

            except Exception as e:
                logger.error(f"❌ Error in staging monitoring loop: {e}")
                await self._send_staging_alert("MONITOR_LOOP_ERROR", str(e))
                await asyncio.sleep(10)  # Brief pause before retry

    async def _check_daily_reset(self):
        """Reset daily counters if needed"""
        today = datetime.now().date()
        if today > self.staging_last_reset:
            self.staging_daily_trades = 0
            self.staging_last_reset = today
            logger.info("🔄 Staging: Daily trade counter reset")

    async def _filter_staging_trades(self, trades):
        """Filter trades based on staging limits"""
        allowed_trades = []

        for trade in trades:
            # Check daily trade limit
            if self.staging_daily_trades >= self.settings.staging.max_trades_per_day:
                logger.info("ℹ️ Staging: Daily trade limit reached, skipping trade")
                continue

            # Check position size limits
            trade_amount = trade.get("amount", 0)
            if trade_amount > self.settings.risk.max_position_size:
                logger.info(
                    f"ℹ️ Staging: Trade amount ${trade_amount} exceeds max position size, skipping"
                )
                continue

            # Additional staging filters can be added here
            allowed_trades.append(trade)

        return allowed_trades

    async def _execute_staging_trades(self, trades):
        """Execute trades in staging environment"""
        logger.info(f"📈 Staging: Executing {len(trades)} trades")

        for trade in trades:
            try:
                if self.settings.staging.enable_paper_trading:
                    # Paper trading mode
                    result = await self._simulate_staging_trade(trade)
                else:
                    # Real testnet trading
                    result = await self.trade_executor.execute_copy_trade(trade)

                if result and result.get("status") == "success":
                    self.staging_trade_count += 1
                    self.staging_daily_trades += 1

                    await self._send_staging_alert(
                        "TRADE_EXECUTED",
                        f"Trade {self.staging_trade_count}: {trade.get('market', 'Unknown')} - "
                        f"${trade.get('amount', 0):.2f} ({'PAPER' if self.settings.staging.enable_paper_trading else 'TESTNET'})",
                    )

                    logger.info(
                        f"✅ Staging trade {self.staging_trade_count} executed successfully"
                    )

                else:
                    logger.warning(f"⚠️ Staging trade failed: {result}")

            except Exception as e:
                logger.error(f"❌ Error executing staging trade: {e}")
                await self._send_staging_alert("TRADE_EXECUTION_ERROR", str(e))

    async def _simulate_staging_trade(self, trade):
        """Simulate a trade for paper trading mode"""
        logger.info(f"🎭 Simulating staging trade: {trade.get('market', 'Unknown')}")

        # Simulate some processing time
        await asyncio.sleep(0.1)

        # Simulate success/failure randomly (90% success rate for testing)
        import random

        success = random.random() < 0.9

        if success:
            return {
                "status": "success",
                "order_id": f"paper_{datetime.now().timestamp()}",
                "amount": trade.get("amount", 0),
            }
        else:
            return {"status": "failed", "reason": "Simulated failure for testing"}

    async def _periodic_staging_health_check(self):
        """Periodic health check for staging"""
        # Run health checks every 5 minutes
        if int(datetime.now().timestamp()) % 300 == 0:
            await self._run_staging_health_check()

    async def _run_staging_health_check(self):
        """Run comprehensive staging health check"""
        logger.info("🏥 Running staging health check...")

        health_status = {
            "timestamp": datetime.now().isoformat(),
            "environment": "staging",
            "uptime_hours": (datetime.now() - self.staging_start_time).total_seconds() / 3600,
            "total_trades": self.staging_trade_count,
            "daily_trades": self.staging_daily_trades,
            "daily_limit": self.settings.staging.max_trades_per_day,
        }

        try:
            # Check RPC connection
            from web3 import Web3

            web3 = Web3(Web3.HTTPProvider(self.settings.network.polygon_rpc_url))
            health_status["rpc_connected"] = web3.is_connected()
            health_status["current_block"] = web3.eth.block_number if web3.is_connected() else None

            # Check wallet balance
            if hasattr(self, "clob_client") and self.clob_client:
                balance = await self.clob_client.get_balance()
                health_status["wallet_balance"] = balance

            # Check memory usage
            import psutil

            process = psutil.Process()
            health_status["memory_mb"] = process.memory_info().rss / 1024 / 1024

            health_status["status"] = "healthy"
            logger.info("✅ Staging health check passed")

        except Exception as e:
            health_status["status"] = "error"
            health_status["error"] = str(e)
            logger.error(f"❌ Staging health check failed: {e}")

        # Log health status
        logger.info(
            f"🏥 Staging Health: {health_status['status']} | "
            f"Trades: {health_status['total_trades']} | "
            f"Memory: {health_status.get('memory_mb', 0):.1f}MB"
        )

        # Send alert if unhealthy
        if health_status["status"] != "healthy":
            await self._send_staging_alert("HEALTH_CHECK_FAILED", str(health_status))

    async def _send_staging_alert(self, alert_type: str, message: str):
        """Send staging-specific alert"""
        staging_message = f"{self.settings.alerts.staging_alert_prefix}{alert_type}: {message}"

        if self.settings.alerts.telegram_bot_token and self.settings.alerts.telegram_chat_id:
            try:
                await send_error_alert(
                    staging_message,
                    {
                        "environment": "staging",
                        "alert_type": alert_type,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            except Exception as e:
                logger.error(f"Failed to send staging alert: {e}")

        logger.info(f"🚨 Staging Alert: {staging_message}")

    async def shutdown(self):
        """Shutdown staging bot gracefully"""
        logger.info("🛑 Shutting down staging bot...")

        self.running = False

        # Send shutdown alert
        await self._send_staging_alert("SHUTDOWN", "Staging bot shutting down")

        # Cleanup resources
        if self.wallet_monitor:
            # Any cleanup needed
            pass

        if self.trade_executor:
            # Any cleanup needed
            pass

        logger.info("✅ Staging bot shutdown complete")


async def main():
    """Main entry point for staging bot"""
    logger.info("🚀 Starting Polymarket Copy Trading Bot (STAGING ENVIRONMENT)")
    logger.info("=" * 60)
    logger.info("🚨 WARNING: This is a STAGING ENVIRONMENT 🚨")
    logger.info("🚨 ONLY USE TESTNET FUNDS AND KEYS 🚨")
    logger.info("🚨 DO NOT USE MAINNET CONFIGURATION 🚨")
    logger.info("=" * 60)

    bot = PolymarketStagingBot()

    try:
        success = await bot.start()
        if success:
            logger.info("✅ Staging bot completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Staging bot failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("🛑 Staging bot interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error in staging bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Validate that we're not accidentally running in production
    if not staging_settings.staging.environment == "staging":
        print("❌ ERROR: This script is for staging only!")
        sys.exit(1)

    # Run the staging bot
    asyncio.run(main())
