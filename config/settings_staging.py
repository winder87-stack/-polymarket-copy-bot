import json
import logging
import os
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, root_validator, validator

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/staging_config.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load environment variables - staging specific
env_path = Path(".env.staging")
if env_path.exists():
    load_dotenv(env_path)
    logger.info("✅ Loaded staging environment variables from .env.staging")
else:
    logger.warning(".env.staging file not found. Using environment variables only.")


class RiskManagementConfig(BaseModel):
    max_position_size: float = Field(
        default=5.0, description="Maximum USDC per position (staging: $5)", ge=1.0
    )
    max_daily_loss: float = Field(
        default=10.0, description="Circuit breaker threshold (staging: $10)", ge=0.0
    )
    min_trade_amount: float = Field(
        default=0.5,
        description="Ignore trades smaller than this (staging: $0.50)",
        ge=0.01,
    )
    max_concurrent_positions: int = Field(
        default=3, description="Maximum open positions (staging: 3)", ge=1
    )
    stop_loss_percentage: float = Field(
        default=0.10,
        description="10% stop loss (staging: more conservative)",
        ge=0.01,
        le=0.5,
    )
    take_profit_percentage: float = Field(
        default=0.15,
        description="15% take profit (staging: more conservative)",
        ge=0.01,
        le=1.0,
    )
    max_slippage: float = Field(
        default=0.05,
        description="5% maximum slippage (staging: higher tolerance)",
        ge=0.001,
        le=0.1,
    )


class NetworkConfig(BaseModel):
    clob_host: str = Field(
        default="https://clob.polymarket.com", description="Polymarket CLOB host"
    )
    chain_id: int = Field(default=80001, description="Polygon Mumbai testnet")
    polygon_rpc_url: str = Field(
        default="https://rpc-mumbai.maticvigil.com",
        description="Polygon Mumbai testnet RPC",
    )
    polygonscan_api_key: str = Field(default="", description="Polygonscan API key")


class TradingConfig(BaseModel):
    private_key: str = Field(..., description="Wallet private key (staging wallet)")
    wallet_address: Optional[str] = Field(
        None, description="Wallet address (auto-calculated if empty)"
    )
    gas_limit: int = Field(default=300000, description="Default gas limit", ge=21000)
    max_gas_price: int = Field(
        default=50, description="Maximum gas price in gwei (staging: lower)", ge=1
    )
    gas_price_multiplier: float = Field(
        default=1.2, description="Gas price multiplier for priority", ge=1.0, le=2.0
    )


class MonitoringConfig(BaseModel):
    monitor_interval: int = Field(
        default=30,
        description="Seconds between wallet checks (staging: slower)",
        ge=5,
        le=300,
    )
    wallets_file: str = Field(
        default="config/wallets_staging.json",
        description="Path to staging wallets config",
    )
    target_wallets: List[str] = Field(
        default_factory=list, description="List of wallet addresses to monitor"
    )
    min_confidence_score: float = Field(
        default=0.8,
        description="Minimum confidence score (staging: higher threshold)",
        ge=0.1,
        le=0.95,
    )


class AlertingConfig(BaseModel):
    telegram_bot_token: Optional[str] = Field(
        None, description="Telegram bot token (staging channel)"
    )
    telegram_chat_id: Optional[str] = Field(
        None, description="Telegram chat ID (staging channel)"
    )
    alert_on_trade: bool = Field(
        default=True, description="Send alerts on trade execution"
    )
    alert_on_error: bool = Field(default=True, description="Send alerts on errors")
    alert_on_circuit_breaker: bool = Field(
        default=True, description="Send alerts when circuit breaker activates"
    )
    staging_alert_prefix: str = Field(
        default="[STAGING] ", description="Prefix for staging alerts"
    )


class LoggingConfig(BaseModel):
    log_level: str = Field(
        default="DEBUG", description="Logging level (staging: more verbose)"
    )
    log_file: str = Field(
        default="logs/polymarket_bot_staging.log", description="Staging log file path"
    )
    log_format: str = Field(
        default="%(asctime)s [STAGING] - %(name)s - %(levelname)s - %(message)s",
        description="Log format with staging indicator",
    )


class StagingConfig(BaseModel):
    """Additional staging-specific configuration"""

    environment: str = Field(default="staging", description="Environment identifier")
    testnet_faucet_url: str = Field(
        default="https://faucet.polygon.technology", description="Testnet faucet URL"
    )
    enable_paper_trading: bool = Field(
        default=False, description="Enable paper trading mode"
    )
    staging_duration_days: int = Field(
        default=7, description="Staging test duration in days"
    )
    max_trades_per_day: int = Field(
        default=5, description="Maximum trades per day in staging"
    )
    enable_extended_logging: bool = Field(
        default=True, description="Enable detailed logging for debugging"
    )
    alert_on_all_events: bool = Field(
        default=True, description="Alert on all significant events"
    )


class Settings(BaseModel):
    risk: RiskManagementConfig = Field(default_factory=RiskManagementConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    alerts: AlertingConfig = Field(default_factory=AlertingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    staging: StagingConfig = Field(default_factory=StagingConfig)

    # Environment variables mapping (staging-specific)
    env_mappings: ClassVar[Dict[str, str]] = {
        "network.clob_host": "STAGING_CLOB_HOST",
        "network.chain_id": "STAGING_CHAIN_ID",
        "network.polygon_rpc_url": "STAGING_POLYGON_RPC_URL",
        "network.polygonscan_api_key": "STAGING_POLYGONSCAN_API_KEY",
        "risk.max_slippage": "STAGING_MAX_SLIPPAGE",
        "risk.max_position_size": "STAGING_MAX_POSITION_SIZE",
        "risk.max_daily_loss": "STAGING_MAX_DAILY_LOSS",
        "risk.min_trade_amount": "STAGING_MIN_TRADE_AMOUNT",
        "monitoring.monitor_interval": "STAGING_MONITOR_INTERVAL",
        "trading.max_gas_price": "STAGING_MAX_GAS_PRICE",
        "trading.gas_limit": "STAGING_DEFAULT_GAS_LIMIT",
        "risk.max_concurrent_positions": "STAGING_MAX_CONCURRENT_POSITIONS",
        "risk.stop_loss_percentage": "STAGING_STOP_LOSS_PERCENTAGE",
        "risk.take_profit_percentage": "STAGING_TAKE_PROFIT_PERCENTAGE",
        "logging.log_level": "STAGING_LOG_LEVEL",
        "logging.log_file": "STAGING_LOG_FILE",
        "alerts.telegram_bot_token": "STAGING_TELEGRAM_BOT_TOKEN",
        "alerts.telegram_chat_id": "STAGING_TELEGRAM_CHAT_ID",
        "trading.private_key": "STAGING_PRIVATE_KEY",
        "trading.wallet_address": "STAGING_WALLET_ADDRESS",
        "monitoring.min_confidence_score": "STAGING_MIN_CONFIDENCE_SCORE",
        "staging.enable_paper_trading": "STAGING_PAPER_TRADING",
        "staging.max_trades_per_day": "STAGING_MAX_TRADES_PER_DAY",
    }

    @validator("trading", pre=True)
    def validate_trading_config(cls, v):
        if not v.get("private_key"):
            private_key = os.getenv("STAGING_PRIVATE_KEY")
            if not private_key:
                raise ValueError(
                    "STAGING_PRIVATE_KEY must be set in environment variables for staging"
                )
            v["private_key"] = private_key

        wallet_address = os.getenv("STAGING_WALLET_ADDRESS")
        if wallet_address:
            v["wallet_address"] = wallet_address

        return v

    @validator("monitoring", pre=True)
    def load_wallets(cls, v):
        wallets_file = v.get("wallets_file", "config/wallets_staging.json")
        if os.path.exists(wallets_file):
            try:
                with open(wallets_file, "r") as f:
                    wallets_config = json.load(f)
                    v["target_wallets"] = wallets_config.get("target_wallets", [])
                    v["min_confidence_score"] = wallets_config.get(
                        "min_confidence_score", 0.8
                    )
                    logger.info(
                        f"✅ Staging: Loaded {len(v['target_wallets'])} target wallets from {wallets_file}"
                    )
            except Exception as e:
                logger.error(f"❌ Staging: Error loading wallets config: {e}")
                v["target_wallets"] = []
        else:
            logger.warning(f"⚠️ Staging: Wallets config file {wallets_file} not found")
            v["target_wallets"] = []
        return v

    @root_validator(pre=True)
    def load_from_env(cls, values):
        """Load configuration from environment variables (staging-specific)"""
        for model_path, env_var in cls.env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                keys = model_path.split(".")
                current = values

                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]

                # Convert to appropriate type
                final_key = keys[-1]
                if final_key in [
                    "chain_id",
                    "gas_limit",
                    "max_gas_price",
                    "monitor_interval",
                    "max_concurrent_positions",
                    "max_trades_per_day",
                ]:
                    try:
                        current[final_key] = int(env_value)
                    except ValueError:
                        pass
                elif final_key in [
                    "max_slippage",
                    "max_position_size",
                    "max_daily_loss",
                    "min_trade_amount",
                    "stop_loss_percentage",
                    "take_profit_percentage",
                    "gas_price_multiplier",
                    "min_confidence_score",
                ]:
                    try:
                        current[final_key] = float(env_value)
                    except ValueError:
                        pass
                elif final_key in [
                    "alert_on_trade",
                    "alert_on_error",
                    "alert_on_circuit_breaker",
                    "enable_paper_trading",
                    "enable_extended_logging",
                    "alert_on_all_events",
                ]:
                    current[final_key] = env_value.lower() in ["true", "1", "yes", "on"]
                else:
                    current[final_key] = env_value

        return values

    def validate_critical_settings(self):
        """Validate critical settings for staging environment"""
        logger.info("🔍 Validating staging environment configuration...")

        if not self.trading.private_key.startswith("0x"):
            raise ValueError("Staging private key must start with '0x'")

        if len(self.trading.private_key) != 66:  # 0x + 64 hex chars
            raise ValueError("Invalid staging private key length")

        if len(self.monitoring.target_wallets) == 0:
            logger.warning(
                "⚠️ Staging: No target wallets configured. Bot will run but not copy any trades."
            )

        if self.risk.max_daily_loss <= 0:
            raise ValueError("STAGING_MAX_DAILY_LOSS must be greater than 0")

        if self.risk.max_position_size <= 0:
            raise ValueError("STAGING_MAX_POSITION_SIZE must be greater than 0")

        if not self.network.polygon_rpc_url.startswith("http"):
            raise ValueError("STAGING_POLYGON_RPC_URL must be a valid HTTP/HTTPS URL")

        # Validate testnet settings
        if self.network.chain_id != 80001:
            logger.warning(
                f"⚠️ Staging: Using chain_id {self.network.chain_id}, expected Mumbai testnet (80001)"
            )

        # Test RPC connection
        try:
            from web3 import Web3

            web3 = Web3(Web3.HTTPProvider(self.network.polygon_rpc_url))
            if not web3.is_connected():
                logger.warning(
                    "❌ Staging: Could not connect to Polygon Mumbai testnet RPC endpoint."
                )
            else:
                logger.info("✅ Staging: Connected to Polygon Mumbai testnet")
                logger.info(f"   Block number: {web3.eth.block_number}")
        except Exception as e:
            logger.warning(f"⚠️ Staging: Error testing RPC connection: {e}")

        # Validate staging-specific settings
        if self.staging.max_trades_per_day <= 0:
            raise ValueError("STAGING_MAX_TRADES_PER_DAY must be greater than 0")

        logger.info("✅ Staging: All critical settings validated successfully")
        logger.info(
            f"   Risk parameters: Max position=${self.risk.max_position_size:.2f}, Max daily loss=${self.risk.max_daily_loss:.2f}"
        )
        logger.info(
            f"   Monitoring {len(self.monitoring.target_wallets)} wallets every {self.monitoring.monitor_interval} seconds"
        )
        logger.info(
            f"   Environment: {self.staging.environment}, Max trades/day: {self.staging.max_trades_per_day}"
        )
        logger.info(
            f"   Paper trading: {'ENABLED' if self.staging.enable_paper_trading else 'DISABLED'}"
        )

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True


# Singleton instance for staging
staging_settings = Settings()

# Create logs directory if it doesn't exist
log_dir = os.path.dirname(staging_settings.logging.log_file)
os.makedirs(log_dir, exist_ok=True)

# Configure root logger for staging
logging.basicConfig(
    level=getattr(logging, staging_settings.logging.log_level.upper(), logging.DEBUG),
    format=staging_settings.logging.log_format,
    handlers=[
        logging.FileHandler(staging_settings.logging.log_file),
        logging.StreamHandler(),
    ],
)

logger.info("✅ Staging environment settings loaded successfully")
logger.info(
    f"Network: {staging_settings.network.polygon_rpc_url} (Chain ID: {staging_settings.network.chain_id})"
)
logger.info(
    f"Risk management: Max daily loss=${staging_settings.risk.max_daily_loss:.2f}"
)
logger.info("🚨 STAGING ENVIRONMENT - ALL TRADES ARE TESTNET ONLY 🚨")

if __name__ == "__main__":
    staging_settings.validate_critical_settings()
    print("✅ Staging configuration validated successfully")
    print("🚨 STAGING ENVIRONMENT - TESTNET ONLY 🚨")
    print(f"Max position size: ${staging_settings.risk.max_position_size}")
    print(f"Max daily loss: ${staging_settings.risk.max_daily_loss}")
    print(f"Paper trading: {staging_settings.staging.enable_paper_trading}")
