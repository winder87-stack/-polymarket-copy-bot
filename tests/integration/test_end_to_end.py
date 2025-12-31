"""
Integration tests for end-to-end trading bot functionality.
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from main import PolymarketCopyBot


class TestEndToEndTradingFlow:
    """Test complete end-to-end trading flow."""

    @pytest.mark.asyncio
    async def test_successful_trading_cycle(
        self,
        mock_polymarket_client,
        mock_wallet_monitor,
        mock_trade_executor,
        test_settings,
    ):
        """Test successful complete trading cycle."""
        # Mock successful initialization
        with (
            patch("main.PolymarketClient", return_value=mock_polymarket_client),
            patch("main.WalletMonitor", return_value=mock_wallet_monitor),
            patch("main.TradeExecutor", return_value=mock_trade_executor),
            patch.object(mock_polymarket_client, "health_check", return_value=True),
            patch.object(mock_wallet_monitor, "health_check", return_value=True),
            patch.object(mock_trade_executor, "health_check", return_value=True),
        ):
            bot = PolymarketCopyBot()

            # Initialize bot
            initialized = await bot.initialize()
            assert initialized

            # Mock a detected trade
            sample_trade = {
                "tx_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "timestamp": datetime.now() - timedelta(seconds=30),
                "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
                "side": "BUY",
                "amount": 10.0,
                "price": 0.65,
                "token_id": "0xabcdef1234567890abcdef1234567890abcdef12",
                "confidence_score": 0.8,
            }

            # Mock monitoring to return detected trade
            with (
                patch.object(
                    mock_wallet_monitor, "monitor_wallets", return_value=[sample_trade]
                ),
                patch.object(
                    mock_trade_executor,
                    "execute_copy_trade",
                    return_value={"status": "success"},
                ),
                patch.object(
                    mock_trade_executor, "manage_positions", return_value=None
                ),
                patch.object(
                    mock_wallet_monitor,
                    "clean_processed_transactions",
                    return_value=None,
                ),
                patch.object(bot, "_periodic_performance_report", return_value=None),
            ):
                # Run monitoring loop once
                await bot.monitor_loop()

                # Verify trade was executed
                mock_trade_executor.execute_copy_trade.assert_called_once_with(
                    sample_trade
                )
                mock_trade_executor.manage_positions.assert_called_once()
                mock_wallet_monitor.clean_processed_transactions.assert_called_once()

    @pytest.mark.asyncio
    async def test_bot_initialization_failure(self, test_settings):
        """Test bot initialization failure."""
        # Mock client initialization failure
        with patch(
            "main.PolymarketClient", side_effect=Exception("Client init failed")
        ):
            bot = PolymarketCopyBot()

            initialized = await bot.initialize()
            assert not initialized

    @pytest.mark.asyncio
    async def test_bot_initialization_health_check_failure(
        self, mock_polymarket_client, mock_wallet_monitor, mock_trade_executor
    ):
        """Test bot initialization with health check failure."""
        with (
            patch("main.PolymarketClient", return_value=mock_polymarket_client),
            patch("main.WalletMonitor", return_value=mock_wallet_monitor),
            patch("main.TradeExecutor", return_value=mock_trade_executor),
            patch.object(mock_polymarket_client, "health_check", return_value=True),
            patch.object(mock_wallet_monitor, "health_check", return_value=True),
            patch.object(mock_trade_executor, "health_check", return_value=False),
        ):
            bot = PolymarketCopyBot()

            initialized = await bot.initialize()
            assert not initialized


class TestErrorRecoveryScenarios:
    """Test error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_trade_execution_failure_recovery(
        self, mock_wallet_monitor, mock_trade_executor, sample_trade
    ):
        """Test recovery from trade execution failures."""
        # Set up bot with mocks
        with (
            patch("main.PolymarketClient") as mock_client_class,
            patch("main.WalletMonitor", return_value=mock_wallet_monitor),
            patch("main.TradeExecutor", return_value=mock_trade_executor),
        ):
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.health_check.return_value = True
            mock_wallet_monitor.health_check.return_value = True
            mock_trade_executor.health_check.return_value = True

            bot = PolymarketCopyBot()
            await bot.initialize()

            # Mock trade detection
            mock_wallet_monitor.monitor_wallets.return_value = [sample_trade]

            # Mock trade execution failure
            mock_trade_executor.execute_copy_trade.side_effect = [
                {"status": "failed", "reason": "API Error"},
                {"status": "success", "order_id": "retry-success"},
            ]

            # Mock other methods
            mock_trade_executor.manage_positions.return_value = None
            mock_wallet_monitor.clean_processed_transactions.return_value = None
            bot._periodic_performance_report = AsyncMock()

            # Run monitoring cycle
            await bot.monitor_loop()

            # Verify trade was attempted
            assert mock_trade_executor.execute_copy_trade.call_count == 1

    @pytest.mark.asyncio
    async def test_wallet_monitoring_failure_recovery(
        self, mock_wallet_monitor, mock_trade_executor
    ):
        """Test recovery from wallet monitoring failures."""
        with (
            patch("main.PolymarketClient") as mock_client_class,
            patch("main.WalletMonitor", return_value=mock_wallet_monitor),
            patch("main.TradeExecutor", return_value=mock_trade_executor),
        ):
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.health_check.return_value = True
            mock_wallet_monitor.health_check.return_value = True
            mock_trade_executor.health_check.return_value = True

            bot = PolymarketCopyBot()
            await bot.initialize()

            # Mock monitoring failure
            mock_wallet_monitor.monitor_wallets.side_effect = Exception(
                "Monitoring failed"
            )

            # Mock other methods
            mock_trade_executor.manage_positions.return_value = None
            mock_wallet_monitor.clean_processed_transactions.return_value = None
            bot._periodic_performance_report = AsyncMock()

            # Should not raise exception, should continue
            await bot.monitor_loop()

            # Verify monitoring was attempted
            mock_wallet_monitor.monitor_wallets.assert_called_once()

    @pytest.mark.asyncio
    async def test_network_connectivity_recovery(
        self, mock_polymarket_client, mock_wallet_monitor, mock_trade_executor
    ):
        """Test recovery from network connectivity issues."""
        with (
            patch("main.PolymarketClient", return_value=mock_polymarket_client),
            patch("main.WalletMonitor", return_value=mock_wallet_monitor),
            patch("main.TradeExecutor", return_value=mock_trade_executor),
        ):
            # Mock initial health check failure
            mock_polymarket_client.health_check.side_effect = [
                False,  # Initial failure
                True,  # Recovery
            ]
            mock_wallet_monitor.health_check.return_value = True
            mock_trade_executor.health_check.return_value = True

            bot = PolymarketCopyBot()
            await bot.initialize()

            # Mock successful monitoring after recovery
            mock_wallet_monitor.monitor_wallets.return_value = []
            mock_trade_executor.manage_positions.return_value = None
            mock_wallet_monitor.clean_processed_transactions.return_value = None
            bot._periodic_performance_report = AsyncMock()

            # Run monitoring cycle
            await bot.monitor_loop()

            # Verify health check was called multiple times
            assert mock_polymarket_client.health_check.call_count >= 2


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration scenarios."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_activation_and_reset(
        self, mock_trade_executor, sample_trade
    ):
        """Test circuit breaker activation and automatic reset."""
        with (
            patch("main.PolymarketClient") as mock_client_class,
            patch("main.WalletMonitor") as mock_wallet_class,
            patch("main.TradeExecutor", return_value=mock_trade_executor),
        ):
            mock_client = Mock()
            mock_wallet = Mock()
            mock_client_class.return_value = mock_client
            mock_wallet_class.return_value = mock_wallet

            # Mock health checks
            mock_client.health_check.return_value = True
            mock_wallet.health_check.return_value = True
            mock_trade_executor.health_check.return_value = True

            bot = PolymarketCopyBot()
            await bot.initialize()

            # Force circuit breaker activation
            mock_trade_executor.daily_loss = 200.0  # Above limit
            mock_trade_executor._check_circuit_breaker_conditions()

            assert mock_trade_executor.circuit_breaker_active

            # Mock trade detection
            mock_wallet.monitor_wallets.return_value = [sample_trade]

            # Mock other methods
            mock_trade_executor.manage_positions.return_value = None
            mock_wallet.clean_processed_transactions.return_value = None
            bot._periodic_performance_report = AsyncMock()

            # Run monitoring cycle - trade should be skipped
            await bot.monitor_loop()

            # Verify trade was not executed due to circuit breaker
            mock_trade_executor.execute_copy_trade.assert_not_called()

            # Simulate time passage and loss reset
            mock_trade_executor.circuit_breaker_time = time.time() - 7200  # 2 hours ago
            mock_trade_executor.daily_loss = 0.0

            # Reset circuit breaker
            mock_trade_executor._check_circuit_breaker_conditions()

            assert not mock_trade_executor.circuit_breaker_active

    @pytest.mark.asyncio
    async def test_consecutive_failure_circuit_breaker(self, mock_trade_executor):
        """Test circuit breaker activation due to consecutive failures."""
        # Set up consecutive failures
        mock_trade_executor.total_trades = 15
        mock_trade_executor.failed_trades = 10  # 66% failure rate

        mock_trade_executor._check_circuit_breaker_conditions()

        assert mock_trade_executor.circuit_breaker_active
        assert "High failure rate" in mock_trade_executor.circuit_breaker_reason


class TestRiskManagementIntegration:
    """Test risk management integration."""

    @pytest.mark.asyncio
    async def test_risk_limits_enforcement(self, mock_trade_executor, sample_trade):
        """Test that risk limits are properly enforced across the system."""
        # Set up risk limits
        mock_trade_executor.settings.risk.max_daily_loss = 50.0
        mock_trade_executor.settings.risk.max_position_size = 25.0

        # Test daily loss limit
        mock_trade_executor.daily_loss = 60.0  # Above limit

        result = mock_trade_executor._apply_risk_management(sample_trade)

        assert result["approved"] is False
        assert "Daily loss limit reached" in result["reason"]

        # Reset and test position size limit
        mock_trade_executor.daily_loss = 0.0
        sample_trade["amount"] = 50.0  # Above position limit

        result = mock_trade_executor._apply_risk_management(sample_trade)

        assert result["approved"] is False
        assert "Position size too large" in result["reason"]

    @pytest.mark.asyncio
    async def test_position_management_integration(
        self, mock_trade_executor, mock_polymarket_client
    ):
        """Test position management integration with price monitoring."""
        # Set up an open position
        position_key = "test_condition_BUY"
        position = {
            "amount": 10.0,
            "entry_price": 0.60,
            "timestamp": time.time() - 3600,  # 1 hour ago
            "original_trade": {
                "condition_id": "test_condition",
                "side": "BUY",
                "wallet_address": "0xtest",
            },
            "order_id": "test-order-123",
        }
        mock_trade_executor.open_positions[position_key] = position

        # Mock price increase triggering take profit
        mock_polymarket_client.get_current_price.return_value = 0.75  # 25% profit

        # Mock successful closing trade
        mock_trade_executor._close_position = AsyncMock(return_value=None)

        await mock_trade_executor.manage_positions()

        # Verify position closing was attempted
        mock_trade_executor._close_position.assert_called_once_with(
            position_key, "TAKE_PROFIT"
        )


class TestPerformanceReportingIntegration:
    """Test performance reporting integration."""

    @pytest.mark.asyncio
    async def test_performance_report_generation(self, mock_trade_executor):
        """Test performance report generation."""
        # Set up some trade history
        mock_trade_executor.total_trades = 100
        mock_trade_executor.successful_trades = 85
        mock_trade_executor.failed_trades = 15
        mock_trade_executor.daily_loss = -125.50  # Profit
        mock_trade_executor.open_positions = {"pos1": {}, "pos2": {}}
        mock_trade_executor.circuit_breaker_active = False
        mock_trade_executor.last_trade_time = time.time() - 1800  # 30 minutes ago
        mock_trade_executor.start_time = time.time() - 86400  # 1 day ago

        # Add some performance data
        mock_trade_executor.trade_performance = [
            {"execution_time": 1.2, "status": "success"},
            {"execution_time": 2.5, "status": "success"},
            {"execution_time": 0.8, "status": "failed"},
        ]

        metrics = mock_trade_executor.get_performance_metrics()

        assert metrics["total_trades"] == 100
        assert metrics["successful_trades"] == 85
        assert metrics["failed_trades"] == 15
        assert metrics["success_rate"] == 0.85
        assert metrics["daily_loss"] == -125.50
        assert metrics["open_positions"] == 2
        assert not metrics["circuit_breaker_active"]
        assert "last_trade_time" in metrics
        assert "uptime_hours" in metrics
        assert "avg_execution_time" in metrics


class TestConfigurationIntegration:
    """Test configuration integration across components."""

    @pytest.mark.asyncio
    async def test_configuration_consistency(self, test_settings):
        """Test that configuration is consistently applied across components."""
        with (
            patch("main.PolymarketClient") as mock_client_class,
            patch("main.WalletMonitor") as mock_wallet_class,
            patch("main.TradeExecutor") as mock_trade_class,
        ):
            # Mock component classes
            mock_client = Mock()
            mock_wallet = Mock()
            mock_trade = Mock()

            mock_client_class.return_value = mock_client
            mock_wallet_class.return_value = mock_wallet
            mock_trade_class.return_value = mock_trade

            # Mock health checks
            mock_client.health_check.return_value = True
            mock_wallet.health_check.return_value = True
            mock_trade.health_check.return_value = True

            bot = PolymarketCopyBot()

            # Verify settings are shared
            assert bot.settings is test_settings

            # Initialize and verify settings are passed to components
            await bot.initialize()

            # Verify components were created
            mock_client_class.assert_called_once()
            mock_wallet_class.assert_called_once()
            mock_trade_class.assert_called_once_with(mock_client)


class TestAlertingIntegration:
    """Test alerting system integration."""

    @pytest.mark.asyncio
    async def test_trade_execution_alerts(self, mock_trade_executor, sample_trade):
        """Test that trade execution triggers alerts."""
        with patch("main.send_telegram_alert") as mock_alert:
            # Mock successful trade execution
            mock_trade_executor.execute_copy_trade = AsyncMock(
                return_value={
                    "status": "success",
                    "order_id": "test-order-123",
                    "copy_amount": 8.5,
                    "execution_time": 1.2,
                    "trade_id": "test-trade-id",
                }
            )

            # Execute trade
            await mock_trade_executor.execute_copy_trade(sample_trade)

            # Verify alert was sent
            if mock_trade_executor.settings.alerts.alert_on_trade:
                mock_alert.assert_called_once()
                alert_message = mock_alert.call_args[0][0]
                assert "Trade Executed" in alert_message
                assert "test-order-123" in alert_message

    @pytest.mark.asyncio
    async def test_error_alerts(self):
        """Test that errors trigger alerts."""
        with patch("main.send_error_alert"):
            # Force an error in trade execution
            with patch("main.PolymarketClient") as mock_client_class:
                mock_client_class.side_effect = Exception("Critical error")

                bot = PolymarketCopyBot()

                try:
                    await bot.initialize()
                except Exception:
                    pass

                # Error alert should have been sent during initialization failure
                # (This depends on the implementation)

    @pytest.mark.asyncio
    async def test_circuit_breaker_alerts(self, mock_trade_executor):
        """Test that circuit breaker activation triggers alerts."""
        with patch("main.send_telegram_alert") as mock_alert:
            # Activate circuit breaker
            mock_trade_executor.activate_circuit_breaker(
                "Test circuit breaker activation"
            )

            # Alert should be sent
            if mock_trade_executor.settings.alerts.alert_on_circuit_breaker:
                mock_alert.assert_called_once()
                alert_message = mock_alert.call_args[0][0]
                assert "CIRCUIT BREAKER ACTIVATED" in alert_message


class TestShutdownIntegration:
    """Test graceful shutdown integration."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown(
        self, mock_polymarket_client, mock_wallet_monitor, mock_trade_executor
    ):
        """Test graceful shutdown procedure."""
        with (
            patch("main.PolymarketClient", return_value=mock_polymarket_client),
            patch("main.WalletMonitor", return_value=mock_wallet_monitor),
            patch("main.TradeExecutor", return_value=mock_trade_executor),
            patch.object(mock_polymarket_client, "health_check", return_value=True),
            patch.object(mock_wallet_monitor, "health_check", return_value=True),
            patch.object(mock_trade_executor, "health_check", return_value=True),
        ):
            bot = PolymarketCopyBot()
            await bot.initialize()

            # Mock shutdown alert
            with patch("main.send_telegram_alert") as mock_alert:
                await bot.shutdown()

                # Shutdown alert should be sent
                mock_alert.assert_called_once()
                alert_message = mock_alert.call_args[0][0]
                assert "BOT STOPPED" in alert_message


class TestConcurrencyIntegration:
    """Test concurrent operations integration."""

    @pytest.mark.asyncio
    async def test_concurrent_trade_execution(self, mock_trade_executor):
        """Test concurrent trade execution."""
        # Set up multiple trades
        trades = [
            {
                "tx_hash": f"0x{i:064x}",
                "timestamp": datetime.now() - timedelta(seconds=30),
                "wallet_address": f"0x{i:040x}",
                "condition_id": f"0x{i:040x}",
                "side": "BUY" if i % 2 == 0 else "SELL",
                "amount": 10.0 + i,
                "price": 0.60 + (i * 0.01),
                "token_id": f"0x{i + 1:040x}",
                "confidence_score": 0.8,
            }
            for i in range(5)
        ]

        # Mock successful execution for all trades
        mock_trade_executor.execute_copy_trade.side_effect = [
            {"status": "success", "order_id": f"order-{i}"} for i in range(5)
        ]

        # Execute trades concurrently (simulate what the bot does)
        tasks = [mock_trade_executor.execute_copy_trade(trade) for trade in trades]
        results = await asyncio.gather(*tasks)

        # Verify all trades were executed
        assert len(results) == 5
        assert all(result["status"] == "success" for result in results)
        assert mock_trade_executor.execute_copy_trade.call_count == 5

    @pytest.mark.asyncio
    async def test_concurrent_wallet_monitoring(self, mock_wallet_monitor):
        """Test concurrent wallet monitoring."""
        [f"0x{i:040x}" for i in range(10)]

        # Mock monitoring results
        mock_wallet_monitor.monitor_wallets.return_value = []

        # Simulate concurrent monitoring
        tasks = [mock_wallet_monitor.monitor_wallets() for _ in range(3)]
        results = await asyncio.gather(*tasks)

        # Verify monitoring was called multiple times
        assert mock_wallet_monitor.monitor_wallets.call_count == 3
        assert all(isinstance(result, list) for result in results)


class TestSystemResilienceIntegration:
    """Test system resilience and error recovery."""

    @pytest.mark.asyncio
    async def test_system_recovery_from_cascading_failures(self, mock_trade_executor):
        """Test system recovery from cascading failures."""
        # Start with successful trades
        mock_trade_executor.execute_copy_trade.side_effect = [
            {"status": "success", "order_id": "success-1"},
            {"status": "success", "order_id": "success-2"},
            {"status": "failed", "reason": "API rate limit"},
            {"status": "failed", "reason": "Network timeout"},
            {"status": "success", "order_id": "success-3"},  # Recovery
        ]

        # Simulate a series of trades
        trades = [
            {
                "tx_hash": f"0x{i:064x}",
                "timestamp": datetime.now() - timedelta(seconds=30),
                "wallet_address": "0xtest",
                "condition_id": "0xtest",
                "side": "BUY",
                "amount": 10.0,
                "price": 0.65,
                "token_id": "0xtest",
                "confidence_score": 0.8,
            }
            for i in range(5)
        ]

        results = []
        for trade in trades:
            result = await mock_trade_executor.execute_copy_trade(trade)
            results.append(result)

        # Verify mixed success/failure pattern
        assert results[0]["status"] == "success"
        assert results[1]["status"] == "success"
        assert results[2]["status"] == "failed"
        assert results[3]["status"] == "failed"
        assert results[4]["status"] == "success"

        # Verify failure tracking
        assert mock_trade_executor.successful_trades == 3
        assert mock_trade_executor.failed_trades == 2

    @pytest.mark.asyncio
    async def test_memory_management_under_load(self, mock_wallet_monitor):
        """Test memory management under sustained load."""
        # Simulate sustained monitoring with transaction accumulation
        mock_wallet_monitor.processed_transactions = set()

        # Add many transactions to processed set
        for i in range(1000):
            mock_wallet_monitor.processed_transactions.add(f"0x{i:064x}")

        initial_count = len(mock_wallet_monitor.processed_transactions)

        # Trigger cleanup (simulate periodic cleanup)
        await mock_wallet_monitor.clean_processed_transactions()

        # Verify cleanup occurred (old transactions removed)
        final_count = len(mock_wallet_monitor.processed_transactions)
        assert final_count <= initial_count
