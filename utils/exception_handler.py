"""
Centralized Exception Handler for Polymarket Copy Bot

Provides:
- Context-aware error logging with severity levels
- Exception classification and handling
- Retry strategy recommendations
- Error context preservation
- Main loop protection (errors don't crash the bot)
"""

import asyncio
import logging
import traceback
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import aiohttp
from web3.exceptions import (
    BadFunctionCallOutput,
    ContractLogicError,
    Web3ValidationError,
)

from core.exceptions import (
    APIError,
    ConfigError,
    PolymarketAPIError,
    PolygonscanError,
    RateLimitError,
    TradingError,
)
from utils.validation import ValidationError

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""

    DEBUG = "debug"  # Informational, no action needed
    INFO = "info"  # Expected condition, handled gracefully
    WARNING = "warning"  # Potentially problematic, monitor
    ERROR = "error"  # Error occurred, operation failed but system continues
    CRITICAL = "critical"  # Critical error, may require intervention


class RetryStrategy(Enum):
    """Retry strategy recommendations"""

    NO_RETRY = "no_retry"  # Don't retry (validation errors, etc.)
    IMMEDIATE = "immediate"  # Retry immediately
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # Retry with exponential backoff
    FIXED_DELAY = "fixed_delay"  # Retry after fixed delay
    RATE_LIMIT_DELAY = "rate_limit_delay"  # Wait for rate limit reset


class ExceptionHandler:
    """
    Centralized exception handler with context-aware logging and retry strategies.

    Features:
    - Exception classification by type
    - Severity level assignment
    - Retry strategy recommendations
    - Context preservation
    - Stack trace logging
    - Main loop protection
    """

    # Exception type to severity mapping
    EXCEPTION_SEVERITY_MAP: Dict[Type[Exception], ErrorSeverity] = {
        # Network errors - usually recoverable
        ConnectionError: ErrorSeverity.ERROR,
        TimeoutError: ErrorSeverity.ERROR,
        asyncio.TimeoutError: ErrorSeverity.ERROR,
        aiohttp.ClientError: ErrorSeverity.ERROR,
        aiohttp.ClientConnectionError: ErrorSeverity.ERROR,
        aiohttp.ClientTimeout: ErrorSeverity.ERROR,
        # API errors
        APIError: ErrorSeverity.ERROR,
        PolymarketAPIError: ErrorSeverity.ERROR,
        PolygonscanError: ErrorSeverity.ERROR,
        RateLimitError: ErrorSeverity.WARNING,
        # Validation errors - don't retry
        ValidationError: ErrorSeverity.WARNING,
        ValueError: ErrorSeverity.WARNING,
        TypeError: ErrorSeverity.WARNING,
        KeyError: ErrorSeverity.WARNING,
        # Web3 errors
        Web3ValidationError: ErrorSeverity.ERROR,
        ContractLogicError: ErrorSeverity.ERROR,
        BadFunctionCallOutput: ErrorSeverity.ERROR,
        # Configuration errors - critical
        ConfigError: ErrorSeverity.CRITICAL,
        # Trading errors
        TradingError: ErrorSeverity.ERROR,
        # Generic errors - log as critical for investigation
        Exception: ErrorSeverity.CRITICAL,
    }

    # Exception type to retry strategy mapping
    EXCEPTION_RETRY_MAP: Dict[Type[Exception], RetryStrategy] = {
        # Network errors - retry with backoff
        ConnectionError: RetryStrategy.EXPONENTIAL_BACKOFF,
        TimeoutError: RetryStrategy.EXPONENTIAL_BACKOFF,
        asyncio.TimeoutError: RetryStrategy.EXPONENTIAL_BACKOFF,
        aiohttp.ClientError: RetryStrategy.EXPONENTIAL_BACKOFF,
        aiohttp.ClientConnectionError: RetryStrategy.EXPONENTIAL_BACKOFF,
        aiohttp.ClientTimeout: RetryStrategy.EXPONENTIAL_BACKOFF,
        # API errors - retry with backoff
        APIError: RetryStrategy.EXPONENTIAL_BACKOFF,
        PolymarketAPIError: RetryStrategy.EXPONENTIAL_BACKOFF,
        PolygonscanError: RetryStrategy.EXPONENTIAL_BACKOFF,
        # Rate limit - wait for reset
        RateLimitError: RetryStrategy.RATE_LIMIT_DELAY,
        # Validation errors - don't retry
        ValidationError: RetryStrategy.NO_RETRY,
        ValueError: RetryStrategy.NO_RETRY,
        TypeError: RetryStrategy.NO_RETRY,
        KeyError: RetryStrategy.NO_RETRY,
        # Web3 errors - may retry
        Web3ValidationError: RetryStrategy.EXPONENTIAL_BACKOFF,
        ContractLogicError: RetryStrategy.NO_RETRY,  # Contract logic errors usually permanent
        BadFunctionCallOutput: RetryStrategy.EXPONENTIAL_BACKOFF,
        # Configuration errors - don't retry
        ConfigError: RetryStrategy.NO_RETRY,
        # Trading errors - depends on type
        TradingError: RetryStrategy.NO_RETRY,
    }

    def __init__(self) -> None:
        """Initialize exception handler"""
        self.error_counts: Dict[str, int] = {}
        self.error_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000

    def classify_exception(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> Tuple[ErrorSeverity, RetryStrategy, str]:
        """
        Classify exception and determine handling strategy.

        Args:
            error: Exception to classify
            context: Optional context information

        Returns:
            Tuple of (severity, retry_strategy, error_category)
        """
        error_type = type(error)

        # Check specific exception types first
        severity = self.EXCEPTION_SEVERITY_MAP.get(error_type, ErrorSeverity.CRITICAL)

        # Check parent classes
        for exc_type, mapped_severity in self.EXCEPTION_SEVERITY_MAP.items():
            if issubclass(error_type, exc_type) and exc_type != Exception:
                severity = mapped_severity
                break

        # Get retry strategy
        retry_strategy = self.EXCEPTION_RETRY_MAP.get(
            error_type, RetryStrategy.NO_RETRY
        )

        # Check parent classes for retry strategy
        for exc_type, mapped_strategy in self.EXCEPTION_RETRY_MAP.items():
            if issubclass(error_type, exc_type) and exc_type != Exception:
                retry_strategy = mapped_strategy
                break

        # Special handling for RateLimitError
        if isinstance(error, RateLimitError):
            retry_strategy = RetryStrategy.RATE_LIMIT_DELAY
            severity = ErrorSeverity.WARNING

        # Determine error category
        if isinstance(error, (ConnectionError, TimeoutError, aiohttp.ClientError)):
            error_category = "network"
        elif isinstance(error, (APIError, PolymarketAPIError, PolygonscanError)):
            error_category = "api"
        elif isinstance(error, (ValidationError, ValueError, TypeError, KeyError)):
            error_category = "validation"
        elif isinstance(
            error, (Web3ValidationError, ContractLogicError, BadFunctionCallOutput)
        ):
            error_category = "blockchain"
        elif isinstance(error, TradingError):
            error_category = "trading"
        elif isinstance(error, ConfigError):
            error_category = "configuration"
        else:
            error_category = "unknown"

        return severity, retry_strategy, error_category

    def log_exception(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        component: str = "unknown",
        operation: str = "unknown",
        include_stack_trace: bool = True,
    ) -> Dict[str, Any]:
        """
        Log exception with context and severity.

        Args:
            error: Exception to log
            context: Additional context information
            component: Component where error occurred
            operation: Operation that failed
            include_stack_trace: Whether to include full stack trace

        Returns:
            Dictionary with error details and handling recommendations
        """
        severity, retry_strategy, error_category = self.classify_exception(
            error, context
        )

        # Build error details
        error_details = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "severity": severity.value,
            "retry_strategy": retry_strategy.value,
            "error_category": error_category,
            "component": component,
            "operation": operation,
            "context": context or {},
        }

        # Add stack trace if requested
        if include_stack_trace:
            error_details["stack_trace"] = traceback.format_exc()

        # Track error
        error_key = f"{error_category}:{type(error).__name__}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        # Add to history
        self.error_history.append(error_details)
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size :]

        # Log with appropriate severity
        log_message = (
            f"❌ [{error_category.upper()}] {component}.{operation}: "
            f"{type(error).__name__}: {str(error)[:200]}"
        )

        if context:
            log_message += f" | Context: {context}"

        if severity == ErrorSeverity.CRITICAL:
            logger.critical(
                log_message, exc_info=include_stack_trace, extra=error_details
            )
        elif severity == ErrorSeverity.ERROR:
            logger.error(log_message, exc_info=include_stack_trace, extra=error_details)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(log_message, extra=error_details)
        elif severity == ErrorSeverity.INFO:
            logger.info(log_message, extra=error_details)
        else:
            logger.debug(log_message, extra=error_details)

        return error_details

    async def handle_exception(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        component: str = "unknown",
        operation: str = "unknown",
        default_return: Any = None,
        retry_callback: Optional[Callable] = None,
        max_retries: int = 0,
    ) -> Any:
        """
        Handle exception with retry logic and return default value.

        This ensures errors don't crash the main event loop.

        Args:
            error: Exception to handle
            context: Additional context
            component: Component name
            operation: Operation name
            default_return: Value to return on error
            retry_callback: Optional async callback to retry
            max_retries: Maximum retry attempts

        Returns:
            Result from retry_callback if successful, otherwise default_return
        """
        error_details = self.log_exception(
            error, context=context, component=component, operation=operation
        )

        severity = ErrorSeverity(error_details["severity"])
        retry_strategy = RetryStrategy(error_details["retry_strategy"])

        # Don't retry if strategy is NO_RETRY or if max_retries is 0
        if retry_strategy == RetryStrategy.NO_RETRY or max_retries == 0:
            return default_return

        # Attempt retry if callback provided
        if retry_callback:
            try:
                if retry_strategy == RetryStrategy.IMMEDIATE:
                    return await retry_callback()
                elif retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                    for attempt in range(max_retries):
                        delay = min(2**attempt, 60)  # Cap at 60 seconds
                        await asyncio.sleep(delay)
                        try:
                            return await retry_callback()
                        except Exception as retry_error:
                            if attempt == max_retries - 1:
                                self.log_exception(
                                    retry_error,
                                    context={"retry_attempt": attempt + 1},
                                    component=component,
                                    operation=operation,
                                )
                            continue
                elif retry_strategy == RetryStrategy.FIXED_DELAY:
                    await asyncio.sleep(5)  # Fixed 5 second delay
                    return await retry_callback()
                elif retry_strategy == RetryStrategy.RATE_LIMIT_DELAY:
                    if isinstance(error, RateLimitError):
                        delay = error.retry_after
                    else:
                        delay = 60  # Default 60 seconds
                    await asyncio.sleep(delay)
                    return await retry_callback()
            except Exception as retry_error:
                self.log_exception(
                    retry_error,
                    context={"retry_failed": True},
                    component=component,
                    operation=operation,
                )

        return default_return

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            "total_errors": len(self.error_history),
            "error_counts": self.error_counts.copy(),
            "recent_errors": self.error_history[-10:] if self.error_history else [],
            "error_categories": {
                category: sum(
                    1 for e in self.error_history if e.get("error_category") == category
                )
                for category in [
                    "network",
                    "api",
                    "validation",
                    "blockchain",
                    "trading",
                    "configuration",
                    "unknown",
                ]
            },
        }

    def should_alert(self, error: Exception) -> bool:
        """
        Determine if error should trigger alert.

        Args:
            error: Exception to check

        Returns:
            True if alert should be sent
        """
        severity, _, _ = self.classify_exception(error)
        return severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]


# Global exception handler instance
exception_handler = ExceptionHandler()


# Convenience functions
def handle_exception(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    component: str = "unknown",
    operation: str = "unknown",
    default_return: Any = None,
) -> Any:
    """
    Convenience function to handle exception.

    Args:
        error: Exception to handle
        context: Additional context
        component: Component name
        operation: Operation name
        default_return: Value to return

    Returns:
        default_return
    """
    exception_handler.log_exception(
        error, context=context, component=component, operation=operation
    )
    return default_return


async def safe_execute(
    func: Callable,
    *args: Any,
    context: Optional[Dict[str, Any]] = None,
    component: str = "unknown",
    operation: str = "unknown",
    default_return: Any = None,
    max_retries: int = 0,
    **kwargs: Any,
) -> Any:
    """
    Safely execute a function with exception handling.

    Ensures errors don't crash the main event loop.

    Args:
        func: Function to execute
        *args: Positional arguments
        context: Additional context
        component: Component name
        operation: Operation name
        default_return: Value to return on error
        max_retries: Maximum retry attempts
        **kwargs: Keyword arguments

    Returns:
        Function result or default_return on error
    """
    try:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    except Exception as e:
        return await exception_handler.handle_exception(
            e,
            context=context,
            component=component,
            operation=operation,
            default_return=default_return,
            retry_callback=lambda: safe_execute(
                func,
                *args,
                context=context,
                component=component,
                operation=operation,
                default_return=default_return,
                max_retries=max_retries - 1,
                **kwargs,
            )
            if max_retries > 0
            else None,
            max_retries=max_retries,
        )
