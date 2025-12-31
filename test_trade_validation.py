#!/usr/bin/env python3
"""Basic test runner for trade validation tests"""

import sys
from datetime import datetime, timedelta


def mock_approx(value, rel=0.1):
    """Simple approximation check"""

    def check(expected):
        return abs(value - expected) / max(abs(value), abs(expected)) <= rel

    return check


class MockTradeValidator:
    """Mock trade validator for testing"""

    def _validate_trade(self, trade):
        """Simplified trade validation logic"""
        if not trade:
            return False

        # Check required fields
        required_fields = [
            "tx_hash",
            "timestamp",
            "wallet_address",
            "condition_id",
            "side",
            "amount",
            "price",
        ]
        for field in required_fields:
            if field not in trade:
                return False

        # Validate data types
        if not isinstance(trade["tx_hash"], str) or not trade["tx_hash"].startswith(
            "0x"
        ):
            return False

        if not isinstance(trade["timestamp"], datetime):
            return False

        if not isinstance(trade["wallet_address"], str) or not trade[
            "wallet_address"
        ].startswith("0x"):
            return False

        if not isinstance(trade["condition_id"], str) or not trade[
            "condition_id"
        ].startswith("0x"):
            return False

        if trade["side"] not in ["BUY", "SELL"]:
            return False

        if not isinstance(trade["amount"], (int, float)) or trade["amount"] <= 0:
            return False

        if not isinstance(trade["price"], (int, float)) or trade["price"] <= 0:
            return False

        # Check timestamp is not in future and not too old
        now = datetime.now()
        if trade["timestamp"] > now + timedelta(
            minutes=1
        ):  # Allow 1 minute future tolerance
            return False

        if trade["timestamp"] < now - timedelta(hours=24):  # Max 24 hours old
            return False

        # Check confidence score if provided
        if "confidence_score" in trade:
            confidence = trade["confidence_score"]
            if (
                not isinstance(confidence, (int, float))
                or confidence < 0
                or confidence > 1
            ):
                return False

        return True


def test_valid_trade():
    """Test that valid trade passes validation"""
    validator = MockTradeValidator()

    valid_trade = {
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

    result = validator._validate_trade(valid_trade)
    assert result is True, "Valid trade should pass validation"
    print("✅ Valid trade test passed")


def test_missing_required_fields():
    """Test rejection when required fields are missing"""
    validator = MockTradeValidator()

    # Test missing each required field
    valid_trade = {
        "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "timestamp": datetime.now(),
        "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
        "side": "BUY",
        "amount": 100.0,
        "price": 0.5,
    }

    required_fields = [
        "tx_hash",
        "timestamp",
        "wallet_address",
        "condition_id",
        "side",
        "amount",
        "price",
    ]

    for field in required_fields:
        test_trade = valid_trade.copy()
        del test_trade[field]

        result = validator._validate_trade(test_trade)
        assert result is False, f"Trade missing {field} should be rejected"

    print("✅ Missing required fields test passed")


def test_invalid_data_types():
    """Test rejection with invalid data types"""
    validator = MockTradeValidator()

    valid_trade = {
        "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "timestamp": datetime.now(),
        "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
        "side": "BUY",
        "amount": 100.0,
        "price": 0.5,
    }

    # Test invalid tx_hash
    test_trade = valid_trade.copy()
    test_trade["tx_hash"] = 123456789
    result = validator._validate_trade(test_trade)
    assert result is False, "Invalid tx_hash type should be rejected"

    # Test invalid side
    test_trade = valid_trade.copy()
    test_trade["side"] = "HOLD"
    result = validator._validate_trade(test_trade)
    assert result is False, "Invalid side should be rejected"

    print("✅ Invalid data types test passed")


def test_invalid_values():
    """Test rejection with invalid values"""
    validator = MockTradeValidator()

    valid_trade = {
        "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "timestamp": datetime.now(),
        "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
        "side": "BUY",
        "amount": 100.0,
        "price": 0.5,
    }

    # Test zero amount
    test_trade = valid_trade.copy()
    test_trade["amount"] = 0.0
    result = validator._validate_trade(test_trade)
    assert result is False, "Zero amount should be rejected"

    # Test negative price
    test_trade = valid_trade.copy()
    test_trade["price"] = -0.5
    result = validator._validate_trade(test_trade)
    assert result is False, "Negative price should be rejected"

    # Test future timestamp
    test_trade = valid_trade.copy()
    test_trade["timestamp"] = datetime.now() + timedelta(hours=2)
    result = validator._validate_trade(test_trade)
    assert result is False, "Future timestamp should be rejected"

    # Test too old timestamp
    test_trade = valid_trade.copy()
    test_trade["timestamp"] = datetime.now() - timedelta(hours=25)
    result = validator._validate_trade(test_trade)
    assert result is False, "Too old timestamp should be rejected"

    print("✅ Invalid values test passed")


def test_confidence_score_validation():
    """Test confidence score validation"""
    validator = MockTradeValidator()

    valid_trade = {
        "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "timestamp": datetime.now(),
        "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
        "side": "BUY",
        "amount": 100.0,
        "price": 0.5,
        "confidence_score": 0.8,
    }

    # Test valid confidence scores
    for score in [0.0, 0.5, 1.0]:
        test_trade = valid_trade.copy()
        test_trade["confidence_score"] = score
        result = validator._validate_trade(test_trade)
        assert result is True, f"Valid confidence score {score} should pass"

    # Test invalid confidence scores
    for score in [-0.1, 1.1, "0.8"]:
        test_trade = valid_trade.copy()
        test_trade["confidence_score"] = score
        result = validator._validate_trade(test_trade)
        assert result is False, f"Invalid confidence score {score} should be rejected"

    print("✅ Confidence score validation test passed")


def test_empty_trade():
    """Test rejection of empty trade"""
    validator = MockTradeValidator()

    result = validator._validate_trade({})
    assert result is False, "Empty trade should be rejected"

    result = validator._validate_trade(None)
    assert result is False, "None trade should be rejected"

    print("✅ Empty trade test passed")


if __name__ == "__main__":
    print("🧪 Running trade validation tests...")

    try:
        test_valid_trade()
        test_missing_required_fields()
        test_invalid_data_types()
        test_invalid_values()
        test_confidence_score_validation()
        test_empty_trade()

        print("\n🎉 All trade validation tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
