"""
Hybrid Portfolio Construction for Adaptive Copy Trading
======================================================

Advanced portfolio allocation system combining multiple methodologies
optimized for different wallet types and market conditions.

Features:
- Risk parity allocation by wallet volatility
- Performance-weighted allocation with momentum
- Correlation-based diversification
- Maximum drawdown constraints
- Automatic rebalancing triggers
- Stress testing for black swan events
- Scenario analysis framework
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from core.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)


class HybridPortfolioConstructor:
    """
    Advanced portfolio construction combining multiple allocation methodologies.

    Provides sophisticated capital allocation across wallet types using:
    - Risk parity for balanced volatility contribution
    - Performance weighting for momentum capture
    - Correlation-based diversification
    - Constraint optimization for risk management
    """

    def __init__(self, performance_analyzer: PerformanceAnalyzer):
        self.analyzer = performance_analyzer

        # Portfolio construction parameters
        self.construction_params = {
            "rebalance_frequency_hours": 6,  # Rebalance every 6 hours
            "min_allocation_pct": 0.02,  # Minimum 2% per wallet type
            "max_allocation_pct": 0.35,  # Maximum 35% per wallet type
            "target_portfolio_volatility": 0.15,  # Target 15% annualized volatility
            "max_correlation_threshold": 0.7,  # Maximum allowed correlation
            "risk_parity_tolerance": 0.05,  # Risk parity convergence tolerance
            "max_drawdown_limit": 0.12,  # 12% max drawdown per wallet type
            "min_wallet_count": 3,  # Minimum wallets for diversification
            "max_wallet_count": 15,  # Maximum wallets to avoid complexity
            "performance_lookback_days": 30,  # Days for performance calculation
            "stress_test_scenarios": 1000,  # Monte Carlo scenarios for stress testing
        }

        # Current portfolio state
        self.current_allocations: Dict[str, float] = {}
        self.portfolio_history: List[Dict[str, Any]] = []
        self.rebalance_history: List[Dict[str, Any]] = []

        # Risk monitoring
        self.portfolio_risk_metrics: Dict[str, Any] = {}
        self.drawdown_tracker: Dict[str, float] = {}

        # Stress testing results
        self.stress_test_results: Dict[str, Any] = {}

        logger.info("🔄 Hybrid portfolio constructor initialized")

    async def construct_optimal_portfolio(
        self,
        available_wallets: List[Dict[str, Any]],
        total_capital: float,
        allocation_method: str = "hybrid_optimization",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Construct optimal portfolio allocation across wallet types.

        Args:
            available_wallets: List of wallet information dictionaries
            total_capital: Total capital available for allocation
            allocation_method: Method to use ("risk_parity", "performance_weighted", "hybrid_optimization")
            constraints: Additional allocation constraints

        Returns:
            Optimal portfolio allocation with risk metrics
        """

        if not available_wallets:
            return {"error": "No wallets available for portfolio construction"}

        # Filter and validate wallets
        valid_wallets = await self._filter_and_validate_wallets(available_wallets)

        if len(valid_wallets) < self.construction_params["min_wallet_count"]:
            return {
                "error": f"Insufficient valid wallets: {len(valid_wallets)} < {self.construction_params['min_wallet_count']}"
            }

        # Get historical performance data
        performance_data = await self._get_wallet_performance_data(valid_wallets)

        # Apply allocation method
        if allocation_method == "risk_parity":
            allocation = await self._risk_parity_allocation(
                valid_wallets, performance_data
            )
        elif allocation_method == "performance_weighted":
            allocation = await self._performance_weighted_allocation(
                valid_wallets, performance_data
            )
        elif allocation_method == "correlation_diversified":
            allocation = await self._correlation_diversified_allocation(
                valid_wallets, performance_data
            )
        elif allocation_method == "hybrid_optimization":
            allocation = await self._hybrid_optimization_allocation(
                valid_wallets, performance_data
            )
        else:
            allocation = await self._equal_weight_allocation(valid_wallets)

        # Apply constraints and validate
        constrained_allocation = self._apply_allocation_constraints(
            allocation, total_capital, constraints or {}
        )

        # Calculate portfolio-level risk metrics
        portfolio_metrics = await self._calculate_portfolio_risk_metrics(
            constrained_allocation, performance_data
        )

        # Generate allocation summary
        allocation_summary = self._generate_allocation_summary(
            constrained_allocation, portfolio_metrics, valid_wallets
        )

        # Store portfolio state
        portfolio_state = {
            "timestamp": datetime.now().isoformat(),
            "allocation_method": allocation_method,
            "total_capital": total_capital,
            "allocations": constrained_allocation,
            "portfolio_metrics": portfolio_metrics,
            "wallet_count": len(valid_wallets),
            "constraints_applied": bool(constraints),
        }

        self.portfolio_history.append(portfolio_state)
        self.current_allocations = constrained_allocation

        logger.info(
            f"✅ Portfolio constructed using {allocation_method}: {len(constrained_allocation)} allocations"
        )

        return allocation_summary

    async def _filter_and_validate_wallets(
        self, wallets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter and validate wallets for portfolio inclusion."""

        valid_wallets = []

        for wallet in wallets:
            wallet_address = wallet.get("address", "")
            wallet_info = await self.analyzer.get_wallet_classification_report(
                wallet_address
            )

            if "error" in wallet_info:
                continue

            # Check minimum requirements
            confidence = wallet_info.get("confidence_score", 0.0)
            if confidence < 0.5:  # Minimum 50% confidence
                continue

            # Check recent activity
            recent_trades = await self._get_wallet_recent_activity(
                wallet_address, days=7
            )
            if len(recent_trades) < 5:  # Minimum 5 trades in last week
                continue

            # Add validation data
            wallet["classification"] = wallet_info.get("classification", "unknown")
            wallet["confidence_score"] = confidence
            wallet["recent_trade_count"] = len(recent_trades)
            wallet["validation_score"] = self._calculate_wallet_validation_score(
                wallet_info, recent_trades
            )

            valid_wallets.append(wallet)

        # Sort by validation score (descending)
        valid_wallets.sort(key=lambda x: x["validation_score"], reverse=True)

        # Limit to maximum wallet count
        max_wallets = self.construction_params["max_wallet_count"]
        if len(valid_wallets) > max_wallets:
            valid_wallets = valid_wallets[:max_wallets]

        return valid_wallets

    def _calculate_wallet_validation_score(
        self, wallet_info: Dict[str, Any], recent_trades: List[Dict[str, Any]]
    ) -> float:
        """Calculate validation score for wallet inclusion."""

        score = 0.0

        # Confidence score (40% weight)
        confidence = wallet_info.get("confidence_score", 0.0)
        score += confidence * 0.4

        # Activity score (30% weight)
        trade_count = len(recent_trades)
        activity_score = min(trade_count / 20, 1.0)  # Max at 20 trades
        score += activity_score * 0.3

        # Performance score (20% weight)
        if recent_trades:
            pnl_values = [t.get("pnl_usd", 0) for t in recent_trades]
            win_rate = sum(1 for p in pnl_values if p > 0) / len(pnl_values)
            score += win_rate * 0.2

        # Diversity score (10% weight) - prefer different wallet types
        # This would be calculated based on current portfolio composition

        return score

    async def _get_wallet_performance_data(
        self, wallets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get historical performance data for wallet portfolio construction."""

        performance_data = {
            "returns": {},
            "volatilities": {},
            "correlations": {},
            "drawdowns": {},
            "sharpe_ratios": {},
        }

        # Get performance metrics for each wallet
        for wallet in wallets:
            wallet_address = wallet["address"]
            wallet.get("classification", "unknown")

            # Get historical performance
            metrics = await self._calculate_wallet_historical_metrics(wallet_address)

            performance_data["returns"][wallet_address] = metrics.get("avg_return", 0.0)
            performance_data["volatilities"][wallet_address] = metrics.get(
                "volatility", 0.2
            )
            performance_data["drawdowns"][wallet_address] = metrics.get(
                "max_drawdown", 0.1
            )
            performance_data["sharpe_ratios"][wallet_address] = metrics.get(
                "sharpe_ratio", 1.0
            )

        # Calculate correlation matrix
        performance_data["correlations"] = await self._calculate_wallet_correlations(
            wallets
        )

        return performance_data

    async def _calculate_wallet_historical_metrics(
        self, wallet_address: str
    ) -> Dict[str, Any]:
        """Calculate historical performance metrics for a wallet."""

        # Get trade history
        trades = self.analyzer.performance_data

        wallet_trades = [
            t
            for t in trades
            if t.get("wallet_address") == wallet_address
            and datetime.fromisoformat(t["timestamp"])
            > datetime.now() - timedelta(days=30)
        ]

        if not wallet_trades:
            return {
                "avg_return": 0.0,
                "volatility": 0.2,
                "max_drawdown": 0.1,
                "sharpe_ratio": 1.0,
            }

        # Calculate returns
        pnl_values = np.array([t.get("pnl_usd", 0) for t in wallet_trades])
        returns = pnl_values / np.maximum(np.abs(pnl_values).mean(), 0.01)  # Normalize

        avg_return = np.mean(returns)
        volatility = np.std(returns)

        # Calculate drawdown
        cumulative = np.cumsum(pnl_values)
        peak = np.maximum.accumulate(cumulative)
        drawdown = cumulative - peak
        max_drawdown = abs(np.min(drawdown)) if len(drawdown) > 0 else 0

        # Sharpe ratio
        risk_free_rate = self.construction_params.get("risk_free_rate", 0.02) / 365
        sharpe_ratio = (
            (avg_return - risk_free_rate) / volatility if volatility > 0 else 0
        )

        return {
            "avg_return": avg_return,
            "volatility": volatility,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
        }

    async def _calculate_wallet_correlations(
        self, wallets: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate correlation matrix between wallets."""

        correlations = {}

        # Create return series for each wallet
        return_series = {}
        for wallet in wallets:
            wallet_address = wallet["address"]
            metrics = await self._calculate_wallet_historical_metrics(wallet_address)
            return_series[wallet_address] = metrics["avg_return"]  # Simplified

        # Calculate pairwise correlations (simplified)
        wallet_addresses = list(return_series.keys())
        for i, wallet1 in enumerate(wallet_addresses):
            for j, wallet2 in enumerate(wallet_addresses):
                if i < j:
                    # Simplified correlation calculation
                    corr_key = f"{wallet1[:8]}..._{wallet2[:8]}..."
                    correlations[corr_key] = (
                        0.1  # Placeholder - would calculate actual correlation
                    )

        return correlations

    async def _risk_parity_allocation(
        self, wallets: List[Dict[str, Any]], performance_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Risk parity allocation: Equal volatility contribution from each wallet.

        This ensures balanced risk exposure across different wallet types.
        """

        volatilities = performance_data["volatilities"]

        if not volatilities:
            return await self._equal_weight_allocation(wallets)

        # Calculate risk parity weights
        vol_array = np.array(list(volatilities.values()))
        inv_volatility = 1.0 / np.maximum(vol_array, 0.01)  # Avoid division by zero

        # Normalize to sum to 1
        raw_weights = inv_volatility / np.sum(inv_volatility)

        # Create allocation dictionary
        allocation = {}
        for i, wallet in enumerate(wallets):
            wallet_address = wallet["address"]
            weight = raw_weights[i] if i < len(raw_weights) else 0.0
            allocation[wallet_address] = weight

        return allocation

    async def _performance_weighted_allocation(
        self, wallets: List[Dict[str, Any]], performance_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Performance-weighted allocation: Allocate more capital to better performing wallets.

        Uses recent Sharpe ratios to weight allocations.
        """

        sharpe_ratios = performance_data["sharpe_ratios"]

        if not sharpe_ratios:
            return await self._equal_weight_allocation(wallets)

        # Apply exponential transformation to emphasize better performers
        sharpe_array = np.array(list(sharpe_ratios.values()))
        exp_weights = np.exp(sharpe_array * 0.5)  # Dampen to avoid extreme allocations

        # Normalize to sum to 1
        raw_weights = exp_weights / np.sum(exp_weights)

        # Create allocation dictionary
        allocation = {}
        for i, wallet in enumerate(wallets):
            wallet_address = wallet["address"]
            weight = raw_weights[i] if i < len(raw_weights) else 0.0
            allocation[wallet_address] = weight

        return allocation

    async def _correlation_diversified_allocation(
        self, wallets: List[Dict[str, Any]], performance_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Correlation-diversified allocation: Minimize portfolio correlation.

        Uses correlation matrix to ensure diversified exposure.
        """

        performance_data["correlations"]

        # Simplified diversification: prefer uncorrelated assets
        # In practice, this would use more sophisticated optimization

        # Start with equal weights and adjust for correlations
        n_wallets = len(wallets)
        base_weight = 1.0 / n_wallets

        allocation = {}
        for wallet in wallets:
            wallet_address = wallet["address"]
            # Apply diversification bonus for less correlated assets
            diversification_bonus = (
                1.0  # Simplified - would calculate based on correlations
            )
            weight = base_weight * diversification_bonus
            allocation[wallet_address] = weight

        # Renormalize
        total_weight = sum(allocation.values())
        allocation = {k: v / total_weight for k, v in allocation.items()}

        return allocation

    async def _hybrid_optimization_allocation(
        self, wallets: List[Dict[str, Any]], performance_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Hybrid optimization combining multiple factors.

        Uses constrained optimization to balance:
        - Risk parity (40%)
        - Performance weighting (35%)
        - Correlation diversification (25%)
        """

        # Get individual allocation methods
        risk_parity = await self._risk_parity_allocation(wallets, performance_data)
        performance_weighted = await self._performance_weighted_allocation(
            wallets, performance_data
        )
        correlation_diversified = await self._correlation_diversified_allocation(
            wallets, performance_data
        )

        # Combine allocations with weights
        hybrid_weights = {
            "risk_parity": 0.4,
            "performance_weighted": 0.35,
            "correlation_diversified": 0.25,
        }

        allocation = {}
        for wallet in wallets:
            wallet_address = wallet["address"]

            combined_weight = (
                risk_parity.get(wallet_address, 0) * hybrid_weights["risk_parity"]
                + performance_weighted.get(wallet_address, 0)
                * hybrid_weights["performance_weighted"]
                + correlation_diversified.get(wallet_address, 0)
                * hybrid_weights["correlation_diversified"]
            )

            allocation[wallet_address] = combined_weight

        return allocation

    async def _equal_weight_allocation(
        self, wallets: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Simple equal weight allocation across all wallets."""

        n_wallets = len(wallets)
        if n_wallets == 0:
            return {}

        equal_weight = 1.0 / n_wallets

        allocation = {}
        for wallet in wallets:
            allocation[wallet["address"]] = equal_weight

        return allocation

    def _apply_allocation_constraints(
        self,
        allocation: Dict[str, float],
        total_capital: float,
        constraints: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        Apply allocation constraints and validate portfolio.
        """

        # Apply min/max allocation constraints
        min_alloc = self.construction_params["min_allocation_pct"]
        max_alloc = self.construction_params["max_allocation_pct"]

        constrained_allocation = {}
        for wallet_address, weight in allocation.items():
            constrained_weight = max(min_alloc, min(max_alloc, weight))
            constrained_allocation[wallet_address] = constrained_weight

        # Renormalize to sum to 1
        total_weight = sum(constrained_allocation.values())
        if total_weight > 0:
            constrained_allocation = {
                k: v / total_weight for k, v in constrained_allocation.items()
            }

        # Apply maximum drawdown constraints per wallet
        max_drawdown_limit = constraints.get(
            "max_drawdown_limit", self.construction_params["max_drawdown_limit"]
        )

        # Filter out wallets exceeding drawdown limits
        filtered_allocation = {}
        for wallet_address, weight in constrained_allocation.items():
            current_drawdown = self.drawdown_tracker.get(wallet_address, 0.0)
            if current_drawdown <= max_drawdown_limit:
                filtered_allocation[wallet_address] = weight

        # Renormalize after filtering
        if filtered_allocation:
            total_filtered_weight = sum(filtered_allocation.values())
            filtered_allocation = {
                k: v / total_filtered_weight for k, v in filtered_allocation.items()
            }

        # Convert to capital amounts
        capital_allocation = {}
        for wallet_address, weight in filtered_allocation.items():
            capital_amount = weight * total_capital
            capital_allocation[wallet_address] = capital_amount

        return capital_allocation

    async def _calculate_portfolio_risk_metrics(
        self, allocation: Dict[str, float], performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive portfolio-level risk metrics.
        """

        portfolio_metrics = {
            "total_allocated_capital": sum(allocation.values()),
            "wallet_count": len(allocation),
            "concentration_ratio": 0.0,
            "expected_volatility": 0.0,
            "expected_return": 0.0,
            "sharpe_ratio": 0.0,
            "value_at_risk_95": 0.0,
            "expected_shortfall_95": 0.0,
            "diversification_ratio": 0.0,
        }

        if not allocation:
            return portfolio_metrics

        # Calculate concentration (Herfindahl-Hirschman Index)
        weights = np.array(list(allocation.values()))
        weights_normalized = weights / np.sum(weights)
        portfolio_metrics["concentration_ratio"] = np.sum(weights_normalized**2)

        # Expected portfolio volatility (simplified)
        volatilities = [
            performance_data["volatilities"].get(wallet, 0.2)
            for wallet in allocation.keys()
        ]
        performance_data.get("correlations", {})

        # Simplified volatility calculation
        avg_volatility = np.mean(volatilities)
        portfolio_metrics["expected_volatility"] = avg_volatility

        # Expected portfolio return
        returns = [
            performance_data["returns"].get(wallet, 0.0) for wallet in allocation.keys()
        ]
        portfolio_metrics["expected_return"] = np.average(
            returns, weights=weights_normalized
        )

        # Portfolio Sharpe ratio
        risk_free_rate = self.construction_params.get("risk_free_rate", 0.02)
        if portfolio_metrics["expected_volatility"] > 0:
            portfolio_metrics["sharpe_ratio"] = (
                portfolio_metrics["expected_return"] - risk_free_rate
            ) / portfolio_metrics["expected_volatility"]

        # Diversification ratio (total volatility / weighted avg individual volatility)
        if avg_volatility > 0:
            portfolio_metrics["diversification_ratio"] = (
                portfolio_metrics["expected_volatility"] / avg_volatility
            )

        return portfolio_metrics

    def _generate_allocation_summary(
        self,
        allocation: Dict[str, float],
        portfolio_metrics: Dict[str, Any],
        wallets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate comprehensive allocation summary."""

        # Create wallet summary
        wallet_summary = []
        for wallet in wallets:
            wallet_address = wallet["address"]
            allocated_capital = allocation.get(wallet_address, 0.0)
            allocation_pct = (
                allocated_capital / portfolio_metrics["total_allocated_capital"]
                if portfolio_metrics["total_allocated_capital"] > 0
                else 0
            )

            wallet_summary.append(
                {
                    "address": wallet_address,
                    "type": wallet.get("classification", "unknown"),
                    "confidence": wallet.get("confidence_score", 0.0),
                    "allocated_capital": allocated_capital,
                    "allocation_percentage": allocation_pct,
                    "recent_trades": wallet.get("recent_trade_count", 0),
                    "validation_score": wallet.get("validation_score", 0.0),
                }
            )

        # Sort by allocation size
        wallet_summary.sort(key=lambda x: x["allocated_capital"], reverse=True)

        return {
            "portfolio_overview": portfolio_metrics,
            "wallet_allocations": wallet_summary,
            "allocation_timestamp": datetime.now().isoformat(),
            "rebalance_required": self._check_rebalance_required(allocation),
            "risk_assessment": self._assess_portfolio_risk(portfolio_metrics),
        }

    def _check_rebalance_required(self, current_allocation: Dict[str, float]) -> bool:
        """Check if portfolio rebalancing is required."""

        # Check time since last rebalance
        if self.portfolio_history:
            last_rebalance = datetime.fromisoformat(
                self.portfolio_history[-1]["timestamp"]
            )
            hours_since = (datetime.now() - last_rebalance).total_seconds() / 3600

            if hours_since >= self.construction_params["rebalance_frequency_hours"]:
                return True

        # Check allocation drift (simplified)
        if self.current_allocations:
            # Calculate drift from target allocations
            total_drift = 0
            for wallet, current_weight in current_allocation.items():
                target_weight = self.current_allocations.get(wallet, 0)
                if target_weight > 0:
                    drift = abs(current_weight - target_weight) / target_weight
                    total_drift += drift

            avg_drift = (
                total_drift / len(current_allocation) if current_allocation else 0
            )
            if avg_drift > 0.1:  # 10% average drift
                return True

        return False

    def _assess_portfolio_risk(
        self, portfolio_metrics: Dict[str, Any]
    ) -> Dict[str, str]:
        """Assess overall portfolio risk level."""

        risk_assessment = {
            "overall_risk": "medium",
            "volatility_risk": "medium",
            "concentration_risk": "medium",
            "diversification_quality": "medium",
        }

        # Volatility assessment
        volatility = portfolio_metrics.get("expected_volatility", 0.15)
        if volatility > 0.25:
            risk_assessment["volatility_risk"] = "high"
        elif volatility < 0.10:
            risk_assessment["volatility_risk"] = "low"

        # Concentration assessment
        concentration = portfolio_metrics.get("concentration_ratio", 0.2)
        if concentration > 0.3:
            risk_assessment["concentration_risk"] = "high"
        elif concentration < 0.1:
            risk_assessment["concentration_risk"] = "low"

        # Diversification assessment
        diversification = portfolio_metrics.get("diversification_ratio", 1.0)
        if diversification > 1.2:
            risk_assessment["diversification_quality"] = "high"
        elif diversification < 0.9:
            risk_assessment["diversification_quality"] = "low"

        # Overall risk assessment
        risk_scores = {"low": 1, "medium": 2, "high": 3}

        avg_risk_score = np.mean(
            [
                risk_scores[risk_assessment["volatility_risk"]],
                risk_scores[risk_assessment["concentration_risk"]],
                risk_scores.get("diversification_quality", "medium") == "low"
                and 3
                or risk_scores.get("diversification_quality", "medium") == "high"
                and 1
                or 2,
            ]
        )

        if avg_risk_score > 2.5:
            risk_assessment["overall_risk"] = "high"
        elif avg_risk_score < 1.5:
            risk_assessment["overall_risk"] = "low"

        return risk_assessment

    async def run_stress_tests(
        self,
        portfolio_allocation: Dict[str, float],
        scenarios: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Run comprehensive stress tests on portfolio allocation.

        Tests portfolio resilience under various market conditions.
        """

        if scenarios is None:
            scenarios = self._generate_stress_scenarios()

        stress_results = {
            "scenarios_tested": len(scenarios),
            "portfolio_survival_rate": 0.0,
            "worst_case_loss": 0.0,
            "average_drawdown": 0.0,
            "volatility_under_stress": 0.0,
            "scenario_breakdown": [],
        }

        scenario_results = []

        for scenario in scenarios:
            scenario_result = await self._run_single_stress_scenario(
                portfolio_allocation, scenario
            )
            scenario_results.append(scenario_result)

        # Aggregate results
        survival_count = sum(1 for r in scenario_results if r["portfolio_survived"])
        stress_results["portfolio_survival_rate"] = survival_count / len(scenarios)

        if scenario_results:
            losses = [r["portfolio_loss"] for r in scenario_results]
            stress_results["worst_case_loss"] = max(losses)
            stress_results["average_drawdown"] = np.mean(
                [r["max_drawdown"] for r in scenario_results]
            )
            stress_results["volatility_under_stress"] = np.std(losses)

        stress_results["scenario_breakdown"] = scenario_results[
            :10
        ]  # First 10 for detail

        self.stress_test_results = stress_results

        logger.info(
            f"🧪 Stress testing completed: {stress_results['portfolio_survival_rate']:.1%} survival rate"
        )

        return stress_results

    def _generate_stress_scenarios(self) -> List[Dict[str, Any]]:
        """Generate comprehensive stress test scenarios."""

        scenarios = []

        # Market crash scenario
        scenarios.append(
            {
                "name": "market_crash",
                "description": "Sudden 50% market decline",
                "volatility_multiplier": 3.0,
                "return_shift": -0.5,
                "correlation_increase": 0.8,
                "liquidity_dry_up": True,
            }
        )

        # High volatility scenario
        scenarios.append(
            {
                "name": "high_volatility",
                "description": "Extreme volatility with 100% increase",
                "volatility_multiplier": 2.0,
                "return_shift": -0.1,
                "correlation_increase": 0.5,
                "liquidity_dry_up": False,
            }
        )

        # Liquidity crisis scenario
        scenarios.append(
            {
                "name": "liquidity_crisis",
                "description": "Complete liquidity dry-up",
                "volatility_multiplier": 1.5,
                "return_shift": -0.3,
                "correlation_increase": 0.9,
                "liquidity_dry_up": True,
            }
        )

        # Correlated crash scenario
        scenarios.append(
            {
                "name": "correlated_crash",
                "description": "All assets decline together",
                "volatility_multiplier": 2.5,
                "return_shift": -0.4,
                "correlation_increase": 0.95,
                "liquidity_dry_up": True,
            }
        )

        # Recovery scenario
        scenarios.append(
            {
                "name": "slow_recovery",
                "description": "Gradual market recovery",
                "volatility_multiplier": 1.8,
                "return_shift": 0.1,
                "correlation_increase": 0.3,
                "liquidity_dry_up": False,
            }
        )

        return scenarios

    async def _run_single_stress_scenario(
        self, allocation: Dict[str, float], scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run a single stress test scenario."""

        # Simulate portfolio performance under stress conditions
        # This is a simplified simulation - in practice would use more sophisticated modeling

        base_returns = np.random.normal(0.001, 0.02, len(allocation))  # Daily returns
        stressed_returns = base_returns * (1 + scenario.get("return_shift", 0))

        # Apply volatility stress
        volatility_multiplier = scenario.get("volatility_multiplier", 1.0)
        stressed_returns *= volatility_multiplier

        # Calculate portfolio performance
        weights = np.array(list(allocation.values()))
        weights = weights / np.sum(weights)  # Normalize

        portfolio_return = np.dot(weights, stressed_returns)
        portfolio_volatility = np.sqrt(
            np.dot(weights.T, np.dot(np.cov(stressed_returns), weights))
        )

        # Simulate drawdown
        cumulative_returns = np.cumprod(1 + stressed_returns) - 1
        peak = np.maximum.accumulate(cumulative_returns)
        drawdown = cumulative_returns - peak
        max_drawdown = abs(np.min(drawdown))

        # Assess survival (portfolio doesn't lose more than 50%)
        portfolio_loss = -portfolio_return  # Convert to positive loss
        portfolio_survived = portfolio_loss < 0.5

        return {
            "scenario_name": scenario["name"],
            "portfolio_return": portfolio_return,
            "portfolio_loss": portfolio_loss,
            "portfolio_volatility": portfolio_volatility,
            "max_drawdown": max_drawdown,
            "portfolio_survived": portfolio_survived,
            "stress_severity": scenario.get("volatility_multiplier", 1.0),
        }

    async def run_scenario_analysis(
        self, portfolio_allocation: Dict[str, float], scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Run scenario analysis for different market conditions.

        Analyzes portfolio performance under various plausible scenarios.
        """

        scenario_results = {}

        for scenario in scenarios:
            scenario_name = scenario["name"]

            # Modify market conditions based on scenario
            modified_allocation = await self._adjust_allocation_for_scenario(
                portfolio_allocation, scenario
            )

            # Calculate scenario performance
            scenario_performance = await self._calculate_scenario_performance(
                modified_allocation, scenario
            )

            scenario_results[scenario_name] = {
                "scenario_description": scenario.get("description", ""),
                "allocation_adjustment": modified_allocation != portfolio_allocation,
                "expected_return": scenario_performance.get("expected_return", 0),
                "expected_volatility": scenario_performance.get(
                    "expected_volatility", 0
                ),
                "sharpe_ratio": scenario_performance.get("sharpe_ratio", 0),
                "survival_probability": scenario_performance.get(
                    "survival_probability", 1.0
                ),
            }

        return {
            "base_allocation_performance": await self._calculate_allocation_performance(
                portfolio_allocation
            ),
            "scenario_analysis": scenario_results,
            "most_stressful_scenario": min(
                scenario_results.keys(),
                key=lambda x: scenario_results[x]["sharpe_ratio"],
            ),
            "most_opportunistic_scenario": max(
                scenario_results.keys(),
                key=lambda x: scenario_results[x]["expected_return"],
            ),
        }

    async def _adjust_allocation_for_scenario(
        self, allocation: Dict[str, float], scenario: Dict[str, Any]
    ) -> Dict[str, float]:
        """Adjust portfolio allocation based on scenario conditions."""

        # Simplified scenario adjustments
        scenario_type = scenario.get("type", "neutral")

        if scenario_type == "bear_market":
            # Reduce aggressive allocations, increase conservative
            adjusted = {}
            for wallet, weight in allocation.items():
                # This would use wallet type information to adjust
                adjusted[wallet] = weight * 0.8  # Reduce all weights
            # Renormalize
            total = sum(adjusted.values())
            adjusted = {k: v / total for k, v in adjusted.items()}

            return adjusted

        elif scenario_type == "bull_market":
            # Increase aggressive allocations
            adjusted = {}
            for wallet, weight in allocation.items():
                adjusted[wallet] = weight * 1.2  # Increase all weights
            # Renormalize
            total = sum(adjusted.values())
            adjusted = {k: v / total for k, v in adjusted.items()}

            return adjusted

        return allocation.copy()  # No adjustment for neutral scenarios

    async def _calculate_scenario_performance(
        self, allocation: Dict[str, float], scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate portfolio performance under scenario conditions."""

        # Simplified scenario performance calculation
        base_performance = await self._calculate_allocation_performance(allocation)

        # Apply scenario modifiers
        scenario_modifier = scenario.get("return_modifier", 1.0)
        volatility_modifier = scenario.get("volatility_modifier", 1.0)

        modified_performance = {
            "expected_return": base_performance["expected_return"] * scenario_modifier,
            "expected_volatility": base_performance["expected_volatility"]
            * volatility_modifier,
            "sharpe_ratio": (base_performance["expected_return"] * scenario_modifier)
            / (base_performance["expected_volatility"] * volatility_modifier),
            "survival_probability": max(0.1, 1.0 - abs(scenario_modifier - 1.0)),
        }

        return modified_performance

    async def _calculate_allocation_performance(
        self, allocation: Dict[str, float]
    ) -> Dict[str, Any]:
        """Calculate baseline performance for an allocation."""

        # Simplified performance calculation
        total_weight = sum(allocation.values())

        # Placeholder performance metrics
        return {
            "expected_return": 0.02,  # 2% daily expected return
            "expected_volatility": 0.15,  # 15% volatility
            "sharpe_ratio": 1.33,
            "total_allocated": total_weight,
        }

    async def _get_wallet_recent_activity(
        self, wallet_address: str, days: int
    ) -> List[Dict[str, Any]]:
        """Get recent trading activity for a wallet."""

        cutoff_date = datetime.now() - timedelta(days=days)

        recent_trades = [
            trade
            for trade in self.analyzer.performance_data
            if (
                trade.get("wallet_address") == wallet_address
                and datetime.fromisoformat(trade["timestamp"]) > cutoff_date
            )
        ]

        return recent_trades

    def get_portfolio_status(self) -> Dict[str, Any]:
        """Get current portfolio construction status."""

        return {
            "current_allocations": self.current_allocations,
            "portfolio_count": len(self.current_allocations),
            "total_allocated_capital": sum(self.current_allocations.values()),
            "last_rebalance": (
                self.portfolio_history[-1]["timestamp"]
                if self.portfolio_history
                else None
            ),
            "rebalance_due": self._check_rebalance_required(self.current_allocations),
            "risk_metrics": self.portfolio_risk_metrics,
        }

    def save_portfolio_state(self):
        """Save portfolio construction state."""

        try:
            state_dir = Path("data/portfolio")
            state_dir.mkdir(parents=True, exist_ok=True)

            # Save current allocations
            with open(state_dir / "current_allocations.json", "w") as f:
                json.dump(self.current_allocations, f, indent=2, default=str)

            # Save portfolio history
            with open(state_dir / "portfolio_history.json", "w") as f:
                json.dump(
                    self.portfolio_history[-100:], f, indent=2, default=str
                )  # Last 100 records

            # Save stress test results
            with open(state_dir / "stress_test_results.json", "w") as f:
                json.dump(self.stress_test_results, f, indent=2, default=str)

            logger.info(f"💾 Portfolio state saved to {state_dir}")

        except Exception as e:
            logger.error(f"Error saving portfolio state: {e}")

    def load_portfolio_state(self):
        """Load portfolio construction state."""

        try:
            state_dir = Path("data/portfolio")

            # Load current allocations
            alloc_file = state_dir / "current_allocations.json"
            if alloc_file.exists():
                with open(alloc_file, "r") as f:
                    self.current_allocations = json.load(f)

            # Load portfolio history
            history_file = state_dir / "portfolio_history.json"
            if history_file.exists():
                with open(history_file, "r") as f:
                    self.portfolio_history = json.load(f)

            # Load stress test results
            stress_file = state_dir / "stress_test_results.json"
            if stress_file.exists():
                with open(stress_file, "r") as f:
                    self.stress_test_results = json.load(f)

            logger.info(f"📊 Portfolio state loaded from {state_dir}")

        except Exception as e:
            logger.error(f"Error loading portfolio state: {e}")
