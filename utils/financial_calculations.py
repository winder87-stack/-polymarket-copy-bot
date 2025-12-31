"""Financial calculations utility for Polymarket copy bot.

This module provides precision financial calculations using Decimal arithmetic
for all monetary operations. Never use float for money calculations.

Key Principles:
- Always use Decimal for money/price calculations
- Use high precision (28 digits) for intermediate calculations
- Round only at final results
- Handle division by zero gracefully
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from typing import Tuple

# Configure Decimal for financial calculations
getcontext().prec = 28  # High precision for financial calculations
getcontext().rounding = ROUND_HALF_UP  # Banker's rounding for accuracy


class FinancialCalculator:
    """
    High-precision financial calculations using Decimal arithmetic.

    All monetary calculations should use this class to ensure:
    - No floating-point rounding errors
    - Consistent precision across operations
    - Safe handling of edge cases (division by zero, etc.)
    """

    @staticmethod
    def to_decimal(value) -> Decimal:
        """
        Safely convert value to Decimal.

        Args:
            value: Value to convert (int, float, str, or Decimal)

        Returns:
            Decimal representation of the value

        Raises:
            ValueError: If value cannot be converted to Decimal
        """
        try:
            return Decimal(str(value))
        except (ValueError, TypeError, InvalidOperation) as e:
            raise ValueError(f"Cannot convert {value} to Decimal: {e}")

    @staticmethod
    def calculate_annualized_return(
        edge: Decimal, days: int, min_days: int = 1
    ) -> Decimal:
        """
        Calculate annualized return based on edge and time to resolution.

        Formula: ((1 + edge)^(365/days) - 1) * 100

        Args:
            edge: Edge percentage as Decimal (e.g., Decimal("0.05") for 5%)
            days: Days until resolution
            min_days: Minimum days to prevent division issues (default: 1)

        Returns:
            Annualized return as percentage (Decimal)

        Example:
            >>> calc = FinancialCalculator()
            >>> calc.calculate_annualized_return(Decimal("0.05"), 30)
            Decimal('84.7...')
        """
        try:
            edge_dec = FinancialCalculator.to_decimal(edge)
            safe_days = max(days, min_days)

            # Calculate exponent (365/days)
            exponent = Decimal(365) / Decimal(safe_days)

            # Calculate base (1 + edge)
            base = Decimal("1") + edge_dec

            # Calculate annualized return: base^exponent - 1
            annualized = base**exponent - Decimal("1")

            # Convert to percentage
            return annualized * Decimal("100")

        except (InvalidOperation, ValueError, ZeroDivisionError) as e:
            raise ValueError(f"Error calculating annualized return: {e}")

    @staticmethod
    def calculate_edge(current_probability: Decimal) -> Decimal:
        """
        Calculate edge based on current probability.

        Edge = (1.00 - current_probability) * 100

        This represents the potential return if the event occurs.

        Args:
            current_probability: Current probability as Decimal (0.0 to 1.0)

        Returns:
            Edge as percentage (Decimal)

        Example:
            >>> calc = FinancialCalculator()
            >>> calc.calculate_edge(Decimal("0.96"))
            Decimal('4.0')
        """
        try:
            prob_dec = FinancialCalculator.to_decimal(current_probability)

            # Validate probability range
            if not Decimal("0") <= prob_dec <= Decimal("1"):
                raise ValueError(f"Probability must be between 0 and 1, got {prob_dec}")

            # Edge = (1.00 - probability) * 100
            edge = (Decimal("1.00") - prob_dec) * Decimal("100")
            return edge

        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Error calculating edge: {e}")

    @staticmethod
    def calculate_position_size(
        account_balance: Decimal,
        risk_percentage: Decimal,
        max_position_size: Decimal,
        edge: Decimal,
        confidence_factor: Decimal = Decimal("1.0"),
    ) -> Decimal:
        """
        Calculate optimal position size using risk-based sizing.

        Formula: min(account_balance * risk_percentage * confidence_factor, max_position_size)

        Adjusts position size based on edge (higher edge = larger position).

        Args:
            account_balance: Total account balance
            risk_percentage: Risk percentage per trade (e.g., 0.03 for 3%)
            max_position_size: Maximum position size allowed
            edge: Edge percentage (used for confidence scaling)
            confidence_factor: Multiplier based on edge (default: 1.0)

        Returns:
            Calculated position size (Decimal)
        """
        try:
            balance_dec = FinancialCalculator.to_decimal(account_balance)
            risk_dec = FinancialCalculator.to_decimal(risk_percentage)
            max_size_dec = FinancialCalculator.to_decimal(max_position_size)
            edge_dec = FinancialCalculator.to_decimal(edge)

            # Scale confidence based on edge (higher edge = more confidence)
            # Edge > 5% is high confidence, scale up to 2x
            if edge_dec > Decimal("5.0"):
                confidence_factor = min(
                    confidence_factor * Decimal("1.5"), Decimal("2.0")
                )
            elif edge_dec > Decimal("3.0"):
                confidence_factor = min(
                    confidence_factor * Decimal("1.2"), Decimal("1.5")
                )

            # Risk-based position size
            risk_based_size = balance_dec * risk_dec * confidence_factor

            # Cap at max position size
            final_size = min(risk_based_size, max_size_dec)

            # Round to 4 decimal places
            return final_size.quantize(Decimal("0.0001"))

        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Error calculating position size: {e}")

    @staticmethod
    def calculate_expected_value(
        probability: Decimal, payoff: Decimal, cost: Decimal
    ) -> Decimal:
        """
        Calculate expected value of a trade.

        Formula: (probability * payoff) - ((1 - probability) * cost)

        Args:
            probability: Probability of winning (0.0 to 1.0)
            payoff: Potential profit amount
            cost: Cost (position size)

        Returns:
            Expected value (Decimal)
        """
        try:
            prob_dec = FinancialCalculator.to_decimal(probability)
            payoff_dec = FinancialCalculator.to_decimal(payoff)
            cost_dec = FinancialCalculator.to_decimal(cost)

            # Expected value = (P * payoff) - ((1-P) * cost)
            win_ev = prob_dec * payoff_dec
            lose_ev = (Decimal("1") - prob_dec) * cost_dec
            expected_value = win_ev - lose_ev

            return expected_value

        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Error calculating expected value: {e}")

    @staticmethod
    def calculate_profit_loss(
        entry_price: Decimal,
        exit_price: Decimal,
        position_size: Decimal,
        is_long: bool = True,
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate profit/loss for a position.

        Args:
            entry_price: Price at position entry
            exit_price: Price at position exit
            position_size: Size of position
            is_long: True for long positions, False for short

        Returns:
            Tuple of (pnl_amount, pnl_percentage)
        """
        try:
            entry_dec = FinancialCalculator.to_decimal(entry_price)
            exit_dec = FinancialCalculator.to_decimal(exit_price)
            size_dec = FinancialCalculator.to_decimal(position_size)

            if is_long:
                # Long: profit when price increases
                price_diff = exit_dec - entry_dec
            else:
                # Short: profit when price decreases
                price_diff = entry_dec - exit_dec

            # Calculate PnL in currency units
            pnl = price_diff * size_dec

            # Calculate PnL percentage
            if entry_dec != Decimal("0"):
                pnl_pct = (price_diff / entry_dec) * Decimal("100")
            else:
                pnl_pct = Decimal("0")

            return (pnl, pnl_pct)

        except (InvalidOperation, ValueError, ZeroDivisionError) as e:
            raise ValueError(f"Error calculating profit/loss: {e}")

    @staticmethod
    def calculate_kelly_criterion(
        win_rate: Decimal, avg_win: Decimal, avg_loss: Decimal
    ) -> Decimal:
        """
        Calculate Kelly Criterion for optimal bet sizing.

        Formula: f = (bp - q) / b
        Where: b = avg_win / avg_loss, p = win_rate, q = 1 - p

        Args:
            win_rate: Probability of winning (0.0 to 1.0)
            avg_win: Average profit amount
            avg_loss: Average loss amount (positive value)

        Returns:
            Kelly fraction (Decimal), capped at 0.25 (25%)
        """
        try:
            win_rate_dec = FinancialCalculator.to_decimal(win_rate)
            avg_win_dec = FinancialCalculator.to_decimal(avg_win)
            avg_loss_dec = FinancialCalculator.to_decimal(avg_loss)

            if avg_loss_dec == Decimal("0"):
                return Decimal("0")

            # Calculate b (win/loss ratio)
            b = avg_win_dec / avg_loss_dec

            # Calculate q (loss rate)
            q = Decimal("1") - win_rate_dec

            # Kelly fraction
            kelly = (b * win_rate_dec - q) / b

            # Cap at 25% (quarter Kelly for safety)
            kelly = min(max(kelly, Decimal("0")), Decimal("0.25"))

            return kelly

        except (InvalidOperation, ValueError, ZeroDivisionError) as e:
            raise ValueError(f"Error calculating Kelly Criterion: {e}")

    @staticmethod
    def calculate_sharpe_ratio(
        returns: list[Decimal], risk_free_rate: Decimal = Decimal("0.02")
    ) -> Decimal:
        """
        Calculate Sharpe Ratio for risk-adjusted returns.

        Formula: (mean_return - risk_free_rate) / std_dev_return

        Args:
            returns: List of return percentages (as Decimals)
            risk_free_rate: Risk-free rate (default: 2%)

        Returns:
            Sharpe ratio (Decimal), or Decimal("0") if insufficient data
        """
        try:
            if not returns or len(returns) < 2:
                return Decimal("0")

            returns_dec = [FinancialCalculator.to_decimal(r) for r in returns]

            # Calculate mean return
            mean_return = sum(returns_dec) / Decimal(len(returns_dec))

            # Calculate standard deviation
            variance = sum((r - mean_return) ** 2 for r in returns_dec) / Decimal(
                len(returns_dec)
            )
            std_dev = variance.sqrt()

            if std_dev == Decimal("0"):
                return Decimal("0")

            # Sharpe ratio
            sharpe = (mean_return - risk_free_rate) / std_dev

            return sharpe

        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Error calculating Sharpe ratio: {e}")

    @staticmethod
    def format_usdc(amount: Decimal) -> str:
        """
        Format USDC amount for display.

        Args:
            amount: USDC amount as Decimal

        Returns:
            Formatted string (e.g., "$1,234.56")
        """
        try:
            amount_dec = FinancialCalculator.to_decimal(amount)
            return f"${amount_dec:,.2f}"
        except (InvalidOperation, ValueError):
            return "$0.00"

    @staticmethod
    def format_percentage(percentage: Decimal, decimals: int = 2) -> str:
        """
        Format percentage for display.

        Args:
            percentage: Percentage as Decimal
            decimals: Number of decimal places (default: 2)

        Returns:
            Formatted string (e.g., "12.34%")
        """
        try:
            pct_dec = FinancialCalculator.to_decimal(percentage)
            return f"{pct_dec:.{decimals}f}%"
        except (InvalidOperation, ValueError):
            return "0.00%"
