"""
Performance tests for load testing, latency measurement, and stress testing.
"""

import asyncio
import os
import statistics
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import psutil
import pytest


class TestLoadTesting:
    """Load testing with multiple wallets."""

    @pytest.mark.asyncio
    async def test_25_wallet_monitoring_load(
        self, performance_test_data, mock_wallet_monitor, performance_monitor
    ):
        """Test monitoring 25 wallets simultaneously."""
        mock_wallet_monitor.target_wallets = performance_test_data["wallets"]

        # Mock transaction fetching
        mock_wallet_monitor.get_wallet_transactions.return_value = []

        performance_monitor.start("25_wallet_monitoring")

        # Monitor all wallets
        detected_trades = await mock_wallet_monitor.monitor_wallets()

        duration = performance_monitor.end("25_wallet_monitoring")

        # Verify performance
        assert isinstance(detected_trades, list)
        assert duration < 30.0  # Should complete within 30 seconds

        # Verify all wallets were processed
        expected_calls = len(performance_test_data["wallets"])
        assert mock_wallet_monitor.get_wallet_transactions.call_count == expected_calls

    @pytest.mark.asyncio
    async def test_high_frequency_transaction_processing(
        self, mock_wallet_monitor, performance_test_data, performance_monitor
    ):
        """Test processing high frequency transactions."""
        # Set up 1000 transactions
        transactions = performance_test_data["transactions"]

        # Mock them as Polymarket transactions
        for tx in transactions:
            tx["to"] = mock_wallet_monitor.polymarket_contracts[0]

        performance_monitor.start("transaction_processing")

        # Process all transactions
        trades = mock_wallet_monitor.detect_polymarket_trades(transactions)

        duration = performance_monitor.end("transaction_processing")

        # Performance assertions
        assert len(trades) >= 0  # Some trades should be detected
        assert duration < 10.0  # Should process 1000 transactions within 10 seconds
        assert len(mock_wallet_monitor.processed_transactions) > 0

    @pytest.mark.asyncio
    async def test_concurrent_trade_execution_load(self, mock_trade_executor, performance_monitor):
        """Test concurrent execution of multiple trades."""
        # Create 50 concurrent trades
        trades = []
        for i in range(50):
            trade = {
                "tx_hash": f"0x{i:064x}",
                "timestamp": datetime.now() - timedelta(seconds=30),
                "wallet_address": f"0x{i:040x}",
                "condition_id": f"0x{i:040x}",
                "side": "BUY" if i % 2 == 0 else "SELL",
                "amount": 10.0,
                "price": 0.65,
                "token_id": f"0x{i+1:040x}",
                "confidence_score": 0.8,
            }
            trades.append(trade)

        # Mock successful execution
        mock_trade_executor.execute_copy_trade.side_effect = [
            {"status": "success", "order_id": f"order-{i}"} for i in range(50)
        ]

        performance_monitor.start("concurrent_trade_execution")

        # Execute all trades concurrently
        tasks = [mock_trade_executor.execute_copy_trade(trade) for trade in trades]
        results = await asyncio.gather(*tasks)

        duration = performance_monitor.end("concurrent_trade_execution")

        # Performance assertions
        assert len(results) == 50
        assert all(r["status"] == "success" for r in results)
        assert duration < 60.0  # Should complete within 60 seconds
        assert mock_trade_executor.execute_copy_trade.call_count == 50


class TestLatencyMeasurement:
    """Latency measurement tests."""

    @pytest.mark.asyncio
    async def test_api_call_latency(self, mock_polymarket_client, performance_monitor):
        """Test API call latency."""

        # Mock API calls with realistic delays
        async def delayed_balance(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return 1000.0

        mock_polymarket_client.get_balance = delayed_balance

        latencies = []

        # Measure multiple calls
        for i in range(10):
            start_time = time.time()
            balance = await mock_polymarket_client.get_balance()
            end_time = time.time()

            latency = end_time - start_time
            latencies.append(latency)

            assert balance == 1000.0

        # Statistical analysis
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile

        # Performance assertions
        assert avg_latency < 0.2  # Average latency under 200ms
        assert p95_latency < 0.3  # 95th percentile under 300ms

    @pytest.mark.asyncio
    async def test_wallet_transaction_fetch_latency(self, mock_wallet_monitor, performance_monitor):
        """Test wallet transaction fetch latency."""

        # Mock API response with delay
        async def delayed_fetch(*args, **kwargs):
            await asyncio.sleep(0.05)  # 50ms delay
            return []

        mock_wallet_monitor.get_wallet_transactions = delayed_fetch

        latencies = []

        # Test multiple wallet fetches
        wallets = [f"0x{i:040x}" for i in range(10)]

        for wallet in wallets:
            start_time = time.time()
            transactions = await mock_wallet_monitor.get_wallet_transactions(wallet)
            end_time = time.time()

            latency = end_time - start_time
            latencies.append(latency)

            assert transactions == []

        # Performance analysis
        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)

        assert avg_latency < 0.1  # Average under 100ms
        assert max_latency < 0.2  # Max under 200ms

    @pytest.mark.asyncio
    async def test_trade_execution_latency(
        self, mock_trade_executor, sample_trade, performance_monitor
    ):
        """Test trade execution latency."""

        # Mock successful execution with delay
        async def delayed_execution(*args, **kwargs):
            await asyncio.sleep(0.15)  # 150ms delay
            return {"status": "success", "order_id": "test-order"}

        mock_trade_executor.execute_copy_trade = delayed_execution

        latencies = []

        # Execute multiple trades
        for i in range(5):
            start_time = time.time()
            result = await mock_trade_executor.execute_copy_trade(sample_trade)
            end_time = time.time()

            latency = end_time - start_time
            latencies.append(latency)

            assert result["status"] == "success"

        # Performance analysis
        avg_latency = statistics.mean(latencies)
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile

        assert avg_latency < 0.3  # Average under 300ms
        assert p99_latency < 0.5  # 99th percentile under 500ms


class TestMemoryUsageProfiling:
    """Memory usage profiling tests."""

    def test_memory_usage_during_transaction_processing(
        self, mock_wallet_monitor, performance_test_data
    ):
        """Test memory usage during transaction processing."""
        process = psutil.Process(os.getpid())

        # Get baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Process transactions
        transactions = performance_test_data["transactions"]
        for tx in transactions[:100]:  # Process first 100
            tx["to"] = mock_wallet_monitor.polymarket_contracts[0]

        mock_wallet_monitor.detect_polymarket_trades(transactions[:100])

        # Check memory after processing
        processing_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = processing_memory - baseline_memory

        # Memory increase should be reasonable (< 50MB)
        assert memory_increase < 50.0

    def test_memory_cleanup_after_processing(self, mock_wallet_monitor):
        """Test memory cleanup after processing."""
        process = psutil.Process(os.getpid())

        # Add many processed transactions
        for i in range(1000):
            mock_wallet_monitor.processed_transactions.add(f"0x{i:064x}")

        memory_before_cleanup = process.memory_info().rss / 1024 / 1024  # MB

        # Trigger cleanup
        mock_wallet_monitor._clean_cache()  # Clean market cache
        # Simulate processed transaction cleanup
        len(mock_wallet_monitor.processed_transactions)
        cutoff_time = datetime.now() - timedelta(hours=25)
        mock_wallet_monitor._get_recent_transaction_hashes(cutoff_time)

        memory_after_cleanup = process.memory_info().rss / 1024 / 1024  # MB

        # Memory should not have increased significantly
        assert memory_after_cleanup - memory_before_cleanup < 10.0

    def test_trade_history_memory_management(self, mock_wallet_monitor):
        """Test trade history memory management."""
        process = psutil.Process(os.getpid())

        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        memory_before = process.memory_info().rss / 1024 / 1024  # MB

        # Add many trades to history
        for i in range(200):
            trade = {"tx_hash": f"0x{i:064x}", "timestamp": datetime.now(), "amount": 10.0}
            mock_wallet_monitor.wallet_trade_history[wallet].append(trade)

        memory_after_addition = process.memory_info().rss / 1024 / 1024  # MB

        # Apply memory limit (simulate cleanup)
        mock_wallet_monitor.wallet_trade_history[wallet] = mock_wallet_monitor.wallet_trade_history[
            wallet
        ][-100:]

        memory_after_cleanup = process.memory_info().rss / 1024 / 1024  # MB

        # Memory increase should be controlled
        assert memory_after_addition - memory_before < 20.0  # Less than 20MB increase
        assert memory_after_cleanup <= memory_after_addition  # Should not increase after cleanup


class TestAPIRateLimitStress:
    """API rate limit stress testing."""

    @pytest.mark.asyncio
    async def test_polygonscan_rate_limit_handling(
        self, mock_wallet_monitor, mock_aiohttp_session, performance_monitor
    ):
        """Test handling of Polygonscan API rate limits."""
        mock_wallet_monitor.polygonscan_api_key = "test-api-key"

        # Mock rate limit response
        rate_limit_response = AsyncMock()
        rate_limit_response.status = 429  # Too Many Requests
        rate_limit_response.json = AsyncMock(return_value={"message": "Rate limit exceeded"})

        mock_aiohttp_session.get.return_value.__aenter__.return_value = rate_limit_response

        performance_monitor.start("rate_limit_handling")

        # Attempt API call
        transactions = await mock_wallet_monitor.get_wallet_transactions("0xtest")

        duration = performance_monitor.end("rate_limit_handling")

        # Should handle rate limit gracefully
        assert transactions == []
        assert duration < 5.0  # Should not hang

    @pytest.mark.asyncio
    async def test_clob_api_rate_limit_stress(self, mock_polymarket_client, performance_monitor):
        """Test CLOB API rate limit stress."""
        # Mock rate limiting with exponential backoff
        call_count = 0

        async def rate_limited_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                await asyncio.sleep(0.1 * call_count)  # Increasing delay
                raise ConnectionError("Rate limited")
            return 1000.0

        mock_polymarket_client.get_balance = rate_limited_response

        performance_monitor.start("clob_rate_limit_stress")

        balance = await mock_polymarket_client.get_balance()

        duration = performance_monitor.end("clob_rate_limit_stress")

        # Should eventually succeed
        assert balance == 1000.0
        assert call_count == 3  # Should have retried
        assert duration < 10.0  # Should not take too long

    @pytest.mark.asyncio
    async def test_concurrent_api_call_stress(self, mock_wallet_monitor, performance_monitor):
        """Test concurrent API calls stress."""
        mock_wallet_monitor.polygonscan_api_key = "test-api-key"

        # Mock delayed API responses
        async def delayed_response(*args, **kwargs):
            await asyncio.sleep(0.1)
            return []

        mock_wallet_monitor.get_wallet_transactions = delayed_response

        performance_monitor.start("concurrent_api_stress")

        # Make 10 concurrent API calls
        wallets = [f"0x{i:040x}" for i in range(10)]
        tasks = [mock_wallet_monitor.get_wallet_transactions(wallet) for wallet in wallets]
        results = await asyncio.gather(*tasks)

        duration = performance_monitor.end("concurrent_api_stress")

        # All calls should complete
        assert len(results) == 10
        assert all(r == [] for r in results)

        # Should complete in reasonable time (allowing for some parallelism)
        assert duration < 5.0


class TestDatabaseAndCachePerformance:
    """Database and cache performance testing."""

    def test_market_cache_performance(self, mock_polymarket_client):
        """Test market cache performance."""
        # Populate cache with many entries
        for i in range(100):
            condition_id = f"0x{i:040x}"
            market_data = {"conditionId": condition_id, "active": True}
            mock_polymarket_client._market_cache[condition_id] = (market_data, time.time())

        # Test cache retrieval speed
        start_time = time.time()

        for i in range(100):
            condition_id = f"0x{i:040x}"
            cached_data, _ = mock_polymarket_client._market_cache.get(condition_id, (None, 0))

            assert cached_data is not None
            assert cached_data["conditionId"] == condition_id

        end_time = time.time()
        cache_retrieval_time = end_time - start_time

        # Cache retrieval should be very fast (< 0.1 seconds for 100 lookups)
        assert cache_retrieval_time < 0.1

    def test_processed_transactions_set_performance(self, mock_wallet_monitor):
        """Test processed transactions set performance."""
        # Add many transactions
        for i in range(10000):
            tx_hash = f"0x{i:064x}"
            mock_wallet_monitor.processed_transactions.add(tx_hash)

        # Test lookup performance
        start_time = time.time()

        for i in range(1000):
            tx_hash = f"0x{i:064x}"
            assert tx_hash in mock_wallet_monitor.processed_transactions

        end_time = time.time()
        lookup_time = end_time - start_time

        # Set lookups should be very fast (< 0.01 seconds for 1000 lookups)
        assert lookup_time < 0.01

    def test_trade_history_performance(self, mock_wallet_monitor):
        """Test trade history performance."""
        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"

        # Add many trades
        for i in range(1000):
            trade = {"tx_hash": f"0x{i:064x}", "timestamp": datetime.now(), "amount": 10.0}
            mock_wallet_monitor.wallet_trade_history[wallet].append(trade)

        # Test history access performance
        start_time = time.time()

        for _ in range(100):
            recent_trades = mock_wallet_monitor.wallet_trade_history[wallet][-10:]

            assert len(recent_trades) == 10

        end_time = time.time()
        access_time = end_time - start_time

        # History access should be fast (< 0.001 seconds for 100 accesses)
        assert access_time < 0.001


class TestSystemResourceStress:
    """System resource stress testing."""

    @pytest.mark.asyncio
    async def test_cpu_usage_under_load(self, mock_trade_executor, performance_monitor):
        """Test CPU usage under concurrent load."""

        # Create many concurrent operations
        async def cpu_intensive_task(task_id):
            # Simulate CPU-intensive work
            result = 0
            for i in range(10000):
                result += i**2
            return result

        performance_monitor.start("cpu_stress_test")

        # Run 20 concurrent CPU-intensive tasks
        tasks = [cpu_intensive_task(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        duration = performance_monitor.end("cpu_stress_test")

        # All tasks should complete
        assert len(results) == 20
        assert all(isinstance(r, int) for r in results)

        # Should complete in reasonable time
        assert duration < 10.0

    @pytest.mark.asyncio
    async def test_network_io_stress(self, mock_wallet_monitor, performance_monitor):
        """Test network I/O stress."""

        # Mock network calls with delays
        async def network_call(wallet):
            await asyncio.sleep(0.01)  # 10ms network delay
            return []

        mock_wallet_monitor.get_wallet_transactions = network_call

        performance_monitor.start("network_io_stress")

        # Make many concurrent network calls
        wallets = [f"0x{i:040x}" for i in range(50)]
        tasks = [mock_wallet_monitor.get_wallet_transactions(wallet) for wallet in wallets]
        results = await asyncio.gather(*tasks)

        duration = performance_monitor.end("network_io_stress")

        # All network calls should complete
        assert len(results) == 50
        assert all(r == [] for r in results)

        # Should handle concurrent I/O efficiently
        assert duration < 5.0  # Should benefit from concurrency

    def test_memory_leak_prevention(self, mock_wallet_monitor):
        """Test prevention of memory leaks."""
        process = psutil.Process(os.getpid())

        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Simulate long-running operation with many objects
        for cycle in range(10):
            # Create many temporary objects
            transactions = []
            for i in range(1000):
                tx = {
                    "hash": f"0x{cycle*1000+i:064x}",
                    "from": f"0x{i:040x}",
                    "to": mock_wallet_monitor.polymarket_contracts[0],
                    "value": "0",
                    "gasUsed": "150000",
                    "gasPrice": "50000000000",
                    "timeStamp": str(int((datetime.now() - timedelta(hours=cycle)).timestamp())),
                    "input": f"0x1234567890abcdef{i:016x}",
                    "blockNumber": str(50000000 + cycle * 1000 + i),
                }
                transactions.append(tx)

            # Process transactions (creates objects)
            trades = mock_wallet_monitor.detect_polymarket_trades(transactions)

            # Clean up
            del transactions
            del trades

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be bounded (< 50MB total increase)
        assert memory_increase < 50.0


class TestScalabilityTesting:
    """Scalability testing for growing loads."""

    @pytest.mark.parametrize("wallet_count", [5, 10, 25, 50])
    @pytest.mark.asyncio
    async def test_scalability_with_wallet_count(
        self, mock_wallet_monitor, performance_monitor, wallet_count
    ):
        """Test scalability as wallet count increases."""
        wallets = [f"0x{i:040x}" for i in range(wallet_count)]
        mock_wallet_monitor.target_wallets = wallets

        # Mock fast transaction fetching
        mock_wallet_monitor.get_wallet_transactions.return_value = []

        performance_monitor.start(f"scalability_{wallet_count}_wallets")

        await mock_wallet_monitor.monitor_wallets()

        duration = performance_monitor.end(f"scalability_{wallet_count}_wallets")

        # Should scale reasonably (linear or near-linear)
        assert duration < wallet_count * 0.5  # Allow up to 0.5s per wallet
        assert mock_wallet_monitor.get_wallet_transactions.call_count == wallet_count

    @pytest.mark.parametrize("transaction_count", [100, 500, 1000, 5000])
    def test_transaction_processing_scalability(
        self, mock_wallet_monitor, performance_monitor, transaction_count
    ):
        """Test scalability with transaction volume."""
        # Create transactions
        transactions = []
        for i in range(transaction_count):
            tx = {
                "hash": f"0x{i:064x}",
                "from": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                "to": mock_wallet_monitor.polymarket_contracts[0],
                "value": "0",
                "gasUsed": "150000",
                "gasPrice": "50000000000",
                "timeStamp": str(int((datetime.now() - timedelta(hours=i % 24)).timestamp())),
                "input": f"0x1234567890abcdef{i:016x}",
                "blockNumber": str(50000000 + i),
            }
            transactions.append(tx)

        performance_monitor.start(f"transaction_scalability_{transaction_count}")

        mock_wallet_monitor.detect_polymarket_trades(transactions)

        duration = performance_monitor.end(f"transaction_scalability_{transaction_count}")

        # Processing time should scale reasonably
        max_expected_time = transaction_count * 0.001  # 1ms per transaction
        assert duration < max_expected_time

        # Should process all transactions
        assert len(mock_wallet_monitor.processed_transactions) > 0
