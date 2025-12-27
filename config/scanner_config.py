import os
from typing import Dict, List

from pydantic import BaseModel, Field

from .settings import Settings


class ScannerConfig(BaseModel):
    """Leaderboard scanner configuration with risk controls"""

    # Data sources
    POLYMARKET_API_KEY: str = Field(default=os.getenv("POLYMARKET_API_KEY", ""))
    POLYGONSCAN_API_KEY: str = Field(default=os.getenv("POLYGONSCAN_API_KEY", ""))
    POLYGON_RPC_URL: str = Field(
        default=os.getenv(
            "POLYGON_RPC_URL",
            "https://falling-solitary-research.matic.quiknode.pro/fa518d685fd0c4d00c5d3284da3bb7d63f046e14",
        )
    )
    USE_TESTNET: bool = Field(default=os.getenv("USE_TESTNET", "true").lower() == "true")

    # FIX: API endpoint configuration
    API_BASE_URL: str = Field(default="https://polymarket.com/api/v1")  # Updated base URL
    API_VERSION: str = Field(default="v1")  # Explicit API version

    # FIX: Add fallback endpoints
    FALLBACK_ENDPOINTS: List[str] = Field(default=[
        "/leaderboard",
        "/traders/leaderboard",
        "/market/leaderboard",
        "/api/leaderboard"  # Original for fallback
    ])

    # FIX: Health check configuration
    HEALTH_CHECK_ENDPOINT: str = Field(default="/health")

    # Scanner parameters
    MIN_WALLET_AGE_DAYS: int = Field(default=30, description="Minimum wallet age to consider")
    MIN_TRADE_COUNT: int = Field(default=50, description="Minimum trades to qualify")
    MIN_PROFIT_FACTOR: float = Field(
        default=1.2, description="Minimum profit factor (gross profits/gross losses)"
    )
    MAX_ACCEPTABLE_DRAWDOWN: float = Field(default=0.35, description="Maximum drawdown percentage")

    # Performance thresholds
    MIN_7D_ROI: float = Field(default=5.0, description="Minimum 7-day ROI percentage")
    MIN_30D_ROI: float = Field(default=15.0, description="Minimum 30-day ROI percentage")
    MIN_WIN_RATE: float = Field(default=0.60, description="Minimum win rate")

    # Risk filters
    EXCLUDE_MARKET_MAKERS: bool = Field(default=True, description="Filter out market maker wallets")
    MAX_CORRELATION_THRESHOLD: float = Field(
        default=0.7, description="Max correlation between copied wallets"
    )

    # Operational settings
    SCAN_INTERVAL_HOURS: int = Field(default=6, description="How often to rescan leaderboards")
    MAX_WALLETS_TO_MONITOR: int = Field(default=25, description="Maximum wallets to track")
    MIN_WALLETS_TO_MONITOR: int = Field(default=5, description="Minimum wallets needed for reliable operation")
    CONFIDENCE_SCORE_THRESHOLD: float = Field(
        default=0.8, description="Minimum confidence score to copy"
    )

    # Circuit breakers
    MAX_DAILY_SCANNER_ERRORS: int = Field(
        default=10, description="Stop scanner after this many errors"
    )
    MEMORY_LIMIT_MB: int = Field(default=512, description="Memory limit for scanner process")

    # API Failure Circuit Breakers
    MAX_API_FAILURES: int = Field(default=5, description="Max API failures before switching to fallback mode")
    FALLBACK_MODE_DURATION_HOURS: float = Field(default=2.0, description="How long to stay in fallback mode after API failures")

    @classmethod
    def from_env(cls) -> "ScannerConfig":
        """Load configuration from environment variables"""
        return cls()

    def validate_critical_settings(self):
        """Validate essential scanner settings"""
        if not self.POLYMARKET_API_KEY:
            raise ValueError("POLYMARKET_API_KEY is required for scanner operation")
        if not self.POLYGONSCAN_API_KEY:
            raise ValueError("POLYGONSCAN_API_KEY is required for blockchain verification")
        if self.MIN_WALLET_AGE_DAYS < 7:
            raise ValueError("Minimum wallet age must be at least 7 days for reliable data")


class WalletScore(BaseModel):
    """Comprehensive wallet scoring model"""

    address: str
    confidence_score: float = 0.0
    risk_score: float = 0.0
    performance_score: float = 0.0
    consistency_score: float = 0.0
    total_score: float = 0.0
    metrics: Dict[str, float] = {}
    last_updated: float = 0.0
    is_market_maker: bool = False
    exclusion_reasons: List[str] = []


# Add at the bottom of config/scanner_config.py
_scanner_config = None


def get_scanner_config() -> ScannerConfig:
    """Get scanner configuration singleton"""
    global _scanner_config
    if _scanner_config is None:
        _scanner_config = ScannerConfig.from_env()
    return _scanner_config


def validate_scanner_config():
    """Validate scanner configuration"""
    config = get_scanner_config()
    config.validate_critical_settings()
    return config
