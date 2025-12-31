"""Test data generators for realistic market scenarios.

This module provides generators for creating test data that simulates
real-world market conditions including volatility, slippage, and edge cases.
"""

import random
from typing import Any, Dict, List, Optional

import pytest


class MarketDataGenerator:
    """Generator for realistic market test data."""

    @staticmethod
    def generate_volatile_price_series(
        base_price: float = 0.5,
        volatility: float = 0.1,
        num_points: int = 100,
        trend: Optional[float] = None,
    ) -> List[float]:
        """
        Generate a series of prices with realistic volatility.

        Args:
            base_price: Starting price (0.0-1.0)
            volatility: Volatility factor (0.0-1.0)
            num_points: Number of price points to generate
            trend: Optional trend factor (-1.0 to 1.0)

        Returns:
            List of price values
        """
        prices = [base_price]
        current_price = base_price

        for _ in range(num_points - 1):
            # Random walk with volatility
            change = random.gauss(0, volatility * base_price)
            current_price += change

            # Apply trend if specified
            if trend:
                current_price += trend * base_price / num_points

            # Clamp to valid range
            current_price = max(0.01, min(0.99, current_price))
            prices.append(current_price)

        return prices

    @staticmethod
    def generate_slippage_scenario(
        intended_price: float,
        slippage_pct: float = 0.02,
        market_volatility: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Generate slippage scenario with realistic market conditions.

        Args:
            intended_price: Intended execution price
            slippage_pct: Expected slippage percentage
            market_volatility: Market volatility factor

        Returns:
            Dictionary with slippage scenario data
        """
        # Calculate actual execution price with slippage
        slippage_amount = intended_price * slippage_pct
        actual_price = intended_price + random.uniform(
            -slippage_amount, slippage_amount
        )

        # Add market volatility
        volatility_impact = random.gauss(0, market_volatility * intended_price)
        actual_price += volatility_impact

        # Clamp to valid range
        actual_price = max(0.01, min(0.99, actual_price))

        # Calculate slippage
        actual_slippage = abs(actual_price - intended_price) / intended_price

        return {
            "intended_price": intended_price,
            "actual_price": actual_price,
            "slippage_pct": actual_slippage,
            "slippage_amount": abs(actual_price - intended_price),
            "market_volatility": market_volatility,
        }

    @staticmethod
    def generate_trade_data(
        base_amount: float = 100.0,
        price_range: tuple = (0.1, 0.9),
        include_edge_cases: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate realistic trade data.

        Args:
            base_amount: Base trade amount
            price_range: (min_price, max_price) tuple
            include_edge_cases: Whether to include edge case values

        Returns:
            Dictionary with trade data
        """
        if include_edge_cases and random.random() < 0.1:  # 10% chance of edge case
            # Edge cases
            edge_cases = [
                {"amount": 0.01, "price": 0.01},  # Minimum values
                {"amount": 10000.0, "price": 0.99},  # Maximum values
                {"amount": base_amount, "price": 0.5},  # Mid-range
            ]
            edge_case = random.choice(edge_cases)
            amount = edge_case["amount"]
            price = edge_case["price"]
        else:
            # Normal distribution
            amount = random.uniform(base_amount * 0.1, base_amount * 2.0)
            price = random.uniform(price_range[0], price_range[1])

        return {
            "tx_hash": f"0x{random.getrandbits(256).to_bytes(32, 'big').hex()}",
            "timestamp": random.randint(1000000000, 2000000000),
            "wallet_address": f"0x{random.getrandbits(160).to_bytes(20, 'big').hex()}",
            "condition_id": f"0x{random.getrandbits(256).to_bytes(32, 'big').hex()}",
            "side": random.choice(["BUY", "SELL"]),
            "amount": amount,
            "price": price,
            "confidence_score": random.uniform(0.5, 1.0),
        }

    @staticmethod
    def generate_market_conditions(
        volatility_level: str = "normal",
    ) -> Dict[str, Any]:
        """
        Generate market conditions for testing.

        Args:
            volatility_level: 'low', 'normal', 'high', 'extreme'

        Returns:
            Dictionary with market conditions
        """
        volatility_map = {
            "low": (0.01, 0.02),
            "normal": (0.03, 0.05),
            "high": (0.08, 0.15),
            "extreme": (0.20, 0.50),
        }

        min_vol, max_vol = volatility_map.get(
            volatility_level, volatility_map["normal"]
        )
        volatility = random.uniform(min_vol, max_vol)

        return {
            "volatility_index": volatility,
            "liquidity_score": random.uniform(0.5, 1.0),
            "gas_price_multiplier": random.uniform(1.0, 2.0),
            "market_depth": random.uniform(1000.0, 10000.0),
            "spread_pct": random.uniform(0.001, 0.01),
        }

    @staticmethod
    def generate_account_balance_scenarios() -> List[Dict[str, Any]]:
        """
        Generate various account balance scenarios for testing.

        Returns:
            List of balance scenario dictionaries
        """
        return [
            {"balance": 10.0, "description": "Minimum balance"},
            {"balance": 100.0, "description": "Low balance"},
            {"balance": 1000.0, "description": "Normal balance"},
            {"balance": 10000.0, "description": "High balance"},
            {"balance": 100000.0, "description": "Very high balance"},
            {"balance": 0.01, "description": "Below minimum"},
            {"balance": 0.0, "description": "Zero balance"},
        ]

    @staticmethod
    def generate_position_size_inputs() -> List[Dict[str, Any]]:
        """
        Generate position size calculation inputs for parameterized tests.

        Returns:
            List of input dictionaries
        """
        scenarios = []

        # Normal scenarios
        for balance in [100.0, 1000.0, 10000.0]:
            for original_amount in [10.0, 100.0, 1000.0]:
                for max_position in [50.0, 500.0, 5000.0]:
                    scenarios.append(
                        {
                            "original_amount": original_amount,
                            "account_balance": balance,
                            "max_position_size": max_position,
                            "risk_percentage": 0.01,
                            "expected_range": (
                                min(1.0, max_position),
                                min(
                                    balance * 0.01, original_amount * 0.1, max_position
                                ),
                            ),
                        }
                    )

        # Edge cases
        edge_cases = [
            {
                "original_amount": 0.01,
                "account_balance": 1.0,
                "max_position_size": 50.0,
                "risk_percentage": 0.01,
                "expected_range": (0.01, 1.0),
            },
            {
                "original_amount": 100000.0,
                "account_balance": 1000.0,
                "max_position_size": 50.0,
                "risk_percentage": 0.01,
                "expected_range": (1.0, 50.0),
            },
            {
                "original_amount": 100.0,
                "account_balance": 0.0,
                "max_position_size": 50.0,
                "risk_percentage": 0.01,
                "expected_range": (0.0, 0.0),
            },
        ]

        scenarios.extend(edge_cases)
        return scenarios


class CircuitBreakerScenarioGenerator:
    """Generator for circuit breaker test scenarios."""

    @staticmethod
    def generate_state_transition_scenarios() -> List[Dict[str, Any]]:
        """
        Generate state transition scenarios for circuit breaker testing.

        Returns:
            List of state transition scenario dictionaries
        """
        scenarios = []

        # Daily loss activation
        scenarios.append(
            {
                "name": "daily_loss_exceeded",
                "initial_state": {"daily_loss": 90.0, "max_daily_loss": 100.0},
                "action": {"type": "record_loss", "amount": 15.0},
                "expected_active": True,
                "expected_reason_contains": "Daily loss limit",
            }
        )

        # Consecutive losses activation
        scenarios.append(
            {
                "name": "consecutive_losses",
                "initial_state": {"consecutive_losses": 4, "daily_loss": 10.0},
                "action": {"type": "record_loss", "amount": 5.0},
                "expected_active": True,
                "expected_reason_contains": "consecutive losses",
            }
        )

        # Failure rate activation
        scenarios.append(
            {
                "name": "high_failure_rate",
                "initial_state": {
                    "total_trades": 20,
                    "failed_trades": 10,
                    "daily_loss": 10.0,
                },
                "action": {"type": "record_trade_result", "success": False},
                "expected_active": True,
                "expected_reason_contains": "High failure rate",
            }
        )

        # Auto-reset after cooldown
        scenarios.append(
            {
                "name": "auto_reset_after_cooldown",
                "initial_state": {
                    "active": True,
                    "activation_time": 0.0,  # Old activation
                    "daily_loss": 0.0,
                },
                "action": {"type": "periodic_check", "current_time": 3700.0},
                "expected_active": False,
            }
        )

        # Profit resets consecutive losses
        scenarios.append(
            {
                "name": "profit_resets_consecutive_losses",
                "initial_state": {"consecutive_losses": 3, "daily_loss": 20.0},
                "action": {"type": "record_profit", "amount": 10.0},
                "expected_consecutive_losses": 0,
            }
        )

        return scenarios


class ValidationTestDataGenerator:
    """Generator for validation test data."""

    @staticmethod
    def generate_wallet_addresses() -> List[Dict[str, Any]]:
        """Generate wallet address test cases."""
        return [
            {
                "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                "valid": True,
                "description": "Valid checksum address",
            },
            {
                "address": "0x742d35cc6634c0532925a3b844bc454e4438f44e",
                "valid": True,
                "description": "Valid lowercase address",
            },
            {
                "address": "0x123",
                "valid": False,
                "description": "Too short",
            },
            {
                "address": "0x" + "0" * 40,
                "valid": True,
                "description": "Zero address",
            },
            {
                "address": "",
                "valid": False,
                "description": "Empty address",
            },
            {
                "address": "not_an_address",
                "valid": False,
                "description": "Invalid format",
            },
        ]

    @staticmethod
    def generate_private_keys() -> List[Dict[str, Any]]:
        """Generate private key test cases."""
        return [
            {
                "key": "0x" + "0" * 64,
                "valid": True,
                "description": "Valid private key",
            },
            {
                "key": "0x" + "a" * 64,
                "valid": True,
                "description": "Valid hex private key",
            },
            {
                "key": "0x123",
                "valid": False,
                "description": "Too short",
            },
            {
                "key": "",
                "valid": False,
                "description": "Empty key",
            },
            {
                "key": "not_a_key",
                "valid": False,
                "description": "Invalid format",
            },
            {
                "key": "0x" + "g" * 64,
                "valid": False,
                "description": "Invalid hex characters",
            },
        ]

    @staticmethod
    def generate_malicious_inputs() -> List[Dict[str, Any]]:
        """Generate potentially malicious input test cases."""
        return [
            {
                "input": '{"script": "alert(1)"}',
                "should_sanitize": True,
                "description": "Script tag in JSON",
            },
            {
                "input": '{"eval": "dangerous_code()"}',
                "should_sanitize": True,
                "description": "Eval in JSON",
            },
            {
                "input": '{"os": "rm -rf /"}',
                "should_sanitize": True,
                "description": "OS command in JSON",
            },
            {
                "input": '{"normal": "data"}',
                "should_sanitize": False,
                "description": "Normal JSON",
            },
            {
                "input": "<script>alert('xss')</script>",
                "should_sanitize": True,
                "description": "XSS attempt",
            },
        ]


# Pytest fixtures for easy use in tests
@pytest.fixture
def market_data_generator() -> MarketDataGenerator:
    """Fixture for market data generator."""
    return MarketDataGenerator()


@pytest.fixture
def circuit_breaker_generator() -> CircuitBreakerScenarioGenerator:
    """Fixture for circuit breaker scenario generator."""
    return CircuitBreakerScenarioGenerator()


@pytest.fixture
def validation_generator() -> ValidationTestDataGenerator:
    """Fixture for validation test data generator."""
    return ValidationTestDataGenerator()
