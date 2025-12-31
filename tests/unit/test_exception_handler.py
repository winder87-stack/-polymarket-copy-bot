"""
Test cases for exception handler module.

Tests cover:
- Exception classification
- Severity assignment
- Retry strategy determination
- Context-aware logging
- Main loop protection
"""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from core.exceptions import ConfigError, RateLimitError, TradingError, ValidationError
from utils.exception_handler import (
    ErrorSeverity,
    ExceptionHandler,
    RetryStrategy,
    safe_execute,
)


class TestExceptionHandler:
    """Test exception handler functionality"""

    def test_classify_network_error(self) -> None:
        """Test classification of network errors"""
        handler = ExceptionHandler()
        error = ConnectionError("Connection failed")
        severity, retry_strategy, category = handler.classify_exception(error)

        assert severity == ErrorSeverity.ERROR
        assert retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert category == "network"

    def test_classify_validation_error(self) -> None:
        """Test classification of validation errors"""
        handler = ExceptionHandler()
        error = ValidationError("Invalid input")
        severity, retry_strategy, category = handler.classify_exception(error)

        assert severity == ErrorSeverity.WARNING
        assert retry_strategy == RetryStrategy.NO_RETRY
        assert category == "validation"

    def test_classify_rate_limit_error(self) -> None:
        """Test classification of rate limit errors"""
        handler = ExceptionHandler()
        error = RateLimitError(retry_after=60, endpoint="/api/trades")
        severity, retry_strategy, category = handler.classify_exception(error)

        assert severity == ErrorSeverity.WARNING
        assert retry_strategy == RetryStrategy.RATE_LIMIT_DELAY
        assert category == "api"

    def test_classify_config_error(self) -> None:
        """Test classification of configuration errors"""
        handler = ExceptionHandler()
        error = ConfigError("Invalid configuration")
        severity, retry_strategy, category = handler.classify_exception(error)

        assert severity == ErrorSeverity.CRITICAL
        assert retry_strategy == RetryStrategy.NO_RETRY
        assert category == "configuration"

    def test_log_exception_with_context(self) -> None:
        """Test exception logging with context"""
        handler = ExceptionHandler()
        error = ValueError("Invalid value")

        with patch("utils.exception_handler.logger") as mock_logger:
            handler.log_exception(
                error,
                context={"key": "value"},
                component="TestComponent",
                operation="test_operation",
                include_stack_trace=False,
            )

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "TestComponent" in call_args[0][0]
            assert "test_operation" in call_args[0][0]

    def test_log_exception_critical(self) -> None:
        """Test critical exception logging"""
        handler = ExceptionHandler()
        error = Exception("Critical error")

        with patch("utils.exception_handler.logger") as mock_logger:
            handler.log_exception(
                error,
                component="TestComponent",
                operation="test_operation",
            )

            mock_logger.critical.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_exception_no_retry(self) -> None:
        """Test exception handling with no retry"""
        handler = ExceptionHandler()
        error = ValidationError("Invalid input")

        result = await handler.handle_exception(
            error,
            component="TestComponent",
            operation="test_operation",
            default_return="default",
        )

        assert result == "default"

    @pytest.mark.asyncio
    async def test_handle_exception_with_retry(self) -> None:
        """Test exception handling with retry"""
        handler = ExceptionHandler()
        error = ConnectionError("Connection failed")

        retry_callback = AsyncMock(return_value="success")

        result = await handler.handle_exception(
            error,
            component="TestComponent",
            operation="test_operation",
            default_return="default",
            retry_callback=retry_callback,
            max_retries=2,
        )

        # Should retry and succeed
        assert result == "success"
        assert retry_callback.call_count > 0

    @pytest.mark.asyncio
    async def test_handle_exception_retry_fails(self) -> None:
        """Test exception handling when retry fails"""
        handler = ExceptionHandler()
        error = ConnectionError("Connection failed")

        retry_callback = AsyncMock(side_effect=ConnectionError("Still failing"))

        result = await handler.handle_exception(
            error,
            component="TestComponent",
            operation="test_operation",
            default_return="default",
            retry_callback=retry_callback,
            max_retries=2,
        )

        # Should return default after retries fail
        assert result == "default"

    @pytest.mark.asyncio
    async def test_handle_exception_rate_limit(self) -> None:
        """Test exception handling for rate limit errors"""
        handler = ExceptionHandler()
        error = RateLimitError(retry_after=1, endpoint="/api/trades")

        retry_callback = AsyncMock(return_value="success")

        result = await handler.handle_exception(
            error,
            component="TestComponent",
            operation="test_operation",
            default_return="default",
            retry_callback=retry_callback,
            max_retries=1,
        )

        # Should wait and retry
        assert result == "success"
        assert retry_callback.call_count > 0

    def test_get_error_statistics(self) -> None:
        """Test error statistics retrieval"""
        handler = ExceptionHandler()

        # Log some errors
        handler.log_exception(
            ConnectionError("Error 1"), component="C1", operation="O1"
        )
        handler.log_exception(ValueError("Error 2"), component="C2", operation="O2")
        handler.log_exception(
            ConnectionError("Error 3"), component="C1", operation="O1"
        )

        stats = handler.get_error_statistics()

        assert stats["total_errors"] == 3
        assert "network:ConnectionError" in stats["error_counts"]
        assert stats["error_counts"]["network:ConnectionError"] == 2
        assert stats["error_counts"]["validation:ValueError"] == 1

    def test_should_alert(self) -> None:
        """Test alert determination"""
        handler = ExceptionHandler()

        # Critical errors should alert
        assert handler.should_alert(Exception("Critical")) is True

        # Error severity should alert
        assert handler.should_alert(ConnectionError("Network error")) is True

        # Warning severity should not alert
        assert handler.should_alert(ValidationError("Invalid")) is False


class TestSafeExecute:
    """Test safe_execute function"""

    @pytest.mark.asyncio
    async def test_safe_execute_success(self) -> None:
        """Test successful execution"""

        async def test_func(x: int, y: int) -> int:
            return x + y

        result = await safe_execute(
            test_func,
            1,
            2,
            component="Test",
            operation="add",
            default_return=0,
        )

        assert result == 3

    @pytest.mark.asyncio
    async def test_safe_execute_exception(self) -> None:
        """Test execution with exception"""

        async def test_func() -> int:
            raise ValueError("Test error")

        result = await safe_execute(
            test_func,
            component="Test",
            operation="test",
            default_return=42,
        )

        assert result == 42

    @pytest.mark.asyncio
    async def test_safe_execute_with_retry(self) -> None:
        """Test execution with retry"""
        call_count = 0

        async def test_func() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Retry needed")
            return 100

        result = await safe_execute(
            test_func,
            component="Test",
            operation="test",
            default_return=0,
            max_retries=3,
        )

        assert result == 100
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_safe_execute_sync_function(self) -> None:
        """Test execution of synchronous function"""

        def test_func(x: int) -> int:
            return x * 2

        result = await safe_execute(
            test_func,
            5,
            component="Test",
            operation="multiply",
            default_return=0,
        )

        assert result == 10

    @pytest.mark.asyncio
    async def test_safe_execute_main_loop_protection(self) -> None:
        """Test that exceptions don't crash the main loop"""

        async def failing_func() -> None:
            raise Exception("This should not crash")

        # Should not raise, should return default
        result = await safe_execute(
            failing_func,
            component="Test",
            operation="failing",
            default_return=None,
        )

        assert result is None


class TestExceptionScenarios:
    """Test specific exception scenarios"""

    @pytest.mark.asyncio
    async def test_network_error_scenario(self) -> None:
        """Test network error handling scenario"""
        handler = ExceptionHandler()

        error = aiohttp.ClientConnectionError("Connection refused")
        details = handler.log_exception(
            error,
            context={"endpoint": "/api/trades", "attempt": 1},
            component="APIClient",
            operation="fetch_trades",
        )

        assert details["error_category"] == "network"
        assert details["severity"] == "error"
        assert details["retry_strategy"] == "exponential_backoff"

    @pytest.mark.asyncio
    async def test_validation_error_scenario(self) -> None:
        """Test validation error handling scenario"""
        handler = ExceptionHandler()

        error = ValidationError("Invalid trade amount")
        details = handler.log_exception(
            error,
            context={"amount": -100, "wallet": "0x123..."},
            component="TradeExecutor",
            operation="validate_trade",
        )

        assert details["error_category"] == "validation"
        assert details["severity"] == "warning"
        assert details["retry_strategy"] == "no_retry"

    @pytest.mark.asyncio
    async def test_rate_limit_scenario(self) -> None:
        """Test rate limit error scenario"""
        handler = ExceptionHandler()

        error = RateLimitError(retry_after=60, endpoint="/api/transactions")
        details = handler.log_exception(
            error,
            context={"wallet": "0x123...", "api_key": "key123"},
            component="WalletMonitor",
            operation="get_transactions",
        )

        assert details["error_category"] == "api"
        assert details["severity"] == "warning"
        assert details["retry_strategy"] == "rate_limit_delay"

    @pytest.mark.asyncio
    async def test_trading_error_scenario(self) -> None:
        """Test trading error scenario"""
        handler = ExceptionHandler()

        error = TradingError("Insufficient balance")
        details = handler.log_exception(
            error,
            context={"required": 100, "available": 50},
            component="TradeExecutor",
            operation="execute_trade",
        )

        assert details["error_category"] == "trading"
        assert details["severity"] == "error"
        assert details["retry_strategy"] == "no_retry"

    @pytest.mark.asyncio
    async def test_config_error_scenario(self) -> None:
        """Test configuration error scenario"""
        handler = ExceptionHandler()

        error = ConfigError("Missing API key")
        details = handler.log_exception(
            error,
            context={"config_file": "settings.json"},
            component="ConfigManager",
            operation="load_config",
        )

        assert details["error_category"] == "configuration"
        assert details["severity"] == "critical"
        assert details["retry_strategy"] == "no_retry"
