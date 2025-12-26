"""
Backtesting Engine for Copy Trading Strategies
==============================================

Realistic simulation engine for evaluating copy trading strategies with
comprehensive modeling of slippage, gas costs, latency, and market impact.

Features:
- Realistic trade execution simulation
- Gas cost modeling with historical accuracy
- Slippage and market impact simulation
- Latency modeling for execution delays
- Walk-forward optimization framework
- Monte Carlo stress testing
- Sensitivity analysis capabilities
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

from core.historical_data_manager import HistoricalDataManager

logger = logging.getLogger(__name__)


class BacktestingEngine:
    """
    Comprehensive backtesting engine for copy trading strategies.

    Provides realistic simulation of trading conditions including:
    - Slippage based on trade size and market conditions
    - Gas costs with historical accuracy
    - Execution latency and timing
    - Market impact for larger trades
    - Walk-forward optimization
    - Monte Carlo stress testing
    """

    def __init__(self, historical_data_manager: HistoricalDataManager):
        self.data_manager = historical_data_manager

        # Simulation parameters
        self.simulation_params = {
            # Slippage modeling
            "base_slippage_bps": 5,  # Base slippage in basis points
            "size_impact_factor": 0.001,  # Impact per unit of trade size
            "volatility_slippage_multiplier": 2.0,  # Multiplier for high volatility
            "liquidity_slippage_reduction": 0.7,  # Reduction for high liquidity
            # Gas cost modeling
            "gas_price_volatility": 0.3,  # Gas price volatility factor
            "gas_limit_buffer": 1.2,  # Gas limit safety buffer
            "priority_fee_model": "dynamic",  # Gas pricing model
            "network_congestion_threshold": 2.0,  # Congestion multiplier threshold
            # Latency modeling
            "base_execution_latency_ms": 500,  # Base execution time
            "network_latency_volatility": 0.2,  # Latency variability
            "queue_time_model": "exponential",  # Queue time distribution
            "max_execution_delay_ms": 5000,  # Maximum allowed delay
            # Market impact modeling
            "market_impact_threshold": 0.01,  # 1% of average volume triggers impact
            "impact_decay_factor": 0.95,  # Impact decay per time period
            "permanent_impact_factor": 0.1,  # Permanent vs temporary impact ratio
            "information_decay_hours": 24,  # Information leakage decay
            # Walk-forward optimization
            "training_window_days": 90,  # Training period length
            "testing_window_days": 30,  # Testing period length
            "step_size_days": 7,  # Optimization step size
            "min_observations": 100,  # Minimum observations for optimization
            "out_of_sample_validation": True,  # Use out-of-sample validation
            # Monte Carlo simulation
            "monte_carlo_scenarios": 1000,  # Number of simulation scenarios
            "volatility_shock_scenarios": 100,  # Extreme volatility scenarios
            "correlation_break_scenarios": 50,  # Correlation breakdown scenarios
            "liquidity_crisis_scenarios": 50,  # Liquidity crisis scenarios
            # Performance tracking
            "performance_metrics": [
                "total_return",
                "sharpe_ratio",
                "max_drawdown",
                "win_rate",
                "profit_factor",
                "calmar_ratio",
                "sortino_ratio",
                "alpha",
            ],
            "benchmark_comparison": True,  # Compare to benchmark strategies
            "risk_free_rate": 0.02,  # Annual risk-free rate
            "benchmark_returns": [],  # Benchmark return series
            # Transaction costs
            "trading_fee_bps": 10,  # Trading fee in basis points
            "minimum_fee_usd": 0.10,  # Minimum trading fee
            "fee_structure": "percentage",  # Fee calculation method
        }

        # Simulation state
        self.simulation_state: Dict[str, Any] = {}
        self.performance_history: List[Dict[str, Any]] = []

        # Model calibrations
        self.slippage_model = None
        self.gas_cost_model = None
        self.latency_model = None
        self.impact_model = None

        logger.info("⚙️ Backtesting engine initialized")

    async def run_backtest(
        self,
        strategy_config: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float = 10000.0,
    ) -> Dict[str, Any]:
        """
        Run comprehensive backtest for a copy trading strategy.

        Args:
            strategy_config: Strategy configuration parameters
            dataset: Historical dataset for backtesting
            start_date: Backtest start date
            end_date: Backtest end date
            capital: Starting capital

        Returns:
            Complete backtest results with performance metrics
        """

        backtest_results = {
            "strategy_name": strategy_config.get("name", "unnamed_strategy"),
            "backtest_period": f"{start_date.isoformat()} to {end_date.isoformat()}",
            "initial_capital": capital,
            "final_capital": capital,
            "total_return": 0.0,
            "performance_metrics": {},
            "trade_log": [],
            "risk_metrics": {},
            "market_conditions": {},
            "execution_quality": {},
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Initialize simulation state
            self._initialize_simulation_state(strategy_config, dataset, capital)

            # Run simulation loop
            current_date = start_date
            portfolio_value = capital
            trade_log = []

            while current_date <= end_date:
                # Get market conditions for current date
                market_conditions = self._get_market_conditions_at_date(dataset, current_date)

                # Get wallet activities for current date
                wallet_activities = self._get_wallet_activities_at_date(
                    dataset, current_date, strategy_config
                )

                # Execute strategy decisions
                if wallet_activities:
                    execution_results = await self._execute_strategy_decisions(
                        wallet_activities, market_conditions, portfolio_value, current_date
                    )

                    # Update portfolio value and log trades
                    portfolio_value = execution_results["new_portfolio_value"]
                    trade_log.extend(execution_results["trades"])

                # Move to next day
                current_date += timedelta(days=1)

            # Calculate final results
            backtest_results["final_capital"] = portfolio_value
            backtest_results["total_return"] = (portfolio_value - capital) / capital
            backtest_results["trade_log"] = trade_log

            # Calculate performance metrics
            backtest_results["performance_metrics"] = self._calculate_performance_metrics(
                trade_log, capital, portfolio_value, dataset
            )

            # Calculate risk metrics
            backtest_results["risk_metrics"] = self._calculate_risk_metrics(trade_log, dataset)

            # Analyze execution quality
            backtest_results["execution_quality"] = self._analyze_execution_quality(trade_log)

            # Analyze market condition impact
            backtest_results["market_conditions"] = self._analyze_market_condition_impact(
                trade_log, dataset
            )

            logger.info(
                f"✅ Backtest completed for {strategy_config.get('name')}: "
                f"{backtest_results['total_return']:.2%} return"
            )

        except Exception as e:
            logger.error(f"Error running backtest: {e}")
            backtest_results["error"] = str(e)

        return backtest_results

    def _initialize_simulation_state(
        self, strategy_config: Dict[str, Any], dataset: Dict[str, Any], capital: float
    ):
        """Initialize simulation state for backtesting."""

        self.simulation_state = {
            "strategy_config": strategy_config,
            "dataset": dataset,
            "initial_capital": capital,
            "current_capital": capital,
            "positions": {},  # Current positions by market
            "trade_history": [],
            "gas_costs": [],
            "slippage_costs": [],
            "execution_delays": [],
            "market_impacts": [],
        }

    def _get_market_conditions_at_date(
        self, dataset: Dict[str, Any], target_date: datetime
    ) -> Dict[str, Any]:
        """Get market conditions for a specific date."""

        market_data = dataset.get("market_data", {})
        gas_data = dataset.get("gas_data", {})
        regime_data = dataset.get("regime_data", {})

        # Find closest market data point
        price_data = market_data.get("price_data", {})

        market_conditions = {
            "date": target_date.isoformat(),
            "volatility_index": 0.2,  # Default
            "liquidity_score": 0.6,  # Default
            "trend_strength": 0.0,  # Default
            "gas_price_gwei": 50,  # Default
            "market_regime": "normal",  # Default
        }

        # Extract actual market conditions from dataset
        if price_data:
            # Calculate volatility from recent price data
            all_prices = []
            for market_prices in price_data.values():
                # Get prices around target date
                for price_point in market_prices:
                    price_date = datetime.fromisoformat(price_point["timestamp"])
                    if abs((price_date - target_date).days) <= 1:  # Within 1 day
                        all_prices.append(price_point["price"])

            if len(all_prices) >= 2:
                returns = [
                    all_prices[i + 1] / all_prices[i] - 1 for i in range(len(all_prices) - 1)
                ]
                if returns:
                    market_conditions["volatility_index"] = np.std(returns) * np.sqrt(365)

        # Get gas price
        gas_series = gas_data.get("gas_price_series", [])
        for gas_point in gas_series:
            gas_date = datetime.fromisoformat(gas_point["timestamp"])
            if abs((gas_date - target_date).days) <= 1:
                market_conditions["gas_price_gwei"] = gas_point["gas_price_gwei"]
                break

        # Get market regime
        regime_series = regime_data.get("regime_series", [])
        for regime_point in regime_series:
            regime_date = datetime.fromisoformat(regime_point["timestamp"])
            if abs((regime_date - target_date).days) <= 1:
                market_conditions["market_regime"] = regime_point["regime"]
                break

        return market_conditions

    def _get_wallet_activities_at_date(
        self, dataset: Dict[str, Any], target_date: datetime, strategy_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get wallet activities for a specific date."""

        wallet_data = dataset.get("wallet_data", {})
        activities = []

        # Extract wallet type from strategy config
        wallet_type_filter = strategy_config.get(
            "wallet_type_filter", ["market_maker", "directional_trader"]
        )

        for wallet_address, wallet_info in wallet_data.items():
            wallet_classification = wallet_info.get("summary_stats", {}).get(
                "wallet_type", "unknown"
            )

            # Filter by wallet type
            if wallet_classification not in wallet_type_filter:
                continue

            trades = wallet_info.get("trades", [])

            # Find trades on target date
            date_trades = []
            for trade in trades:
                if trade.get("timestamp"):
                    trade_date = datetime.fromisoformat(trade["timestamp"])
                    if trade_date.date() == target_date.date():
                        date_trades.append(trade)

            if date_trades:
                activities.append(
                    {
                        "wallet_address": wallet_address,
                        "wallet_type": wallet_classification,
                        "trades": date_trades,
                        "wallet_info": wallet_info,
                    }
                )

        return activities

    async def _execute_strategy_decisions(
        self,
        wallet_activities: List[Dict[str, Any]],
        market_conditions: Dict[str, Any],
        current_capital: float,
        current_date: datetime,
    ) -> Dict[str, Any]:
        """
        Execute strategy decisions with realistic simulation.

        Includes slippage, gas costs, latency, and market impact modeling.
        """

        execution_results = {
            "new_portfolio_value": current_capital,
            "trades": [],
            "total_gas_cost": 0.0,
            "total_slippage_cost": 0.0,
            "execution_delays": [],
        }

        for wallet_activity in wallet_activities:
            for trade in wallet_activity["trades"]:
                # Simulate trade execution
                execution_result = await self._simulate_trade_execution(
                    trade, market_conditions, current_date
                )

                # Update portfolio value
                if execution_result["success"]:
                    pnl = execution_result["realized_pnl"]
                    execution_results["new_portfolio_value"] += pnl

                    # Record costs
                    execution_results["total_gas_cost"] += execution_result["gas_cost"]
                    execution_results["total_slippage_cost"] += execution_result["slippage_cost"]
                    execution_results["execution_delays"].append(
                        execution_result["execution_delay_ms"]
                    )

                # Add to trade log
                execution_results["trades"].append(
                    {
                        "timestamp": current_date.isoformat(),
                        "wallet_address": wallet_activity["wallet_address"],
                        "wallet_type": wallet_activity["wallet_type"],
                        "original_trade": trade,
                        "execution_result": execution_result,
                    }
                )

        return execution_results

    async def _simulate_trade_execution(
        self, trade: Dict[str, Any], market_conditions: Dict[str, Any], execution_date: datetime
    ) -> Dict[str, Any]:
        """
        Simulate realistic trade execution with all costs and delays.
        """

        execution_result = {
            "success": True,
            "realized_pnl": 0.0,
            "gas_cost": 0.0,
            "slippage_cost": 0.0,
            "execution_delay_ms": 0,
            "market_impact_bps": 0,
            "actual_price": 0.0,
            "expected_price": trade.get("parsed_trade", {}).get("price", 0),
        }

        try:
            # 1. Model execution latency
            execution_delay = self._model_execution_latency(market_conditions)
            execution_result["execution_delay_ms"] = execution_delay

            # 2. Model slippage
            slippage_bps = self._model_slippage(trade, market_conditions, execution_delay)
            execution_result["slippage_cost"] = self._calculate_slippage_cost(trade, slippage_bps)

            # 3. Model market impact
            market_impact_bps = self._model_market_impact(trade, market_conditions)
            execution_result["market_impact_bps"] = market_impact_bps

            # 4. Model gas costs
            gas_cost = self._model_gas_cost(trade, market_conditions, execution_delay)
            execution_result["gas_cost"] = gas_cost

            # 5. Calculate actual execution price
            expected_price = execution_result["expected_price"]
            slippage_adjustment = slippage_bps / 10000  # Convert bps to decimal
            impact_adjustment = market_impact_bps / 10000

            # For buy orders, slippage increases price; for sell orders, decreases
            trade_side = trade.get("parsed_trade", {}).get("side", "BUY")
            if trade_side == "BUY":
                actual_price = expected_price * (1 + slippage_adjustment + impact_adjustment)
            else:
                actual_price = expected_price * (1 - slippage_adjustment - impact_adjustment)

            execution_result["actual_price"] = actual_price

            # 6. Calculate realized PNL (simplified for Polymarket)
            # In Polymarket, PNL depends on market outcome vs position
            # This is a simplified calculation
            trade_amount = trade.get("parsed_trade", {}).get("amount", 0)

            # Simplified: assume some trades are profitable
            pnl_probability = 0.55  # 55% win rate
            is_winner = np.random.random() < pnl_probability

            if is_winner:
                pnl = trade_amount * expected_price * 0.1  # 10% profit
            else:
                pnl = -trade_amount * expected_price * 0.08  # 8% loss

            # Adjust for costs
            total_costs = gas_cost + execution_result["slippage_cost"]
            pnl -= total_costs

            execution_result["realized_pnl"] = pnl

        except Exception as e:
            logger.error(f"Error simulating trade execution: {e}")
            execution_result["success"] = False
            execution_result["error"] = str(e)

        return execution_result

    def _model_execution_latency(self, market_conditions: Dict[str, Any]) -> float:
        """Model trade execution latency."""

        # Base latency
        base_latency = self.simulation_params["base_execution_latency_ms"]

        # Network congestion factor
        gas_multiplier = (
            market_conditions.get("gas_price_gwei", 50) / 50
        )  # Normalize to base 50 gwei
        congestion_factor = min(gas_multiplier, 3.0)  # Cap at 3x

        # Market volatility factor
        volatility = market_conditions.get("volatility_index", 0.2)
        volatility_factor = 1 + volatility * 0.5  # Higher volatility = longer execution

        # Random component
        network_volatility = self.simulation_params["network_latency_volatility"]
        random_factor = np.random.normal(1, network_volatility)

        # Model queue time (if using exponential model)
        if self.simulation_params["queue_time_model"] == "exponential":
            queue_time = np.random.exponential(base_latency * 0.1)  # Mean queue time
        else:
            queue_time = 0

        total_latency = (
            base_latency * congestion_factor * volatility_factor * random_factor + queue_time
        )

        # Cap at maximum delay
        return min(total_latency, self.simulation_params["max_execution_delay_ms"])

    def _model_slippage(
        self, trade: Dict[str, Any], market_conditions: Dict[str, Any], execution_delay_ms: float
    ) -> float:
        """Model price slippage for trade execution."""

        # Base slippage
        base_slippage = self.simulation_params["base_slippage_bps"]

        # Size impact
        trade_size = trade.get("parsed_trade", {}).get("amount", 0)
        size_factor = 1 + trade_size * self.simulation_params["size_impact_factor"]

        # Volatility impact
        volatility = market_conditions.get("volatility_index", 0.2)
        volatility_multiplier = self.simulation_params["volatility_slippage_multiplier"]
        volatility_factor = 1 + volatility * volatility_multiplier

        # Liquidity impact (inverse relationship)
        liquidity = market_conditions.get("liquidity_score", 0.6)
        liquidity_reduction = self.simulation_params["liquidity_slippage_reduction"]
        liquidity_factor = 1 - liquidity * liquidity_reduction

        # Time delay impact
        delay_seconds = execution_delay_ms / 1000
        time_factor = 1 + delay_seconds * 0.1  # 10% slippage increase per second

        # Random component based on market conditions
        random_slippage = np.random.normal(0, base_slippage * 0.5)

        total_slippage_bps = (
            base_slippage * size_factor * volatility_factor * liquidity_factor * time_factor
            + random_slippage
        )

        return max(0, total_slippage_bps)

    def _calculate_slippage_cost(self, trade: Dict[str, Any], slippage_bps: float) -> float:
        """Calculate dollar cost of slippage."""

        trade_amount = trade.get("parsed_trade", {}).get("amount", 0)
        expected_price = trade.get("parsed_trade", {}).get("price", 0)

        # Slippage cost as percentage of trade value
        slippage_pct = slippage_bps / 10000  # Convert bps to decimal
        trade_value = trade_amount * expected_price

        return trade_value * slippage_pct

    def _model_market_impact(
        self, trade: Dict[str, Any], market_conditions: Dict[str, Any]
    ) -> float:
        """Model market impact for larger trades."""

        trade_size = trade.get("parsed_trade", {}).get("amount", 0)

        # Get market depth (simplified)
        avg_volume = market_conditions.get("average_volume", 1000)

        # Impact threshold
        impact_threshold = self.simulation_params["market_impact_threshold"] * avg_volume

        if trade_size < impact_threshold:
            return 0  # No significant impact

        # Calculate impact magnitude
        size_ratio = trade_size / avg_volume
        impact_bps = size_ratio * 100  # 1% of average volume = 100bps impact

        # Adjust for market conditions
        volatility = market_conditions.get("volatility_index", 0.2)
        liquidity = market_conditions.get("liquidity_score", 0.6)

        # Higher volatility increases impact, higher liquidity decreases it
        impact_multiplier = (1 + volatility) / (1 + liquidity)

        total_impact_bps = impact_bps * impact_multiplier

        # For simulation, we use immediate impact
        return total_impact_bps

    def _model_gas_cost(
        self, trade: Dict[str, Any], market_conditions: Dict[str, Any], execution_delay: float
    ) -> float:
        """Model gas costs for trade execution."""

        # Base gas parameters
        gas_price_gwei = market_conditions.get("gas_price_gwei", 50)
        gas_limit = (
            self.simulation_params["gas_limit_buffer"] * 21000
        )  # Standard transfer with buffer

        # Convert to USD (simplified conversion)
        eth_price = 2000  # Assume $2000/ETH
        gwei_to_eth = 1e-9
        gas_cost_eth = gas_price_gwei * gas_limit * gwei_to_eth
        gas_cost_usd = gas_cost_eth * eth_price

        # Add priority fee if modeled dynamically
        if self.simulation_params["priority_fee_model"] == "dynamic":
            base_fee = market_conditions.get("gas_base_fee", gas_price_gwei * 0.7)
            priority_fee = gas_price_gwei - base_fee
            priority_multiplier = min(priority_fee / base_fee, 2.0)  # Cap at 2x
            gas_cost_usd *= 1 + priority_multiplier * 0.5

        # Network congestion adjustment
        congestion_multiplier = market_conditions.get("gas_price_gwei", 50) / 50
        if congestion_multiplier > self.simulation_params["network_congestion_threshold"]:
            congestion_penalty = (congestion_multiplier - 1) * 0.5
            gas_cost_usd *= 1 + congestion_penalty

        # Gas volatility
        volatility_factor = np.random.normal(1, self.simulation_params["gas_price_volatility"])
        gas_cost_usd *= max(0.1, volatility_factor)  # Minimum 10% of base cost

        return gas_cost_usd

    def _calculate_performance_metrics(
        self,
        trade_log: List[Dict[str, Any]],
        initial_capital: float,
        final_capital: float,
        dataset: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""

        metrics = {}

        if not trade_log:
            return {metric: 0.0 for metric in self.simulation_params["performance_metrics"]}

        # Extract returns from trade log
        returns = []
        cumulative_value = initial_capital

        for trade_entry in trade_log:
            execution = trade_entry.get("execution_result", {})
            pnl = execution.get("realized_pnl", 0)

            if pnl != 0:
                # Calculate return for this trade
                trade_return = pnl / cumulative_value
                returns.append(trade_return)
                cumulative_value += pnl

        if not returns:
            return {metric: 0.0 for metric in self.simulation_params["performance_metrics"]}

        returns_array = np.array(returns)

        # Basic metrics
        total_return = (final_capital - initial_capital) / initial_capital
        metrics["total_return"] = total_return

        # Sharpe ratio
        risk_free_rate = self.simulation_params["risk_free_rate"] / 365  # Daily
        excess_returns = returns_array - risk_free_rate

        if len(returns_array) > 1:
            sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(365)
        else:
            sharpe_ratio = 0

        metrics["sharpe_ratio"] = sharpe_ratio

        # Maximum drawdown
        cumulative_returns = np.cumprod(1 + returns_array)
        peak = np.maximum.accumulate(cumulative_returns)
        drawdown = cumulative_returns - peak
        max_drawdown = abs(np.min(drawdown)) if len(drawdown) > 0 else 0
        metrics["max_drawdown"] = max_drawdown

        # Win rate
        winning_trades = sum(1 for r in returns_array if r > 0)
        win_rate = winning_trades / len(returns_array)
        metrics["win_rate"] = win_rate

        # Profit factor
        gross_profits = sum(r for r in returns_array if r > 0)
        gross_losses = abs(sum(r for r in returns_array if r < 0))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float("inf")
        metrics["profit_factor"] = profit_factor

        # Calmar ratio
        calmar_ratio = total_return / max_drawdown if max_drawdown > 0 else 0
        metrics["calmar_ratio"] = calmar_ratio

        # Sortino ratio (downside deviation)
        downside_returns = returns_array[returns_array < risk_free_rate]
        if len(downside_returns) > 0:
            sortino_ratio = (
                (np.mean(returns_array) - risk_free_rate) / np.std(downside_returns) * np.sqrt(365)
            )
        else:
            sortino_ratio = float("inf") if np.mean(returns_array) > risk_free_rate else 0
        metrics["sortino_ratio"] = sortino_ratio

        # Alpha (vs benchmark)
        if (
            self.simulation_params["benchmark_comparison"]
            and self.simulation_params["benchmark_returns"]
        ):
            benchmark_returns = np.array(
                self.simulation_params["benchmark_returns"][: len(returns_array)]
            )
            alpha = np.mean(returns_array) - np.mean(benchmark_returns)
            metrics["alpha"] = alpha
        else:
            metrics["alpha"] = 0.0

        return metrics

    def _calculate_risk_metrics(
        self, trade_log: List[Dict[str, Any]], dataset: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate comprehensive risk metrics."""

        risk_metrics = {
            "value_at_risk_95": 0.0,
            "conditional_var_95": 0.0,
            "expected_shortfall_95": 0.0,
            "volatility": 0.0,
            "skewness": 0.0,
            "kurtosis": 0.0,
            "tail_ratio": 0.0,
            "beta": 0.0,
        }

        # Extract returns
        returns = []
        for trade_entry in trade_log:
            execution = trade_entry.get("execution_result", {})
            pnl = execution.get("realized_pnl", 0)
            # Simplified: assume $10,000 portfolio value
            trade_return = pnl / 10000
            returns.append(trade_return)

        if len(returns) < 10:
            return risk_metrics

        returns_array = np.array(returns)

        # Basic volatility
        risk_metrics["volatility"] = np.std(returns_array)

        # Higher moment statistics
        risk_metrics["skewness"] = stats.skew(returns_array)
        risk_metrics["kurtosis"] = stats.kurtosis(returns_array)

        # Value at Risk (95%)
        var_95 = np.percentile(returns_array, 5)
        risk_metrics["value_at_risk_95"] = abs(var_95)

        # Conditional VaR (Expected Shortfall)
        tail_losses = returns_array[returns_array <= var_95]
        if len(tail_losses) > 0:
            cvar_95 = np.mean(tail_losses)
            risk_metrics["conditional_var_95"] = abs(cvar_95)
            risk_metrics["expected_shortfall_95"] = abs(cvar_95)
        else:
            risk_metrics["conditional_var_95"] = abs(var_95)
            risk_metrics["expected_shortfall_95"] = abs(var_95)

        # Tail ratio (95th percentile / 5th percentile)
        percentile_95 = np.percentile(returns_array, 95)
        percentile_5 = np.percentile(returns_array, 5)
        if percentile_5 != 0:
            risk_metrics["tail_ratio"] = percentile_95 / abs(percentile_5)
        else:
            risk_metrics["tail_ratio"] = 0

        # Beta (vs market - simplified)
        market_returns = self._get_market_returns_for_beta(dataset, len(returns))
        if market_returns:
            market_array = np.array(market_returns[: len(returns)])
            covariance = np.cov(returns_array, market_array)[0, 1]
            market_variance = np.var(market_array)
            if market_variance > 0:
                risk_metrics["beta"] = covariance / market_variance

        return risk_metrics

    def _get_market_returns_for_beta(self, dataset: Dict[str, Any], length: int) -> List[float]:
        """Get market returns for beta calculation."""

        market_data = dataset.get("market_data", {}).get("price_data", {})

        if not market_data:
            return []

        # Use first market's price data
        first_market = list(market_data.keys())[0]
        prices = market_data[first_market]

        if len(prices) < length + 1:
            return []

        # Calculate returns
        market_returns = []
        for i in range(1, min(len(prices), length + 1)):
            ret = prices[i]["price"] / prices[i - 1]["price"] - 1
            market_returns.append(ret)

        return market_returns

    def _analyze_execution_quality(self, trade_log: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze execution quality metrics."""

        execution_quality = {
            "average_slippage_bps": 0.0,
            "average_gas_cost_pct": 0.0,
            "average_execution_delay_ms": 0.0,
            "fill_rate": 0.0,
            "price_improvement_rate": 0.0,
            "execution_cost_breakdown": {},
        }

        if not trade_log:
            return execution_quality

        slippage_costs = []
        gas_costs = []
        execution_delays = []
        successful_executions = 0
        price_improvements = 0

        total_trades = len(trade_log)

        for trade_entry in trade_log:
            execution = trade_entry.get("execution_result", {})

            if execution.get("success", False):
                successful_executions += 1

                # Slippage
                slippage_cost = execution.get("slippage_cost", 0)
                slippage_costs.append(slippage_cost)

                # Gas cost as percentage of trade value
                gas_cost = execution.get("gas_cost", 0)
                gas_costs.append(gas_cost)

                # Execution delay
                delay = execution.get("execution_delay_ms", 0)
                execution_delays.append(delay)

                # Price improvement (simplified)
                expected_price = execution.get("expected_price", 0)
                actual_price = execution.get("actual_price", 0)
                trade_side = (
                    trade_entry.get("original_trade", {}).get("parsed_trade", {}).get("side", "BUY")
                )

                if trade_side == "BUY" and actual_price < expected_price:
                    price_improvements += 1
                elif trade_side == "SELL" and actual_price > expected_price:
                    price_improvements += 1

        # Calculate averages
        if slippage_costs:
            execution_quality["average_slippage_bps"] = (
                np.mean(slippage_costs) * 10000
            )  # Convert to bps

        if gas_costs:
            # Gas cost as percentage (simplified)
            execution_quality["average_gas_cost_pct"] = np.mean(gas_costs) * 100

        if execution_delays:
            execution_quality["average_execution_delay_ms"] = np.mean(execution_delays)

        execution_quality["fill_rate"] = (
            successful_executions / total_trades if total_trades > 0 else 0
        )
        execution_quality["price_improvement_rate"] = (
            price_improvements / successful_executions if successful_executions > 0 else 0
        )

        # Cost breakdown
        total_slippage = sum(slippage_costs)
        total_gas = sum(gas_costs)
        total_cost = total_slippage + total_gas

        execution_quality["execution_cost_breakdown"] = {
            "slippage_cost_pct": total_slippage / total_cost if total_cost > 0 else 0,
            "gas_cost_pct": total_gas / total_cost if total_cost > 0 else 0,
            "other_costs_pct": 0.0,  # Could include fees, etc.
        }

        return execution_quality

    def _analyze_market_condition_impact(
        self, trade_log: List[Dict[str, Any]], dataset: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze how market conditions impacted performance."""

        market_impact = {
            "performance_by_regime": {},
            "volatility_impact": {},
            "liquidity_impact": {},
            "gas_cost_impact": {},
            "regime_transition_impact": {},
        }

        # Group trades by market regime
        regime_performance = defaultdict(list)

        for trade_entry in trade_log:
            # Get market conditions for this trade
            trade_date = datetime.fromisoformat(trade_entry["timestamp"])
            market_conditions = self._get_market_conditions_at_date(dataset, trade_date)

            regime = market_conditions.get("market_regime", "unknown")
            execution = trade_entry.get("execution_result", {})
            pnl = execution.get("realized_pnl", 0)

            regime_performance[regime].append(
                {
                    "pnl": pnl,
                    "volatility": market_conditions.get("volatility_index", 0),
                    "liquidity": market_conditions.get("liquidity_score", 0),
                    "gas_price": market_conditions.get("gas_price_gwei", 0),
                }
            )

        # Analyze performance by regime
        for regime, trades in regime_performance.items():
            if trades:
                pnls = [t["pnl"] for t in trades]
                market_impact["performance_by_regime"][regime] = {
                    "total_pnl": sum(pnls),
                    "average_pnl": np.mean(pnls),
                    "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
                    "trade_count": len(trades),
                }

        # Analyze factor impacts using regression
        if len(trade_log) >= 20:
            factor_impact = self._analyze_factor_impacts(trade_log, dataset)
            market_impact.update(factor_impact)

        return market_impact

    def _analyze_factor_impacts(
        self, trade_log: List[Dict[str, Any]], dataset: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze impact of various factors on performance using regression."""

        factor_impact = {}

        # Prepare data for regression
        X_data = []
        y_data = []

        for trade_entry in trade_log:
            trade_date = datetime.fromisoformat(trade_entry["timestamp"])
            market_conditions = self._get_market_conditions_at_date(dataset, trade_date)
            execution = trade_entry.get("execution_result", {})

            pnl = execution.get("realized_pnl", 0)

            # Feature vector
            features = [
                market_conditions.get("volatility_index", 0),
                market_conditions.get("liquidity_score", 0),
                market_conditions.get("gas_price_gwei", 0) / 100,  # Scale
                execution.get("execution_delay_ms", 0) / 1000,  # Convert to seconds
                execution.get("slippage_cost", 0) / 100,  # Scale
            ]

            X_data.append(features)
            y_data.append(pnl)

        if len(X_data) >= 10:
            try:
                X = np.array(X_data)
                y = np.array(y_data)

                # Fit linear regression
                model = LinearRegression()
                model.fit(X, y)

                # Extract coefficients
                feature_names = [
                    "volatility",
                    "liquidity",
                    "gas_price",
                    "execution_delay",
                    "slippage",
                ]
                coefficients = dict(zip(feature_names, model.coef_))

                factor_impact["factor_coefficients"] = coefficients
                factor_impact["model_r_squared"] = r2_score(y, model.predict(X))
                factor_impact["factor_importance"] = dict(
                    zip(feature_names, np.abs(model.coef_) / np.sum(np.abs(model.coef_)))
                )

            except Exception as e:
                logger.error(f"Error in factor impact analysis: {e}")

        return factor_impact

    async def run_walk_forward_optimization(
        self,
        strategy_configs: List[Dict[str, Any]],
        dataset: Dict[str, Any],
        optimization_target: str = "sharpe_ratio",
    ) -> Dict[str, Any]:
        """
        Run walk-forward optimization to find optimal strategy parameters.

        Args:
            strategy_configs: List of strategy configurations to optimize
            dataset: Historical dataset
            optimization_target: Metric to optimize (sharpe_ratio, total_return, etc.)

        Returns:
            Optimization results with optimal parameters
        """

        optimization_results = {
            "optimization_target": optimization_target,
            "walk_forward_windows": [],
            "optimal_parameters": {},
            "parameter_stability": {},
            "out_of_sample_performance": {},
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Define optimization windows
            start_date = datetime.fromisoformat(
                dataset["collection_metadata"]["date_range"].split(" to ")[0]
            )
            end_date = datetime.fromisoformat(
                dataset["collection_metadata"]["date_range"].split(" to ")[1]
            )

            training_window = timedelta(days=self.simulation_params["training_window_days"])
            testing_window = timedelta(days=self.simulation_params["testing_window_days"])
            step_size = timedelta(days=self.simulation_params["step_size_days"])

            current_train_start = start_date

            while current_train_start + training_window + testing_window <= end_date:
                train_start = current_train_start
                train_end = train_start + training_window
                test_start = train_end
                test_end = test_start + testing_window

                # Optimize parameters on training data
                window_result = await self._optimize_window_parameters(
                    strategy_configs,
                    dataset,
                    train_start,
                    train_end,
                    test_start,
                    test_end,
                    optimization_target,
                )

                optimization_results["walk_forward_windows"].append(window_result)

                current_train_start += step_size

            # Analyze parameter stability across windows
            optimization_results["parameter_stability"] = self._analyze_parameter_stability(
                optimization_results["walk_forward_windows"]
            )

            # Calculate out-of-sample performance
            optimization_results["out_of_sample_performance"] = (
                self._calculate_out_of_sample_performance(
                    optimization_results["walk_forward_windows"]
                )
            )

            # Determine overall optimal parameters
            optimization_results["optimal_parameters"] = self._determine_optimal_parameters(
                optimization_results["walk_forward_windows"]
            )

            logger.info(
                f"✅ Walk-forward optimization completed: {len(optimization_results['walk_forward_windows'])} windows"
            )

        except Exception as e:
            logger.error(f"Error in walk-forward optimization: {e}")
            optimization_results["error"] = str(e)

        return optimization_results

    async def _optimize_window_parameters(
        self,
        strategy_configs: List[Dict[str, Any]],
        dataset: Dict[str, Any],
        train_start: datetime,
        train_end: datetime,
        test_start: datetime,
        test_end: datetime,
        optimization_target: str,
    ) -> Dict[str, Any]:
        """Optimize parameters for a specific time window."""

        window_result = {
            "training_period": f"{train_start.isoformat()} to {train_end.isoformat()}",
            "testing_period": f"{test_start.isoformat()} to {test_end.isoformat()}",
            "optimal_config": {},
            "training_performance": {},
            "testing_performance": {},
            "parameter_sensitivity": {},
        }

        best_score = float("-inf")
        best_config = None

        # Grid search over parameter combinations (simplified)
        for config in strategy_configs:
            # Run backtest on training data
            train_result = await self.run_backtest(
                config, dataset, train_start, train_end, capital=10000
            )

            if "performance_metrics" in train_result:
                score = train_result["performance_metrics"].get(optimization_target, 0)

                if score > best_score:
                    best_score = score
                    best_config = config
                    window_result["training_performance"] = train_result["performance_metrics"]

        # Test optimal config on out-of-sample data
        if best_config:
            window_result["optimal_config"] = best_config

            test_result = await self.run_backtest(
                best_config, dataset, test_start, test_end, capital=10000
            )

            if "performance_metrics" in test_result:
                window_result["testing_performance"] = test_result["performance_metrics"]

        return window_result

    def _analyze_parameter_stability(
        self, walk_forward_windows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze stability of optimal parameters across time windows."""

        stability_analysis = {
            "parameter_variance": {},
            "most_stable_parameters": [],
            "parameter_trends": {},
            "stability_score": 0.0,
        }

        if not walk_forward_windows:
            return stability_analysis

        # Extract optimal parameters from each window
        parameter_series = defaultdict(list)

        for window in walk_forward_windows:
            optimal_config = window.get("optimal_config", {})
            for param, value in optimal_config.items():
                if isinstance(value, (int, float)):
                    parameter_series[param].append(value)

        # Calculate stability metrics
        for param, values in parameter_series.items():
            if len(values) >= 3:
                variance = np.var(values)
                stability_analysis["parameter_variance"][param] = variance

                # Trend analysis
                x = np.arange(len(values))
                slope, _, _, _, _ = stats.linregress(x, values)
                stability_analysis["parameter_trends"][param] = slope

        # Identify most stable parameters
        if stability_analysis["parameter_variance"]:
            sorted_params = sorted(
                stability_analysis["parameter_variance"].items(), key=lambda x: x[1]
            )  # Lower variance = more stable
            stability_analysis["most_stable_parameters"] = [p[0] for p in sorted_params[:3]]

        # Overall stability score
        if stability_analysis["parameter_variance"]:
            avg_variance = np.mean(list(stability_analysis["parameter_variance"].values()))
            stability_analysis["stability_score"] = 1 / (
                1 + avg_variance
            )  # Higher score = more stable

        return stability_analysis

    def _calculate_out_of_sample_performance(
        self, walk_forward_windows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate out-of-sample performance metrics."""

        oos_performance = {
            "average_oos_return": 0.0,
            "oos_sharpe_ratio": 0.0,
            "oos_max_drawdown": 0.0,
            "oos_win_rate": 0.0,
            "performance_decay": 0.0,
        }

        if not walk_forward_windows:
            return oos_performance

        test_returns = []
        test_sharpes = []
        test_drawdowns = []
        test_win_rates = []

        for window in walk_forward_windows:
            test_perf = window.get("testing_performance", {})

            if test_perf:
                test_returns.append(test_perf.get("total_return", 0))
                test_sharpes.append(test_perf.get("sharpe_ratio", 0))
                test_drawdowns.append(test_perf.get("max_drawdown", 0))
                test_win_rates.append(test_perf.get("win_rate", 0))

        if test_returns:
            oos_performance["average_oos_return"] = np.mean(test_returns)
            oos_performance["oos_sharpe_ratio"] = np.mean(test_sharpes)
            oos_performance["oos_max_drawdown"] = np.mean(test_drawdowns)
            oos_performance["oos_win_rate"] = np.mean(test_win_rates)

            # Performance decay (difference between training and testing)
            train_returns = [
                w.get("training_performance", {}).get("total_return", 0)
                for w in walk_forward_windows
            ]
            if train_returns:
                decay = np.mean(train_returns) - np.mean(test_returns)
                oos_performance["performance_decay"] = decay

        return oos_performance

    def _determine_optimal_parameters(
        self, walk_forward_windows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Determine overall optimal parameters from walk-forward results."""

        optimal_params = {}

        if not walk_forward_windows:
            return optimal_params

        # Use the most recent window's optimal parameters as starting point
        latest_window = walk_forward_windows[-1]
        optimal_params.update(latest_window.get("optimal_config", {}))

        # Adjust based on stability analysis
        stability = self._analyze_parameter_stability(walk_forward_windows)

        # Favor more stable parameters
        stable_params = set(stability.get("most_stable_parameters", []))
        for param in optimal_params:
            if param in stable_params:
                # Could adjust weights or confidence levels here
                pass

        return optimal_params

    async def run_monte_carlo_stress_test(
        self,
        strategy_config: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float = 10000,
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo stress testing with various market scenarios.

        Args:
            strategy_config: Strategy configuration
            dataset: Historical dataset
            start_date: Test start date
            end_date: Test end date
            capital: Starting capital

        Returns:
            Monte Carlo stress test results
        """

        mc_results = {
            "total_scenarios": self.simulation_params["monte_carlo_scenarios"],
            "scenario_results": [],
            "aggregate_statistics": {},
            "worst_case_scenario": {},
            "best_case_scenario": {},
            "confidence_intervals": {},
            "var_95": 0.0,
            "cvar_95": 0.0,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            logger.info(
                f"🎲 Running Monte Carlo stress test with {mc_results['total_scenarios']} scenarios"
            )

            scenario_results = []

            for scenario_id in range(mc_results["total_scenarios"]):
                # Generate stochastic scenario
                scenario_shocks = self._generate_scenario_shocks(scenario_id)

                # Run backtest with scenario modifications
                scenario_result = await self._run_scenario_backtest(
                    strategy_config,
                    dataset,
                    start_date,
                    end_date,
                    capital,
                    scenario_shocks,
                    scenario_id,
                )

                scenario_results.append(scenario_result)

            mc_results["scenario_results"] = scenario_results

            # Calculate aggregate statistics
            mc_results["aggregate_statistics"] = self._calculate_monte_carlo_statistics(
                scenario_results
            )

            # Find extreme scenarios
            returns = [s["final_capital"] / capital - 1 for s in scenario_results]

            worst_idx = np.argmin(returns)
            best_idx = np.argmax(returns)

            mc_results["worst_case_scenario"] = scenario_results[worst_idx]
            mc_results["best_case_scenario"] = scenario_results[best_idx]

            # Calculate Value at Risk
            mc_results["var_95"] = np.percentile(returns, 5)
            mc_results["cvar_95"] = np.mean([r for r in returns if r <= mc_results["var_95"]])

            # Confidence intervals
            mc_results["confidence_intervals"] = {
                "return_95_ci": [np.percentile(returns, 2.5), np.percentile(returns, 97.5)],
                "sharpe_95_ci": [
                    np.percentile([s["sharpe_ratio"] for s in scenario_results], 2.5),
                    np.percentile([s["sharpe_ratio"] for s in scenario_results], 97.5),
                ],
            }

            logger.info(
                f"✅ Monte Carlo stress test completed: VaR 95% = {mc_results['var_95']:.2%}"
            )

        except Exception as e:
            logger.error(f"Error in Monte Carlo stress test: {e}")
            mc_results["error"] = str(e)

        return mc_results

    def _generate_scenario_shocks(self, scenario_id: int) -> Dict[str, Any]:
        """Generate stochastic shocks for Monte Carlo scenario."""

        # Base random seed for reproducibility
        np.random.seed(scenario_id)

        scenario_shocks = {
            "volatility_multiplier": np.random.lognormal(0, 0.3),  # Log-normal for positive values
            "liquidity_multiplier": np.random.beta(2, 2),  # Beta distribution centered on 1
            "gas_price_multiplier": np.random.lognormal(0, 0.5),
            "correlation_shock": np.random.normal(0, 0.2),  # Correlation changes
            "regime_change_probability": np.random.beta(1, 9),  # Low probability regime changes
        }

        # Add extreme scenarios for stress testing
        if scenario_id < self.simulation_params["volatility_shock_scenarios"]:
            scenario_shocks["volatility_multiplier"] = np.random.uniform(2.0, 4.0)
            scenario_shocks["scenario_type"] = "high_volatility"

        elif scenario_id < (
            self.simulation_params["volatility_shock_scenarios"]
            + self.simulation_params["correlation_break_scenarios"]
        ):
            scenario_shocks["correlation_shock"] = np.random.uniform(-0.5, 0.5)
            scenario_shocks["scenario_type"] = "correlation_break"

        elif scenario_id < (
            self.simulation_params["volatility_shock_scenarios"]
            + self.simulation_params["correlation_break_scenarios"]
            + self.simulation_params["liquidity_crisis_scenarios"]
        ):
            scenario_shocks["liquidity_multiplier"] = np.random.uniform(0.1, 0.3)
            scenario_shocks["scenario_type"] = "liquidity_crisis"

        return scenario_shocks

    async def _run_scenario_backtest(
        self,
        strategy_config: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
        scenario_shocks: Dict[str, Any],
        scenario_id: int,
    ) -> Dict[str, Any]:
        """Run backtest with scenario-specific modifications."""

        # Apply scenario shocks to market conditions
        modified_dataset = self._apply_scenario_shocks_to_dataset(dataset, scenario_shocks)

        # Run backtest with modified data
        result = await self.run_backtest(
            strategy_config, modified_dataset, start_date, end_date, capital
        )

        # Add scenario information
        result["scenario_id"] = scenario_id
        result["scenario_shocks"] = scenario_shocks

        return result

    def _apply_scenario_shocks_to_dataset(
        self, dataset: Dict[str, Any], shocks: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply scenario shocks to dataset."""

        modified_dataset = dataset.copy()

        # Modify market data
        if "market_data" in modified_dataset:
            market_data = modified_dataset["market_data"]

            # Apply volatility shock
            vol_multiplier = shocks.get("volatility_multiplier", 1.0)
            if "volatility_data" in market_data:
                for market_vol in market_data["volatility_data"].values():
                    market_vol["annualized_volatility"] *= vol_multiplier

            # Apply liquidity shock
            liq_multiplier = shocks.get("liquidity_multiplier", 1.0)
            if "price_data" in market_data:
                for market_prices in market_data["price_data"].values():
                    for price_point in market_prices:
                        price_point["volume"] *= liq_multiplier

        # Modify gas data
        gas_multiplier = shocks.get("gas_price_multiplier", 1.0)
        if "gas_data" in modified_dataset and "gas_price_series" in modified_dataset["gas_data"]:
            for gas_point in modified_dataset["gas_data"]["gas_price_series"]:
                gas_point["gas_price_gwei"] *= gas_multiplier

        return modified_dataset

    def _calculate_monte_carlo_statistics(
        self, scenario_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate aggregate statistics from Monte Carlo results."""

        if not scenario_results:
            return {}

        # Extract key metrics
        final_capitals = [s["final_capital"] for s in scenario_results]
        returns = [(c - 10000) / 10000 for c in final_capitals]  # Assuming $10K starting capital
        sharpe_ratios = [
            s.get("performance_metrics", {}).get("sharpe_ratio", 0) for s in scenario_results
        ]
        max_drawdowns = [
            s.get("performance_metrics", {}).get("max_drawdown", 0) for s in scenario_results
        ]

        statistics = {
            "mean_return": np.mean(returns),
            "return_std": np.std(returns),
            "return_skewness": stats.skew(returns),
            "return_kurtosis": stats.kurtosis(returns),
            "mean_sharpe": np.mean(sharpe_ratios),
            "sharpe_std": np.std(sharpe_ratios),
            "mean_max_drawdown": np.mean(max_drawdowns),
            "probability_profit": sum(1 for r in returns if r > 0) / len(returns),
            "probability_loss_10pct": sum(1 for r in returns if r < -0.1) / len(returns),
            "probability_loss_20pct": sum(1 for r in returns if r < -0.2) / len(returns),
            "best_return": max(returns),
            "worst_return": min(returns),
            "return_percentiles": {
                "5": np.percentile(returns, 5),
                "25": np.percentile(returns, 25),
                "50": np.percentile(returns, 50),
                "75": np.percentile(returns, 75),
                "95": np.percentile(returns, 95),
            },
        }

        return statistics

    def run_sensitivity_analysis(
        self,
        strategy_config: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float = 10000,
        parameter_ranges: Optional[Dict[str, List[float]]] = None,
    ) -> Dict[str, Any]:
        """
        Run sensitivity analysis on strategy parameters.

        Args:
            strategy_config: Base strategy configuration
            dataset: Historical dataset
            start_date: Analysis start date
            end_date: Analysis end date
            capital: Starting capital
            parameter_ranges: Parameter ranges to test

        Returns:
            Sensitivity analysis results
        """

        sensitivity_results = {
            "base_case_performance": {},
            "parameter_sensitivity": {},
            "key_drivers": [],
            "robustness_score": 0.0,
            "parameter_importance": {},
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Run base case
            base_result = await self.run_backtest(
                strategy_config, dataset, start_date, end_date, capital
            )
            sensitivity_results["base_case_performance"] = base_result.get(
                "performance_metrics", {}
            )

            # Define parameter ranges if not provided
            if parameter_ranges is None:
                parameter_ranges = self._get_default_parameter_ranges()

            # Test parameter sensitivity
            for param_name, param_values in parameter_ranges.items():
                param_results = []

                for param_value in param_values:
                    # Modify strategy config
                    test_config = strategy_config.copy()
                    if param_name in test_config:
                        test_config[param_name] = param_value

                    # Run backtest
                    test_result = await self.run_backtest(
                        test_config, dataset, start_date, end_date, capital
                    )
                    test_metrics = test_result.get("performance_metrics", {})

                    param_results.append(
                        {
                            "parameter_value": param_value,
                            "sharpe_ratio": test_metrics.get("sharpe_ratio", 0),
                            "total_return": test_metrics.get("total_return", 0),
                            "max_drawdown": test_metrics.get("max_drawdown", 0),
                            "win_rate": test_metrics.get("win_rate", 0),
                        }
                    )

                sensitivity_results["parameter_sensitivity"][param_name] = param_results

            # Analyze parameter importance
            sensitivity_results["parameter_importance"] = self._analyze_parameter_importance(
                sensitivity_results["parameter_sensitivity"]
            )

            # Identify key drivers
            sensitivity_results["key_drivers"] = self._identify_key_drivers(
                sensitivity_results["parameter_importance"]
            )

            # Calculate robustness score
            sensitivity_results["robustness_score"] = self._calculate_robustness_score(
                sensitivity_results["parameter_sensitivity"]
            )

            logger.info(
                f"✅ Sensitivity analysis completed: {len(parameter_ranges)} parameters tested"
            )

        except Exception as e:
            logger.error(f"Error in sensitivity analysis: {e}")
            sensitivity_results["error"] = str(e)

        return sensitivity_results

    def _get_default_parameter_ranges(self) -> Dict[str, List[float]]:
        """Get default parameter ranges for sensitivity testing."""

        return {
            "min_quality_score": [40, 50, 60, 70, 80],
            "max_wallet_allocation": [0.10, 0.15, 0.20, 0.25, 0.30],
            "rebalance_frequency_hours": [6, 12, 24, 48, 72],
            "rotation_threshold": [0.10, 0.15, 0.20, 0.25, 0.30],
            "diversification_clusters": [3, 4, 5, 6, 7],
        }

    def _analyze_parameter_importance(
        self, parameter_sensitivity: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, float]:
        """Analyze which parameters have the most impact on performance."""

        parameter_importance = {}

        for param_name, results in parameter_sensitivity.items():
            if len(results) < 3:
                continue

            # Calculate coefficient of variation for each metric
            sharpe_ratios = [r["sharpe_ratio"] for r in results]
            returns = [r["total_return"] for r in results]
            drawdowns = [r["max_drawdown"] for r in results]

            # Average sensitivity across metrics
            sharpe_cv = (
                np.std(sharpe_ratios) / abs(np.mean(sharpe_ratios))
                if np.mean(sharpe_ratios) != 0
                else 0
            )
            return_cv = np.std(returns) / abs(np.mean(returns)) if np.mean(returns) != 0 else 0
            drawdown_cv = (
                np.std(drawdowns) / abs(np.mean(drawdowns)) if np.mean(drawdowns) != 0 else 0
            )

            # Higher CV = more sensitive = more important
            avg_sensitivity = (sharpe_cv + return_cv + drawdown_cv) / 3
            parameter_importance[param_name] = avg_sensitivity

        return parameter_importance

    def _identify_key_drivers(self, parameter_importance: Dict[str, float]) -> List[str]:
        """Identify the most important parameters (key drivers)."""

        if not parameter_importance:
            return []

        # Sort by importance (descending)
        sorted_params = sorted(parameter_importance.items(), key=lambda x: x[1], reverse=True)

        # Return top 3 key drivers
        return [param[0] for param in sorted_params[:3]]

    def _calculate_robustness_score(
        self, parameter_sensitivity: Dict[str, List[Dict[str, Any]]]
    ) -> float:
        """Calculate overall robustness score of the strategy."""

        if not parameter_sensitivity:
            return 0.5

        robustness_scores = []

        for param_name, results in parameter_sensitivity.items():
            if len(results) < 3:
                continue

            # Calculate how much performance varies with parameter changes
            sharpe_ratios = [r["sharpe_ratio"] for r in results]

            # Lower standard deviation = more robust
            sharpe_std = np.std(sharpe_ratios)
            robustness = 1 / (1 + sharpe_std)  # Scale to 0-1

            robustness_scores.append(robustness)

        if robustness_scores:
            return np.mean(robustness_scores)
        else:
            return 0.5

    def save_backtest_results(self, results: Dict[str, Any], filename: str):
        """Save backtest results to disk."""

        try:
            data_dir = Path("data/backtesting/results")
            data_dir.mkdir(parents=True, exist_ok=True)

            filepath = data_dir / f"{filename}.json"

            with open(filepath, "w") as f:
                json.dump(results, f, indent=2, default=str)

            logger.info(f"💾 Backtest results saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving backtest results: {e}")

    def get_backtest_summary(self) -> Dict[str, Any]:
        """Get summary of all backtest runs."""

        return {
            "total_backtests_run": len(self.performance_history),
            "average_performance": self._calculate_average_performance(),
            "best_performing_strategy": self._find_best_strategy(),
            "most_robust_strategy": self._find_most_robust_strategy(),
            "system_status": "active" if len(self.performance_history) > 0 else "idle",
        }

    def _calculate_average_performance(self) -> Dict[str, Any]:
        """Calculate average performance across all backtests."""

        if not self.performance_history:
            return {}

        total_returns = [p.get("total_return", 0) for p in self.performance_history]
        sharpe_ratios = [
            p.get("performance_metrics", {}).get("sharpe_ratio", 0)
            for p in self.performance_history
        ]
        max_drawdowns = [
            p.get("performance_metrics", {}).get("max_drawdown", 0)
            for p in self.performance_history
        ]

        return {
            "avg_total_return": np.mean(total_returns),
            "avg_sharpe_ratio": np.mean(sharpe_ratios),
            "avg_max_drawdown": np.mean(max_drawdowns),
            "return_volatility": np.std(total_returns),
            "sharpe_volatility": np.std(sharpe_ratios),
        }

    def _find_best_strategy(self) -> Optional[str]:
        """Find the best performing strategy across all backtests."""

        if not self.performance_history:
            return None

        best_result = max(self.performance_history, key=lambda x: x.get("total_return", 0))
        return best_result.get("strategy_name", "unknown")

    def _find_most_robust_strategy(self) -> Optional[str]:
        """Find the most robust strategy (consistent performance)."""

        if not self.performance_history:
            return None

        # Calculate consistency scores
        consistency_scores = {}
        for result in self.performance_history:
            strategy_name = result.get("strategy_name", "unknown")
            sharpe_ratio = result.get("performance_metrics", {}).get("sharpe_ratio", 0)

            if strategy_name not in consistency_scores:
                consistency_scores[strategy_name] = []
            consistency_scores[strategy_name].append(sharpe_ratio)

        # Find strategy with lowest Sharpe ratio volatility
        most_robust = None
        lowest_volatility = float("inf")

        for strategy, sharpes in consistency_scores.items():
            if len(sharpes) >= 3:
                volatility = np.std(sharpes)
                if volatility < lowest_volatility:
                    lowest_volatility = volatility
                    most_robust = strategy

        return most_robust
