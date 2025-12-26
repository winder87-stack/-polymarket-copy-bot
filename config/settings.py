import json
import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, root_validator, validator

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/config.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = Path(".env")
if env_path.exists():
    load_dotenv(env_path)
else:
    logger.warning(".env file not found. Using environment variables only.")


class RiskManagementConfig(BaseModel):
    max_position_size: float = Field(default=50.0, description="Maximum USDC per position", ge=1.0)
    max_daily_loss: float = Field(default=100.0, description="Circuit breaker threshold", ge=0.0)
    min_trade_amount: float = Field(
        default=1.0, description="Ignore trades smaller than this", ge=0.01
    )
    max_concurrent_positions: int = Field(default=10, description="Maximum open positions", ge=1)
    stop_loss_percentage: float = Field(default=0.15, description="15% stop loss", ge=0.01, le=0.5)
    take_profit_percentage: float = Field(
        default=0.25, description="25% take profit", ge=0.01, le=1.0
    )
    max_slippage: float = Field(default=0.02, description="2% maximum slippage", ge=0.001, le=0.1)


class NetworkConfig(BaseModel):
    clob_host: str = Field(
        default="https://clob.polymarket.com", description="Polymarket CLOB host"
    )
    chain_id: int = Field(default=137, description="Polygon mainnet")
    polygon_rpc_url: str = Field(default="https://polygon-rpc.com", description="Polygon RPC URL")
    polygonscan_api_key: str = Field(default="", description="Polygonscan API key")


class TradingConfig(BaseModel):
    private_key: str = Field(..., description="Wallet private key")
    wallet_address: Optional[str] = Field(
        None, description="Wallet address (auto-calculated if empty)"
    )
    gas_limit: int = Field(default=300000, description="Default gas limit", ge=21000)
    max_gas_price: int = Field(default=100, description="Maximum gas price in gwei", ge=1)
    gas_price_multiplier: float = Field(
        default=1.1, description="Gas price multiplier for priority", ge=1.0, le=2.0
    )


class MonitoringConfig(BaseModel):
    monitor_interval: int = Field(
        default=15, description="Seconds between wallet checks", ge=5, le=300
    )
    wallets_file: str = Field(default="config/wallets.json", description="Path to wallets config")
    target_wallets: List[str] = Field(
        default_factory=list, description="List of wallet addresses to monitor"
    )
    min_confidence_score: float = Field(
        default=0.7, description="Minimum confidence score for trade detection", ge=0.1, le=0.95
    )


class AlertingConfig(BaseModel):
    telegram_bot_token: Optional[str] = Field(None, description="Telegram bot token")
    telegram_chat_id: Optional[str] = Field(None, description="Telegram chat ID")
    alert_on_trade: bool = Field(default=True, description="Send alerts on trade execution")
    alert_on_error: bool = Field(default=True, description="Send alerts on errors")
    alert_on_circuit_breaker: bool = Field(
        default=True, description="Send alerts when circuit breaker activates"
    )


class LoggingConfig(BaseModel):
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/polymarket_bot.log", description="Log file path")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format"
    )


class Settings(BaseModel):
    risk: RiskManagementConfig = Field(default_factory=RiskManagementConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    alerts: AlertingConfig = Field(default_factory=AlertingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Environment variables mapping
    env_mappings: ClassVar[Dict[str, str]] = {
        "network.clob_host": "CLOB_HOST",
        "network.chain_id": "CHAIN_ID",
        "network.polygon_rpc_url": "POLYGON_RPC_URL",
        "network.polygonscan_api_key": "POLYGONSCAN_API_KEY",
        "risk.max_slippage": "MAX_SLIPPAGE",
        "risk.max_position_size": "MAX_POSITION_SIZE",
        "risk.max_daily_loss": "MAX_DAILY_LOSS",
        "risk.min_trade_amount": "MIN_TRADE_AMOUNT",
        "monitoring.monitor_interval": "MONITOR_INTERVAL",
        "trading.max_gas_price": "MAX_GAS_PRICE",
        "trading.gas_limit": "DEFAULT_GAS_LIMIT",
        "risk.max_concurrent_positions": "MAX_CONCURRENT_POSITIONS",
        "risk.stop_loss_percentage": "STOP_LOSS_PERCENTAGE",
        "risk.take_profit_percentage": "TAKE_PROFIT_PERCENTAGE",
        "logging.log_level": "LOG_LEVEL",
        "logging.log_file": "LOG_FILE",
        "alerts.telegram_bot_token": "TELEGRAM_BOT_TOKEN",
        "alerts.telegram_chat_id": "TELEGRAM_CHAT_ID",
        "trading.private_key": "PRIVATE_KEY",
        "trading.wallet_address": "WALLET_ADDRESS",
        "monitoring.min_confidence_score": "MIN_CONFIDENCE_SCORE",
    }

    @validator("trading", pre=True)
    def validate_trading_config(cls, v):
        if not v.get("private_key"):
            private_key = os.getenv("PRIVATE_KEY")
            if not private_key:
                raise ValueError("PRIVATE_KEY must be set in environment variables")
            v["private_key"] = private_key

        wallet_address = os.getenv("WALLET_ADDRESS")
        if wallet_address:
            v["wallet_address"] = wallet_address

        return v

    @validator("monitoring", pre=True)
    def load_wallets(cls, v):
        wallets_file = v.get("wallets_file", "config/wallets.json")
        if os.path.exists(wallets_file):
            try:
                with open(wallets_file, "r") as f:
                    wallets_config = json.load(f)
                    v["target_wallets"] = wallets_config.get("target_wallets", [])
                    v["min_confidence_score"] = wallets_config.get("min_confidence_score", 0.7)
                    logger.info(f"Loaded {len(v['target_wallets'])} target wallets")
            except Exception as e:
                logger.error(f"Error loading wallets config: {e}")
                v["target_wallets"] = []
        return v

    @root_validator(pre=True)
    def load_from_env(cls, values):
        """Load configuration from environment variables"""
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
                elif final_key in ["alert_on_trade", "alert_on_error", "alert_on_circuit_breaker"]:
                    current[final_key] = env_value.lower() in ["true", "1", "yes", "on"]
                else:
                    current[final_key] = env_value

        return values

    def validate_critical_settings(self):
        """Validate critical settings before starting"""
        if not self.trading.private_key.startswith("0x"):
            raise ValueError("Private key must start with '0x'")

        if len(self.trading.private_key) != 66:  # 0x + 64 hex chars
            raise ValueError("Invalid private key length")

        if len(self.monitoring.target_wallets) == 0:
            logger.warning("No target wallets configured. Bot will run but not copy any trades.")

        if self.risk.max_daily_loss <= 0:
            raise ValueError("MAX_DAILY_LOSS must be greater than 0")

        if self.risk.max_position_size <= 0:
            raise ValueError("MAX_POSITION_SIZE must be greater than 0")

        if not self.network.polygon_rpc_url.startswith("http"):
            raise ValueError("POLYGON_RPC_URL must be a valid HTTP/HTTPS URL")

        # Test RPC connection
        try:
            from web3 import Web3

            web3 = Web3(Web3.HTTPProvider(self.network.polygon_rpc_url))
            if not web3.is_connected():
                logger.warning(
                    "❌ Could not connect to Polygon RPC endpoint. Some features may not work."
                )
        except Exception as e:
            logger.warning(f"⚠️ Error testing RPC connection: {e}")

        logger.info("✅ All critical settings validated successfully")
        logger.info(
            f"Risk parameters: Max position=${self.risk.max_position_size:.2f}, Max daily loss=${self.risk.max_daily_loss:.2f}"
        )
        logger.info(
            f"Monitoring {len(self.monitoring.target_wallets)} wallets every {self.monitoring.monitor_interval} seconds"
        )

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True


# Singleton instance
settings = Settings()

# Create logs directory if it doesn't exist
log_dir = os.path.dirname(settings.logging.log_file)
os.makedirs(log_dir, exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=getattr(logging, settings.logging.log_level.upper(), logging.INFO),
    format=settings.logging.log_format,
    handlers=[logging.FileHandler(settings.logging.log_file), logging.StreamHandler()],
)

logger.info("✅ Settings loaded successfully")
logger.info(f"Network: {settings.network.clob_host}")
logger.info(f"Risk management enabled: Max daily loss=${settings.risk.max_daily_loss:.2f}")

if __name__ == "__main__":
    settings.validate_critical_settings()
    print("✅ Configuration validated successfully")
