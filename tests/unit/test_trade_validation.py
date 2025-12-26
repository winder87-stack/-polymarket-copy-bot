"""
Unit tests for trade validation - test all rejection conditions

Tests cover:
- Missing required fields validation
- Invalid field types validation
- Price validation (zero, negative)
- Amount validation (zero, negative)
- Wallet address validation
- Condition ID validation
- Timestamp validation (future, too old)
- Confidence score validation
- Side validation (BUY/SELL only)
- Integration with risk management
- Edge cases and boundary conditions
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from config.settings import Settings
from core.trade_executor import TradeExecutor


@pytest.fixture
def mock_clob_client():
    """Create a mock CLOB client for testing"""
    mock_client = MagicMock()
    mock_client.wallet_address = "0x1234567890abcdef1234567890abcdef12345678"
    return mock_client


@pytest.fixture
def trade_validator(mock_clob_client):
    """Setup trade executor with mocked dependencies for validation testing"""
    executor = TradeExecutor(mock_clob_client)
    executor.settings = Settings()
    return executor


@pytest.fixture
def valid_trade():
    """Create a valid trade for testing"""
    return {
        "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "timestamp": datetime.now(),
        "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
        "side": "BUY",
        "amount": 100.0,
        "price": 0.5,
        "token_id": "0xabcdef1234567890abcdef1234567890abcdef12",
        "confidence_score": 0.8,
    }


class TestTradeValidationFields:
    """Test trade validation for required fields and data types"""

    def test_valid_trade_passes_validation(self, trade_validator, valid_trade):
        """Test that a completely valid trade passes validation"""
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True

    def test_missing_tx_hash_rejects(self, trade_validator, valid_trade):
        """Test rejection when tx_hash is missing"""
        del valid_trade["tx_hash"]
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_missing_timestamp_rejects(self, trade_validator, valid_trade):
        """Test rejection when timestamp is missing"""
        del valid_trade["timestamp"]
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_missing_wallet_address_rejects(self, trade_validator, valid_trade):
        """Test rejection when wallet_address is missing"""
        del valid_trade["wallet_address"]
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_missing_condition_id_rejects(self, trade_validator, valid_trade):
        """Test rejection when condition_id is missing"""
        del valid_trade["condition_id"]
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_missing_side_rejects(self, trade_validator, valid_trade):
        """Test rejection when side is missing"""
        del valid_trade["side"]
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_missing_amount_rejects(self, trade_validator, valid_trade):
        """Test rejection when amount is missing"""
        del valid_trade["amount"]
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_missing_price_rejects(self, trade_validator, valid_trade):
        """Test rejection when price is missing"""
        del valid_trade["price"]
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False


class TestTradeValidationDataTypes:
    """Test trade validation for correct data types"""

    def test_invalid_tx_hash_type_rejects(self, trade_validator, valid_trade):
        """Test rejection when tx_hash is not string"""
        valid_trade["tx_hash"] = 123456789
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_timestamp_type_rejects(self, trade_validator, valid_trade):
        """Test rejection when timestamp is not datetime"""
        valid_trade["timestamp"] = "2024-01-01T00:00:00Z"
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_wallet_address_type_rejects(self, trade_validator, valid_trade):
        """Test rejection when wallet_address is not string"""
        valid_trade["wallet_address"] = 123456789
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_condition_id_type_rejects(self, trade_validator, valid_trade):
        """Test rejection when condition_id is not string"""
        valid_trade["condition_id"] = 123456789
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_side_type_rejects(self, trade_validator, valid_trade):
        """Test rejection when side is not string"""
        valid_trade["side"] = 123
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_amount_type_rejects(self, trade_validator, valid_trade):
        """Test rejection when amount is not number"""
        valid_trade["amount"] = "100.0"
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_price_type_rejects(self, trade_validator, valid_trade):
        """Test rejection when price is not number"""
        valid_trade["price"] = "0.5"
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_confidence_score_type_rejects(self, trade_validator, valid_trade):
        """Test rejection when confidence_score is not number"""
        valid_trade["confidence_score"] = "0.8"
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False


class TestTradeValidationValues:
    """Test trade validation for valid value ranges"""

    def test_zero_amount_rejects(self, trade_validator, valid_trade):
        """Test rejection when amount is zero"""
        valid_trade["amount"] = 0.0
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_negative_amount_rejects(self, trade_validator, valid_trade):
        """Test rejection when amount is negative"""
        valid_trade["amount"] = -100.0
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_zero_price_rejects(self, trade_validator, valid_trade):
        """Test rejection when price is zero"""
        valid_trade["price"] = 0.0
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_negative_price_rejects(self, trade_validator, valid_trade):
        """Test rejection when price is negative"""
        valid_trade["price"] = -0.5
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_side_value_rejects(self, trade_validator, valid_trade):
        """Test rejection when side is not BUY or SELL"""
        valid_trade["side"] = "HOLD"
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

        valid_trade["side"] = "buy"  # lowercase
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_negative_confidence_score_rejects(self, trade_validator, valid_trade):
        """Test rejection when confidence_score is negative"""
        valid_trade["confidence_score"] = -0.1
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_confidence_score_over_one_rejects(self, trade_validator, valid_trade):
        """Test rejection when confidence_score is over 1.0"""
        valid_trade["confidence_score"] = 1.1
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_future_timestamp_rejects(self, trade_validator, valid_trade):
        """Test rejection when timestamp is in the future"""
        valid_trade["timestamp"] = datetime.now() + timedelta(hours=1)
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_too_old_timestamp_rejects(self, trade_validator, valid_trade):
        """Test rejection when timestamp is too old"""
        valid_trade["timestamp"] = datetime.now() - timedelta(days=2)
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_wallet_address_format_rejects(self, trade_validator, valid_trade):
        """Test rejection when wallet_address format is invalid"""
        valid_trade["wallet_address"] = "invalid_address"
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

        valid_trade["wallet_address"] = "0x123"  # too short
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_condition_id_format_rejects(self, trade_validator, valid_trade):
        """Test rejection when condition_id format is invalid"""
        valid_trade["condition_id"] = "invalid_condition"
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_invalid_tx_hash_format_rejects(self, trade_validator, valid_trade):
        """Test rejection when tx_hash format is invalid"""
        valid_trade["tx_hash"] = "invalid_hash"
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

        valid_trade["tx_hash"] = "0x123"  # too short
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False


class TestTradeValidationBoundaries:
    """Test trade validation boundary conditions"""

    def test_minimum_valid_amount(self, trade_validator, valid_trade):
        """Test minimum valid amount"""
        valid_trade["amount"] = 0.000001  # Very small but positive
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True

    def test_maximum_valid_amount(self, trade_validator, valid_trade):
        """Test maximum valid amount"""
        valid_trade["amount"] = 1000000.0  # Large amount
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True

    def test_minimum_valid_price(self, trade_validator, valid_trade):
        """Test minimum valid price"""
        valid_trade["price"] = 0.000001  # Very small but positive
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True

    def test_maximum_valid_price(self, trade_validator, valid_trade):
        """Test maximum valid price"""
        valid_trade["price"] = 1000000.0  # Very large price
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True

    def test_zero_confidence_score_accepts(self, trade_validator, valid_trade):
        """Test that zero confidence score is accepted"""
        valid_trade["confidence_score"] = 0.0
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True

    def test_one_confidence_score_accepts(self, trade_validator, valid_trade):
        """Test that confidence score of 1.0 is accepted"""
        valid_trade["confidence_score"] = 1.0
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True

    def test_recent_timestamp_accepts(self, trade_validator, valid_trade):
        """Test that recent timestamp is accepted"""
        valid_trade["timestamp"] = datetime.now() - timedelta(minutes=30)
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True

    def test_max_age_timestamp_accepts(self, trade_validator, valid_trade):
        """Test that maximum age timestamp is accepted"""
        valid_trade["timestamp"] = datetime.now() - timedelta(hours=23, minutes=59)
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True


class TestTradeValidationIntegration:
    """Test trade validation integration with other systems"""

    @pytest.mark.asyncio
    async def test_validation_with_risk_management(self, trade_validator, valid_trade):
        """Test that validation integrates properly with risk management"""
        # Mock successful validation
        with patch.object(trade_validator, '_validate_trade', return_value=True):
            result = await trade_validator.execute_copy_trade(valid_trade)

            # Should not be rejected for validation reasons
            assert result["status"] != "rejected"
            assert "validation_error" not in result.get("reason", "")

    @pytest.mark.asyncio
    async def test_validation_failure_blocks_trade(self, trade_validator, valid_trade):
        """Test that validation failure blocks trade execution"""
        # Mock validation failure
        with patch.object(trade_validator, '_validate_trade', return_value=False):
            result = await trade_validator.execute_copy_trade(valid_trade)

            # Should be rejected due to validation
            assert result["status"] == "rejected"
            assert "validation" in result.get("reason", "").lower()

    def test_validation_error_logging(self, trade_validator, valid_trade, caplog):
        """Test that validation errors are properly logged"""
        invalid_trade = valid_trade.copy()
        invalid_trade["amount"] = -100.0  # Invalid amount

        with caplog.at_level("ERROR"):
            trade_validator._validate_trade(invalid_trade)

        assert "validation error" in caplog.text.lower() or "invalid" in caplog.text.lower()

    def test_validation_with_missing_optional_fields(self, trade_validator, valid_trade):
        """Test validation with missing optional fields"""
        # Remove optional fields
        optional_fields = ["token_id", "confidence_score"]
        for field in optional_fields:
            if field in valid_trade:
                del valid_trade[field]

        # Should still pass validation (these are optional)
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True


class TestTradeValidationEdgeCases:
    """Test trade validation edge cases"""

    def test_empty_trade_rejects(self, trade_validator):
        """Test rejection of empty trade dictionary"""
        is_valid = trade_validator._validate_trade({})
        assert is_valid is False

    def test_none_trade_rejects(self, trade_validator):
        """Test rejection of None trade"""
        is_valid = trade_validator._validate_trade(None)
        assert is_valid is False

    def test_extra_fields_accepted(self, trade_validator, valid_trade):
        """Test that extra fields are accepted"""
        valid_trade["extra_field"] = "extra_value"
        valid_trade["another_field"] = 123

        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True

    def test_unicode_characters_in_strings(self, trade_validator, valid_trade):
        """Test handling of unicode characters in string fields"""
        valid_trade["tx_hash"] = "0x1234567890abcdefñçüabcdef1234567890abcdef"  # Unicode in hash
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False  # Invalid characters in hash

    def test_very_long_strings(self, trade_validator, valid_trade):
        """Test handling of very long strings"""
        long_string = "0x" + "a" * 1000  # Very long hash
        valid_trade["tx_hash"] = long_string
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False  # Invalid length

    def test_special_characters_in_wallet_address(self, trade_validator, valid_trade):
        """Test wallet address with special characters"""
        valid_trade["wallet_address"] = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e!"  # Special char
        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_scientific_notation_numbers(self, trade_validator, valid_trade):
        """Test numbers in scientific notation"""
        valid_trade["amount"] = 1e-6  # Very small number in scientific notation
        valid_trade["price"] = 1e6    # Very large number in scientific notation

        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is True

    def test_boolean_values_for_numeric_fields(self, trade_validator, valid_trade):
        """Test boolean values where numbers are expected"""
        valid_trade["amount"] = True
        valid_trade["price"] = False

        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False

    def test_list_values_for_string_fields(self, trade_validator, valid_trade):
        """Test list values where strings are expected"""
        valid_trade["tx_hash"] = ["0x123"]
        valid_trade["wallet_address"] = ["0x456"]

        is_valid = trade_validator._validate_trade(valid_trade)
        assert is_valid is False
