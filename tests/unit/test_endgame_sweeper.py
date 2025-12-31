"""
Unit tests for EndgameSweeper module.

This module provides comprehensive test coverage for the EndgameSweeper class,
including tests for market scanning, opportunity analysis, risk management,
and position management.

Author: Polymarket Bot Team
Version: 1.0.0
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.endgame_sweeper import (
    EndgameSweeper,
    EndgameTrade,
    EndgamePosition,
)
from core.circuit_breaker import CircuitBreaker
from utils.financial_calculations import FinancialCalculator


@pytest.fixture
def mock_clob_client():
    """Create a mock CLOB client for testing."""
    client = AsyncMock()
    client.get_balance = AsyncMock(return_value={"usdc": 10000.0})
    client.get_market = AsyncMock(return_value={"price": 0.97})
    client.get_markets = AsyncMock(return_value=[])
    client.place_order = AsyncMock(return_value={"orderID": "test_order_123"})
    client.wallet_address = "0x1234567890123456789012345678901234567890"
    return client


@pytest.fixture
def mock_circuit_breaker():
    """Create a mock circuit breaker for testing."""
    cb = MagicMock(spec=CircuitBreaker)
    cb.max_daily_loss = 100.0
    cb.check_trade_allowed = AsyncMock(return_value=None)
    cb.get_state = MagicMock(
        return_value={
            "active": False,
            "daily_loss": 0.0,
            "consecutive_losses": 0,
        }
    )
    cb.record_trade_result = AsyncMock()
    cb.record_loss = AsyncMock()
    cb.record_profit = AsyncMock()
    return cb


@pytest.fixture
def endgame_sweeper(mock_clob_client, mock_circuit_breaker):
    """Create an EndgameSweeper instance for testing."""
    return EndgameSweeper(
        clob_client=mock_clob_client,
        circuit_breaker=mock_circuit_breaker,
    )


class TestEndgameTrade:
    """Tests for EndgameTrade data class."""

    def test_endgame_trade_creation(self):
        """Test creating an EndgameTrade object."""
        trade = EndgameTrade(
            condition_id="test_condition_id",
            market_question="Will X happen?",
            probability=Decimal("0.96"),
            edge=Decimal("4.0"),
            annualized_return=Decimal("150.0"),
            days_to_resolution=3,
            liquidity_usdc=Decimal("15000.0"),
            token_id="token_123",
            entry_price=Decimal("0.96"),
        )

        assert trade.condition_id == "test_condition_id"
        assert trade.probability == Decimal("0.96")
        assert trade.edge == Decimal("4.0")
        assert trade.days_to_resolution == 3
        assert trade.liquidity_usdc == Decimal("15000.0")


class TestEndgamePosition:
    """Tests for EndgamePosition data class."""

    def test_endgame_position_creation(self):
        """Test creating an EndgamePosition object."""
        position = EndgamePosition(
            condition_id="test_condition_id",
            token_id="token_123",
            side="BUY",
            entry_price=Decimal("0.96"),
            position_size=Decimal("100.0"),
            entry_time=1234567890.0,
        )

        assert position.condition_id == "test_condition_id"
        assert position.side == "BUY"
        assert position.entry_price == Decimal("0.96")
        assert position.position_size == Decimal("100.0")
        assert position.exit_reason is None


class TestFinancialCalculations:
    """Tests for financial calculation methods."""

    def test_calculate_annualized_return(self):
        """Test annualized return calculation."""
        # Test case: 5% edge over 7 days
        edge = Decimal("0.05")
        days = 7
        annualized = FinancialCalculator.calculate_annualized_return(edge, days)

        # Should be significantly higher than 5% due to compounding
        assert annualized > Decimal("100.0")
        assert annualized < Decimal("1000.0")

    def test_calculate_edge(self):
        """Test edge calculation."""
        # 96% probability should give 4% edge
        probability = Decimal("0.96")
        edge = FinancialCalculator.calculate_edge(probability)

        assert edge == Decimal("4.0")

    def test_calculate_edge_boundary_cases(self):
        """Test edge calculation with boundary values."""
        # 100% probability = 0% edge
        assert FinancialCalculator.calculate_edge(Decimal("1.0")) == Decimal("0.0")

        # 95% probability = 5% edge
        assert FinancialCalculator.calculate_edge(Decimal("0.95")) == Decimal("5.0")

    def test_calculate_position_size(self):
        """Test position size calculation."""
        balance = Decimal("10000.0")
        risk_pct = Decimal("0.03")  # 3%
        max_size = Decimal("300.0")
        edge = Decimal("4.0")

        position_size = FinancialCalculator.calculate_position_size(
            balance, risk_pct, max_size, edge
        )

        # Should be 3% of balance ($300) or max_size, whichever is smaller
        assert position_size == Decimal("300.0")

    def test_calculate_profit_loss_long(self):
        """Test P&L calculation for long positions."""
        entry = Decimal("0.96")
        exit_price = Decimal("0.98")
        size = Decimal("100.0")

        pnl, pnl_pct = FinancialCalculator.calculate_profit_loss(
            entry, exit_price, size, is_long=True
        )

        # Should be profitable (price increased)
        assert pnl > Decimal("0.0")
        assert pnl_pct > Decimal("0.0")


class TestEndgameSweeperInit:
    """Tests for EndgameSweeper initialization."""

    def test_initialization(self, endgame_sweeper):
        """Test that EndgameSweeper initializes correctly."""
        assert endgame_sweeper.clob_client is not None
        assert endgame_sweeper.circuit_breaker is not None
        assert endgame_sweeper.total_scans == 0
        assert endgame_sweeper.trades_executed == 0
        assert endgame_sweeper.running is False

    def test_configuration_constants(self, endgame_sweeper):
        """Test that configuration constants are set correctly."""
        assert endgame_sweeper.MIN_PROBABILITY == Decimal("0.95")
        assert endgame_sweeper.MAX_PROBABILITY_EXIT == Decimal("0.998")
        assert endgame_sweeper.MIN_LIQUIDITY_USDC == Decimal("10000.0")
        assert endgame_sweeper.MAX_DAYS_TO_RESOLUTION == 7
        assert endgame_sweeper.MAX_POSITION_PERCENTAGE == Decimal("0.03")
        assert endgame_sweeper.STOP_LOSS_PERCENTAGE == Decimal("0.10")


class TestMarketAnalysis:
    """Tests for market analysis functionality."""

    @pytest.mark.asyncio
    async def test_find_opportunities_no_markets(self, endgame_sweeper):
        """Test finding opportunities when no markets available."""
        endgame_sweeper.clob_client.get_markets = AsyncMock(return_value=[])

        opportunities = await endgame_sweeper._find_opportunities()

        assert opportunities == []
        assert endgame_sweeper.clob_client.get_markets.called

    @pytest.mark.asyncio
    async def test_find_opportunities_with_valid_market(self, endgame_sweeper):
        """Test finding opportunities with valid market data."""
        # Create a valid high-probability market
        market = {
            "condition_id": "test_cond_123",
            "question": "Will this event occur?",
            "price": 0.96,
            "bestAsk": 0.96,
            "endTime": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            "liquidity": 15000.0,
            "token_id": "token_123",
        }

        endgame_sweeper.clob_client.get_markets = AsyncMock(return_value=[market])

        opportunities = await endgame_sweeper._find_opportunities()

        assert len(opportunities) == 1
        assert opportunities[0].condition_id == "test_cond_123"
        assert opportunities[0].probability == Decimal("0.96")

    @pytest.mark.asyncio
    async def test_filter_blacklisted_markets(self, endgame_sweeper):
        """Test that blacklisted markets are filtered out."""
        # Create a market with election keyword (blacklisted)
        market = {
            "condition_id": "election_market",
            "question": "Who will win the election?",
            "price": 0.97,
            "bestAsk": 0.97,
            "endTime": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            "liquidity": 15000.0,
            "token_id": "token_123",
        }

        endgame_sweeper.clob_client.get_markets = AsyncMock(return_value=[market])

        opportunities = await endgame_sweeper._find_opportunities()

        # Should be filtered out due to "election" keyword
        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_filter_by_probability(self, endgame_sweeper):
        """Test that low-probability markets are filtered out."""
        # Create a market with low probability
        market = {
            "condition_id": "low_prob_market",
            "question": "Will this happen?",
            "price": 0.85,  # Below 95% threshold
            "bestAsk": 0.85,
            "endTime": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            "liquidity": 15000.0,
            "token_id": "token_123",
        }

        endgame_sweeper.clob_client.get_markets = AsyncMock(return_value=[market])

        opportunities = await endgame_sweeper._find_opportunities()

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_filter_by_liquidity(self, endgame_sweeper):
        """Test that low-liquidity markets are filtered out."""
        # Create a market with low liquidity
        market = {
            "condition_id": "low_liquidity_market",
            "question": "Will this happen?",
            "price": 0.96,
            "bestAsk": 0.96,
            "endTime": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            "liquidity": 5000.0,  # Below $10K threshold
            "token_id": "token_123",
        }

        endgame_sweeper.clob_client.get_markets = AsyncMock(return_value=[market])

        opportunities = await endgame_sweeper._find_opportunities()

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_filter_by_days_to_resolution(self, endgame_sweeper):
        """Test that long-dated markets are filtered out."""
        # Create a market with long time to resolution
        market = {
            "condition_id": "long_date_market",
            "question": "Will this happen?",
            "price": 0.96,
            "bestAsk": 0.96,
            "endTime": (
                datetime.now(timezone.utc) + timedelta(days=10)
            ).isoformat(),  # Over 7-day limit
            "liquidity": 15000.0,
            "token_id": "token_123",
        }

        endgame_sweeper.clob_client.get_markets = AsyncMock(return_value=[market])

        opportunities = await endgame_sweeper._find_opportunities()

        assert len(opportunities) == 0


class TestRiskManagement:
    """Tests for risk management functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_trade(
        self, endgame_sweeper, mock_circuit_breaker
    ):
        """Test that circuit breaker blocks trades when active."""
        # Activate circuit breaker
        mock_circuit_breaker.get_state.return_value = {
            "active": True,
            "daily_loss": 150.0,
            "reason": "Daily loss limit reached",
        }

        # Create opportunity
        opportunity = EndgameTrade(
            condition_id="test_cond",
            market_question="Test question",
            probability=Decimal("0.96"),
            edge=Decimal("4.0"),
            annualized_return=Decimal("150.0"),
            days_to_resolution=3,
            liquidity_usdc=Decimal("15000.0"),
            token_id="token_123",
            entry_price=Decimal("0.96"),
        )

        # Should be filtered out
        filtered = await endgame_sweeper._filter_opportunities([opportunity])

        assert len(filtered) == 0

    @pytest.mark.asyncio
    async def test_max_concurrent_positions_limit(self, endgame_sweeper):
        """Test that max concurrent positions limit is enforced."""
        # Set up mock to indicate max positions reached
        endgame_sweeper.open_positions.set("pos1", {"data": "test"})
        endgame_sweeper.open_positions.set("pos2", {"data": "test"})
        endgame_sweeper.open_positions.set("pos3", {"data": "test"})
        endgame_sweeper.open_positions.set("pos4", {"data": "test"})
        endgame_sweeper.open_positions.set("pos5", {"data": "test"})
        endgame_sweeper.open_positions.set("pos6", {"data": "test"})
        endgame_sweeper.open_positions.set("pos7", {"data": "test"})
        endgame_sweeper.open_positions.set("pos8", {"data": "test"})
        endgame_sweeper.open_positions.set("pos9", {"data": "test"})
        endgame_sweeper.open_positions.set("pos10", {"data": "test"})

        # Create opportunity
        opportunity = EndgameTrade(
            condition_id="test_cond_new",
            market_question="Test question",
            probability=Decimal("0.96"),
            edge=Decimal("4.0"),
            annualized_return=Decimal("150.0"),
            days_to_resolution=3,
            liquidity_usdc=Decimal("15000.0"),
            token_id="token_123",
            entry_price=Decimal("0.96"),
        )

        # Should be filtered out due to max positions
        filtered = await endgame_sweeper._filter_opportunities([opportunity])

        assert len(filtered) == 0


class TestPositionManagement:
    """Tests for position management functionality."""

    @pytest.mark.asyncio
    async def test_check_exit_probability_threshold(self, endgame_sweeper):
        """Test auto-exit at 99.8% probability."""
        position = EndgamePosition(
            condition_id="test_cond",
            token_id="token_123",
            side="BUY",
            entry_price=Decimal("0.96"),
            position_size=Decimal("100.0"),
            entry_time=time.time(),
        )

        # Mock market with 99.9% probability
        endgame_sweeper.clob_client.get_market = AsyncMock(
            return_value={
                "price": 0.999,  # Above 99.8% threshold
                "endTime": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            }
        )

        position_key = "test_cond_BUY"
        exit_reason = await endgame_sweeper._check_exit_conditions(
            position, position_key
        )

        # Should trigger probability exit
        assert exit_reason == "PROBABILITY_EXIT"

    @pytest.mark.asyncio
    async def test_check_exit_stop_loss(self, endgame_sweeper):
        """Test stop loss at 10% move against entry."""
        position = EndgamePosition(
            condition_id="test_cond",
            token_id="token_123",
            side="BUY",
            entry_price=Decimal("0.96"),
            position_size=Decimal("100.0"),
            entry_time=time.time(),
        )

        # Mock market with 10% price drop
        endgame_sweeper.clob_client.get_market = AsyncMock(
            return_value={
                "price": 0.864,  # 10% drop from 0.96
                "endTime": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            }
        )

        position_key = "test_cond_BUY"
        exit_reason = await endgame_sweeper._check_exit_conditions(
            position, position_key
        )

        # Should trigger stop loss
        assert exit_reason == "STOP_LOSS"

    @pytest.mark.asyncio
    async def test_take_profit(self, endgame_sweeper):
        """Test take profit when price moves favorably."""
        position = EndgamePosition(
            condition_id="test_cond",
            token_id="token_123",
            side="BUY",
            entry_price=Decimal("0.96"),
            position_size=Decimal("100.0"),
            entry_time=time.time(),
        )

        # Mock market with 10% price increase
        endgame_sweeper.clob_client.get_market = AsyncMock(
            return_value={
                "price": 1.056,  # 10% increase from 0.96
                "endTime": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            }
        )

        position_key = "test_cond_BUY"
        exit_reason = await endgame_sweeper._check_exit_conditions(
            position, position_key
        )

        # Should trigger take profit
        assert exit_reason == "TAKE_PROFIT"


class TestCorrelationCheck:
    """Tests for correlation checking functionality."""

    def test_extract_keywords(self, endgame_sweeper):
        """Test keyword extraction from market question."""
        question = "Will Bitcoin price exceed $100,000 by end of year?"

        keywords = endgame_sweeper._extract_keywords(question)

        # Should extract meaningful keywords
        assert "bitcoin" in keywords
        assert "price" in keywords
        assert "exceed" in keywords
        assert "year" in keywords

    def test_check_correlation_overlap(self, endgame_sweeper):
        """Test correlation detection with existing positions."""
        # Add position with keywords
        endgame_sweeper.market_keywords.set("existing_market", {"bitcoin", "crypto"})

        # Create opportunity with overlapping keyword
        opportunity = EndgameTrade(
            condition_id="new_market",
            market_question="Will Bitcoin reach new highs?",
            probability=Decimal("0.96"),
            edge=Decimal("4.0"),
            annualized_return=Decimal("150.0"),
            days_to_resolution=3,
            liquidity_usdc=Decimal("15000.0"),
            token_id="token_123",
            entry_price=Decimal("0.96"),
        )

        # Should detect correlation
        safe_opps = await endgame_sweeper._check_correlations([opportunity])

        assert len(safe_opps) == 0


class TestIntegration:
    """Integration tests for end-to-end functionality."""

    @pytest.mark.asyncio
    async def test_full_scan_and_execute(self, endgame_sweeper):
        """Test complete scan and execute workflow."""
        # Mock market data
        market = {
            "condition_id": "test_cond",
            "question": "Will this event occur?",
            "price": 0.96,
            "bestAsk": 0.96,
            "endTime": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            "liquidity": 15000.0,
            "token_id": "token_123",
        }

        endgame_sweeper.clob_client.get_markets = AsyncMock(return_value=[market])

        # Run scan
        result = await endgame_sweeper.scan_and_execute()

        # Verify results
        assert "scan_time" in result
        assert "total_opportunities" in result
        assert "trades_executed" in result
        assert result["total_opportunities"] >= 0

    def test_get_stats(self, endgame_sweeper):
        """Test statistics retrieval."""
        stats = endgame_sweeper.get_stats()

        assert "running" in stats
        assert "total_scans" in stats
        assert "opportunities_found" in stats
        assert "trades_executed" in stats
        assert "open_positions" in stats

    @pytest.mark.asyncio
    async def test_health_check(self, endgame_sweeper):
        """Test health check functionality."""
        health = await endgame_sweeper.health_check()

        assert isinstance(health, bool)


# Helper function for running tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
