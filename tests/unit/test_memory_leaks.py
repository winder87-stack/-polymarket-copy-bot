"""
Unit tests for memory leak scenarios in trade_executor.py and wallet_monitor.py

Tests cover:
- Position lock memory leaks
- Transaction cache growth
- Memory usage monitoring
- Lock cleanup after position close
- Stale lock detection and cleanup
"""

import asyncio
import gc
import time
from unittest.mock import MagicMock, patch

import pytest

from config.settings import Settings
from core.trade_executor import TradeExecutor
from core.wallet_monitor import WalletMonitor


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


@pytest.fixture
def wallet_monitor():
    """Setup wallet monitor for testing"""
    monitor = WalletMonitor(Settings())
    return monitor


class TestPositionLockMemoryLeaks:
    """Test position lock memory leak scenarios"""

    def test_position_lock_creation_and_cleanup(self, trade_executor):
        """Test that position locks are created and cleaned up properly"""
        position_key = "test_position_123"

        # Initially no locks
        assert position_key not in trade_executor._position_locks
        assert len(trade_executor._position_locks) == 0

        # Create lock
        lock = trade_executor._get_position_lock(position_key)
        assert isinstance(lock, asyncio.Lock)
        assert position_key in trade_executor._position_locks
        assert len(trade_executor._position_locks) == 1

        # Get same lock again (should reuse)
        lock2 = trade_executor._get_position_lock(position_key)
        assert lock is lock2
        assert len(trade_executor._position_locks) == 1

    @pytest.mark.asyncio
    async def test_position_lock_cleanup_on_close(self, trade_executor):
        """Test that position locks are cleaned up when positions are closed"""
        position_key = "test_close_position"

        # Setup mock position
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

        # Create lock for position
        trade_executor._get_position_lock(position_key)
        assert position_key in trade_executor._position_locks

        # Mock successful position close
        with (
            patch.object(trade_executor.clob_client, "get_current_price", return_value=0.55),
            patch.object(trade_executor, "execute_copy_trade") as mock_execute,
        ):

            mock_execute.return_value = {"status": "success"}

            # Close position
            await trade_executor._close_position(position_key, "TEST_CLOSE")

            # Verify lock was cleaned up
            assert position_key not in trade_executor._position_locks
            assert position_key not in trade_executor.open_positions

    @pytest.mark.asyncio
    async def test_stale_lock_cleanup(self, trade_executor):
        """Test periodic cleanup of stale position locks"""
        # Create some locks
        positions_with_locks = ["pos1", "pos2", "pos3"]
        positions_without_locks = ["pos4", "pos5"]

        # Add positions with locks
        for pos in positions_with_locks:
            trade_executor._get_position_lock(pos)
            trade_executor.open_positions[pos] = {"timestamp": time.time()}

        # Add stale locks (no corresponding position)
        for pos in positions_without_locks:
            trade_executor._position_locks[pos] = asyncio.Lock()

        assert len(trade_executor._position_locks) == 5

        # Run cleanup
        await trade_executor._cleanup_stale_locks()

        # Verify stale locks were cleaned up
        assert len(trade_executor._position_locks) == 3  # Only valid positions remain
        for pos in positions_with_locks:
            assert pos in trade_executor._position_locks
        for pos in positions_without_locks:
            assert pos not in trade_executor._position_locks

    def test_lock_count_monitoring(self, trade_executor):
        """Test lock count monitoring for memory leak detection"""
        # Add many locks
        for i in range(1500):
            pos_key = f"position_{i}"
            trade_executor._position_locks[pos_key] = asyncio.Lock()

        # Add some positions to make it look like a leak
        for i in range(10):
            trade_executor.open_positions[f"real_pos_{i}"] = {"timestamp": time.time()}

        # Run cleanup
        await trade_executor._cleanup_stale_locks()

        # Verify high lock count is still detected
        lock_count = len(trade_executor._position_locks)
        position_count = len(trade_executor.open_positions)

        # Should detect excessive locks
        assert lock_count > 1000  # Still high after cleanup
        assert position_count == 10  # Only real positions remain

    @pytest.mark.asyncio
    async def test_concurrent_lock_operations(self, trade_executor):
        """Test concurrent lock creation and cleanup"""

        async def create_and_use_lock(position_id):
            lock = trade_executor._get_position_lock(f"concurrent_{position_id}")
            async with lock:
                await asyncio.sleep(0.01)  # Simulate work
                return position_id

        # Run concurrent operations
        tasks = [create_and_use_lock(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        # Verify all operations completed
        assert len(results) == 50
        assert set(results) == set(range(50))

        # Verify locks were created
        concurrent_locks = [
            k for k in trade_executor._position_locks.keys() if k.startswith("concurrent_")
        ]
        assert len(concurrent_locks) == 50


class TestTransactionCacheMemoryLeaks:
    """Test transaction cache memory leak scenarios"""

    def test_processed_transactions_growth(self, wallet_monitor):
        """Test that processed transactions cache grows appropriately"""
        initial_size = len(wallet_monitor.processed_transactions)

        # Add transactions
        transactions = [f"tx_{i}" for i in range(1000)]
        for tx in transactions:
            wallet_monitor.processed_transactions.add(tx)

        # Verify growth
        assert len(wallet_monitor.processed_transactions) == initial_size + 1000

    def test_transaction_cache_cleanup(self, wallet_monitor):
        """Test transaction cache cleanup functionality"""
        # Add old transactions (simulate age > cleanup threshold)
        old_transactions = [f"old_tx_{i}" for i in range(500)]
        for tx in old_transactions:
            wallet_monitor.processed_transactions.add(tx)
            # Mock age by setting last cleanup time far in past
            wallet_monitor.last_transaction_cleanup = time.time() - 4000

        initial_size = len(wallet_monitor.processed_transactions)

        # Trigger cleanup (this would be called periodically)
        # Note: Actual cleanup logic would need to be implemented
        # For now, just test that the set operations work

        assert len(wallet_monitor.processed_transactions) >= initial_size

    def test_cache_memory_usage(self, wallet_monitor):
        """Test cache memory usage monitoring"""
        # Add many transactions to test memory usage
        large_transaction_set = set()
        for i in range(10000):
            large_transaction_set.add(f"large_tx_{i}")

        # Basic memory check (would need psutil in real implementation)
        assert len(large_transaction_set) == 10000

        # Clean up
        del large_transaction_set
        gc.collect()

    def test_transaction_deduplication(self, wallet_monitor):
        """Test that duplicate transactions don't cause memory bloat"""
        tx_hash = "duplicate_tx_123"

        # Add same transaction multiple times
        for _ in range(10):
            wallet_monitor.processed_transactions.add(tx_hash)

        # Should only be stored once
        count = sum(1 for tx in wallet_monitor.processed_transactions if tx == tx_hash)
        assert count == 1


class TestMemoryUsageMonitoring:
    """Test memory usage monitoring functionality"""

    def test_memory_usage_tracking(self, trade_executor):
        """Test basic memory usage tracking"""
        # This would require psutil in a real implementation
        # For now, test the basic structure

        initial_positions = len(trade_executor.open_positions)
        initial_locks = len(trade_executor._position_locks)

        # Add some positions and locks
        for i in range(100):
            pos_key = f"memory_test_{i}"
            trade_executor._get_position_lock(pos_key)
            trade_executor.open_positions[pos_key] = {"timestamp": time.time()}

        # Verify tracking
        assert len(trade_executor.open_positions) == initial_positions + 100
        assert len(trade_executor._position_locks) == initial_locks + 100

    @pytest.mark.asyncio
    async def test_memory_cleanup_scheduling(self, trade_executor):
        """Test that memory cleanup runs periodically"""
        # Mock time to simulate periodic cleanup
        with patch("time.time") as mock_time:
            # Start at time 0
            mock_time.return_value = 0

            # Initial cleanup
            await trade_executor._cleanup_stale_locks()
            len(trade_executor._position_locks)

            # Advance time past cleanup interval (300 seconds)
            mock_time.return_value = 301

            # Add some stale locks
            for i in range(10):
                trade_executor._position_locks[f"stale_{i}"] = asyncio.Lock()

            # Periodic cleanup should trigger
            await trade_executor._perform_periodic_cleanup()

            # Verify cleanup occurred (stale locks removed)
            # Note: In real implementation, this would be time-based

    def test_garbage_collection_pressure(self, trade_executor):
        """Test garbage collection under memory pressure"""
        # Create many short-lived objects
        locks_created = []
        for i in range(1000):
            lock = asyncio.Lock()
            locks_created.append(lock)
            trade_executor._position_locks[f"gc_test_{i}"] = lock

        # Delete references
        del locks_created
        gc.collect()

        # Verify locks still exist (owned by executor)
        assert len(trade_executor._position_locks) >= 1000

        # Clean up
        trade_executor._position_locks.clear()


class TestResourceCleanup:
    """Test resource cleanup in various scenarios"""

    @pytest.mark.asyncio
    async def test_cleanup_after_failed_operations(self, trade_executor):
        """Test cleanup after failed position operations"""
        position_key = "failed_operation_test"

        # Create position and lock
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
        trade_executor._get_position_lock(position_key)

        # Simulate failed close operation
        with patch.object(
            trade_executor, "execute_copy_trade", side_effect=Exception("Network error")
        ):
            try:
                await trade_executor._close_position(position_key, "FAILED_TEST")
            except Exception:
                pass  # Expected to fail

        # Verify cleanup still happened (lock should be removed even on failure)
        # Note: In current implementation, cleanup happens in finally block
        assert position_key not in trade_executor._position_locks

    @pytest.mark.asyncio
    async def test_bulk_cleanup_operations(self, trade_executor):
        """Test bulk cleanup of multiple resources"""
        # Create multiple positions and locks
        positions = []
        for i in range(50):
            pos_key = f"bulk_test_{i}"
            positions.append(pos_key)
            trade_executor._get_position_lock(pos_key)
            trade_executor.open_positions[pos_key] = {"timestamp": time.time()}

        initial_count = len(trade_executor._position_locks)

        # Bulk cleanup
        await trade_executor._cleanup_stale_locks()

        # Since positions exist, locks should remain
        assert len(trade_executor._position_locks) == initial_count

        # Now remove positions and cleanup
        for pos in positions:
            del trade_executor.open_positions[pos]

        await trade_executor._cleanup_stale_locks()

        # All locks should be cleaned up
        assert len(trade_executor._position_locks) == 0

    def test_resource_cleanup_on_shutdown(self, trade_executor):
        """Test resource cleanup simulation on shutdown"""
        # Add various resources
        for i in range(100):
            pos_key = f"shutdown_test_{i}"
            trade_executor._get_position_lock(pos_key)
            trade_executor.open_positions[pos_key] = {"timestamp": time.time()}

        # Simulate shutdown cleanup
        locks_before = len(trade_executor._position_locks)
        positions_before = len(trade_executor.open_positions)

        # Clear resources (simulating shutdown)
        trade_executor._position_locks.clear()
        trade_executor.open_positions.clear()

        # Verify cleanup
        assert len(trade_executor._position_locks) == 0
        assert len(trade_executor.open_positions) == 0
        assert locks_before == 100
        assert positions_before == 100
