#!/usr/bin/env python3
"""
Integration test for circuit breaker with position manager

Tests that circuit breaker properly integrates with trade executor
and position management scenarios.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.circuit_breaker import CircuitBreaker


async def test_circuit_breaker_basic():
    """Test basic circuit breaker functionality"""
    print("🧪 Testing basic circuit breaker functionality...")

    # Create circuit breaker
    cb = CircuitBreaker(
        max_daily_loss=100.0,
        wallet_address="0x1234567890abcdef1234567890abcdef12345678",
        state_file=Path("data/test_circuit_breaker_state.json"),
        alert_on_activation=False,
    )

    # Test: No circuit breaker initially
    result = await cb.check_trade_allowed("test_trade_1")
    assert result is None, "Circuit breaker should allow trades initially"
    print("✅ Circuit breaker allows trades initially")

    # Test: Record losses up to limit
    await cb.record_loss(50.0)
    await cb.record_loss(50.0)  # Total: 100.0

    state = cb.get_state()
    assert state["active"] is True, "Circuit breaker should activate at limit"
    assert state["daily_loss"] == 100.0, (
        f"Daily loss should be 100.0, got {state['daily_loss']}"
    )
    print("✅ Circuit breaker activates at daily loss limit")

    # Test: Trade blocked when active
    result = await cb.check_trade_allowed("test_trade_2")
    assert result is not None, "Circuit breaker should block trades when active"
    assert result["status"] == "skipped", "Blocked trade should have 'skipped' status"
    print("✅ Circuit breaker blocks trades when active")

    # Test: Reset circuit breaker
    await cb.reset("Test reset")
    state = cb.get_state()
    assert state["active"] is False, "Circuit breaker should be inactive after reset"
    print("✅ Circuit breaker resets correctly")

    print("✅ Basic circuit breaker tests passed!\n")


async def test_consecutive_losses():
    """Test 5 consecutive losses trigger"""
    print("🧪 Testing consecutive losses trigger...")

    cb = CircuitBreaker(
        max_daily_loss=1000.0,  # High limit to avoid daily loss trigger
        wallet_address="0x1234567890abcdef1234567890abcdef12345678",
        state_file=Path("data/test_circuit_breaker_state.json"),
        alert_on_activation=False,
    )

    # Record 4 losses (should not trigger)
    for i in range(4):
        await cb.record_loss(10.0)
        state = cb.get_state()
        assert state["active"] is False, (
            f"Circuit breaker should not activate after {i + 1} losses"
        )
        assert state["consecutive_losses"] == i + 1, (
            f"Consecutive losses should be {i + 1}"
        )

    # Record 5th loss (should trigger)
    await cb.record_loss(10.0)
    state = cb.get_state()
    assert state["active"] is True, (
        "Circuit breaker should activate after 5 consecutive losses"
    )
    assert state["consecutive_losses"] == 5, "Consecutive losses should be 5"
    print("✅ 5 consecutive losses trigger circuit breaker")

    # Test: Profit resets consecutive losses
    await cb.reset("Test reset")
    await cb.record_loss(10.0)
    await cb.record_loss(10.0)
    await cb.record_profit(20.0)  # Profit should reset counter
    state = cb.get_state()
    assert state["consecutive_losses"] == 0, "Profit should reset consecutive losses"
    print("✅ Profit resets consecutive losses counter")

    print("✅ Consecutive losses tests passed!\n")


async def test_daily_loss_reset():
    """Test daily loss reset at UTC midnight"""
    print("🧪 Testing daily loss reset at UTC midnight...")

    cb = CircuitBreaker(
        max_daily_loss=100.0,
        wallet_address="0x1234567890abcdef1234567890abcdef12345678",
        state_file=Path("data/test_circuit_breaker_state.json"),
        alert_on_activation=False,
    )

    # Record some losses
    await cb.record_loss(50.0)
    state = cb.get_state()
    assert state["daily_loss"] == 50.0, "Daily loss should be 50.0"

    # Simulate crossing midnight UTC
    from datetime import datetime, timedelta, timezone

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    cb._state.last_reset_date = yesterday

    # Check and reset
    await cb._check_and_reset_daily_loss()

    # Daily loss should be reset
    state = cb.get_state()
    assert state["daily_loss"] == 0.0, (
        "Daily loss should be reset to 0.0 after midnight"
    )
    assert state["consecutive_losses"] == 0, "Consecutive losses should be reset"
    print("✅ Daily loss resets at UTC midnight")

    print("✅ Daily loss reset tests passed!\n")


async def test_recovery_eta():
    """Test recovery ETA calculation"""
    print("🧪 Testing recovery ETA calculation...")

    cb = CircuitBreaker(
        max_daily_loss=100.0,
        wallet_address="0x1234567890abcdef1234567890abcdef12345678",
        state_file=Path("data/test_circuit_breaker_state.json"),
        alert_on_activation=False,
    )

    # Activate circuit breaker
    await cb.record_loss(100.0)

    state = cb.get_state()
    assert state["recovery_eta"] != "N/A", "Recovery ETA should be calculated"
    assert "minutes" in state["recovery_eta"] or "h" in state["recovery_eta"], (
        "Recovery ETA should include time"
    )
    print(f"✅ Recovery ETA: {state['recovery_eta']}")

    print("✅ Recovery ETA tests passed!\n")


async def test_race_conditions():
    """Test atomic state transitions (no race conditions)"""
    print("🧪 Testing atomic state transitions...")

    cb = CircuitBreaker(
        max_daily_loss=100.0,
        wallet_address="0x1234567890abcdef1234567890abcdef12345678",
        state_file=Path("data/test_circuit_breaker_state.json"),
        alert_on_activation=False,
    )

    # Concurrent loss recording
    tasks = [cb.record_loss(10.0) for _ in range(10)]
    await asyncio.gather(*tasks)

    # Daily loss should be exactly 100.0 (no race conditions)
    state = cb.get_state()
    assert state["daily_loss"] == 100.0, (
        f"Daily loss should be exactly 100.0, got {state['daily_loss']}"
    )
    assert state["active"] is True, "Circuit breaker should be active"
    print("✅ Concurrent loss recording is atomic (no race conditions)")

    # Concurrent trade checks
    await cb.reset("Test reset")
    await cb.record_loss(100.0)  # Reactivate

    tasks = [cb.check_trade_allowed(f"trade_{i}") for i in range(10)]
    results = await asyncio.gather(*tasks)

    # All should be blocked
    assert all(r is not None for r in results), "All trades should be blocked"
    assert all(r["status"] == "skipped" for r in results), (
        "All trades should have 'skipped' status"
    )
    print("✅ Concurrent trade checks work correctly")

    print("✅ Race condition tests passed!\n")


async def main():
    """Run all integration tests"""
    print("=" * 60)
    print("Circuit Breaker Integration Tests")
    print("=" * 60)
    print()

    try:
        await test_circuit_breaker_basic()
        await test_consecutive_losses()
        await test_daily_loss_reset()
        await test_recovery_eta()
        await test_race_conditions()

        print("=" * 60)
        print("✅ All integration tests passed!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
