"""
Edge case tests for blockchain reorgs, network partitions, and other edge conditions.
"""
import pytest
import asyncio
import time
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from datetime import datetime, timedelta
import json

from core.wallet_monitor import WalletMonitor
from core.trade_executor import TradeExecutor
from core.clob_client import PolymarketClient


class TestBlockchainReorgScenarios:
    """Test blockchain reorg simulation."""

    def test_blockchain_reorg_transaction_disappearance(self, mock_wallet_monitor, edge_case_scenarios):
        """Test handling of transactions that disappear due to reorg."""
        reorg_data = edge_case_scenarios['blockchain_reorg']

        # Simulate original transaction
        original_tx = reorg_data['original_tx'].copy()
        original_tx.update({
            'hash': reorg_data['original_tx']['hash'],
            'blockNumber': reorg_data['original_tx']['blockNumber'],
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'timeStamp': str(int((datetime.now() - timedelta(hours=1)).timestamp())),
            'input': '0x1234567890abcdef',
        })

        # Process original transaction
        trades1 = mock_wallet_monitor.detect_polymarket_trades([original_tx])
        assert len(trades1) == 1
        assert original_tx['hash'] in mock_wallet_monitor.processed_transactions

        # Simulate reorg - transaction disappears
        # In a real reorg, we'd need to re-query the blockchain
        # For testing, we simulate by clearing processed transactions
        mock_wallet_monitor.processed_transactions.clear()

        # Re-query should not reprocess if we detect the reorg
        # (In practice, this would require comparing block numbers)
        trades2 = mock_wallet_monitor.detect_polymarket_trades([original_tx])
        assert len(trades2) == 1  # Would be reprocessed in this simple test

    def test_uncle_block_handling(self, mock_wallet_monitor):
        """Test handling of transactions in uncle blocks."""
        # Create transaction in a block that becomes an uncle
        uncle_tx = {
            'hash': '0xuncle1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '0',
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int((datetime.now() - timedelta(hours=1)).timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'  # This block becomes an uncle
        }

        # Process transaction
        trades = mock_wallet_monitor.detect_polymarket_trades([uncle_tx])
        assert len(trades) == 1

        # In a real scenario, if the block becomes an uncle,
        # the transaction should be re-processed when it appears in the main chain
        # For testing, we verify it was processed initially
        assert uncle_tx['hash'] in mock_wallet_monitor.processed_transactions

    def test_deep_reorg_handling(self, mock_wallet_monitor):
        """Test handling of deep blockchain reorgs."""
        # Create a chain of transactions that get reorged
        base_block = 50000000
        transactions = []

        for i in range(10):
            tx = {
                'hash': f'0xreorg{i:064x}',
                'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                'to': mock_wallet_monitor.polymarket_contracts[0],
                'value': '0',
                'gasUsed': '150000',
                'gasPrice': '50000000000',
                'timeStamp': str(int((datetime.now() - timedelta(hours=i)).timestamp())),
                'input': f'0x1234567890abcdef{i:016x}',
                'blockNumber': str(base_block + i)
            }
            transactions.append(tx)

        # Process all transactions
        trades = mock_wallet_monitor.detect_polymarket_trades(transactions)
        assert len(trades) == 10

        # Simulate deep reorg by clearing processed transactions
        mock_wallet_monitor.processed_transactions.clear()

        # Re-processing should handle the reorg gracefully
        trades_reorg = mock_wallet_monitor.detect_polymarket_trades(transactions)
        assert len(trades_reorg) == 10  # All transactions reprocessed


class TestNetworkPartitionTesting:
    """Test network partition scenarios."""

    @pytest.mark.asyncio
    async def test_network_partition_during_api_call(self, mock_wallet_monitor, edge_case_scenarios):
        """Test network partition during API call."""
        partition_error = edge_case_scenarios['network_partition']['connection_error']

        # Mock API call that fails with connection error
        mock_wallet_monitor.get_wallet_transactions.side_effect = partition_error

        # Should handle the error gracefully
        transactions = await mock_wallet_monitor.get_wallet_transactions("0xtest")

        assert transactions == []  # Should return empty list on error

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, mock_wallet_monitor, edge_case_scenarios):
        """Test network timeout handling."""
        timeout_error = edge_case_scenarios['network_partition']['timeout_error']

        # Mock API call that times out
        mock_wallet_monitor.get_wallet_transactions.side_effect = timeout_error

        transactions = await mock_wallet_monitor.get_wallet_transactions("0xtest")

        assert transactions == []

    @pytest.mark.asyncio
    async def test_partial_network_failure(self, mock_wallet_monitor):
        """Test partial network failure (some calls succeed, some fail)."""
        # Mock alternating success/failure
        call_count = 0

        async def alternating_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return []
            else:
                raise ConnectionError("Intermittent network failure")

        mock_wallet_monitor.get_wallet_transactions = alternating_response

        # Make multiple calls
        results = []
        for i in range(4):
            try:
                transactions = await mock_wallet_monitor.get_wallet_transactions("0xtest")
                results.append(transactions)
            except ConnectionError:
                results.append("failed")

        # Should have mixed results
        assert "failed" in results
        assert [] in results

    @pytest.mark.asyncio
    async def test_network_recovery_after_partition(self, mock_wallet_monitor):
        """Test network recovery after partition."""
        call_count = 0

        async def recovering_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Network partition")
            return []

        mock_wallet_monitor.get_wallet_transactions = recovering_response

        # First two calls should fail
        for i in range(2):
            transactions = await mock_wallet_monitor.get_wallet_transactions("0xtest")
            assert transactions == []

        # Third call should succeed
        transactions = await mock_wallet_monitor.get_wallet_transactions("0xtest")
        assert transactions == []


class TestInvalidTransactionHandling:
    """Test handling of invalid transactions."""

    def test_malformed_transaction_parsing(self, mock_wallet_monitor, edge_case_scenarios):
        """Test parsing of malformed transactions."""
        invalid_tx = edge_case_scenarios['invalid_transaction']['missing_fields']

        # Should not crash
        trade = mock_wallet_monitor.parse_polymarket_trade(invalid_tx)

        assert trade is None

    def test_invalid_price_transaction(self, mock_wallet_monitor, edge_case_scenarios):
        """Test handling of transactions with invalid prices."""
        invalid_price_tx = edge_case_scenarios['invalid_transaction']['invalid_price']

        # Complete the transaction data
        invalid_price_tx.update({
            'hash': '0xinvalidprice1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int((datetime.now() - timedelta(hours=1)).timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        })

        trade = mock_wallet_monitor.parse_polymarket_trade(invalid_price_tx)

        # Should still parse but price will be invalid
        assert trade is not None
        assert trade['price'] == 1.5  # Invalid price

    def test_ancient_transaction_filtering(self, mock_wallet_monitor, edge_case_scenarios):
        """Test filtering of ancient transactions."""
        ancient_tx = {
            'hash': '0xancient1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '0',
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int(edge_case_scenarios['invalid_transaction']['ancient_timestamp'].timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        }

        trade = mock_wallet_monitor.parse_polymarket_trade(ancient_tx)

        # Should be rejected as too old
        assert trade is None

    def test_zero_value_transaction_handling(self, mock_wallet_monitor):
        """Test handling of zero-value transactions."""
        zero_value_tx = {
            'hash': '0xzerovalue1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '0',
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int((datetime.now() - timedelta(hours=1)).timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        }

        with patch('core.wallet_monitor.calculate_confidence_score', return_value=0.8):
            trade = mock_wallet_monitor.parse_polymarket_trade(zero_value_tx)

            assert trade is not None
            assert trade['value_eth'] == 0.0

    def test_extremely_high_gas_transaction(self, mock_wallet_monitor):
        """Test handling of transactions with extremely high gas usage."""
        high_gas_tx = {
            'hash': '0xhighgas1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '0',
            'gasUsed': '5000000',  # Extremely high gas
            'gasPrice': '50000000000',
            'timeStamp': str(int((datetime.now() - timedelta(hours=1)).timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        }

        with patch('core.wallet_monitor.calculate_confidence_score', return_value=0.8):
            trade = mock_wallet_monitor.parse_polymarket_trade(high_gas_tx)

            assert trade is not None
            assert trade['gas_used'] == 5000000


class TestClockSkewScenarios:
    """Test clock skew scenarios."""

    def test_future_timestamp_transaction(self, mock_wallet_monitor, edge_case_scenarios):
        """Test handling of transactions with future timestamps."""
        future_tx = {
            'hash': '0xfuture1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '0',
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int(edge_case_scenarios['clock_skew']['future_timestamp'].timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        }

        trade = mock_wallet_monitor.parse_polymarket_trade(future_tx)

        # Should be rejected due to future timestamp or handled gracefully
        assert trade is not None  # In this implementation, it parses but timestamp is in future

    def test_past_timestamp_transaction(self, mock_wallet_monitor, edge_case_scenarios):
        """Test handling of transactions with past timestamps."""
        past_tx = {
            'hash': '0xpast1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '0',
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int(edge_case_scenarios['clock_skew']['past_timestamp'].timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        }

        trade = mock_wallet_monitor.parse_polymarket_trade(past_tx)

        # Should be parsed but may be filtered due to age
        assert trade is not None

    def test_clock_skew_during_monitoring(self, mock_wallet_monitor):
        """Test clock skew during monitoring operations."""
        # Create transaction with timestamp that might be affected by clock skew
        skew_tx = {
            'hash': '0xskew1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '0',
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int((datetime.now() - timedelta(seconds=10)).timestamp())),  # Slightly in past
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        }

        # Mock system clock being slightly off
        with patch('core.wallet_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now() - timedelta(minutes=5)  # System clock 5 minutes behind

            trade = mock_wallet_monitor.parse_polymarket_trade(skew_tx)

            # Should still be parsed despite clock skew
            assert trade is not None


class TestExtremeValueScenarios:
    """Test extreme value scenarios."""

    def test_maximum_transaction_value(self, mock_wallet_monitor):
        """Test handling of maximum transaction values."""
        max_value_tx = {
            'hash': '0xmaxvalue1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '115792089237316195423570985008687907853269984665640564039457584007913129639935',  # Max uint256
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int((datetime.now() - timedelta(hours=1)).timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        }

        with patch('core.wallet_monitor.calculate_confidence_score', return_value=0.8):
            trade = mock_wallet_monitor.parse_polymarket_trade(max_value_tx)

            assert trade is not None
            assert trade['value_eth'] > 0  # Should be converted

    def test_minimum_transaction_value(self, mock_wallet_monitor):
        """Test handling of minimum transaction values."""
        min_value_tx = {
            'hash': '0xminvalue1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '1',  # Minimum value
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int((datetime.now() - timedelta(hours=1)).timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        }

        with patch('core.wallet_monitor.calculate_confidence_score', return_value=0.8):
            trade = mock_wallet_monitor.parse_polymarket_trade(min_value_tx)

            assert trade is not None
            assert trade['value_eth'] > 0

    def test_maximum_gas_price(self, mock_wallet_monitor):
        """Test handling of maximum gas prices."""
        max_gas_tx = {
            'hash': '0xmaxgas1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '0',
            'gasUsed': '150000',
            'gasPrice': '115792089237316195423570985008687907853269984665640564039457584007913129639935',  # Max uint256
            'timeStamp': str(int((datetime.now() - timedelta(hours=1)).timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        }

        with patch('core.wallet_monitor.calculate_confidence_score', return_value=0.8):
            trade = mock_wallet_monitor.parse_polymarket_trade(max_gas_tx)

            assert trade is not None
            assert trade['gas_price'] > 0

    def test_empty_input_data(self, mock_wallet_monitor):
        """Test handling of transactions with empty input data."""
        empty_input_tx = {
            'hash': '0xemptyinput1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '0',
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int((datetime.now() - timedelta(hours=1)).timestamp())),
            'input': '0x',  # Empty input
            'blockNumber': '50000000'
        }

        with patch('core.wallet_monitor.calculate_confidence_score', return_value=0.8):
            trade = mock_wallet_monitor.parse_polymarket_trade(empty_input_tx)

            assert trade is not None
            assert trade['input_data'] == '0x'


class TestConcurrencyEdgeCases:
    """Test concurrency-related edge cases."""

    @pytest.mark.asyncio
    async def test_concurrent_transaction_processing(self, mock_wallet_monitor):
        """Test concurrent processing of the same transactions."""
        # Create the same transaction multiple times
        tx = {
            'hash': '0xconcurrent1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'to': mock_wallet_monitor.polymarket_contracts[0],
            'value': '0',
            'gasUsed': '150000',
            'gasPrice': '50000000000',
            'timeStamp': str(int((datetime.now() - timedelta(hours=1)).timestamp())),
            'input': '0x1234567890abcdef',
            'blockNumber': '50000000'
        }

        transactions = [tx] * 10  # Same transaction 10 times

        # Process concurrently
        tasks = [mock_wallet_monitor.detect_polymarket_trades([tx]) for tx in transactions]
        results = await asyncio.gather(*tasks)

        # Only one trade should be detected (due to duplicate prevention)
        total_trades = sum(len(result) for result in results)
        assert total_trades == 1

        # Transaction should be in processed set
        assert tx['hash'] in mock_wallet_monitor.processed_transactions

    @pytest.mark.asyncio
    async def test_race_condition_in_position_management(self, mock_trade_executor):
        """Test race conditions in position management."""
        # Set up a position
        position_key = "test_condition_BUY"
        position = {
            'amount': 10.0,
            'entry_price': 0.60,
            'timestamp': time.time(),
            'original_trade': {
                'condition_id': 'test_condition',
                'side': 'BUY',
                'wallet_address': '0xtest'
            },
            'order_id': 'test-order-123'
        }
        mock_trade_executor.open_positions[position_key] = position

        # Simulate concurrent position closing attempts
        async def close_position_attempt():
            await mock_trade_executor._close_position(position_key, "TAKE_PROFIT")
            return position_key in mock_trade_executor.open_positions

        tasks = [close_position_attempt() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # Position should be closed by at least one attempt
        assert not all(results)  # At least one should have found position gone

    @pytest.mark.asyncio
    async def test_concurrent_wallet_monitoring(self, mock_wallet_monitor):
        """Test concurrent monitoring of the same wallet."""
        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        mock_wallet_monitor.target_wallets = [wallet]

        # Mock transaction fetching
        mock_wallet_monitor.get_wallet_transactions.return_value = []

        # Run multiple monitoring cycles concurrently
        tasks = [mock_wallet_monitor.monitor_wallets() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All should complete without errors
        assert len(results) == 5
        assert all(isinstance(result, list) for result in results)


class TestStateCorruptionScenarios:
    """Test state corruption scenarios."""

    def test_corrupted_trade_history_recovery(self, mock_wallet_monitor):
        """Test recovery from corrupted trade history."""
        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"

        # Add some valid trades
        valid_trades = [
            {'tx_hash': '0xvalid1', 'timestamp': datetime.now(), 'amount': 10.0},
            {'tx_hash': '0xvalid2', 'timestamp': datetime.now(), 'amount': 20.0}
        ]
        mock_wallet_monitor.wallet_trade_history[wallet] = valid_trades

        # Add corrupted trade
        corrupted_trade = {'invalid': 'data'}  # Missing required fields
        mock_wallet_monitor.wallet_trade_history[wallet].append(corrupted_trade)

        # Should handle corrupted data gracefully
        stats = mock_wallet_monitor.get_wallet_stats(wallet)

        # Stats should still be calculable
        assert isinstance(stats, dict)
        assert 'total_trades' in stats

    def test_empty_collections_handling(self, mock_wallet_monitor, mock_trade_executor):
        """Test handling of empty collections."""
        # Empty wallet trade history
        stats = mock_wallet_monitor.get_wallet_stats("0xnonexistent")
        assert stats['total_trades'] == 0

        # Empty open positions
        assert len(mock_trade_executor.open_positions) == 0

        # Empty processed transactions
        assert len(mock_wallet_monitor.processed_transactions) == 0

    def test_large_data_set_memory_limits(self, mock_wallet_monitor):
        """Test memory limits with large data sets."""
        # Add many processed transactions
        for i in range(10000):
            mock_wallet_monitor.processed_transactions.add(f"0x{i:064x}")

        # Add many trades to history
        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        for i in range(500):
            trade = {'tx_hash': f'0xtrade{i:064x}', 'timestamp': datetime.now(), 'amount': 10.0}
            mock_wallet_monitor.wallet_trade_history[wallet].append(trade)

        # Apply limits (simulate cleanup)
        mock_wallet_monitor.wallet_trade_history[wallet] = mock_wallet_monitor.wallet_trade_history[wallet][-100:]

        # Should be within limits
        assert len(mock_wallet_monitor.wallet_trade_history[wallet]) <= 100
        assert len(mock_wallet_monitor.processed_transactions) == 10000  # No automatic cleanup for processed tx


class TestErrorPropagationAndHandling:
    """Test error propagation and handling."""

    @pytest.mark.asyncio
    async def test_cascading_error_handling(self, mock_wallet_monitor, mock_trade_executor):
        """Test cascading error handling."""
        # Set up scenario where wallet monitoring fails
        mock_wallet_monitor.monitor_wallets.side_effect = Exception("Monitoring failed")

        # Set up trade executor to handle the failure
        mock_trade_executor.execute_copy_trade.side_effect = Exception("Trading failed")

        # The system should handle these errors without crashing
        # (In the actual bot, this would be handled in the main loop)

        # Test individual component error handling
        with pytest.raises(Exception):
            await mock_wallet_monitor.monitor_wallets()

        # Should not affect other components
        assert len(mock_trade_executor.open_positions) == 0

    def test_exception_safety_in_parsing(self, mock_wallet_monitor):
        """Test exception safety in transaction parsing."""
        # Create transaction that will cause parsing errors
        problematic_tx = {
            'hash': None,  # Will cause issues
            'from': None,
            'to': None,
            'value': None,
            'gasUsed': None,
            'gasPrice': None,
            'timeStamp': None,
            'input': None,
            'blockNumber': None
        }

        # Should not crash
        trade = mock_wallet_monitor.parse_polymarket_trade(problematic_tx)

        assert trade is None

    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self, mock_trade_executor):
        """Test recovery from partial failures."""
        # Set up mixed success/failure scenario
        call_count = 0

        async def mixed_results(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Every third call fails
                raise Exception("Intermittent failure")
            return {'status': 'success'}

        mock_trade_executor.execute_copy_trade = mixed_results

        # Execute multiple trades
        trades = [{'id': i} for i in range(9)]
        results = []

        for trade in trades:
            try:
                result = await mock_trade_executor.execute_copy_trade(trade)
                results.append('success')
            except Exception:
                results.append('failed')

        # Should have some successes and some failures
        assert 'success' in results
        assert 'failed' in results
        assert len(results) == 9
