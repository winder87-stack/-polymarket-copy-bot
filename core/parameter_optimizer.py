"""
Parameter Optimization Framework
===============================

Advanced optimization system for copy trading strategy parameters using
multiple algorithms: grid search, genetic algorithms, Bayesian optimization,
with comprehensive validation and stability analysis.

Features:
- Grid search for parameter space exploration
- Genetic algorithm optimization for complex parameter interactions
- Bayesian optimization for efficient hyperparameter tuning
- Out-of-sample validation to prevent overfitting
- Parameter stability analysis across time periods
- Optimization report generation with statistical validation
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern

logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """
    Comprehensive parameter optimization framework for copy trading strategies.

    Supports multiple optimization algorithms with rigorous validation
    and stability analysis to ensure robust parameter selection.
    """

    def __init__(self, backtesting_engine) -> None:
        self.backtesting_engine = backtesting_engine

        # Optimization configuration
        self.optimization_config = {
            # Grid search parameters
            "grid_search_points": 100,  # Maximum grid points to evaluate
            "grid_search_parallel": 4,  # Parallel grid evaluations
            # Genetic algorithm parameters
            "population_size": 50,  # GA population size
            "generations": 30,  # GA generations
            "mutation_rate": 0.1,  # GA mutation rate
            "crossover_rate": 0.8,  # GA crossover rate
            "elitism_rate": 0.1,  # GA elitism rate
            # Bayesian optimization parameters
            "bayesian_iterations": 50,  # BO iterations
            "bayesian_exploration_weight": 0.1,  # BO exploration vs exploitation
            "bayesian_kernel": "matern",  # BO kernel function
            # Validation parameters
            "cv_folds": 5,  # Cross-validation folds
            "validation_window_days": 30,  # Validation window size
            "out_of_sample_ratio": 0.3,  # Out-of-sample data ratio
            "walk_forward_steps": 6,  # Walk-forward validation steps
            # Stability analysis parameters
            "stability_windows": 10,  # Number of stability windows
            "stability_threshold": 0.15,  # Parameter stability threshold
            "parameter_sensitivity_threshold": 0.1,  # Sensitivity threshold
            # Performance metrics
            "optimization_target": "sharpe_ratio",  # Primary optimization target
            "secondary_metrics": ["total_return", "max_drawdown", "win_rate"],
            "risk_adjustment": True,  # Apply risk adjustment to optimization
            # Computational limits
            "max_evaluations": 500,  # Maximum function evaluations
            "time_limit_seconds": 3600,  # Time limit per optimization
            "convergence_tolerance": 1e-4,  # Optimization convergence tolerance
        }

        # Parameter definitions for different strategies
        self.parameter_definitions = {
            "wallet_quality_scorer": {
                "min_quality_score": {"min": 30, "max": 80, "type": "int"},
                "max_wallet_allocation": {"min": 0.05, "max": 0.25, "type": "float"},
                "rebalance_frequency_hours": {"min": 6, "max": 72, "type": "int"},
                "rotation_threshold": {"min": 0.05, "max": 0.30, "type": "float"},
                "diversification_clusters": {"min": 3, "max": 8, "type": "int"},
            },
            "adaptive_strategy_engine": {
                "strategy_switch_threshold": {
                    "min": 0.05,
                    "max": 0.25,
                    "type": "float",
                },
                "hysteresis_band": {"min": 0.01, "max": 0.10, "type": "float"},
                "performance_window_days": {"min": 3, "max": 14, "type": "int"},
                "min_confidence_threshold": {"min": 0.4, "max": 0.8, "type": "float"},
            },
            "market_maker_tactics": {
                "min_spread_capture_pct": {"min": 0.01, "max": 0.10, "type": "float"},
                "inventory_rebalance_threshold": {
                    "min": 0.1,
                    "max": 0.4,
                    "type": "float",
                },
                "gas_efficiency_threshold": {"min": 0.5, "max": 0.9, "type": "float"},
            },
        }

        # Optimization results storage
        self.optimization_results: Dict[str, Any] = {}
        self.parameter_stability: Dict[str, Any] = {}
        self.validation_results: Dict[str, Any] = {}

        logger.info("🔬 Parameter optimization framework initialized")

    async def optimize_strategy_parameters(
        self,
        strategy_name: str,
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float = 10000.0,
        optimization_method: str = "bayesian",
        parameter_space: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Optimize parameters for a specific strategy using chosen optimization method.

        Args:
            strategy_name: Name of the strategy to optimize
            dataset: Historical dataset for optimization
            start_date: Optimization start date
            end_date: Optimization end date
            capital: Starting capital
            optimization_method: Optimization method ("grid", "genetic", "bayesian")
            parameter_space: Custom parameter space (optional)

        Returns:
            Complete optimization results with validation
        """

        optimization_result: Dict[str, Any] = {
            "strategy_name": strategy_name,
            "optimization_method": optimization_method,
            "parameter_space": parameter_space
            or self.parameter_definitions.get(strategy_name, {}),
            "optimal_parameters": {},
            "optimization_path": [],
            "validation_results": {},
            "stability_analysis": {},
            "performance_summary": {},
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Get parameter space
            param_space = parameter_space or self.parameter_definitions.get(
                strategy_name, {}
            )

            if not param_space:
                optimization_result["error"] = (
                    f"No parameter space defined for strategy {strategy_name}"
                )
                return optimization_result

            # Run optimization based on method
            if optimization_method == "grid":
                (
                    optimal_params,
                    optimization_path,
                ) = await self._grid_search_optimization(
                    strategy_name, param_space, dataset, start_date, end_date, capital
                )
            elif optimization_method == "genetic":
                (
                    optimal_params,
                    optimization_path,
                ) = await self._genetic_algorithm_optimization(
                    strategy_name, param_space, dataset, start_date, end_date, capital
                )
            elif optimization_method == "bayesian":
                optimal_params, optimization_path = await self._bayesian_optimization(
                    strategy_name, param_space, dataset, start_date, end_date, capital
                )
            else:
                optimization_result["error"] = (
                    f"Unknown optimization method: {optimization_method}"
                )
                return optimization_result

            optimization_result["optimal_parameters"] = optimal_params
            optimization_result["optimization_path"] = optimization_path

            # Validate optimal parameters
            validation_results = await self._validate_optimal_parameters(
                strategy_name, optimal_params, dataset, start_date, end_date, capital
            )
            optimization_result["validation_results"] = validation_results

            # Analyze parameter stability
            stability_analysis = await self._analyze_parameter_stability(
                strategy_name, optimal_params, dataset, start_date, end_date
            )
            optimization_result["stability_analysis"] = stability_analysis

            # Generate performance summary
            performance_summary = self._generate_optimization_performance_summary(
                optimal_params, validation_results, stability_analysis
            )
            optimization_result["performance_summary"] = performance_summary

            # Store results
            self._store_optimization_results(strategy_name, optimization_result)

            logger.info(
                f"✅ Parameter optimization completed for {strategy_name} using {optimization_method}"
            )

        except Exception as e:
            logger.error(f"Error in parameter optimization for {strategy_name}: {e}")
            optimization_result["error"] = str(e)

        return optimization_result

    async def _grid_search_optimization(
        self,
        strategy_name: str,
        param_space: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Perform grid search optimization."""

        # Generate parameter grid
        param_grid = self._generate_parameter_grid(param_space)
        logger.info(f"Grid search: evaluating {len(param_grid)} parameter combinations")

        # Evaluate each parameter combination
        best_score = float("-inf")
        best_params = {}
        optimization_path = []

        for i, params in enumerate(param_grid):
            try:
                # Evaluate parameter combination
                evaluation_result = await self._evaluate_parameter_combination(
                    strategy_name, params, dataset, start_date, end_date, capital
                )

                score = evaluation_result["score"]
                optimization_path.append(
                    {
                        "iteration": i + 1,
                        "parameters": params,
                        "score": score,
                        "metrics": evaluation_result["metrics"],
                    }
                )

                if score > best_score:
                    best_score = score
                    best_params = params

                # Progress logging
                if (i + 1) % 10 == 0:
                    logger.debug(
                        f"Grid search progress: {i + 1}/{len(param_grid)} combinations evaluated"
                    )

            except Exception as e:
                logger.error(f"Error evaluating parameter combination {i}: {e}")
                continue

        return best_params, optimization_path

    def _generate_parameter_grid(
        self, param_space: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate parameter grid for grid search."""

        # Simplified grid generation - in practice would use more sophisticated sampling
        grid_points = []

        # For demonstration, generate a smaller grid
        n_points_per_param = min(
            5,
            max(
                1,
                int(
                    float(self.optimization_config["grid_search_points"])
                    ** (1 / len(param_space))
                ),
            ),
        )

        # Generate parameter values
        param_values = {}
        for param_name, param_def in param_space.items():
            param_min = param_def["min"]
            param_max = param_def["max"]
            param_type = param_def["type"]

            if param_type == "int":
                values = np.linspace(
                    param_min, param_max, n_points_per_param, dtype=int
                )
            else:
                values = np.linspace(param_min, param_max, n_points_per_param)

            param_values[param_name] = values

        # Generate all combinations (simplified - using meshgrid for small grids)
        if len(param_space) == 1:
            param_name = list(param_space.keys())[0]
            for value in param_values[param_name]:
                grid_points.append({param_name: value})
        elif len(param_space) == 2:
            param_names = list(param_space.keys())
            values1 = param_values[param_names[0]]
            values2 = param_values[param_names[1]]

            for v1 in values1:
                for v2 in values2:
                    grid_points.append({param_names[0]: v1, param_names[1]: v2})
        else:
            # For larger parameter spaces, use random sampling
            n_samples = min(self.optimization_config["grid_search_points"], 100)
            for _ in range(n_samples):
                sample = {}
                for param_name, values in param_values.items():
                    sample[param_name] = np.random.choice(values)
                grid_points.append(sample)

        return grid_points

    async def _genetic_algorithm_optimization(
        self,
        strategy_name: str,
        param_space: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Perform genetic algorithm optimization."""

        population_size = self.optimization_config["population_size"]
        generations = self.optimization_config["generations"]

        # Initialize population
        population = self._initialize_ga_population(param_space, population_size)

        optimization_path = []
        best_individual = None
        best_fitness = float("-inf")

        logger.info(
            f"Genetic algorithm: evolving population of {population_size} over {generations} generations"
        )

        for generation in range(generations):
            # Evaluate fitness of current population
            fitness_scores = []
            evaluation_results = []

            for individual in population:
                evaluation = await self._evaluate_parameter_combination(
                    strategy_name, individual, dataset, start_date, end_date, capital
                )
                fitness = evaluation["score"]
                fitness_scores.append(fitness)
                evaluation_results.append(evaluation)

                if fitness > best_fitness:
                    best_fitness = fitness
                    best_individual = individual.copy()

            # Record generation statistics
            generation_stats = {
                "generation": generation + 1,
                "best_fitness": max(fitness_scores),
                "avg_fitness": np.mean(fitness_scores),
                "fitness_std": np.std(fitness_scores),
                "best_individual": best_individual,
            }
            optimization_path.append(generation_stats)

            # Create next generation
            if generation < generations - 1:
                population = self._evolve_population(
                    population, fitness_scores, param_space
                )

            logger.debug(
                f"Generation {generation + 1}: best fitness = {max(fitness_scores):.4f}"
            )

        return best_individual or {}, optimization_path

    def _initialize_ga_population(
        self, param_space: Dict[str, Any], population_size: int
    ) -> List[Dict[str, Any]]:
        """Initialize genetic algorithm population."""

        population = []

        for _ in range(population_size):
            individual = {}
            for param_name, param_def in param_space.items():
                param_min = param_def["min"]
                param_max = param_def["max"]
                param_type = param_def["type"]

                if param_type == "int":
                    value = np.random.randint(param_min, param_max + 1)
                else:
                    value = np.random.uniform(param_min, param_max)

                individual[param_name] = value

            population.append(individual)

        return population

    def _evolve_population(
        self,
        population: List[Dict[str, Any]],
        fitness_scores: List[float],
        param_space: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Evolve population using genetic operators."""

        population_size = len(population)
        new_population = []

        # Elitism - keep best individuals
        elitism_count = int(population_size * self.optimization_config["elitism_rate"])
        elite_indices = np.argsort(fitness_scores)[-elitism_count:]
        for idx in elite_indices:
            new_population.append(population[idx].copy())

        # Generate rest through crossover and mutation
        while len(new_population) < population_size:
            # Selection (tournament selection)
            parent1 = self._tournament_selection(population, fitness_scores)
            parent2 = self._tournament_selection(population, fitness_scores)

            # Crossover
            if np.random.random() < self.optimization_config["crossover_rate"]:
                child1, child2 = self._crossover(parent1, parent2, param_space)
            else:
                child1, child2 = parent1.copy(), parent2.copy()

            # Mutation
            child1 = self._mutate(child1, param_space)
            child2 = self._mutate(child2, param_space)

            new_population.extend([child1, child2])

        return new_population[:population_size]

    def _tournament_selection(
        self, population: List[Dict[str, Any]], fitness_scores: List[float]
    ) -> Dict[str, Any]:
        """Tournament selection for genetic algorithm."""

        tournament_size = 3
        tournament_indices = np.random.choice(
            len(population), tournament_size, replace=False
        )
        tournament_fitness = [fitness_scores[i] for i in tournament_indices]
        winner_idx = tournament_indices[np.argmax(tournament_fitness)]

        return population[winner_idx]

    def _crossover(
        self,
        parent1: Dict[str, Any],
        parent2: Dict[str, Any],
        param_space: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Perform crossover between two parents."""

        child1 = {}
        child2 = {}

        for param_name in param_space.keys():
            if np.random.random() < 0.5:
                child1[param_name] = parent1[param_name]
                child2[param_name] = parent2[param_name]
            else:
                child1[param_name] = parent2[param_name]
                child2[param_name] = parent1[param_name]

        return child1, child2

    def _mutate(
        self, individual: Dict[str, Any], param_space: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply mutation to individual."""

        mutated = individual.copy()

        for param_name, param_def in param_space.items():
            if np.random.random() < self.optimization_config["mutation_rate"]:
                param_min = param_def["min"]
                param_max = param_def["max"]
                param_type = param_def["type"]

                # Gaussian mutation
                current_value = mutated[param_name]
                mutation_strength = (param_max - param_min) * 0.1  # 10% of range

                new_value = current_value + np.random.normal(0, mutation_strength)

                # Ensure bounds
                if param_type == "int":
                    new_value = int(np.clip(new_value, param_min, param_max))
                else:
                    new_value = np.clip(new_value, param_min, param_max)

                mutated[param_name] = new_value

        return mutated

    async def _bayesian_optimization(
        self,
        strategy_name: str,
        param_space: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Perform Bayesian optimization."""

        # Set up Gaussian process
        kernel = (
            Matern(nu=2.5)
            if self.optimization_config["bayesian_kernel"] == "matern"
            else None
        )

        gp = GaussianProcessRegressor(
            kernel=kernel, alpha=1e-6, normalize_y=True, n_restarts_optimizer=10
        )

        # Initial random evaluations
        n_initial = min(10, len(self._generate_parameter_grid(param_space)))
        initial_points = self._generate_parameter_grid(param_space)[:n_initial]

        X_observed = []
        y_observed = []

        # Evaluate initial points
        for params in initial_points:
            evaluation = await self._evaluate_parameter_combination(
                strategy_name, params, dataset, start_date, end_date, capital
            )
            X_observed.append(list(params.values()))
            y_observed.append(evaluation["score"])

        optimization_path = []

        # Bayesian optimization loop
        for iteration in range(self.optimization_config["bayesian_iterations"]):
            try:
                # Fit GP model
                X_train = np.array(X_observed)
                y_train = np.array(y_observed)

                if len(X_train) > 1:
                    gp.fit(X_train, y_train)

                    # Find next point to evaluate (Expected Improvement)
                    next_point = self._acquire_next_point(
                        gp, param_space, X_train, y_train
                    )

                    # Evaluate next point
                    next_params = dict(zip(param_space.keys(), next_point))
                    evaluation = await self._evaluate_parameter_combination(
                        strategy_name,
                        next_params,
                        dataset,
                        start_date,
                        end_date,
                        capital,
                    )

                    # Add to observations
                    X_observed.append(list(next_params.values()))
                    y_observed.append(evaluation["score"])

                    optimization_path.append(
                        {
                            "iteration": iteration + 1,
                            "parameters": next_params,
                            "score": evaluation["score"],
                            "acquisition_value": 0,  # Would compute EI value
                        }
                    )

                    logger.debug(
                        f"BO iteration {iteration + 1}: score = {evaluation['score']:.4f}"
                    )

            except Exception as e:
                logger.error(
                    f"Error in Bayesian optimization iteration {iteration}: {e}"
                )
                break

        # Find best parameters
        if y_observed:
            best_idx = np.argmax(y_observed)
            best_params = dict(zip(param_space.keys(), X_observed[best_idx]))
        else:
            best_params = {}

        return best_params, optimization_path

    def _acquire_next_point(
        self, gp, param_space: Dict[str, Any], X_train: np.ndarray, y_train: np.ndarray
    ) -> np.ndarray:
        """Find next point to evaluate using Expected Improvement."""

        # Simple random search for next point (simplified implementation)
        # In practice, would use proper acquisition function optimization

        param_bounds = []
        for param_def in param_space.values():
            param_bounds.append((param_def["min"], param_def["max"]))

        # Random candidate
        candidate = []
        for bounds in param_bounds:
            value = np.random.uniform(bounds[0], bounds[1])
            candidate.append(value)

        return np.array(candidate)

    async def _evaluate_parameter_combination(
        self,
        strategy_name: str,
        parameters: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Evaluate a specific parameter combination."""

        try:
            # Create strategy configuration with parameters
            strategy_config = self._create_strategy_config(strategy_name, parameters)

            # Run backtest
            backtest_result = await self.backtesting_engine.run_backtest(
                strategy_config, dataset, start_date, end_date, capital
            )

            # Extract optimization target
            performance_metrics = backtest_result.get("performance_metrics", {})
            target_metric = self.optimization_config["optimization_target"]
            score = performance_metrics.get(target_metric, 0)

            # Apply risk adjustment if enabled
            if self.optimization_config["risk_adjustment"]:
                risk_penalty = self._calculate_risk_penalty(backtest_result)
                score = score - risk_penalty

            return {
                "score": score,
                "metrics": performance_metrics,
                "risk_adjusted_score": score,
                "backtest_result": backtest_result,
            }

        except Exception as e:
            logger.error(f"Error evaluating parameter combination: {e}")
            return {"score": float("-inf"), "metrics": {}, "error": str(e)}

    def _create_strategy_config(
        self, strategy_name: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create strategy configuration from parameters."""

        # Base configuration
        config = {"name": f"{strategy_name}_optimized", "type": strategy_name}

        # Add parameters
        config.update(parameters)

        # Add strategy-specific settings
        if strategy_name == "wallet_quality_scorer":
            config.update(
                {
                    "wallet_type_filter": [
                        "market_maker",
                        "directional_trader",
                        "arbitrage_trader",
                    ],
                    "quality_weighted_allocation": True,
                }
            )
        elif strategy_name == "adaptive_strategy_engine":
            config.update(
                {
                    "strategy_definitions": self.backtesting_engine.simulation_params.get(
                        "strategy_definitions", {}
                    )
                }
            )

        return config

    def _calculate_risk_penalty(self, backtest_result: Dict[str, Any]) -> float:
        """Calculate risk penalty for optimization score."""

        risk_metrics = backtest_result.get("risk_metrics", {})
        max_drawdown = risk_metrics.get("max_drawdown", 0)
        volatility = risk_metrics.get("volatility", 0.15)

        # Risk penalty based on drawdown and volatility
        drawdown_penalty = max_drawdown * 2  # Scale drawdown to penalty
        volatility_penalty = volatility * 5  # Scale volatility to penalty

        return drawdown_penalty + volatility_penalty

    async def _validate_optimal_parameters(
        self,
        strategy_name: str,
        optimal_params: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Validate optimal parameters using out-of-sample testing."""

        validation_results = {
            "out_of_sample_performance": {},
            "walk_forward_validation": {},
            "cross_validation_scores": {},
            "parameter_sensitivity": {},
            "robustness_tests": {},
            "validation_summary": {},
        }

        try:
            # Out-of-sample validation
            oos_performance = await self._run_out_of_sample_validation(
                strategy_name, optimal_params, dataset, start_date, end_date, capital
            )
            validation_results["out_of_sample_performance"] = oos_performance

            # Walk-forward validation
            wf_validation = await self._run_walk_forward_validation(
                strategy_name, optimal_params, dataset, start_date, end_date, capital
            )
            validation_results["walk_forward_validation"] = wf_validation

            # Cross-validation
            cv_scores = await self._run_cross_validation(
                strategy_name, optimal_params, dataset, start_date, end_date, capital
            )
            validation_results["cross_validation_scores"] = cv_scores

            # Parameter sensitivity analysis
            sensitivity = await self._run_parameter_sensitivity_analysis(
                strategy_name, optimal_params, dataset, start_date, end_date, capital
            )
            validation_results["parameter_sensitivity"] = sensitivity

            # Robustness tests
            robustness = await self._run_robustness_tests(
                strategy_name, optimal_params, dataset, start_date, end_date, capital
            )
            validation_results["robustness_tests"] = robustness

            # Validation summary
            validation_results["validation_summary"] = self._create_validation_summary(
                validation_results
            )

        except Exception as e:
            logger.error(f"Error in parameter validation: {e}")
            validation_results["error"] = str(e)

        return validation_results

    async def _run_out_of_sample_validation(
        self,
        strategy_name: str,
        optimal_params: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Run out-of-sample validation."""

        # Split data into in-sample and out-of-sample
        total_days = (end_date - start_date).days
        split_point = start_date + timedelta(
            days=int(total_days * (1 - self.optimization_config["out_of_sample_ratio"]))
        )

        # In-sample performance (used for optimization)
        in_sample_result = await self._evaluate_parameter_combination(
            strategy_name, optimal_params, dataset, start_date, split_point, capital
        )

        # Out-of-sample performance
        oos_result = await self._evaluate_parameter_combination(
            strategy_name, optimal_params, dataset, split_point, end_date, capital
        )

        return {
            "in_sample_score": in_sample_result["score"],
            "out_of_sample_score": oos_result["score"],
            "oos_degradation": in_sample_result["score"] - oos_result["score"],
            "oos_ratio": (
                oos_result["score"] / in_sample_result["score"]
                if in_sample_result["score"] != 0
                else 0
            ),
            "validation_period_days": (end_date - split_point).days,
        }

    async def _run_walk_forward_validation(
        self,
        strategy_name: str,
        optimal_params: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Run walk-forward validation."""

        wf_results = {
            "walk_forward_scores": [],
            "average_wf_score": 0.0,
            "wf_volatility": 0.0,
            "wf_trend": 0.0,
        }

        # Use existing walk-forward method from backtesting engine
        walk_forward_results = (
            await self.backtesting_engine.run_walk_forward_optimization(
                [self._create_strategy_config(strategy_name, optimal_params)],
                dataset,
                start_date,
                end_date,
            )
        )

        if walk_forward_results and "walk_forward_windows" in walk_forward_results:
            wf_scores = []
            for window in walk_forward_results["walk_forward_windows"]:
                testing_perf = window.get("testing_performance", {})
                score = testing_perf.get(
                    self.optimization_config["optimization_target"], 0
                )
                wf_scores.append(score)

                wf_results["walk_forward_scores"].append(
                    {"window": window.get("training_period"), "score": score}
                )

            if wf_scores:
                wf_results["average_wf_score"] = np.mean(wf_scores)
                wf_results["wf_volatility"] = np.std(wf_scores)

                # Trend analysis
                if len(wf_scores) > 1:
                    x = np.arange(len(wf_scores))
                    slope, _, _, _, _ = stats.linregress(x, wf_scores)
                    wf_results["wf_trend"] = slope

        return wf_results

    async def _run_cross_validation(
        self,
        strategy_name: str,
        optimal_params: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Run cross-validation on optimal parameters."""

        cv_scores = []
        cv_folds = self.optimization_config["cv_folds"]

        # Simple time-series cross-validation
        total_days = (end_date - start_date).days
        fold_size = total_days // cv_folds

        for fold in range(cv_folds):
            fold_start = start_date + timedelta(days=fold * fold_size)
            fold_end = fold_start + timedelta(days=fold_size)

            if fold_end > end_date:
                fold_end = end_date

            # Evaluate on this fold
            fold_result = await self._evaluate_parameter_combination(
                strategy_name, optimal_params, dataset, fold_start, fold_end, capital
            )

            cv_scores.append(fold_result["score"])

        return {
            "cv_scores": cv_scores,
            "cv_mean": np.mean(cv_scores),
            "cv_std": np.std(cv_scores),
            "cv_confidence_interval": [
                np.mean(cv_scores) - 1.96 * np.std(cv_scores) / np.sqrt(len(cv_scores)),
                np.mean(cv_scores) + 1.96 * np.std(cv_scores) / np.sqrt(len(cv_scores)),
            ],
        }

    async def _run_parameter_sensitivity_analysis(
        self,
        strategy_name: str,
        optimal_params: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Run parameter sensitivity analysis."""

        sensitivity_results = {}

        for param_name, param_value in optimal_params.items():
            # Test parameter variations
            param_def = self.parameter_definitions.get(strategy_name, {}).get(
                param_name, {}
            )
            param_min = param_def.get("min", param_value * 0.5)
            param_max = param_def.get("max", param_value * 1.5)
            param_type = param_def.get("type", "float")

            # Test points around optimal value
            test_points = []
            for multiplier in [0.8, 0.9, 1.0, 1.1, 1.2]:
                if param_type == "int":
                    test_value = int(param_value * multiplier)
                    test_value = max(param_min, min(param_max, test_value))
                else:
                    test_value = param_value * multiplier
                    test_value = max(param_min, min(param_max, test_value))

                test_points.append(test_value)

            # Evaluate each test point
            param_scores = []
            for test_value in test_points:
                test_params = optimal_params.copy()
                test_params[param_name] = test_value

                result = await self._evaluate_parameter_combination(
                    strategy_name, test_params, dataset, start_date, end_date, capital
                )

                param_scores.append(result["score"])

            # Calculate sensitivity metrics
            sensitivity = (
                np.std(param_scores) / abs(np.mean(param_scores))
                if np.mean(param_scores) != 0
                else 0
            )

            sensitivity_results[param_name] = {
                "optimal_value": param_value,
                "test_values": test_points,
                "test_scores": param_scores,
                "sensitivity": sensitivity,
                "sensitivity_interpretation": self._interpret_sensitivity(sensitivity),
                "robust_range": self._calculate_robust_range(
                    test_points, param_scores, optimal_params[param_name]
                ),
            }

        return sensitivity_results

    def _interpret_sensitivity(self, sensitivity: float) -> str:
        """Interpret parameter sensitivity."""

        if sensitivity < 0.1:
            return "low_sensitivity"
        elif sensitivity < 0.25:
            return "moderate_sensitivity"
        elif sensitivity < 0.5:
            return "high_sensitivity"
        else:
            return "extreme_sensitivity"

    def _calculate_robust_range(
        self, test_values: List[float], test_scores: List[float], optimal_value: float
    ) -> Dict[str, Any]:
        """Calculate robust parameter range."""

        optimal_score = (
            test_scores[test_values.index(optimal_value)]
            if optimal_value in test_values
            else max(test_scores)
        )

        # Find values within 5% of optimal score
        threshold_score = optimal_score * 0.95
        robust_values = [
            v for v, s in zip(test_values, test_scores) if s >= threshold_score
        ]

        return {
            "robust_values": robust_values,
            "robust_range_width": max(robust_values) - min(robust_values)
            if robust_values
            else 0,
            "robustness_score": len(robust_values) / len(test_values),
        }

    async def _run_robustness_tests(
        self,
        strategy_name: str,
        optimal_params: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        capital: float,
    ) -> Dict[str, Any]:
        """Run robustness tests on optimal parameters."""

        robustness_results = {
            "monte_carlo_robustness": {},
            "stress_test_performance": {},
            "regime_robustness": {},
            "data_sensitivity": {},
        }

        try:
            # Monte Carlo robustness
            mc_results = await self.backtesting_engine.run_monte_carlo_stress_test(
                self._create_strategy_config(strategy_name, optimal_params),
                dataset,
                start_date,
                end_date,
                capital,
            )

            robustness_results["monte_carlo_robustness"] = {
                "survival_probability": mc_results.get("aggregate_statistics", {}).get(
                    "probability_profit", 0
                ),
                "var_95_robustness": mc_results.get("var_95", 0),
                "expected_shortfall_robustness": mc_results.get("cvar_95", 0),
            }

            # Stress test performance
            robustness_results["stress_test_performance"] = mc_results.get(
                "aggregate_statistics", {}
            )

        except Exception as e:
            logger.error(f"Error in robustness tests: {e}")
            robustness_results["error"] = str(e)

        return robustness_results

    def _create_validation_summary(
        self, validation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create validation summary with recommendations."""

        summary = {
            "overall_validation_score": 0.0,
            "validation_strengths": [],
            "validation_concerns": [],
            "recommendations": [],
            "confidence_level": "unknown",
        }

        try:
            # Calculate overall validation score
            scores = []

            # Out-of-sample performance
            oos = validation_results.get("out_of_sample_performance", {})
            oos_ratio = oos.get("oos_ratio", 0)
            if oos_ratio > 0.8:
                scores.append(1.0)
                summary["validation_strengths"].append(
                    "Strong out-of-sample performance"
                )
            elif oos_ratio > 0.6:
                scores.append(0.7)
                summary["validation_concerns"].append(
                    "Moderate out-of-sample degradation"
                )
            else:
                scores.append(0.3)
                summary["validation_concerns"].append(
                    "Significant out-of-sample degradation"
                )

            # Walk-forward validation
            wf = validation_results.get("walk_forward_validation", {})
            wf_volatility = wf.get("wf_volatility", 1.0)
            if wf_volatility < 0.2:
                scores.append(1.0)
                summary["validation_strengths"].append(
                    "Stable walk-forward performance"
                )
            else:
                scores.append(0.5)
                summary["validation_concerns"].append("High walk-forward volatility")

            # Cross-validation
            cv = validation_results.get("cross_validation_scores", {})
            cv_std = cv.get("cv_std", 1.0)
            cv_mean = cv.get("cv_mean", 0)
            if cv_std / abs(cv_mean) < 0.3 if cv_mean != 0 else False:
                scores.append(1.0)
                summary["validation_strengths"].append(
                    "Consistent cross-validation performance"
                )
            else:
                scores.append(0.6)
                summary["validation_concerns"].append(
                    "Variable cross-validation results"
                )

            # Parameter sensitivity
            sensitivity = validation_results.get("parameter_sensitivity", {})
            high_sensitivity_params = [
                param
                for param, data in sensitivity.items()
                if data.get("sensitivity", 0) > 0.25
            ]

            if not high_sensitivity_params:
                scores.append(1.0)
                summary["validation_strengths"].append("Low parameter sensitivity")
            else:
                scores.append(0.7)
                summary["validation_concerns"].append(
                    f"High sensitivity to parameters: {high_sensitivity_params}"
                )

            # Overall score
            summary["overall_validation_score"] = np.mean(scores) if scores else 0.5

            # Confidence level
            if summary["overall_validation_score"] > 0.8:
                summary["confidence_level"] = "high"
            elif summary["overall_validation_score"] > 0.6:
                summary["confidence_level"] = "moderate"
            else:
                summary["confidence_level"] = "low"

            # Recommendations
            if summary["confidence_level"] == "high":
                summary["recommendations"].append(
                    "Parameters are well-validated and can be used in production"
                )
            elif summary["confidence_level"] == "moderate":
                summary["recommendations"].append(
                    "Parameters show reasonable validation but monitor performance closely"
                )
            else:
                summary["recommendations"].append(
                    "Parameters require further validation or adjustment before production use"
                )

        except Exception as e:
            logger.error(f"Error creating validation summary: {e}")
            summary["error"] = str(e)

        return summary

    async def _analyze_parameter_stability(
        self,
        strategy_name: str,
        optimal_params: Dict[str, Any],
        dataset: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Analyze parameter stability across different time periods."""

        stability_results = {
            "parameter_stability_scores": {},
            "stability_over_time": {},
            "most_stable_parameters": [],
            "stability_recommendations": [],
        }

        try:
            # Divide time period into windows
            total_days = (end_date - start_date).days
            window_size = max(
                30, total_days // self.optimization_config["stability_windows"]
            )

            stability_scores = defaultdict(list)

            for i in range(self.optimization_config["stability_windows"]):
                window_start = start_date + timedelta(days=i * window_size)
                window_end = min(window_start + timedelta(days=window_size), end_date)

                if (window_end - window_start).days < 15:  # Skip very short windows
                    continue

                # Optimize parameters for this window
                window_optimization = await self.optimize_strategy_parameters(
                    strategy_name,
                    dataset,
                    window_start,
                    window_end,
                    optimization_method="bayesian",
                )

                window_params = window_optimization.get("optimal_parameters", {})

                # Compare with overall optimal parameters
                for param_name in optimal_params.keys():
                    if param_name in window_params:
                        overall_value = optimal_params[param_name]
                        window_value = window_params[param_name]

                        if overall_value != 0:
                            deviation = abs(window_value - overall_value) / abs(
                                overall_value
                            )
                            stability_scores[param_name].append(deviation)

            # Calculate stability metrics
            for param_name, deviations in stability_scores.items():
                if deviations:
                    stability_score = 1 - np.mean(
                        deviations
                    )  # Lower deviation = higher stability
                    stability_results["parameter_stability_scores"][param_name] = {
                        "stability_score": stability_score,
                        "mean_deviation": np.mean(deviations),
                        "deviation_std": np.std(deviations),
                        "stability_interpretation": (
                            "stable" if stability_score > 0.8 else "variable"
                        ),
                    }

            # Find most stable parameters
            if stability_results["parameter_stability_scores"]:
                sorted_stability = sorted(
                    stability_results["parameter_stability_scores"].items(),
                    key=lambda x: x[1]["stability_score"],
                    reverse=True,
                )
                stability_results["most_stable_parameters"] = [
                    p[0] for p, _ in sorted_stability[:3]
                ]

            # Stability recommendations
            unstable_params = [
                param
                for param, data in stability_results[
                    "parameter_stability_scores"
                ].items()
                if data["stability_score"] < 0.7
            ]

            if unstable_params:
                stability_results["stability_recommendations"].append(
                    f"Monitor parameters closely: {unstable_params}"
                )
            else:
                stability_results["stability_recommendations"].append(
                    "Parameters show good stability across time periods"
                )

        except Exception as e:
            logger.error(f"Error analyzing parameter stability: {e}")
            stability_results["error"] = str(e)

        return stability_results

    def _generate_optimization_performance_summary(
        self,
        optimal_params: Dict[str, Any],
        validation_results: Dict[str, Any],
        stability_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate comprehensive optimization performance summary."""

        summary = {
            "optimization_quality_score": 0.0,
            "key_performance_metrics": {},
            "validation_assessment": "unknown",
            "stability_assessment": "unknown",
            "production_readiness": "unknown",
            "performance_summary_text": "",
        }

        try:
            # Calculate optimization quality score
            scores = []

            # Validation performance
            validation_score = validation_results.get("validation_summary", {}).get(
                "overall_validation_score", 0.5
            )
            scores.append(validation_score)

            # Parameter stability
            stability_scores = [
                data.get("stability_score", 0.5)
                for data in stability_analysis.get(
                    "parameter_stability_scores", {}
                ).values()
            ]
            avg_stability = np.mean(stability_scores) if stability_scores else 0.5
            scores.append(avg_stability)

            # Out-of-sample performance
            oos_ratio = validation_results.get("out_of_sample_performance", {}).get(
                "oos_ratio", 0.5
            )
            scores.append(oos_ratio)

            summary["optimization_quality_score"] = np.mean(scores)

            # Key performance metrics
            oos_perf = validation_results.get("out_of_sample_performance", {})
            summary["key_performance_metrics"] = {
                "out_of_sample_ratio": oos_perf.get("oos_ratio", 0),
                "oos_degradation": oos_perf.get("oos_degradation", 0),
                "validation_confidence": validation_score,
                "parameter_stability": avg_stability,
                "walk_forward_avg_score": validation_results.get(
                    "walk_forward_validation", {}
                ).get("average_wf_score", 0),
            }

            # Assessments
            if validation_score > 0.8:
                summary["validation_assessment"] = "excellent"
            elif validation_score > 0.6:
                summary["validation_assessment"] = "good"
            else:
                summary["validation_assessment"] = "needs_improvement"

            if avg_stability > 0.8:
                summary["stability_assessment"] = "highly_stable"
            elif avg_stability > 0.6:
                summary["stability_assessment"] = "moderately_stable"
            else:
                summary["stability_assessment"] = "unstable"

            # Production readiness
            if summary["optimization_quality_score"] > 0.8:
                summary["production_readiness"] = "production_ready"
            elif summary["optimization_quality_score"] > 0.6:
                summary["production_readiness"] = "conditional_ready"
            else:
                summary["production_readiness"] = "needs_work"

            # Generate summary text
            summary["performance_summary_text"] = self._generate_summary_text(summary)

        except Exception as e:
            logger.error(f"Error generating optimization performance summary: {e}")
            summary["error"] = str(e)

        return summary

    def _generate_summary_text(self, summary: Dict[str, Any]) -> str:
        """Generate human-readable performance summary."""

        quality_score = summary["optimization_quality_score"]
        validation = summary["validation_assessment"]
        stability = summary["stability_assessment"]
        readiness = summary["production_readiness"]

        summary_text = f"""
Optimization Performance Summary:
- Overall Quality Score: {quality_score:.2f}
- Validation Assessment: {validation}
- Parameter Stability: {stability}
- Production Readiness: {readiness}

Key Metrics:
- Out-of-Sample Performance: {summary["key_performance_metrics"]["out_of_sample_ratio"]:.2f}
- Parameter Stability Score: {summary["key_performance_metrics"]["parameter_stability"]:.2f}
- Validation Confidence: {summary["key_performance_metrics"]["validation_confidence"]:.2f}
"""

        return summary_text.strip()

    def _store_optimization_results(self, strategy_name: str, results: Dict[str, Any]):
        """Store optimization results for analysis."""

        self.optimization_results[strategy_name] = results

    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get summary of all optimization runs."""

        return {
            "total_optimizations": len(self.optimization_results),
            "optimized_strategies": list(self.optimization_results.keys()),
            "best_performing_optimization": self._find_best_optimization(),
            "optimization_methods_used": self._get_methods_used(),
            "average_optimization_score": self._calculate_average_optimization_score(),
        }

    def _find_best_optimization(self) -> Optional[str]:
        """Find the best performing optimization."""

        if not self.optimization_results:
            return None

        best_strategy = None
        best_score = 0

        for strategy, results in self.optimization_results.items():
            perf_summary = results.get("performance_summary", {})
            score = perf_summary.get("optimization_quality_score", 0)

            if score > best_score:
                best_score = score
                best_strategy = strategy

        return best_strategy

    def _get_methods_used(self) -> List[str]:
        """Get list of optimization methods used."""

        methods = set()
        for results in self.optimization_results.values():
            method = results.get("optimization_method")
            if method:
                methods.add(method)

        return list(methods)

    def _calculate_average_optimization_score(self) -> float:
        """Calculate average optimization quality score."""

        scores = []
        for results in self.optimization_results.values():
            perf_summary = results.get("performance_summary", {})
            score = perf_summary.get("optimization_quality_score", 0)
            scores.append(score)

        return np.mean(scores) if scores else 0.0

    def save_optimization_results(self, results: Dict[str, Any], filename: str):
        """Save optimization results to disk."""

        try:
            data_dir = Path("data/optimization")
            data_dir.mkdir(parents=True, exist_ok=True)

            filepath = data_dir / f"{filename}.json"

            with open(filepath, "w") as f:
                json.dump(results, f, indent=2, default=str)

            logger.info(f"💾 Optimization results saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving optimization results: {e}")
