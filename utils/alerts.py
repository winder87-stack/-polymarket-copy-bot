import asyncio
import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from config.settings import settings

# Import staging settings if available
try:
    from config.settings_staging import staging_settings

    STAGING_MODE = True
except (ImportError, Exception):
    # Handle both ImportError and ValidationError (when STAGING_PRIVATE_KEY is missing)
    STAGING_MODE = False
    staging_settings = None

logger = logging.getLogger(__name__)


class TelegramAlertManager:
    def __init__(self, staging_mode: bool = False) -> None:
        if staging_mode and STAGING_MODE and staging_settings:
            # Use staging configuration
            self.bot_token = staging_settings.alerts.telegram_bot_token
            self.chat_id = staging_settings.alerts.telegram_chat_id
            self.enabled = bool(
                self.bot_token
                and self.chat_id
                and staging_settings.alerts.alert_on_trade
            )
            self.staging_mode = True
            self.alert_prefix = staging_settings.alerts.staging_alert_prefix
            logger.info("🚨 Initialized STAGING alert manager")
        else:
            # Use production configuration
            self.bot_token = settings.alerts.telegram_bot_token
            self.chat_id = settings.alerts.telegram_chat_id
            self.enabled = bool(
                self.bot_token and self.chat_id and settings.alerts.alert_on_trade
            )
            self.staging_mode = False
            self.alert_prefix = ""

        self.last_alert_time = 0
        self.alert_cooldown = 60  # 1 minute cooldown between alerts

        if self.enabled:
            try:
                from telegram import Bot

                self.bot = Bot(token=self.bot_token)
                logger.info("✅ Telegram bot initialized successfully")
            except ImportError:
                logger.error(
                    "❌ Telegram library not installed. Install with: pip install python-telegram-bot"
                )
                self.enabled = False
            except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
                logger.error(
                    f"❌ Network error initializing Telegram bot: {str(e)[:100]}"
                )
                self.enabled = False
            except (ValueError, KeyError, ImportError) as e:
                logger.error(
                    f"❌ Configuration error initializing Telegram bot: {str(e)[:100]}"
                )
                self.enabled = False
            except Exception as e:
                logger.critical(
                    f"❌ Unexpected error initializing Telegram bot: {str(e)}",
                    exc_info=True,
                )
                self.enabled = False
        else:
            logger.info("ℹ️ Telegram alerts disabled or not configured")

    async def send_alert(
        self, message: str, parse_mode: str = "Markdown", force: bool = False
    ) -> bool:
        """Send alert via Telegram with cooldown protection"""
        if not self.enabled and not force:
            return False

        # Add staging prefix if in staging mode
        if self.staging_mode and self.alert_prefix:
            message = f"{self.alert_prefix}{message}"

        # Cooldown protection
        now = time.time()
        if now - self.last_alert_time < self.alert_cooldown and not force:
            logger.debug(
                f"Skipping Telegram alert due to cooldown ({self.alert_cooldown}s)"
            )
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id, text=message, parse_mode=parse_mode
            )
            self.last_alert_time = now
            env_indicator = "[STAGING] " if self.staging_mode else ""
            logger.info(f"✅ {env_indicator}Telegram alert sent successfully")
            return True
        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            env_indicator = "[STAGING] " if self.staging_mode else ""
            logger.error(
                f"❌ {env_indicator}Network error sending Telegram alert: {str(e)[:100]}"
            )
            return False
        except (ValueError, TypeError, KeyError) as e:
            env_indicator = "[STAGING] " if self.staging_mode else ""
            logger.error(
                f"❌ {env_indicator}Data error sending Telegram alert: {str(e)[:100]}"
            )
            return False
        except Exception as e:
            env_indicator = "[STAGING] " if self.staging_mode else ""
            logger.critical(
                f"❌ {env_indicator}Unexpected error sending Telegram alert: {str(e)}",
                exc_info=True,
            )
            return False

    async def send_error_alert(
        self, error: str, context: Optional[Dict[str, Any]] = None
    ):
        """Send error alert with context"""
        if not settings.alerts.alert_on_error:
            return

        error_message = f"❌ **ERROR**\n{error}"

        if context:
            context_str = "\n".join(
                [
                    f"{k}: {v}"
                    for k, v in context.items()
                    if k not in ["private_key", "secret"]
                ]
            )
            error_message += f"\n\n**Context:**\n{context_str}"

        await self.send_alert(error_message)

    async def send_trade_alert(self, trade_details: Dict[str, Any]) -> None:
        """Send trade execution alert"""
        if not settings.alerts.alert_on_trade:
            return

        message = (
            f"✅ **TRADE EXECUTED**\n"
            f"Market: `{trade_details.get('condition_id', 'Unknown')[-8:]}`\n"
            f"Side: {trade_details.get('side', 'Unknown')}\n"
            f"Amount: {trade_details.get('amount', 0):.4f}\n"
            f"Price: ${trade_details.get('price', 0):.4f}\n"
            f"Order ID: `{trade_details.get('order_id', 'Unknown')[-8:]}`\n"
            f"Wallet: `{trade_details.get('wallet_address', 'Unknown')[-6:]}`"
        )

        await self.send_alert(message)

    async def send_performance_report(self, metrics: Dict[str, Any]) -> None:
        """Send daily performance report"""
        if (
            not hasattr(self, "last_report_time")
            or time.time() - getattr(self, "last_report_time", 0) > 3600
        ):
            report = (
                f"📊 **PERFORMANCE REPORT**\n"
                f"Total Trades: {metrics.get('total_trades', 0)}\n"
                f"Success Rate: {metrics.get('success_rate', 0):.1%}\n"
                f"Daily P&L: ${metrics.get('total_pnl', 0):.2f}\n"
                f"Open Positions: {metrics.get('open_positions', 0)}\n"
                f"Daily Loss: ${metrics.get('daily_loss', 0):.2f}\n"
                f"Uptime: {metrics.get('uptime_hours', 0):.1f} hours"
            )

            await self.send_alert(report, force=True)
            self.last_report_time = time.time()


# Global alert manager instances
alert_manager = TelegramAlertManager(staging_mode=False)  # Production alerts
staging_alert_manager = (
    TelegramAlertManager(staging_mode=True) if STAGING_MODE else None
)


# Convenience functions
async def send_telegram_alert(
    message: str, parse_mode: str = "Markdown", force: bool = False
) -> bool:
    return await alert_manager.send_alert(message, parse_mode, force)


async def send_error_alert(
    error: str, context: Optional[Dict[str, Any]] = None
) -> None:
    """Send error alert with secure logging"""
    from utils.logging_security import SecureLogger

    # Log the error securely before sending alert
    SecureLogger.log("error", f"Error alert triggered: {error[:100]}", context or {})

    await alert_manager.send_error_alert(error, context)


async def send_trade_alert(trade_details: Dict[str, Any]) -> None:
    await alert_manager.send_trade_alert(trade_details)


async def send_performance_report(metrics: Dict[str, Any]) -> None:
    await alert_manager.send_performance_report(metrics)


# Staging-specific convenience functions
async def send_staging_alert(
    message: str, parse_mode: str = "Markdown", force: bool = False
) -> bool:
    """Send staging-specific alert"""
    if staging_alert_manager:
        return await staging_alert_manager.send_alert(message, parse_mode, force)
    else:
        logger.warning("Staging alert manager not available")
        return False


async def send_staging_error_alert(
    error: str, context: Optional[Dict[str, Any]] = None
) -> None:
    """Send staging-specific error alert"""
    if staging_alert_manager:
        await staging_alert_manager.send_error_alert(error, context)
    else:
        logger.warning("Staging alert manager not available")


async def send_staging_trade_alert(trade_details: Dict[str, Any]) -> None:
    """Send staging-specific trade alert"""
    if staging_alert_manager:
        await staging_alert_manager.send_trade_alert(trade_details)
    else:
        logger.warning("Staging alert manager not available")


async def test_alerts() -> None:
    """Test alert functionality"""
    logger.info("🧪 Testing alert functionality...")

    if not alert_manager.enabled:
        logger.warning("Telegram alerts not configured. Skipping tests.")
        return

    # Test error alert
    await send_error_alert("Test error alert", {"component": "test", "severity": "low"})

    # Test trade alert
    await send_trade_alert(
        {
            "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
            "side": "BUY",
            "amount": 10.5,
            "price": 0.65,
            "order_id": "test_order_123",
            "wallet_address": "0xabcdef1234567890abcdef1234567890abcdef12",
        }
    )

    # Test performance report
    await send_performance_report(
        {
            "total_trades": 42,
            "success_rate": 0.85,
            "total_pnl": 123.45,
            "open_positions": 3,
            "daily_loss": 10.0,
            "uptime_hours": 24.5,
        }
    )

    logger.info("✅ Alert tests completed")


if __name__ == "__main__":
    # Run test alerts
    asyncio.run(test_alerts())
