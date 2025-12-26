"""
Unit tests for core/trade_executor.py - Trade execution and risk management.
"""
import pytest
import asyncio
import time
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from core.trade_executor import TradeExecutor
from utils.helpers import normalize_address


class TestTradeExecutorInitialization:
    """Test TradeExecutor initialization."""

    def test_executor_initialization_success(self, mock_polymarket_client, test_settings):
        """Test successful trade executor initialization."""
        executor = TradeExecutor(mock_polymarket_client)

        assert executor.clob_client == mock_polymarket_client
        assert executor.wallet_address == mock_polymarket_client.wallet_address
        assert executor.daily_loss == 0.0
        assert executor.total_trades == 0
        assert executor.successful_trades == 0
        assert executor.failed_trades == 0
        assert isinstance(executor.open_positions, dict)
        assert isinstance(executor.trade_performance, list)
        assert not executor.circuit_breaker_active

    def test_executor_initialization_with_settings(self, mock_polymarket_client, test_settings):
        """Test executor initialization with settings reference."""
        executor = TradeExecutor(mock_polymarket_client)

        assert executor.settings == test_settings


class TestTradeExecutorValidation:
    """Test trade validation functionality."""

    def test_validate_trade_success(self, mock_trade_executor, sample_trade):
        """Test successful trade validation."""
        is_valid = mock_trade_executor._validate_trade(sample_trade)

        assert is_valid is True

    def test_validate_trade_missing_fields(self, mock_trade_executor, sample_trade):
        """Test trade validation with missing required fields."""
        del sample_trade['tx_hash']

        is_valid = mock_trade_executor._validate_trade(sample_trade)

        assert is_valid is False

    @pytest.mark.parametrize("invalid_side", ["INVALID", "buy", "sell", ""])
    def test_validate_trade_invalid_side(self, mock_trade_executor, sample_trade, invalid_side):
        """Test trade validation with invalid side."""
        sample_trade['side'] = invalid_side

        is_valid = mock_trade_executor._validate_trade(sample_trade)

        assert is_valid is False

    @pytest.mark.parametrize("invalid_price", [-0.1, 0.0, 1.1, 2.0])
    def test_validate_trade_invalid_price(self, mock_trade_executor, sample_trade, invalid_price):
        """Test trade validation with invalid price."""
        sample_trade['price'] = invalid_price

        is_valid = mock_trade_executor._validate_trade(sample_trade)

        assert is_valid is False

    def test_validate_trade_invalid_amount(self, mock_trade_executor, sample_trade):
        """Test trade validation with invalid amount."""
        sample_trade['amount'] = -10.0

        is_valid = mock_trade_executor._validate_trade(sample_trade)

        assert is_valid is False

    def test_validate_trade_stale_timestamp(self, mock_trade_executor, sample_trade):
        """Test trade validation with stale timestamp."""
        sample_trade['timestamp'] = datetime.now() - timedelta(minutes=10)  # Older than 5 minutes

        is_valid = mock_trade_executor._validate_trade(sample_trade)

        # Should still be valid but log a warning
        assert is_valid is True


class TestTradeExecutorRiskManagement:
    """Test risk management functionality."""

    def test_apply_risk_management_success(self, mock_trade_executor, sample_trade):
        """Test successful risk management check."""
        result = mock_trade_executor._apply_risk_management(sample_trade)

        assert result['approved'] is True

    def test_apply_risk_management_daily_loss_limit(self, mock_trade_executor, sample_trade):
        """Test risk management with daily loss limit exceeded."""
        mock_trade_executor.daily_loss = 150.0  # Above 100.0 limit

        result = mock_trade_executor._apply_risk_management(sample_trade)

        assert result['approved'] is False
        assert 'Daily loss limit reached' in result['reason']

    def test_apply_risk_management_position_size_limit(self, mock_trade_executor, sample_trade):
        """Test risk management with position size limit exceeded."""
        sample_trade['amount'] = 100.0  # Above 50.0 limit

        result = mock_trade_executor._apply_risk_management(sample_trade)

        assert result['approved'] is False
        assert 'Position size too large' in result['reason']

    def test_apply_risk_management_min_trade_amount(self, mock_trade_executor, sample_trade):
        """Test risk management with trade amount below minimum."""
        sample_trade['amount'] = 0.5  # Below 1.0 minimum

        result = mock_trade_executor._apply_risk_management(sample_trade)

        assert result['approved'] is False
        assert 'below minimum' in result['reason']

    def test_apply_risk_management_concurrent_positions_limit(self, mock_trade_executor, sample_trade):
        """Test risk management with concurrent positions limit exceeded."""
        # Add 10 existing positions
        mock_trade_executor.open_positions = {f"pos_{i}": {} for i in range(10)}

        result = mock_trade_executor._apply_risk_management(sample_trade)

        assert result['approved'] is False
        assert 'Max concurrent positions reached' in result['reason']

    def test_apply_risk_management_low_confidence(self, mock_trade_executor, sample_trade):
        """Test risk management with low confidence score."""
        sample_trade['confidence_score'] = 0.5  # Below 0.7 minimum

        result = mock_trade_executor._apply_risk_management(sample_trade)

        assert result['approved'] is False
        assert 'Low confidence score' in result['reason']


class TestTradeExecutorCopyAmountCalculation:
    """Test copy amount calculation functionality."""

    async def test_calculate_copy_amount_success(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test successful copy amount calculation."""
        # Mock balance and price
        mock_polymarket_client.get_balance.return_value = 1000.0
        mock_polymarket_client.get_current_price.return_value = 0.65

        copy_amount = await mock_trade_executor._calculate_copy_amount(sample_trade, sample_market_data)

        assert isinstance(copy_amount, float)
        assert copy_amount > 0
        assert copy_amount <= mock_trade_executor.settings.risk.max_position_size

    async def test_calculate_copy_amount_balance_unavailable(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test copy amount calculation when balance is unavailable."""
        mock_polymarket_client.get_balance.return_value = None

        copy_amount = await mock_trade_executor._calculate_copy_amount(sample_trade, sample_market_data)

        # Should use conservative fallback
        assert copy_amount == min(sample_trade['amount'] * 0.1, mock_trade_executor.settings.risk.max_position_size)

    async def test_calculate_copy_amount_price_unavailable(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test copy amount calculation when current price is unavailable."""
        mock_polymarket_client.get_balance.return_value = 1000.0
        mock_polymarket_client.get_current_price.return_value = None

        copy_amount = await mock_trade_executor._calculate_copy_amount(sample_trade, sample_market_data)

        # Should use trade price as fallback
        assert isinstance(copy_amount, float)

    async def test_calculate_copy_amount_risk_based(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test risk-based copy amount calculation."""
        mock_polymarket_client.get_balance.return_value = 2000.0  # Large balance
        mock_polymarket_client.get_current_price.return_value = 0.65

        copy_amount = await mock_trade_executor._calculate_copy_amount(sample_trade, sample_market_data)

        # Should be higher with larger balance
        assert copy_amount > sample_trade['amount'] * 0.1

    async def test_calculate_copy_amount_capped_by_max_position(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test copy amount capping by max position size."""
        mock_polymarket_client.get_balance.return_value = 10000.0  # Very large balance
        mock_polymarket_client.get_current_price.return_value = 0.65

        copy_amount = await mock_trade_executor._calculate_copy_amount(sample_trade, sample_market_data)

        # Should be capped at max position size
        assert copy_amount <= mock_trade_executor.settings.risk.max_position_size

    async def test_calculate_copy_amount_minimum_trade_amount(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test copy amount meets minimum trade requirements."""
        mock_polymarket_client.get_balance.return_value = 10.0  # Small balance
        mock_polymarket_client.get_current_price.return_value = 0.65

        copy_amount = await mock_trade_executor._calculate_copy_amount(sample_trade, sample_market_data)

        # Should meet minimum trade amount
        assert copy_amount >= mock_trade_executor.settings.risk.min_trade_amount


class TestTradeExecutorTokenIdDetermination:
    """Test token ID determination functionality."""

    def test_get_token_id_for_outcome_buy(self, mock_trade_executor, sample_trade, sample_market_data):
        """Test token ID determination for BUY orders."""
        sample_trade['side'] = 'BUY'

        token_id = mock_trade_executor._get_token_id_for_outcome(sample_market_data, sample_trade)

        assert token_id == sample_market_data['tokens'][0]['tokenId']

    def test_get_token_id_for_outcome_sell(self, mock_trade_executor, sample_trade, sample_market_data):
        """Test token ID determination for SELL orders."""
        sample_trade['side'] = 'SELL'

        token_id = mock_trade_executor._get_token_id_for_outcome(sample_market_data, sample_trade)

        assert token_id == sample_market_data['tokens'][-1]['tokenId']

    def test_get_token_id_missing_tokens(self, mock_trade_executor, sample_trade):
        """Test token ID determination when market has no tokens."""
        market_data = {'conditionId': 'test'}

        token_id = mock_trade_executor._get_token_id_for_outcome(market_data, sample_trade)

        assert token_id is None

    def test_get_token_id_outcomes_fallback(self, mock_trade_executor, sample_trade):
        """Test token ID determination using outcomes fallback."""
        market_data = {
            'conditionId': 'test',
            'outcomes': [{'tokenId': 'fallback-token-id'}]
        }

        token_id = mock_trade_executor._get_token_id_for_outcome(market_data, sample_trade)

        assert token_id == 'fallback-token-id'


class TestTradeExecutorMainExecution:
    """Test main trade execution functionality."""

    async def test_execute_copy_trade_success(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test successful copy trade execution."""
        # Mock all dependencies
        mock_polymarket_client.get_market.return_value = sample_market_data
        mock_polymarket_client.place_order.return_value = {'orderID': 'test-order-123'}
        mock_polymarket_client.get_balance.return_value = 1000.0
        mock_polymarket_client.get_current_price.return_value = 0.65

        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result['status'] == 'success'
        assert result['order_id'] == 'test-order-123'
        assert 'copy_amount' in result
        assert 'trade_id' in result

    async def test_execute_copy_trade_circuit_breaker_active(self, mock_trade_executor, sample_trade):
        """Test copy trade execution when circuit breaker is active."""
        mock_trade_executor.circuit_breaker_active = True
        mock_trade_executor.circuit_breaker_reason = "Test circuit breaker"

        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result['status'] == 'skipped'
        assert 'Circuit breaker' in result['reason']

    async def test_execute_copy_trade_invalid_trade(self, mock_trade_executor, sample_trade):
        """Test copy trade execution with invalid trade data."""
        del sample_trade['tx_hash']  # Make trade invalid

        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result['status'] == 'invalid'

    async def test_execute_copy_trade_risk_rejected(self, mock_trade_executor, sample_trade):
        """Test copy trade execution when rejected by risk management."""
        # Force rejection by exceeding daily loss
        mock_trade_executor.daily_loss = 150.0

        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result['status'] == 'rejected'
        assert 'Daily loss limit reached' in result['reason']

    async def test_execute_copy_trade_market_not_found(self, mock_trade_executor, sample_trade, mock_polymarket_client):
        """Test copy trade execution when market is not found."""
        mock_polymarket_client.get_market.return_value = None

        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result['status'] == 'failed'
        assert 'Market not found' in result['reason']

    async def test_execute_copy_trade_amount_too_small(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test copy trade execution when calculated amount is too small."""
        mock_polymarket_client.get_market.return_value = sample_market_data
        mock_polymarket_client.get_balance.return_value = 10.0  # Very small balance

        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result['status'] == 'skipped'
        assert 'too small' in result['reason']

    async def test_execute_copy_trade_token_id_not_found(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test copy trade execution when token ID cannot be determined."""
        market_data_no_tokens = {'conditionId': 'test'}  # No tokens
        mock_polymarket_client.get_market.return_value = market_data_no_tokens

        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result['status'] == 'failed'
        assert 'Token ID not found' in result['reason']

    async def test_execute_copy_trade_order_failure(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test copy trade execution when order placement fails."""
        mock_polymarket_client.get_market.return_value = sample_market_data
        mock_polymarket_client.place_order.return_value = None
        mock_polymarket_client.get_balance.return_value = 1000.0

        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result['status'] == 'failed'
        assert 'Order placement failed' in result['reason']

    async def test_execute_copy_trade_execution_error(self, mock_trade_executor, sample_trade, mock_polymarket_client):
        """Test copy trade execution with execution error."""
        mock_polymarket_client.get_market.side_effect = Exception("API Error")

        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result['status'] == 'error'
        assert 'API Error' in str(result['error'])


class TestTradeExecutorPositionManagement:
    """Test position management functionality."""

    async def test_manage_positions_no_positions(self, mock_trade_executor):
        """Test position management with no open positions."""
        await mock_trade_executor.manage_positions()

        # Should complete without error
        assert mock_trade_executor.open_positions == {}

    async def test_manage_positions_with_take_profit(self, mock_trade_executor, mock_polymarket_client):
        """Test position management with take profit trigger."""
        # Set up a position that should trigger take profit
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

        # Mock current price that's above take profit threshold
        mock_polymarket_client.get_current_price.return_value = 0.73  # 21.7% profit

        await mock_trade_executor.manage_positions()

        # Position should be closed
        assert position_key not in mock_trade_executor.open_positions

    async def test_manage_positions_with_stop_loss(self, mock_trade_executor, mock_polymarket_client):
        """Test position management with stop loss trigger."""
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

        # Mock current price that's below stop loss threshold
        mock_polymarket_client.get_current_price.return_value = 0.47  # 21.7% loss

        await mock_trade_executor.manage_positions()

        # Position should be closed
        assert position_key not in mock_trade_executor.open_positions

    async def test_manage_positions_time_based_exit(self, mock_trade_executor, mock_polymarket_client):
        """Test position management with time-based exit."""
        position_key = "test_condition_BUY"
        position = {
            'amount': 10.0,
            'entry_price': 0.60,
            'timestamp': time.time() - 90000,  # 25 hours ago
            'original_trade': {
                'condition_id': 'test_condition',
                'side': 'BUY',
                'wallet_address': '0xtest'
            },
            'order_id': 'test-order-123'
        }
        mock_trade_executor.open_positions[position_key] = position

        mock_polymarket_client.get_current_price.return_value = 0.60  # No P&L

        await mock_trade_executor.manage_positions()

        # Position should be closed due to time
        assert position_key not in mock_trade_executor.open_positions

    async def test_manage_positions_sell_side(self, mock_trade_executor, mock_polymarket_client):
        """Test position management for SELL positions."""
        position_key = "test_condition_SELL"
        position = {
            'amount': 10.0,
            'entry_price': 0.60,
            'timestamp': time.time(),
            'original_trade': {
                'condition_id': 'test_condition',
                'side': 'SELL',
                'wallet_address': '0xtest'
            },
            'order_id': 'test-order-123'
        }
        mock_trade_executor.open_positions[position_key] = position

        # For SELL positions, profit when price goes down
        mock_polymarket_client.get_current_price.return_value = 0.48  # Price decreased

        await mock_trade_executor.manage_positions()

        # Position should still be open (no trigger conditions met)
        assert position_key in mock_trade_executor.open_positions


class TestTradeExecutorCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initial_state(self, mock_trade_executor):
        """Test circuit breaker initial state."""
        assert not mock_trade_executor.circuit_breaker_active
        assert mock_trade_executor.circuit_breaker_reason == ""
        assert mock_trade_executor.circuit_breaker_time is None

    def test_activate_circuit_breaker(self, mock_trade_executor):
        """Test circuit breaker activation."""
        reason = "Test activation"

        mock_trade_executor.activate_circuit_breaker(reason)

        assert mock_trade_executor.circuit_breaker_active
        assert mock_trade_executor.circuit_breaker_reason == reason
        assert mock_trade_executor.circuit_breaker_time is not None

    def test_reset_circuit_breaker(self, mock_trade_executor):
        """Test circuit breaker reset."""
        mock_trade_executor.activate_circuit_breaker("Test reason")
        assert mock_trade_executor.circuit_breaker_active

        mock_trade_executor.reset_circuit_breaker()

        assert not mock_trade_executor.circuit_breaker_active
        assert mock_trade_executor.circuit_breaker_reason == ""
        assert mock_trade_executor.circuit_breaker_time is None

    def test_get_circuit_breaker_remaining_time_inactive(self, mock_trade_executor):
        """Test remaining time when circuit breaker is inactive."""
        remaining_time = mock_trade_executor._get_circuit_breaker_remaining_time()

        assert remaining_time == 0.0

    def test_get_circuit_breaker_remaining_time_active(self, mock_trade_executor):
        """Test remaining time when circuit breaker is active."""
        mock_trade_executor.activate_circuit_breaker("Test")

        # Mock the time to be recent
        mock_trade_executor.circuit_breaker_time = time.time() - 1800  # 30 minutes ago

        remaining_time = mock_trade_executor._get_circuit_breaker_remaining_time()

        # Should have ~30 minutes remaining (3600 - 1800 = 1800 seconds = 30 minutes)
        assert 25 <= remaining_time <= 35  # Allow some tolerance

    def test_check_circuit_breaker_conditions_daily_loss(self, mock_trade_executor):
        """Test circuit breaker activation due to daily loss."""
        mock_trade_executor.daily_loss = 150.0  # Above threshold

        mock_trade_executor._check_circuit_breaker_conditions()

        assert mock_trade_executor.circuit_breaker_active
        assert "Daily loss limit reached" in mock_trade_executor.circuit_breaker_reason

    def test_check_circuit_breaker_conditions_failure_rate(self, mock_trade_executor):
        """Test circuit breaker activation due to high failure rate."""
        mock_trade_executor.total_trades = 20
        mock_trade_executor.failed_trades = 12  # 60% failure rate

        mock_trade_executor._check_circuit_breaker_conditions()

        assert mock_trade_executor.circuit_breaker_active
        assert "High failure rate" in mock_trade_executor.circuit_breaker_reason

    def test_check_circuit_breaker_conditions_reset(self, mock_trade_executor):
        """Test circuit breaker reset when conditions improve."""
        mock_trade_executor.activate_circuit_breaker("Test reason")

        # Mock time passage
        mock_trade_executor.circuit_breaker_time = time.time() - 7200  # 2 hours ago

        # Reset failure rates
        mock_trade_executor.failed_trades = 0
        mock_trade_executor.total_trades = 5

        mock_trade_executor._check_circuit_breaker_conditions()

        assert not mock_trade_executor.circuit_breaker_active


class TestTradeExecutorPositionClosing:
    """Test position closing functionality."""

    async def test_close_position_success(self, mock_trade_executor, mock_polymarket_client):
        """Test successful position closing."""
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

        mock_polymarket_client.get_current_price.return_value = 0.70
        mock_polymarket_client.place_order.return_value = {'orderID': 'close-order-456'}

        await mock_trade_executor._close_position(position_key, "TAKE_PROFIT")

        # Position should be removed
        assert position_key not in mock_trade_executor.open_positions

        # Daily loss should be updated (this was a profitable trade)
        assert mock_trade_executor.daily_loss < 0  # Negative means profit

    async def test_close_position_failure(self, mock_trade_executor, mock_polymarket_client):
        """Test position closing failure."""
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

        mock_polymarket_client.get_current_price.return_value = 0.70
        mock_polymarket_client.place_order.return_value = None  # Order failed

        await mock_trade_executor._close_position(position_key, "TAKE_PROFIT")

        # Position should still exist
        assert position_key in mock_trade_executor.open_positions


class TestTradeExecutorDailyLossTracking:
    """Test daily loss tracking functionality."""

    async def test_update_daily_loss_reset(self, mock_trade_executor):
        """Test daily loss reset at midnight UTC."""
        # Set up mock last reset time to yesterday
        yesterday = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        mock_trade_executor.last_reset_time = yesterday

        await mock_trade_executor._update_daily_loss()

        # Daily loss should be reset to 0
        assert mock_trade_executor.daily_loss == 0.0

    async def test_update_daily_loss_no_reset(self, mock_trade_executor):
        """Test daily loss when no reset is needed."""
        original_loss = 50.0
        mock_trade_executor.daily_loss = original_loss

        # Set last reset to today
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        mock_trade_executor.last_reset_time = today

        await mock_trade_executor._update_daily_loss()

        # Daily loss should remain unchanged
        assert mock_trade_executor.daily_loss == original_loss


class TestTradeExecutorHealthCheck:
    """Test health check functionality."""

    async def test_health_check_success(self, mock_trade_executor, mock_polymarket_client):
        """Test successful health check."""
        mock_polymarket_client.get_balance.return_value = 1000.0

        healthy = await mock_trade_executor.health_check()

        assert healthy is True

    async def test_health_check_balance_failure(self, mock_trade_executor, mock_polymarket_client):
        """Test health check failure due to balance retrieval error."""
        mock_polymarket_client.get_balance.side_effect = Exception("API Error")

        healthy = await mock_trade_executor.health_check()

        assert healthy is False

    async def test_health_check_circuit_breaker_warning(self, mock_trade_executor, mock_polymarket_client):
        """Test health check with circuit breaker warning."""
        mock_polymarket_client.get_balance.return_value = 1000.0
        mock_trade_executor.circuit_breaker_active = True

        healthy = await mock_trade_executor.health_check()

        # Should still pass but with warning
        assert healthy is True

    async def test_health_check_too_many_positions(self, mock_trade_executor, mock_polymarket_client):
        """Test health check with too many open positions."""
        mock_polymarket_client.get_balance.return_value = 1000.0

        # Add many positions
        max_positions = mock_trade_executor.settings.risk.max_concurrent_positions
        mock_trade_executor.open_positions = {f"pos_{i}": {} for i in range(max_positions * 2)}

        healthy = await mock_trade_executor.health_check()

        # Should still pass but with warning
        assert healthy is True


class TestTradeExecutorPerformanceMetrics:
    """Test performance metrics functionality."""

    def test_get_performance_metrics_success(self, mock_trade_executor):
        """Test successful performance metrics retrieval."""
        # Set up some mock data
        mock_trade_executor.total_trades = 100
        mock_trade_executor.successful_trades = 85
        mock_trade_executor.failed_trades = 15
        mock_trade_executor.daily_loss = -25.0  # Profit
        mock_trade_executor.open_positions = {"pos1": {}, "pos2": {}}
        mock_trade_executor.circuit_breaker_active = False
        mock_trade_executor.last_trade_time = time.time() - 3600
        mock_trade_executor.start_time = time.time() - 86400  # 1 day ago

        # Add some trade performance data
        mock_trade_executor.trade_performance = [
            {'execution_time': 1.5, 'status': 'success'},
            {'execution_time': 2.1, 'status': 'success'},
            {'execution_time': 3.2, 'status': 'failed'}
        ]

        metrics = mock_trade_executor.get_performance_metrics()

        assert metrics['total_trades'] == 100
        assert metrics['successful_trades'] == 85
        assert metrics['failed_trades'] == 15
        assert metrics['success_rate'] == 0.85
        assert metrics['daily_loss'] == -25.0
        assert metrics['open_positions'] == 2
        assert metrics['circuit_breaker_active'] is False
        assert 'last_trade_time' in metrics
        assert 'uptime_hours' in metrics
        assert 'avg_execution_time' in metrics

    def test_get_performance_metrics_no_trades(self, mock_trade_executor):
        """Test performance metrics with no trades."""
        metrics = mock_trade_executor.get_performance_metrics()

        assert metrics['total_trades'] == 0
        assert metrics['successful_trades'] == 0
        assert metrics['failed_trades'] == 0
        assert metrics['success_rate'] == 0.0
        assert metrics['daily_loss'] == 0.0
        assert metrics['open_positions'] == 0


class TestTradeExecutorIntegration:
    """Integration tests for TradeExecutor."""

    async def test_full_trade_execution_flow(self, mock_trade_executor, sample_trade, sample_market_data, mock_polymarket_client):
        """Test complete trade execution flow."""
        # Set up mocks for successful execution
        mock_polymarket_client.get_market.return_value = sample_market_data
        mock_polymarket_client.get_balance.return_value = 1000.0
        mock_polymarket_client.get_current_price.return_value = 0.65
        mock_polymarket_client.place_order.return_value = {'orderID': 'integration-test-order'}

        # Execute trade
        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        # Verify success
        assert result['status'] == 'success'
        assert result['order_id'] == 'integration-test-order'

        # Verify state updates
        assert mock_trade_executor.total_trades == 1
        assert mock_trade_executor.successful_trades == 1
        assert len(mock_trade_executor.open_positions) == 1
        assert len(mock_trade_executor.trade_performance) == 1

    async def test_position_management_flow(self, mock_trade_executor, mock_polymarket_client):
        """Test complete position management flow."""
        # Set up position
        position_key = "test_condition_BUY"
        position = {
            'amount': 10.0,
            'entry_price': 0.60,
            'timestamp': time.time() - 90000,  # Old enough for time-based exit
            'original_trade': {
                'condition_id': 'test_condition',
                'side': 'BUY',
                'wallet_address': '0xtest'
            },
            'order_id': 'test-order-123'
        }
        mock_trade_executor.open_positions[position_key] = position

        # Mock closing order
        mock_polymarket_client.get_current_price.return_value = 0.60
        mock_polymarket_client.place_order.return_value = {'orderID': 'close-order'}

        # Run position management
        await mock_trade_executor.manage_positions()

        # Position should be closed
        assert position_key not in mock_trade_executor.open_positions

    async def test_circuit_breaker_flow(self, mock_trade_executor, sample_trade):
        """Test complete circuit breaker flow."""
        # Trigger circuit breaker
        mock_trade_executor.daily_loss = 150.0
        mock_trade_executor._check_circuit_breaker_conditions()

        assert mock_trade_executor.circuit_breaker_active

        # Try to execute trade (should be blocked)
        result = await mock_trade_executor.execute_copy_trade(sample_trade)

        assert result['status'] == 'skipped'
        assert 'Circuit breaker' in result['reason']

        # Simulate time passage and reset
        mock_trade_executor.circuit_breaker_time = time.time() - 7200  # 2 hours ago
        mock_trade_executor.daily_loss = 0.0  # Reset loss

        mock_trade_executor._check_circuit_breaker_conditions()

        # Circuit breaker should be reset
        assert not mock_trade_executor.circuit_breaker_active
