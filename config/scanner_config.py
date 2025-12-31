import os
from typing import Dict, List

from pydantic import BaseModel, Field


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

    # Cross-Market Arbitrage Configuration
    ARBITRAGE_ENABLED: bool = Field(
        default=False, description="Enable cross-market arbitrage strategy"
    )
    ARBITRAGE_MAX_POSITION_PERCENT: float = Field(
        default=0.02,
        description="Maximum position size per arbitrage (2% of portfolio)",
    )
    ARBITRAGE_MIN_LIQUIDITY_USD: float = Field(
        default=25000,
        description="Minimum liquidity requirement per arb opportunity ($25K)",
    )
    ARBITRAGE_MIN_CORRELATION: float = Field(
        default=0.8, description="Minimum correlation threshold for market pairs (0.8)"
    )
    ARBITRAGE_MAX_DAILY_VOLATILITY: float = Field(
        default=0.5, description="Maximum daily volatility allowed (50%)"
    )
    ARBITRAGE_MAX_SLIPPAGE_PERCENT: float = Field(
        default=0.005, description="Maximum acceptable slippage (0.5%)"
    )
    ARBITRAGE_POLL_INTERVAL_SECONDS: int = Field(
        default=30, description="Order book polling interval (30 seconds)"
    )
    ARBITRAGE_MIN_EDGE_PERCENT: float = Field(
        default=1.0, description="Minimum profit margin to execute arb (1%)"
    )
    # 🔴 FIX: Add API endpoint configuration with fallbacks
    API_ENDPOINTS: List[str] = Field(
        default=[
            "https://polymarket.com/api/v1/leaderboard",  # Primary (updated)
            "https://polymarket.com/api/leaderboard",  # Fallback (original)
            "https://polymarket.com/v1/leaderboard",  # Alternative
            "https://polymarket.com/leaderboard",  # Last resort
        ]
    )
    USE_TESTNET: bool = Field(default=False)  # Set to False for production
    API_TIMEOUT: int = Field(default=30)  # seconds

    # Scanner parameters
    MIN_WALLET_AGE_DAYS: int = Field(
        default=30, description="Minimum wallet age to consider"
    )
    MIN_TRADE_COUNT: int = Field(default=50, description="Minimum trades to qualify")
    MIN_PROFIT_FACTOR: float = Field(
        default=1.2, description="Minimum profit factor (gross profits/gross losses)"
    )
    MAX_ACCEPTABLE_DRAWDOWN: float = Field(
        default=0.35, description="Maximum drawdown percentage"
    )

    # Performance thresholds
    MIN_7D_ROI: float = Field(default=5.0, description="Minimum 7-day ROI percentage")
    MIN_30D_ROI: float = Field(
        default=15.0, description="Minimum 30-day ROI percentage"
    )
    MIN_WIN_RATE: float = Field(default=0.60, description="Minimum win rate")

    # Risk filters
    EXCLUDE_MARKET_MAKERS: bool = Field(
        default=True, description="Filter out market maker wallets"
    )
    MAX_CORRELATION_THRESHOLD: float = Field(
        default=0.7, description="Max correlation between copied wallets"
    )

    # Operational settings
    SCAN_INTERVAL_HOURS: int = Field(
        default=6, description="How often to rescan leaderboards"
    )
    MAX_WALLETS_TO_MONITOR: int = Field(
        default=25, description="Maximum wallets to track"
    )
    MIN_WALLETS_TO_MONITOR: int = Field(
        default=5, description="Minimum wallets needed for reliable operation"
    )
    CONFIDENCE_SCORE_THRESHOLD: float = Field(
        default=0.8, description="Minimum confidence score to copy"
    )

    # Circuit breakers
    MAX_DAILY_SCANNER_ERRORS: int = Field(
        default=10, description="Stop scanner after this many errors"
    )
    MEMORY_LIMIT_MB: int = Field(
        default=512, description="Memory limit for scanner process"
    )

    # API Failure Circuit Breakers
    MAX_API_FAILURES: int = Field(
        default=5, description="Max API failures before switching to fallback mode"
    )
    FALLBACK_MODE_DURATION_HOURS: float = Field(
        default=2.0, description="How long to stay in fallback mode after API failures"
    )

    # Quality scoring thresholds
    MIN_QUALITY_SCORE_FOR_TRADING: float = Field(
        default=5.0, description="Minimum quality score for trading (5.0+)"
    )
    MAX_WALLETS_IN_PORTFOLIO: int = Field(
        default=5,
        description="Maximum wallets to track simultaneously (quality over quantity)",
    )
    MIN_TRADES_FOR_ROTATION: int = Field(
        default=10, description="Minimum trades before wallet rotation consideration"
    )
    SCORE_DECLINE_THRESHOLD: float = Field(
        default=1.0, description="Score decline to trigger rotation (1.0 points)"
    )
    WALLET_ROTATION_COOLDOWN_DAYS: int = Field(
        default=7, description="Days before reconsidering removed wallet"
    )

    # Per-wallet exposure limits
    ELITE_MAX_PORTFOLIO_PERCENT: float = Field(
        default=0.15, description="Elite wallets max portfolio % (15%)"
    )
    EXPERT_MAX_PORTFOLIO_PERCENT: float = Field(
        default=0.10, description="Expert wallets max portfolio % (10%)"
    )
    GOOD_MAX_PORTFOLIO_PERCENT: float = Field(
        default=0.07, description="Good wallets max portfolio % (7%)"
    )

    # Market maker detection thresholds
    MARKET_MAKER_TRADE_COUNT: int = Field(
        default=500, description="Trade count threshold for MM detection"
    )
    MARKET_MAKER_AVG_HOLD_TIME: int = Field(
        default=3600, description="Avg hold time threshold for MM (1 hour)"
    )
    MARKET_MAKER_PROFIT_PER_TRADE: float = Field(
        default=0.01, description="Min profit per trade for MM detection (1%)"
    )

    # Red flag thresholds
    NEW_WALLET_MAX_DAYS: int = Field(
        default=7, description="Max wallet age days for 'new' flag"
    )
    NEW_WALLET_MAX_BET: float = Field(
        default=1000.0, description="Max bet for new wallet before flag"
    )
    LUCK_NOT_SKILL_MIN_WIN_RATE: float = Field(
        default=0.90, description="Min win rate for 'luck not skill' flag (90%)"
    )
    LUCK_NOT_SKILL_MAX_TRADES: int = Field(
        default=20, description="Max trades for 'luck not skill' flag"
    )
    WASH_TRADING_SCORE_THRESHOLD: float = Field(
        default=0.70, description="Wash trading score threshold"
    )
    EXCESSIVE_DRAWDOWN_THRESHOLD: float = Field(
        default=0.35, description="Max drawdown before red flag (35%)"
    )

    # Position sizing
    BASE_POSITION_PERCENT: float = Field(
        default=0.02, description="Base position size (% of portfolio)"
    )
    MAX_POSITION_SIZE_USDC: float = Field(
        default=500.00, description="Maximum position size in USDC"
    )
    MIN_POSITION_SIZE_USDC: float = Field(
        default=1.00, description="Minimum position size in USDC"
    )

    # Behavior monitoring
    WIN_RATE_CHANGE_THRESHOLD: float = Field(
        default=0.15, description="Win rate change to trigger alert (15%)"
    )
    POSITION_SIZE_CHANGE_THRESHOLD: float = Field(
        default=2.0, description="Position size change to trigger alert (2x)"
    )
    VOLATILITY_CHANGE_THRESHOLD: float = Field(
        default=0.20, description="Volatility increase to trigger alert (20%)"
    )

    @classmethod
    def from_env(cls) -> "ScannerConfig":
        """Load configuration from environment variables"""
        return cls()

    def validate_critical_settings(self) -> None:
        """Validate essential scanner settings"""
        if not self.POLYMARKET_API_KEY:
            raise ValueError("POLYMARKET_API_KEY is required for scanner operation")
        if not self.POLYGONSCAN_API_KEY:
            raise ValueError(
                "POLYGONSCAN_API_KEY is required for blockchain verification"
            )
        if self.MIN_WALLET_AGE_DAYS < 7:
            raise ValueError(
                "Minimum wallet age must be at least 7 days for reliable data"
            )
        if self.MIN_QUALITY_SCORE_FOR_TRADING < 3.0:
            raise ValueError("Minimum quality score must be at least 3.0")
        if self.MAX_WALLETS_IN_PORTFOLIO < 3:
            raise ValueError("Minimum 3 wallets required for portfolio diversification")


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


def validate_scanner_config() -> ScannerConfig:
    """Validate scanner configuration"""
    config = get_scanner_config()
    config.validate_critical_settings()
    return config
