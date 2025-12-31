"""
Pytest configuration and shared fixtures for unit tests.

This module provides comprehensive fixtures for testing critical modules:
- Trade Executor (money calculations, position sizing)
- Circuit Breaker (risk limits, state transitions)
- Market Analyzer (correlation logic, undefined names)
- Wallet Monitor (position management, cache safety)
"""

import asyncio
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.logger import get_logger

logger = get_logger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_clob_client():
    """Create a mock CLOB client for testing."""
    mock_client = MagicMock()
    mock_client.wallet_address = "0x1234567890abcdef1234567890abcdef12345678"

    # Mock methods
    mock_client.health_check = AsyncMock(return_value=True)
    mock_client.place_order = AsyncMock(return_value={"order_id": "test_order_123"})
    mock_client.cancel_order = AsyncMock(return_value=True)
    mock_client.get_token_balance = AsyncMock(return_value=Decimal("10000.0"))
    mock_client.get_market_price = AsyncMock(return_value=Decimal("0.5"))

    return mock_client


@pytest.fixture
def test_settings():
    """Create a test settings instance with proper environment."""
    old_env = os.environ.copy()

    # Set required environment variables for testing
    os.environ["PRIVATE_KEY"] = (
        "0x1234567890123456789012345678901234567890123456789012345678901234"
    )
    os.environ["POLYGON_RPC_URL"] = "https://polygon-rpc.com"
    os.environ["TELEGRAM_BOT_TOKEN"] = "test_bot_token"
    os.environ["TELEGRAM_CHAT_ID"] = "test_chat_id"
    os.environ["POLYGONSCAN_API_KEY"] = "test_api_key"
    os.environ["LOG_LEVEL"] = "DEBUG"

    try:
        from config.settings import Settings

        settings = Settings()
        yield settings
    finally:
        # Restore environment
        os.environ.clear()
        os.environ.update(old_env)


@pytest.fixture
def sample_trade_data():
    """Create sample trade data for testing."""
    return {
        "market_id": "test_market_123",
        "outcome_id": "YES",
        "price": Decimal("0.5"),
        "side": "BUY",
        "size": Decimal("100.0"),
        "maker": "0x1234567890abcdef1234567890abcdef12345678",
    }


@pytest.fixture
def sample_position():
    """Create sample position data for testing."""
    return {
        "market_id": "test_market_123",
        "outcome_id": "YES",
        "entry_price": Decimal("0.5"),
        "current_price": Decimal("0.55"),
        "size": Decimal("100.0"),
        "pnl": Decimal("10.0"),
        "entry_time": datetime.now(timezone.utc),
        "stop_loss": Decimal("0.45"),
        "take_profit": Decimal("0.625"),
    }


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        config_data = {
            "target_wallets": ["0x1234567890abcdef1234567890abcdef12345678"],
            "min_confidence_score": 0.7,
        }
        import json

        json.dump(config_data, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except OSError:
        pass


# =============================================================================
# Trade Executor Fixtures
# =============================================================================


@pytest.fixture
def mock_trade_executor(mock_clob_client, test_settings):
    """Create a mock trade executor for testing."""
    from core.trade_executor import TradeExecutor

    executor = TradeExecutor(mock_clob_client)
    return executor


@pytest.fixture
def sample_money_calculation_scenarios():
    """Create sample money calculation scenarios for testing."""
    return [
        {
            "account_balance": Decimal("10000.0"),
            "risk_percent": Decimal("0.01"),
            "expected_position_size": Decimal("100.0"),
        },
        {
            "account_balance": Decimal("50000.0"),
            "risk_percent": Decimal("0.02"),
            "expected_position_size": Decimal("1000.0"),
        },
        {
            "account_balance": Decimal("1000.0"),
            "risk_percent": Decimal("0.05"),
            "expected_position_size": Decimal("50.0"),
        },
    ]


@pytest.fixture
def sample_risk_management_scenarios():
    """Create sample risk management scenarios for testing."""
    return [
        {
            "daily_loss": 50.0,
            "max_daily_loss": 100.0,
            "expected_circuit_state": False,
        },
        {
            "daily_loss": 100.0,
            "max_daily_loss": 100.0,
            "expected_circuit_state": True,
        },
        {
            "daily_loss": 150.0,
            "max_daily_loss": 100.0,
            "expected_circuit_state": True,
        },
    ]


# =============================================================================
# Circuit Breaker Fixtures
# =============================================================================


@pytest.fixture
def temp_circuit_breaker_state_file():
    """Create a temporary state file for circuit breaker testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        state_data = {
            "active": False,
            "reason": "",
            "daily_loss": 0.0,
            "consecutive_losses": 0,
            "failed_trades": 0,
            "total_trades": 0,
        }
        import json

        json.dump(state_data, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    try:
        if temp_path.exists():
            temp_path.unlink()
    except OSError:
        pass


@pytest.fixture
def circuit_breaker_scenarios():
    """Create circuit breaker test scenarios."""
    return [
        {
            "name": "daily_loss_limit_reached",
            "daily_loss": 100.0,
            "max_daily_loss": 100.0,
            "consecutive_losses": 2,
            "expected_active": True,
            "expected_reason": "Daily loss limit reached",
        },
        {
            "name": "consecutive_losses_threshold",
            "daily_loss": 50.0,
            "max_daily_loss": 200.0,
            "consecutive_losses": 5,
            "expected_active": True,
            "expected_reason": "5 consecutive losses detected",
        },
        {
            "name": "normal_operation",
            "daily_loss": 50.0,
            "max_daily_loss": 200.0,
            "consecutive_losses": 1,
            "expected_active": False,
            "expected_reason": "",
        },
    ]


@pytest.fixture
def circuit_breaker_state_transitions():
    """Create circuit breaker state transition scenarios."""
    return [
        {
            "from_state": "inactive",
            "to_state": "active",
            "trigger": "daily_loss_limit",
            "valid": True,
        },
        {
            "from_state": "active",
            "to_state": "inactive",
            "trigger": "manual_reset",
            "valid": True,
        },
        {
            "from_state": "active",
            "to_state": "active",
            "trigger": "another_loss",
            "valid": True,
        },
    ]


# =============================================================================
# Market Analyzer Fixtures
# =============================================================================


@pytest.fixture
def sample_market_analyzer_data():
    """Create sample market analyzer data for testing."""
    return {
        "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
        "confidence_score": 0.85,
        "risk_score": 0.15,
        "position_size_factor": 1.5,
        "trade_volume": Decimal("50000.0"),
        "profitability_score": 0.78,
        "correlation_with_other_wallets": 0.92,
    }


@pytest.fixture
def correlation_test_scenarios():
    """Create correlation test scenarios."""
    return [
        {
            "name": "high_correlation",
            "correlation": 0.95,
            "expected_action": "allow",
            "threshold": 0.9,
        },
        {
            "name": "low_correlation",
            "correlation": 0.65,
            "expected_action": "flag_for_review",
            "threshold": 0.9,
        },
        {
            "name": "negative_correlation",
            "correlation": -0.45,
            "expected_action": "reject",
            "threshold": 0.9,
        },
    ]


@pytest.fixture
def undefined_name_test_cases():
    """Create undefined name test cases for market analyzer."""
    return [
        {
            "description": "variable used but not defined",
            "code_snippet": "position = calculate_position(wallet)",
            "undefined_name": "calculate_position",
        },
        {
            "description": "class attribute accessed incorrectly",
            "code_snippet": "wallet.balance = wallet.get_balance()",
            "undefined_name": "wallet.balance",
        },
        {
            "description": "function parameter missing",
            "code_snippet": "execute_trade(market_id, side)",
            "undefined_name": "size parameter missing",
        },
    ]


# =============================================================================
# Wallet Monitor Fixtures
# =============================================================================


@pytest.fixture
def sample_wallet_transactions():
    """Create sample wallet transactions for testing."""
    return [
        {
            "hash": "0x" + "a" * 64,
            "from": "0x1234567890abcdef1234567890abcdef12345678",
            "to": "0xabcdef1234567890abcdef1234567890abcdef12",
            "value": "100000000000000000000",  # 100 USDC
            "input": "0x",
            "gas": 100000,
            "gasUsed": 85000,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "hash": "0x" + "b" * 64,
            "from": "0x1234567890abcdef1234567890abcdef12345678",
            "to": "0xabcdef1234567890abcdef1234567890abcdef12",
            "value": "50000000000000000000",  # 50 USDC
            "input": "0x1234",
            "gas": 100000,
            "gasUsed": 90000,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    ]


@pytest.fixture
def sample_monitored_positions():
    """Create sample monitored positions for testing."""
    return {
        "0xmarket_123": {
            "market_id": "0xmarket_123",
            "outcome_id": "YES",
            "entry_price": Decimal("0.5"),
            "current_price": Decimal("0.55"),
            "size": Decimal("100.0"),
            "pnl": Decimal("10.0"),
            "entry_time": datetime.now(timezone.utc),
            "stop_loss": Decimal("0.45"),
            "take_profit": Decimal("0.625"),
        },
        "0xmarket_456": {
            "market_id": "0xmarket_456",
            "outcome_id": "NO",
            "entry_price": Decimal("0.6"),
            "current_price": Decimal("0.58"),
            "size": Decimal("50.0"),
            "pnl": Decimal("-5.0"),
            "entry_time": datetime.now(timezone.utc),
            "stop_loss": Decimal("0.54"),
            "take_profit": Decimal("0.75"),
        },
    }


@pytest.fixture
def cache_test_scenarios():
    """Create cache test scenarios for wallet monitor."""
    return [
        {
            "name": "cache_hit",
            "key": "wallet_tx_0x1234",
            "exists": True,
            "within_ttl": True,
        },
        {
            "name": "cache_miss",
            "key": "wallet_tx_0x5678",
            "exists": False,
            "within_ttl": True,
        },
        {
            "name": "cache_expired",
            "key": "wallet_tx_0x9abc",
            "exists": True,
            "within_ttl": False,
        },
    ]


# =============================================================================
# Common Test Utilities
# =============================================================================


@pytest.fixture
def test_timer():
    """Create a simple timer for measuring test duration."""
    import time

    class TestTimer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()

        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return 0.0

    return TestTimer()


@pytest.fixture
def mock_async_response():
    """Create a mock async response helper."""

    async def _mock_response(data: any, delay: float = 0.0):
        """Mock async response with optional delay."""
        if delay > 0:
            await asyncio.sleep(delay)
        return data

    return _mock_response


@pytest.fixture
def mock_api_error():
    """Create a mock API error for testing."""
    from core.exceptions import APIError

    async def _mock_api_error(
        message: str, status_code: int = 500, error_code: str = "INTERNAL_ERROR"
    ):
        """Mock API error."""
        raise APIError(
            message=message,
            status_code=status_code,
            error_code=error_code,
            response={"error": message},
        )

    return _mock_api_error


# =============================================================================
# Money Safety Test Helpers
# =============================================================================


@pytest.fixture
def decimal_calculator():
    """Create a decimal calculator for money safety tests."""
    from decimal import Decimal, getcontext, ROUND_HALF_UP

    getcontext().prec = 28
    getcontext().rounding = ROUND_HALF_UP

    class DecimalCalculator:
        @staticmethod
        def multiply(a: Decimal, b: Decimal) -> Decimal:
            """Safe decimal multiplication."""
            return Decimal(str(a)) * Decimal(str(b))

        @staticmethod
        def divide(a: Decimal, b: Decimal) -> Decimal:
            """Safe decimal division."""
            if b == Decimal("0"):
                raise ValueError("Division by zero")
            return Decimal(str(a)) / Decimal(str(b))

        @staticmethod
        def add(a: Decimal, b: Decimal) -> Decimal:
            """Safe decimal addition."""
            return Decimal(str(a)) + Decimal(str(b))

        @staticmethod
        def subtract(a: Decimal, b: Decimal) -> Decimal:
            """Safe decimal subtraction."""
            return Decimal(str(a)) - Decimal(str(b))

    return DecimalCalculator()


@pytest.fixture
def float_calculator():
    """Create a float calculator for comparison (should NOT be used)."""

    class FloatCalculator:
        @staticmethod
        def multiply(a: float, b: float) -> float:
            """Float multiplication (for testing failures)."""
            return a * b

        @staticmethod
        def divide(a: float, b: float) -> float:
            """Float division (for testing failures)."""
            return a / b

    return FloatCalculator()


# =============================================================================
# Thread Safety Test Helpers
# =============================================================================


@pytest.fixture
def async_lock_tester():
    """Create a tester for async lock behavior."""

    class AsyncLockTester:
        def __init__(self):
            self.lock = asyncio.Lock()
            self.counter = 0
            self.errors = 0

        async def increment(self, delay: float = 0.0):
            """Increment counter with optional delay."""
            async with self.lock:
                self.counter += 1
                if delay > 0:
                    await asyncio.sleep(delay)

        async def get_counter(self) -> int:
            """Get current counter value."""
            async with self.lock:
                return self.counter

        async def concurrent_increment(self, n: int = 10, delay: float = 0.01):
            """Run n concurrent increments to test lock."""
            tasks = [self.increment(delay) for _ in range(n)]
            await asyncio.gather(*tasks)

    return AsyncLockTester()


# =============================================================================
# Memory Safety Test Helpers
# =============================================================================


@pytest.fixture
def memory_monitor():
    """Create a memory monitor for testing."""
    import tracemalloc

    class MemoryMonitor:
        def __init__(self):
            tracemalloc.start()
            self.snapshot1 = tracemalloc.take_snapshot()
            self.snapshot2 = None

        def checkpoint(self):
            """Take a memory snapshot."""
            self.snapshot2 = tracemalloc.take_snapshot()

        def get_memory_diff(self):
            """Get memory difference between snapshots."""
            if self.snapshot1 and self.snapshot2:
                stats = self.snapshot2.compare_to(self.snapshot1, "lineno")
                total_diff = sum(stat.size_diff for stat in stats)
                return total_diff / 1024 / 1024  # KB
            return 0.0

        def stop(self):
            """Stop memory monitoring."""
            if self.snapshot2:
                self.snapshot2 = None
            tracemalloc.stop()

    return MemoryMonitor()


# =============================================================================
# API Resilience Test Helpers
# =============================================================================


@pytest.fixture
def mock_api_client_with_failures():
    """Create a mock API client that simulates failures."""

    class MockAPIClientWithFailures:
        def __init__(self):
            self.call_count = 0
            self.failure_sequence = [False] * 5 + [True, True]  # Fail after 5 calls
            self.wallet_address = "0x1234567890abcdef1234567890abcdef12345678"

        async def place_order(self, *args, **kwargs):
            """Mock place order with simulated failures."""
            self.call_count += 1
            if self.call_count <= len(self.failure_sequence):
                should_fail = self.failure_sequence[self.call_count - 1]
                if should_fail:
                    from core.exceptions import APIError

                    raise APIError(
                        message="Simulated API failure",
                        status_code=500,
                        error_code="SIMULATED_FAILURE",
                    )
            return {"order_id": f"test_order_{self.call_count}"}

        async def get_token_balance(self, *args, **kwargs):
            """Mock get token balance."""
            return Decimal("10000.0")

    return MockAPIClientWithFailures()


# =============================================================================
# Configure pytest-asyncio
# =============================================================================

pytest_plugins = ["pytest_asyncio"]
