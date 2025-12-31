"""Custom exceptions for Polymarket copy bot."""

from typing import Any, Optional


class PolymarketBotError(Exception):
    """Base exception for all Polymarket bot errors."""

    def __init__(self, message: str, details: Optional[dict] = None) -> None:
        """
        Initialize the exception.

        Args:
            message: Error message
            details: Optional additional error details
        """
        super().__init__(message)
        self.details = details or {}


class TradingError(PolymarketBotError):
    """Trading operation failed."""

    pass


class InsufficientBalanceError(TradingError):
    """Not enough funds for the requested operation."""

    def __init__(self, required: str, available: str, currency: str = "USDC") -> None:
        """
        Initialize insufficient balance error.

        Args:
            required: Amount required for the operation
            available: Amount currently available
            currency: Currency type (default: USDC)
        """
        message = f"Insufficient {currency} balance. Required: {required}, Available: {available}"
        super().__init__(
            message,
            {"required": required, "available": available, "currency": currency},
        )


class SlippageExceededError(TradingError):
    """Price slippage exceeded acceptable threshold."""

    def __init__(
        self, expected_price: str, actual_price: str, max_slippage: str
    ) -> None:
        """
        Initialize slippage exceeded error.

        Args:
            expected_price: Expected price
            actual_price: Actual price that triggered slippage
            max_slippage: Maximum acceptable slippage percentage
        """
        message = f"Slippage exceeded. Expected: {expected_price}, Actual: {actual_price}, Max slippage: {max_slippage}"
        super().__init__(
            message,
            {
                "expected_price": expected_price,
                "actual_price": actual_price,
                "max_slippage": max_slippage,
            },
        )


class CircuitBreakerTriggeredError(TradingError):
    """Circuit breaker triggered due to daily loss limit."""

    def __init__(self, daily_loss: str, limit: str) -> None:
        """
        Initialize circuit breaker error.

        Args:
            daily_loss: Current daily loss amount
            limit: Daily loss limit that was exceeded
        """
        message = f"Circuit breaker triggered. Daily loss: {daily_loss}, Limit: {limit}"
        super().__init__(message, {"daily_loss": daily_loss, "limit": limit})


class PositionLimitError(TradingError):
    """Position size limit exceeded."""

    def __init__(self, requested_size: str, max_size: str) -> None:
        """
        Initialize position limit error.

        Args:
            requested_size: Requested position size
            max_size: Maximum allowed position size
        """
        message = f"Position size limit exceeded. Requested: {requested_size}, Max: {max_size}"
        super().__init__(
            message, {"requested_size": requested_size, "max_size": max_size}
        )


class APIError(PolymarketBotError):
    """API call failed."""

    pass


class RateLimitError(APIError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int = 60, endpoint: Optional[str] = None) -> None:
        """
        Initialize rate limit error.

        Args:
            retry_after: Seconds to wait before retrying
            endpoint: API endpoint that was rate limited
        """
        self.retry_after = retry_after
        self.endpoint = endpoint
        message = "Rate limited"
        if endpoint:
            message += f" on {endpoint}"
        message += f", retry after {retry_after}s"
        super().__init__(message, {"retry_after": retry_after, "endpoint": endpoint})


class PolygonscanError(APIError):
    """Polygonscan API error."""

    pass


class PolymarketAPIError(APIError):
    """Polymarket CLOB API error."""

    pass


class ConfigError(PolymarketBotError):
    """Configuration error."""

    pass


class ValidationError(PolymarketBotError):
    """Data validation error."""

    def __init__(
        self, message: str, field: Optional[str] = None, value: Any = None
    ) -> None:
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field that failed validation (optional)
            value: Value that failed validation (optional)
        """
        super().__init__(message, {"field": field, "value": value})
        self.field = field
        self.value = value


class InitializationError(PolymarketBotError):
    """Application initialization failed."""

    def __init__(self, message: str, component: Optional[str] = None) -> None:
        """
        Initialize initialization error.

        Args:
            message: Error message
            component: Component that failed to initialize (optional)
        """
        super().__init__(message, {"component": component})
        self.component = component


class DependencyError(PolymarketBotError):
    """Required dependency is missing or incompatible."""

    def __init__(self, message: str, dependency: Optional[str] = None) -> None:
        """
        Initialize dependency error.

        Args:
            message: Error message
            dependency: Name of missing dependency (optional)
        """
        super().__init__(message, {"dependency": dependency})
        self.dependency = dependency


class GracefulShutdown(PolymarketBotError):
    """Request for graceful shutdown (not an error)."""

    def __init__(self, message: str = "Graceful shutdown requested") -> None:
        """
        Initialize graceful shutdown signal.

        Args:
            message: Shutdown message
        """
        super().__init__(message, {})
