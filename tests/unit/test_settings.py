"""
Unit tests for config/settings.py - Configuration validation and loading.
"""
import pytest
import os
import json
import tempfile
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime
from pathlib import Path

from config.settings import (
    Settings,
    RiskManagementConfig,
    NetworkConfig,
    TradingConfig,
    MonitoringConfig,
    AlertingConfig,
    LoggingConfig,
    settings
)


class TestRiskManagementConfig:
    """Test RiskManagementConfig validation."""

    def test_valid_risk_config(self):
        """Test valid risk management configuration."""
        config = RiskManagementConfig(
            max_position_size=50.0,
            max_daily_loss=100.0,
            min_trade_amount=1.0,
            max_concurrent_positions=10,
            stop_loss_percentage=0.15,
            take_profit_percentage=0.25,
            max_slippage=0.02
        )
        assert config.max_position_size == 50.0
        assert config.max_daily_loss == 100.0
        assert config.min_trade_amount == 1.0

    @pytest.mark.parametrize("invalid_value", [-10.0, 0.0])
    def test_invalid_max_position_size(self, invalid_value):
        """Test invalid max position size values."""
        with pytest.raises(ValueError):
            RiskManagementConfig(max_position_size=invalid_value)

    @pytest.mark.parametrize("invalid_value", [-10.0])
    def test_invalid_max_daily_loss(self, invalid_value):
        """Test invalid max daily loss values."""
        with pytest.raises(ValueError):
            RiskManagementConfig(max_daily_loss=invalid_value)

    def test_invalid_min_trade_amount(self):
        """Test invalid minimum trade amount."""
        with pytest.raises(ValueError):
            RiskManagementConfig(min_trade_amount=0.005)  # Below minimum

    def test_invalid_stop_loss_percentage(self):
        """Test invalid stop loss percentage."""
        with pytest.raises(ValueError):
            RiskManagementConfig(stop_loss_percentage=0.005)  # Below minimum

        with pytest.raises(ValueError):
            RiskManagementConfig(stop_loss_percentage=0.6)  # Above maximum

    def test_invalid_take_profit_percentage(self):
        """Test invalid take profit percentage."""
        with pytest.raises(ValueError):
            RiskManagementConfig(take_profit_percentage=0.005)  # Below minimum

        with pytest.raises(ValueError):
            RiskManagementConfig(take_profit_percentage=1.5)  # Above maximum

    def test_invalid_max_slippage(self):
        """Test invalid max slippage."""
        with pytest.raises(ValueError):
            RiskManagementConfig(max_slippage=0.0005)  # Below minimum

        with pytest.raises(ValueError):
            RiskManagementConfig(max_slippage=0.15)  # Above maximum


class TestNetworkConfig:
    """Test NetworkConfig validation."""

    def test_valid_network_config(self):
        """Test valid network configuration."""
        config = NetworkConfig(
            clob_host="https://clob.polymarket.com",
            chain_id=137,
            polygon_rpc_url="https://polygon-rpc.com",
            polygonscan_api_key="test-key"
        )
        assert config.clob_host == "https://clob.polymarket.com"
        assert config.chain_id == 137

    def test_invalid_chain_id(self):
        """Test invalid chain ID."""
        with pytest.raises(ValueError):
            NetworkConfig(chain_id=-1)


class TestTradingConfig:
    """Test TradingConfig validation."""

    def test_valid_trading_config(self):
        """Test valid trading configuration."""
        config = TradingConfig(
            private_key="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            wallet_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            gas_limit=300000,
            max_gas_price=100,
            gas_price_multiplier=1.1
        )
        assert config.private_key.startswith("0x")
        assert config.gas_limit == 300000

    def test_invalid_private_key_length(self):
        """Test invalid private key length."""
        with pytest.raises(ValueError):
            TradingConfig(private_key="0x1234567890abcdef")  # Too short

    def test_private_key_without_prefix(self):
        """Test private key without 0x prefix."""
        with pytest.raises(ValueError):
            TradingConfig(private_key="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef")

    def test_invalid_gas_limit(self):
        """Test invalid gas limit."""
        with pytest.raises(ValueError):
            TradingConfig(
                private_key="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                gas_limit=10000  # Below minimum
            )

    def test_invalid_gas_price_multiplier(self):
        """Test invalid gas price multiplier."""
        with pytest.raises(ValueError):
            TradingConfig(
                private_key="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                gas_price_multiplier=0.5  # Below minimum
            )

        with pytest.raises(ValueError):
            TradingConfig(
                private_key="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                gas_price_multiplier=2.5  # Above maximum
            )


class TestMonitoringConfig:
    """Test MonitoringConfig validation."""

    def test_valid_monitoring_config(self):
        """Test valid monitoring configuration."""
        config = MonitoringConfig(
            monitor_interval=15,
            wallets_file="config/wallets.json",
            target_wallets=["0x742d35Cc6634C0532925a3b844Bc454e4438f44e"],
            min_confidence_score=0.7
        )
        assert config.monitor_interval == 15
        assert config.min_confidence_score == 0.7

    def test_invalid_monitor_interval(self):
        """Test invalid monitor interval."""
        with pytest.raises(ValueError):
            MonitoringConfig(monitor_interval=3)  # Below minimum

        with pytest.raises(ValueError):
            MonitoringConfig(monitor_interval=350)  # Above maximum

    def test_invalid_confidence_score(self):
        """Test invalid confidence score."""
        with pytest.raises(ValueError):
            MonitoringConfig(min_confidence_score=0.05)  # Below minimum

        with pytest.raises(ValueError):
            MonitoringConfig(min_confidence_score=0.98)  # Above maximum


class TestAlertingConfig:
    """Test AlertingConfig validation."""

    def test_valid_alerting_config(self):
        """Test valid alerting configuration."""
        config = AlertingConfig(
            telegram_bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            telegram_chat_id="123456789",
            alert_on_trade=True,
            alert_on_error=True,
            alert_on_circuit_breaker=True
        )
        assert config.telegram_bot_token is not None
        assert config.alert_on_trade is True


class TestLoggingConfig:
    """Test LoggingConfig validation."""

    def test_valid_logging_config(self):
        """Test valid logging configuration."""
        config = LoggingConfig(
            log_level="INFO",
            log_file="logs/polymarket_bot.log",
            log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        assert config.log_level == "INFO"
        assert config.log_file.endswith(".log")


class TestSettings:
    """Test Settings class functionality."""

    def test_settings_initialization(self, test_settings):
        """Test settings initialization."""
        assert isinstance(test_settings.risk, RiskManagementConfig)
        assert isinstance(test_settings.network, NetworkConfig)
        assert isinstance(test_settings.trading, TradingConfig)
        assert isinstance(test_settings.monitoring, MonitoringConfig)
        assert isinstance(test_settings.alerts, AlertingConfig)
        assert isinstance(test_settings.logging, LoggingConfig)

    def test_env_variable_loading(self, mock_env_vars):
        """Test loading configuration from environment variables."""
        settings_instance = Settings()

        # Test that environment variables are loaded
        assert settings_instance.risk.max_daily_loss == 100.0
        assert settings_instance.risk.max_position_size == 50.0
        assert settings_instance.monitoring.monitor_interval == 15
        assert settings_instance.trading.private_key == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    def test_env_variable_type_conversion(self, mock_env_vars):
        """Test type conversion for environment variables."""
        settings_instance = Settings()

        # Test integer conversion
        assert isinstance(settings_instance.monitoring.monitor_interval, int)
        assert settings_instance.monitoring.monitor_interval == 15

        # Test float conversion
        assert isinstance(settings_instance.risk.max_daily_loss, float)
        assert settings_instance.risk.max_daily_loss == 100.0

        # Test boolean conversion
        assert isinstance(settings_instance.alerts.alert_on_trade, bool)

    def test_wallet_loading_from_file(self, temp_config_file, mock_env_vars):
        """Test loading wallets from configuration file."""
        with patch('config.settings.os.path.exists', return_value=True):
            with patch('config.settings.open') as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                    'target_wallets': [
                        "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                        "0x742d35Cc6634C0532925a3b844Bc454e4438f44f"
                    ],
                    'min_confidence_score': 0.8
                })

                settings_instance = Settings()
                assert len(settings_instance.monitoring.target_wallets) == 2
                assert settings_instance.monitoring.min_confidence_score == 0.8

    def test_wallet_loading_file_not_found(self, mock_env_vars):
        """Test behavior when wallets file is not found."""
        with patch('config.settings.os.path.exists', return_value=False):
            settings_instance = Settings()
            assert settings_instance.monitoring.target_wallets == []

    def test_wallet_loading_invalid_json(self, mock_env_vars):
        """Test behavior when wallets file contains invalid JSON."""
        with patch('config.settings.os.path.exists', return_value=True):
            with patch('config.settings.open') as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "invalid json"

                settings_instance = Settings()
                assert settings_instance.monitoring.target_wallets == []

    @patch('config.settings.Web3')
    def test_validate_critical_settings_valid(self, mock_web3_class, mock_env_vars):
        """Test critical settings validation with valid settings."""
        mock_web3_instance = Mock()
        mock_web3_instance.is_connected.return_value = True
        mock_web3_class.return_value = mock_web3_instance

        settings_instance = Settings()
        # Should not raise an exception
        settings_instance.validate_critical_settings()

    @patch('config.settings.Web3')
    def test_validate_critical_settings_invalid_private_key(self, mock_web3_class):
        """Test critical settings validation with invalid private key."""
        settings_instance = Settings()
        settings_instance.trading.private_key = "invalid-key"

        with pytest.raises(ValueError, match="Private key must start with '0x'"):
            settings_instance.validate_critical_settings()

    @patch('config.settings.Web3')
    def test_validate_critical_settings_short_private_key(self, mock_web3_class):
        """Test critical settings validation with too short private key."""
        settings_instance = Settings()
        settings_instance.trading.private_key = "0x1234567890abcdef"

        with pytest.raises(ValueError, match="Invalid private key length"):
            settings_instance.validate_critical_settings()

    @patch('config.settings.Web3')
    def test_validate_critical_settings_zero_daily_loss(self, mock_web3_class):
        """Test critical settings validation with zero daily loss."""
        settings_instance = Settings()
        settings_instance.risk.max_daily_loss = 0

        with pytest.raises(ValueError, match="MAX_DAILY_LOSS must be greater than 0"):
            settings_instance.validate_critical_settings()

    @patch('config.settings.Web3')
    def test_validate_critical_settings_zero_position_size(self, mock_web3_class):
        """Test critical settings validation with zero position size."""
        settings_instance = Settings()
        settings_instance.risk.max_position_size = 0

        with pytest.raises(ValueError, match="MAX_POSITION_SIZE must be greater than 0"):
            settings_instance.validate_critical_settings()

    @patch('config.settings.Web3')
    def test_validate_critical_settings_invalid_rpc_url(self, mock_web3_class):
        """Test critical settings validation with invalid RPC URL."""
        settings_instance = Settings()
        settings_instance.network.polygon_rpc_url = "invalid-url"

        with pytest.raises(ValueError, match="POLYGON_RPC_URL must be a valid HTTP/HTTPS URL"):
            settings_instance.validate_critical_settings()

    @patch('config.settings.Web3')
    def test_validate_critical_settings_web3_connection_failure(self, mock_web3_class):
        """Test critical settings validation when Web3 connection fails."""
        mock_web3_instance = Mock()
        mock_web3_instance.is_connected.return_value = False
        mock_web3_class.return_value = mock_web3_instance

        settings_instance = Settings()

        # Should not raise an exception but should log a warning
        settings_instance.validate_critical_settings()

    def test_env_mappings_completeness(self, test_settings):
        """Test that all settings have environment variable mappings."""
        expected_mappings = {
            'network.clob_host': 'CLOB_HOST',
            'network.polygon_rpc_url': 'POLYGON_RPC_URL',
            'network.polygonscan_api_key': 'POLYGONSCAN_API_KEY',
            'risk.max_slippage': 'MAX_SLIPPAGE',
            'risk.max_position_size': 'MAX_POSITION_SIZE',
            'risk.max_daily_loss': 'MAX_DAILY_LOSS',
            'risk.min_trade_amount': 'MIN_TRADE_AMOUNT',
            'monitoring.monitor_interval': 'MONITOR_INTERVAL',
            'trading.max_gas_price': 'MAX_GAS_PRICE',
            'trading.gas_limit': 'DEFAULT_GAS_LIMIT',
            'risk.max_concurrent_positions': 'MAX_CONCURRENT_POSITIONS',
            'risk.stop_loss_percentage': 'STOP_LOSS_PERCENTAGE',
            'risk.take_profit_percentage': 'TAKE_PROFIT_PERCENTAGE',
            'logging.log_level': 'LOG_LEVEL',
            'logging.log_file': 'LOG_FILE',
            'alerts.telegram_bot_token': 'TELEGRAM_BOT_TOKEN',
            'alerts.telegram_chat_id': 'TELEGRAM_CHAT_ID',
            'trading.private_key': 'PRIVATE_KEY',
            'trading.wallet_address': 'WALLET_ADDRESS',
            'monitoring.min_confidence_score': 'MIN_CONFIDENCE_SCORE'
        }

        assert test_settings.env_mappings == expected_mappings

    def test_nested_env_variable_loading(self, mock_env_vars):
        """Test loading nested configuration from environment variables."""
        with patch.dict(os.environ, {
            'MAX_SLIPPAGE': '0.03',
            'MAX_CONCURRENT_POSITIONS': '15',
            'LOG_LEVEL': 'DEBUG'
        }):
            settings_instance = Settings()

            assert settings_instance.risk.max_slippage == 0.03
            assert settings_instance.risk.max_concurrent_positions == 15
            assert settings_instance.logging.log_level == 'DEBUG'

    def test_invalid_env_variable_values(self):
        """Test handling of invalid environment variable values."""
        with patch.dict(os.environ, {
            'MAX_DAILY_LOSS': 'invalid',
            'MONITOR_INTERVAL': 'not-a-number',
            'ALERT_ON_TRADE': 'maybe'
        }):
            settings_instance = Settings()

            # Should keep default values for invalid conversions
            assert settings_instance.risk.max_daily_loss == 100.0  # default
            assert settings_instance.monitoring.monitor_interval == 15  # default
            assert settings_instance.alerts.alert_on_trade is True  # default


class TestSettingsIntegration:
    """Integration tests for Settings class."""

    def test_full_configuration_loading(self, mock_env_vars, temp_config_file):
        """Test loading full configuration from multiple sources."""
        with patch('config.settings.os.path.exists', return_value=True), \
             patch('config.settings.open') as mock_open, \
             patch('config.settings.Web3') as mock_web3_class:

            # Mock Web3 connection
            mock_web3_instance = Mock()
            mock_web3_instance.is_connected.return_value = True
            mock_web3_class.return_value = mock_web3_instance

            # Mock file reading
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                'target_wallets': ["0x742d35Cc6634C0532925a3b844Bc454e4438f44e"],
                'min_confidence_score': 0.75
            })

            settings_instance = Settings()

            # Validate all settings are loaded correctly
            assert settings_instance.trading.private_key == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            assert settings_instance.risk.max_daily_loss == 100.0
            assert settings_instance.monitoring.monitor_interval == 15
            assert len(settings_instance.monitoring.target_wallets) == 1
            assert settings_instance.monitoring.min_confidence_score == 0.75

    def test_settings_singleton_behavior(self):
        """Test that settings behaves as a singleton."""
        settings1 = Settings()
        settings2 = Settings()

        # Should be the same instance (singleton pattern)
        assert settings1 is settings2

        # Modifications should affect both
        original_value = settings1.risk.max_position_size
        settings1.risk.max_position_size = 999.0
        assert settings2.risk.max_position_size == 999.0

        # Reset for other tests
        settings1.risk.max_position_size = original_value
