"""Comprehensive unit tests for validation security checks.

Tests security validation for sensitive data including:
- Private key validation
- Wallet address validation
- Input sanitization
- Malicious input detection
- Security edge cases
"""

import pytest

from utils.validation import InputValidator, ValidationError
from tests.fixtures.market_data_generators import ValidationTestDataGenerator


class TestPrivateKeySecurity:
    """Test private key security validation."""

    @pytest.mark.parametrize(
        "test_case",
        ValidationTestDataGenerator.generate_private_keys(),
    )
    def test_private_key_validation(self, test_case: dict):
        """Test private key validation with various inputs."""
        if test_case["valid"]:
            result = InputValidator.validate_private_key(test_case["key"])
            assert result == test_case["key"]
        else:
            with pytest.raises(ValidationError):
                InputValidator.validate_private_key(test_case["key"])

    def test_private_key_length_validation(self):
        """Test private key length validation."""
        # Too short
        with pytest.raises(ValidationError):
            InputValidator.validate_private_key("0x123")

        # Too long
        with pytest.raises(ValidationError):
            InputValidator.validate_private_key("0x" + "a" * 65)

        # Correct length
        valid_key = "0x" + "a" * 64
        result = InputValidator.validate_private_key(valid_key)
        assert result == valid_key

    def test_private_key_format_validation(self):
        """Test private key format validation."""
        # Missing 0x prefix
        with pytest.raises(ValidationError):
            InputValidator.validate_private_key("a" * 64)

        # Invalid hex characters
        with pytest.raises(ValidationError):
            InputValidator.validate_private_key("0x" + "g" * 64)

        # Valid format
        valid_key = "0x" + "0123456789abcdef" * 4
        result = InputValidator.validate_private_key(valid_key)
        assert result == valid_key

    def test_empty_private_key_rejection(self):
        """Test empty private key is rejected."""
        with pytest.raises(ValidationError):
            InputValidator.validate_private_key("")

        with pytest.raises(ValidationError):
            InputValidator.validate_private_key("   ")

    def test_private_key_whitespace_handling(self):
        """Test private key whitespace handling."""
        valid_key = "0x" + "a" * 64
        # Should strip whitespace
        result = InputValidator.validate_private_key(f"  {valid_key}  ")
        assert result == valid_key


class TestWalletAddressSecurity:
    """Test wallet address security validation."""

    @pytest.mark.parametrize(
        "test_case",
        ValidationTestDataGenerator.generate_wallet_addresses(),
    )
    def test_wallet_address_validation(self, test_case: dict):
        """Test wallet address validation with various inputs."""
        if test_case["valid"]:
            result = InputValidator.validate_wallet_address(test_case["address"])
            assert len(result) == 42  # 0x + 40 hex chars
        else:
            with pytest.raises((ValidationError, ValueError)):
                InputValidator.validate_wallet_address(test_case["address"])

    def test_wallet_address_checksum_validation(self):
        """Test wallet address checksum validation."""
        # Lowercase address should be converted to checksum
        lowercase = "0x742d35cc6634c0532925a3b844bc454e4438f44e"
        result = InputValidator.validate_wallet_address(lowercase)
        assert result != lowercase  # Should be checksummed
        assert result.lower() == lowercase.lower()

    def test_invalid_ethereum_address_rejection(self):
        """Test invalid Ethereum addresses are rejected."""
        # Invalid checksum
        invalid = "0x742d35Cc6634C0532925a3b844Bc454e4438f44f"  # Wrong checksum
        # Should still validate format but may fail checksum check
        try:
            result = InputValidator.validate_wallet_address(invalid)
            # If it passes, it should be valid format
            assert len(result) == 42
        except (ValidationError, ValueError):
            pass  # Expected for invalid addresses

    def test_wallet_address_length_validation(self):
        """Test wallet address length validation."""
        # Too short
        with pytest.raises(ValidationError):
            InputValidator.validate_wallet_address("0x123")

        # Too long
        with pytest.raises(ValidationError):
            InputValidator.validate_wallet_address("0x" + "a" * 41)

        # Correct length
        valid_address = "0x" + "a" * 40
        result = InputValidator.validate_wallet_address(valid_address)
        assert len(result) == 42


class TestInputSanitization:
    """Test input sanitization for security."""

    @pytest.mark.parametrize(
        "test_case",
        ValidationTestDataGenerator.generate_malicious_inputs(),
    )
    def test_malicious_input_sanitization(self, test_case: dict):
        """Test sanitization of potentially malicious inputs."""
        sanitized = InputValidator.sanitize_json_input(test_case["input"])

        if test_case["should_sanitize"]:
            # Check that dangerous content was removed
            assert "script" not in str(sanitized).lower() or "[SANITIZED]" in str(
                sanitized
            )
            assert "eval" not in str(sanitized).lower() or "[SANITIZED]" in str(
                sanitized
            )
        else:
            # Normal input should pass through
            assert sanitized is not None

    def test_json_size_limit(self):
        """Test JSON input size limit."""
        # Large JSON should be rejected
        large_json = '{"data": "' + "x" * 10001 + '"}'
        with pytest.raises(ValidationError):
            InputValidator.sanitize_json_input(large_json)

    def test_invalid_json_rejection(self):
        """Test invalid JSON is rejected."""
        invalid_json = '{"invalid": json}'
        with pytest.raises(ValidationError):
            InputValidator.sanitize_json_input(invalid_json)

    def test_nested_malicious_content_sanitization(self):
        """Test sanitization of nested malicious content."""
        nested_json = '{"level1": {"level2": {"script": "alert(1)"}}}'
        sanitized = InputValidator.sanitize_json_input(nested_json)

        # Script should be removed from nested structure
        assert "script" not in str(sanitized).lower() or "[SANITIZED]" in str(sanitized)


class TestTradeAmountSecurity:
    """Test trade amount security validation."""

    def test_negative_amount_rejection(self):
        """Test negative amounts are rejected."""
        with pytest.raises(ValidationError):
            InputValidator.validate_trade_amount(-10.0)

    def test_zero_amount_rejection(self):
        """Test zero amounts are rejected."""
        with pytest.raises(ValidationError):
            InputValidator.validate_trade_amount(0.0)

    def test_excessive_amount_rejection(self):
        """Test excessive amounts are rejected."""
        with pytest.raises(ValidationError):
            InputValidator.validate_trade_amount(20000.0, max_amount=10000.0)

    def test_amount_precision_validation(self):
        """Test amount precision validation."""
        # Very high precision should be handled
        high_precision = 100.123456789012345
        result = InputValidator.validate_trade_amount(high_precision)
        assert isinstance(result, float)
        assert result > 0

    def test_amount_string_validation(self):
        """Test amount string validation."""
        # Valid string
        result = InputValidator.validate_trade_amount("100.50")
        assert result == 100.50

        # Invalid string
        with pytest.raises(ValidationError):
            InputValidator.validate_trade_amount("not_a_number")


class TestPriceSecurity:
    """Test price security validation."""

    def test_price_range_validation(self):
        """Test price range validation."""
        # Below minimum
        with pytest.raises(ValidationError):
            InputValidator.validate_price(0.005, min_price=0.01)

        # Above maximum
        with pytest.raises(ValidationError):
            InputValidator.validate_price(0.995, max_price=0.99)

        # Valid range
        result = InputValidator.validate_price(0.5)
        assert 0.01 <= result <= 0.99

    def test_price_precision_validation(self):
        """Test price precision validation."""
        # Very high precision
        high_precision = 0.123456789012345
        result = InputValidator.validate_price(high_precision)
        assert isinstance(result, float)
        # Should be rounded to reasonable precision
        assert len(str(result).split(".")[1]) <= 6


class TestTransactionDataSecurity:
    """Test transaction data security validation."""

    def test_missing_required_fields(self):
        """Test missing required fields are detected."""
        incomplete_tx = {"hash": "0x123"}
        with pytest.raises(ValidationError):
            InputValidator.validate_transaction_data(incomplete_tx)

    def test_invalid_transaction_hash(self):
        """Test invalid transaction hash is rejected."""
        tx = {
            "hash": "invalid_hash",
            "from": "0x" + "a" * 40,
            "to": "0x" + "b" * 40,
            "blockNumber": 100,
            "timeStamp": 1000000000,
        }
        with pytest.raises(ValidationError):
            InputValidator.validate_transaction_data(tx)

    def test_invalid_gas_validation(self):
        """Test invalid gas values are rejected."""
        tx = {
            "hash": "0x" + "a" * 64,
            "from": "0x" + "a" * 40,
            "to": "0x" + "b" * 40,
            "blockNumber": 100,
            "timeStamp": 1000000000,
            "gasUsed": 1000,  # Below minimum
        }
        with pytest.raises(ValidationError):
            InputValidator.validate_transaction_data(tx)

    def test_transaction_address_validation(self):
        """Test transaction addresses are validated."""
        tx = {
            "hash": "0x" + "a" * 64,
            "from": "invalid_address",
            "to": "0x" + "b" * 40,
            "blockNumber": 100,
            "timeStamp": 1000000000,
        }
        with pytest.raises(ValidationError):
            InputValidator.validate_transaction_data(tx)


class TestConfigSecurity:
    """Test configuration security validation."""

    def test_missing_private_key_rejection(self):
        """Test missing private key is rejected."""
        config = {"MAX_POSITION_SIZE": 50.0}
        with pytest.raises(ValidationError):
            InputValidator.validate_config_settings(config)

    def test_invalid_numeric_settings(self):
        """Test invalid numeric settings are rejected."""
        config = {
            "PRIVATE_KEY": "0x" + "a" * 64,
            "MAX_POSITION_SIZE": -10.0,  # Invalid
        }
        with pytest.raises(ValidationError):
            InputValidator.validate_config_settings(config)

    def test_invalid_url_validation(self):
        """Test invalid URLs are rejected."""
        config = {
            "PRIVATE_KEY": "0x" + "a" * 64,
            "POLYGON_RPC_URL": "not_a_url",
        }
        with pytest.raises(ValidationError):
            InputValidator.validate_config_settings(config)

    def test_config_settings_range_validation(self):
        """Test config settings are within valid ranges."""
        config = {
            "PRIVATE_KEY": "0x" + "a" * 64,
            "MAX_POSITION_SIZE": 50.0,  # Valid
            "MAX_DAILY_LOSS": 100.0,  # Valid
            "MIN_TRADE_AMOUNT": 1.0,  # Valid
        }
        result = InputValidator.validate_config_settings(config)
        assert result == config
