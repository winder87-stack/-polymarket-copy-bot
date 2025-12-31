"""
Wallet Selection and Weighting Optimization Engine
==================================================

Machine learning-based optimization system for dynamic wallet selection
and portfolio weighting in market maker copy trading strategies.

Features:
- ML-based wallet quality prediction
- Dynamic portfolio rebalancing
- Walk-forward optimization
- Performance decay detection
- Risk-constrained optimization
- Monte Carlo scenario analysis
"""

import json
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler

if TYPE_CHECKING:
    pass

from utils.time_utils import get_current_time_utc

logger = logging.getLogger(__name__)


class WalletOptimizer:
    """
    Advanced optimization engine for wallet selection and weighting.

    Uses machine learning and optimization techniques to dynamically
    allocate capital across different wallet types for optimal returns.
    """

    def __init__(self, performance_analyzer: Any) -> None:
        self.analyzer = performance_analyzer

        # Optimization configuration
        self.optimization_config = {
            "rebalance_frequency": "daily",  # daily, weekly, monthly
            "min_allocation": 0.02,  # Minimum 2% allocation per wallet type
            "max_allocation": 0.40,  # Maximum 40% allocation per wallet type
            "risk_target": 0.15,  # Target portfolio volatility (15%)
            "return_target": 0.25,  # Target annual return (25%)
            "optimization_horizon": 30,  # Days to look ahead for optimization
            "ml_model": "gradient_boosting",  # ML model for prediction
            "monte_carlo_runs": 500,  # Monte Carlo simulation runs
            "walk_forward_windows": 5,  # Walk-forward validation windows
        }

        # ML models for wallet quality prediction
        self.quality_prediction_model = None
        self.return_prediction_model = None
        self.risk_prediction_model = None

        # Optimization state
        self.current_allocations: Dict[str, float] = {}
        self.optimization_history: List[Dict[str, Any]] = []
        self.model_performance: Dict[str, Any] = {}

        # Training data
        self.feature_columns = [
            "win_rate",
            "profit_factor",
            "sharpe_ratio",
            "max_drawdown",
            "avg_win",
            "avg_loss",
            "total_trades",
            "avg_holding_time",
            "gas_efficiency",
            "confidence_score",
            "mm_probability",
        ]

        logger.info("🎯 Wallet optimizer initialized")

    async def optimize_portfolio_allocation(
        self,
        target_date: Optional[datetime] = None,
        optimization_method: str = "ml_optimization",
    ) -> Dict[str, Any]:
        """
        Optimize portfolio allocation across wallet types.

        Args:
            target_date: Date for optimization (default: now)
            optimization_method: Optimization method to use

        Returns:
            Optimized portfolio allocation
        """

        if target_date is None:
            target_date = get_current_time_utc()

        logger.info(
            f"🎯 Optimizing portfolio allocation for {target_date.date()} using {optimization_method}"
        )

        # Get historical performance data
        historical_data = self._get_historical_performance_data(target_date)

        if not historical_data:
            logger.warning("No historical data available for optimization")
            return self._get_default_allocation()

        # Choose optimization method
        if optimization_method == "ml_optimization":
            allocation = await self._ml_based_optimization(historical_data, target_date)
        elif optimization_method == "mean_variance":
            allocation = self._mean_variance_optimization(historical_data)
        elif optimization_method == "risk_parity":
            allocation = self._risk_parity_optimization(historical_data)
        elif optimization_method == "equal_weight":
            allocation = self._equal_weight_allocation(historical_data)
        else:
            allocation = self._get_default_allocation()

        # Validate and constrain allocation
        validated_allocation = self._validate_and_constrain_allocation(allocation)

        # Store optimization result
        optimization_result = {
            "timestamp": get_current_time_utc().isoformat(),
            "target_date": target_date.isoformat(),
            "method": optimization_method,
            "allocation": validated_allocation,
            "historical_data_points": len(historical_data),
            "expected_return": self._calculate_expected_return(
                validated_allocation, historical_data
            ),
            "expected_risk": self._calculate_expected_risk(
                validated_allocation, historical_data
            ),
            "sharpe_ratio": self._calculate_allocation_sharpe(
                validated_allocation, historical_data
            ),
        }

        self.optimization_history.append(optimization_result)
        self.current_allocations = validated_allocation

        logger.info(
            f"✅ Optimization complete. Best allocation: {validated_allocation}"
        )

        return validated_allocation

    def _get_historical_performance_data(
        self, target_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical performance data for optimization."""

        # Look back 90 days for training data
        start_date = target_date - timedelta(days=90)

        # Filter performance data
        historical_data = []
        for record in self.analyzer.performance_data:
            record_date = datetime.fromisoformat(record["timestamp"])
            if start_date <= record_date <= target_date:
                historical_data.append(record)

        return historical_data

    async def _ml_based_optimization(
        self, historical_data: List[Dict[str, Any]], target_date: datetime
    ) -> Dict[str, float]:
        """
        ML-based portfolio optimization using predictive models.
        """

        # Train/update ML models if needed
        await self._train_ml_models(historical_data)

        # Generate predictions for each wallet type
        wallet_type_predictions = {}

        # Get unique wallet types
        wallet_types = set(
            record.get("wallet_type", "unknown") for record in historical_data
        )
        wallet_types.discard("unknown")

        for wallet_type in wallet_types:
            # Get recent performance metrics for this wallet type
            type_data = [
                r for r in historical_data if r.get("wallet_type") == wallet_type
            ]

            if len(type_data) < 5:  # Need minimum data for prediction
                continue

            # Calculate current metrics
            recent_metrics = self._calculate_wallet_type_metrics(
                type_data[-30:]
            )  # Last 30 records

            # Prepare features for prediction
            features = self._prepare_prediction_features(recent_metrics)

            # Make predictions
            predicted_return = self.return_prediction_model.predict([features])[0]
            predicted_risk = self.risk_prediction_model.predict([features])[0]
            predicted_quality = self.quality_prediction_model.predict([features])[0]

            wallet_type_predictions[wallet_type] = {
                "predicted_return": predicted_return,
                "predicted_risk": predicted_risk,
                "predicted_quality": predicted_quality,
                "sharpe_ratio": predicted_return / predicted_risk
                if predicted_risk > 0
                else 0,
            }

        if not wallet_type_predictions:
            return self._get_default_allocation()

        # Optimize allocation using predicted metrics
        allocation = self._optimize_ml_allocation(wallet_type_predictions)

        return allocation

    async def _train_ml_models(self, historical_data: List[Dict[str, Any]]):
        """Train ML models for wallet performance prediction."""

        # Prepare training data
        training_data = []

        # Group data by wallet type and time periods
        df = pd.DataFrame(historical_data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Create rolling windows of performance data
        for wallet_type in df["wallet_type"].unique():
            type_data = df[df["wallet_type"] == wallet_type].sort_values("timestamp")

            if len(type_data) < 20:  # Need sufficient data
                continue

            # Create rolling windows (e.g., 10-day windows to predict next 5 days)
            for i in range(10, len(type_data) - 5):
                window_data = type_data.iloc[i - 10 : i]

                # Calculate features from window
                features = self._calculate_window_features(window_data)

                # Calculate target (next 5 days performance)
                future_data = type_data.iloc[i : i + 5]
                target_return = future_data["pnl_usd"].sum()
                target_risk = future_data["pnl_usd"].std()
                target_quality = future_data["pnl_usd"].mean() / (
                    future_data["pnl_usd"].std() + 0.001
                )

                training_data.append(
                    {
                        "features": features,
                        "target_return": target_return,
                        "target_risk": target_risk,
                        "target_quality": target_quality,
                    }
                )

        if len(training_data) < 10:
            logger.warning("Insufficient training data for ML models")
            return

        # Prepare feature matrix and targets
        X = np.array([d["features"] for d in training_data])
        y_return = np.array([d["target_return"] for d in training_data])
        y_risk = np.array([d["target_risk"] for d in training_data])
        y_quality = np.array([d["target_quality"] for d in training_data])

        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Train models
        if self.optimization_config["ml_model"] == "gradient_boosting":
            self.return_prediction_model = GradientBoostingRegressor(
                n_estimators=100, random_state=42
            )
            self.risk_prediction_model = GradientBoostingRegressor(
                n_estimators=100, random_state=42
            )
            self.quality_prediction_model = GradientBoostingRegressor(
                n_estimators=100, random_state=42
            )
        else:
            self.return_prediction_model = RandomForestRegressor(
                n_estimators=100, random_state=42
            )
            self.risk_prediction_model = RandomForestRegressor(
                n_estimators=100, random_state=42
            )
            self.quality_prediction_model = RandomForestRegressor(
                n_estimators=100, random_state=42
            )

        # Train models
        self.return_prediction_model.fit(X_scaled, y_return)
        self.risk_prediction_model.fit(X_scaled, y_risk)
        self.quality_prediction_model.fit(X_scaled, y_quality)

        # Store scaler for later use
        self.feature_scaler = scaler

        # Evaluate model performance
        self._evaluate_ml_models(X_scaled, y_return, y_risk, y_quality)

        logger.info("🤖 ML models trained successfully")

    def _calculate_window_features(self, window_data: pd.DataFrame) -> List[float]:
        """Calculate features from a rolling window of performance data."""

        features = []

        # Basic statistics
        pnl_values = window_data["pnl_usd"].values
        features.extend(
            [
                np.mean(pnl_values),  # Average P&L
                np.std(pnl_values),  # Volatility
                np.max(pnl_values),  # Best trade
                np.min(pnl_values),  # Worst trade
                np.sum(pnl_values > 0) / len(pnl_values),  # Win rate
                (
                    np.sum(pnl_values) / np.sum(np.abs(pnl_values))
                    if np.sum(np.abs(pnl_values)) > 0
                    else 0
                ),  # Profit factor
            ]
        )

        # Trend features
        if len(pnl_values) > 5:
            recent_avg = np.mean(pnl_values[-3:])
            older_avg = np.mean(pnl_values[:-3])
            features.append(recent_avg - older_avg)  # Momentum
        else:
            features.append(0)

        # Wallet-specific features
        features.extend(
            [
                window_data.get("confidence_score", 0).mean(),
                window_data.get("mm_probability", 0).mean(),
                window_data.get("position_size_usd", 0).mean(),
                window_data.get("holding_time_hours", 0).mean(),
            ]
        )

        # Pad or truncate to fixed length
        while len(features) < len(self.feature_columns):
            features.append(0)

        return features[: len(self.feature_columns)]

    def _prepare_prediction_features(self, metrics: Dict[str, Any]) -> List[float]:
        """Prepare features for ML prediction from current metrics."""

        features = []

        # Extract features in the same order as training
        trade_metrics = metrics.get("trade_metrics", {})
        profit_loss = metrics.get("profit_loss_metrics", {})
        risk_metrics = metrics.get("risk_metrics", {})

        features.extend(
            [
                trade_metrics.get("win_rate", 0),
                profit_loss.get("profit_factor", 0),
                risk_metrics.get("sharpe_ratio", 0),
                risk_metrics.get("max_drawdown_usd", 0),
                profit_loss.get("avg_win_usd", 0),
                profit_loss.get("avg_loss_usd", 0),
                trade_metrics.get("total_trades", 0),
                metrics.get("timing_metrics", {}).get("avg_holding_time_hours", 0),
                metrics.get("efficiency_metrics", {}).get("gas_efficiency_ratio", 0),
                0.8,  # Placeholder for confidence_score
                0.6,  # Placeholder for mm_probability
            ]
        )

        # Scale features
        if hasattr(self, "feature_scaler"):
            features_scaled = self.feature_scaler.transform([features])
            return features_scaled[0].tolist()
        else:
            return features

    def _optimize_ml_allocation(
        self, predictions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Optimize allocation using ML predictions and risk constraints.
        """

        wallet_types = list(predictions.keys())

        if len(wallet_types) < 2:
            # Single wallet type - allocate everything to it
            return {wallet_types[0]: 1.0}

        # Extract predicted returns and risks
        returns = np.array([predictions[wt]["predicted_return"] for wt in wallet_types])
        risks = np.array([predictions[wt]["predicted_risk"] for wt in wallet_types])

        # Objective: Maximize Sharpe ratio (return/risk)
        sharpe_ratios = returns / risks

        # Simple allocation based on Sharpe ratios (risk-adjusted)
        # Normalize to sum to 1
        if np.sum(sharpe_ratios) > 0:
            raw_weights = sharpe_ratios / np.sum(sharpe_ratios)
        else:
            # Equal weight if all Sharpe ratios are negative/zero
            raw_weights = np.ones(len(wallet_types)) / len(wallet_types)

        # Apply constraints
        allocation = {}
        for i, wallet_type in enumerate(wallet_types):
            weight = raw_weights[i]
            # Apply min/max constraints
            weight = max(self.optimization_config["min_allocation"], weight)
            weight = min(self.optimization_config["max_allocation"], weight)
            allocation[wallet_type] = weight

        # Renormalize to sum to 1
        total_weight = sum(allocation.values())
        if total_weight > 0:
            allocation = {wt: w / total_weight for wt, w in allocation.items()}

        return allocation

    def _mean_variance_optimization(
        self, historical_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Traditional mean-variance portfolio optimization.
        """

        # Calculate historical returns and covariance by wallet type
        df = pd.DataFrame(historical_data)
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        # Aggregate by date and wallet type
        returns_matrix = (
            df.groupby(["date", "wallet_type"])["pnl_usd"].sum().unstack().fillna(0)
        )

        if returns_matrix.shape[1] < 2:
            return self._get_default_allocation()

        # Calculate expected returns and covariance matrix
        expected_returns = returns_matrix.mean().values
        cov_matrix = returns_matrix.cov().values

        # Number of assets
        n_assets = len(expected_returns)

        # Optimization constraints
        constraints = [
            {"type": "eq", "fun": lambda x: np.sum(x) - 1},  # Weights sum to 1
        ]

        # Bounds for each asset
        bounds = [
            (
                self.optimization_config["min_allocation"],
                self.optimization_config["max_allocation"],
            )
            for _ in range(n_assets)
        ]

        # Objective: Minimize portfolio variance (for given return target)
        def portfolio_variance(weights: Any) -> Any:
            return np.dot(weights.T, np.dot(cov_matrix, weights))

        # Target return constraint
        target_return = self.optimization_config["return_target"] / 252  # Daily target
        constraints.append(
            {"type": "eq", "fun": lambda x: np.dot(expected_returns, x) - target_return}
        )

        # Initial guess (equal weight)
        init_guess = np.ones(n_assets) / n_assets

        # Optimize
        try:
            result = minimize(
                portfolio_variance,
                init_guess,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
            )

            if result.success:
                allocation = dict(zip(returns_matrix.columns, result.x))
                return allocation
            else:
                logger.warning("Mean-variance optimization failed, using equal weight")
                return self._equal_weight_allocation(historical_data)

        except Exception as e:
            logger.error(f"Mean-variance optimization error: {e}")
            return self._equal_weight_allocation(historical_data)

    def _risk_parity_optimization(
        self, historical_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Risk parity optimization (equal risk contribution from each asset).
        """

        df = pd.DataFrame(historical_data)
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        returns_matrix = (
            df.groupby(["date", "wallet_type"])["pnl_usd"].sum().unstack().fillna(0)
        )

        if returns_matrix.shape[1] < 2:
            return self._get_default_allocation()

        # Calculate covariance matrix
        cov_matrix = returns_matrix.cov().values

        # Risk parity optimization (simplified)
        # Start with equal weights and iteratively adjust
        n_assets = len(cov_matrix)
        weights = np.ones(n_assets) / n_assets

        # Simple risk parity: weights inversely proportional to volatility
        volatilities = np.sqrt(np.diag(cov_matrix))
        inverse_vol_weights = 1 / volatilities
        weights = inverse_vol_weights / np.sum(inverse_vol_weights)

        # Apply constraints
        weights = np.clip(
            weights,
            self.optimization_config["min_allocation"],
            self.optimization_config["max_allocation"],
        )

        # Renormalize
        weights = weights / np.sum(weights)

        allocation = dict(zip(returns_matrix.columns, weights))
        return allocation

    def _equal_weight_allocation(
        self, historical_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Simple equal weight allocation across all wallet types."""

        df = pd.DataFrame(historical_data)
        wallet_types = df["wallet_type"].unique()
        wallet_types = [wt for wt in wallet_types if wt != "unknown"]

        if not wallet_types:
            return self._get_default_allocation()

        equal_weight = 1.0 / len(wallet_types)
        allocation = {wt: equal_weight for wt in wallet_types}

        return allocation

    def _get_default_allocation(self) -> Dict[str, float]:
        """Get default allocation when optimization fails."""

        return {
            "market_maker": 0.4,
            "directional_trader": 0.3,
            "high_frequency_trader": 0.2,
            "mixed_trader": 0.1,
        }

    def _validate_and_constrain_allocation(
        self, allocation: Dict[str, float]
    ) -> Dict[str, float]:
        """Validate and constrain portfolio allocation."""

        # Remove zero or negative allocations
        allocation = {k: v for k, v in allocation.items() if v > 0.001}

        # Apply min/max constraints
        for wallet_type in allocation:
            allocation[wallet_type] = max(
                self.optimization_config["min_allocation"],
                min(
                    self.optimization_config["max_allocation"], allocation[wallet_type]
                ),
            )

        # Renormalize to sum to 1
        total_weight = sum(allocation.values())
        if total_weight > 0:
            allocation = {k: v / total_weight for k, v in allocation.items()}

        # Ensure we have at least some allocation
        if not allocation:
            allocation = self._get_default_allocation()

        return allocation

    def _calculate_expected_return(
        self, allocation: Dict[str, float], historical_data: List[Dict[str, Any]]
    ) -> float:
        """Calculate expected portfolio return."""

        df = pd.DataFrame(historical_data)

        expected_return = 0
        for wallet_type, weight in allocation.items():
            type_data = df[df["wallet_type"] == wallet_type]
            if not type_data.empty:
                type_return = type_data["pnl_usd"].mean()
                expected_return += weight * type_return

        return expected_return

    def _calculate_expected_risk(
        self, allocation: Dict[str, float], historical_data: List[Dict[str, Any]]
    ) -> float:
        """Calculate expected portfolio risk (volatility)."""

        df = pd.DataFrame(historical_data)
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        portfolio_returns = []
        dates = df["date"].unique()

        for date in dates:
            daily_return = 0
            for wallet_type, weight in allocation.items():
                type_data = df[
                    (df["date"] == date) & (df["wallet_type"] == wallet_type)
                ]
                if not type_data.empty:
                    type_return = type_data["pnl_usd"].sum()
                    daily_return += weight * type_return

            portfolio_returns.append(daily_return)

        return np.std(portfolio_returns) if portfolio_returns else 0

    def _calculate_allocation_sharpe(
        self, allocation: Dict[str, float], historical_data: List[Dict[str, Any]]
    ) -> float:
        """Calculate Sharpe ratio for allocation."""

        expected_return = self._calculate_expected_return(allocation, historical_data)
        expected_risk = self._calculate_expected_risk(allocation, historical_data)

        risk_free_rate = self.optimization_config["risk_free_rate"] / 365  # Daily

        return (
            (expected_return - risk_free_rate) / expected_risk
            if expected_risk > 0
            else 0
        )

    def _calculate_wallet_type_metrics(
        self, type_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate metrics for a wallet type (simplified version)."""

        if not type_data:
            return {}

        pnl_values = [record.get("pnl_usd", 0) for record in type_data]

        return {
            "trade_metrics": {
                "win_rate": sum(1 for p in pnl_values if p > 0) / len(pnl_values),
                "total_trades": len(pnl_values),
            },
            "profit_loss_metrics": {
                "profit_factor": (
                    (
                        sum(p for p in pnl_values if p > 0)
                        / abs(sum(p for p in pnl_values if p < 0))
                    )
                    if any(p < 0 for p in pnl_values)
                    else float("inf")
                ),
                "avg_win_usd": (
                    np.mean([p for p in pnl_values if p > 0])
                    if any(p > 0 for p in pnl_values)
                    else 0
                ),
                "avg_loss_usd": (
                    abs(np.mean([p for p in pnl_values if p < 0]))
                    if any(p < 0 for p in pnl_values)
                    else 0
                ),
            },
            "risk_metrics": {
                "sharpe_ratio": self._calculate_sharpe_ratio(np.array(pnl_values)),
                "max_drawdown_usd": self._calculate_max_drawdown(np.array(pnl_values)),
            },
            "timing_metrics": {
                "avg_holding_time_hours": np.mean(
                    [record.get("holding_time_hours", 1) for record in type_data]
                )
            },
            "efficiency_metrics": {"gas_efficiency_ratio": 1.0},  # Placeholder
        }

    def detect_performance_decay(
        self, wallet_type: str, current_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect if a wallet type's performance is decaying.

        Returns decay analysis and recommendations.
        """

        # Get historical performance for this wallet type
        historical_metrics = []
        for record in self.optimization_history[-30:]:  # Last 30 optimization runs
            if wallet_type in record.get("allocation", {}):
                allocation_weight = record["allocation"][wallet_type]
                historical_metrics.append(
                    {
                        "weight": allocation_weight,
                        "expected_return": record.get("expected_return", 0),
                        "expected_risk": record.get("expected_risk", 0),
                        "sharpe_ratio": record.get("sharpe_ratio", 0),
                    }
                )

        if len(historical_metrics) < 5:
            return {"decay_detected": False, "reason": "Insufficient historical data"}

        # Analyze trend in performance metrics
        [m["weight"] for m in historical_metrics]
        sharpe_ratios = [m["sharpe_ratio"] for m in historical_metrics]

        # Check for declining Sharpe ratio
        if len(sharpe_ratios) >= 5:
            recent_avg = np.mean(sharpe_ratios[-3:])
            older_avg = np.mean(sharpe_ratios[:-3])

            decay_threshold = 0.2  # 20% decline
            decay_ratio = (
                (older_avg - recent_avg) / abs(older_avg) if older_avg != 0 else 0
            )

            if decay_ratio > decay_threshold:
                return {
                    "decay_detected": True,
                    "decay_ratio": decay_ratio,
                    "reason": f"Sharpe ratio declined by {decay_ratio:.1%} over recent periods",
                    "recommendation": "Reduce allocation to this wallet type",
                    "suggested_weight_reduction": min(
                        0.5, decay_ratio * 2
                    ),  # Reduce by up to 50%
                }

        return {
            "decay_detected": False,
            "reason": "No significant performance decay detected",
        }

    async def run_walk_forward_optimization(
        self, total_period_days: int = 90, walk_forward_windows: int = 5
    ) -> Dict[str, Any]:
        """
        Run walk-forward optimization to validate strategy stability.
        """

        logger.info(
            f"🏃 Running walk-forward optimization: {total_period_days} days, {walk_forward_windows} windows"
        )

        window_size = total_period_days // walk_forward_windows
        results = []

        for i in range(walk_forward_windows):
            # Define training and testing periods
            test_start = get_current_time_utc() - timedelta(
                days=total_period_days - i * window_size
            )
            test_end = test_start + timedelta(days=window_size)

            # Optimize using data up to test_start
            allocation = await self.optimize_portfolio_allocation(
                target_date=test_start, optimization_method="ml_optimization"
            )

            # Evaluate performance during test period
            test_performance = self._evaluate_allocation_performance(
                allocation, test_start, test_end
            )

            results.append(
                {
                    "window": i + 1,
                    "test_period": {
                        "start": test_start.isoformat(),
                        "end": test_end.isoformat(),
                    },
                    "allocation": allocation,
                    "performance": test_performance,
                }
            )

        # Analyze walk-forward results
        analysis = self._analyze_walk_forward_results(results)

        return {
            "walk_forward_results": results,
            "analysis": analysis,
            "recommendations": self._generate_walk_forward_recommendations(analysis),
        }

    def _evaluate_allocation_performance(
        self, allocation: Dict[str, float], start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Evaluate how well an allocation performed during a test period."""

        # Filter performance data for the test period
        test_data = []
        for record in self.analyzer.performance_data:
            record_date = datetime.fromisoformat(record["timestamp"])
            if start_date <= record_date <= end_date:
                test_data.append(record)

        if not test_data:
            return {"total_return": 0, "sharpe_ratio": 0, "max_drawdown": 0}

        # Calculate portfolio returns based on allocation
        df = pd.DataFrame(test_data)
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        portfolio_returns = []
        for date in df["date"].unique():
            daily_return = 0
            for wallet_type, weight in allocation.items():
                type_data = df[
                    (df["date"] == date) & (df["wallet_type"] == wallet_type)
                ]
                if not type_data.empty:
                    type_return = type_data["pnl_usd"].sum()
                    daily_return += weight * type_return

            portfolio_returns.append(daily_return)

        # Calculate performance metrics
        total_return = sum(portfolio_returns)
        sharpe_ratio = self._calculate_sharpe_ratio(np.array(portfolio_returns))
        max_drawdown = self._calculate_max_drawdown(np.array(portfolio_returns))

        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "daily_returns": portfolio_returns,
        }

    def _analyze_walk_forward_results(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze walk-forward optimization results."""

        if not results:
            return {}

        # Extract performance metrics
        returns = [r["performance"]["total_return"] for r in results]
        sharpe_ratios = [r["performance"]["sharpe_ratio"] for r in results]
        [r["performance"]["max_drawdown"] for r in results]

        # Calculate stability metrics
        return_volatility = np.std(returns)
        sharpe_volatility = np.std(sharpe_ratios)
        avg_return = np.mean(returns)
        avg_sharpe = np.mean(sharpe_ratios)

        # Consistency metrics
        positive_returns = sum(1 for r in returns if r > 0)
        consistency_ratio = positive_returns / len(returns)

        return {
            "stability_metrics": {
                "return_volatility": return_volatility,
                "sharpe_volatility": sharpe_volatility,
                "avg_return": avg_return,
                "avg_sharpe_ratio": avg_sharpe,
                "return_consistency": consistency_ratio,
            },
            "performance_distribution": {
                "returns": {
                    "mean": np.mean(returns),
                    "std": np.std(returns),
                    "min": min(returns),
                    "max": max(returns),
                },
                "sharpe_ratios": {
                    "mean": np.mean(sharpe_ratios),
                    "std": np.std(sharpe_ratios),
                    "min": min(sharpe_ratios),
                    "max": max(sharpe_ratios),
                },
            },
        }

    def _generate_walk_forward_recommendations(
        self, analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on walk-forward analysis."""

        recommendations = []

        stability = analysis.get("stability_metrics", {})
        consistency = stability.get("return_consistency", 0)

        if consistency > 0.8:
            recommendations.append(
                "✅ **High Consistency**: Strategy shows consistent performance across different market conditions"
            )
        elif consistency > 0.6:
            recommendations.append(
                "⚠️ **Moderate Consistency**: Strategy performs reasonably well but shows some variability"
            )
        else:
            recommendations.append(
                "❌ **Low Consistency**: Strategy performance is highly variable - consider more robust approach"
            )

        sharpe_volatility = stability.get("sharpe_volatility", 0)
        if sharpe_volatility < 0.5:
            recommendations.append(
                "📊 **Stable Risk-Adjusted Returns**: Sharpe ratio remains stable across periods"
            )
        else:
            recommendations.append(
                "⚠️ **Variable Risk-Adjustment**: Risk-adjusted performance fluctuates significantly"
            )

        return recommendations

    async def run_monte_carlo_simulation(
        self,
        allocation: Dict[str, float],
        simulation_days: int = 30,
        num_simulations: int = 1000,
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation to assess allocation robustness.
        """

        logger.info(
            f"🎲 Running Monte Carlo simulation: {num_simulations} runs, {simulation_days} days"
        )

        # Get historical return distributions by wallet type
        historical_returns = self._get_historical_return_distributions()

        simulation_results = []

        for sim in range(num_simulations):
            portfolio_returns = []

            for day in range(simulation_days):
                daily_return = 0

                for wallet_type, weight in allocation.items():
                    if wallet_type in historical_returns:
                        # Sample return from historical distribution
                        returns_dist = historical_returns[wallet_type]
                        sampled_return = np.random.choice(returns_dist)
                        daily_return += weight * sampled_return
                    else:
                        # Use default if no historical data
                        daily_return += weight * np.random.normal(
                            0, 0.01
                        )  # Small random return

                portfolio_returns.append(daily_return)

            # Calculate simulation metrics
            total_return = sum(portfolio_returns)
            sharpe_ratio = self._calculate_sharpe_ratio(np.array(portfolio_returns))
            max_drawdown = self._calculate_max_drawdown(np.array(portfolio_returns))

            simulation_results.append(
                {
                    "total_return": total_return,
                    "sharpe_ratio": sharpe_ratio,
                    "max_drawdown": max_drawdown,
                    "final_portfolio_value": 10000
                    * (1 + total_return / 10000),  # Assuming $10k starting
                }
            )

        # Analyze simulation results
        returns = [r["total_return"] for r in simulation_results]
        sharpe_ratios = [r["sharpe_ratio"] for r in simulation_results]

        analysis = {
            "expected_return": np.mean(returns),
            "return_volatility": np.std(returns),
            "return_confidence_interval": np.percentile(returns, [5, 95]),
            "sharpe_distribution": {
                "mean": np.mean(sharpe_ratios),
                "std": np.std(sharpe_ratios),
                "percentile_5": np.percentile(sharpe_ratios, 5),
                "percentile_95": np.percentile(sharpe_ratios, 95),
            },
            "value_at_risk_95": np.percentile(returns, 5),
            "expected_shortfall_95": np.mean(
                [r for r in returns if r <= np.percentile(returns, 5)]
            ),
            "prob_profit": sum(1 for r in returns if r > 0) / len(returns),
            "prob_loss": sum(1 for r in returns if r < -500) / len(returns),  # >5% loss
        }

        return {
            "simulation_parameters": {
                "num_simulations": num_simulations,
                "simulation_days": simulation_days,
                "allocation": allocation,
            },
            "results_summary": analysis,
            "full_results": simulation_results[:100],  # First 100 for detailed analysis
        }

    def _get_historical_return_distributions(self) -> Dict[str, List[float]]:
        """Get historical return distributions by wallet type."""

        df = pd.DataFrame(self.analyzer.performance_data)

        distributions = {}
        for wallet_type in df["wallet_type"].unique():
            if wallet_type != "unknown":
                type_returns = df[df["wallet_type"] == wallet_type]["pnl_usd"].values
                if len(type_returns) > 10:  # Need sufficient data
                    distributions[wallet_type] = type_returns.tolist()

        return distributions

    def save_optimizer_state(self) -> None:
        """Save optimizer state and models."""

        try:
            state_dir = Path("data/optimizer")
            state_dir.mkdir(parents=True, exist_ok=True)

            # Save current allocations
            with open(state_dir / "current_allocations.json", "w") as f:
                json.dump(self.current_allocations, f, indent=2)

            # Save optimization history
            with open(state_dir / "optimization_history.json", "w") as f:
                json.dump(
                    self.optimization_history[-100:], f, indent=2
                )  # Last 100 records

            # Save ML models if they exist
            if self.return_prediction_model:
                with open(state_dir / "return_model.pkl", "wb") as f:
                    pickle.dump(self.return_prediction_model, f)

            if self.risk_prediction_model:
                with open(state_dir / "risk_model.pkl", "wb") as f:
                    pickle.dump(self.risk_prediction_model, f)

            if self.quality_prediction_model:
                with open(state_dir / "quality_model.pkl", "wb") as f:
                    pickle.dump(self.quality_prediction_model, f)

            logger.info(f"💾 Optimizer state saved to {state_dir}")

        except Exception as e:
            logger.error(f"Error saving optimizer state: {e}")

    def load_optimizer_state(self) -> None:
        """Load optimizer state and models."""

        try:
            state_dir = Path("data/optimizer")

            # Load current allocations
            alloc_file = state_dir / "current_allocations.json"
            if alloc_file.exists():
                with open(alloc_file, "r") as f:
                    self.current_allocations = json.load(f)

            # Load optimization history
            history_file = state_dir / "optimization_history.json"
            if history_file.exists():
                with open(history_file, "r") as f:
                    self.optimization_history = json.load(f)

            # Load ML models
            return_model_file = state_dir / "return_model.pkl"
            if return_model_file.exists():
                with open(return_model_file, "rb") as f:
                    self.return_prediction_model = pickle.load(f)

            risk_model_file = state_dir / "risk_model.pkl"
            if risk_model_file.exists():
                with open(risk_model_file, "rb") as f:
                    self.risk_prediction_model = pickle.load(f)

            quality_model_file = state_dir / "quality_model.pkl"
            if quality_model_file.exists():
                with open(quality_model_file, "rb") as f:
                    self.quality_prediction_model = pickle.load(f)

            logger.info(f"📊 Optimizer state loaded from {state_dir}")

        except Exception as e:
            logger.error(f"Error loading optimizer state: {e}")

    def _evaluate_ml_models(
        self, X: Any, y_return: Any, y_risk: Any, y_quality: Any
    ) -> None:
        """Evaluate performance of trained ML models."""

        # Cross-validation scores
        cv_splitter = TimeSeriesSplit(n_splits=3)

        return_scores = cross_val_score(
            self.return_prediction_model, X, y_return, cv=cv_splitter, scoring="r2"
        )
        risk_scores = cross_val_score(
            self.risk_prediction_model, X, y_risk, cv=cv_splitter, scoring="r2"
        )
        quality_scores = cross_val_score(
            self.quality_prediction_model, X, y_quality, cv=cv_splitter, scoring="r2"
        )

        self.model_performance = {
            "return_model": {
                "mean_r2": return_scores.mean(),
                "std_r2": return_scores.std(),
                "cv_scores": return_scores.tolist(),
            },
            "risk_model": {
                "mean_r2": risk_scores.mean(),
                "std_r2": risk_scores.std(),
                "cv_scores": risk_scores.tolist(),
            },
            "quality_model": {
                "mean_r2": quality_scores.mean(),
                "std_r2": quality_scores.std(),
                "cv_scores": quality_scores.tolist(),
            },
        }

        logger.info(
            f"🤖 ML Model Performance - Return R²: {return_scores.mean():.3f}, Risk R²: {risk_scores.mean():.3f}, Quality R²: {quality_scores.mean():.3f}"
        )

    async def get_optimization_dashboard(self) -> Dict[str, Any]:
        """Generate optimization dashboard data."""

        # Current allocation status
        current_status = {
            "current_allocations": self.current_allocations,
            "last_optimization": (
                self.optimization_history[-1] if self.optimization_history else None
            ),
            "model_performance": self.model_performance,
        }

        # Performance trends
        recent_history = (
            self.optimization_history[-10:]
            if len(self.optimization_history) > 10
            else self.optimization_history
        )

        performance_trends = []
        for record in recent_history:
            performance_trends.append(
                {
                    "date": record["timestamp"],
                    "sharpe_ratio": record.get("sharpe_ratio", 0),
                    "expected_return": record.get("expected_return", 0),
                    "expected_risk": record.get("expected_risk", 0),
                }
            )

        # Allocation changes over time
        allocation_history = []
        for record in recent_history:
            allocation_history.append(
                {"date": record["timestamp"], "allocations": record["allocation"]}
            )

        return {
            "current_status": current_status,
            "performance_trends": performance_trends,
            "allocation_history": allocation_history,
            "optimization_config": self.optimization_config,
        }
