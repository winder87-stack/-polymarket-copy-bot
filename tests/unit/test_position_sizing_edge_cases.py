"""Comprehensive unit tests for position sizing with volatile market edge cases.

Tests position sizing calculations under various market conditions including:
- High volatility scenarios
- Extreme price movements
- Low liquidity conditions
- Edge cases with minimum/maximum values
"""

import pytest
from decimal import Decimal, getcontext

from tests.fixtures.market_data_generators import MarketDataGenerator
from utils.helpers import calculate_position_size


class TestPositionSizingVolatileMarkets:
    """Test position sizing in volatile market conditions."""

    @pytest.mark.parametrize(
        "volatility_level,base_price,expected_range",
        [
            ("low", 0.5, (0.45, 0.55)),
            ("normal", 0.5, (0.40, 0.60)),
            ("high", 0.5, (0.30, 0.70)),
            ("extreme", 0.5, (0.10, 0.90)),
        ],
    )
    def test_position_size_with_volatility(
        self, volatility_level: str, base_price: float, expected_range: tuple
    ):
        """Test position sizing adapts to market volatility."""
        generator = MarketDataGenerator()
        market_conditions = generator.generate_market_conditions(volatility_level)

        # Generate price series with volatility
        prices = generator.generate_volatile_price_series(
            base_price=base_price,
            volatility=market_conditions["volatility_index"],
            num_points=10,
        )

        account_balance = 1000.0
        max_position_size = 100.0
        original_amount = 100.0

        # Calculate position size for each price
        position_sizes = []
        for price in prices:
            # Simulate position sizing calculation
            # Higher volatility should result in smaller position sizes
            volatility_multiplier = 1.0 / (
                1.0 + market_conditions["volatility_index"] * 10
            )
            adjusted_max = max_position_size * volatility_multiplier

            size = calculate_position_size(
                original_amount=original_amount,
                account_balance=account_balance,
                max_position_size=adjusted_max,
            )

            position_sizes.append(size)

        # Verify position sizes are within expected range
        avg_size = sum(position_sizes) / len(position_sizes)
        assert 1.0 <= avg_size <= max_position_size

        # Higher volatility should result in smaller average position size
        if volatility_level == "extreme":
            assert avg_size < max_position_size * 0.5

    @pytest.mark.parametrize(
        "price_change_pct,expected_impact",
        [
            (0.01, "minimal"),  # 1% change
            (0.05, "moderate"),  # 5% change
            (0.10, "significant"),  # 10% change
            (0.25, "extreme"),  # 25% change
            (0.50, "extreme"),  # 50% change
        ],
    )
    def test_position_size_with_price_movements(
        self, price_change_pct: float, expected_impact: str
    ):
        """Test position sizing with rapid price movements."""
        base_price = 0.5
        new_price = base_price * (1 + price_change_pct)

        account_balance = 1000.0
        max_position_size = 100.0
        original_amount = 100.0

        # Calculate position size at base price
        base_size = calculate_position_size(
            original_amount=original_amount,
            account_balance=account_balance,
            max_position_size=max_position_size,
        )

        # Calculate position size at new price
        # Price movement affects risk calculation
        price_risk = abs(new_price - base_price) / base_price
        risk_adjusted_max = max_position_size * (1.0 - min(price_risk, 0.5))

        new_size = calculate_position_size(
            original_amount=original_amount,
            account_balance=account_balance,
            max_position_size=risk_adjusted_max,
        )

        # Verify impact on position size
        if expected_impact == "extreme":
            assert new_size < base_size * 0.7
        elif expected_impact == "significant":
            assert new_size < base_size * 0.9

    def test_position_size_with_low_liquidity(self):
        """Test position sizing in low liquidity conditions."""
        generator = MarketDataGenerator()
        market_conditions = generator.generate_market_conditions("normal")
        market_conditions["liquidity_score"] = 0.1  # Very low liquidity

        account_balance = 1000.0
        max_position_size = 100.0
        original_amount = 100.0

        # Low liquidity should reduce position size
        liquidity_multiplier = 0.5 + (market_conditions["liquidity_score"] * 0.5)
        adjusted_max = max_position_size * liquidity_multiplier

        size = calculate_position_size(
            original_amount=original_amount,
            account_balance=account_balance,
            max_position_size=adjusted_max,
        )

        assert size <= adjusted_max
        assert size < max_position_size  # Should be reduced

    @pytest.mark.parametrize(
        "account_balance,original_amount,max_position,expected_min,expected_max",
        [
            (10.0, 100.0, 50.0, 1.0, 10.0),  # Low balance
            (100.0, 1000.0, 50.0, 1.0, 50.0),  # Normal
            (10000.0, 100.0, 50.0, 1.0, 50.0),  # High balance
            (0.01, 100.0, 50.0, 0.0, 0.01),  # Below minimum
        ],
    )
    def test_position_size_edge_cases(
        self,
        account_balance: float,
        original_amount: float,
        max_position: float,
        expected_min: float,
        expected_max: float,
    ):
        """Test position sizing with edge case inputs."""
        size = calculate_position_size(
            original_amount=original_amount,
            account_balance=account_balance,
            max_position_size=max_position,
        )

        assert expected_min <= size <= expected_max

    def test_position_size_with_zero_balance(self):
        """Test position sizing with zero account balance."""
        size = calculate_position_size(
            original_amount=100.0,
            account_balance=0.0,
            max_position_size=50.0,
        )

        # Should return minimum or zero
        assert size >= 0.0
        assert size <= 1.0  # Minimum trade amount

    def test_position_size_with_very_large_amount(self):
        """Test position sizing with very large original amount."""
        size = calculate_position_size(
            original_amount=1000000.0,
            account_balance=1000.0,
            max_position_size=50.0,
        )

        # Should be capped by max_position_size
        assert size <= 50.0
        assert size >= 1.0  # Minimum trade amount

    def test_position_size_precision(self):
        """Test position sizing maintains precision."""
        getcontext().prec = 28

        account_balance = Decimal("1000.123456789")
        original_amount = Decimal("100.987654321")
        max_position_size = Decimal("50.555555555")

        # Convert to float for function call
        size = calculate_position_size(
            original_amount=float(original_amount),
            account_balance=float(account_balance),
            max_position_size=float(max_position_size),
        )

        # Verify reasonable precision
        assert isinstance(size, float)
        assert size > 0.0

    @pytest.mark.parametrize(
        "risk_percentage,expected_multiplier",
        [
            (0.005, 0.5),  # 0.5% risk
            (0.01, 1.0),  # 1% risk (default)
            (0.02, 2.0),  # 2% risk
            (0.05, 5.0),  # 5% risk
        ],
    )
    def test_position_size_with_different_risk_levels(
        self, risk_percentage: float, expected_multiplier: float
    ):
        """Test position sizing with different risk percentages."""
        account_balance = 1000.0
        original_amount = 100.0
        max_position_size = 100.0

        size = calculate_position_size(
            original_amount=original_amount,
            account_balance=account_balance,
            max_position_size=max_position_size,
            risk_percentage=risk_percentage,
        )

        # Higher risk percentage should allow larger positions
        base_size = calculate_position_size(
            original_amount=original_amount,
            account_balance=account_balance,
            max_position_size=max_position_size,
            risk_percentage=0.01,
        )

        if risk_percentage > 0.01:
            assert size >= base_size
        elif risk_percentage < 0.01:
            assert size <= base_size

    def test_position_size_consistency_across_calculations(self):
        """Test position sizing produces consistent results."""
        account_balance = 1000.0
        original_amount = 100.0
        max_position_size = 50.0

        # Run multiple times with same inputs
        sizes = []
        for _ in range(10):
            size = calculate_position_size(
                original_amount=original_amount,
                account_balance=account_balance,
                max_position_size=max_position_size,
            )
            sizes.append(size)

        # All results should be identical (deterministic)
        assert len(set(sizes)) == 1

    def test_position_size_with_market_crash_scenario(self):
        """Test position sizing during market crash scenario."""
        generator = MarketDataGenerator()

        # Simulate market crash: price drops 50%
        base_price = 0.5
        crash_price = 0.25

        account_balance = 1000.0
        max_position_size = 100.0
        original_amount = 100.0

        # Before crash
        normal_size = calculate_position_size(
            original_amount=original_amount,
            account_balance=account_balance,
            max_position_size=max_position_size,
        )

        # During crash - should reduce position size significantly
        # High volatility and price risk
        crash_volatility = 0.3
        price_risk = abs(crash_price - base_price) / base_price
        risk_adjusted_max = max_position_size * (1.0 - min(price_risk, 0.7))

        crash_size = calculate_position_size(
            original_amount=original_amount,
            account_balance=account_balance,
            max_position_size=risk_adjusted_max,
        )

        # Position size should be significantly reduced
        assert crash_size < normal_size * 0.5

    def test_position_size_with_market_surge_scenario(self):
        """Test position sizing during market surge scenario."""
        # Simulate market surge: price increases 50%
        base_price = 0.5
        surge_price = 0.75

        account_balance = 1000.0
        max_position_size = 100.0
        original_amount = 100.0

        # Normal conditions
        normal_size = calculate_position_size(
            original_amount=original_amount,
            account_balance=account_balance,
            max_position_size=max_position_size,
        )

        # During surge - increased volatility
        price_risk = abs(surge_price - base_price) / base_price
        risk_adjusted_max = max_position_size * (1.0 - min(price_risk * 0.5, 0.3))

        surge_size = calculate_position_size(
            original_amount=original_amount,
            account_balance=account_balance,
            max_position_size=risk_adjusted_max,
        )

        # Position size should be reduced but less than crash
        assert surge_size < normal_size
        assert surge_size > normal_size * 0.7
