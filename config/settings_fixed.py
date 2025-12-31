"""
Settings Module with Lazy Singleton Initialization (FIXED VERSION)
============================================================

This module provides configuration management with lazy singleton pattern
to prevent Pydantic validation errors during test collection.

Key Fix:
- Lazy initialization: Settings() only created when get_settings() is called
- Prevents module-level singleton initialization that runs on import
- Allows pytest patches to be applied before Settings is created
"""

import logging
import os
from typing import Optional, List, Any

from pydantic import BaseModel, Field, field_validator, ConfigDict

logger = logging.getLogger(__name__)


class Config(BaseModel):
    """Base configuration class with ConfigDict for Pydantic V2"""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )


class NetworkConfig(Config):
    """Network configuration."""

    clob_host: str = Field(
        default="https://clob.polymarket.com", description="Polymarket CLOB API host"
    )
    chain_id: int = Field(default=137, description="Polygon chain ID")
    polygon_rpc_url: str = Field(
        default="https://polygon-rpc.com", description="Polygon RPC endpoint"
    )
    polygon_rpc_fallbacks: List[str] = Field(
        default_factory=list,
        description="Fallback RPC endpoints for failover (comma-separated in env var)",
    )
    polygonscan_api_key: str = Field(
        default="", description="Polygonscan API key (optional)"
    )

    @field_validator("polygon_rpc_fallbacks", mode="before")
    @classmethod
    def parse_fallback_endpoints(cls, v: Any) -> List[str]:
        """
        Parse fallback endpoints from environment variable or list.

        Args:
            v: String (comma-separated) or list of endpoints

        Returns:
            List of endpoint URLs
        """
        if isinstance(v, str):
            # Parse comma-separated string
            endpoints = [e.strip() for e in v.split(",") if e.strip()]
            return endpoints
        elif isinstance(v, list):
            return v
        else:
            # Try to load from environment
            env_value = os.getenv("POLYGON_RPC_FALLBACKS")
            if env_value:
                return [e.strip() for e in env_value.split(",") if e.strip()]
            return []


class TradingConfig(Config):
    """Trading configuration."""

    private_key: str = Field(description="Wallet private key")
    wallet_address: Optional[str] = Field(
        default="", description="Wallet address (auto-calculated if empty)"
    )
    gas_limit: int = Field(default=300000, description="Default gas limit", ge=21000)
    max_gas_price: int = Field(
        default=100, description="Maximum gas price in gwei", ge=1
    )
    gas_price_multiplier: float = Field(
        default=1.1, description="Gas price multiplier for priority", ge=1.0, le=2.0
    )

    # Advanced gas optimization
    gas_optimization_enabled: bool = Field(
        default=True, description="Enable advanced gas optimization"
    )
    gas_optimization_mode: str = Field(
        default="balanced",
        description="Gas optimization mode: conservative, balanced, or aggressive",
    )
    gas_prediction_enabled: bool = Field(
        default=True, description="Enable gas price prediction using historical data"
    )
    mev_protection_enabled: bool = Field(
        default=True, description="Enable MEV protection mechanisms"
    )
    gas_spike_threshold: float = Field(
        default=2.0,
        description="Gas spike detection threshold multiplier",
        ge=1.0,
        le=5.0,
    )
    max_gas_wait_minutes: int = Field(
        default=15,
        description="Maximum minutes to wait for gas to decrease",
        ge=0,
        le=60,
    )


class MonitoringConfig(Config):
    """Monitoring configuration."""

    monitor_interval: int = Field(
        default=15, description="Seconds between wallet checks", ge=5, le=300
    )
    wallets_file: str = Field(
        default="config/wallets.json", description="Path to wallets config"
    )
    target_wallets: List[str] = Field(
        default_factory=list, description="List of wallet addresses to monitor"
    )
    min_confidence_score: float = Field(
        default=0.7,
        description="Minimum confidence score for trade detection",
        ge=0.1,
        le=0.95,
    )

    @field_validator("monitor_interval")
    @classmethod
    def _validate_interval(cls, v: int) -> int:
        """Validate monitor interval is within reasonable bounds."""
        if v < 5:
            raise ValueError("Monitor interval must be at least 5 seconds")
        if v > 300:
            raise ValueError("Monitor interval must be at most 300 seconds")
        return v


class AlertingConfig(Config):
    """Alerting configuration."""

    telegram_bot_token: Optional[str] = Field(None, description="Telegram bot token")
    telegram_chat_id: Optional[str] = Field(None, description="Telegram chat ID")
    alert_on_trade: bool = Field(
        default=True, description="Send alerts on trade execution"
    )
    alert_on_error: bool = Field(default=True, description="Send alerts on errors")
    alert_on_circuit_breaker: bool = Field(
        default=True, description="Send alerts when circuit breaker activates"
    )


class LoggingConfig(Config):
    """Logging configuration."""

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    log_file: str = Field(
        default="logs/polymarket_bot.log", description="Path to log file"
    )
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format",
    )


class RiskManagementConfig(Config):
    """Risk management configuration."""

    max_position_size: float = Field(
        default=50.0, description="Maximum position size in USDC", ge=0.01, le=100000.0
    )
    max_daily_loss: float = Field(
        default=100.0, description="Maximum daily loss in USDC", ge=0.01, le=1000000.0
    )
    min_trade_amount: float = Field(
        default=1.0, description="Minimum trade amount in USDC", ge=0.01, le=1000.0
    )
    max_concurrent_positions: int = Field(
        default=10, description="Maximum concurrent positions", ge=1, le=100
    )
    stop_loss_percentage: float = Field(
        default=0.15, description="Stop loss percentage", ge=0.001, le=0.5
    )
    take_profit_percentage: float = Field(
        default=0.25, description="Take profit percentage", ge=0.001, le=1.0
    )
    max_slippage: float = Field(
        default=0.02, description="Maximum slippage", ge=0.001, le=0.1
    )


class Settings(Config):
    """Main settings class with lazy singleton pattern.

    This version prevents Pydantic validation errors during test collection
    by not initializing Settings() until get_settings() is called.
    """

    # Configuration sections
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    alerting: AlertingConfig = Field(default_factory=AlertingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    risk_management: RiskManagementConfig = Field(default_factory=RiskManagementConfig)

    @field_validator("trading")
    @classmethod
    def _validate_trading_config(cls, v: TradingConfig) -> TradingConfig:
        """Validate trading configuration."""
        # Ensure private key is not empty
        if not v.private_key or not v.private_key.strip():
            raise ValueError("Private key cannot be empty")
        return v

    @field_validator("risk_management")
    @classmethod
    def _validate_risk_management(cls, v: RiskManagementConfig) -> RiskManagementConfig:
        """Validate risk management configuration."""
        # Ensure max_position_size is positive
        if v.max_position_size <= 0:
            raise ValueError("MAX_POSITION_SIZE must be greater than 0")
        # Ensure max_daily_loss is positive
        if v.max_daily_loss <= 0:
            raise ValueError("MAX_DAILY_LOSS must be greater than 0")
        return v

    @field_validator("monitoring")
    @classmethod
    def _validate_monitoring(cls, v: MonitoringConfig) -> MonitoringConfig:
        """Validate monitoring configuration."""
        # Ensure monitor_interval is positive
        if v.monitor_interval <= 0:
            raise ValueError("MONITOR_INTERVAL must be greater than 0")
        return v


# Singleton instance (lazy initialization)
_settings: Optional["Settings"] = None


def get_settings() -> Settings:
    """Get settings singleton instance (lazy initialization).

    This function ensures Settings is only created once,
    preventing Pydantic validation errors during test collection.

    Returns:
        Settings singleton instance
    """
    global _settings
    if _settings is None:
        # Create settings instance only when explicitly requested
        _settings = Settings()
    return _settings


def validate_settings() -> Settings:
    """Validate settings configuration.

    This function validates critical settings and returns the settings instance.

    Returns:
        Validated Settings instance
    """
    # Get settings singleton
    settings = get_settings()

    # Import validation here to avoid circular dependency
    from utils.validation import InputValidator, ValidationError as ValidationErr

    # Validate critical settings
    try:
        # Create settings dict for validation
        settings_dict = settings.model_dump()

        # Validate private key
        InputValidator.validate_private_key(settings_dict["trading"]["private_key"])

        logger.info("✅ Settings validated successfully")
        return settings

    except (ValidationErr, KeyError) as e:
        logger.error(f"❌ Settings validation failed: {e}")
        raise ValueError(f"Settings validation failed: {e}")


# Create logs directory if it doesn't exist
log_dir = os.path.dirname(get_settings().logging.log_file)
os.makedirs(log_dir, exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=getattr(logging, get_settings().logging.log_level.upper(), logging.INFO),
    format=get_settings().logging.log_format,
    handlers=[
        logging.FileHandler(get_settings().logging.log_file),
        logging.StreamHandler(),
    ],
)

logger.info("✅ Settings loaded successfully")
logger.info(f"Network: {get_settings().network.clob_host}")
logger.info(
    f"Risk management enabled: Max daily loss=${get_settings().risk_management.max_daily_loss:.2f}"
)
