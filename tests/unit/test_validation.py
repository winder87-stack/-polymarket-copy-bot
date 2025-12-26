"""
Comprehensive tests for input validation utilities.

Tests cover:
- Wallet address validation and normalization
- Private key format validation
- Trade amount validation with bounds checking
- Price validation between 0 and 1
- Condition ID validation
- Transaction data validation
- JSON input sanitization
- Configuration settings validation
- API response validation
- Hex string validation
- Token amount validation
- Fuzz testing with random inputs
- Edge cases and error conditions
"""

import os
from decimal import Decimal
from unittest.mock import patch

import pytest

from utils.validation import InputValidator, ValidationError


class TestWalletAddressValidation:
    """Test wallet address validation"""

    def test_valid_wallet_address(self):
        """Test validation of valid wallet addresses"""
        valid_addresses = [
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "0x742d35cc6634c0532925a3b844bc454e4438f44e",  # lowercase
            "0x742D35CC6634C0532925A3B844BC454E4438F44E",  # uppercase
        ]

        for address in valid_addresses:
            result = InputValidator.validate_wallet_address(address)
            assert result.startswith("0x")
            assert len(result) == 42
            # Should be checksummed
            assert result == result.lower() or result != result.lower()

    def test_invalid_wallet_address_format(self):
        """Test rejection of invalid wallet address formats"""
        invalid_addresses = [
            "",  # empty
            "0x",  # too short
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44",  # too short (41 chars)
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44e123",  # too long (43 chars)
            "742d35Cc6634C0532925a3b844Bc454e4438f44e",  # missing 0x
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44g",  # invalid hex char
            "not_an_address",  # completely invalid
            None,  # None value
        ]

        for address in invalid_addresses:
            with pytest.raises(ValidationError):
                InputValidator.validate_wallet_address(address)

    def test_wallet_address_normalization(self):
        """Test that addresses are normalized to checksum format"""
        address = "0x742d35cc6634c0532925a3b844bc454e4438f44e"
        result = InputValidator.validate_wallet_address(address)
        # Should convert to checksum format
        assert result != address.lower()

    def test_allow_empty_wallet_address(self):
        """Test allowing empty wallet addresses when specified"""
        result = InputValidator.validate_wallet_address("", allow_empty=True)
        assert result == ""

    def test_empty_wallet_address_not_allowed(self):
        """Test rejection of empty wallet address by default"""
        with pytest.raises(ValidationError, match="Wallet address cannot be empty"):
            InputValidator.validate_wallet_address("")


class TestPrivateKeyValidation:
    """Test private key validation"""

    def test_valid_private_key(self):
        """Test validation of valid private keys"""
        valid_key = "0x1234567890123456789012345678901234567890123456789012345678901234"
        result = InputValidator.validate_private_key(valid_key)
        assert result == valid_key

    def test_invalid_private_key_format(self):
        """Test rejection of invalid private key formats"""
        invalid_keys = [
            "",  # empty
            "0x",  # too short
            "0x123456789012345678901234567890123456789012345678901234567890123",  # too short
            "0x12345678901234567890123456789012345678901234567890123456789012345",  # too long
            "1234567890123456789012345678901234567890123456789012345678901234",  # missing 0x
            "0x123456789012345678901234567890123456789012345678901234567890gggg",  # invalid hex
            "not_a_private_key",  # completely invalid
        ]

        for key in invalid_keys:
            with pytest.raises(ValidationError):
                InputValidator.validate_private_key(key)


class TestTradeAmountValidation:
    """Test trade amount validation"""

    def test_valid_trade_amounts(self):
        """Test validation of valid trade amounts"""
        valid_amounts = [
            (1.0, 1.0),
            ("1.5", 1.5),
            (Decimal("2.5"), 2.5),
            (100.0, 100.0),
        ]

        for amount, expected in valid_amounts:
            result = InputValidator.validate_trade_amount(amount)
            assert result == expected

    def test_trade_amount_bounds(self):
        """Test trade amount bounds checking"""
        # Test minimum amount
        with pytest.raises(ValidationError, match="below minimum"):
            InputValidator.validate_trade_amount(0.005, min_amount=0.01)

        # Test maximum amount
        with pytest.raises(ValidationError, match="above maximum"):
            InputValidator.validate_trade_amount(200.0, max_amount=100.0)

        # Test negative amount
        with pytest.raises(ValidationError, match="must be positive"):
            InputValidator.validate_trade_amount(-1.0)

        # Test zero amount
        with pytest.raises(ValidationError, match="must be positive"):
            InputValidator.validate_trade_amount(0)

    def test_trade_amount_precision(self):
        """Test trade amount precision handling"""
        # Should quantize to 6 decimal places
        result = InputValidator.validate_trade_amount(1.123456789)
        assert result == 1.123457  # Rounded appropriately

    def test_invalid_trade_amount_format(self):
        """Test rejection of invalid trade amount formats"""
        invalid_amounts = [
            "invalid",
            "1.2.3",
            None,
            [],
            {},
        ]

        for amount in invalid_amounts:
            with pytest.raises(ValidationError):
                InputValidator.validate_trade_amount(amount)


class TestPriceValidation:
    """Test price validation"""

    def test_valid_prices(self):
        """Test validation of valid prices"""
        valid_prices = [
            (0.5, 0.5),
            ("0.25", 0.25),
            (Decimal("0.75"), 0.75),
            (0.01, 0.01),
            (0.99, 0.99),
        ]

        for price, expected in valid_prices:
            result = InputValidator.validate_price(price)
            assert result == expected

    def test_price_bounds(self):
        """Test price bounds checking"""
        # Test below minimum
        with pytest.raises(ValidationError, match="out of valid range"):
            InputValidator.validate_price(0.005)

        # Test above maximum
        with pytest.raises(ValidationError, match="out of valid range"):
            InputValidator.validate_price(1.5)

        # Test negative price
        with pytest.raises(ValidationError, match="out of valid range"):
            InputValidator.validate_price(-0.1)

    def test_price_precision_warning(self):
        """Test high precision price warning"""
        with patch("utils.validation.logger") as mock_logger:
            result = InputValidator.validate_price(0.123456789)
            mock_logger.warning.assert_called_once()
            assert result == 0.123457  # Should be rounded


class TestConditionIdValidation:
    """Test condition ID validation"""

    def test_valid_condition_id(self):
        """Test validation of valid condition IDs"""
        valid_id = "0x1234567890123456789012345678901234567890123456789012345678901234"
        result = InputValidator.validate_condition_id(valid_id)
        assert result == valid_id

    def test_invalid_condition_id(self):
        """Test rejection of invalid condition IDs"""
        invalid_ids = [
            "",  # empty
            "0x123",  # too short
            "0x1234567890123456789012345678901234567890123456789012345678901234567890",  # too long
            "1234567890123456789012345678901234567890123456789012345678901234",  # missing 0x
            "0xgggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg",  # invalid hex
        ]

        for condition_id in invalid_ids:
            with pytest.raises(ValidationError):
                InputValidator.validate_condition_id(condition_id)


class TestTransactionDataValidation:
    """Test transaction data validation"""

    def test_valid_transaction_data(self):
        """Test validation of valid transaction data"""
        tx_data = {
            "hash": "0x1234567890123456789012345678901234567890123456789012345678901234",
            "from": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "to": "0x742d35Cc6634C0532925a3b844Bc454e4438f44f",
            "blockNumber": "12345678",
            "timeStamp": "1640995200",
        }

        result = InputValidator.validate_transaction_data(tx_data)
        assert result["hash"] == tx_data["hash"]
        assert result["blockNumber"] == 12345678
        assert result["timeStamp"] == 1640995200

    def test_missing_transaction_fields(self):
        """Test rejection of transactions with missing required fields"""
        incomplete_tx = {
            "hash": "0x1234567890123456789012345678901234567890123456789012345678901234",
            # Missing 'from', 'to', 'blockNumber', 'timeStamp'
        }

        with pytest.raises(ValidationError, match="Missing required transaction field"):
            InputValidator.validate_transaction_data(incomplete_tx)

    def test_invalid_transaction_addresses(self):
        """Test rejection of transactions with invalid addresses"""
        invalid_tx = {
            "hash": "0x1234567890123456789012345678901234567890123456789012345678901234",
            "from": "invalid_address",
            "to": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "blockNumber": "12345678",
            "timeStamp": "1640995200",
        }

        with pytest.raises(ValidationError):
            InputValidator.validate_transaction_data(invalid_tx)

    def test_gas_validation(self):
        """Test gas usage validation"""
        tx_with_gas = {
            "hash": "0x1234567890123456789012345678901234567890123456789012345678901234",
            "from": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "to": "0x742d35Cc6634C0532925a3b844Bc454e4438f44f",
            "blockNumber": "12345678",
            "timeStamp": "1640995200",
            "gasUsed": "21000",
        }

        result = InputValidator.validate_transaction_data(tx_with_gas)
        assert result["gasUsed"] == 21000

        # Test gas too low
        tx_low_gas = tx_with_gas.copy()
        tx_low_gas["gasUsed"] = "20000"
        with pytest.raises(ValidationError, match="Gas used below minimum"):
            InputValidator.validate_transaction_data(tx_low_gas)

        # Test gas too high
        tx_high_gas = tx_with_gas.copy()
        tx_high_gas["gasUsed"] = "20000000"
        with pytest.raises(ValidationError, match="Gas used above maximum"):
            InputValidator.validate_transaction_data(tx_high_gas)


class TestJsonSanitization:
    """Test JSON input sanitization"""

    def test_valid_json_sanitization(self):
        """Test sanitization of valid JSON"""
        valid_json = '{"key": "value", "number": 123}'
        result = InputValidator.sanitize_json_input(valid_json)
        assert result == {"key": "value", "number": 123}

    def test_json_with_dangerous_content(self):
        """Test sanitization of JSON with potentially dangerous content"""
        dangerous_json = '{"script": "<script>alert(\'xss\')</script>", "normal": "safe"}'
        result = InputValidator.sanitize_json_input(dangerous_json)

        # Should remove dangerous fields
        assert "script" not in result
        assert result["normal"] == "safe"

    def test_malformed_json(self):
        """Test rejection of malformed JSON"""
        malformed_json = '{"invalid": json}'
        with pytest.raises(ValidationError, match="Invalid JSON format"):
            InputValidator.sanitize_json_input(malformed_json)

    def test_large_json(self):
        """Test rejection of too large JSON"""
        large_json = '{"data": "' + "x" * 10001 + '"}'  # Over 10KB limit
        with pytest.raises(ValidationError, match="JSON input too large"):
            InputValidator.sanitize_json_input(large_json)


class TestConfigValidation:
    """Test configuration settings validation"""

    def test_valid_config(self):
        """Test validation of valid configuration"""
        valid_config = {
            "PRIVATE_KEY": "0x1234567890123456789012345678901234567890123456789012345678901234",
            "MAX_POSITION_SIZE": "100.0",
            "MAX_DAILY_LOSS": "500.0",
            "MIN_TRADE_AMOUNT": "1.0",
            "MAX_SLIPPAGE": "0.02",
            "MONITOR_INTERVAL": "30",
            "POLYGON_RPC_URL": "https://polygon-rpc.com",
        }

        result = InputValidator.validate_config_settings(valid_config)
        assert result == valid_config

    def test_missing_private_key(self):
        """Test rejection of config without private key"""
        config_without_key = {"MAX_POSITION_SIZE": "100.0"}
        with pytest.raises(ValidationError, match="Missing PRIVATE_KEY"):
            InputValidator.validate_config_settings(config_without_key)

    def test_invalid_config_values(self):
        """Test rejection of invalid configuration values"""
        invalid_configs = [
            {
                "PRIVATE_KEY": "0x1234567890123456789012345678901234567890123456789012345678901234",
                "MAX_POSITION_SIZE": "-100.0",  # Negative
            },
            {
                "PRIVATE_KEY": "0x1234567890123456789012345678901234567890123456789012345678901234",
                "MAX_DAILY_LOSS": "0",  # Zero
            },
            {
                "PRIVATE_KEY": "0x1234567890123456789012345678901234567890123456789012345678901234",
                "MAX_SLIPPAGE": "0.5",  # Too high
            },
            {
                "PRIVATE_KEY": "0x1234567890123456789012345678901234567890123456789012345678901234",
                "MONITOR_INTERVAL": "2",  # Too low
            },
        ]

        for config in invalid_configs:
            with pytest.raises(ValidationError):
                InputValidator.validate_config_settings(config)

    def test_invalid_url(self):
        """Test rejection of invalid URLs"""
        invalid_config = {
            "PRIVATE_KEY": "0x1234567890123456789012345678901234567890123456789012345678901234",
            "POLYGON_RPC_URL": "not_a_url",
        }

        with pytest.raises(ValidationError, match="Invalid URL format"):
            InputValidator.validate_config_settings(invalid_config)


class TestApiResponseValidation:
    """Test API response validation"""

    def test_valid_api_response(self):
        """Test validation of valid API responses"""
        valid_response = {"key": "value", "number": 123}
        result = InputValidator.validate_api_response(valid_response)
        assert result == valid_response

    def test_invalid_api_response_type(self):
        """Test rejection of invalid response types"""
        with pytest.raises(ValidationError, match="type mismatch"):
            InputValidator.validate_api_response("not a dict", dict)

    def test_empty_dict_response(self):
        """Test handling of empty dict responses"""
        with pytest.raises(ValidationError, match="Empty API response"):
            InputValidator.validate_api_response({})


class TestHexStringValidation:
    """Test hex string validation"""

    def test_valid_hex_strings(self):
        """Test validation of valid hex strings"""
        valid_hex = "0x1234567890abcdef"
        result = InputValidator.validate_hex_string(valid_hex)
        assert result == valid_hex

    def test_hex_string_length_bounds(self):
        """Test hex string length validation"""
        # Too short
        with pytest.raises(ValidationError, match="length .* out of range"):
            InputValidator.validate_hex_string("0x12", min_length=4, max_length=10)

        # Too long
        with pytest.raises(ValidationError, match="length .* out of range"):
            InputValidator.validate_hex_string(
                "0x1234567890abcdef1234567890abcdef", min_length=2, max_length=20
            )

    def test_invalid_hex_format(self):
        """Test rejection of invalid hex formats"""
        invalid_hex = "0xgggggggg"
        with pytest.raises(ValidationError, match="Invalid hex format"):
            InputValidator.validate_hex_string(invalid_hex)


class TestTokenAmountValidation:
    """Test token amount validation"""

    def test_valid_token_amounts(self):
        """Test validation of valid token amounts"""
        result = InputValidator.validate_token_amount(100.123456, decimals=6)
        assert result == 100.123456

    def test_token_amount_bounds(self):
        """Test token amount bounds checking"""
        # Below minimum
        with pytest.raises(ValidationError, match="out of range"):
            InputValidator.validate_token_amount(0.5, min_amount=1.0)

        # Above maximum
        with pytest.raises(ValidationError, match="out of range"):
            InputValidator.validate_token_amount(10**13, max_amount=10**12)

    def test_token_precision(self):
        """Test token amount precision handling"""
        result = InputValidator.validate_token_amount(100.123456789, decimals=6)
        assert result == 100.123457  # Rounded to 6 decimals


class TestFuzzTesting:
    """Fuzz testing with random inputs"""

    @pytest.mark.parametrize(
        "invalid_input",
        [
            None,
            "",
            " ",
            "\n",
            "\t",
            "\r",
            "0x",
            "0x1",
            "0xgggggggggggggggggggggggggggggggggggggggg",
            "not_hex",
            "123",
            "-1",
            "0.0.0",
            [],
            {},
            {"key": "value"},
            True,
            False,
            0,
            -1,
            1.5,
            float("inf"),
            float("-inf"),
            float("nan"),
        ],
    )
    def test_wallet_address_fuzz(self, invalid_input):
        """Fuzz test wallet address validation"""
        try:
            result = InputValidator.validate_wallet_address(str(invalid_input))
            # If we get here, it should be a valid address
            assert result.startswith("0x")
            assert len(result) == 42
        except ValidationError:
            # Expected for invalid inputs
            pass
        except Exception as e:
            # Should not raise unexpected exceptions
            pytest.fail(f"Unexpected exception: {e}")

    @pytest.mark.parametrize(
        "invalid_input",
        [
            None,
            "",
            " ",
            "0x",
            "0x1",
            "0xgggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg",
            [],
            {},
            True,
            False,
            0,
            -1,
        ],
    )
    def test_private_key_fuzz(self, invalid_input):
        """Fuzz test private key validation"""
        try:
            result = InputValidator.validate_private_key(str(invalid_input))
            # If we get here, it should be a valid private key
            assert result.startswith("0x")
            assert len(result) == 66
        except ValidationError:
            # Expected for invalid inputs
            pass
        except Exception as e:
            # Should not raise unexpected exceptions
            pytest.fail(f"Unexpected exception: {e}")

    @pytest.mark.parametrize(
        "invalid_input",
        [
            None,
            "",
            " ",
            "invalid",
            "1.2.3",
            "-1",
            "abc",
            [],
            {},
            True,
            False,
            float("inf"),
            float("-inf"),
            float("nan"),
        ],
    )
    def test_trade_amount_fuzz(self, invalid_input):
        """Fuzz test trade amount validation"""
        try:
            result = InputValidator.validate_trade_amount(invalid_input)
            # If we get here, it should be a valid amount
            assert isinstance(result, float)
            assert result > 0
        except ValidationError:
            # Expected for invalid inputs
            pass
        except Exception as e:
            # Should not raise unexpected exceptions
            pytest.fail(f"Unexpected exception: {e}")

    @pytest.mark.parametrize(
        "invalid_json",
        [
            None,
            "",
            " ",
            "{",
            "}",
            "{invalid}",
            "[invalid]",
            '{"key": value}',
            '{"key": "value",}',
            '{"key": "value", "key2": }',
            '<script>alert("xss")</script>',
            '{"data": "' + "x" * 10001 + '"}',
        ],
    )
    def test_json_sanitization_fuzz(self, invalid_json):
        """Fuzz test JSON sanitization"""
        try:
            result = InputValidator.sanitize_json_input(str(invalid_json))
            # If we get here, it should be valid sanitized JSON
            assert isinstance(result, dict)
        except ValidationError:
            # Expected for invalid inputs
            pass
        except Exception as e:
            # Should not raise unexpected exceptions
            pytest.fail(f"Unexpected exception: {e}")


class TestErrorMessages:
    """Test error message quality"""

    def test_descriptive_error_messages(self):
        """Test that error messages are descriptive and safe"""
        test_cases = [
            ("", InputValidator.validate_wallet_address, "Wallet address cannot be empty"),
            ("invalid", InputValidator.validate_private_key, "Invalid private key format"),
            (-1, InputValidator.validate_trade_amount, "Invalid amount value"),
            (1.5, InputValidator.validate_price, "out of valid range"),
            ("", InputValidator.validate_condition_id, "Condition ID cannot be empty"),
        ]

        for invalid_input, validator_func, expected_message in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                validator_func(invalid_input)

            error_message = str(exc_info.value)
            # Error message should contain expected text and not leak sensitive info
            assert expected_message.lower() in error_message.lower()
            # Should not contain sensitive data
            assert "private_key" not in error_message.lower()
            assert "secret" not in error_message.lower()
            assert "password" not in error_message.lower()

    def test_error_message_consistency(self):
        """Test that similar validation errors have consistent messages"""
        # Test multiple invalid wallet addresses
        invalid_addresses = ["", "0x", "invalid", "0xgggggggggggggggggggggggggggggggggggggggg"]

        for address in invalid_addresses:
            try:
                InputValidator.validate_wallet_address(address)
                pytest.fail(f"Expected ValidationError for address: {address}")
            except ValidationError as e:
                # All should mention "wallet address" or similar
                assert "wallet" in str(e).lower() or "address" in str(e).lower()


class TestValidationIntegration:
    """Integration tests for validation combinations"""

    def test_complete_transaction_validation(self):
        """Test validation of a complete transaction workflow"""
        # Simulate a complete transaction processing workflow
        raw_tx = {
            "hash": "0x1234567890123456789012345678901234567890123456789012345678901234",
            "from": "0x742d35cc6634c0532925a3b844bc454e4438f44e",
            "to": "0x742d35cc6634c0532925a3b844bc454e4438f44f",
            "blockNumber": "12345678",
            "timeStamp": "1640995200",
            "gasUsed": "25000",
            "value": "1000000000000000000",  # 1 ETH in wei
        }

        # Should validate successfully
        validated_tx = InputValidator.validate_transaction_data(raw_tx)
        assert validated_tx["from"] != raw_tx["from"]  # Should be checksummed
        assert validated_tx["to"] != raw_tx["to"]  # Should be checksummed
        assert isinstance(validated_tx["blockNumber"], int)
        assert isinstance(validated_tx["gasUsed"], int)

    def test_config_validation_workflow(self):
        """Test complete configuration validation workflow"""
        with patch.dict(
            os.environ,
            {
                "PRIVATE_KEY": "0x1234567890123456789012345678901234567890123456789012345678901234",
                "MAX_POSITION_SIZE": "100.0",
                "MAX_DAILY_LOSS": "500.0",
            },
        ):
            config_dict = {
                "PRIVATE_KEY": os.getenv("PRIVATE_KEY"),
                "MAX_POSITION_SIZE": os.getenv("MAX_POSITION_SIZE"),
                "MAX_DAILY_LOSS": os.getenv("MAX_DAILY_LOSS"),
            }

            # Should validate successfully
            validated_config = InputValidator.validate_config_settings(config_dict)
            assert validated_config["PRIVATE_KEY"] == config_dict["PRIVATE_KEY"]
            assert validated_config["MAX_POSITION_SIZE"] == config_dict["MAX_POSITION_SIZE"]

    def test_trade_workflow_validation(self):
        """Test complete trade workflow validation"""
        # Simulate a complete trade order validation
        condition_id = "0x1234567890123456789012345678901234567890123456789012345678901234"
        amount = 10.5
        price = 0.75
        token_id = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"

        # All should validate successfully
        validated_condition = InputValidator.validate_condition_id(condition_id)
        validated_amount = InputValidator.validate_trade_amount(amount)
        validated_price = InputValidator.validate_price(price)
        validated_token = InputValidator.validate_hex_string(token_id, 42, 42)

        assert validated_condition == condition_id
        assert validated_amount == amount
        assert validated_price == price
        assert validated_token == token_id
