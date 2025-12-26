"""
Unit tests for core/wallet_monitor.py - Wallet monitoring and trade detection.
"""
import pytest
import asyncio
import time
import json
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

from core.wallet_monitor import WalletMonitor
from utils.helpers import normalize_address, calculate_confidence_score


class TestWalletMonitorInitialization:
    """Test WalletMonitor initialization."""

    def test_monitor_initialization_success(self, mock_web3, test_settings):
        """Test successful wallet monitor initialization."""
        with patch('core.wallet_monitor.Web3', return_value=mock_web3):
            monitor = WalletMonitor()

            assert monitor.web3 == mock_web3
            assert len(monitor.target_wallets) == len(test_settings.monitoring.target_wallets)
            assert monitor.polygonscan_api_key == test_settings.network.polygonscan_api_key
            assert isinstance(monitor.processed_transactions, set)
            assert isinstance(monitor.wallet_trade_history, dict)
            assert monitor.api_call_delay == 0.2

    def test_monitor_initialization_with_web3_block_number(self, mock_web3, test_settings):
        """Test initialization with Web3 block number."""
        mock_web3.eth.block_number = 50000000
        mock_web3.is_connected.return_value = True

        with patch('core.wallet_monitor.Web3', return_value=mock_web3):
            monitor = WalletMonitor()

            assert monitor.last_checked_block == 50000000

    def test_monitor_initialization_web3_disconnected(self, mock_web3):
        """Test initialization when Web3 is disconnected."""
        mock_web3.is_connected.return_value = False

        with patch('core.wallet_monitor.Web3', return_value=mock_web3):
            monitor = WalletMonitor()

            assert monitor.last_checked_block == 0

    def test_polymarket_contract_addresses(self, mock_web3):
        """Test Polymarket contract addresses are configured."""
        with patch('core.wallet_monitor.Web3', return_value=mock_web3):
            monitor = WalletMonitor()

            expected_contracts = [
                "0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a",  # Polymarket AMM
                "0x8c16f85a4d5f8f23d29e9c7e3d4a3a5a6e4f2b2e"   # Polymarket CTF Exchange
            ]

            assert monitor.polymarket_contracts == expected_contracts


class TestWalletMonitorTransactionFetching:
    """Test transaction fetching functionality."""

    async def test_get_wallet_transactions_with_api_key(self, mock_wallet_monitor, mock_aiohttp_session, mock_polygonscan_response):
        """Test transaction fetching with Polygonscan API key."""
        mock_wallet_monitor.polygonscan_api_key = "test-api-key"

        transactions = await mock_wallet_monitor.get_wallet_transactions(
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            49900000,
            50000000
        )

        assert transactions == mock_polygonscan_response['result']
        mock_aiohttp_session.get.assert_called_once()

        # Check API call parameters
        call_args = mock_aiohttp_session.get.call_args
        params = call_args[1]['params']
        assert params['module'] == 'account'
        assert params['action'] == 'txlist'
        assert params['address'] == "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        assert params['startblock'] == 49900000
        assert params['endblock'] == 50000000
        assert params['apikey'] == "test-api-key"

    async def test_get_wallet_transactions_api_failure(self, mock_wallet_monitor, mock_aiohttp_session):
        """Test transaction fetching when API returns error."""
        mock_wallet_monitor.polygonscan_api_key = "test-api-key"
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'status': '0',
            'message': 'Error',
            'result': []
        })
        mock_aiohttp_session.get.return_value.__aenter__.return_value = mock_response

        transactions = await mock_wallet_monitor.get_wallet_transactions("0xtest")

        assert transactions == []

    async def test_get_wallet_transactions_no_api_key(self, mock_wallet_monitor):
        """Test transaction fetching fallback when no API key."""
        mock_wallet_monitor.polygonscan_api_key = ""

        transactions = await mock_wallet_monitor.get_wallet_transactions("0xtest")

        # Should call basic transaction method
        assert transactions == []

    async def test_get_basic_transactions_success(self, mock_wallet_monitor, mock_web3, sample_transaction):
        """Test basic transaction fetching using Web3."""
        mock_web3.is_connected.return_value = True
        mock_web3.eth.get_block.return_value = {
            'transactions': [sample_transaction]
        }

        transactions = await mock_wallet_monitor._get_basic_transactions("0xtest", 49900000)

        assert len(transactions) == 1
        assert transactions[0]['hash'] == sample_transaction['hash']

    async def test_get_basic_transactions_web3_disconnected(self, mock_wallet_monitor, mock_web3):
        """Test basic transaction fetching when Web3 is disconnected."""
        mock_web3.is_connected.return_value = False

        transactions = await mock_wallet_monitor._get_basic_transactions("0xtest")

        assert transactions == []

    async def test_rate_limiting(self, mock_wallet_monitor, mock_aiohttp_session, mock_polygonscan_response):
        """Test API rate limiting."""
        mock_wallet_monitor.polygonscan_api_key = "test-api-key"

        # Set last API call to very recent
        mock_wallet_monitor.last_api_call = time.time()

        start_time = time.time()
        await mock_wallet_monitor.get_wallet_transactions("0xtest")
        end_time = time.time()

        # Should have waited for rate limiting
        assert end_time - start_time >= mock_wallet_monitor.api_call_delay


class TestWalletMonitorTradeDetection:
    """Test trade detection functionality."""

    def test_detect_polymarket_trades_success(self, mock_wallet_monitor, sample_transaction):
        """Test successful Polymarket trade detection."""
        # Set up transaction to be detected as Polymarket trade
        sample_transaction['to'] = mock_wallet_monitor.polymarket_contracts[0]
        sample_transaction['input'] = '0x1234567800000000000000000000000000000000000000000000000000000000'

        trades = mock_wallet_monitor.detect_polymarket_trades([sample_transaction])

        assert len(trades) == 1
        trade = trades[0]
        assert trade['tx_hash'] == sample_transaction['hash']
        assert trade['wallet_address'] == normalize_address(sample_transaction['from'])
        assert trade['contract_address'] == normalize_address(sample_transaction['to'])

    def test_detect_polymarket_trades_already_processed(self, mock_wallet_monitor, sample_transaction):
        """Test that already processed transactions are skipped."""
        sample_transaction['to'] = mock_wallet_monitor.polymarket_contracts[0]
        mock_wallet_monitor.processed_transactions.add(sample_transaction['hash'])

        trades = mock_wallet_monitor.detect_polymarket_trades([sample_transaction])

        assert len(trades) == 0

    def test_detect_polymarket_trades_non_polymarket_contract(self, mock_wallet_monitor, sample_transaction):
        """Test that non-Polymarket contract transactions are ignored."""
        sample_transaction['to'] = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"  # Random address

        trades = mock_wallet_monitor.detect_polymarket_trades([sample_transaction])

        assert len(trades) == 0

    def test_detect_polymarket_trades_recent_transaction(self, mock_wallet_monitor, sample_transaction):
        """Test that very recent transactions are skipped to avoid reorgs."""
        sample_transaction['to'] = mock_wallet_monitor.polymarket_contracts[0]
        # Set timestamp to now (very recent)
        sample_transaction['timeStamp'] = str(int(time.time()))

        trades = mock_wallet_monitor.detect_polymarket_trades([sample_transaction])

        assert len(trades) == 0

    def test_detect_polymarket_trades_low_confidence(self, mock_wallet_monitor, sample_transaction):
        """Test that low confidence trades are skipped."""
        sample_transaction['to'] = mock_wallet_monitor.polymarket_contracts[0]
        # Set very old timestamp to pass recency check
        sample_transaction['timeStamp'] = str(int((datetime.now() - timedelta(days=1)).timestamp()))
        # Set empty input to get low confidence score
        sample_transaction['input'] = '0x'

        # Mock confidence score to be very low
        with patch('core.wallet_monitor.calculate_confidence_score', return_value=0.1):
            trades = mock_wallet_monitor.detect_polymarket_trades([sample_transaction])

            assert len(trades) == 0


class TestWalletMonitorTradeParsing:
    """Test trade parsing functionality."""

    def test_parse_polymarket_trade_success(self, mock_wallet_monitor, sample_transaction):
        """Test successful trade parsing."""
        sample_transaction['to'] = mock_wallet_monitor.polymarket_contracts[0]
        sample_transaction['timeStamp'] = str(int((datetime.now() - timedelta(hours=1)).timestamp()))
        sample_transaction['input'] = '0x1234567890abcdef'

        with patch('core.wallet_monitor.calculate_confidence_score', return_value=0.8):
            trade = mock_wallet_monitor.parse_polymarket_trade(sample_transaction)

            assert trade is not None
            assert trade['tx_hash'] == sample_transaction['hash']
            assert isinstance(trade['timestamp'], datetime)
            assert trade['confidence_score'] == 0.8

    def test_parse_polymarket_trade_parsing_error(self, mock_wallet_monitor, sample_transaction):
        """Test trade parsing with parsing errors."""
        # Remove required fields to cause parsing error
        del sample_transaction['hash']

        trade = mock_wallet_monitor.parse_polymarket_trade(sample_transaction)

        assert trade is None

    @pytest.mark.parametrize("input_data,expected_side", [
        ("buyShares", "BUY"),
        ("sellShares", "SELL"),
        ("purchase", "BUY"),
        ("closePosition", "SELL"),
        ("randomData", "BUY")  # Default case
    ])
    def test_determine_trade_side(self, mock_wallet_monitor, input_data, expected_side):
        """Test trade side determination."""
        tx = {'input': input_data}

        side = mock_wallet_monitor._determine_trade_side(tx)

        assert side == expected_side

    def test_determine_trade_side_with_value(self, mock_wallet_monitor):
        """Test trade side determination based on transaction value."""
        tx = {'input': 'random', 'value': '1000000000000000000'}  # 1 ETH

        side = mock_wallet_monitor._determine_trade_side(tx)

        assert side == "BUY"  # Positive value defaults to BUY

    def test_extract_trade_amount(self, mock_wallet_monitor, sample_transaction):
        """Test trade amount extraction."""
        amount = mock_wallet_monitor._extract_trade_amount(sample_transaction)

        # Should be calculated based on gas used
        assert isinstance(amount, float)
        assert amount > 0

    def test_extract_trade_price(self, mock_wallet_monitor, sample_transaction):
        """Test trade price extraction."""
        price = mock_wallet_monitor._extract_trade_price(sample_transaction)

        # Should be calculated based on gas price
        assert isinstance(price, float)
        assert 0.01 <= price <= 0.99


class TestWalletMonitorRateLimiting:
    """Test rate limiting functionality."""

    async def test_should_monitor_wallet_normal_case(self, mock_wallet_monitor):
        """Test wallet monitoring decision for normal case."""
        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        # Set last trade to be old enough
        mock_wallet_monitor.wallet_last_trade_time[wallet] = datetime.now() - timedelta(hours=2)

        should_monitor = await mock_wallet_monitor.should_monitor_wallet(wallet)

        assert should_monitor is True

    async def test_should_monitor_wallet_too_frequent(self, mock_wallet_monitor):
        """Test wallet monitoring decision when trades are too frequent."""
        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        # Set last trade to be very recent
        mock_wallet_monitor.wallet_last_trade_time[wallet] = datetime.now() - timedelta(minutes=10)

        should_monitor = await mock_wallet_monitor.should_monitor_wallet(wallet)

        assert should_monitor is False

    async def test_should_monitor_wallet_high_frequency(self, mock_wallet_monitor):
        """Test wallet monitoring decision when wallet has high trade frequency."""
        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"

        # Add many recent trades
        recent_trades = [
            {'timestamp': datetime.now() - timedelta(minutes=i)}
            for i in range(10)  # 10 trades in last hour
        ]
        mock_wallet_monitor.wallet_trade_history[wallet] = recent_trades

        should_monitor = await mock_wallet_monitor.should_monitor_wallet(wallet)

        assert should_monitor is False


class TestWalletMonitorMainMonitoring:
    """Test main monitoring loop functionality."""

    async def test_monitor_wallets_success(self, mock_wallet_monitor, mock_aiohttp_session, mock_polygonscan_response, sample_transaction):
        """Test successful wallet monitoring."""
        mock_wallet_monitor.polygonscan_api_key = "test-api-key"

        # Mock transaction response
        mock_polygonscan_response['result'] = [sample_transaction]

        detected_trades = await mock_wallet_monitor.monitor_wallets()

        # Should have processed transactions
        assert mock_wallet_monitor.last_checked_block > 0

    async def test_monitor_wallets_no_target_wallets(self, mock_wallet_monitor):
        """Test monitoring with no target wallets."""
        mock_wallet_monitor.target_wallets = []

        detected_trades = await mock_wallet_monitor.monitor_wallets()

        assert detected_trades == []

    async def test_monitor_wallets_with_detected_trades(self, mock_wallet_monitor, sample_transaction, sample_trade):
        """Test monitoring with actual detected trades."""
        mock_wallet_monitor.polygonscan_api_key = "test-api-key"

        # Set up transaction to be detected
        sample_transaction['to'] = mock_wallet_monitor.polymarket_contracts[0]
        sample_transaction['timeStamp'] = str(int((datetime.now() - timedelta(hours=1)).timestamp()))

        with patch.object(mock_wallet_monitor, 'get_wallet_transactions', return_value=[sample_transaction]), \
             patch.object(mock_wallet_monitor, 'detect_polymarket_trades', return_value=[sample_trade]):

            detected_trades = await mock_wallet_monitor.monitor_wallets()

            assert len(detected_trades) == 1
            assert detected_trades[0] == sample_trade

    async def test_monitor_wallets_error_handling(self, mock_wallet_monitor):
        """Test error handling during wallet monitoring."""
        mock_wallet_monitor.polygonscan_api_key = "test-api-key"

        with patch.object(mock_wallet_monitor, 'get_wallet_transactions', side_effect=Exception("API Error")):
            detected_trades = await mock_wallet_monitor.monitor_wallets()

            # Should continue processing other wallets
            assert isinstance(detected_trades, list)


class TestWalletMonitorStatistics:
    """Test statistics and reporting functionality."""

    def test_get_wallet_stats_with_trades(self, mock_wallet_monitor, sample_trade):
        """Test wallet statistics with trade history."""
        wallet = sample_trade['wallet_address']
        mock_wallet_monitor.wallet_trade_history[wallet] = [sample_trade]

        stats = mock_wallet_monitor.get_wallet_stats(wallet)

        assert stats['total_trades'] == 1
        assert 'avg_confidence' in stats
        assert 'last_trade_time' in stats
        assert 'recent_markets' in stats
        assert 'success_rate' in stats

    def test_get_wallet_stats_no_trades(self, mock_wallet_monitor):
        """Test wallet statistics with no trade history."""
        wallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        mock_wallet_monitor.wallet_trade_history[wallet] = []

        stats = mock_wallet_monitor.get_wallet_stats(wallet)

        assert stats['total_trades'] == 0
        assert stats['avg_confidence'] == 0.0
        assert stats['last_trade_time'] is None
        assert stats['recent_markets'] == []
        assert stats['success_rate'] == 0.0

    def test_get_all_stats(self, mock_wallet_monitor, sample_trade):
        """Test getting statistics for all wallets."""
        wallet = sample_trade['wallet_address']
        mock_wallet_monitor.wallet_trade_history[wallet] = [sample_trade]

        all_stats = mock_wallet_monitor.get_all_stats()

        assert wallet in all_stats
        assert all_stats[wallet]['total_trades'] == 1


class TestWalletMonitorCleanup:
    """Test cleanup functionality."""

    async def test_clean_processed_transactions(self, mock_wallet_monitor):
        """Test cleaning old processed transactions."""
        # Add some transactions with different ages
        now = datetime.now()
        old_tx = f"old_tx_{int((now - timedelta(days=2)).timestamp())}"
        recent_tx = f"recent_tx_{int((now - timedelta(hours=1)).timestamp())}"

        mock_wallet_monitor.processed_transactions = {old_tx, recent_tx}

        # Add recent trades to keep recent transactions
        recent_trade = {
            'tx_hash': recent_tx,
            'timestamp': now - timedelta(hours=1)
        }
        mock_wallet_monitor.wallet_trade_history["0xtest"] = [recent_trade]

        await mock_wallet_monitor.clean_processed_transactions()

        assert old_tx not in mock_wallet_monitor.processed_transactions
        assert recent_tx in mock_wallet_monitor.processed_transactions


class TestWalletMonitorHealthCheck:
    """Test health check functionality."""

    async def test_health_check_success(self, mock_wallet_monitor, mock_web3, mock_aiohttp_session, mock_polygonscan_response):
        """Test successful health check."""
        mock_web3.is_connected.return_value = True
        mock_wallet_monitor.target_wallets = ["0x742d35Cc6634C0532925a3b844Bc454e4438f44e"]

        healthy = await mock_wallet_monitor.health_check()

        assert healthy is True

    async def test_health_check_web3_disconnected(self, mock_wallet_monitor, mock_web3):
        """Test health check when Web3 is disconnected."""
        mock_web3.is_connected.return_value = False

        healthy = await mock_wallet_monitor.health_check()

        assert healthy is True  # Health check still passes but logs warning

    async def test_health_check_transaction_fetch_error(self, mock_wallet_monitor, mock_aiohttp_session):
        """Test health check with transaction fetch error."""
        mock_wallet_monitor.target_wallets = ["0x742d35Cc6634C0532925a3b844Bc454e4438f44e"]
        mock_aiohttp_session.get.side_effect = Exception("API Error")

        healthy = await mock_wallet_monitor.health_check()

        assert healthy is False


class TestWalletMonitorIntegration:
    """Integration tests for WalletMonitor."""

    async def test_full_monitoring_cycle(self, mock_wallet_monitor, sample_transaction, sample_trade):
        """Test complete monitoring cycle."""
        mock_wallet_monitor.polygonscan_api_key = "test-api-key"

        # Set up transaction to be detected
        sample_transaction['to'] = mock_wallet_monitor.polymarket_contracts[0]
        sample_transaction['timeStamp'] = str(int((datetime.now() - timedelta(hours=1)).timestamp()))

        with patch.object(mock_wallet_monitor, 'get_wallet_transactions', return_value=[sample_transaction]), \
             patch.object(mock_wallet_monitor, 'detect_polymarket_trades', return_value=[sample_trade]):

            # Run monitoring cycle
            detected_trades = await mock_wallet_monitor.monitor_wallets()

            # Verify results
            assert len(detected_trades) == 1
            assert detected_trades[0]['tx_hash'] == sample_trade['tx_hash']

            # Verify state updates
            assert sample_transaction['hash'] in mock_wallet_monitor.processed_transactions
            assert sample_trade['wallet_address'] in mock_wallet_monitor.wallet_trade_history

    async def test_monitoring_with_multiple_wallets(self, mock_wallet_monitor):
        """Test monitoring multiple wallets."""
        wallet1 = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        wallet2 = "0x742d35Cc6634C0532925a3b844Bc454e4438f44f"

        mock_wallet_monitor.target_wallets = [wallet1, wallet2]

        with patch.object(mock_wallet_monitor, 'get_wallet_transactions', return_value=[]), \
             patch.object(mock_wallet_monitor, 'should_monitor_wallet', return_value=True):

            detected_trades = await mock_wallet_monitor.monitor_wallets()

            # Should have called get_wallet_transactions for both wallets
            assert mock_wallet_monitor.get_wallet_transactions.call_count == 2

    async def test_error_recovery_in_monitoring(self, mock_wallet_monitor):
        """Test error recovery during monitoring."""
        mock_wallet_monitor.target_wallets = ["0x742d35Cc6634C0532925a3b844Bc454e4438f44e"]

        with patch.object(mock_wallet_monitor, 'get_wallet_transactions', side_effect=Exception("Network error")), \
             patch.object(mock_wallet_monitor, 'should_monitor_wallet', return_value=True):

            # Should not raise exception
            detected_trades = await mock_wallet_monitor.monitor_wallets()

            assert isinstance(detected_trades, list)
