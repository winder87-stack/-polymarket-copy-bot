"""
Unit tests for utils/helpers.py - Utility functions.
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from decimal import Decimal

from utils.helpers import (
    normalize_address,
    wei_to_usdc,
    usdc_to_wei,
    calculate_confidence_score,
    calculate_position_size,
    format_currency,
    get_time_ago,
    truncate_string,
    safe_json_parse,
    get_environment_info,
    generate_environment_hash,
    retry_with_backoff
)


class TestNormalizeAddress:
    """Test address normalization."""

    def test_normalize_address_with_prefix(self):
        """Test normalizing address that already has 0x prefix."""
        address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"

        result = normalize_address(address)

        assert result == address.lower()

    def test_normalize_address_without_prefix(self):
        """Test normalizing address without 0x prefix."""
        address = "742d35Cc6634C0532925a3b844Bc454e4438f44e"

        result = normalize_address(address)

        assert result == "0x742d35Cc6634C0532925a3b844Bc454e4438f44e".lower()

    def test_normalize_address_uppercase(self):
        """Test normalizing uppercase address."""
        address = "0x742D35CC6634C0532925A3B844BC454E4438F44E"

        result = normalize_address(address)

        assert result == address.lower()

    def test_normalize_address_invalid_length(self):
        """Test normalizing address with invalid length."""
        address = "0x742d35Cc6634C0532925a3b844Bc454e"  # Too short

        result = normalize_address(address)

        # Should still return with 0x prefix but mark as invalid in logs
        assert result == "0x742d35Cc6634C0532925a3b844Bc454e"

    def test_normalize_address_none(self):
        """Test normalizing None address."""
        result = normalize_address(None)

        assert result == ""

    def test_normalize_address_empty_string(self):
        """Test normalizing empty string."""
        result = normalize_address("")

        assert result == ""


class TestCurrencyConversion:
    """Test currency conversion functions."""

    def test_wei_to_usdc_integer(self):
        """Test converting wei to USDC with integer input."""
        wei_amount = 1000000  # 1 USDC in wei

        result = wei_to_usdc(wei_amount)

        assert result == 1.0

    def test_wei_to_usdc_float(self):
        """Test converting wei to USDC with float input."""
        wei_amount = 1500000.0  # 1.5 USDC in wei

        result = wei_to_usdc(wei_amount)

        assert result == 1.5

    def test_wei_to_usdc_string(self):
        """Test converting wei to USDC with string input."""
        wei_amount = "2000000"

        result = wei_to_usdc(wei_amount)

        assert result == 2.0

    def test_wei_to_usdc_large_number(self):
        """Test converting large wei amount to USDC."""
        wei_amount = 1000000000000  # 1,000,000 USDC

        result = wei_to_usdc(wei_amount)

        assert result == 1000000.0

    def test_wei_to_usdc_zero(self):
        """Test converting zero wei to USDC."""
        result = wei_to_usdc(0)

        assert result == 0.0

    def test_wei_to_usdc_invalid_input(self):
        """Test converting invalid input to USDC."""
        result = wei_to_usdc("invalid")

        assert result == 0.0

    def test_usdc_to_wei_integer(self):
        """Test converting USDC to wei with integer input."""
        usdc_amount = 1

        result = usdc_to_wei(usdc_amount)

        assert result == 1000000

    def test_usdc_to_wei_float(self):
        """Test converting USDC to wei with float input."""
        usdc_amount = 1.5

        result = usdc_to_wei(usdc_amount)

        assert result == 1500000

    def test_usdc_to_wei_string(self):
        """Test converting USDC to wei with string input."""
        usdc_amount = "2.5"

        result = usdc_to_wei(usdc_amount)

        assert result == 2500000

    def test_usdc_to_wei_precision(self):
        """Test USDC to wei conversion precision."""
        usdc_amount = 0.123456

        result = usdc_to_wei(usdc_amount)

        assert result == 123456

    def test_usdc_to_wei_zero(self):
        """Test converting zero USDC to wei."""
        result = usdc_to_wei(0)

        assert result == 0

    def test_usdc_to_wei_invalid_input(self):
        """Test converting invalid USDC input to wei."""
        result = usdc_to_wei("invalid")

        assert result == 0


class TestCalculateConfidenceScore:
    """Test confidence score calculation."""

    def test_calculate_confidence_score_high_value(self):
        """Test confidence score with high transaction value."""
        tx = {
            'value': '1000000000000000000',  # 1 ETH
            'gasUsed': '50000',
            'input': '0x1234567890abcdef'
        }

        result = calculate_confidence_score(tx)

        assert result > 0.5  # Should be reasonably high

    def test_calculate_confidence_score_contract_interaction(self):
        """Test confidence score for contract interaction."""
        tx = {
            'value': '0',
            'gasUsed': '150000',
            'input': '0xa9059cbb000000000000000000000000742d35Cc6634C0532925a3b844Bc454e4438f44e00000000000000000000000000000000000000000000000000000000000003e8'
        }

        result = calculate_confidence_score(tx)

        assert result > 0.4  # Should be higher due to input data

    def test_calculate_confidence_score_gas_usage(self):
        """Test confidence score based on gas usage."""
        tx = {
            'value': '0',
            'gasUsed': '75000',  # Medium gas usage
            'input': '0x'
        }

        result = calculate_confidence_score(tx)

        assert 0.2 < result < 0.4

    def test_calculate_confidence_score_input_length(self):
        """Test confidence score based on input data length."""
        tx = {
            'value': '0',
            'gasUsed': '21000',
            'input': '0x' + 'a' * 200  # Long input data
        }

        result = calculate_confidence_score(tx)

        assert result > 0.3

    def test_calculate_confidence_score_with_patterns(self):
        """Test confidence score with pattern matching."""
        tx = {
            'value': '0',
            'gasUsed': '21000',
            'input': '0x12345678sellShares00000000000000000000000000000000000000000000000000000000'
        }

        patterns = ['sellShares', 'buyShares']
        result = calculate_confidence_score(tx, patterns)

        assert result > 0.4  # Should get pattern bonus

    def test_calculate_confidence_score_minimum(self):
        """Test minimum confidence score."""
        tx = {
            'value': '0',
            'gasUsed': '21000',
            'input': '0x'
        }

        result = calculate_confidence_score(tx)

        assert result >= 0.3  # Base score

    def test_calculate_confidence_score_maximum(self):
        """Test that confidence score is capped at 1.0."""
        tx = {
            'value': '1000000000000000000000',  # Very high value
            'gasUsed': '1000000',  # Very high gas
            'input': '0x' + 'a' * 1000  # Very long input
        }

        patterns = ['sellShares', 'buyShares', 'transferPosition']
        result = calculate_confidence_score(tx, patterns)

        assert result <= 1.0


class TestCalculatePositionSize:
    """Test position size calculation."""

    def test_calculate_position_size_normal_case(self):
        """Test normal position size calculation."""
        result = calculate_position_size(
            original_amount=100.0,
            account_balance=1000.0,
            max_position_size=50.0,
            risk_percentage=0.01
        )

        # Should be min of: risk_based (10.0), proportional (10.0), max_size (50.0)
        assert result == 10.0

    def test_calculate_position_size_high_balance(self):
        """Test position size with high account balance."""
        result = calculate_position_size(
            original_amount=10.0,
            account_balance=10000.0,
            max_position_size=100.0,
            risk_percentage=0.01
        )

        # Risk based: 10000 * 0.01 = 100
        # Proportional: 10 * 0.1 = 1
        # Should choose minimum: 1.0
        assert result == 1.0

    def test_calculate_position_size_capped_by_max(self):
        """Test position size capped by maximum position size."""
        result = calculate_position_size(
            original_amount=1000.0,
            account_balance=10000.0,
            max_position_size=50.0,
            risk_percentage=0.02
        )

        # Risk based: 10000 * 0.02 = 200
        # Proportional: 1000 * 0.1 = 100
        # Should be capped at max_position_size: 50.0
        assert result == 50.0

    def test_calculate_position_size_minimum_amount(self):
        """Test position size meets minimum requirements."""
        result = calculate_position_size(
            original_amount=0.1,
            account_balance=100.0,
            max_position_size=100.0,
            risk_percentage=0.001
        )

        # Should be at least 1.0 (minimum trade amount)
        assert result >= 1.0

    def test_calculate_position_size_error_handling(self):
        """Test position size calculation error handling."""
        result = calculate_position_size(
            original_amount=-10.0,  # Invalid
            account_balance=1000.0,
            max_position_size=50.0
        )

        # Should fall back to safe calculation
        assert isinstance(result, float)
        assert result > 0


class TestFormatCurrency:
    """Test currency formatting."""

    def test_format_currency_large_number(self):
        """Test formatting large currency amounts."""
        result = format_currency(1234.56)

        assert result == "$1,234.56"

    def test_format_currency_medium_number(self):
        """Test formatting medium currency amounts."""
        result = format_currency(123.456)

        assert result == "$123.46"

    def test_format_currency_small_number(self):
        """Test formatting small currency amounts."""
        result = format_currency(0.123456)

        assert result == "$0.1235"

    def test_format_currency_very_small_number(self):
        """Test formatting very small currency amounts."""
        result = format_currency(0.001234)

        assert result == "$0.0012"

    def test_format_currency_negative_number(self):
        """Test formatting negative currency amounts."""
        result = format_currency(-123.45)

        assert result == "-$123.45"

    def test_format_currency_zero(self):
        """Test formatting zero."""
        result = format_currency(0.0)

        assert result == "$0.00"


class TestGetTimeAgo:
    """Test time ago calculation."""

    def test_get_time_ago_seconds(self):
        """Test time ago for seconds."""
        past_time = datetime.now() - timedelta(seconds=30)

        result = get_time_ago(past_time)

        assert "30 seconds ago" in result

    def test_get_time_ago_minutes(self):
        """Test time ago for minutes."""
        past_time = datetime.now() - timedelta(minutes=5)

        result = get_time_ago(past_time)

        assert "5 minutes ago" in result

    def test_get_time_ago_hours(self):
        """Test time ago for hours."""
        past_time = datetime.now() - timedelta(hours=2)

        result = get_time_ago(past_time)

        assert "2 hours ago" in result

    def test_get_time_ago_days(self):
        """Test time ago for days."""
        past_time = datetime.now() - timedelta(days=3)

        result = get_time_ago(past_time)

        assert "3 days ago" in result

    def test_get_time_ago_months(self):
        """Test time ago for months."""
        past_time = datetime.now() - timedelta(days=60)

        result = get_time_ago(past_time)

        assert "2 months ago" in result

    def test_get_time_ago_years(self):
        """Test time ago for years."""
        past_time = datetime.now() - timedelta(days=400)

        result = get_time_ago(past_time)

        assert "1 year ago" in result

    def test_get_time_ago_future(self):
        """Test time ago for future dates."""
        future_time = datetime.now() + timedelta(hours=1)

        result = get_time_ago(future_time)

        # Should handle future dates gracefully
        assert isinstance(result, str)


class TestTruncateString:
    """Test string truncation."""

    def test_truncate_string_short(self):
        """Test truncating short string."""
        result = truncate_string("short string", 20)

        assert result == "short string"

    def test_truncate_string_long(self):
        """Test truncating long string."""
        long_string = "this is a very long string that should be truncated"
        result = truncate_string(long_string, 20)

        assert result == "this is a very lo..."
        assert len(result) == 23  # 20 + 3 for "..."

    def test_truncate_string_exact_length(self):
        """Test truncating string at exact length."""
        exact_string = "exactly twenty chars"
        result = truncate_string(exact_string, 20)

        assert result == exact_string

    def test_truncate_string_none(self):
        """Test truncating None."""
        result = truncate_string(None, 20)

        assert result == ""

    def test_truncate_string_empty(self):
        """Test truncating empty string."""
        result = truncate_string("", 20)

        assert result == ""


class TestSafeJsonParse:
    """Test safe JSON parsing."""

    def test_safe_json_parse_valid_json(self):
        """Test parsing valid JSON string."""
        json_str = '{"key": "value", "number": 123}'

        result = safe_json_parse(json_str)

        assert result == {"key": "value", "number": 123}

    def test_safe_json_parse_invalid_json(self):
        """Test parsing invalid JSON string."""
        json_str = '{"key": "value", "number": 123'  # Missing closing brace

        result = safe_json_parse(json_str)

        assert result is None

    def test_safe_json_parse_empty_string(self):
        """Test parsing empty string."""
        result = safe_json_parse("")

        assert result is None

    def test_safe_json_parse_none(self):
        """Test parsing None."""
        result = safe_json_parse(None)

        assert result is None

    def test_safe_json_parse_complex_json(self):
        """Test parsing complex JSON structure."""
        complex_json = {
            "trades": [
                {"id": 1, "amount": 100.0},
                {"id": 2, "amount": 200.0}
            ],
            "metadata": {
                "timestamp": "2024-01-01T00:00:00Z",
                "version": "1.0"
            }
        }
        json_str = json.dumps(complex_json)

        result = safe_json_parse(json_str)

        assert result == complex_json


class TestGetEnvironmentInfo:
    """Test environment info collection."""

    @patch('platform.system')
    @patch('platform.platform')
    @patch('platform.machine')
    @patch('platform.processor')
    @patch('sys.version')
    def test_get_environment_info(self, mock_version, mock_processor, mock_machine, mock_platform, mock_system):
        """Test environment info collection."""
        mock_system.return_value = "Linux"
        mock_platform.return_value = "Linux-5.4.0-74-generic-x86_64-with-Ubuntu-20.04.3-LTS"
        mock_machine.return_value = "x86_64"
        mock_processor.return_value = "x86_64"
        mock_version.return_value = "3.9.7 (default, Sep 10 2021, 14:59:43) [GCC 9.3.0]"

        result = get_environment_info()

        assert result['system'] == "Linux"
        assert result['platform'] == "Linux-5.4.0-74-generic-x86_64-with-Ubuntu-20.04.3-LTS"
        assert result['machine'] == "x86_64"
        assert result['processor'] == "x86_64"
        assert "3.9.7" in result['python_version']
        assert 'timestamp' in result
        assert 'environment_hash' in result
        assert len(result['environment_hash']) == 8


class TestGenerateEnvironmentHash:
    """Test environment hash generation."""

    def test_generate_environment_hash(self):
        """Test environment hash generation."""
        with patch.dict('os.environ', {'VAR1': 'value1', 'VAR2': 'value2'}):
            result = generate_environment_hash()

            assert len(result) == 8
            assert isinstance(result, str)
            # Should be valid hex
            int(result, 16)

    def test_generate_environment_hash_empty(self):
        """Test environment hash with empty environment."""
        with patch.dict('os.environ', {}, clear=True):
            result = generate_environment_hash()

            assert len(result) == 8

    def test_generate_environment_hash_consistency(self):
        """Test that environment hash is consistent."""
        env_vars = {'TEST_VAR': 'test_value', 'ANOTHER_VAR': 'another_value'}

        with patch.dict('os.environ', env_vars):
            hash1 = generate_environment_hash()
            hash2 = generate_environment_hash()

            assert hash1 == hash2


class TestRetryWithBackoff:
    """Test retry decorator."""

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success_first_try(self):
        """Test retry decorator when function succeeds on first try."""
        call_count = 0

        @retry_with_backoff(max_attempts=3)
        async def test_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await test_function()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success_after_retries(self):
        """Test retry decorator when function succeeds after retries."""
        call_count = 0

        @retry_with_backoff(max_attempts=3)
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await test_function()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_backoff_exhaust_retries(self):
        """Test retry decorator when all retries are exhausted."""
        call_count = 0

        @retry_with_backoff(max_attempts=3)
        async def test_function():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent failure")

        with pytest.raises(ConnectionError):
            await test_function()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_backoff_returns_none_on_failure(self):
        """Test retry decorator returns None when function fails."""
        @retry_with_backoff(max_attempts=2)
        async def test_function():
            raise Exception("Failure")

        result = await test_function()

        assert result is None


class TestHelpersIntegration:
    """Integration tests for helper functions."""

    def test_currency_conversion_round_trip(self):
        """Test that currency conversion is reversible."""
        original_usdc = 123.456789

        # Convert USDC to wei
        wei_amount = usdc_to_wei(original_usdc)

        # Convert back to USDC
        back_to_usdc = wei_to_usdc(wei_amount)

        assert abs(back_to_usdc - original_usdc) < 0.000001  # Account for precision loss

    def test_address_normalization_consistency(self):
        """Test that address normalization is consistent."""
        addresses = [
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "0x742D35CC6634C0532925A3B844BC454E4438F44E"
        ]

        normalized = [normalize_address(addr) for addr in addresses]

        # All should be the same
        assert all(addr == normalized[0] for addr in normalized)
        assert normalized[0] == "0x742d35cc6634c0532925a3b844bc454e4438f44e"

    def test_confidence_scoring_realistic_transaction(self):
        """Test confidence scoring with realistic transaction data."""
        # Realistic Polymarket trade transaction
        tx = {
            'value': '0',
            'gasUsed': '125000',
            'input': '0x12345678000000000000000000000000742d35Cc6634C0532925a3b844Bc454e4438f44e00000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001'
        }

        score = calculate_confidence_score(tx)

        # Should be reasonably high due to gas usage and input data
        assert score > 0.5

    def test_position_sizing_realistic_scenario(self):
        """Test position sizing in realistic trading scenario."""
        # Trader with $10,000 balance, wants to risk 1% per trade
        # Original trade was $500, max position $200

        position = calculate_position_size(
            original_amount=500.0,
            account_balance=10000.0,
            max_position_size=200.0,
            risk_percentage=0.01
        )

        # Risk-based: 10000 * 0.01 = $100
        # Proportional: 500 * 0.1 = $50
        # Max size: $200
        # Should choose minimum: $50
        assert position == 50.0

    def test_time_formatting_realistic_scenarios(self):
        """Test time formatting in realistic scenarios."""
        now = datetime.now()

        test_cases = [
            (now - timedelta(seconds=30), "seconds ago"),
            (now - timedelta(minutes=5), "minutes ago"),
            (now - timedelta(hours=2), "hours ago"),
            (now - timedelta(days=1), "day ago"),
            (now - timedelta(days=30), "month ago"),
            (now - timedelta(days=365), "year ago"),
        ]

        for past_time, expected_unit in test_cases:
            result = get_time_ago(past_time)
            assert expected_unit in result

    def test_json_parsing_error_handling(self):
        """Test JSON parsing error handling."""
        invalid_cases = [
            "{invalid json",
            '{"key": "value"',  # Missing closing brace
            '["incomplete array"',  # Missing closing bracket
            '{"key": undefined}',  # Invalid value
            None,
            "",
        ]

        for invalid_json in invalid_cases:
            result = safe_json_parse(invalid_json)
            assert result is None

    def test_string_truncation_edge_cases(self):
        """Test string truncation edge cases."""
        test_cases = [
            ("", 10, ""),
            ("short", 10, "short"),
            ("exactly ten chars", 16, "exactly ten chars"),
            ("this is a very long string that exceeds the limit", 20, "this is a very lo..."),
            (None, 10, ""),
        ]

        for input_str, max_len, expected in test_cases:
            result = truncate_string(input_str, max_len)
            assert result == expected
