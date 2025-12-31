"""Integration tests for multi-account functionality.

Tests the complete multi-wallet workflow including account management,
strategy allocation, and unified reporting.
"""

import json
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from config.account_manager import AccountManager, WalletProfile
from config.accounts_config import AccountsConfig, AccountsConfigLoader
from config.settings import RiskManagementConfig, Settings
from core.strategy_allocator import AllocationResult, StrategyAllocator
from monitoring.multi_account_dashboard import MultiAccountDashboard


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    risk_config = RiskManagementConfig(
        max_position_size=50.0,
        max_daily_loss=100.0,
        min_trade_amount=1.0,
    )

    trading_config = MagicMock()
    trading_config.private_key = "0x" + "0" * 64
    trading_config.wallet_address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"

    settings = MagicMock(spec=Settings)
    settings.risk = risk_config
    settings.trading = trading_config
    settings.monitoring = MagicMock()

    return settings


@pytest.fixture
def temp_state_file() -> Path:
    """Create temporary state file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def account_manager(mock_settings: Settings, temp_state_file: Path) -> AccountManager:
    """Create account manager for testing."""
    return AccountManager(settings=mock_settings, state_file=temp_state_file)


@pytest.fixture
def sample_wallet_profiles() -> list[WalletProfile]:
    """Create sample wallet profiles for testing."""
    return [
        WalletProfile(
            account_id="account_1",
            wallet_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            private_key="0x" + "0" * 64,
            enabled=True,
            allocation_percentage=50.0,
            min_balance_usdc=10.0,
            tags=["conservative"],
        ),
        WalletProfile(
            account_id="account_2",
            wallet_address="0x8b5a7da2fdf239b51b9c68a2a1a35bb156d200f2",
            private_key="0x" + "1" * 64,
            enabled=True,
            allocation_percentage=50.0,
            min_balance_usdc=10.0,
            tags=["aggressive"],
        ),
    ]


class TestAccountManager:
    """Test AccountManager functionality."""

    def test_initialization(self, account_manager: AccountManager) -> None:
        """Test account manager initialization."""
        assert account_manager is not None
        assert len(account_manager.wallet_profiles) >= 0

    def test_add_account(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test adding accounts."""
        profile = sample_wallet_profiles[0]
        account_manager.add_account(profile)

        assert profile.account_id in account_manager.wallet_profiles
        assert profile.account_id in account_manager.account_balances

    def test_get_enabled_accounts(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test getting enabled accounts."""
        for profile in sample_wallet_profiles:
            account_manager.add_account(profile)

        enabled = account_manager.get_enabled_accounts()
        assert len(enabled) == 2

        # Disable one account
        account_manager.wallet_profiles["account_1"].enabled = False
        enabled = account_manager.get_enabled_accounts()
        assert len(enabled) == 1

    @pytest.mark.asyncio
    async def test_update_balance(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test balance updates."""
        profile = sample_wallet_profiles[0]
        account_manager.add_account(profile)

        await account_manager.update_balance(profile.account_id, Decimal("100.0"))

        balance = await account_manager.get_balance(profile.account_id)
        assert balance == Decimal("100.0")

    @pytest.mark.asyncio
    async def test_get_total_balance(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test total balance calculation."""
        for profile in sample_wallet_profiles:
            account_manager.add_account(profile)
            await account_manager.update_balance(profile.account_id, Decimal("50.0"))

        total = account_manager.get_total_balance()
        assert total == Decimal("100.0")

    def test_get_account_risk_config(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test getting account risk config."""
        profile = sample_wallet_profiles[0]
        custom_risk = RiskManagementConfig(max_position_size=25.0, max_daily_loss=50.0)
        profile.risk_config = custom_risk
        account_manager.add_account(profile)

        risk_config = account_manager.get_account_risk_config(profile.account_id)
        assert risk_config.max_position_size == 25.0

    def test_validate_allocation_percentages(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test allocation percentage validation."""
        for profile in sample_wallet_profiles:
            account_manager.add_account(profile)

        assert account_manager.validate_allocation_percentages() is True

        # Test invalid allocation
        account_manager.wallet_profiles["account_1"].allocation_percentage = 30.0
        account_manager.wallet_profiles["account_2"].allocation_percentage = 30.0
        assert account_manager.validate_allocation_percentages() is False

    @pytest.mark.asyncio
    async def test_health_check(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test health check."""
        for profile in sample_wallet_profiles:
            account_manager.add_account(profile)
            await account_manager.update_balance(profile.account_id, Decimal("50.0"))

        health = await account_manager.health_check()
        assert health is True


class TestStrategyAllocator:
    """Test StrategyAllocator functionality."""

    @pytest.mark.asyncio
    async def test_allocate_trade(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test trade allocation."""
        for profile in sample_wallet_profiles:
            account_manager.add_account(profile)
            await account_manager.update_balance(profile.account_id, Decimal("100.0"))

        allocator = StrategyAllocator(account_manager)

        original_trade = {
            "tx_hash": "0x123",
            "amount": 100.0,
            "price": 0.5,
        }

        allocations = await allocator.allocate_trade(original_trade, Decimal("100.0"))

        assert len(allocations) == 2
        assert sum(a.allocation_amount for a in allocations) == Decimal("100.0")

    @pytest.mark.asyncio
    async def test_allocate_trade_with_insufficient_balance(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test allocation with insufficient balance."""
        for profile in sample_wallet_profiles:
            account_manager.add_account(profile)
            # Set low balance
            await account_manager.update_balance(profile.account_id, Decimal("10.0"))

        allocator = StrategyAllocator(account_manager)

        original_trade = {
            "tx_hash": "0x123",
            "amount": 100.0,
            "price": 0.5,
        }

        allocations = await allocator.allocate_trade(original_trade, Decimal("100.0"))

        # Should filter out accounts with insufficient balance
        assert len(allocations) == 0

    @pytest.mark.asyncio
    async def test_validate_allocation(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test allocation validation."""
        for profile in sample_wallet_profiles:
            account_manager.add_account(profile)
            await account_manager.update_balance(profile.account_id, Decimal("100.0"))

        allocator = StrategyAllocator(account_manager)

        allocations = [
            AllocationResult(
                account_id="account_1",
                wallet_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                allocation_amount=Decimal("50.0"),
                allocation_percentage=50.0,
                original_amount=Decimal("100.0"),
            ),
            AllocationResult(
                account_id="account_2",
                wallet_address="0x8b5a7da2fdf239b51b9c68a2a1a35bb156d200f2",
                allocation_amount=Decimal("50.0"),
                allocation_percentage=50.0,
                original_amount=Decimal("100.0"),
            ),
        ]

        is_valid, error = await allocator.validate_allocation(
            allocations, Decimal("100.0")
        )
        assert is_valid is True
        assert error is None


class TestMultiAccountDashboard:
    """Test MultiAccountDashboard functionality."""

    @pytest.mark.asyncio
    async def test_get_unified_report(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test unified report generation."""
        for profile in sample_wallet_profiles:
            account_manager.add_account(profile)
            await account_manager.update_balance(profile.account_id, Decimal("100.0"))

            # Set some trade stats
            balance = account_manager.account_balances[profile.account_id]
            balance.total_trades = 10
            balance.total_pnl = Decimal("50.0")
            balance.daily_pnl = Decimal("10.0")

        allocator = StrategyAllocator(account_manager)
        dashboard = MultiAccountDashboard(account_manager, allocator)

        report = await dashboard.get_unified_report()

        assert "summary" in report
        assert "accounts" in report
        assert report["summary"]["total_accounts"] == 2
        assert report["summary"]["total_balance_usdc"] == 200.0

    @pytest.mark.asyncio
    async def test_get_account_performance_report(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test account-specific performance report."""
        profile = sample_wallet_profiles[0]
        account_manager.add_account(profile)
        await account_manager.update_balance(profile.account_id, Decimal("100.0"))

        dashboard = MultiAccountDashboard(account_manager)

        report = await dashboard.get_account_performance_report(profile.account_id)

        assert report is not None
        assert report["account_id"] == profile.account_id
        assert report["balance_usdc"] == 100.0

    @pytest.mark.asyncio
    async def test_get_risk_alerts(
        self,
        account_manager: AccountManager,
        sample_wallet_profiles: list[WalletProfile],
    ) -> None:
        """Test risk alert generation."""
        profile = sample_wallet_profiles[0]
        profile.min_balance_usdc = 50.0
        account_manager.add_account(profile)
        await account_manager.update_balance(
            profile.account_id, Decimal("10.0")
        )  # Below minimum

        dashboard = MultiAccountDashboard(account_manager)

        alerts = await dashboard.get_risk_alerts()

        assert len(alerts) > 0
        assert any(alert["type"] == "low_balance" for alert in alerts)


class TestAccountsConfigLoader:
    """Test AccountsConfigLoader functionality."""

    def test_create_example_config(self) -> None:
        """Test example config creation."""
        example = AccountsConfigLoader.create_example_config()
        assert "accounts" in example
        assert len(example["accounts"]) == 2

    def test_load_from_file(self, temp_state_file: Path) -> None:
        """Test loading config from file."""
        config_data = AccountsConfigLoader.create_example_config()

        with open(temp_state_file, "w") as f:
            json.dump(config_data, f)

        config = AccountsConfigLoader.load_from_file(temp_state_file)
        assert len(config.accounts) == 2

    def test_convert_to_wallet_profiles(self) -> None:
        """Test conversion to wallet profiles."""
        config_data = AccountsConfigLoader.create_example_config()
        config = AccountsConfig(**config_data)

        default_risk = RiskManagementConfig()
        profiles = AccountsConfigLoader.convert_to_wallet_profiles(config, default_risk)

        assert len(profiles) == 2
        assert all(isinstance(p, WalletProfile) for p in profiles)


@pytest.mark.asyncio
async def test_end_to_end_workflow(
    account_manager: AccountManager, sample_wallet_profiles: list[WalletProfile]
) -> None:
    """Test complete end-to-end workflow."""
    # 1. Add accounts
    for profile in sample_wallet_profiles:
        account_manager.add_account(profile)
        await account_manager.update_balance(profile.account_id, Decimal("100.0"))

    # 2. Create allocator
    allocator = StrategyAllocator(account_manager)

    # 3. Allocate a trade
    original_trade = {
        "tx_hash": "0x123",
        "amount": 100.0,
        "price": 0.5,
    }
    allocations = await allocator.allocate_trade(original_trade, Decimal("100.0"))

    assert len(allocations) == 2

    # 4. Create dashboard
    dashboard = MultiAccountDashboard(account_manager, allocator)

    # 5. Get unified report
    report = await dashboard.get_unified_report()
    assert report["summary"]["total_accounts"] == 2

    # 6. Get risk alerts
    alerts = await dashboard.get_risk_alerts()
    assert isinstance(alerts, list)

    # 7. Format report
    formatted = await dashboard.format_report_for_display(report)
    assert "MULTI-ACCOUNT TRADING DASHBOARD" in formatted
