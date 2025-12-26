"""
Machine Learning Strategy Optimizer
===================================

Advanced ML system for adaptive copy trading strategy optimization.

Features:
- Strategy prediction models using wallet behavior data
- Real-time strategy recommendation engine
- Reinforcement learning for continuous optimization
- Model drift detection and automated retraining
- Explainable AI for strategy transparency
- Model monitoring and validation framework
"""

import asyncio
import json
import logging
import pickle
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix, mean_squared_error,
    r2_score, explained_variance_score
)

logger = logging.getLogger(__name__)


class MLStrategyOptimizer:
    """
    Machine learning system for optimizing adaptive copy trading strategies.

    Uses advanced ML techniques to predict optimal strategies based on:
    - Wallet behavior patterns
    - Market conditions
    - Historical performance data
    - Real-time feature engineering
    """

    def __init__(self):
        # ML Models
        self.strategy_predictor = None
        self.performance_predictor = None
        self.risk_predictor = None

        # Feature engineering
        self.feature_scaler = StandardScaler()
        self.label_encoder = LabelEncoder()

        # Model training parameters
        self.training_params = {
            "min_samples_for_training": 1000,
            "retraining_interval_hours": 24,
            "validation_split_ratio": 0.2,
            "early_stopping_rounds": 50,
            "feature_importance_threshold": 0.01,
            "max_model_age_days": 30,
            "confidence_threshold": 0.7
        }

        # Training data
        self.training_data: List[Dict[str, Any]] = []
        self.feature_store: Dict[str, Any] = {}

        # Model performance tracking
        self.model_performance_history: List[Dict[str, Any]] = []
        self.prediction_accuracy: Dict[str, float] = {}

        # Reinforcement learning
        self.rl_agent = None
        self.rl_training_data: List[Dict[str, Any]] = []

        # Model monitoring
        self.drift_detector = None
        self.model_health_metrics: Dict[str, Any] = {}

        # Feature engineering parameters
        self.feature_params = {
            "temporal_windows": [1, 6, 24, 168],  # 1h, 6h, 1d, 1w
            "behavior_features": [
                "trade_frequency", "buy_sell_ratio", "avg_position_size",
                "holding_time_distribution", "profit_factor", "win_rate",
                "max_drawdown", "volatility_exposure", "market_correlation"
            ],
            "market_features": [
                "volatility_index", "liquidity_score", "trend_strength",
                "gas_price_multiplier", "market_regime"
            ],
            "wallet_type_features": [
                "is_market_maker", "is_directional", "is_arbitrage",
                "confidence_score", "behavior_consistency"
            ]
        }

        logger.info("🧠 ML Strategy Optimizer initialized")

    async def predict_optimal_strategy(
        self,
        wallet_address: str,
        wallet_data: Dict[str, Any],
        market_conditions: Dict[str, Any],
        available_strategies: List[str]
    ) -> Dict[str, Any]:
        """
        Predict optimal trading strategy for a wallet using ML models.

        Args:
            wallet_address: Target wallet address
            wallet_data: Wallet behavior and classification data
            market_conditions: Current market conditions
            available_strategies: List of available strategy options

        Returns:
            Strategy prediction with confidence scores
        """

        prediction_result = {
            "recommended_strategy": None,
            "confidence_score": 0.0,
            "prediction_probabilities": {},
            "feature_importance": {},
            "prediction_timestamp": datetime.now().isoformat(),
            "model_version": None,
            "fallback_reason": None
        }

        try:
            # Check if models are trained and available
            if not self._models_ready():
                prediction_result["fallback_reason"] = "Models not trained yet"
                return self._fallback_prediction(wallet_data, available_strategies, prediction_result)

            # Feature engineering
            features = await self._extract_features(wallet_address, wallet_data, market_conditions)

            if not features:
                prediction_result["fallback_reason"] = "Feature extraction failed"
                return self._fallback_prediction(wallet_data, available_strategies, prediction_result)

            # Scale features
            scaled_features = self.feature_scaler.transform([list(features.values())])

            # Strategy prediction
            if self.strategy_predictor:
                strategy_probs = self.strategy_predictor.predict_proba(scaled_features)[0]

                # Map probabilities to available strategies
                strategy_probabilities = {}
                for i, prob in enumerate(strategy_probs):
                    strategy_name = self.label_encoder.inverse_transform([i])[0]
                    if strategy_name in available_strategies:
                        strategy_probabilities[strategy_name] = prob

                # Select highest probability strategy
                if strategy_probabilities:
                    best_strategy = max(strategy_probabilities.keys(),
                                      key=lambda x: strategy_probabilities[x])
                    prediction_result["recommended_strategy"] = best_strategy
                    prediction_result["confidence_score"] = strategy_probabilities[best_strategy]
                    prediction_result["prediction_probabilities"] = strategy_probabilities

                    # Get feature importance if available
                    if hasattr(self.strategy_predictor, 'feature_importances_'):
                        feature_names = list(features.keys())
                        importance_dict = dict(zip(feature_names,
                                                 self.strategy_predictor.feature_importances_))
                        prediction_result["feature_importance"] = importance_dict

                    prediction_result["model_version"] = getattr(self.strategy_predictor, '_model_version', 'unknown')

                else:
                    prediction_result["fallback_reason"] = "No matching strategies in prediction"
                    return self._fallback_prediction(wallet_data, available_strategies, prediction_result)

            else:
                prediction_result["fallback_reason"] = "Strategy predictor not available"
                return self._fallback_prediction(wallet_data, available_strategies, prediction_result)

        except Exception as e:
            logger.error(f"Error in strategy prediction for {wallet_address}: {e}")
            prediction_result["error"] = str(e)
            prediction_result["fallback_reason"] = f"Prediction error: {e}"
            return self._fallback_prediction(wallet_data, available_strategies, prediction_result)

        return prediction_result

    def _models_ready(self) -> bool:
        """Check if ML models are trained and ready for prediction."""

        return (
            self.strategy_predictor is not None and
            hasattr(self.strategy_predictor, 'predict_proba') and
            len(self.label_encoder.classes_) > 0
        )

    def _fallback_prediction(
        self,
        wallet_data: Dict[str, Any],
        available_strategies: List[str],
        prediction_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Provide fallback prediction when ML models are unavailable."""

        # Simple rule-based fallback
        wallet_type = wallet_data.get("classification", "unknown")

        fallback_strategies = {
            "market_maker": "market_maker_conservative",
            "directional_trader": "directional_momentum",
            "arbitrage_trader": "arbitrage_cross_market",
            "high_frequency_trader": "high_frequency_scalping",
            "mixed_trader": "directional_mean_reversion",
            "low_activity": "passive_hold"
        }

        fallback_strategy = fallback_strategies.get(wallet_type, "passive_hold")

        # Check if fallback strategy is available
        if fallback_strategy in available_strategies:
            prediction_result["recommended_strategy"] = fallback_strategy
            prediction_result["confidence_score"] = 0.5  # Moderate confidence for fallback
        else:
            # Default to first available strategy
            prediction_result["recommended_strategy"] = available_strategies[0] if available_strategies else "passive_hold"
            prediction_result["confidence_score"] = 0.3  # Low confidence

        prediction_result["prediction_method"] = "rule_based_fallback"

        return prediction_result

    async def _extract_features(
        self,
        wallet_address: str,
        wallet_data: Dict[str, Any],
        market_conditions: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Extract comprehensive features for ML prediction.

        Combines wallet behavior, market conditions, and temporal patterns.
        """

        features = {}

        try:
            # Wallet classification features
            wallet_type = wallet_data.get("classification", "unknown")
            confidence_score = wallet_data.get("confidence_score", 0.0)

            features["is_market_maker"] = 1.0 if wallet_type == "market_maker" else 0.0
            features["is_directional"] = 1.0 if wallet_type == "directional_trader" else 0.0
            features["is_arbitrage"] = 1.0 if wallet_type == "arbitrage_trader" else 0.0
            features["is_high_frequency"] = 1.0 if wallet_type == "high_frequency_trader" else 0.0
            features["confidence_score"] = confidence_score

            # Behavioral features from wallet data
            behavior_metrics = wallet_data.get("behavior_metrics", {})

            # Trade frequency and timing
            trade_count_24h = behavior_metrics.get("trades_24h", 0)
            trade_count_7d = behavior_metrics.get("trades_7d", 0)

            features["trade_frequency_24h"] = trade_count_24h
            features["trade_frequency_7d"] = trade_count_7d
            features["avg_trades_per_hour"] = trade_count_24h / 24 if trade_count_24h > 0 else 0

            # Buy/sell behavior
            buy_sell_ratio = behavior_metrics.get("buy_sell_ratio", 1.0)
            features["buy_sell_ratio"] = buy_sell_ratio
            features["trade_imbalance"] = abs(buy_sell_ratio - 1.0)

            # Position sizing
            avg_position_size = behavior_metrics.get("avg_position_size", 0)
            position_size_volatility = behavior_metrics.get("position_size_volatility", 0)

            features["avg_position_size"] = avg_position_size
            features["position_size_volatility"] = position_size_volatility
            features["position_consistency"] = 1.0 / (1.0 + position_size_volatility)

            # Holding time patterns
            avg_holding_time = behavior_metrics.get("avg_holding_time_hours", 1.0)
            holding_time_volatility = behavior_metrics.get("holding_time_volatility", 0)

            features["avg_holding_time"] = avg_holding_time
            features["holding_time_volatility"] = holding_time_volatility
            features["holding_time_consistency"] = 1.0 / (1.0 + holding_time_volatility)

            # Performance metrics
            win_rate = behavior_metrics.get("win_rate", 0.5)
            profit_factor = behavior_metrics.get("profit_factor", 1.0)
            max_drawdown = behavior_metrics.get("max_drawdown", 0.1)
            sharpe_ratio = behavior_metrics.get("sharpe_ratio", 1.0)

            features["win_rate"] = win_rate
            features["profit_factor"] = profit_factor
            features["max_drawdown"] = max_drawdown
            features["sharpe_ratio"] = sharpe_ratio
            features["risk_adjusted_return"] = win_rate * profit_factor / (max_drawdown + 0.01)

            # Market condition features
            volatility_index = market_conditions.get("volatility_index", 0.2)
            liquidity_score = market_conditions.get("liquidity_score", 0.6)
            trend_strength = market_conditions.get("trend_strength", 0.0)
            gas_multiplier = market_conditions.get("gas_price_multiplier", 1.0)

            features["market_volatility"] = volatility_index
            features["market_liquidity"] = liquidity_score
            features["trend_strength"] = trend_strength
            features["gas_price_multiplier"] = gas_multiplier
            features["market_stress"] = volatility_index * (2 - liquidity_score)

            # Temporal features
            current_hour = datetime.now().hour
            current_day = datetime.now().weekday()

            features["hour_of_day"] = current_hour / 24  # Normalize to 0-1
            features["is_weekend"] = 1.0 if current_day >= 5 else 0.0
            features["is_business_hours"] = 1.0 if 9 <= current_hour <= 17 else 0.0

            # Cross-sectional features
            features["volatility_adjusted_frequency"] = trade_count_24h / (volatility_index + 0.1)
            features["liquidity_adjusted_profit"] = profit_factor * liquidity_score
            features["gas_adjusted_win_rate"] = win_rate / (gas_multiplier ** 0.5)

            # Behavioral consistency features
            behavior_consistency = self._calculate_behavior_consistency(wallet_data)
            features["behavior_consistency"] = behavior_consistency
            features["behavior_stability"] = behavior_consistency * confidence_score

        except Exception as e:
            logger.error(f"Error extracting features for {wallet_address}: {e}")
            return {}

        return features

    def _calculate_behavior_consistency(self, wallet_data: Dict[str, Any]) -> float:
        """Calculate behavioral consistency score for the wallet."""

        try:
            # Check consistency across different time periods
            metrics = wallet_data.get("behavior_metrics", {})

            # Consistency in trade frequency
            freq_1h = metrics.get("trades_1h", 0)
            freq_24h = metrics.get("trades_24h", 0)
            freq_7d = metrics.get("trades_7d", 0)

            if freq_24h > 0:
                freq_consistency = min(freq_1h * 24 / freq_24h, freq_24h * 7 / freq_7d) if freq_7d > 0 else 0.5
                freq_consistency = min(freq_consistency, 1.0)
            else:
                freq_consistency = 0.5

            # Consistency in win rate
            win_rate_short = metrics.get("win_rate_24h", 0.5)
            win_rate_long = metrics.get("win_rate_7d", 0.5)
            win_rate_consistency = 1.0 - abs(win_rate_short - win_rate_long)

            # Overall consistency score
            consistency_score = (freq_consistency + win_rate_consistency) / 2

            return consistency_score

        except Exception as e:
            logger.error(f"Error calculating behavior consistency: {e}")
            return 0.5

    async def train_strategy_predictor(
        self,
        training_data: Optional[List[Dict[str, Any]]] = None,
        force_retrain: bool = False
    ) -> Dict[str, Any]:
        """
        Train the strategy prediction model using historical data.

        Args:
            training_data: Custom training data (optional)
            force_retrain: Force retraining even if recent model exists

        Returns:
            Training results and model performance metrics
        """

        training_results = {
            "training_successful": False,
            "model_type": "strategy_predictor",
            "training_samples": 0,
            "feature_count": 0,
            "cross_validation_score": 0.0,
            "training_timestamp": datetime.now().isoformat(),
            "model_version": None,
            "performance_metrics": {}
        }

        try:
            # Check if retraining is needed
            if not force_retrain and self._recent_model_exists():
                training_results["reason"] = "Recent model exists, skipping training"
                return training_results

            # Use provided data or existing training data
            if training_data:
                self.training_data.extend(training_data)

            if len(self.training_data) < self.training_params["min_samples_for_training"]:
                training_results["reason"] = f"Insufficient training data: {len(self.training_data)} < {self.training_params['min_samples_for_training']}"
                return training_results

            # Prepare training data
            X, y = await self._prepare_training_data()

            if X is None or y is None or len(X) == 0:
                training_results["reason"] = "Failed to prepare training data"
                return training_results

            training_results["training_samples"] = len(X)
            training_results["feature_count"] = X.shape[1]

            # Split data for validation
            split_idx = int(len(X) * (1 - self.training_params["validation_split_ratio"]))
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]

            # Train ensemble model
            self.strategy_predictor = VotingClassifier([
                ('rf', RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    min_samples_split=20,
                    random_state=42
                )),
                ('gb', GradientBoostingRegressor(
                    n_estimators=100,
                    max_depth=6,
                    learning_rate=0.1,
                    random_state=42
                )),
                ('lr', LogisticRegression(
                    random_state=42,
                    max_iter=1000
                ))
            ])

            # Fit label encoder
            self.label_encoder.fit(y_train)

            # Transform labels
            y_train_encoded = self.label_encoder.transform(y_train)

            # Fit scaler on training features
            self.feature_scaler.fit(X_train)

            # Scale training data
            X_train_scaled = self.feature_scaler.transform(X_train)

            # Train model
            self.strategy_predictor.fit(X_train_scaled, y_train_encoded)

            # Add model version
            model_version = f"v_{int(time.time())}"
            setattr(self.strategy_predictor, '_model_version', model_version)
            training_results["model_version"] = model_version

            # Validate model
            validation_results = await self._validate_model(X_val, y_val)
            training_results["performance_metrics"] = validation_results

            # Calculate cross-validation score
            cv_scores = cross_val_score(
                self.strategy_predictor, X_train_scaled, y_train_encoded,
                cv=TimeSeriesSplit(n_splits=5), scoring='accuracy'
            )
            training_results["cross_validation_score"] = cv_scores.mean()

            training_results["training_successful"] = True

            # Save training results
            self.model_performance_history.append(training_results)

            logger.info(f"✅ Strategy predictor trained: {training_results['cross_validation_score']:.3f} CV accuracy")

        except Exception as e:
            logger.error(f"Error training strategy predictor: {e}")
            training_results["error"] = str(e)

        return training_results

    async def _prepare_training_data(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Prepare training data from historical strategy decisions."""

        try:
            if not self.training_data:
                return None, None

            # Extract features and labels
            feature_list = []
            label_list = []

            for record in self.training_data:
                features = record.get("features", {})
                strategy = record.get("selected_strategy", "")

                if features and strategy:
                    feature_list.append(list(features.values()))
                    label_list.append(strategy)

            if not feature_list or not label_list:
                return None, None

            X = np.array(feature_list)
            y = np.array(label_list)

            return X, y

        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return None, None

    async def _validate_model(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> Dict[str, Any]:
        """Validate trained model performance."""

        validation_metrics = {}

        try:
            if self.strategy_predictor is None:
                return validation_metrics

            # Scale validation data
            X_val_scaled = self.feature_scaler.transform(X_val)

            # Encode validation labels
            y_val_encoded = self.label_encoder.transform(y_val)

            # Predictions
            y_pred = self.strategy_predictor.predict(X_val_scaled)
            y_pred_proba = self.strategy_predictor.predict_proba(X_val_scaled)

            # Classification metrics
            validation_metrics["accuracy"] = accuracy_score(y_val_encoded, y_pred)
            validation_metrics["precision"] = precision_score(y_val_encoded, y_pred, average='weighted')
            validation_metrics["recall"] = recall_score(y_val_encoded, y_pred, average='weighted')
            validation_metrics["f1_score"] = f1_score(y_val_encoded, y_pred, average='weighted')

            # Confusion matrix
            cm = confusion_matrix(y_val_encoded, y_pred)
            validation_metrics["confusion_matrix"] = cm.tolist()

            # Class-specific metrics
            class_report = classification_report(
                y_val_encoded, y_pred,
                target_names=self.label_encoder.classes_,
                output_dict=True
            )
            validation_metrics["class_report"] = class_report

            # Prediction confidence analysis
            prediction_confidences = np.max(y_pred_proba, axis=1)
            validation_metrics["avg_prediction_confidence"] = np.mean(prediction_confidences)
            validation_metrics["confidence_std"] = np.std(prediction_confidences)
            validation_metrics["high_confidence_predictions"] = np.mean(prediction_confidences > 0.8)

        except Exception as e:
            logger.error(f"Error validating model: {e}")
            validation_metrics["error"] = str(e)

        return validation_metrics

    def _recent_model_exists(self) -> bool:
        """Check if a recent model exists."""

        if self.strategy_predictor is None:
            return False

        # Check model age
        if hasattr(self.strategy_predictor, '_training_timestamp'):
            training_time = getattr(self.strategy_predictor, '_training_timestamp')
            if isinstance(training_time, str):
                training_time = datetime.fromisoformat(training_time)

            age_hours = (datetime.now() - training_time).total_seconds() / 3600
            return age_hours < self.training_params["retraining_interval_hours"]

        return False

    async def train_performance_predictor(
        self,
        performance_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Train model to predict strategy performance under different conditions.

        Args:
            performance_data: Historical performance data with features and outcomes

        Returns:
            Training results for performance predictor
        """

        training_results = {
            "training_successful": False,
            "model_type": "performance_predictor",
            "training_samples": 0,
            "feature_count": 0,
            "r2_score": 0.0,
            "rmse": 0.0,
            "training_timestamp": datetime.now().isoformat()
        }

        try:
            if len(performance_data) < 100:
                training_results["reason"] = "Insufficient performance data"
                return training_results

            # Prepare data
            X, y = [], []

            for record in performance_data:
                features = record.get("features", {})
                performance = record.get("performance_score", 0.0)

                if features and isinstance(performance, (int, float)):
                    X.append(list(features.values()))
                    y.append(performance)

            if not X or not y:
                training_results["reason"] = "No valid performance training data"
                return training_results

            X = np.array(X)
            y = np.array(y)

            training_results["training_samples"] = len(X)
            training_results["feature_count"] = X.shape[1]

            # Split data
            split_idx = int(len(X) * 0.8)
            X_train, X_test = X[:split_idx], X[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Train gradient boosting regressor
            self.performance_predictor = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.1,
                random_state=42
            )

            self.performance_predictor.fit(X_train_scaled, y_train)

            # Evaluate
            y_pred = self.performance_predictor.predict(X_test_scaled)

            training_results["r2_score"] = r2_score(y_test, y_pred)
            training_results["rmse"] = np.sqrt(mean_squared_error(y_test, y_pred))
            training_results["explained_variance"] = explained_variance_score(y_test, y_pred)

            training_results["training_successful"] = True

            logger.info(f"✅ Performance predictor trained: R² = {training_results['r2_score']:.3f}")

        except Exception as e:
            logger.error(f"Error training performance predictor: {e}")
            training_results["error"] = str(e)

        return training_results

    async def initialize_reinforcement_learning(
        self,
        state_space_size: int = 50,
        action_space_size: int = 10
    ) -> Dict[str, Any]:
        """
        Initialize reinforcement learning agent for strategy optimization.

        Args:
            state_space_size: Size of state representation
            action_space_size: Number of possible actions (strategies)

        Returns:
            RL initialization results
        """

        init_results = {
            "initialization_successful": False,
            "state_space_size": state_space_size,
            "action_space_size": action_space_size,
            "model_type": "reinforcement_learning",
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Initialize Q-learning agent (simplified implementation)
            self.rl_agent = {
                "q_table": defaultdict(lambda: np.zeros(action_space_size)),
                "learning_rate": 0.1,
                "discount_factor": 0.95,
                "exploration_rate": 1.0,
                "exploration_decay": 0.995,
                "min_exploration_rate": 0.01,
                "state_space_size": state_space_size,
                "action_space_size": action_space_size,
                "training_episodes": 0
            }

            init_results["initialization_successful"] = True

            logger.info("🎮 Reinforcement learning agent initialized")

        except Exception as e:
            logger.error(f"Error initializing RL agent: {e}")
            init_results["error"] = str(e)

        return init_results

    async def update_reinforcement_learning(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray
    ) -> Dict[str, Any]:
        """
        Update reinforcement learning agent with new experience.

        Args:
            state: Current state representation
            action: Action taken (strategy index)
            reward: Reward received
            next_state: Next state after action

        Returns:
            Update results
        """

        update_results = {
            "update_successful": False,
            "q_value_change": 0.0,
            "exploration_rate": 0.0
        }

        try:
            if not self.rl_agent:
                update_results["error"] = "RL agent not initialized"
                return update_results

            # Convert state to hashable key
            state_key = tuple(state.astype(float))
            next_state_key = tuple(next_state.astype(float))

            # Q-learning update
            q_table = self.rl_agent["q_table"]
            lr = self.rl_agent["learning_rate"]
            gamma = self.rl_agent["discount_factor"]

            # Get current Q-value
            current_q = q_table[state_key][action]

            # Get max Q-value for next state
            next_max_q = np.max(q_table[next_state_key])

            # Update Q-value
            new_q = current_q + lr * (reward + gamma * next_max_q - current_q)
            q_table[state_key][action] = new_q

            update_results["q_value_change"] = new_q - current_q

            # Decay exploration rate
            self.rl_agent["exploration_rate"] *= self.rl_agent["exploration_decay"]
            self.rl_agent["exploration_rate"] = max(
                self.rl_agent["exploration_rate"],
                self.rl_agent["min_exploration_rate"]
            )

            update_results["exploration_rate"] = self.rl_agent["exploration_rate"]
            update_results["update_successful"] = True

            # Track training progress
            self.rl_agent["training_episodes"] += 1

        except Exception as e:
            logger.error(f"Error updating RL agent: {e}")
            update_results["error"] = str(e)

        return update_results

    async def detect_model_drift(
        self,
        recent_predictions: List[Dict[str, Any]],
        performance_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Detect model drift using recent prediction performance.

        Args:
            recent_predictions: Recent prediction results with outcomes
            performance_threshold: Threshold for triggering retraining

        Returns:
            Drift detection results
        """

        drift_results = {
            "drift_detected": False,
            "drift_severity": 0.0,
            "accuracy_decline": 0.0,
            "confidence_decline": 0.0,
            "retraining_recommended": False,
            "timestamp": datetime.now().isoformat()
        }

        try:
            if len(recent_predictions) < 50:
                drift_results["reason"] = "Insufficient recent predictions for drift detection"
                return drift_results

            # Calculate recent performance
            recent_accuracies = []
            recent_confidences = []

            for pred in recent_predictions[-100:]:  # Last 100 predictions
                if "actual_outcome" in pred and "predicted_strategy" in pred:
                    accuracy = 1.0 if pred["predicted_strategy"] == pred["actual_outcome"] else 0.0
                    recent_accuracies.append(accuracy)

                if "confidence_score" in pred:
                    recent_confidences.append(pred["confidence_score"])

            if not recent_accuracies:
                drift_results["reason"] = "No accuracy data available"
                return drift_results

            recent_accuracy = np.mean(recent_accuracies)
            recent_confidence = np.mean(recent_confidences) if recent_confidences else 0.5

            # Compare to baseline performance
            baseline_accuracy = self.prediction_accuracy.get("baseline_accuracy", 0.7)
            baseline_confidence = self.prediction_accuracy.get("baseline_confidence", 0.7)

            accuracy_decline = baseline_accuracy - recent_accuracy
            confidence_decline = baseline_confidence - recent_confidence

            drift_results["accuracy_decline"] = accuracy_decline
            drift_results["confidence_decline"] = confidence_decline

            # Calculate overall drift severity
            drift_severity = (accuracy_decline + confidence_decline) / 2
            drift_results["drift_severity"] = drift_severity

            # Determine if retraining is needed
            if drift_severity > (1 - performance_threshold):
                drift_results["drift_detected"] = True
                drift_results["retraining_recommended"] = True

            # Update drift detector
            self.model_health_metrics["last_drift_check"] = datetime.now().isoformat()
            self.model_health_metrics["drift_severity"] = drift_severity

        except Exception as e:
            logger.error(f"Error detecting model drift: {e}")
            drift_results["error"] = str(e)

        return drift_results

    def get_model_explainability(
        self,
        features: Dict[str, float],
        prediction: str
    ) -> Dict[str, Any]:
        """
        Provide explainable AI insights for strategy predictions.

        Args:
            features: Input features used for prediction
            prediction: Predicted strategy

        Returns:
            Explainability analysis
        """

        explanation = {
            "prediction": prediction,
            "top_contributing_features": [],
            "feature_importance_breakdown": {},
            "decision_factors": [],
            "confidence_interpretation": "",
            "recommendations": []
        }

        try:
            if not self.strategy_predictor or not hasattr(self.strategy_predictor, 'feature_importances_'):
                explanation["error"] = "Model does not support explainability"
                return explanation

            # Get feature importance
            feature_names = list(features.keys())
            importance_scores = self.strategy_predictor.feature_importances_

            # Create importance mapping
            feature_importance = dict(zip(feature_names, importance_scores))
            explanation["feature_importance_breakdown"] = feature_importance

            # Get top contributing features
            sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            explanation["top_contributing_features"] = sorted_features[:5]

            # Generate decision factors
            decision_factors = []

            for feature_name, importance in sorted_features[:3]:
                feature_value = features[feature_name]

                # Interpret feature contribution
                if "is_market_maker" in feature_name and feature_value > 0.5:
                    decision_factors.append(f"Strong market maker behavior pattern (importance: {importance:.3f})")
                elif "win_rate" in feature_name and feature_value > 0.6:
                    decision_factors.append(f"High historical win rate suggests profitable strategy (importance: {importance:.3f})")
                elif "volatility" in feature_name and feature_value > 0.25:
                    decision_factors.append(f"High market volatility favors conservative approach (importance: {importance:.3f})")
                elif "trade_frequency" in feature_name and feature_value > 10:
                    decision_factors.append(f"High trade frequency indicates active strategy preference (importance: {importance:.3f})")

            explanation["decision_factors"] = decision_factors

            # Confidence interpretation
            confidence_level = "high" if explanation.get("confidence_score", 0) > 0.8 else "medium" if explanation.get("confidence_score", 0) > 0.6 else "low"
            explanation["confidence_interpretation"] = f"The model's {confidence_level} confidence in this prediction is based on strong alignment with historical patterns."

            # Generate recommendations
            if confidence_level == "low":
                explanation["recommendations"].append("Consider multiple strategies or reduce position size due to prediction uncertainty")
            if any("volatility" in factor for factor in decision_factors):
                explanation["recommendations"].append("Monitor market volatility closely as it significantly influences this prediction")

        except Exception as e:
            logger.error(f"Error generating model explainability: {e}")
            explanation["error"] = str(e)

        return explanation

    def get_model_health_status(self) -> Dict[str, Any]:
        """Get comprehensive model health and performance status."""

        health_status = {
            "overall_health": "unknown",
            "models_trained": {
                "strategy_predictor": self.strategy_predictor is not None,
                "performance_predictor": self.performance_predictor is not None,
                "reinforcement_learning": self.rl_agent is not None
            },
            "training_data_size": len(self.training_data),
            "last_training": None,
            "prediction_accuracy": self.prediction_accuracy,
            "drift_status": "unknown",
            "model_versions": {},
            "performance_metrics": {}
        }

        # Determine overall health
        trained_models = sum(health_status["models_trained"].values())
        if trained_models == 0:
            health_status["overall_health"] = "not_initialized"
        elif trained_models < 2:
            health_status["overall_health"] = "partial"
        elif len(self.training_data) < self.training_params["min_samples_for_training"]:
            health_status["overall_health"] = "insufficient_data"
        else:
            health_status["overall_health"] = "healthy"

        # Get latest training info
        if self.model_performance_history:
            latest_training = self.model_performance_history[-1]
            health_status["last_training"] = latest_training.get("training_timestamp")
            health_status["performance_metrics"] = latest_training.get("performance_metrics", {})

        # Get model versions
        if self.strategy_predictor and hasattr(self.strategy_predictor, '_model_version'):
            health_status["model_versions"]["strategy_predictor"] = self.strategy_predictor._model_version

        if self.performance_predictor and hasattr(self.performance_predictor, '_model_version'):
            health_status["model_versions"]["performance_predictor"] = self.performance_predictor._model_version

        # Drift status
        if self.model_health_metrics.get("drift_severity", 0) > 0.2:
            health_status["drift_status"] = "significant_drift"
        elif self.model_health_metrics.get("drift_severity", 0) > 0.1:
            health_status["drift_status"] = "minor_drift"
        else:
            health_status["drift_status"] = "stable"

        return health_status

    def save_ml_models(self):
        """Save trained ML models to disk."""

        try:
            model_dir = Path("data/ml_models")
            model_dir.mkdir(parents=True, exist_ok=True)

            # Save strategy predictor
            if self.strategy_predictor:
                model_path = model_dir / "strategy_predictor.pkl"
                joblib.dump(self.strategy_predictor, model_path)

            # Save performance predictor
            if self.performance_predictor:
                perf_path = model_dir / "performance_predictor.pkl"
                joblib.dump(self.performance_predictor, perf_path)

            # Save scalers and encoders
            scaler_path = model_dir / "feature_scaler.pkl"
            joblib.dump(self.feature_scaler, scaler_path)

            encoder_path = model_dir / "label_encoder.pkl"
            joblib.dump(self.label_encoder, encoder_path)

            # Save RL agent
            if self.rl_agent:
                rl_path = model_dir / "rl_agent.pkl"
                with open(rl_path, 'wb') as f:
                    pickle.dump(dict(self.rl_agent), f)

            # Save training data
            data_path = model_dir / "training_data.json"
            with open(data_path, 'w') as f:
                json.dump(self.training_data, f, indent=2, default=str)

            # Save model metadata
            metadata = {
                "saved_at": datetime.now().isoformat(),
                "model_versions": {},
                "training_samples": len(self.training_data),
                "performance_history": self.model_performance_history[-5:]  # Last 5 training sessions
            }

            if self.strategy_predictor and hasattr(self.strategy_predictor, '_model_version'):
                metadata["model_versions"]["strategy_predictor"] = self.strategy_predictor._model_version

            metadata_path = model_dir / "model_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)

            logger.info(f"💾 ML models saved to {model_dir}")

        except Exception as e:
            logger.error(f"Error saving ML models: {e}")

    def load_ml_models(self):
        """Load trained ML models from disk."""

        try:
            model_dir = Path("data/ml_models")

            # Load strategy predictor
            model_path = model_dir / "strategy_predictor.pkl"
            if model_path.exists():
                self.strategy_predictor = joblib.load(model_path)

            # Load performance predictor
            perf_path = model_dir / "performance_predictor.pkl"
            if perf_path.exists():
                self.performance_predictor = joblib.load(perf_path)

            # Load scalers and encoders
            scaler_path = model_dir / "feature_scaler.pkl"
            if scaler_path.exists():
                self.feature_scaler = joblib.load(scaler_path)

            encoder_path = model_dir / "label_encoder.pkl"
            if encoder_path.exists():
                self.label_encoder = joblib.load(encoder_path)

            # Load RL agent
            rl_path = model_dir / "rl_agent.pkl"
            if rl_path.exists():
                with open(rl_path, 'rb') as f:
                    self.rl_agent = pickle.load(f)

            # Load training data
            data_path = model_dir / "training_data.json"
            if data_path.exists():
                with open(data_path, 'r') as f:
                    self.training_data = json.load(f)

            logger.info(f"📊 ML models loaded from {model_dir}")

        except Exception as e:
            logger.error(f"Error loading ML models: {e}")

    async def add_training_example(
        self,
        features: Dict[str, float],
        selected_strategy: str,
        outcome: Optional[Dict[str, Any]] = None
    ):
        """Add a training example for model improvement."""

        training_example = {
            "timestamp": datetime.now().isoformat(),
            "features": features,
            "selected_strategy": selected_strategy,
            "outcome": outcome
        }

        self.training_data.append(training_example)

        # Keep only recent examples to prevent memory issues
        max_training_examples = 10000
        if len(self.training_data) > max_training_examples:
            self.training_data = self.training_data[-max_training_examples:]

    async def run_model_monitoring_loop(self, check_interval_minutes: int = 60):
        """Run continuous model monitoring and retraining."""

        logger.info(f"🔍 Starting model monitoring loop (check every {check_interval_minutes} minutes)")

        while True:
            try:
                # Check model health
                health_status = self.get_model_health_status()

                # Check for model drift
                recent_predictions = []  # Would need to collect recent predictions
                if len(recent_predictions) >= 100:
                    drift_results = await self.detect_model_drift(recent_predictions)

                    if drift_results["retraining_recommended"]:
                        logger.warning("📈 Model drift detected, triggering retraining")
                        await self.train_strategy_predictor(force_retrain=True)

                # Check if retraining is needed based on data size
                if len(self.training_data) >= self.training_params["min_samples_for_training"] * 2:
                    # Retrain with expanded dataset
                    await self.train_strategy_predictor(force_retrain=True)

                await asyncio.sleep(check_interval_minutes * 60)

            except Exception as e:
                logger.error(f"Error in model monitoring loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
