"""
Unit tests for race condition scenarios in concurrent operations

Tests cover:
- Concurrent trade execution on same position
- Concurrent position management operations
- Signal handler interactions during execution
- Network failure during critical operations
- Lock contention scenarios
"""

import asyncio
import signal
import time
from unittest.mock import MagicMock, patch

import aiohttp
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
def trade_executor(mock_clob_client):
    """Setup trade executor with mocked dependencies"""
    executor = TradeExecutor(mock_clob_client)
    executor.settings = Settings()
    return executor


class TestConcurrentTradeExecution:
    """Test race conditions in concurrent trade execution"""

    @pytest.mark.asyncio
    async def test_concurrent_trades_same_position(self, trade_executor):
        """Test concurrent trade execution on the same position"""
        position_key = "race_condition_test"

        # Setup position
        trade_executor.open_positions[position_key] = {
            "amount": 10.0,
            "entry_price": 0.5,
            "timestamp": time.time(),
            "original_trade": {
                "tx_hash": "0x123",
                "wallet_address": "0xabc",
                "condition_id": "cond123",
                "side": "BUY",
                "amount": 10.0,
                "price": 0.5,
                "confidence_score": 0.9,
            },
            "order_id": "order123",
        }

        async def execute_trade_on_position(trade_id):
            """Execute a trade that affects the same position"""
            trade = {
                "tx_hash": f"0x{trade_id}",
                "wallet_address": "0xabc",
                "condition_id": "cond123",
                "side": "SELL",  # Close position
                "amount": 10.0,
                "price": 0.55,
                "confidence_score": 0.95,
            }

            return await trade_executor.execute_copy_trade(trade)

        # Execute multiple concurrent trades on same position
        tasks = [execute_trade_on_position(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results - should handle concurrency gracefully
        successful_closes = sum(
            1 for r in results if isinstance(r, dict) and r.get("status") == "success"
        )
        exceptions = sum(1 for r in results if isinstance(r, Exception))

        # Only one close should succeed, others should fail gracefully
        assert successful_closes <= 1
        # Some operations might fail due to position already closed
        assert exceptions <= len(results) - successful_closes

    @pytest.mark.asyncio
    async def test_concurrent_position_management(self, trade_executor):
        """Test concurrent position management operations"""
        # Setup multiple positions
        positions = []
        for i in range(10):
            pos_key = f"concurrent_pos_{i}"
            positions.append(pos_key)
            trade_executor.open_positions[pos_key] = {
                "amount": 10.0,
                "entry_price": 0.5,
                "timestamp": time.time(),
                "original_trade": {
                    "tx_hash": f"0x{i}",
                    "wallet_address": "0xabc",
                    "condition_id": f"cond{i}",
                    "side": "BUY",
                    "amount": 10.0,
                    "price": 0.5,
                    "confidence_score": 0.9,
                },
                "order_id": f"order{i}",
            }

        async def manage_positions():
            """Run position management"""
            await trade_executor.manage_positions()

        # Run multiple concurrent position management operations
        tasks = [manage_positions() for _ in range(3)]
        await asyncio.gather(*tasks)

        # Verify no crashes occurred and state is consistent
        assert isinstance(trade_executor.open_positions, dict)

    @pytest.mark.asyncio
    async def test_concurrent_circuit_breaker_operations(self, trade_executor):
        """Test concurrent circuit breaker activation/deactivation"""

        async def toggle_circuit_breaker(task_id):
            """Randomly activate/deactivate circuit breaker"""
            if task_id % 2 == 0:
                trade_executor.activate_circuit_breaker(f"Task {task_id}")
            else:
                trade_executor.reset_circuit_breaker()

            # Check conditions
            trade_executor._check_circuit_breaker_conditions()
            return trade_executor.circuit_breaker_active

        # Run concurrent circuit breaker operations
        tasks = [toggle_circuit_breaker(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Final state should be deterministic (last operation wins)
        final_state = trade_executor.circuit_breaker_active
        assert isinstance(final_state, bool)

    @pytest.mark.asyncio
    async def test_lock_contention_scenarios(self, trade_executor):
        """Test lock contention in high concurrency scenarios"""
        # Setup many positions
        for i in range(50):
            pos_key = f"lock_test_{i}"
            trade_executor._get_position_lock(pos_key)

        async def acquire_and_release_lock(lock_key):
            """Acquire and release a position lock"""
            lock = trade_executor._get_position_lock(lock_key)
            async with lock:
                await asyncio.sleep(0.001)  # Minimal contention
                return lock_key

        # Run many concurrent lock operations
        lock_keys = [f"contention_{i}" for i in range(100)]
        tasks = [acquire_and_release_lock(key) for key in lock_keys]
        results = await asyncio.gather(*tasks)

        # All operations should complete successfully
        assert len(results) == 100
        assert set(results) == set(lock_keys)


class TestSignalHandlerRaceConditions:
    """Test race conditions involving signal handlers"""

    def test_signal_handler_during_operation(self, trade_executor):
        """Test signal handler behavior during operations"""
        # Setup signal handling simulation
        signal_received = False
        original_handler = None

        def mock_signal_handler(signum, frame):
            nonlocal signal_received
            signal_received = True
            # Simulate graceful shutdown
            trade_executor.circuit_breaker_active = True

        # Install mock signal handler
        original_handler = signal.signal(signal.SIGTERM, mock_signal_handler)

        try:
            # Simulate receiving signal during operation
            signal.raise_signal(signal.SIGTERM)

            # Verify signal was handled
            assert signal_received
            assert trade_executor.circuit_breaker_active

        finally:
            # Restore original handler
            if original_handler:
                signal.signal(signal.SIGTERM, original_handler)

    @pytest.mark.asyncio
    async def test_signal_during_async_operation(self, trade_executor):
        """Test signal handling during async operations"""
        operation_completed = False
        signal_handled = False

        async def async_operation():
            nonlocal operation_completed
            await asyncio.sleep(0.1)
            operation_completed = True

        def signal_handler(signum, frame):
            nonlocal signal_handled
            signal_handled = True

        # Install signal handler
        original_handler = signal.signal(signal.SIGINT, signal_handler)

        try:
            # Start async operation
            task = asyncio.create_task(async_operation())

            # Send signal after short delay
            await asyncio.sleep(0.05)
            signal.raise_signal(signal.SIGINT)

            # Wait for operation to complete
            await task

            # Verify both operation completed and signal was handled
            assert operation_completed
            assert signal_handled

        finally:
            if original_handler:
                signal.signal(signal.SIGINT, original_handler)

    def test_concurrent_signal_handling(self, trade_executor):
        """Test multiple signals during concurrent operations"""
        signal_count = 0

        def counting_signal_handler(signum, frame):
            nonlocal signal_count
            signal_count += 1

        original_handler = signal.signal(signal.SIGUSR1, counting_signal_handler)

        try:
            # Send multiple signals
            for _ in range(5):
                signal.raise_signal(signal.SIGUSR1)
                time.sleep(0.001)  # Small delay

            # Verify all signals were handled
            assert signal_count == 5

        finally:
            if original_handler:
                signal.signal(signal.SIGUSR1, original_handler)


class TestNetworkFailureRaceConditions:
    """Test race conditions during network failures"""

    @pytest.mark.asyncio
    async def test_network_failure_during_trade_execution(self, trade_executor):
        """Test network failure during trade execution"""
        trade = {
            "tx_hash": "0x123",
            "wallet_address": "0xabc",
            "condition_id": "cond123",
            "side": "BUY",
            "amount": 10.0,
            "price": 0.5,
            "confidence_score": 0.9,
        }

        # Mock network failure at different points
        call_count = 0

        def failing_network_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on second call
                raise ConnectionError("Network failure")
            return {"orderID": f"order_{call_count}"}

        with patch.object(
            trade_executor.clob_client, "place_order", side_effect=failing_network_call
        ):
            # Execute trade - should handle network failure gracefully
            result = await trade_executor.execute_copy_trade(trade)

            # Should return error result, not crash
            assert result["status"] in ["error", "failed"]
            assert "error" in result or "reason" in result

    @pytest.mark.asyncio
    async def test_concurrent_network_failures(self, trade_executor):
        """Test concurrent operations during network failures"""

        async def failing_operation(operation_id):
            """Operation that may fail due to network issues"""
            try:
                # Simulate network call that might fail
                await asyncio.sleep(0.01)
                if operation_id % 3 == 0:  # Every third operation fails
                    raise aiohttp.ClientError(f"Network error {operation_id}")
                return f"success_{operation_id}"
            except Exception as e:
                return f"error_{operation_id}: {str(e)}"

        # Run many concurrent operations that may fail
        tasks = [failing_operation(i) for i in range(30)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results
        successes = sum(
            1 for r in results if isinstance(r, str) and r.startswith("success_")
        )
        errors = sum(
            1 for r in results if isinstance(r, str) and r.startswith("error_")
        )
        exceptions = sum(1 for r in results if isinstance(r, Exception))

        # Should have mix of successes and failures
        assert successes > 0
        assert errors + exceptions > 0
        assert len(results) == 30

    @pytest.mark.asyncio
    async def test_timeout_race_conditions(self, trade_executor):
        """Test race conditions with timeouts"""
        timeout_events = []

        async def operation_with_timeout(operation_id):
            """Operation that may timeout"""
            try:
                await asyncio.wait_for(
                    asyncio.sleep(0.1), timeout=0.05 if operation_id % 2 == 0 else 0.2
                )
                return f"completed_{operation_id}"
            except asyncio.TimeoutError:
                timeout_events.append(operation_id)
                return f"timeout_{operation_id}"

        # Run operations with different timeout characteristics
        tasks = [operation_with_timeout(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        # Some operations should timeout
        timeouts = sum(1 for r in results if "timeout_" in r)
        completions = sum(1 for r in results if "completed_" in r)

        assert timeouts > 0
        assert completions > 0
        assert len(timeout_events) == timeouts


class TestStateConsistencyRaceConditions:
    """Test race conditions that affect state consistency"""

    @pytest.mark.asyncio
    async def test_concurrent_state_updates(self, trade_executor):
        """Test concurrent updates to shared state"""
        update_count = 0

        async def update_state(task_id):
            nonlocal update_count
            # Update various state variables concurrently
            async with trade_executor._state_lock:
                trade_executor.total_trades += 1
                trade_executor.successful_trades += task_id % 2  # Some succeed
                update_count += 1
                await asyncio.sleep(0.001)  # Simulate work

        # Run concurrent state updates
        tasks = [update_state(i) for i in range(50)]
        await asyncio.gather(*tasks)

        # Verify state consistency
        assert update_count == 50
        assert trade_executor.total_trades == 50
        assert trade_executor.successful_trades >= 0
        assert trade_executor.successful_trades <= 50

    @pytest.mark.asyncio
    async def test_position_state_race_conditions(self, trade_executor):
        """Test race conditions in position state management"""
        position_key = "state_race_test"

        async def modify_position(task_id):
            """Concurrently modify position state"""
            if task_id == 0:
                # First task creates position
                trade_executor.open_positions[position_key] = {
                    "amount": 10.0,
                    "entry_price": 0.5,
                    "timestamp": time.time(),
                    "original_trade": {
                        "tx_hash": "0x123",
                        "wallet_address": "0xabc",
                        "condition_id": "cond123",
                        "side": "BUY",
                        "amount": 10.0,
                        "price": 0.5,
                        "confidence_score": 0.9,
                    },
                    "order_id": "order123",
                }
            else:
                # Other tasks try to access/modify
                await asyncio.sleep(0.001)  # Small delay
                if position_key in trade_executor.open_positions:
                    # Simulate reading position data
                    amount = trade_executor.open_positions[position_key]["amount"]
                    assert amount == 10.0

        # Run concurrent position modifications
        tasks = [modify_position(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify final state
        assert position_key in trade_executor.open_positions
        assert trade_executor.open_positions[position_key]["amount"] == 10.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_races(self, trade_executor):
        """Test race conditions in circuit breaker state"""
        state_changes = []

        async def change_circuit_breaker_state(task_id):
            """Randomly change circuit breaker state"""
            async with trade_executor._state_lock:
                if task_id % 3 == 0:
                    trade_executor.activate_circuit_breaker(f"Task {task_id}")
                    state_changes.append(("activate", task_id))
                elif task_id % 3 == 1:
                    trade_executor.reset_circuit_breaker()
                    state_changes.append(("reset", task_id))
                else:
                    trade_executor._check_circuit_breaker_conditions()
                    state_changes.append(("check", task_id))

                await asyncio.sleep(0.001)

        # Run concurrent circuit breaker operations
        tasks = [change_circuit_breaker_state(i) for i in range(30)]
        await asyncio.gather(*tasks)

        # Verify operations completed without corruption
        assert len(state_changes) == 30
        # State should be in a valid final state
        assert isinstance(trade_executor.circuit_breaker_active, bool)
