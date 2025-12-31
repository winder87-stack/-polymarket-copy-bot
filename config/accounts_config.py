"""Configuration Schema for Multi-Account Wallet Settings.

This module provides configuration schema and loading for wallet-specific settings,
enabling easy setup of multiple trading accounts with individual risk parameters.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from config.account_manager import WalletProfile
from config.settings import RiskManagementConfig

logger = logging.getLogger(__name__)


class AccountConfig(BaseModel):
    """Configuration for a single trading account."""

    account_id: str = Field(description="Unique identifier for this account")
    wallet_address: Optional[str] = Field(
        default=None,
        description="Wallet address (auto-derived from private_key if not provided)",
    )
    private_key: str = Field(description="Private key for signing transactions")
    enabled: bool = Field(default=True, description="Whether this account is active")
    allocation_percentage: float = Field(
        default=100.0,
        description="Percentage of trades allocated (0-100)",
        ge=0.0,
        le=100.0,
    )
    min_balance_usdc: float = Field(
        default=10.0, description="Minimum balance threshold", ge=0.0
    )
    max_balance_usdc: Optional[float] = Field(
        default=None, description="Maximum balance threshold (optional)", ge=0.0
    )
    tags: List[str] = Field(
        default_factory=list, description="Tags for categorizing accounts"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    # Risk management overrides (optional)
    risk_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Account-specific risk configuration overrides"
    )

    @field_validator("allocation_percentage")
    @classmethod
    def validate_allocation(cls, v: float) -> float:
        """Validate allocation percentage."""
        if v < 0 or v > 100:
            raise ValueError("Allocation percentage must be between 0 and 100")
        return v


class AccountsConfig(BaseModel):
    """Configuration for multiple trading accounts."""

    accounts: List[AccountConfig] = Field(
        default_factory=list, description="List of trading account configurations"
    )
    default_risk_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Default risk configuration for accounts without overrides",
    )

    @field_validator("accounts")
    @classmethod
    def validate_accounts(cls, v: List[AccountConfig]) -> List[AccountConfig]:
        """Validate account configurations."""
        # Check for duplicate account IDs
        account_ids = [acc.account_id for acc in v]
        if len(account_ids) != len(set(account_ids)):
            raise ValueError("Duplicate account IDs found")

        # Validate allocation percentages sum to 100% (within tolerance)
        enabled_accounts = [acc for acc in v if acc.enabled]
        if enabled_accounts:
            total_allocation = sum(
                acc.allocation_percentage for acc in enabled_accounts
            )
            if abs(total_allocation - 100.0) > 0.01 and len(enabled_accounts) > 1:
                logger.warning(
                    f"Allocation percentages sum to {total_allocation:.2f}%, expected 100%"
                )

        return v


class AccountsConfigLoader:
    """Loader for multi-account configuration files."""

    @staticmethod
    def load_from_file(config_path: Optional[Path] = None) -> AccountsConfig:
        """
        Load accounts configuration from JSON file.

        Args:
            config_path: Path to config file (defaults to config/accounts.json)

        Returns:
            AccountsConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if config_path is None:
            config_path = Path("config/accounts.json")

        if not config_path.exists():
            logger.info(
                f"Accounts config file not found: {config_path}. Using defaults."
            )
            return AccountsConfig()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both single account and multiple accounts format
            if "accounts" not in data:
                # Single account format (backward compatibility)
                if "account_id" in data or "private_key" in data:
                    data = {"accounts": [data]}
                else:
                    data = {"accounts": []}

            config = AccountsConfig(**data)
            logger.info(f"✅ Loaded {len(config.accounts)} accounts from {config_path}")

            return config

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ValueError(f"Error loading config file: {e}")

    @staticmethod
    def load_from_env() -> Optional[AccountsConfig]:
        """
        Load accounts configuration from environment variables.

        Environment variables:
        - ACCOUNTS_CONFIG_PATH: Path to accounts config file
        - ACCOUNTS_CONFIG_JSON: JSON string with accounts config

        Returns:
            AccountsConfig instance or None if not configured
        """
        # Try JSON string first
        config_json = os.getenv("ACCOUNTS_CONFIG_JSON")
        if config_json:
            try:
                data = json.loads(config_json)
                if "accounts" not in data:
                    data = {"accounts": [data]} if data else {"accounts": []}
                return AccountsConfig(**data)
            except Exception as e:
                logger.error(f"Error parsing ACCOUNTS_CONFIG_JSON: {e}")
                return None

        # Try file path
        config_path = os.getenv("ACCOUNTS_CONFIG_PATH")
        if config_path:
            return AccountsConfigLoader.load_from_file(Path(config_path))

        return None

    @staticmethod
    def convert_to_wallet_profiles(
        config: AccountsConfig,
        default_risk_config: Optional[RiskManagementConfig] = None,
    ) -> List[WalletProfile]:
        """
        Convert AccountsConfig to list of WalletProfile objects.

        Args:
            config: AccountsConfig instance
            default_risk_config: Default risk config to use if account doesn't specify

        Returns:
            List of WalletProfile objects
        """
        profiles = []

        for account_config in config.accounts:
            # Build risk config
            risk_config = None
            if account_config.risk_config:
                # Merge with default if provided
                if default_risk_config:
                    risk_dict = default_risk_config.model_dump()
                    risk_dict.update(account_config.risk_config)
                    risk_config = RiskManagementConfig(**risk_dict)
                else:
                    risk_config = RiskManagementConfig(**account_config.risk_config)
            elif default_risk_config:
                risk_config = default_risk_config

            # Derive wallet address if not provided
            wallet_address = account_config.wallet_address
            if not wallet_address:
                try:
                    from eth_account import Account

                    account = Account.from_key(account_config.private_key)
                    wallet_address = account.address.lower()
                except Exception as e:
                    logger.error(f"Error deriving wallet address: {e}")
                    wallet_address = account_config.account_id

            profile = WalletProfile(
                account_id=account_config.account_id,
                wallet_address=wallet_address,
                private_key=account_config.private_key,
                enabled=account_config.enabled,
                allocation_percentage=account_config.allocation_percentage,
                risk_config=risk_config,
                min_balance_usdc=account_config.min_balance_usdc,
                max_balance_usdc=account_config.max_balance_usdc,
                tags=account_config.tags,
                metadata=account_config.metadata,
            )

            profiles.append(profile)

        return profiles

    @staticmethod
    def create_example_config() -> Dict[str, Any]:
        """
        Create example configuration for documentation.

        Returns:
            Example configuration dictionary
        """
        return {
            "accounts": [
                {
                    "account_id": "account_1",
                    "private_key": "0x" + "0" * 64,  # Placeholder
                    "enabled": True,
                    "allocation_percentage": 50.0,
                    "min_balance_usdc": 10.0,
                    "tags": ["conservative"],
                    "risk_config": {
                        "max_position_size": 25.0,
                        "max_daily_loss": 50.0,
                        "min_trade_amount": 1.0,
                    },
                },
                {
                    "account_id": "account_2",
                    "private_key": "0x" + "1" * 64,  # Placeholder
                    "enabled": True,
                    "allocation_percentage": 50.0,
                    "min_balance_usdc": 10.0,
                    "tags": ["aggressive"],
                    "risk_config": {
                        "max_position_size": 50.0,
                        "max_daily_loss": 100.0,
                        "min_trade_amount": 2.0,
                    },
                },
            ],
            "default_risk_config": {
                "max_position_size": 50.0,
                "max_daily_loss": 100.0,
                "min_trade_amount": 1.0,
                "max_concurrent_positions": 10,
                "stop_loss_percentage": 0.15,
                "take_profit_percentage": 0.25,
                "max_slippage": 0.02,
            },
        }


def load_accounts_config(
    config_path: Optional[Path] = None, settings: Optional[Any] = None
) -> AccountsConfig:
    """
    Load accounts configuration with fallback to environment and defaults.

    Args:
        config_path: Optional path to config file
        settings: Optional settings instance for default risk config

    Returns:
        AccountsConfig instance
    """
    # Try environment first
    env_config = AccountsConfigLoader.load_from_env()
    if env_config:
        return env_config

    # Try file
    if config_path or Path("config/accounts.json").exists():
        return AccountsConfigLoader.load_from_file(config_path)

    # Return empty config (will use single account from settings)
    logger.info("No accounts config found. Using single account mode.")
    return AccountsConfig()
