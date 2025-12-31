"""Account Manager for Multi-Wallet Support.

This module provides account management functionality for supporting multiple trading wallets
with isolated risk management, balance tracking, and strategy allocation.

The AccountManager maintains backward compatibility with single-account configurations
while enabling multi-wallet operations for risk distribution.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from config.settings import RiskManagementConfig, Settings
from utils.helpers import BoundedCache, normalize_address
from utils.logging_security import SecureLogger
from utils.validation import InputValidator, ValidationError

logger = logging.getLogger(__name__)


class WalletProfile(BaseModel):
    """Profile for a single trading wallet with isolated risk management."""

    account_id: str = Field(description="Unique identifier for this account")
    wallet_address: str = Field(description="Wallet address (checksummed)")
    private_key: str = Field(description="Private key for signing transactions")
    enabled: bool = Field(default=True, description="Whether this account is active")
    allocation_percentage: float = Field(
        default=100.0,
        description="Percentage of trades allocated to this account (0-100)",
        ge=0.0,
        le=100.0,
    )
    risk_config: Optional[RiskManagementConfig] = Field(
        default=None,
        description="Account-specific risk configuration (overrides global)",
    )
    min_balance_usdc: float = Field(
        default=10.0,
        description="Minimum balance threshold before disabling account",
        ge=0.0,
    )
    max_balance_usdc: Optional[float] = Field(
        default=None, description="Maximum balance threshold (optional)", ge=0.0
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorizing accounts (e.g., 'conservative', 'aggressive')",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for this account"
    )

    @field_validator("wallet_address")
    @classmethod
    def validate_wallet_address(cls, v: str) -> str:
        """Validate and normalize wallet address."""
        try:
            return InputValidator.validate_wallet_address(v)
        except ValidationError as e:
            raise ValueError(f"Invalid wallet address: {e}")

    @field_validator("private_key")
    @classmethod
    def validate_private_key(cls, v: str) -> str:
        """Validate private key format."""
        try:
            return InputValidator.validate_private_key(v)
        except ValidationError as e:
            raise ValueError(f"Invalid private key: {e}")

    @model_validator(mode="after")
    def validate_allocation(self) -> "WalletProfile":
        """Validate allocation percentage is reasonable."""
        if self.allocation_percentage < 0 or self.allocation_percentage > 100:
            raise ValueError("Allocation percentage must be between 0 and 100")
        return self


class AccountBalance(BaseModel):
    """Balance tracking for an account."""

    account_id: str
    wallet_address: str
    balance_usdc: Decimal = Field(
        default=Decimal("0.0"), description="Current USDC balance"
    )
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    balance_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="Historical balance snapshots"
    )
    total_trades: int = Field(default=0, description="Total trades executed")
    total_pnl: Decimal = Field(default=Decimal("0.0"), description="Total P&L")
    daily_pnl: Decimal = Field(default=Decimal("0.0"), description="Daily P&L")


class AccountManager:
    """
    Manages multiple trading accounts with isolated risk management.

    This class provides:
    - Wallet profile management
    - Balance tracking per account
    - Strategy allocation across accounts
    - Isolated risk management per account
    - Unified reporting

    Thread Safety:
        Uses asyncio locks for concurrent operations
    """

    def __init__(self, settings: Settings, state_file: Optional[Path] = None) -> None:
        """
        Initialize the account manager.

        Args:
            settings: Application settings (for backward compatibility)
            state_file: Optional path to persist account state
        """
        self.settings = settings
        self.state_file = state_file or Path("data/account_manager_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Thread safety
        self._state_lock: asyncio.Lock = asyncio.Lock()

        # Account storage
        self.wallet_profiles: Dict[str, WalletProfile] = {}
        self.account_balances: Dict[str, AccountBalance] = {}

        # Balance cache with TTL
        self.balance_cache: BoundedCache = BoundedCache(
            max_size=1000,
            ttl_seconds=60,  # Cache balances for 1 minute
            memory_threshold_mb=10.0,
            cleanup_interval_seconds=30,
        )

        # Performance tracking
        self.last_balance_update: Dict[str, float] = {}
        self.balance_update_interval: float = 30.0  # Update balances every 30 seconds

        # Load existing state
        self._load_state()

        # Initialize from settings if no accounts exist (backward compatibility)
        if not self.wallet_profiles:
            self._initialize_from_settings()

        SecureLogger.log(
            "info",
            "Initialized account manager",
            {
                "account_count": len(self.wallet_profiles),
                "enabled_accounts": sum(
                    1 for p in self.wallet_profiles.values() if p.enabled
                ),
            },
        )

    def _initialize_from_settings(self) -> None:
        """Initialize single account from settings for backward compatibility."""
        try:
            private_key = self.settings.trading.private_key
            wallet_address = self.settings.trading.wallet_address

            if not private_key:
                logger.warning(
                    "No private key configured. Account manager initialized with no accounts."
                )
                return

            # Generate account ID from wallet address
            account_id = normalize_address(
                wallet_address or self._derive_address_from_key(private_key)
            )

            profile = WalletProfile(
                account_id=account_id,
                wallet_address=account_id,
                private_key=private_key,
                enabled=True,
                allocation_percentage=100.0,
                risk_config=None,  # Use global risk config
                tags=["default"],
            )

            self.wallet_profiles[account_id] = profile

            # Initialize balance
            balance = AccountBalance(
                account_id=account_id,
                wallet_address=account_id,
                balance_usdc=Decimal("0.0"),
            )
            self.account_balances[account_id] = balance

            logger.info(
                f"✅ Initialized single account from settings: {account_id[:10]}..."
            )

        except Exception as e:
            logger.error(f"Error initializing from settings: {e}", exc_info=True)

    def _derive_address_from_key(self, private_key: str) -> str:
        """Derive wallet address from private key."""
        try:
            from eth_account import Account

            account = Account.from_key(private_key)
            return normalize_address(account.address)
        except Exception as e:
            logger.error(f"Error deriving address from key: {e}")
            return "0x" + "0" * 40

    def _load_state(self) -> None:
        """Load account state from file."""
        if not self.state_file.exists():
            logger.debug(f"State file not found: {self.state_file}. Starting fresh.")
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Load wallet profiles
            if "wallet_profiles" in data:
                for profile_data in data["wallet_profiles"]:
                    try:
                        profile = WalletProfile(**profile_data)
                        self.wallet_profiles[profile.account_id] = profile
                    except Exception as e:
                        logger.error(
                            f"Error loading wallet profile: {e}", exc_info=True
                        )

            # Load account balances
            if "account_balances" in data:
                for balance_data in data["account_balances"]:
                    try:
                        balance = AccountBalance(**balance_data)
                        # Convert string balances to Decimal
                        if isinstance(balance.balance_usdc, str):
                            balance.balance_usdc = Decimal(balance.balance_usdc)
                        if isinstance(balance.total_pnl, str):
                            balance.total_pnl = Decimal(balance.total_pnl)
                        if isinstance(balance.daily_pnl, str):
                            balance.daily_pnl = Decimal(balance.daily_pnl)
                        self.account_balances[balance.account_id] = balance
                    except Exception as e:
                        logger.error(
                            f"Error loading account balance: {e}", exc_info=True
                        )

            logger.info(
                f"✅ Loaded {len(self.wallet_profiles)} accounts from state file"
            )

        except Exception as e:
            logger.error(f"Error loading state: {e}", exc_info=True)

    async def _save_state(self) -> None:
        """Save account state to file."""
        async with self._state_lock:
            try:
                data = {
                    "wallet_profiles": [
                        profile.model_dump()
                        for profile in self.wallet_profiles.values()
                    ],
                    "account_balances": [
                        {
                            **balance.model_dump(),
                            "balance_usdc": str(balance.balance_usdc),
                            "total_pnl": str(balance.total_pnl),
                            "daily_pnl": str(balance.daily_pnl),
                        }
                        for balance in self.account_balances.values()
                    ],
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }

                # Write atomically
                temp_file = self.state_file.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)

                temp_file.replace(self.state_file)

            except Exception as e:
                logger.error(f"Error saving state: {e}", exc_info=True)

    def add_account(self, profile: WalletProfile) -> None:
        """
        Add a new trading account.

        Args:
            profile: Wallet profile to add

        Raises:
            ValueError: If account ID already exists
        """
        if profile.account_id in self.wallet_profiles:
            raise ValueError(f"Account {profile.account_id} already exists")

        self.wallet_profiles[profile.account_id] = profile

        # Initialize balance
        balance = AccountBalance(
            account_id=profile.account_id,
            wallet_address=profile.wallet_address,
            balance_usdc=Decimal("0.0"),
        )
        self.account_balances[profile.account_id] = balance

        logger.info(
            f"✅ Added account: {profile.account_id[:10]}... (allocation: {profile.allocation_percentage}%)"
        )

        # Save state asynchronously
        asyncio.create_task(self._save_state())

    def remove_account(self, account_id: str) -> None:
        """
        Remove an account (marks as disabled, doesn't delete).

        Args:
            account_id: Account ID to remove
        """
        if account_id not in self.wallet_profiles:
            raise ValueError(f"Account {account_id} not found")

        self.wallet_profiles[account_id].enabled = False
        logger.info(f"✅ Disabled account: {account_id[:10]}...")

        asyncio.create_task(self._save_state())

    def get_account(self, account_id: str) -> Optional[WalletProfile]:
        """Get wallet profile for an account."""
        return self.wallet_profiles.get(account_id)

    def get_enabled_accounts(self) -> List[WalletProfile]:
        """Get all enabled accounts."""
        return [profile for profile in self.wallet_profiles.values() if profile.enabled]

    def get_accounts_by_allocation(self) -> List[WalletProfile]:
        """Get enabled accounts sorted by allocation percentage (descending)."""
        enabled = self.get_enabled_accounts()
        return sorted(enabled, key=lambda p: p.allocation_percentage, reverse=True)

    async def update_balance(
        self, account_id: str, balance_usdc: Decimal, source: str = "api"
    ) -> None:
        """
        Update balance for an account.

        Args:
            account_id: Account ID
            balance_usdc: New balance in USDC
            source: Source of balance update (e.g., 'api', 'trade')
        """
        if account_id not in self.account_balances:
            logger.warning(
                f"Account {account_id} not found in balances. Creating entry."
            )
            self.account_balances[account_id] = AccountBalance(
                account_id=account_id,
                wallet_address=self.wallet_profiles.get(
                    account_id,
                    WalletProfile(
                        account_id=account_id,
                        wallet_address=account_id,
                        private_key="",
                    ),
                ).wallet_address,
            )

        async with self._state_lock:
            balance = self.account_balances[account_id]
            old_balance = balance.balance_usdc
            balance.balance_usdc = balance_usdc
            balance.last_updated = datetime.now(timezone.utc)

            # Track balance history (keep last 100 entries)
            balance.balance_history.append(
                {
                    "balance": str(balance_usdc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": source,
                }
            )
            if len(balance.balance_history) > 100:
                balance.balance_history = balance.balance_history[-100:]

            # Cache balance
            self.balance_cache.set(f"balance_{account_id}", balance_usdc)

            # Log significant balance changes
            if abs(balance_usdc - old_balance) > Decimal("10.0"):
                logger.info(
                    f"💰 Balance update for {account_id[:10]}...: ${old_balance:.2f} -> ${balance_usdc:.2f} ({source})"
                )

    async def get_balance(
        self, account_id: str, use_cache: bool = True
    ) -> Optional[Decimal]:
        """
        Get current balance for an account.

        Args:
            account_id: Account ID
            use_cache: Whether to use cached balance if available

        Returns:
            Current balance or None if account not found
        """
        if account_id not in self.account_balances:
            return None

        # Check cache first
        if use_cache:
            cached_balance = self.balance_cache.get(f"balance_{account_id}")
            if cached_balance is not None:
                return Decimal(str(cached_balance))

        # Return stored balance
        balance = self.account_balances[account_id]
        return balance.balance_usdc

    def get_total_balance(self) -> Decimal:
        """Get total balance across all enabled accounts."""
        total = Decimal("0.0")
        for account_id, profile in self.wallet_profiles.items():
            if profile.enabled:
                balance = self.account_balances.get(account_id)
                if balance:
                    total += balance.balance_usdc
        return total

    def get_account_risk_config(self, account_id: str) -> RiskManagementConfig:
        """
        Get risk configuration for an account (account-specific or global fallback).

        Args:
            account_id: Account ID

        Returns:
            Risk management configuration
        """
        profile = self.wallet_profiles.get(account_id)
        if profile and profile.risk_config:
            return profile.risk_config
        return self.settings.risk

    def validate_allocation_percentages(self) -> bool:
        """
        Validate that allocation percentages sum to 100% (within tolerance).

        Returns:
            True if allocations are valid
        """
        enabled_accounts = self.get_enabled_accounts()
        if not enabled_accounts:
            return True  # No accounts, nothing to validate

        total_allocation = sum(
            account.allocation_percentage for account in enabled_accounts
        )
        tolerance = 0.01  # Allow 0.01% tolerance for floating point

        if abs(total_allocation - 100.0) > tolerance:
            logger.warning(
                f"⚠️ Allocation percentages sum to {total_allocation:.2f}%, expected 100%"
            )
            return False

        return True

    def get_unified_metrics(self) -> Dict[str, Any]:
        """
        Get unified metrics across all accounts.

        Returns:
            Dictionary with aggregated metrics
        """
        enabled_accounts = self.get_enabled_accounts()
        total_balance = self.get_total_balance()

        account_metrics = []
        for account_id, profile in self.wallet_profiles.items():
            if not profile.enabled:
                continue

            balance = self.account_balances.get(account_id)
            if not balance:
                continue

            account_metrics.append(
                {
                    "account_id": account_id,
                    "wallet_address": profile.wallet_address,
                    "allocation_percentage": profile.allocation_percentage,
                    "balance_usdc": float(balance.balance_usdc),
                    "total_trades": balance.total_trades,
                    "total_pnl": float(balance.total_pnl),
                    "daily_pnl": float(balance.daily_pnl),
                    "tags": profile.tags,
                    "enabled": profile.enabled,
                }
            )

        return {
            "total_accounts": len(enabled_accounts),
            "total_balance_usdc": float(total_balance),
            "accounts": account_metrics,
            "allocation_valid": self.validate_allocation_percentages(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def health_check(self) -> bool:
        """Perform health check on account manager."""
        try:
            # Check that we have at least one enabled account
            enabled_accounts = self.get_enabled_accounts()
            if not enabled_accounts:
                logger.warning("⚠️ No enabled accounts configured")
                return False

            # Validate allocations
            if not self.validate_allocation_percentages():
                logger.warning("⚠️ Invalid allocation percentages")
                # Don't fail health check, just warn

            # Check for accounts below minimum balance
            low_balance_accounts = []
            for account_id, profile in self.wallet_profiles.items():
                if not profile.enabled:
                    continue
                balance = self.account_balances.get(account_id)
                if balance and balance.balance_usdc < Decimal(
                    str(profile.min_balance_usdc)
                ):
                    low_balance_accounts.append(account_id)

            if low_balance_accounts:
                logger.warning(
                    f"⚠️ {len(low_balance_accounts)} accounts below minimum balance threshold"
                )

            return True

        except Exception as e:
            logger.error(f"Error in account manager health check: {e}", exc_info=True)
            return False
