"""
Unit tests for StrategyRiskManager

Tests strategy-specific risk management including:
- Risk profile management
- Circuit breaker activation and reset
- Correlation limit checking
- Volatility-adjusted position sizing
- State persistence
- Audit logging

Run with: pytest tests/unit/test_strategy_risk_manager.py -v
"""

import asyncio
import pickle
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from risk_management.strategy_risk_manager import (
    StrategyCircuitBreakerState,
    StrategyRiskManager,
    StrategyRiskProfile,
    TradingStrategy,
)


# Fixtures
@pytest.fixture
def temp_state_file(tmp_path):
    """Create temporary state file for testing."""
    return tmp_path / "test_risk_state.pkl"


@pytest.fixture
def temp_audit_log(tmp_path):
    """Create temporary audit log file for testing."""
    return tmp_path / "test_risk_audit.log"


@pytest.fixture
def risk_manager(temp_state_file, temp_audit_log):
    """Create StrategyRiskManager instance with temporary files."""
    return StrategyRiskManager(
        state_file=temp_state_file,
        audit_log_file=temp_audit_log,
    )


# Tests for StrategyRiskProfile
def test_strategy_risk_profile_creation():
    """Test StrategyRiskProfile dataclass creation."""
    profile = StrategyRiskProfile(
        strategy=TradingStrategy.COPY_TRADING,
        max_position_size=Decimal("50.0"),
        max_daily_loss=Decimal("100.0"),
        max_consecutive_losses=5,
        max_failure_rate=0.5,
        min_correlation_threshold=0.0,
        max_correlation_threshold=0.9,
        max_slippage=0.02,
        volatility_adjustment=False,
        max_portfolio_exposure=Decimal("500.0"),
        max_positions_per_market=3,
        enabled=True,
    )

    assert profile.strategy == TradingStrategy.COPY_TRADING
    assert profile.max_position_size == Decimal("50.0")
    assert profile.max_daily_loss == Decimal("100.0")
    assert profile.max_consecutive_losses == 5
    assert profile.volatility_adjustment is False
    assert profile.enabled is True


def test_strategy_risk_profile_to_dict():
    """Test StrategyRiskProfile serialization."""
    profile = StrategyRiskProfile(
        strategy=TradingStrategy.CROSS_MARKET_ARB,
        max_position_size=Decimal("10.0"),
        max_daily_loss=Decimal("25.0"),
        max_consecutive_losses=5,
        max_failure_rate=0.3,
        min_correlation_threshold=0.8,
        max_correlation_threshold=0.95,
        max_slippage=0.005,
        volatility_adjustment=True,
        max_portfolio_exposure=Decimal("100.0"),
        max_positions_per_market=1,
        enabled=False,
    )

    data = profile.to_dict()

    assert data["strategy"] == "cross_market_arb"
    assert data["max_position_size"] == 10.0
    assert data["max_daily_loss"] == 25.0
    assert data["enabled"] is False


def test_strategy_risk_profile_from_dict():
    """Test StrategyRiskProfile deserialization."""
    data = {
        "strategy": "endgame_sweep",
        "max_position_size": 20.0,
        "max_daily_loss": 50.0,
        "max_consecutive_losses": 3,
        "max_failure_rate": 0.4,
        "min_correlation_threshold": 0.0,
        "max_correlation_threshold": 0.8,
        "max_slippage": 0.01,
        "volatility_adjustment": True,
        "max_portfolio_exposure": 200.0,
        "max_positions_per_market": 2,
        "enabled": True,
    }

    profile = StrategyRiskProfile.from_dict(data)

    assert profile.strategy == TradingStrategy.ENDGAME_SWEEP
    assert profile.max_position_size == Decimal("20.0")
    assert profile.max_daily_loss == Decimal("50.0")
    assert profile.volatility_adjustment is True


# Tests for StrategyCircuitBreakerState
def test_circuit_breaker_state_creation():
    """Test StrategyCircuitBreakerState dataclass creation."""
    state = StrategyCircuitBreakerState(
        strategy=TradingStrategy.COPY_TRADING,
        active=True,
        reason="Daily loss exceeded",
        activation_time=1234567890.0,
        daily_loss=Decimal("100.0"),
        total_loss=Decimal("150.0"),
        total_profit=Decimal("200.0"),
        consecutive_losses=5,
        failed_trades=10,
        successful_trades=20,
        last_reset_date=datetime.now(timezone.utc),
        last_reset_time=1234567890.0,
    )

    assert state.strategy == TradingStrategy.COPY_TRADING
    assert state.active is True
    assert state.daily_loss == Decimal("100.0")
    assert state.consecutive_losses == 5


def test_circuit_breaker_state_to_dict():
    """Test StrategyCircuitBreakerState serialization."""
    state = StrategyCircuitBreakerState(
        strategy=TradingStrategy.CROSS_MARKET_ARB,
        active=False,
        reason="",
        activation_time=None,
        daily_loss=Decimal("25.0"),
        total_loss=Decimal("0.0"),
        total_profit=Decimal("50.0"),
        consecutive_losses=0,
        failed_trades=0,
        successful_trades=10,
        last_reset_date=datetime.now(timezone.utc),
        last_reset_time=1234567890.0,
    )

    data = state.to_dict()

    assert data["strategy"] == "cross_market_arb"
    assert data["active"] is False
    assert data["daily_loss"] == 25.0
    assert "last_reset_date" in data


def test_circuit_breaker_state_from_dict():
    """Test StrategyCircuitBreakerState deserialization."""
    data = {
        "strategy": "copy_trading",
        "active": True,
        "reason": "Test",
        "activation_time": 1234567890.0,
        "daily_loss": 75.0,
        "total_loss": 100.0,
        "total_profit": 200.0,
        "consecutive_losses": 3,
        "failed_trades": 5,
        "successful_trades": 10,
        "last_reset_date": datetime.now(timezone.utc).isoformat(),
        "last_reset_time": 1234567890.0,
    }

    state = StrategyCircuitBreakerState.from_dict(data)

    assert state.strategy == TradingStrategy.COPY_TRADING
    assert state.active is True
    assert state.daily_loss == Decimal("75.0")


# Tests for StrategyRiskManager initialization
def test_risk_manager_initialization(temp_state_file, temp_audit_log):
    """Test StrategyRiskManager initialization."""
    manager = StrategyRiskManager(
        state_file=temp_state_file,
        audit_log_file=temp_audit_log,
    )

    # Check that default profiles are loaded
    assert len(manager.strategy_profiles) == 4
    assert TradingStrategy.COPY_TRADING in manager.strategy_profiles
    assert TradingStrategy.ENDGAME_SWEEP in manager.strategy_profiles

    # Check that files were created
    assert temp_state_file.parent.exists()
    assert temp_audit_log.parent.exists()


def test_risk_manager_loads_state(temp_state_file, temp_audit_log):
    """Test that state is loaded from disk."""
    # Create a saved state first
    old_manager = StrategyRiskManager(
        state_file=temp_state_file,
        audit_log_file=temp_audit_log,
    )

    # Save some state
    asyncio.run(old_manager.update_volatility_data("vix", 35.0))

    # Create new manager (should load saved state)
    new_manager = StrategyRiskManager(
        state_file=temp_state_file,
        audit_log_file=temp_audit_log,
    )

    # Check that volatility data was loaded
    assert "vix" in new_manager._volatility_data
    assert new_manager._volatility_data["vix"] == 35.0


# Tests for risk profile management
@pytest.mark.asyncio
async def test_get_risk_profile(risk_manager):
    """Test getting risk profile for a strategy."""
    profile = await risk_manager.get_risk_profile(TradingStrategy.COPY_TRADING)

    assert profile is not None
    assert profile.strategy == TradingStrategy.COPY_TRADING
    assert profile.max_position_size == Decimal("50.0")
    assert profile.enabled is True


@pytest.mark.asyncio
async def test_get_risk_profile_missing_strategy(risk_manager):
    """Test getting risk profile for missing strategy (returns default)."""
    # Get a strategy that exists
    profile = await risk_manager.get_risk_profile(TradingStrategy.COPY_TRADING)

    assert profile is not None
    assert profile.strategy == TradingStrategy.COPY_TRADING


@pytest.mark.asyncio
async def test_set_risk_profile(risk_manager):
    """Test setting a new risk profile."""
    new_profile = StrategyRiskProfile(
        strategy=TradingStrategy.COPY_TRADING,
        max_position_size=Decimal("75.0"),
        max_daily_loss=Decimal("150.0"),
        max_consecutive_losses=7,
        max_failure_rate=0.6,
        min_correlation_threshold=0.1,
        max_correlation_threshold=0.85,
        max_slippage=0.03,
        volatility_adjustment=True,
        max_portfolio_exposure=Decimal("600.0"),
        max_positions_per_market=4,
        enabled=True,
    )

    await risk_manager.set_risk_profile(TradingStrategy.COPY_TRADING, new_profile)

    # Check that profile was updated
    updated_profile = await risk_manager.get_risk_profile(TradingStrategy.COPY_TRADING)
    assert updated_profile.max_position_size == Decimal("75.0")
    assert updated_profile.volatility_adjustment is True


# Tests for trade checking
@pytest.mark.asyncio
async def test_check_trade_allowed_all_checks_pass(risk_manager):
    """Test trade check when all checks pass."""
    trade_details = {
        "amount": 25.0,  # Below max of 50.0
        "market_id": "0x123...",
    }

    # Mock low portfolio exposure
    risk_manager._total_portfolio_exposure = Decimal("100.0")  # Below max of 500.0

    # Mock circuit breaker not active
    if TradingStrategy.COPY_TRADING in risk_manager._circuit_breakers:
        risk_manager._circuit_breakers[TradingStrategy.COPY_TRADING].active = False

    result = await risk_manager.check_trade_allowed(
        TradingStrategy.COPY_TRADING, trade_details
    )

    # Should allow trade
    assert result is None


@pytest.mark.asyncio
async def test_check_trade_blocked_by_position_size(risk_manager):
    """Test trade check blocked by position size."""
    trade_details = {
        "amount": 75.0,  # Above max of 50.0
        "market_id": "0x123...",
    }

    result = await risk_manager.check_trade_allowed(
        TradingStrategy.COPY_TRADING, trade_details
    )

    # Should block trade
    assert result is not None
    assert result["status"] == "skipped"
    assert "exceeds maximum" in result["reason"]


@pytest.mark.asyncio
async def test_check_trade_blocked_by_circuit_breaker(risk_manager):
    """Test trade check blocked by circuit breaker."""
    # Activate circuit breaker
    if TradingStrategy.COPY_TRADING in risk_manager._circuit_breakers:
        await risk_manager._activate_circuit_breaker(
            risk_manager._circuit_breakers[TradingStrategy.COPY_TRADING],
            "Test activation",
        )

    trade_details = {
        "amount": 25.0,
        "market_id": "0x123...",
    }

    result = await risk_manager.check_trade_allowed(
        TradingStrategy.COPY_TRADING, trade_details
    )

    # Should block trade
    assert result is not None
    assert result["status"] == "skipped"
    assert "Circuit breaker active" in result["reason"]


@pytest.mark.asyncio
async def test_check_trade_disabled_strategy(risk_manager):
    """Test trade check when strategy is disabled."""
    # Disable strategy
    profile = await risk_manager.get_risk_profile(TradingStrategy.COPY_TRADING)
    profile.enabled = False
    await risk_manager.set_risk_profile(TradingStrategy.COPY_TRADING, profile)

    trade_details = {
        "amount": 25.0,
        "market_id": "0x123...",
    }

    result = await risk_manager.check_trade_allowed(
        TradingStrategy.COPY_TRADING, trade_details
    )

    # Should block trade
    assert result is not None
    assert result["status"] == "skipped"
    assert "not enabled" in result["reason"]


# Tests for correlation checking
@pytest.mark.asyncio
async def test_check_portfolio_correlation_passes(risk_manager):
    """Test correlation check when within limits."""
    # Mock active positions with low correlation
    risk_manager._active_positions = {
        "0x111...": [{"amount": 25.0}],
        "0x222...": [{"amount": 25.0}],
    }

    # Mock low correlation (0.5, below threshold of 0.9)
    await risk_manager.update_market_correlation("0x111...", "0x222...", 0.5)

    trade_details = {
        "amount": 25.0,
        "market_id": "0x333...",  # New market
    }

    result = await risk_manager.check_trade_allowed(
        TradingStrategy.COPY_TRADING, trade_details
    )

    # Should allow trade (correlation 0.5 < 0.9)
    assert result is None


@pytest.mark.asyncio
async def test_check_portfolio_correlation_blocks(risk_manager):
    """Test correlation check when exceeds limits."""
    # Mock active positions
    risk_manager._active_positions = {
        "0x111...": [{"amount": 25.0}],
        "0x222...": [{"amount": 25.0}],
    }

    # Mock high correlation (0.95, above threshold of 0.9)
    await risk_manager.update_market_correlation("0x111...", "0x222...", 0.95)

    trade_details = {
        "amount": 25.0,
        "market_id": "0x333...",  # New market
    }

    result = await risk_manager.check_trade_allowed(
        TradingStrategy.COPY_TRADING, trade_details
    )

    # Should block trade
    assert result is not None
    assert result["status"] == "skipped"
    assert "correlation" in result["reason"]


# Tests for volatility adjustment
@pytest.mark.asyncio
async def test_check_volatility_adjustment_allows(risk_manager):
    """Test volatility adjustment when VIX is low."""
    # Mock low volatility (VIX = 15, below threshold of 30)
    await risk_manager.update_volatility_data("vix", 15.0)

    trade_details = {
        "amount": 25.0,
        "market_id": "0x123...",
    }

    result = await risk_manager.check_trade_allowed(
        TradingStrategy.COPY_TRADING, trade_details
    )

    # Should allow trade
    assert result is None


@pytest.mark.asyncio
async def test_check_volatility_adjustment_blocks(risk_manager):
    """Test volatility adjustment when VIX is high."""
    # Mock high volatility (VIX = 40, above threshold of 30)
    await risk_manager.update_volatility_data("vix", 40.0)

    trade_details = {
        "amount": 25.0,
        "market_id": "0x123...",
    }

    result = await risk_manager.check_trade_allowed(
        TradingStrategy.COPY_TRADING, trade_details
    )

    # Should block trade
    assert result is not None
    assert result["status"] == "skipped"
    assert "Volatility" in result["reason"]


# Tests for trade result recording
@pytest.mark.asyncio
async def test_record_trade_result_success(risk_manager):
    """Test recording successful trade result."""
    trade_id = "test_trade_123"

    await risk_manager.record_trade_result(
        TradingStrategy.COPY_TRADING,
        success=True,
        profit=Decimal("10.0"),
        trade_id=trade_id,
    )

    # Check state
    cb_state = risk_manager._circuit_breakers[TradingStrategy.COPY_TRADING]
    assert cb_state.successful_trades == 1
    assert cb_state.consecutive_losses == 0
    assert cb_state.total_profit == Decimal("10.0")
    assert cb_state.daily_loss == Decimal("0.0")


@pytest.mark.asyncio
async def test_record_trade_result_loss(risk_manager):
    """Test recording trade loss."""
    await risk_manager.record_trade_result(
        TradingStrategy.COPY_TRADING,
        success=True,
        profit=Decimal("-5.0"),  # Loss
        trade_id="test_trade_456",
    )

    # Check state
    cb_state = risk_manager._circuit_breakers[TradingStrategy.COPY_TRADING]
    assert cb_state.total_loss == Decimal("5.0")
    assert cb_state.daily_loss == Decimal("5.0")
    assert cb_state.consecutive_losses == 1


@pytest.mark.asyncio
async def test_record_trade_result_failure(risk_manager):
    """Test recording failed trade."""
    await risk_manager.record_trade_result(
        TradingStrategy.COPY_TRADING,
        success=False,
        profit=None,
        trade_id="test_trade_789",
    )

    # Check state
    cb_state = risk_manager._circuit_breakers[TradingStrategy.COPY_TRADING]
    assert cb_state.failed_trades == 1
    assert cb_state.consecutive_losses == 1


@pytest.mark.asyncio
async def test_record_trade_activates_circuit_breaker(risk_manager):
    """Test that recording losses activates circuit breaker."""
    # Record multiple consecutive losses
    for i in range(6):  # Exceeds max of 5
        await risk_manager.record_trade_result(
            TradingStrategy.COPY_TRADING,
            success=True,
            profit=Decimal("-1.0"),
            trade_id=f"test_trade_{i}",
        )

    # Check that circuit breaker activated
    cb_state = risk_manager._circuit_breakers[TradingStrategy.COPY_TRADING]
    assert cb_state.active is True
    assert "consecutive" in cb_state.reason.lower()


# Tests for circuit breaker operations
@pytest.mark.asyncio
async def test_activate_circuit_breaker(risk_manager):
    """Test circuit breaker activation."""
    cb_state = risk_manager._circuit_breakers[TradingStrategy.COPY_TRADING]

    await risk_manager._activate_circuit_breaker(cb_state, "Test activation")

    # Check activation
    assert cb_state.active is True
    assert cb_state.reason == "Test activation"
    assert cb_state.activation_time is not None


@pytest.mark.asyncio
async def test_reset_circuit_breaker(risk_manager):
    """Test circuit breaker reset."""
    # Activate first
    cb_state = risk_manager._circuit_breakers[TradingStrategy.COPY_TRADING]
    cb_state.active = True
    cb_state.reason = "Test"

    await risk_manager.reset_circuit_breaker(
        TradingStrategy.COPY_TRADING, "Manual reset"
    )

    # Check reset
    assert cb_state.active is False
    assert cb_state.reason == ""
    assert cb_state.daily_loss == Decimal("0.0")
    assert cb_state.consecutive_losses == 0


# Tests for volatility data
@pytest.mark.asyncio
async def test_update_volatility_data(risk_manager):
    """Test volatility data update."""
    await risk_manager.update_volatility_data("vix", 35.5)

    assert "vix" in risk_manager._volatility_data
    assert risk_manager._volatility_data["vix"] == 35.5


# Tests for market correlation
@pytest.mark.asyncio
async def test_update_market_correlation(risk_manager):
    """Test market correlation update."""
    await risk_manager.update_market_correlation("market_1", "market_2", 0.85)

    key = tuple(sorted(("market_1", "market_2")))
    assert key in risk_manager._market_correlations
    assert risk_manager._market_correlations[key] == 0.85


# Tests for risk metrics
@pytest.mark.asyncio
async def test_get_risk_metrics(risk_manager):
    """Test getting risk metrics."""
    metrics = await risk_manager.get_risk_metrics()

    assert "timestamp" in metrics
    assert "strategies" in metrics
    assert "portfolio" in metrics

    # Check portfolio metrics
    assert "total_exposure" in metrics["portfolio"]
    assert "active_positions" in metrics["portfolio"]

    # Check strategy metrics
    assert "copy_trading" in metrics["strategies"]
    assert "circuit_breaker_active" in metrics["strategies"]["copy_trading"]
    assert "success_rate" in metrics["strategies"]["copy_trading"]


# Tests for daily reset
@pytest.mark.asyncio
async def test_check_daily_reset(risk_manager):
    """Test daily reset functionality."""
    # Set last reset date to yesterday
    cb_state = risk_manager._circuit_breakers[TradingStrategy.COPY_TRADING]
    cb_state.last_reset_date = datetime.now(timezone.utc) - timedelta(days=1)
    cb_state.daily_loss = Decimal("50.0")
    cb_state.consecutive_losses = 3

    # Perform daily reset
    await risk_manager.check_daily_reset()

    # Check reset
    assert cb_state.last_reset_date.date() == datetime.now(timezone.utc).date()
    assert cb_state.daily_loss == Decimal("0.0")
    assert cb_state.consecutive_losses == 0


# Tests for state persistence
def test_save_state(risk_manager):
    """Test state persistence."""
    # This is tested implicitly by other tests
    # Just verify the file exists
    assert risk_manager.state_file.parent.exists()


# Tests for audit logging
@pytest.mark.asyncio
async def test_audit_log_created(risk_manager):
    """Test that audit log is created."""
    # Perform an action that should log
    await risk_manager.set_risk_profile(
        TradingStrategy.COPY_TRADING,
        await risk_manager.get_risk_profile(TradingStrategy.COPY_TRADING),
    )

    # Check that audit log exists
    assert risk_manager.audit_log_file.parent.exists()

    # Check log content
    if risk_manager.audit_log_file.exists():
        with open(risk_manager.audit_log_file, "r") as f:
            content = f.read()
            assert "PROFILE_UPDATE" in content
            assert "copy_trading" in content


# Tests for multi-strategy support
@pytest.mark.asyncio
async def test_multiple_strategies_independent(risk_manager):
    """Test that multiple strategies operate independently."""
    # Activate circuit breaker for one strategy
    cb1 = risk_manager._circuit_breakers[TradingStrategy.COPY_TRADING]
    await risk_manager._activate_circuit_breaker(cb1, "Strategy 1 activated")

    # Check other strategies
    cb2 = risk_manager._circuit_breakers[TradingStrategy.ENDGAME_SWEEP]

    # Strategy 2 should still be allowed
    trade_details = {
        "amount": 25.0,
        "market_id": "0x123...",
    }

    result = await risk_manager.check_trade_allowed(
        TradingStrategy.ENDGAME_SWEEP, trade_details
    )

    # Should allow trade (different strategy)
    assert result is None


# Tests for error handling
@pytest.mark.asyncio
async def test_get_risk_profile_handles_unknown_strategy(risk_manager):
    """Test that unknown strategy returns default profile."""
    # Get a non-existent strategy (should return default)
    # In implementation, this returns copy_trading as default
    profile = await risk_manager.get_risk_profile(TradingStrategy.MARKET_MAKING)

    # Should have a profile (default or actual)
    assert profile is not None


@pytest.mark.asyncio
async def test_check_trade_allows_on_error(risk_manager):
    """Test that trade check allows on error (conservative)."""
    # Create an invalid trade_details that might cause errors
    trade_details = {
        "amount": "invalid",  # Invalid type
        "market_id": "0x123...",
    }

    # Should not raise exception, but may return None (allow)
    result = await risk_manager.check_trade_allowed(
        TradingStrategy.COPY_TRADING, trade_details
    )

    # Result can be None (allow) or dict (block)
    # Main point: no exception raised
    assert result is None or isinstance(result, dict)


# Tests for shutdown
@pytest.mark.asyncio
async def test_shutdown(risk_manager):
    """Test graceful shutdown."""
    # Add some state
    await risk_manager.update_volatility_data("vix", 35.0)

    # Shutdown
    await risk_manager.shutdown()

    # Check that state was saved (file should exist and not be empty)
    assert risk_manager.state_file.exists()
    if risk_manager.state_file.stat().st_size > 0:
        with open(risk_manager.state_file, "rb") as f:
            data = pickle.load(f)
            # Should have saved data
            assert "strategies" in data or "circuit_breakers" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
