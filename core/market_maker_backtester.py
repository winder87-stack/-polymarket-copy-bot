"""
Market Maker Risk Management Backtesting Framework
==================================================

Comprehensive backtesting system for evaluating risk management strategies
specific to market maker copying. Tests position sizing, trade filtering,
loss limitation, and profit capture algorithms across historical data.

Features:
- Historical trade data simulation
- Multiple risk management strategy comparison
- Performance metrics calculation
- Risk-adjusted return analysis
- Walk-forward optimization
- Monte Carlo simulation for robustness testing
"""

import json
import logging
import random
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats

from core.market_maker_risk_manager import MarketMakerRiskManager

logger = logging.getLogger(__name__)


class MarketMakerBacktester:
    """
    Comprehensive backtesting framework for market maker risk management strategies.

    Tests and validates risk management approaches using historical data and
    Monte Carlo simulations to ensure robustness across different market conditions.
    """

    def __init__(self, risk_manager: MarketMakerRiskManager):
        self.risk_manager = risk_manager
        self.detector = risk_manager.detector

        # Backtesting configuration
        self.backtest_config = {
            "initial_balance": 10000.0,  # Starting balance in USD
            "max_position_pct": 0.1,  # Max 10% of balance per position
            "commission_per_trade": 0.001,  # 0.1% commission
            "slippage_model": "fixed",  # fixed, percentage, or realistic
            "slippage_pct": 0.0005,  # 0.05% slippage
            "time_decay_factor": 0.999,  # Daily time decay for older data
            "monte_carlo_runs": 100,  # Number of Monte Carlo simulations
            "walk_forward_periods": 5,  # Number of walk-forward periods
        }

        # Results storage
        self.backtest_results: Dict[str, Any] = {}
        self.performance_history: List[Dict[str, Any]] = []

        # Test data generation
        self.test_data_generators = {
            "historical": self._generate_historical_test_data,
            "synthetic": self._generate_synthetic_test_data,
            "monte_carlo": self._generate_monte_carlo_scenarios,
        }

        logger.info("🧪 Market maker backtester initialized")

    async def run_comprehensive_backtest(
        self,
        test_data_type: str = "synthetic",
        test_period_days: int = 30,
        strategies_to_test: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run comprehensive backtest across multiple strategies and scenarios.

        Args:
            test_data_type: Type of test data ("historical", "synthetic", "monte_carlo")
            test_period_days: Length of test period in days
            strategies_to_test: List of strategy names to test

        Returns:
            Comprehensive backtest results
        """

        if strategies_to_test is None:
            strategies_to_test = [
                "baseline",
                "conservative_mm",
                "aggressive_mm",
                "adaptive",
            ]

        logger.info(
            f"🧪 Starting comprehensive backtest: {test_data_type} data, {test_period_days} days, {len(strategies_to_test)} strategies"
        )

        # Generate test data
        test_data = await self._generate_test_data(test_data_type, test_period_days)

        # Run backtests for each strategy
        strategy_results = {}
        for strategy_name in strategies_to_test:
            logger.info(f"Testing strategy: {strategy_name}")
            result = await self._run_strategy_backtest(strategy_name, test_data)
            strategy_results[strategy_name] = result

        # Analyze and compare results
        comparison_results = self._compare_strategy_performance(strategy_results)

        # Generate robustness tests
        robustness_results = await self._run_robustness_tests(
            strategy_results, test_data
        )

        # Compile final results
        comprehensive_results = {
            "backtest_metadata": {
                "test_data_type": test_data_type,
                "test_period_days": test_period_days,
                "strategies_tested": strategies_to_test,
                "monte_carlo_runs": self.backtest_config["monte_carlo_runs"],
                "timestamp": datetime.now().isoformat(),
            },
            "strategy_results": strategy_results,
            "strategy_comparison": comparison_results,
            "robustness_tests": robustness_results,
            "recommendations": self._generate_backtest_recommendations(
                comparison_results
            ),
        }

        self.backtest_results = comprehensive_results

        # Save results
        self._save_backtest_results(comprehensive_results)

        logger.info("🧪 Comprehensive backtest completed")
        return comprehensive_results

    async def _generate_test_data(
        self, data_type: str, period_days: int
    ) -> List[Dict[str, Any]]:
        """Generate test data based on specified type."""

        generator = self.test_data_generators.get(
            data_type, self._generate_synthetic_test_data
        )
        return await generator(period_days)

    async def _generate_synthetic_test_data(
        self, period_days: int
    ) -> List[Dict[str, Any]]:
        """
        Generate synthetic test data that mimics real market maker behavior.

        Creates realistic trade sequences with various market conditions.
        """

        test_data = []
        base_timestamp = datetime.now() - timedelta(days=period_days)

        # Define wallet types and their behavior patterns
        wallet_types = {
            "market_maker": {
                "frequency": 8,  # trades per hour
                "win_rate": 0.55,
                "avg_profit_pct": 0.8,
                "avg_loss_pct": -0.4,
                "holding_time_hours": 1.5,
                "trade_count": period_days * 8 * 0.7,  # 70% activity
            },
            "arbitrage_trader": {
                "frequency": 6,
                "win_rate": 0.65,
                "avg_profit_pct": 1.2,
                "avg_loss_pct": -0.6,
                "holding_time_hours": 2.0,
                "trade_count": period_days * 6 * 0.6,
            },
            "high_frequency_trader": {
                "frequency": 12,
                "win_rate": 0.52,
                "avg_profit_pct": 0.6,
                "avg_loss_pct": -0.3,
                "holding_time_hours": 0.8,
                "trade_count": period_days * 12 * 0.8,
            },
            "directional_trader": {
                "frequency": 2,
                "win_rate": 0.45,
                "avg_profit_pct": 8.0,
                "avg_loss_pct": -12.0,
                "holding_time_hours": 24.0,
                "trade_count": period_days * 2 * 0.5,
            },
        }

        # Generate trades for each wallet type
        wallet_id = 0
        for wallet_type, params in wallet_types.items():
            trade_count = int(params["trade_count"])

            for i in range(trade_count):
                # Generate timestamp with realistic distribution
                hours_offset = (i / params["frequency"]) + random.uniform(0, 24)
                timestamp = base_timestamp + timedelta(hours=hours_offset)

                # Determine if trade is profitable
                is_win = random.random() < params["win_rate"]
                if is_win:
                    pnl_pct = abs(
                        random.gauss(
                            params["avg_profit_pct"], params["avg_profit_pct"] * 0.5
                        )
                    )
                else:
                    pnl_pct = -abs(
                        random.gauss(
                            params["avg_loss_pct"], abs(params["avg_loss_pct"]) * 0.5
                        )
                    )

                # Generate trade data
                trade = {
                    "wallet_address": f"0x{wallet_id:040x}",
                    "wallet_type": wallet_type,
                    "timestamp": timestamp.isoformat(),
                    "amount": random.uniform(10, 1000),  # Trade size
                    "side": "BUY" if random.random() < 0.5 else "SELL",
                    "price": random.uniform(0.1, 10.0),
                    "market_id": f"market_{random.randint(1, 20)}",
                    "condition_id": f"condition_{random.randint(1, 50)}",
                    "gas_price": random.uniform(50, 200),  # Gwei
                    "market_cap": random.uniform(50000, 500000),
                    "actual_pnl_pct": pnl_pct,
                    "holding_time_hours": random.gauss(
                        params["holding_time_hours"], params["holding_time_hours"] * 0.5
                    ),
                    "confidence_score": random.uniform(0.5, 0.95),
                    "market_liquidity_score": random.uniform(0.3, 1.0),
                    "volatility_index": random.uniform(0.8, 1.5),
                }

                test_data.append(trade)
            wallet_id += 1

        # Sort by timestamp
        test_data.sort(key=lambda x: x["timestamp"])

        logger.info(
            f"🎲 Generated {len(test_data)} synthetic trades across {len(wallet_types)} wallet types"
        )
        return test_data

    async def _generate_historical_test_data(
        self, period_days: int
    ) -> List[Dict[str, Any]]:
        """
        Generate test data from historical market maker behavior.

        Uses actual historical data if available, otherwise falls back to synthetic.
        """

        # This would integrate with actual historical data sources
        # For now, generate enhanced synthetic data
        return await self._generate_synthetic_test_data(period_days)

    async def _generate_monte_carlo_scenarios(
        self, period_days: int
    ) -> List[Dict[str, Any]]:
        """
        Generate Monte Carlo scenarios by varying key parameters.
        """

        base_scenarios = await self._generate_synthetic_test_data(period_days // 2)

        # Create variations with different parameters
        monte_carlo_data = []
        for scenario in base_scenarios:
            # Create 5 variations per base scenario
            for variation in range(5):
                varied_scenario = scenario.copy()

                # Vary key parameters
                variation_factors = {
                    "actual_pnl_pct": random.uniform(0.5, 2.0),  # 50%-200% of base
                    "gas_price": random.uniform(0.5, 2.0),
                    "market_liquidity_score": random.uniform(0.7, 1.3),
                    "volatility_index": random.uniform(0.8, 1.5),
                    "confidence_score": random.uniform(0.8, 1.2),
                }

                for param, factor in variation_factors.items():
                    if param in varied_scenario:
                        if param.endswith("_pct"):
                            varied_scenario[param] *= factor
                        else:
                            varied_scenario[param] *= random.uniform(0.8, 1.2)

                monte_carlo_data.append(varied_scenario)

        logger.info(f"🎲 Generated {len(monte_carlo_data)} Monte Carlo scenarios")
        return monte_carlo_data

    async def _run_strategy_backtest(
        self, strategy_name: str, test_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Run backtest for a specific strategy.

        Args:
            strategy_name: Name of the strategy to test
            test_data: List of trade data for testing

        Returns:
            Strategy performance results
        """

        # Initialize strategy-specific risk manager
        strategy_risk_manager = self._create_strategy_risk_manager(strategy_name)

        # Initialize portfolio state
        portfolio = {
            "balance": self.backtest_config["initial_balance"],
            "positions": {},
            "trade_history": [],
            "daily_stats": {},
            "circuit_breakers": [],
        }

        # Process each trade in chronological order
        for trade_data in test_data:
            await self._process_trade_for_backtest(
                strategy_risk_manager, portfolio, trade_data, strategy_name
            )

        # Calculate final performance metrics
        performance_metrics = self._calculate_performance_metrics(portfolio)

        # Calculate risk metrics
        risk_metrics = self._calculate_risk_metrics(portfolio)

        # Calculate strategy-specific metrics
        strategy_metrics = self._calculate_strategy_metrics(portfolio, strategy_name)

        results = {
            "strategy_name": strategy_name,
            "performance_metrics": performance_metrics,
            "risk_metrics": risk_metrics,
            "strategy_metrics": strategy_metrics,
            "portfolio_final_state": {
                "balance": portfolio["balance"],
                "total_trades": len(portfolio["trade_history"]),
                "open_positions": len(portfolio["positions"]),
                "circuit_breaker_events": len(portfolio["circuit_breakers"]),
            },
        }

        return results

    def _create_strategy_risk_manager(
        self, strategy_name: str
    ) -> MarketMakerRiskManager:
        """Create a risk manager instance configured for the specific strategy."""

        # Create a deep copy to avoid modifying the original
        strategy_manager = deepcopy(self.risk_manager)

        # Apply strategy-specific configuration
        if strategy_name == "conservative_mm":
            # Very conservative settings for market makers
            strategy_manager.wallet_type_configs["market_maker"].update(
                {
                    "position_size_multiplier": 0.02,  # 2% of normal
                    "stop_loss_pct": 0.2,  # 0.2% stops
                    "take_profit_pct": 0.5,  # 0.5% targets
                    "min_trade_quality_score": 0.8,  # Higher quality threshold
                }
            )

        elif strategy_name == "aggressive_mm":
            # More aggressive settings
            strategy_manager.wallet_type_configs["market_maker"].update(
                {
                    "position_size_multiplier": 0.2,  # 20% of normal
                    "stop_loss_pct": 1.5,  # 1.5% stops
                    "take_profit_pct": 2.0,  # 2% targets
                    "min_trade_quality_score": 0.3,  # Lower quality threshold
                }
            )

        elif strategy_name == "adaptive":
            # Adaptive sizing based on market conditions
            strategy_manager.wallet_type_configs["market_maker"].update(
                {
                    "position_size_multiplier": 0.08,  # 8% base
                    "volatility_multiplier": 0.7,  # More conservative in volatility
                    "correlation_limit": 0.8,  # Stricter correlation limits
                }
            )

        # Strategy "baseline" uses default configuration

        return strategy_manager

    async def _process_trade_for_backtest(
        self,
        risk_manager: MarketMakerRiskManager,
        portfolio: Dict[str, Any],
        trade_data: Dict[str, Any],
        strategy_name: str,
    ):
        """Process a single trade through the backtesting framework."""

        try:
            # Evaluate trade risk
            risk_evaluation = await risk_manager.evaluate_trade_risk(
                trade_data["wallet_address"],
                trade_data,
                market_conditions={
                    "volatility": trade_data.get("volatility_index", 1.0),
                    "gas_price_multiplier": trade_data.get("gas_price", 100) / 100.0,
                    "liquidity_score": trade_data.get("market_liquidity_score", 1.0),
                },
            )

            # Check if trade should be executed
            if not risk_evaluation["should_execute"]:
                # Record rejected trade
                portfolio["trade_history"].append(
                    {
                        "timestamp": trade_data["timestamp"],
                        "action": "rejected",
                        "reason": risk_evaluation["rejection_reason"],
                        "strategy": strategy_name,
                        "wallet_type": trade_data["wallet_type"],
                    }
                )
                return

            # Calculate position size and entry
            position_size = risk_evaluation["position_size_usd"]

            # Apply commission and slippage
            commission = position_size * self.backtest_config["commission_per_trade"]
            slippage = position_size * self.backtest_config["slippage_pct"]
            total_cost = position_size + commission + slippage

            # Check if we have enough balance
            if total_cost > portfolio["balance"]:
                return  # Insufficient balance

            # Execute trade
            portfolio["balance"] -= total_cost

            # Simulate position outcome
            actual_pnl_pct = trade_data.get("actual_pnl_pct", 0)
            pnl_amount = position_size * (actual_pnl_pct / 100.0)

            # Apply risk management (simplified)
            stop_loss_triggered = False
            take_profit_triggered = False

            if (
                actual_pnl_pct
                <= -risk_evaluation["stop_loss_usd"] / position_size * 100
            ):
                stop_loss_triggered = True
                pnl_amount = -risk_evaluation["stop_loss_usd"]
            elif (
                actual_pnl_pct
                >= risk_evaluation["take_profit_usd"] / position_size * 100
            ):
                take_profit_triggered = True
                pnl_amount = risk_evaluation["take_profit_usd"]

            # Update portfolio
            portfolio["balance"] += position_size + pnl_amount  # Return capital + pnl

            # Record trade
            trade_record = {
                "timestamp": trade_data["timestamp"],
                "action": "executed",
                "wallet_address": trade_data["wallet_address"],
                "wallet_type": trade_data["wallet_type"],
                "position_size": position_size,
                "pnl_amount": pnl_amount,
                "pnl_pct": actual_pnl_pct,
                "commission": commission,
                "slippage": slippage,
                "stop_loss_triggered": stop_loss_triggered,
                "take_profit_triggered": take_profit_triggered,
                "strategy": strategy_name,
                "quality_score": risk_evaluation.get("quality_score", 0),
                "risk_score": risk_evaluation.get("risk_score", 0),
            }

            portfolio["trade_history"].append(trade_record)

        except Exception as e:
            logger.error(f"Error processing trade in backtest: {e}")

    def _calculate_performance_metrics(
        self, portfolio: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""

        trades = [t for t in portfolio["trade_history"] if t["action"] == "executed"]
        initial_balance = self.backtest_config["initial_balance"]
        final_balance = portfolio["balance"]

        if not trades:
            return {
                "total_return_pct": 0,
                "total_return_usd": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "max_drawdown_pct": 0,
                "sharpe_ratio": 0,
                "total_trades": 0,
            }

        # Basic metrics
        total_return_usd = final_balance - initial_balance
        total_return_pct = (total_return_usd / initial_balance) * 100

        winning_trades = [t for t in trades if t["pnl_amount"] > 0]
        losing_trades = [t for t in trades if t["pnl_amount"] < 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0

        total_wins = sum(t["pnl_amount"] for t in winning_trades)
        total_losses = abs(sum(t["pnl_amount"] for t in losing_trades))

        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        avg_win = total_wins / len(winning_trades) if winning_trades else 0
        avg_loss = total_losses / len(losing_trades) if losing_trades else 0

        # Calculate drawdown
        balance_history = [initial_balance]
        current_balance = initial_balance

        for trade in trades:
            current_balance += trade["pnl_amount"]
            balance_history.append(current_balance)

        peak = initial_balance
        max_drawdown = 0

        for balance in balance_history:
            if balance > peak:
                peak = balance
            drawdown = (peak - balance) / peak
            max_drawdown = max(max_drawdown, drawdown)

        # Calculate Sharpe ratio (simplified, assuming daily returns)
        daily_returns = []
        daily_pnl = {}

        for trade in trades:
            date = datetime.fromisoformat(trade["timestamp"]).date()
            if date not in daily_pnl:
                daily_pnl[date] = 0
            daily_pnl[date] += trade["pnl_amount"]

        for pnl in daily_pnl.values():
            daily_return = pnl / initial_balance
            daily_returns.append(daily_return)

        if daily_returns:
            avg_daily_return = np.mean(daily_returns)
            std_daily_return = np.std(daily_returns)
            sharpe_ratio = (
                avg_daily_return / std_daily_return * np.sqrt(365)
                if std_daily_return > 0
                else 0
            )
        else:
            sharpe_ratio = 0

        return {
            "total_return_pct": total_return_pct,
            "total_return_usd": total_return_usd,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_drawdown_pct": max_drawdown * 100,
            "sharpe_ratio": sharpe_ratio,
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
        }

    def _calculate_risk_metrics(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive risk metrics."""

        trades = [t for t in portfolio["trade_history"] if t["action"] == "executed"]

        if not trades:
            return {
                "value_at_risk_95": 0,
                "expected_shortfall_95": 0,
                "volatility": 0,
                "skewness": 0,
                "kurtosis": 0,
                "maximum_consecutive_losses": 0,
                "largest_loss": 0,
                "recovery_factor": 0,
            }

        pnl_values = [t["pnl_amount"] for t in trades]

        # VaR and Expected Shortfall
        confidence_level = 0.05
        var_95 = np.percentile(pnl_values, confidence_level * 100)
        expected_shortfall_95 = np.mean([x for x in pnl_values if x <= var_95])

        # Statistical measures
        volatility = np.std(pnl_values)
        skewness = stats.skew(pnl_values)
        kurtosis = stats.kurtosis(pnl_values)

        # Drawdown analysis
        balance_history = [self.backtest_config["initial_balance"]]
        current_balance = self.backtest_config["initial_balance"]

        for trade in trades:
            current_balance += trade["pnl_amount"]
            balance_history.append(current_balance)

        # Maximum consecutive losses
        consecutive_losses = 0
        max_consecutive_losses = 0

        for pnl in pnl_values:
            if pnl < 0:
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:
                consecutive_losses = 0

        largest_loss = min(pnl_values) if pnl_values else 0

        # Recovery factor (net profit / max drawdown)
        performance_metrics = self._calculate_performance_metrics(portfolio)
        max_drawdown = performance_metrics["max_drawdown_pct"] / 100
        net_profit = performance_metrics["total_return_usd"]
        recovery_factor = (
            net_profit / max_drawdown if max_drawdown > 0 else float("inf")
        )

        return {
            "value_at_risk_95": var_95,
            "expected_shortfall_95": expected_shortfall_95,
            "volatility": volatility,
            "skewness": skewness,
            "kurtosis": kurtosis,
            "maximum_consecutive_losses": max_consecutive_losses,
            "largest_loss": largest_loss,
            "recovery_factor": recovery_factor,
        }

    def _calculate_strategy_metrics(
        self, portfolio: Dict[str, Any], strategy_name: str
    ) -> Dict[str, Any]:
        """Calculate strategy-specific performance metrics."""

        trades = [t for t in portfolio["trade_history"] if t["action"] == "executed"]

        if not trades:
            return {}

        # Group by wallet type
        wallet_type_performance = {}
        for trade in trades:
            wallet_type = trade.get("wallet_type", "unknown")
            if wallet_type not in wallet_type_performance:
                wallet_type_performance[wallet_type] = []

            wallet_type_performance[wallet_type].append(trade["pnl_amount"])

        wallet_type_stats = {}
        for wallet_type, pnls in wallet_type_performance.items():
            wallet_type_stats[wallet_type] = {
                "trade_count": len(pnls),
                "total_pnl": sum(pnls),
                "avg_pnl": np.mean(pnls),
                "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
                "best_trade": max(pnls),
                "worst_trade": min(pnls),
            }

        # Risk management effectiveness
        rejected_trades = [
            t for t in portfolio["trade_history"] if t["action"] == "rejected"
        ]
        rejection_rate = (
            len(rejected_trades) / len(portfolio["trade_history"])
            if portfolio["trade_history"]
            else 0
        )

        # Circuit breaker analysis
        circuit_breaker_events = len(portfolio.get("circuit_breakers", []))

        return {
            "wallet_type_performance": wallet_type_stats,
            "rejection_rate": rejection_rate,
            "circuit_breaker_events": circuit_breaker_events,
            "avg_quality_score": np.mean([t.get("quality_score", 0) for t in trades]),
            "avg_risk_score": np.mean([t.get("risk_score", 0) for t in trades]),
            "stop_loss_triggers": sum(
                1 for t in trades if t.get("stop_loss_triggered", False)
            ),
            "take_profit_triggers": sum(
                1 for t in trades if t.get("take_profit_triggered", False)
            ),
        }

    def _compare_strategy_performance(
        self, strategy_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare performance across different strategies."""

        comparison = {
            "best_performing_strategy": None,
            "performance_rankings": [],
            "risk_adjusted_rankings": [],
            "statistical_significance": {},
            "key_differences": {},
        }

        if not strategy_results:
            return comparison

        # Rank strategies by total return
        performance_rankings = sorted(
            strategy_results.items(),
            key=lambda x: x[1]["performance_metrics"]["total_return_pct"],
            reverse=True,
        )

        comparison["performance_rankings"] = [
            {
                "strategy": name,
                "return_pct": result["performance_metrics"]["total_return_pct"],
            }
            for name, result in performance_rankings
        ]

        comparison["best_performing_strategy"] = performance_rankings[0][0]

        # Risk-adjusted rankings (Sharpe ratio)
        risk_adjusted_rankings = sorted(
            strategy_results.items(),
            key=lambda x: x[1]["performance_metrics"]["sharpe_ratio"],
            reverse=True,
        )

        comparison["risk_adjusted_rankings"] = [
            {
                "strategy": name,
                "sharpe_ratio": result["performance_metrics"]["sharpe_ratio"],
            }
            for name, result in risk_adjusted_rankings
        ]

        # Statistical significance testing (simplified)
        if len(strategy_results) >= 2:
            returns = [
                result["performance_metrics"]["total_return_pct"]
                for result in strategy_results.values()
            ]
            comparison["statistical_significance"] = {
                "best_vs_worst_return_diff": max(returns) - min(returns),
                "return_volatility": np.std(returns),
                "consistent_winners": sum(1 for r in returns if r > 0),
            }

        # Key differences analysis
        comparison["key_differences"] = self._analyze_strategy_differences(
            strategy_results
        )

        return comparison

    def _analyze_strategy_differences(
        self, strategy_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze key differences between strategies."""

        differences = {}

        if len(strategy_results) < 2:
            return differences

        # Compare win rates
        win_rates = {
            name: result["performance_metrics"]["win_rate"]
            for name, result in strategy_results.items()
        }

        differences["win_rate_range"] = max(win_rates.values()) - min(
            win_rates.values()
        )

        # Compare risk metrics
        volatilities = {
            name: result["risk_metrics"]["volatility"]
            for name, result in strategy_results.items()
        }

        differences["volatility_range"] = max(volatilities.values()) - min(
            volatilities.values()
        )

        # Compare trade counts
        trade_counts = {
            name: result["portfolio_final_state"]["total_trades"]
            for name, result in strategy_results.items()
        }

        differences["trade_count_range"] = max(trade_counts.values()) - min(
            trade_counts.values()
        )

        return differences

    async def _run_robustness_tests(
        self, strategy_results: Dict[str, Any], original_test_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Run robustness tests including Monte Carlo simulations."""

        robustness_results = {
            "monte_carlo_results": {},
            "walk_forward_results": {},
            "stress_test_results": {},
        }

        # Monte Carlo simulation
        logger.info(
            f"Running {self.backtest_config['monte_carlo_runs']} Monte Carlo simulations"
        )

        monte_carlo_results = {}
        for strategy_name in strategy_results.keys():
            mc_returns = []

            for run in range(self.backtest_config["monte_carlo_runs"]):
                # Shuffle trade order to simulate different market conditions
                shuffled_data = original_test_data.copy()
                random.shuffle(shuffled_data)

                # Run backtest with shuffled data
                mc_result = await self._run_strategy_backtest(
                    strategy_name, shuffled_data[: len(shuffled_data) // 2]
                )
                mc_returns.append(mc_result["performance_metrics"]["total_return_pct"])

            monte_carlo_results[strategy_name] = {
                "mean_return": np.mean(mc_returns),
                "std_return": np.std(mc_returns),
                "min_return": min(mc_returns),
                "max_return": max(mc_returns),
                "return_confidence_95": np.percentile(mc_returns, [2.5, 97.5]),
            }

        robustness_results["monte_carlo_results"] = monte_carlo_results

        # Walk-forward analysis
        walk_forward_results = await self._run_walk_forward_analysis(
            strategy_results, original_test_data
        )
        robustness_results["walk_forward_results"] = walk_forward_results

        # Stress tests
        stress_test_results = await self._run_stress_tests(
            strategy_results, original_test_data
        )
        robustness_results["stress_test_results"] = stress_test_results

        return robustness_results

    async def _run_walk_forward_analysis(
        self, strategy_results: Dict[str, Any], test_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Run walk-forward analysis to test strategy stability."""

        walk_forward_results = {}

        # Split data into periods
        periods = self.backtest_config["walk_forward_periods"]
        period_size = len(test_data) // periods

        for strategy_name in strategy_results.keys():
            period_returns = []

            for i in range(periods):
                start_idx = i * period_size
                end_idx = (i + 1) * period_size

                period_data = test_data[start_idx:end_idx]
                period_result = await self._run_strategy_backtest(
                    strategy_name, period_data
                )
                period_returns.append(
                    period_result["performance_metrics"]["total_return_pct"]
                )

            walk_forward_results[strategy_name] = {
                "period_returns": period_returns,
                "avg_period_return": np.mean(period_returns),
                "return_stability": 1
                / (1 + np.std(period_returns)),  # Higher = more stable
                "best_period": max(period_returns),
                "worst_period": min(period_returns),
            }

        return walk_forward_results

    async def _run_stress_tests(
        self, strategy_results: Dict[str, Any], test_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Run stress tests under extreme market conditions."""

        stress_scenarios = {
            "high_volatility": lambda trade: {
                **trade,
                "volatility_index": trade.get("volatility_index", 1.0) * 2.0,
            },
            "low_liquidity": lambda trade: {
                **trade,
                "market_liquidity_score": trade.get("market_liquidity_score", 1.0)
                * 0.3,
            },
            "high_gas": lambda trade: {
                **trade,
                "gas_price": trade.get("gas_price", 100) * 3.0,
            },
            "adverse_pnl": lambda trade: {
                **trade,
                "actual_pnl_pct": trade.get("actual_pnl_pct", 0) * 1.5,
            },  # Make losses worse
        }

        stress_results = {}

        for scenario_name, scenario_func in stress_scenarios.items():
            scenario_results = {}

            # Apply stress scenario to test data
            stressed_data = [scenario_func(trade.copy()) for trade in test_data]

            for strategy_name in strategy_results.keys():
                stress_result = await self._run_strategy_backtest(
                    strategy_name, stressed_data
                )
                scenario_results[strategy_name] = stress_result["performance_metrics"]

            stress_results[scenario_name] = scenario_results

        return stress_results

    def _generate_backtest_recommendations(
        self, comparison_results: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on backtest results."""

        recommendations = []

        if not comparison_results.get("performance_rankings"):
            return recommendations

        best_strategy = comparison_results["best_performing_strategy"]
        rankings = comparison_results["performance_rankings"]

        # Best strategy recommendation
        recommendations.append(
            f"🎯 **Recommended Strategy**: {best_strategy} (best performer in backtest)"
        )

        # Risk assessment
        if comparison_results.get("risk_adjusted_rankings"):
            risk_best = comparison_results["risk_adjusted_rankings"][0]["strategy"]
            if risk_best != best_strategy:
                recommendations.append(
                    f"⚖️ **Risk-Adjusted Alternative**: Consider {risk_best} for better risk-adjusted returns"
                )

        # Statistical significance
        if comparison_results.get("statistical_significance"):
            stats = comparison_results["statistical_significance"]
            if stats.get("consistent_winners", 0) >= len(rankings) * 0.7:
                recommendations.append(
                    "✅ **Robust Results**: Most strategies show positive returns"
                )
            else:
                recommendations.append(
                    "⚠️ **Variable Results**: Strategy performance varies significantly"
                )

        # Key differences insights
        differences = comparison_results.get("key_differences", {})
        if differences.get("win_rate_range", 0) > 0.2:
            recommendations.append(
                "📊 **Win Rate Variation**: Large differences in win rates suggest strategy-specific market fit"
            )

        return recommendations

    def _save_backtest_results(self, results: Dict[str, Any]):
        """Save backtest results to file."""

        try:
            results_dir = Path("monitoring/backtests")
            results_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = results_dir / f"backtest_results_{timestamp}.json"

            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, default=str)

            logger.info(f"💾 Backtest results saved to {results_file}")

        except Exception as e:
            logger.error(f"Error saving backtest results: {e}")

    async def run_parameter_optimization(
        self,
        strategy_name: str,
        parameter_ranges: Dict[str, List[float]],
        test_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Run parameter optimization for a specific strategy.

        Args:
            strategy_name: Strategy to optimize
            parameter_ranges: Dictionary of parameter names to lists of values to test
            test_data: Test data for optimization

        Returns:
            Optimization results with best parameters
        """

        logger.info(f"🔬 Optimizing parameters for strategy: {strategy_name}")

        # Generate all parameter combinations
        param_names = list(parameter_ranges.keys())
        param_values = list(parameter_ranges.values())

        from itertools import product

        combinations = list(product(*param_values))

        optimization_results = []

        for combo in combinations:
            params = dict(zip(param_names, combo))

            # Create strategy with these parameters
            self._create_optimized_strategy(strategy_name, params)

            # Run backtest
            result = await self._run_strategy_backtest(
                f"{strategy_name}_opt", test_data
            )

            # Store result with parameters
            result["parameters"] = params
            optimization_results.append(result)

        # Find best performing combination
        best_result = max(
            optimization_results, key=lambda x: x["performance_metrics"]["sharpe_ratio"]
        )

        # Analyze parameter sensitivity
        sensitivity_analysis = self._analyze_parameter_sensitivity(
            optimization_results, param_names
        )

        optimization_summary = {
            "strategy": strategy_name,
            "total_combinations_tested": len(combinations),
            "best_parameters": best_result["parameters"],
            "best_performance": best_result["performance_metrics"],
            "parameter_sensitivity": sensitivity_analysis,
            "optimization_timestamp": datetime.now().isoformat(),
        }

        return optimization_summary

    def _create_optimized_strategy(
        self, strategy_name: str, params: Dict[str, float]
    ) -> MarketMakerRiskManager:
        """Create a strategy instance with optimized parameters."""

        strategy_manager = self._create_strategy_risk_manager(strategy_name)

        # Apply optimized parameters to market maker config
        if "position_size_multiplier" in params:
            strategy_manager.wallet_type_configs["market_maker"][
                "position_size_multiplier"
            ] = params["position_size_multiplier"]

        if "stop_loss_pct" in params:
            strategy_manager.wallet_type_configs["market_maker"]["stop_loss_pct"] = (
                params["stop_loss_pct"]
            )

        if "take_profit_pct" in params:
            strategy_manager.wallet_type_configs["market_maker"]["take_profit_pct"] = (
                params["take_profit_pct"]
            )

        if "min_trade_quality_score" in params:
            strategy_manager.wallet_type_configs["market_maker"][
                "min_trade_quality_score"
            ] = params["min_trade_quality_score"]

        return strategy_manager

    def _analyze_parameter_sensitivity(
        self, results: List[Dict[str, Any]], param_names: List[str]
    ) -> Dict[str, Any]:
        """Analyze how sensitive performance is to parameter changes."""

        sensitivity = {}

        for param_name in param_names:
            param_values = [r["parameters"][param_name] for r in results]
            performances = [
                r["performance_metrics"]["total_return_pct"] for r in results
            ]

            # Calculate correlation between parameter and performance
            if len(set(param_values)) > 1:  # Only if parameter actually varies
                correlation = np.corrcoef(param_values, performances)[0, 1]
                sensitivity[param_name] = {
                    "correlation_with_performance": correlation,
                    "impact_level": (
                        "high"
                        if abs(correlation) > 0.7
                        else "medium"
                        if abs(correlation) > 0.3
                        else "low"
                    ),
                }

        return sensitivity
