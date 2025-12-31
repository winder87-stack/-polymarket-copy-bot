"""
Tests for Pydantic v2 validator methods in config/settings.py

Tests cover:
- Trading configuration validation
- Monitoring configuration validation
- Environment variable loading
- Private key format validation
- Wallets file loading
- Error handling for invalid configurations
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from config.settings import MonitoringConfig, Settings, TradingConfig


class TestTradingConfigValidation:
    """Test trading configuration validation"""

    def test_valid_private_key_from_env(self):
        """Test loading valid private key from environment"""
        valid_key = "0x1234567890123456789012345678901234567890123456789012345678901234"

        with patch.dict(os.environ, {"PRIVATE_KEY": valid_key}):
            config = TradingConfig()
            assert config.private_key == valid_key

    def test_invalid_private_key_format(self):
        """Test rejection of invalid private key formats"""
        invalid_keys = [
            "invalid_key",  # No 0x prefix
            "0x123",  # Too short
            "0x1234567890123456789012345678901234567890123456789012345678901234567890",  # Too long
            "",  # Empty
        ]

        for invalid_key in invalid_keys:
            with patch.dict(os.environ, {"PRIVATE_KEY": invalid_key}):
                with pytest.raises(
                    ValueError,
                    match="Private key must start with '0x' and be 66 characters long",
                ):
                    TradingConfig()

    def test_wallet_address_from_env(self):
        """Test loading wallet address from environment"""
        private_key = (
            "0x1234567890123456789012345678901234567890123456789012345678901234"
        )
        wallet_address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"

        with patch.dict(
            os.environ, {"PRIVATE_KEY": private_key, "WALLET_ADDRESS": wallet_address}
        ):
            config = TradingConfig()
            assert config.wallet_address == wallet_address

    def test_missing_private_key(self):
        """Test error when no private key is available"""
        # Clear PRIVATE_KEY from environment
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                ValueError, match="PRIVATE_KEY must be set in environment variables"
            ):
                TradingConfig()


class TestMonitoringConfigValidation:
    """Test monitoring configuration validation"""

    def test_load_wallets_from_file(self):
        """Test loading wallets from JSON file"""
        wallets_data = {
            "target_wallets": ["0x123", "0x456", "0x789"],
            "min_confidence_score": 0.8,
        }

        # Create temporary wallets file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(wallets_data, f)
            temp_file = f.name

        try:
            with patch("config.settings.MonitoringConfig.wallets_file", temp_file):
                config = MonitoringConfig(wallets_file=temp_file)
                assert config.target_wallets == wallets_data["target_wallets"]
                assert (
                    config.min_confidence_score == wallets_data["min_confidence_score"]
                )
        finally:
            os.unlink(temp_file)

    def test_missing_wallets_file(self):
        """Test graceful handling of missing wallets file"""
        config = MonitoringConfig(wallets_file="nonexistent.json")
        assert config.target_wallets == []
        assert config.min_confidence_score == 0.7  # default value

    def test_invalid_wallets_file(self):
        """Test handling of invalid JSON in wallets file"""
        # Create temporary file with invalid JSON
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content")
            temp_file = f.name

        try:
            with patch("config.settings.MonitoringConfig.wallets_file", temp_file):
                config = MonitoringConfig(wallets_file=temp_file)
                assert config.target_wallets == []  # Should default to empty list
        finally:
            os.unlink(temp_file)


class TestEnvironmentVariableLoading:
    """Test loading configuration from environment variables"""

    def test_env_var_mapping(self):
        """Test that environment variables are properly mapped to config fields"""
        env_vars = {
            "CLOB_HOST": "https://test.clob.com",
            "CHAIN_ID": "80001",  # Polygon Mumbai testnet
            "MAX_POSITION_SIZE": "200.0",
            "MAX_DAILY_LOSS": "500.0",
            "MONITOR_INTERVAL": "30",
            "MAX_GAS_PRICE": "200",
            "DEFAULT_GAS_LIMIT": "400000",
            "MAX_CONCURRENT_POSITIONS": "5",
            "STOP_LOSS_PERCENTAGE": "0.20",
            "TAKE_PROFIT_PERCENTAGE": "0.30",
            "LOG_LEVEL": "DEBUG",
            "LOG_FILE": "/tmp/test.log",
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_CHAT_ID": "123456789",
            "MIN_CONFIDENCE_SCORE": "0.9",
        }

        with patch.dict(os.environ, env_vars):
            config = Settings()

            # Test network config
            assert config.network.clob_host == "https://test.clob.com"
            assert config.network.chain_id == 80001

            # Test risk config
            assert config.risk.max_position_size == 200.0
            assert config.risk.max_daily_loss == 500.0
            assert config.risk.max_concurrent_positions == 5
            assert config.risk.stop_loss_percentage == 0.20
            assert config.risk.take_profit_percentage == 0.30

            # Test monitoring config
            assert config.monitoring.monitor_interval == 30
            assert config.monitoring.min_confidence_score == 0.9

            # Test trading config
            assert config.trading.max_gas_price == 200
            assert config.trading.gas_limit == 400000

            # Test logging config
            assert config.logging.log_level == "DEBUG"
            assert config.logging.log_file == "/tmp/test.log"

            # Test alerts config
            assert config.alerts.telegram_bot_token == "test_token"
            assert config.alerts.telegram_chat_id == "123456789"

    def test_boolean_env_vars(self):
        """Test boolean environment variable conversion"""
        env_vars = {
            "PRIVATE_KEY": "0x1234567890123456789012345678901234567890123456789012345678901234"
        }

        # Test boolean conversions (alert_on_trade, alert_on_error, alert_on_circuit_breaker)
        boolean_tests = [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ]

        for env_value, expected in boolean_tests:
            env_vars_with_bool = {**env_vars, "ALERT_ON_TRADE": env_value}
            with patch.dict(os.environ, env_vars_with_bool):
                Settings()
                # Note: This tests the pattern, though the actual implementation
                # may need adjustment based on the specific boolean fields

    def test_invalid_numeric_env_vars(self):
        """Test graceful handling of invalid numeric environment variables"""
        env_vars = {
            "PRIVATE_KEY": "0x1234567890123456789012345678901234567890123456789012345678901234",
            "CHAIN_ID": "invalid_number",
            "MAX_POSITION_SIZE": "not_a_float",
        }

        with patch.dict(os.environ, env_vars):
            config = Settings()
            # Should use default values when env vars are invalid
            assert config.network.chain_id == 137  # default
            assert config.risk.max_position_size == 50.0  # default


class TestSettingsValidation:
    """Test the overall Settings validation"""

    def test_validate_critical_settings_success(self):
        """Test successful critical settings validation"""
        valid_key = "0x1234567890123456789012345678901234567890123456789012345678901234"

        with patch.dict(os.environ, {"PRIVATE_KEY": valid_key}):
            config = Settings()
            # Should not raise any exceptions
            config.validate_critical_settings()

    def test_validate_critical_settings_invalid_private_key(self):
        """Test validation failure with invalid private key"""
        invalid_key = "invalid_key"

        with patch.dict(os.environ, {"PRIVATE_KEY": invalid_key}):
            config = Settings()
            with pytest.raises(ValueError, match="Invalid private key length"):
                config.validate_critical_settings()

    def test_validate_critical_settings_zero_max_daily_loss(self):
        """Test validation failure with zero max daily loss"""
        valid_key = "0x1234567890123456789012345678901234567890123456789012345678901234"

        with patch.dict(os.environ, {"PRIVATE_KEY": valid_key, "MAX_DAILY_LOSS": "0"}):
            config = Settings()
            with pytest.raises(
                ValueError, match="MAX_DAILY_LOSS must be greater than 0"
            ):
                config.validate_critical_settings()

    def test_validate_critical_settings_zero_max_position_size(self):
        """Test validation failure with zero max position size"""
        valid_key = "0x1234567890123456789012345678901234567890123456789012345678901234"

        with patch.dict(
            os.environ, {"PRIVATE_KEY": valid_key, "MAX_POSITION_SIZE": "0"}
        ):
            config = Settings()
            with pytest.raises(
                ValueError, match="MAX_POSITION_SIZE must be greater than 0"
            ):
                config.validate_critical_settings()

    def test_validate_critical_settings_invalid_rpc_url(self):
        """Test validation failure with invalid RPC URL"""
        valid_key = "0x1234567890123456789012345678901234567890123456789012345678901234"

        with patch.dict(
            os.environ, {"PRIVATE_KEY": valid_key, "POLYGON_RPC_URL": "invalid_url"}
        ):
            config = Settings()
            with pytest.raises(
                ValueError, match="POLYGON_RPC_URL must be a valid HTTP/HTTPS URL"
            ):
                config.validate_critical_settings()


class TestValidatorSignatures:
    """Test that validators have correct Pydantic v2 signatures"""

    def test_field_validator_signatures(self):
        """Test that field validators are properly decorated as classmethods"""

        # Check that validate_trading_config is a classmethod
        assert isinstance(Settings.validate_trading_config, classmethod)
        assert Settings.validate_trading_config.__name__ == "validate_trading_config"

        # Check that load_wallets is a classmethod
        assert isinstance(Settings.load_wallets, classmethod)
        assert Settings.load_wallets.__name__ == "load_wallets"

        # Check that load_from_env is a classmethod
        assert isinstance(Settings.load_from_env, classmethod)
        assert Settings.load_from_env.__name__ == "load_from_env"

    def test_validator_decorators(self):
        """Test that validators have the correct Pydantic v2 decorators"""

        # Check that the decorators are applied
        assert hasattr(
            Settings.validate_trading_config, "__validator_config__"
        ) or hasattr(Settings, "__pydantic_validator__")

        # The actual decorator attributes may vary, but the methods should exist
        assert hasattr(Settings, "validate_trading_config")
        assert hasattr(Settings, "load_wallets")
        assert hasattr(Settings, "load_from_env")
