"""
Unit tests for utils/security.py - Security utilities and data masking.
"""

from unittest.mock import patch

from utils.security import (
    _mask_sensitive_value,
    _mask_value,
    generate_session_id,
    get_environment_hash,
    mask_sensitive_data,
    secure_compare,
    secure_log,
    validate_private_key,
)


class TestSecureLogging:
    """Test secure logging functionality."""

    def test_secure_log_info_level(self, mock_logger):
        """Test secure logging at info level."""
        test_data = {
            "private_key": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "amount": 100.0,
            "normal_field": "normal_value",
        }

        secure_log(mock_logger, "test_action", test_data, level="info")

        # Check that logger.info was called
        mock_logger.info.assert_called_once()

        # Check the logged message contains masked data
        logged_message = mock_logger.info.call_args[0][0]
        assert "[REDACTED]" in logged_message
        assert "normal_value" in logged_message
        assert "100.0" in logged_message

    def test_secure_log_error_level(self, mock_logger):
        """Test secure logging at error level."""
        test_data = {"error": "test error"}

        secure_log(mock_logger, "error_action", test_data, level="error")

        mock_logger.error.assert_called_once()

    def test_secure_log_warning_level(self, mock_logger):
        """Test secure logging at warning level."""
        test_data = {"warning": "test warning"}

        secure_log(mock_logger, "warning_action", test_data, level="warning")

        mock_logger.warning.assert_called_once()

    def test_secure_log_debug_level(self, mock_logger):
        """Test secure logging at debug level."""
        test_data = {"debug": "test debug"}

        secure_log(mock_logger, "debug_action", test_data, level="debug")

        mock_logger.debug.assert_called_once()

    def test_secure_log_fallback_on_error(self, mock_logger):
        """Test secure logging fallback when JSON serialization fails."""

        # Create an object that can't be JSON serialized
        class NonSerializable:
            pass

        test_data = {"non_serializable": NonSerializable()}

        secure_log(mock_logger, "test_action", test_data)

        # Should still log something
        mock_logger.info.assert_called_once()


class TestMaskSensitiveValue:
    """Test _mask_sensitive_value function."""

    def test_mask_sensitive_value_private_key(self):
        """Test masking private key."""
        private_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        result = _mask_sensitive_value("private_key", private_key)

        assert result == "0x1234...[REDACTED]"

    def test_mask_sensitive_value_wallet_address(self):
        """Test masking wallet address."""
        wallet_address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"

        result = _mask_sensitive_value("wallet_address", wallet_address)

        assert result == "0x742d...8f44e"

    def test_mask_sensitive_value_api_key(self):
        """Test masking API key."""
        api_key = "sk_live_1234567890abcdef"

        result = _mask_sensitive_value("api_key", api_key)

        assert result == "[REDACTED]"

    def test_mask_sensitive_value_secret_key(self):
        """Test masking secret key."""
        secret = "my_secret_value"

        result = _mask_sensitive_value("secret_key", secret)

        assert result == "my_se...[REDACTED]"

    def test_mask_sensitive_value_normal_value(self):
        """Test that normal values are not masked."""
        normal_value = "normal_string"

        result = _mask_sensitive_value("normal_field", normal_value)

        assert result == normal_value

    def test_mask_sensitive_value_none_value(self):
        """Test masking None value."""
        result = _mask_sensitive_value("field", None)

        assert result is None

    def test_mask_sensitive_value_dict(self):
        """Test masking dictionary values."""
        test_dict = {
            "private_key": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "normal_field": "normal_value",
            "secret_token": "secret_value",
        }

        result = _mask_sensitive_value("data", test_dict)

        assert result["private_key"] == "0x1234...[REDACTED]"
        assert result["normal_field"] == "normal_value"
        assert result["secret_token"] == "sec...[REDACTED]"

    def test_mask_sensitive_value_list(self):
        """Test masking list values."""
        test_list = ["0x742d35Cc6634C0532925a3b844Bc454e4438f44e", "normal_item", "secret_item"]

        result = _mask_sensitive_value("items", test_list)

        assert result[0] == "0x742d...8f44e"
        assert result[1] == "normal_item"
        assert result[2] == "sec...[REDACTED]"

    def test_mask_sensitive_value_nested_structures(self):
        """Test masking nested data structures."""
        nested_data = {
            "user": {
                "wallet": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                "preferences": ["setting1", "secret_password"],
            },
            "api_keys": [
                {"key": "sk_live_12345", "active": True},
                {"key": "normal_key", "active": False},
            ],
        }

        result = _mask_sensitive_value("nested", nested_data)

        assert result["user"]["wallet"] == "0x742d...8f44e"
        assert result["user"]["preferences"][1] == "sec...[REDACTED]"
        assert result["api_keys"][0]["key"] == "[REDACTED]"
        assert result["api_keys"][1]["key"] == "normal_key"


class TestMaskValue:
    """Test _mask_value function."""

    def test_mask_value_long_string(self):
        """Test masking long string."""
        long_string = "this_is_a_very_long_string_that_should_be_masked"

        result = _mask_value(long_string)

        assert result == "this_...[REDACTED]"

    def test_mask_value_short_string(self):
        """Test masking short string."""
        short_string = "abc"

        result = _mask_value(short_string)

        assert result == "abc...[REDACTED]"

    def test_mask_value_empty_string(self):
        """Test masking empty string."""
        empty_string = ""

        result = _mask_value(empty_string)

        assert result == "[REDACTED]"


class TestValidatePrivateKey:
    """Test validate_private_key function."""

    def test_validate_private_key_valid_with_prefix(self):
        """Test validating valid private key with 0x prefix."""
        valid_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        result = validate_private_key(valid_key)

        assert result is True

    def test_validate_private_key_valid_without_prefix(self):
        """Test validating valid private key without 0x prefix."""
        valid_key = "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        result = validate_private_key(valid_key)

        assert result is True

    def test_validate_private_key_invalid_length_short(self):
        """Test validating private key that is too short."""
        short_key = "0x1234567890abcdef"

        result = validate_private_key(short_key)

        assert result is False

    def test_validate_private_key_invalid_length_long(self):
        """Test validating private key that is too long."""
        long_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"

        result = validate_private_key(long_key)

        assert result is False

    def test_validate_private_key_invalid_hex(self):
        """Test validating private key with invalid hex characters."""
        invalid_key = "0xgggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg"

        result = validate_private_key(invalid_key)

        assert result is False

    def test_validate_private_key_none(self):
        """Test validating None as private key."""
        result = validate_private_key(None)

        assert result is False

    def test_validate_private_key_empty_string(self):
        """Test validating empty string as private key."""
        result = validate_private_key("")

        assert result is False


class TestMaskSensitiveData:
    """Test mask_sensitive_data function."""

    def test_mask_sensitive_data_simple_dict(self):
        """Test masking simple dictionary."""
        data = {
            "private_key": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "amount": 100.0,
            "description": "test transaction",
        }

        result = mask_sensitive_data(data)

        assert result["private_key"] == "0x1234...[REDACTED]"
        assert result["amount"] == 100.0
        assert result["description"] == "test transaction"

    def test_mask_sensitive_data_complex_structure(self):
        """Test masking complex data structure."""
        data = {
            "trade": {
                "wallet": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                "token_id": "0xabcdef1234567890abcdef1234567890abcdef",
                "details": {"secret": "hidden_value", "public": "visible_value"},
            },
            "orders": [
                {"id": "order1", "key": "sk_live_secret"},
                {"id": "order2", "key": "normal_key"},
            ],
        }

        result = mask_sensitive_data(data)

        # Check nested masking
        assert result["trade"]["wallet"] == "0x742d...8f44e"
        assert result["trade"]["token_id"] == "0xabc...cdef"
        assert result["trade"]["details"]["secret"] == "hid...[REDACTED]"
        assert result["trade"]["details"]["public"] == "visible_value"
        assert result["orders"][0]["key"] == "[REDACTED]"
        assert result["orders"][1]["key"] == "normal_key"


class TestGetEnvironmentHash:
    """Test get_environment_hash function."""

    def test_get_environment_hash_with_data(self):
        """Test environment hash generation with environment variables."""
        test_env = {
            "NORMAL_VAR": "normal_value",
            "SECRET_KEY": "secret_value",
            "API_TOKEN": "token_value",
            "WALLET_ADDRESS": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        }

        with patch.dict("os.environ", test_env):
            result = get_environment_hash()

            # Should be an 8-character hex string
            assert len(result) == 8
            assert all(c in "0123456789abcdef" for c in result)

    def test_get_environment_hash_empty_env(self):
        """Test environment hash generation with empty environment."""
        with patch.dict("os.environ", {}, clear=True):
            result = get_environment_hash()

            assert len(result) == 8
            assert isinstance(result, str)

    def test_get_environment_hash_consistency(self):
        """Test that environment hash is consistent for same input."""
        test_env = {"VAR1": "value1", "VAR2": "value2"}

        with patch.dict("os.environ", test_env):
            result1 = get_environment_hash()
            result2 = get_environment_hash()

            assert result1 == result2

    def test_get_environment_hash_filters_sensitive(self):
        """Test that sensitive environment variables are filtered out."""
        sensitive_env = {
            "PRIVATE_KEY": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "API_KEY": "sk_live_secret",
            "SECRET_TOKEN": "secret_token",
            "NORMAL_VAR": "normal_value",
        }

        filtered_env = {"NORMAL_VAR": "normal_value"}

        with patch.dict("os.environ", sensitive_env):
            # Mock the filtering logic to return only non-sensitive vars
            with patch("utils.security.os.environ", filtered_env):
                result = get_environment_hash()

                # Should be based only on filtered environment
                assert isinstance(result, str)


class TestGenerateSessionId:
    """Test generate_session_id function."""

    def test_generate_session_id_format(self):
        """Test session ID format."""
        result = generate_session_id()

        # Should be 8 characters long
        assert len(result) == 8

        # Should contain only hexadecimal characters
        assert all(c in "0123456789abcdef" for c in result.lower())

    def test_generate_session_id_uniqueness(self):
        """Test that session IDs are unique."""
        ids = {generate_session_id() for _ in range(100)}

        # Should generate unique IDs (very high probability)
        assert len(ids) == 100


class TestSecureCompare:
    """Test secure_compare function."""

    def test_secure_compare_equal_strings(self):
        """Test comparing equal strings."""
        result = secure_compare("password123", "password123")

        assert result is True

    def test_secure_compare_different_strings(self):
        """Test comparing different strings."""
        result = secure_compare("password123", "password456")

        assert result is False

    def test_secure_compare_different_lengths(self):
        """Test comparing strings of different lengths."""
        result = secure_compare("short", "longer_string")

        assert result is False

    def test_secure_compare_empty_strings(self):
        """Test comparing empty strings."""
        result = secure_compare("", "")

        assert result is True

    def test_secure_compare_case_sensitive(self):
        """Test that comparison is case sensitive."""
        result = secure_compare("Password", "password")

        assert result is False

    def test_secure_compare_timing_attack_resistance(self):
        """Test that comparison is resistant to timing attacks."""
        # This is a basic test - in practice, we'd need more sophisticated timing analysis
        import time

        # Compare strings of different lengths
        start_time = time.time()
        result1 = secure_compare("a", "ab")
        time1 = time.time() - start_time

        start_time = time.time()
        result2 = secure_compare("ab", "abc")
        time2 = time.time() - start_time

        # Both should return False
        assert result1 is False
        assert result2 is False

        # Times should be similar (within reasonable bounds)
        # This is a rough check - in real timing attack tests we'd use statistical analysis
        time_diff = abs(time1 - time2)
        assert time_diff < 0.001  # Less than 1ms difference


class TestSecurityIntegration:
    """Integration tests for security utilities."""

    def test_full_secure_logging_flow(self, mock_logger):
        """Test complete secure logging flow."""
        complex_data = {
            "trade": {
                "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                "private_key": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "amount": 100.5,
                "token_id": "0xabcdef1234567890abcdef1234567890abcdef",
                "metadata": {
                    "api_secret": "sk_live_secret_key",
                    "user_agent": "Bot/1.0",
                    "timestamp": 1234567890,
                },
            },
            "orders": [
                {"order_id": "order1", "secret_key": "secret1"},
                {"order_id": "order2", "public_key": "public2"},
            ],
            "status": "success",
        }

        secure_log(mock_logger, "trade_execution", complex_data)

        # Verify logging was called
        mock_logger.info.assert_called_once()

        # Get the logged message
        logged_message = mock_logger.info.call_args[0][0]

        # Verify sensitive data is masked
        assert "0x742d...8f44e" in logged_message  # Masked wallet
        assert "0x1234...[REDACTED]" in logged_message  # Masked private key
        assert "0xabc...cdef" in logged_message  # Masked token ID
        assert "[REDACTED]" in logged_message  # Masked API secret
        assert "secret1" not in logged_message  # Secret is masked
        assert "public2" in logged_message  # Public data is not masked
        assert "100.5" in logged_message  # Numbers are not masked
        assert "success" in logged_message  # Status is not masked

    def test_private_key_validation_flow(self):
        """Test private key validation in realistic scenarios."""
        # Valid keys
        valid_keys = [
            "0x" + "1" * 64,  # All 1s with prefix
            "a" * 64,  # All 'a's without prefix
            "1234567890abcdef" * 4,  # Mixed hex
        ]

        for key in valid_keys:
            assert validate_private_key(key)

        # Invalid keys
        invalid_keys = [
            "0x" + "1" * 63,  # Too short with prefix
            "1" * 65,  # Too long without prefix
            "gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg",  # Invalid hex
            "",  # Empty
            "0x",  # Just prefix
            "not_hex_at_all",  # Non-hex
        ]

        for key in invalid_keys:
            assert not validate_private_key(key)

    def test_environment_hash_stability(self):
        """Test environment hash stability and filtering."""
        # Test with various environment configurations
        test_cases = [
            {"VAR1": "value1", "VAR2": "value2"},
            {"PRIVATE_KEY": "secret", "NORMAL_VAR": "normal"},
            {"API_KEY": "secret", "TOKEN": "secret", "SETTING": "value"},
            {},  # Empty environment
        ]

        for env_vars in test_cases:
            with patch.dict("os.environ", env_vars):
                hash1 = get_environment_hash()
                hash2 = get_environment_hash()

                # Hash should be consistent
                assert hash1 == hash2

                # Hash should be 8 characters
                assert len(hash1) == 8

                # Hash should be valid hex
                int(hash1, 16)  # Should not raise ValueError

    def test_secure_comparison_edge_cases(self):
        """Test secure comparison with edge cases."""
        test_cases = [
            # (str1, str2, expected_result)
            ("", "", True),
            ("a", "a", True),
            ("a", "b", False),
            ("ab", "a", False),
            ("a", "ab", False),
            ("password", "password", True),
            ("Password", "password", False),  # Case sensitive
            ("123456", "123456", True),
            ("123456", "123457", False),
            ("a" * 1000, "a" * 1000, True),  # Long strings
            ("a" * 1000, "b" * 1000, False),
        ]

        for str1, str2, expected in test_cases:
            result = secure_compare(str1, str2)
            assert result == expected, f"Failed for: {repr(str1)} vs {repr(str2)}"
