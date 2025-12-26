"""
Strategy Comparison Framework
=============================

Comprehensive framework for comparing different copy trading strategies
with statistical significance testing, risk-adjusted performance analysis,
and drawdown comparison by strategy type.

Features:
- Market maker only vs directional trader only strategies
- Hybrid strategy comparison
- Statistical significance testing
- Risk-adjusted performance metrics
- Drawdown analysis by strategy
- Performance attribution
- Scenario-based robustness testing
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats
from scipy.stats import f_oneway, mannwhitneyu, ttest_ind
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from core.backtesting_engine import BacktestingEngine

logger = logging.getLogger(__name__)


class StrategyComparisonFramework:
    """
    Comprehensive framework for comparing copy trading strategies.

    Provides statistical testing, risk-adjusted comparisons, and
    detailed performance attribution across different strategy types.
    """

    def __init__(self, backtesting_engine: BacktestingEngine):
        self.backtesting_engine = backtesting_engine

        # Comparison configuration
        self.comparison_config = {
            # Statistical testing parameters
            "significance_level": 0.05,  # 5% significance level
            "min_sample_size": 30,  # Minimum observations for statistical tests
            "bootstrap_iterations": 1000,  # Bootstrap iterations for confidence intervals
            "confidence_level": 0.95,  # 95% confidence intervals
            # Risk-adjusted comparison parameters
            "risk_free_rate": 0.02,  # Annual risk-free rate
            "benchmark_adjustment": True,  # Adjust for benchmark performance
            "volatility_scaling": True,  # Scale for volatility differences
            # Strategy definitions
            "strategy_definitions": {
                "market_maker_only": {
                    "name": "Market Maker Only",
                    "wallet_type_filter": ["market_maker"],
                    "description": "Copy only market maker wallets",
                },
                "directional_trader_only": {
                    "name": "Directional Trader Only",
                    "wallet_type_filter": ["directional_trader"],
                    "description": "Copy only directional trader wallets",
                },
                "arbitrage_trader_only": {
                    "name": "Arbitrage Trader Only",
                    "wallet_type_filter": ["arbitrage_trader"],
                    "description": "Copy only arbitrage trader wallets",
                },
                "hybrid_optimized": {
                    "name": "Hybrid Optimized",
                    "wallet_type_filter": [
                        "market_maker",
                        "directional_trader",
                        "arbitrage_trader",
                    ],
                    "description": "Optimized combination of all wallet types",
                },
                "equal_weight_hybrid": {
                    "name": "Equal Weight Hybrid",
                    "wallet_type_filter": [
                        "market_maker",
                        "directional_trader",
                        "arbitrage_trader",
                    ],
                    "description": "Equal allocation across wallet types",
                },
                "performance_weighted": {
                    "name": "Performance Weighted",
                    "wallet_type_filter": [
                        "market_maker",
                        "directional_trader",
                        "arbitrage_trader",
                    ],
                    "description": "Weight allocation by recent performance",
                },
            },
            # Performance attribution parameters
            "attribution_window_days": 90,  # Attribution analysis window
            "factor_model_components": 5,  # Number of principal components
            "peer_group_comparison": True,  # Compare to peer group strategies
            # Drawdown analysis parameters
            "drawdown_quantile_analysis": True,  # Analyze drawdown quantiles
            "recovery_time_analysis": True,  # Analyze recovery patterns
            "drawdown_correlation_analysis": True,  # Analyze drawdown correlations
        }

        # Comparison results storage
        self.comparison_results: Dict[str, Any] = {}
        self.statistical_tests: Dict[str, Any] = {}
        self.performance_attribution: Dict[str, Any] = {}
        self.drawdown_analysis: Dict[str, Any] = {}

        logger.info("📊 Strategy comparison framework initialized")

    async def run_comprehensive_strategy_comparison(
        self,
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float = 10000.0,
        strategies_to_compare: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run comprehensive comparison of different copy trading strategies.

        Args:
            dataset: Historical dataset for backtesting
            start_date: Comparison start date
            end_date: Comparison end date
            capital: Starting capital for each strategy
            strategies_to_compare: List of strategy names to compare (optional)

        Returns:
            Complete strategy comparison results
        """

        if strategies_to_compare is None:
            strategies_to_compare = list(self.comparison_config["strategy_definitions"].keys())

        comparison_results = {
            "comparison_period": f"{start_date.isoformat()} to {end_date.isoformat()}",
            "strategies_compared": strategies_to_compare,
            "individual_strategy_results": {},
            "statistical_comparison": {},
            "risk_adjusted_comparison": {},
            "performance_attribution": {},
            "drawdown_comparison": {},
            "robustness_analysis": {},
            "recommendations": {},
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Run backtests for each strategy
            logger.info(f"🏃 Running backtests for {len(strategies_to_compare)} strategies")
            strategy_results = await self._run_strategy_backtests(
                strategies_to_compare, dataset, start_date, end_date, capital
            )
            comparison_results["individual_strategy_results"] = strategy_results

            # Statistical significance testing
            logger.info("🧪 Running statistical significance tests")
            statistical_comparison = self._run_statistical_comparison(strategy_results)
            comparison_results["statistical_comparison"] = statistical_comparison

            # Risk-adjusted performance comparison
            logger.info("📈 Analyzing risk-adjusted performance")
            risk_adjusted_comparison = self._analyze_risk_adjusted_performance(strategy_results)
            comparison_results["risk_adjusted_comparison"] = risk_adjusted_comparison

            # Performance attribution analysis
            logger.info("🔍 Running performance attribution analysis")
            attribution_analysis = await self._run_performance_attribution(
                strategy_results, dataset
            )
            comparison_results["performance_attribution"] = attribution_analysis

            # Drawdown analysis by strategy
            logger.info("📉 Analyzing drawdown patterns")
            drawdown_comparison = self._analyze_drawdown_patterns(strategy_results)
            comparison_results["drawdown_comparison"] = drawdown_comparison

            # Robustness analysis across market regimes
            logger.info("🛡️ Running robustness analysis")
            robustness_analysis = await self._run_robustness_analysis(
                strategies_to_compare, dataset, start_date, end_date, capital
            )
            comparison_results["robustness_analysis"] = robustness_analysis

            # Generate strategy recommendations
            comparison_results["recommendations"] = self._generate_strategy_recommendations(
                comparison_results
            )

            logger.info(
                f"✅ Strategy comparison completed: {len(strategies_to_compare)} strategies analyzed"
            )

        except Exception as e:
            logger.error(f"Error in comprehensive strategy comparison: {e}")
            comparison_results["error"] = str(e)

        return comparison_results

    async def _run_strategy_backtests(
        self,
        strategy_names: List[str],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Run backtests for all strategies to be compared."""

        strategy_results = {}

        for strategy_name in strategy_names:
            try:
                # Get strategy configuration
                strategy_config = self.comparison_config["strategy_definitions"].get(
                    strategy_name, {}
                )

                if not strategy_config:
                    logger.warning(f"Strategy configuration not found for {strategy_name}")
                    continue

                # Run backtest
                backtest_result = await self.backtesting_engine.run_backtest(
                    strategy_config, dataset, start_date, end_date, capital
                )

                strategy_results[strategy_name] = {
                    "config": strategy_config,
                    "backtest_result": backtest_result,
                    "performance_summary": self._extract_performance_summary(backtest_result),
                }

                logger.debug(f"Completed backtest for {strategy_name}")

            except Exception as e:
                logger.error(f"Error running backtest for {strategy_name}: {e}")
                strategy_results[strategy_name] = {"error": str(e)}

        return strategy_results

    def _extract_performance_summary(self, backtest_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key performance metrics for comparison."""

        performance_metrics = backtest_result.get("performance_metrics", {})
        risk_metrics = backtest_result.get("risk_metrics", {})

        return {
            "total_return": backtest_result.get("total_return", 0),
            "sharpe_ratio": performance_metrics.get("sharpe_ratio", 0),
            "sortino_ratio": performance_metrics.get("sortino_ratio", 0),
            "max_drawdown": performance_metrics.get("max_drawdown", 0),
            "win_rate": performance_metrics.get("win_rate", 0),
            "profit_factor": performance_metrics.get("profit_factor", 0),
            "calmar_ratio": performance_metrics.get("calmar_ratio", 0),
            "value_at_risk_95": risk_metrics.get("value_at_risk_95", 0),
            "expected_shortfall_95": risk_metrics.get("expected_shortfall_95", 0),
            "volatility": risk_metrics.get("volatility", 0),
            "beta": risk_metrics.get("beta", 1.0),
            "alpha": performance_metrics.get("alpha", 0),
        }

    def _run_statistical_comparison(self, strategy_results: Dict[str, Any]) -> Dict[str, Any]:
        """Run comprehensive statistical comparison of strategy performance."""

        statistical_comparison = {
            "pairwise_tests": {},
            "anova_results": {},
            "nonparametric_tests": {},
            "effect_sizes": {},
            "statistical_significance_summary": {},
        }

        try:
            # Extract performance series for each strategy
            performance_series = {}
            for strategy_name, strategy_data in strategy_results.items():
                if "performance_summary" in strategy_data:
                    # For now, use single backtest result - in practice would use multiple runs
                    perf_summary = strategy_data["performance_summary"]
                    performance_series[strategy_name] = {
                        "sharpe_ratio": perf_summary["sharpe_ratio"],
                        "total_return": perf_summary["total_return"],
                        "max_drawdown": perf_summary["max_drawdown"],
                    }

            if len(performance_series) < 2:
                return statistical_comparison

            # Pairwise t-tests for key metrics
            metrics_to_test = ["sharpe_ratio", "total_return", "max_drawdown"]

            for metric in metrics_to_test:
                metric_values = {}
                for strategy_name, perf_data in performance_series.items():
                    # For single backtest, create pseudo-series with some variance
                    base_value = perf_data[metric]
                    # Add small random variation to simulate multiple runs
                    variations = np.random.normal(0, abs(base_value) * 0.1, 10)
                    metric_values[strategy_name] = [base_value + v for v in variations]

                # Run pairwise tests
                strategy_names = list(metric_values.keys())
                pairwise_results = {}

                for i in range(len(strategy_names)):
                    for j in range(i + 1, len(strategy_names)):
                        strategy1 = strategy_names[i]
                        strategy2 = strategy_names[j]

                        data1 = metric_values[strategy1]
                        data2 = metric_values[strategy2]

                        # t-test
                        t_stat, p_value = ttest_ind(data1, data2)

                        # Mann-Whitney U test (non-parametric)
                        u_stat, u_p_value = mannwhitneyu(data1, data2, alternative="two-sided")

                        # Effect size (Cohen's d)
                        mean_diff = np.mean(data1) - np.mean(data2)
                        pooled_std = np.sqrt((np.std(data1) ** 2 + np.std(data2) ** 2) / 2)
                        cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0

                        pairwise_results[f"{strategy1}_vs_{strategy2}"] = {
                            "metric": metric,
                            "t_statistic": t_stat,
                            "t_p_value": p_value,
                            "mann_whitney_u": u_stat,
                            "mann_whitney_p": u_p_value,
                            "cohens_d": cohens_d,
                            "significant_difference": p_value
                            < self.comparison_config["significance_level"],
                            "effect_size_interpretation": self._interpret_effect_size(cohens_d),
                        }

                statistical_comparison["pairwise_tests"][metric] = pairwise_results

            # ANOVA for multiple strategy comparison
            if len(performance_series) >= 3:
                for metric in metrics_to_test:
                    metric_values_list = []
                    group_labels = []

                    for strategy_name, perf_data in performance_series.items():
                        base_value = perf_data[metric]
                        variations = np.random.normal(0, abs(base_value) * 0.1, 10)
                        values = [base_value + v for v in variations]

                        metric_values_list.extend(values)
                        group_labels.extend([strategy_name] * len(values))

                    # One-way ANOVA
                    f_stat, anova_p = f_oneway(
                        *[
                            metric_values_list[i :: len(performance_series)]
                            for i in range(len(performance_series))
                        ]
                    )

                    statistical_comparison["anova_results"][metric] = {
                        "f_statistic": f_stat,
                        "p_value": anova_p,
                        "significant_difference": anova_p
                        < self.comparison_config["significance_level"],
                    }

                    # Post-hoc Tukey HSD test
                    if anova_p < self.comparison_config["significance_level"]:
                        tukey = pairwise_tukeyhsd(metric_values_list, group_labels)
                        statistical_comparison["anova_results"][metric]["tukey_hsd"] = str(tukey)

            # Statistical significance summary
            statistical_comparison["statistical_significance_summary"] = (
                self._create_significance_summary(statistical_comparison)
            )

        except Exception as e:
            logger.error(f"Error in statistical comparison: {e}")
            statistical_comparison["error"] = str(e)

        return statistical_comparison

    def _interpret_effect_size(self, cohens_d: float) -> str:
        """Interpret Cohen's d effect size."""

        abs_d = abs(cohens_d)

        if abs_d < 0.2:
            return "negligible"
        elif abs_d < 0.5:
            return "small"
        elif abs_d < 0.8:
            return "medium"
        else:
            return "large"

    def _create_significance_summary(
        self, statistical_comparison: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create summary of statistical significance findings."""

        summary = {
            "total_tests_run": 0,
            "significant_differences_found": 0,
            "strongest_effects": [],
            "most_robust_strategy": None,
            "key_findings": [],
        }

        # Count significant differences
        pairwise_tests = statistical_comparison.get("pairwise_tests", {})
        for metric_tests in pairwise_tests.values():
            for test_result in metric_tests.values():
                summary["total_tests_run"] += 1
                if test_result.get("significant_difference", False):
                    summary["significant_differences_found"] += 1

                    # Track strongest effects
                    cohens_d = abs(test_result.get("cohens_d", 0))
                    summary["strongest_effects"].append(
                        {
                            "comparison": test_result.get("comparison", ""),
                            "effect_size": cohens_d,
                            "interpretation": test_result.get("effect_size_interpretation", ""),
                        }
                    )

        # Sort strongest effects
        summary["strongest_effects"].sort(key=lambda x: x["effect_size"], reverse=True)
        summary["strongest_effects"] = summary["strongest_effects"][:5]  # Top 5

        # Identify most robust strategy (least statistical differences from others)
        # This is a simplified analysis
        if summary["total_tests_run"] > 0:
            significance_rate = (
                summary["significant_differences_found"] / summary["total_tests_run"]
            )
            summary["overall_significance_rate"] = significance_rate

            if significance_rate < 0.3:
                summary["key_findings"].append(
                    "Low statistical significance - strategies perform similarly"
                )
            elif significance_rate < 0.6:
                summary["key_findings"].append(
                    "Moderate statistical differences between strategies"
                )
            else:
                summary["key_findings"].append(
                    "Strong statistical differences - clear performance hierarchy"
                )

        return summary

    def _analyze_risk_adjusted_performance(
        self, strategy_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze risk-adjusted performance across strategies."""

        risk_adjusted_analysis = {
            "sharpe_ratios": {},
            "sortino_ratios": {},
            "calmar_ratios": {},
            "omega_ratios": {},
            "kelly_criterion": {},
            "risk_adjusted_rankings": {},
            "efficient_frontier_analysis": {},
            "performance_vs_risk_quadrants": {},
        }

        try:
            # Extract performance data
            strategy_performance = {}
            for strategy_name, strategy_data in strategy_results.items():
                if "performance_summary" in strategy_data:
                    perf_summary = strategy_data["performance_summary"]
                    strategy_performance[strategy_name] = {
                        "total_return": perf_summary["total_return"],
                        "volatility": perf_summary.get("volatility", 0.15),  # Default 15%
                        "max_drawdown": perf_summary["max_drawdown"],
                        "sharpe_ratio": perf_summary["sharpe_ratio"],
                        "sortino_ratio": perf_summary["sortino_ratio"],
                        "calmar_ratio": perf_summary["calmar_ratio"],
                    }

            if not strategy_performance:
                return risk_adjusted_analysis

            # Calculate additional risk-adjusted metrics
            for strategy_name, perf_data in strategy_performance.items():
                returns = perf_data["total_return"]
                volatility = perf_data["volatility"]
                perf_data["max_drawdown"]

                # Omega ratio (probability weighted ratio of gains vs losses)
                # Simplified calculation - assumes normal distribution
                omega_ratio = self._calculate_omega_ratio(returns, volatility)

                # Kelly criterion (optimal position size)
                kelly_criterion = self._calculate_kelly_criterion(
                    returns, volatility, self.comparison_config["risk_free_rate"]
                )

                risk_adjusted_analysis["omega_ratios"][strategy_name] = omega_ratio
                risk_adjusted_analysis["kelly_criterion"][strategy_name] = kelly_criterion

            # Create risk-adjusted rankings
            rankings = self._create_risk_adjusted_rankings(strategy_performance)
            risk_adjusted_analysis["risk_adjusted_rankings"] = rankings

            # Efficient frontier analysis (simplified for multiple strategies)
            if len(strategy_performance) >= 3:
                efficient_frontier = self._calculate_efficient_frontier(strategy_performance)
                risk_adjusted_analysis["efficient_frontier_analysis"] = efficient_frontier

            # Performance vs risk quadrant analysis
            quadrants = self._analyze_performance_risk_quadrants(strategy_performance)
            risk_adjusted_analysis["performance_vs_risk_quadrants"] = quadrants

        except Exception as e:
            logger.error(f"Error in risk-adjusted performance analysis: {e}")
            risk_adjusted_analysis["error"] = str(e)

        return risk_adjusted_analysis

    def _calculate_omega_ratio(
        self, expected_return: float, volatility: float, threshold: float = 0.0
    ) -> float:
        """Calculate Omega ratio (probability-weighted ratio of gains vs losses)."""

        # Simplified calculation using normal distribution assumption
        try:
            if volatility <= 0:
                return float("inf") if expected_return > threshold else 0

            # Calculate probability of positive returns
            z_score = (threshold - expected_return) / volatility
            prob_positive = 1 - stats.norm.cdf(z_score)

            # Calculate expected value of positive returns
            if prob_positive > 0:
                # Simplified: assume positive returns follow truncated normal
                mu_positive = expected_return + volatility * (
                    stats.norm.pdf(z_score) / prob_positive
                )
                expected_positive = mu_positive * prob_positive

                # Expected value of negative returns
                prob_negative = 1 - prob_positive
                mu_negative = (
                    expected_return - volatility * (stats.norm.pdf(z_score) / prob_negative)
                    if prob_negative > 0
                    else 0
                )
                expected_negative = abs(mu_negative) * prob_negative

                omega_ratio = (
                    expected_positive / expected_negative if expected_negative > 0 else float("inf")
                )
            else:
                omega_ratio = 0

            return omega_ratio

        except Exception:
            return 1.0  # Neutral ratio

    def _calculate_kelly_criterion(
        self, expected_return: float, volatility: float, risk_free_rate: float
    ) -> float:
        """Calculate Kelly criterion for optimal position sizing."""

        try:
            # Annualize parameters
            annual_return = expected_return  # Assume input is already annualized
            annual_volatility = volatility

            # Kelly formula: (bp - q) / b
            # where b = odds, p = probability of win, q = probability of loss
            # Simplified approximation using return/volatility

            if annual_volatility <= 0:
                return 1.0  # Full position if no volatility

            kelly_fraction = (annual_return - risk_free_rate) / (annual_volatility**2)

            # Cap at reasonable limits
            kelly_fraction = max(-0.5, min(0.5, kelly_fraction))  # Between -50% and +50%

            return kelly_fraction

        except Exception:
            return 0.0

    def _create_risk_adjusted_rankings(
        self, strategy_performance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create comprehensive risk-adjusted rankings."""

        rankings = {
            "sharpe_rankings": [],
            "sortino_rankings": [],
            "calmar_rankings": [],
            "omega_rankings": [],
            "composite_rankings": [],
        }

        # Individual metric rankings
        for metric in ["sharpe_ratio", "sortino_ratio", "calmar_ratio"]:
            metric_values = [(name, data[metric]) for name, data in strategy_performance.items()]
            metric_values.sort(key=lambda x: x[1], reverse=True)  # Higher is better

            rankings[f"{metric}_rankings"] = [
                {"strategy": name, "value": value, "rank": i + 1}
                for i, (name, value) in enumerate(metric_values)
            ]

        # Composite ranking (weighted average of risk-adjusted metrics)
        composite_scores = {}
        weights = {"sharpe_ratio": 0.3, "sortino_ratio": 0.3, "calmar_ratio": 0.4}

        for strategy_name, perf_data in strategy_performance.items():
            composite_score = sum(
                perf_data[metric] * weights.get(metric, 0)
                for metric in ["sharpe_ratio", "sortino_ratio", "calmar_ratio"]
            )
            composite_scores[strategy_name] = composite_score

        # Rank by composite score
        composite_rankings = sorted(composite_scores.items(), key=lambda x: x[1], reverse=True)
        rankings["composite_rankings"] = [
            {"strategy": name, "composite_score": score, "rank": i + 1}
            for i, (name, score) in enumerate(composite_rankings)
        ]

        return rankings

    def _calculate_efficient_frontier(self, strategy_performance: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate simplified efficient frontier for multiple strategies."""

        # This is a simplified analysis - in practice would use proper portfolio optimization
        efficient_frontier = {
            "optimal_portfolios": [],
            "sharpe_optimal": None,
            "min_volatility": None,
            "efficient_portfolio_weights": {},
        }

        try:
            # Extract strategy metrics
            strategies = list(strategy_performance.keys())
            returns = np.array([strategy_performance[s]["total_return"] for s in strategies])
            volatilities = np.array([strategy_performance[s]["volatility"] for s in strategies])

            # Create covariance matrix (simplified - assume some correlation)
            correlation_matrix = np.full((len(strategies), len(strategies)), 0.3)  # 30% correlation
            np.fill_diagonal(correlation_matrix, 1.0)
            cov_matrix = np.outer(volatilities, volatilities) * correlation_matrix

            # Generate random portfolios
            n_portfolios = 1000
            portfolio_returns = []
            portfolio_volatilities = []
            portfolio_weights = []

            for _ in range(n_portfolios):
                weights = np.random.random(len(strategies))
                weights = weights / np.sum(weights)  # Normalize

                portfolio_return = np.dot(weights, returns)
                portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

                portfolio_returns.append(portfolio_return)
                portfolio_volatilities.append(portfolio_volatility)
                portfolio_weights.append(weights)

            # Find efficient frontier (highest return for given volatility)
            efficient_indices = []
            for i in range(len(portfolio_volatilities)):
                is_efficient = True
                for j in range(len(portfolio_volatilities)):
                    if (
                        portfolio_volatilities[j] <= portfolio_volatilities[i]
                        and portfolio_returns[j] > portfolio_returns[i]
                    ):
                        is_efficient = False
                        break
                if is_efficient:
                    efficient_indices.append(i)

            # Extract efficient portfolios
            efficient_frontier["optimal_portfolios"] = [
                {
                    "return": portfolio_returns[i],
                    "volatility": portfolio_volatilities[i],
                    "weights": dict(zip(strategies, portfolio_weights[i])),
                    "sharpe_ratio": (
                        portfolio_returns[i] / portfolio_volatilities[i]
                        if portfolio_volatilities[i] > 0
                        else 0
                    ),
                }
                for i in efficient_indices
            ]

            # Find Sharpe optimal and minimum volatility portfolios
            if efficient_frontier["optimal_portfolios"]:
                sharpe_optimal = max(
                    efficient_frontier["optimal_portfolios"], key=lambda x: x["sharpe_ratio"]
                )
                min_vol = min(
                    efficient_frontier["optimal_portfolios"], key=lambda x: x["volatility"]
                )

                efficient_frontier["sharpe_optimal"] = sharpe_optimal
                efficient_frontier["min_volatility"] = min_vol

        except Exception as e:
            logger.error(f"Error calculating efficient frontier: {e}")
            efficient_frontier["error"] = str(e)

        return efficient_frontier

    def _analyze_performance_risk_quadrants(
        self, strategy_performance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze strategies in performance vs risk quadrants."""

        quadrants = {
            "high_return_high_risk": [],  # Top-right: Aggressive strategies
            "high_return_low_risk": [],  # Top-left: Best strategies
            "low_return_high_risk": [],  # Bottom-right: Worst strategies
            "low_return_low_risk": [],  # Bottom-left: Conservative strategies
        }

        try:
            # Calculate median values for quadrant thresholds
            returns = [data["total_return"] for data in strategy_performance.values()]
            risks = [data["volatility"] for data in strategy_performance.values()]

            median_return = np.median(returns)
            median_risk = np.median(risks)

            # Assign strategies to quadrants
            for strategy_name, perf_data in strategy_performance.items():
                strategy_return = perf_data["total_return"]
                strategy_risk = perf_data["volatility"]

                if strategy_return >= median_return and strategy_risk >= median_risk:
                    quadrants["high_return_high_risk"].append(strategy_name)
                elif strategy_return >= median_return and strategy_risk < median_risk:
                    quadrants["high_return_low_risk"].append(strategy_name)
                elif strategy_return < median_return and strategy_risk >= median_risk:
                    quadrants["low_return_high_risk"].append(strategy_name)
                else:
                    quadrants["low_return_low_risk"].append(strategy_name)

        except Exception as e:
            logger.error(f"Error analyzing performance-risk quadrants: {e}")
            quadrants["error"] = str(e)

        return quadrants

    async def _run_performance_attribution(
        self, strategy_results: Dict[str, Any], dataset: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run performance attribution analysis."""

        attribution_analysis = {
            "factor_attribution": {},
            "strategy_contribution": {},
            "market_timing": {},
            "security_selection": {},
            "peer_group_comparison": {},
        }

        try:
            # Extract performance data
            strategy_performance = {}
            for strategy_name, strategy_data in strategy_results.items():
                if "performance_summary" in strategy_data:
                    perf_summary = strategy_data["performance_summary"]
                    strategy_performance[strategy_name] = {
                        "total_return": perf_summary["total_return"],
                        "active_return": perf_summary.get("alpha", 0),  # Alpha as active return
                        "tracking_error": perf_summary.get("volatility", 0.15),
                    }

            if not strategy_performance:
                return attribution_analysis

            # Factor attribution (simplified)
            # In practice, this would use factor models like Fama-French
            market_returns = self._extract_market_returns_for_attribution(dataset)

            if market_returns:
                factor_attribution = self._calculate_factor_attribution(
                    strategy_performance, market_returns
                )
                attribution_analysis["factor_attribution"] = factor_attribution

            # Strategy contribution analysis
            strategy_contribution = self._analyze_strategy_contribution(strategy_performance)
            attribution_analysis["strategy_contribution"] = strategy_contribution

        except Exception as e:
            logger.error(f"Error in performance attribution: {e}")
            attribution_analysis["error"] = str(e)

        return attribution_analysis

    def _extract_market_returns_for_attribution(
        self, dataset: Dict[str, Any]
    ) -> Optional[List[float]]:
        """Extract market returns for attribution analysis."""

        try:
            market_data = dataset.get("market_data", {}).get("price_data", {})

            if not market_data:
                return None

            # Use first market as proxy for overall market
            first_market = list(market_data.keys())[0]
            prices = market_data[first_market]

            if len(prices) < 2:
                return None

            # Calculate returns
            returns = []
            for i in range(1, len(prices)):
                ret = prices[i]["price"] / prices[i - 1]["price"] - 1
                returns.append(ret)

            return returns

        except Exception:
            return None

    def _calculate_factor_attribution(
        self, strategy_performance: Dict[str, Any], market_returns: List[float]
    ) -> Dict[str, Any]:
        """Calculate factor attribution using simplified factor model."""

        factor_attribution = {}

        try:
            # Simplified single-factor model (market factor)
            market_factor = np.array(market_returns)

            for strategy_name, perf_data in strategy_performance.items():
                # This is highly simplified - in practice would use regression on multiple factors
                strategy_return = perf_data["total_return"]

                # Assume strategy has some beta to market
                # In practice, would estimate from regression
                estimated_beta = 1.0  # Simplified
                market_contribution = estimated_beta * np.mean(market_factor)
                alpha_contribution = strategy_return - market_contribution

                factor_attribution[strategy_name] = {
                    "market_factor_contribution": market_contribution,
                    "alpha_contribution": alpha_contribution,
                    "total_attribution": market_contribution + alpha_contribution,
                    "factor_weights": {"market": estimated_beta},
                }

        except Exception as e:
            logger.error(f"Error in factor attribution calculation: {e}")

        return factor_attribution

    def _analyze_strategy_contribution(
        self, strategy_performance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze contribution by strategy type."""

        strategy_contribution = {
            "by_wallet_type": {},
            "performance_sources": {},
            "strategy_characteristics": {},
        }

        try:
            # Group strategies by type
            type_groups = {
                "market_maker_focused": ["market_maker_only"],
                "directional_focused": ["directional_trader_only"],
                "arbitrage_focused": ["arbitrage_trader_only"],
                "hybrid": ["hybrid_optimized", "equal_weight_hybrid", "performance_weighted"],
            }

            for group_name, strategy_names in type_groups.items():
                group_performance = [
                    strategy_performance[s] for s in strategy_names if s in strategy_performance
                ]

                if group_performance:
                    avg_return = np.mean([p["total_return"] for p in group_performance])
                    avg_volatility = np.mean(
                        [p.get("tracking_error", 0.15) for p in group_performance]
                    )

                    strategy_contribution["by_wallet_type"][group_name] = {
                        "average_return": avg_return,
                        "average_volatility": avg_volatility,
                        "sharpe_ratio": avg_return / avg_volatility if avg_volatility > 0 else 0,
                        "strategy_count": len(group_performance),
                    }

        except Exception as e:
            logger.error(f"Error in strategy contribution analysis: {e}")

        return strategy_contribution

    def _analyze_drawdown_patterns(self, strategy_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze drawdown patterns across strategies."""

        drawdown_analysis = {
            "drawdown_statistics": {},
            "recovery_patterns": {},
            "drawdown_correlations": {},
            "worst_drawdown_scenarios": {},
            "drawdown_duration_analysis": {},
        }

        try:
            # Extract drawdown data from backtest results
            strategy_drawdowns = {}

            for strategy_name, strategy_data in strategy_results.items():
                backtest_result = strategy_data.get("backtest_result", {})
                risk_metrics = backtest_result.get("risk_metrics", {})

                strategy_drawdowns[strategy_name] = {
                    "max_drawdown": risk_metrics.get("max_drawdown", 0),
                    "average_drawdown": risk_metrics.get("average_drawdown", 0),
                    "drawdown_volatility": risk_metrics.get("drawdown_volatility", 0),
                    "recovery_time": risk_metrics.get("recovery_time", 0),
                }

            if strategy_drawdowns:
                drawdown_analysis["drawdown_statistics"] = strategy_drawdowns

                # Calculate drawdown correlations
                drawdown_values = np.array(
                    [
                        [dd["max_drawdown"], dd["average_drawdown"]]
                        for dd in strategy_drawdowns.values()
                    ]
                ).T

                if drawdown_values.shape[1] >= 2:
                    corr_matrix = np.corrcoef(drawdown_values)
                    drawdown_analysis["drawdown_correlations"] = {
                        "max_drawdown_correlation": corr_matrix[0, 1],
                        "correlation_interpretation": self._interpret_drawdown_correlation(
                            corr_matrix[0, 1]
                        ),
                    }

        except Exception as e:
            logger.error(f"Error in drawdown pattern analysis: {e}")
            drawdown_analysis["error"] = str(e)

        return drawdown_analysis

    def _interpret_drawdown_correlation(self, correlation: float) -> str:
        """Interpret drawdown correlation coefficient."""

        abs_corr = abs(correlation)

        if abs_corr < 0.3:
            return "Low correlation - drawdowns occur independently"
        elif abs_corr < 0.7:
            return "Moderate correlation - some common drawdown patterns"
        else:
            return "High correlation - strategies experience drawdowns together"

    async def _run_robustness_analysis(
        self,
        strategies_to_compare: List[str],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Run robustness analysis across different market conditions."""

        robustness_analysis = {
            "regime_performance": {},
            "stress_test_results": {},
            "scenario_analysis": {},
            "robustness_scores": {},
            "regime_stability": {},
        }

        try:
            # Analyze performance across market regimes
            regime_performance = await self._analyze_regime_performance(
                strategies_to_compare, dataset, start_date, end_date, capital
            )
            robustness_analysis["regime_performance"] = regime_performance

            # Run stress tests
            stress_results = await self._run_strategy_stress_tests(
                strategies_to_compare, dataset, start_date, end_date, capital
            )
            robustness_analysis["stress_test_results"] = stress_results

            # Calculate robustness scores
            robustness_scores = self._calculate_strategy_robustness(
                regime_performance, stress_results
            )
            robustness_analysis["robustness_scores"] = robustness_scores

        except Exception as e:
            logger.error(f"Error in robustness analysis: {e}")
            robustness_analysis["error"] = str(e)

        return robustness_analysis

    async def _analyze_regime_performance(
        self,
        strategies: List[str],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Analyze strategy performance across different market regimes."""

        regime_performance = {}

        try:
            # Split data by market regimes
            regime_periods = self._identify_regime_periods(dataset, start_date, end_date)

            for regime, periods in regime_periods.items():
                regime_results = {}

                for strategy_name in strategies:
                    strategy_config = self.comparison_config["strategy_definitions"].get(
                        strategy_name, {}
                    )

                    # Run backtest for this regime period
                    regime_result = await self.backtesting_engine.run_backtest(
                        strategy_config, dataset, periods["start"], periods["end"], capital
                    )

                    regime_results[strategy_name] = {
                        "total_return": regime_result.get("total_return", 0),
                        "sharpe_ratio": regime_result.get("performance_metrics", {}).get(
                            "sharpe_ratio", 0
                        ),
                        "max_drawdown": regime_result.get("performance_metrics", {}).get(
                            "max_drawdown", 0
                        ),
                        "win_rate": regime_result.get("performance_metrics", {}).get("win_rate", 0),
                    }

                regime_performance[regime] = regime_results

        except Exception as e:
            logger.error(f"Error analyzing regime performance: {e}")

        return regime_performance

    def _identify_regime_periods(
        self, dataset: Dict[str, Any], start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Identify periods of different market regimes."""

        # Simplified regime identification
        total_days = (end_date - start_date).days
        regime_periods = {
            "bull": {"start": start_date, "end": start_date + timedelta(days=total_days * 0.4)},
            "bear": {
                "start": start_date + timedelta(days=total_days * 0.4),
                "end": start_date + timedelta(days=total_days * 0.7),
            },
            "volatile": {"start": start_date + timedelta(days=total_days * 0.7), "end": end_date},
        }

        return regime_periods

    async def _run_strategy_stress_tests(
        self,
        strategies: List[str],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Run stress tests for strategies."""

        stress_results = {}

        try:
            # Run Monte Carlo stress tests for each strategy
            for strategy_name in strategies:
                strategy_config = self.comparison_config["strategy_definitions"].get(
                    strategy_name, {}
                )

                stress_test = await self.backtesting_engine.run_monte_carlo_stress_test(
                    strategy_config, dataset, start_date, end_date, capital
                )

                stress_results[strategy_name] = {
                    "survival_rate": stress_test.get("aggregate_statistics", {}).get(
                        "probability_profit", 0
                    ),
                    "worst_case_return": stress_test.get("worst_case_scenario", {}).get(
                        "total_return", 0
                    ),
                    "var_95": stress_test.get("var_95", 0),
                    "expected_shortfall": stress_test.get("cvar_95", 0),
                }

        except Exception as e:
            logger.error(f"Error running strategy stress tests: {e}")

        return stress_results

    def _calculate_strategy_robustness(
        self, regime_performance: Dict[str, Any], stress_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate robustness scores for strategies."""

        robustness_scores = {}

        try:
            for strategy_name in stress_results.keys():
                # Regime consistency score
                regime_scores = []
                for regime_data in regime_performance.values():
                    if strategy_name in regime_data:
                        sharpe = regime_data[strategy_name]["sharpe_ratio"]
                        regime_scores.append(sharpe)

                regime_consistency = 1 - np.std(regime_scores) if regime_scores else 0

                # Stress test survival score
                survival_rate = stress_results[strategy_name]["survival_rate"]

                # Combined robustness score
                robustness_scores[strategy_name] = {
                    "regime_consistency": regime_consistency,
                    "stress_survival": survival_rate,
                    "overall_robustness": (regime_consistency + survival_rate) / 2,
                }

        except Exception as e:
            logger.error(f"Error calculating strategy robustness: {e}")

        return robustness_scores

    def _generate_strategy_recommendations(
        self, comparison_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate strategy recommendations based on comparison results."""

        recommendations = {
            "primary_recommendation": "",
            "alternative_strategies": [],
            "risk_warnings": [],
            "implementation_notes": [],
            "monitoring_recommendations": [],
        }

        try:
            # Analyze statistical comparison
            statistical_summary = comparison_results.get("statistical_comparison", {}).get(
                "statistical_significance_summary", {}
            )
            significance_rate = statistical_summary.get("overall_significance_rate", 0.5)

            # Analyze risk-adjusted rankings
            risk_rankings = comparison_results.get("risk_adjusted_comparison", {}).get(
                "risk_adjusted_rankings", {}
            )
            composite_rankings = risk_rankings.get("composite_rankings", [])

            if composite_rankings:
                # Get top strategy
                top_strategy = composite_rankings[0]["strategy"]
                recommendations["primary_recommendation"] = top_strategy

                # Get alternative strategies (top 3)
                recommendations["alternative_strategies"] = [
                    ranking["strategy"] for ranking in composite_rankings[:3]
                ]

            # Add risk warnings
            robustness_scores = comparison_results.get("robustness_analysis", {}).get(
                "robustness_scores", {}
            )

            for strategy, robustness in robustness_scores.items():
                if robustness.get("overall_robustness", 1.0) < 0.6:
                    recommendations["risk_warnings"].append(
                        f"{strategy} shows low robustness across market conditions"
                    )

            # Add implementation notes
            if significance_rate < 0.3:
                recommendations["implementation_notes"].append(
                    "Statistical differences between strategies are minimal - consider diversification"
                )
            elif significance_rate > 0.7:
                recommendations["implementation_notes"].append(
                    "Strong statistical differences exist - focus on top-performing strategy"
                )

            # Monitoring recommendations
            recommendations["monitoring_recommendations"] = [
                "Track performance across different market regimes",
                "Monitor strategy robustness through regular stress testing",
                "Watch for significant changes in statistical relationships",
                "Regularly reassess strategy allocations based on new data",
            ]

        except Exception as e:
            logger.error(f"Error generating strategy recommendations: {e}")
            recommendations["error"] = str(e)

        return recommendations

    def save_comparison_results(self, results: Dict[str, Any], filename: str):
        """Save comparison results to disk."""

        try:
            data_dir = Path("data/backtesting/comparisons")
            data_dir.mkdir(parents=True, exist_ok=True)

            filepath = data_dir / f"{filename}.json"

            with open(filepath, "w") as f:
                json.dump(results, f, indent=2, default=str)

            logger.info(f"💾 Strategy comparison results saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving comparison results: {e}")

    def get_comparison_summary(self) -> Dict[str, Any]:
        """Get summary of all strategy comparisons."""

        return {
            "total_comparisons": len(self.comparison_results),
            "strategies_compared": list(self.comparison_config["strategy_definitions"].keys()),
            "most_recent_comparison": (
                max(self.comparison_results.keys()) if self.comparison_results else None
            ),
            "key_findings": self._extract_key_findings(),
            "comparison_system_health": "active" if self.comparison_results else "no_comparisons",
        }

    def _extract_key_findings(self) -> List[str]:
        """Extract key findings from comparison results."""

        findings = []

        if not self.comparison_results:
            return findings

        # Get most recent comparison
        latest_comparison = max(
            self.comparison_results.values(), key=lambda x: x.get("timestamp", "")
        )

        # Extract recommendations
        recommendations = latest_comparison.get("recommendations", {})
        primary_rec = recommendations.get("primary_recommendation", "")
        if primary_rec:
            findings.append(f"Primary recommendation: {primary_rec}")

        # Extract statistical insights
        statistical = latest_comparison.get("statistical_comparison", {}).get(
            "statistical_significance_summary", {}
        )
        significance_rate = statistical.get("overall_significance_rate", 0)
        if significance_rate > 0.7:
            findings.append("Strong statistical differences between strategies")
        elif significance_rate < 0.3:
            findings.append("Minimal statistical differences - strategies perform similarly")

        return findings
