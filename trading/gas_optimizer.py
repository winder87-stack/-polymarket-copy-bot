"""Advanced Gas Price Optimization System.

This module provides comprehensive gas price optimization including:
- Gas price prediction using historical data and time-series analysis
- MEV-resistant transaction ordering to reduce front-running vulnerability
- Dynamic gas multiplier based on market volatility
- Fallback strategies during gas spikes
- Cost-benefit analysis for trade execution timing

All gas prices are handled in gwei (1 gwei = 10^9 wei).
"""

import logging
import time
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from web3 import Web3


logger = logging.getLogger(__name__)

# Gas Price Prediction Constants
DEFAULT_HISTORY_SIZE = 1000  # Number of historical gas prices to track
SHORT_TERM_WINDOW = 10  # Short-term moving average window
MEDIUM_TERM_WINDOW = 50  # Medium-term moving average window
LONG_TERM_WINDOW = 200  # Long-term moving average window
DEFAULT_PREDICTION_HORIZON_MINUTES = 5  # Default prediction horizon
DEFAULT_GAS_PRICE_GWEI = 50.0  # Default gas price if unavailable
GAS_SPIKE_THRESHOLD_MULTIPLIER = 2.0  # Multiplier above average for spike detection

# Moving Average Weights
SHORT_MA_WEIGHT = 0.5  # Weight for short-term moving average
MEDIUM_MA_WEIGHT = 0.3  # Weight for medium-term moving average
LONG_MA_WEIGHT = 0.2  # Weight for long-term moving average
TREND_ADJUSTMENT_FACTOR = 0.1  # Factor for trend adjustment

# Time-of-Day Constants (UTC)
PEAK_HOURS_START = 14  # Peak hours start (2 PM UTC)
PEAK_HOURS_END = 20  # Peak hours end (8 PM UTC)
OFF_PEAK_HOURS_START = 0  # Off-peak hours start (midnight UTC)
OFF_PEAK_HOURS_END = 6  # Off-peak hours end (6 AM UTC)
PEAK_HOURS_MULTIPLIER = 1.15  # Gas multiplier during peak hours
OFF_PEAK_HOURS_MULTIPLIER = 0.90  # Gas multiplier during off-peak hours
WEEKEND_DAY_START = 5  # Saturday (weekday 5)
WEEKEND_MULTIPLIER = 0.95  # Gas multiplier on weekends

# MEV Protection Constants
DEFAULT_MAX_BATCH_SIZE = 5  # Maximum transactions per batch
HIGH_MEV_RISK_THRESHOLD = 70  # MEV risk score threshold for high risk
MEDIUM_MEV_RISK_THRESHOLD = 40  # MEV risk score threshold for medium risk
MAX_TRADE_SIZE_FOR_MEV_SCORE = 1000.0  # $1000 trade size for max MEV score
MAX_PRICE_IMPACT_FOR_MEV_SCORE = 0.01  # 1% price impact for max MEV score
MAX_VOLATILITY_FOR_MEV_SCORE = 1.0  # 1.0 volatility for max MEV score
MAX_URGENCY_FOR_MEV_SCORE = 5  # Maximum urgency value
MEV_RISK_WEIGHT_SIZE = 0.3  # Weight for trade size in MEV risk
MEV_RISK_WEIGHT_IMPACT = 0.3  # Weight for price impact in MEV risk
MEV_RISK_WEIGHT_VOLATILITY = 0.2  # Weight for volatility in MEV risk
MEV_RISK_WEIGHT_URGENCY = 0.2  # Weight for urgency in MEV risk
HIGH_RISK_GAS_ADJUSTMENT = 1.05  # Gas adjustment for high MEV risk
MEDIUM_RISK_GAS_ADJUSTMENT = 1.02  # Gas adjustment for medium MEV risk
HIGH_RISK_DELAY_MIN = 1.0  # Minimum delay for high risk (seconds)
HIGH_RISK_DELAY_MAX = 3.0  # Maximum delay for high risk (seconds)
MEDIUM_RISK_DELAY_MIN = 0.5  # Minimum delay for medium risk (seconds)
MEDIUM_RISK_DELAY_MAX = 1.5  # Maximum delay for medium risk (seconds)

# Gas Optimization Mode Constants
CONSERVATIVE_BASE_MULTIPLIER = 1.0  # No premium for conservative mode
CONSERVATIVE_VOLATILITY_MIN = 0.95  # Minimum volatility multiplier
CONSERVATIVE_VOLATILITY_MAX = 1.05  # Maximum volatility multiplier
CONSERVATIVE_SPIKE_THRESHOLD = 1.5  # Lower spike threshold
CONSERVATIVE_MAX_WAIT_MINUTES = 30  # Willing to wait longer
CONSERVATIVE_COST_PRIORITY = 0.8  # Prioritize cost
CONSERVATIVE_SPEED_PRIORITY = 0.2  # Less priority on speed

AGGRESSIVE_BASE_MULTIPLIER = 1.2  # Higher premium for aggressive mode
AGGRESSIVE_VOLATILITY_MIN = 1.1  # Minimum volatility multiplier
AGGRESSIVE_VOLATILITY_MAX = 1.5  # Maximum volatility multiplier
AGGRESSIVE_SPIKE_THRESHOLD = 2.5  # Higher spike threshold
AGGRESSIVE_MAX_WAIT_MINUTES = 5  # Less willing to wait
AGGRESSIVE_COST_PRIORITY = 0.2  # Less priority on cost
AGGRESSIVE_SPEED_PRIORITY = 0.8  # Prioritize speed

BALANCED_BASE_MULTIPLIER = 1.1  # Moderate premium for balanced mode
BALANCED_VOLATILITY_MIN = 1.0  # Minimum volatility multiplier
BALANCED_VOLATILITY_MAX = 1.2  # Maximum volatility multiplier
BALANCED_SPIKE_THRESHOLD = 2.0  # Moderate spike threshold
BALANCED_MAX_WAIT_MINUTES = 15  # Moderate wait time
BALANCED_COST_PRIORITY = 0.5  # Balanced cost/speed priority
BALANCED_SPEED_PRIORITY = 0.5  # Balanced cost/speed priority

# Cost-Benefit Analysis Constants
MIN_SAVINGS_THRESHOLD_USD = 0.50  # Minimum $0.50 savings to wait
MIN_SAVINGS_THRESHOLD_PCT = 5.0  # Minimum 5% savings percentage
MIN_CONFIDENCE_FOR_WAIT = 0.5  # Minimum confidence to recommend waiting
DEFAULT_ETH_PRICE_USD = 2000.0  # Default ETH price for cost calculations
DEFAULT_GAS_LIMIT = 300000  # Default gas limit for transactions
GWEI_TO_WEI_FACTOR = 1e9  # Conversion factor: 1 gwei = 10^9 wei

# Urgency Adjustment Constants
MAX_URGENCY_ADJUSTMENT = 0.1  # Up to 10% gas increase for urgent trades
URGENCY_MULTIPLIER_FACTOR = 0.1  # Factor for urgency multiplier calculation

# Response Time Calculation Constants
RESPONSE_TIME_AVG_WEIGHT_RECENT = 0.1  # Weight for recent response time
RESPONSE_TIME_AVG_WEIGHT_HISTORICAL = 0.9  # Weight for historical average


class GasOptimizationMode(Enum):
    """Gas optimization modes"""

    CONSERVATIVE = "conservative"  # Minimize costs, accept slower execution
    BALANCED = "balanced"  # Balance cost and speed
    AGGRESSIVE = "aggressive"  # Prioritize speed, accept higher costs


class GasSpikeStrategy(Enum):
    """Strategies for handling gas spikes"""

    WAIT = "wait"  # Wait for gas to decrease
    EXECUTE = "execute"  # Execute immediately despite high gas
    DEFER = "defer"  # Defer to next optimal window
    BATCH = "batch"  # Batch with other pending trades


class GasPricePredictor:
    """
    Predicts gas prices using historical data and time-series analysis.

    Uses:
    - Moving averages (short, medium, long-term)
    - Volatility analysis
    - Time-of-day patterns
    - Day-of-week patterns
    - Recent trend analysis
    """

    def __init__(self, history_size: int = DEFAULT_HISTORY_SIZE) -> None:
        """Initialize gas price predictor.

        Creates a predictor that tracks historical gas prices and uses
        time-series analysis to predict future gas prices.

        Args:
            history_size: Number of historical gas prices to track.
                Defaults to DEFAULT_HISTORY_SIZE.
        """
        self.history_size = history_size
        self.gas_history: deque = deque(maxlen=history_size)
        self.timestamp_history: deque = deque(maxlen=history_size)

        # Prediction parameters
        self.short_window = SHORT_TERM_WINDOW
        self.medium_window = MEDIUM_TERM_WINDOW
        self.long_window = LONG_TERM_WINDOW

        logger.info("Gas price predictor initialized")

    def add_gas_price(
        self, gas_price_gwei: float, timestamp: Optional[float] = None
    ) -> None:
        """Add gas price observation to history.

        Adds a new gas price observation to the historical data used for
        prediction. The history is maintained as a deque with maximum size
        to prevent unbounded memory growth.

        Args:
            gas_price_gwei: Gas price in gwei (1 gwei = 10^9 wei).
            timestamp: Unix timestamp of the observation.
                Defaults to current time if not provided.
        """
        if timestamp is None:
            timestamp = time.time()

        self.gas_history.append(gas_price_gwei)
        self.timestamp_history.append(timestamp)

    def predict_gas_price(
        self,
        prediction_horizon_minutes: int = DEFAULT_PREDICTION_HORIZON_MINUTES,
    ) -> Dict[str, Any]:
        """Predict gas price for future time horizon.

        Uses time-series analysis including moving averages, volatility,
        trend analysis, and time-of-day patterns to predict future gas prices.

        Args:
            prediction_horizon_minutes: Minutes into future to predict.
                Defaults to DEFAULT_PREDICTION_HORIZON_MINUTES.

        Returns:
            Dictionary containing:
            - predicted_price_gwei: Predicted gas price in gwei
            - confidence: Prediction confidence (0.0-1.0)
            - method: Prediction method used
            - lower_bound: Lower confidence bound in gwei
            - upper_bound: Upper confidence bound in gwei
            - volatility: Current gas price volatility
            - trend: Recent trend (positive = increasing)
            - short_ma: Short-term moving average
            - medium_ma: Medium-term moving average
            - long_ma: Long-term moving average
        """
        CONFIDENCE_BOUND_MULTIPLIER_LOWER = 0.9  # 10% below for lower bound
        CONFIDENCE_BOUND_MULTIPLIER_UPPER = 1.1  # 10% above for upper bound

        if len(self.gas_history) < self.short_window:
            # Not enough data - return current price
            current = (
                self.gas_history[-1] if self.gas_history else DEFAULT_GAS_PRICE_GWEI
            )
            return {
                "predicted_price_gwei": current,
                "confidence": 0.0,
                "method": "insufficient_data",
                "lower_bound": current * CONFIDENCE_BOUND_MULTIPLIER_LOWER,
                "upper_bound": current * CONFIDENCE_BOUND_MULTIPLIER_UPPER,
            }

        gas_array = np.array(self.gas_history)

        # Calculate moving averages
        short_ma = (
            np.mean(gas_array[-self.short_window :])
            if len(gas_array) >= self.short_window
            else gas_array[-1]
        )
        medium_ma = (
            np.mean(gas_array[-self.medium_window :])
            if len(gas_array) >= self.medium_window
            else short_ma
        )
        long_ma = (
            np.mean(gas_array[-self.long_window :])
            if len(gas_array) >= self.long_window
            else medium_ma
        )

        # Calculate volatility
        volatility = (
            np.std(gas_array[-self.short_window :])
            if len(gas_array) >= self.short_window
            else 0.0
        )

        # Trend analysis
        recent_trend = (
            (gas_array[-1] - gas_array[-min(10, len(gas_array))])
            / min(10, len(gas_array))
            if len(gas_array) > 1
            else 0.0
        )

        # Time-of-day adjustment (gas tends to be higher during peak hours)
        now = datetime.now(timezone.utc)
        hour = now.hour
        # Peak hours: US trading hours (14:00-20:00 UTC)
        if PEAK_HOURS_START <= hour <= PEAK_HOURS_END:
            time_multiplier = PEAK_HOURS_MULTIPLIER
        elif OFF_PEAK_HOURS_START <= hour <= OFF_PEAK_HOURS_END:
            time_multiplier = OFF_PEAK_HOURS_MULTIPLIER
        else:
            time_multiplier = 1.0

        # Day-of-week adjustment
        weekday = now.weekday()
        if weekday >= WEEKEND_DAY_START:  # Weekend
            day_multiplier = WEEKEND_MULTIPLIER
        else:
            day_multiplier = 1.0

        # Predict future price using weighted combination of moving averages
        base_prediction = (
            short_ma * SHORT_MA_WEIGHT
            + medium_ma * MEDIUM_MA_WEIGHT
            + long_ma * LONG_MA_WEIGHT
        )
        trend_adjustment = (
            recent_trend * prediction_horizon_minutes * TREND_ADJUSTMENT_FACTOR
        )
        predicted_price = base_prediction + trend_adjustment

        # Apply time adjustments
        predicted_price *= time_multiplier * day_multiplier

        # Confidence calculation (based on data quality and volatility)
        data_quality = min(1.0, len(self.gas_history) / self.long_window)
        volatility_factor = max(0.0, 1.0 - (volatility / base_prediction))
        confidence = data_quality * volatility_factor

        # Calculate bounds (95% confidence interval)
        std_dev = volatility * np.sqrt(prediction_horizon_minutes / 60)
        lower_bound = max(0.1, predicted_price - 2 * std_dev)
        upper_bound = predicted_price + 2 * std_dev

        return {
            "predicted_price_gwei": float(predicted_price),
            "confidence": float(confidence),
            "method": "time_series_analysis",
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
            "volatility": float(volatility),
            "trend": float(recent_trend),
            "short_ma": float(short_ma),
            "medium_ma": float(medium_ma),
            "long_ma": float(long_ma),
        }

    def detect_gas_spike(
        self,
        current_gas: float,
        threshold_multiplier: float = GAS_SPIKE_THRESHOLD_MULTIPLIER,
    ) -> bool:
        """Detect if current gas price is a spike.

        Compares current gas price against recent average to detect
        significant price increases that may indicate network congestion
        or unusual market conditions.

        Args:
            current_gas: Current gas price in gwei.
            threshold_multiplier: Multiplier above recent average to
                consider a spike. Defaults to GAS_SPIKE_THRESHOLD_MULTIPLIER.

        Returns:
            True if current gas price exceeds threshold_multiplier times
            the recent average, False otherwise.
        """
        if len(self.gas_history) < self.medium_window:
            return False

        recent_avg = np.mean(list(self.gas_history)[-self.medium_window :])
        return current_gas > recent_avg * threshold_multiplier

    def get_volatility(self) -> float:
        """Get current gas price volatility.

        Calculates standard deviation of recent gas prices as a measure
        of volatility. Higher volatility indicates more unpredictable
        gas prices.

        Returns:
            Volatility as standard deviation of recent gas prices.
            Returns 0.0 if insufficient data available.
        """
        if len(self.gas_history) < self.short_window:
            return 0.0

        return float(np.std(list(self.gas_history)[-self.short_window :]))


class MEVProtection:
    """MEV (Maximal Extractable Value) protection mechanisms.

    Implements strategies to reduce vulnerability to various MEV attacks:
    - Front-running: Attackers execute trades before yours
    - Sandwich attacks: Attackers trade before and after yours
    - Back-running: Attackers execute trades immediately after yours

    Uses transaction batching, randomization, and timing strategies to
    reduce predictability and MEV extraction opportunities.
    """

    def __init__(self) -> None:
        """Initialize MEV protection system.

        Creates empty transaction queue and pending transactions dictionary
        for managing MEV-protected transaction ordering.
        """
        self.pending_transactions: Dict[str, Dict[str, Any]] = {}
        self.transaction_queue: List[Dict[str, Any]] = []

    def add_transaction(
        self, tx_hash: str, trade_data: Dict[str, Any], priority: int = 0
    ) -> None:
        """Add transaction to MEV-protected queue.

        Adds a transaction to the queue for MEV-protected ordering.
        Transactions are grouped by priority and randomized within
        priority groups to reduce predictability.

        Args:
            tx_hash: Unique transaction hash identifier.
            trade_data: Dictionary containing trade information including:
                - amount: Trade amount
                - price: Trade price
                - gas_price: Gas price for transaction
                - Other trade-specific fields
            priority: Priority level (higher = more urgent).
                Defaults to 0 (normal priority).
        """
        self.pending_transactions[tx_hash] = {
            "trade_data": trade_data,
            "priority": priority,
            "timestamp": time.time(),
            "gas_price": trade_data.get("gas_price", 0),
        }

    def get_optimal_ordering(
        self, max_batch_size: int = DEFAULT_MAX_BATCH_SIZE
    ) -> List[Dict[str, Any]]:
        """
        Get optimal transaction ordering to reduce MEV vulnerability.

        Strategies:
        1. Batch similar trades together (harder to front-run)
        2. Randomize order within batches (reduce predictability)
        3. Add small random delays (reduce timing attacks)
        4. Use private mempool when available

        Args:
            max_batch_size: Maximum transactions per batch

        Returns:
            Ordered list of transactions
        """
        if not self.pending_transactions:
            return []

        # Group by priority
        priority_groups: Dict[int, List[Dict[str, Any]]] = {}
        for tx_hash, tx_data in self.pending_transactions.items():
            priority = tx_data["priority"]
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append({**tx_data, "tx_hash": tx_hash})

        # Sort by priority (highest first)
        sorted_priorities = sorted(priority_groups.keys(), reverse=True)

        # Build ordered list
        ordered_transactions = []
        for priority in sorted_priorities:
            transactions = priority_groups[priority]

            # Randomize within priority group (reduce predictability)
            np.random.shuffle(transactions)

            # Batch transactions
            for i in range(0, len(transactions), max_batch_size):
                batch = transactions[i : i + max_batch_size]
                ordered_transactions.extend(batch)

        return ordered_transactions

    def calculate_mev_risk_score(self, trade_data: Dict[str, Any]) -> float:
        """Calculate MEV risk score for a trade.

        Evaluates multiple factors to determine how attractive a trade
        is to MEV extractors. Higher scores indicate higher risk.

        Factors considered:
        - Trade size: Larger trades are more attractive to MEV
        - Price impact: Higher slippage creates more MEV opportunity
        - Market volatility: Higher volatility increases MEV opportunity
        - Time sensitivity: Urgent trades are more vulnerable

        Args:
            trade_data: Dictionary containing:
                - amount: Trade amount
                - price: Trade price
                - price_impact: Expected price impact (0.0-1.0)
                - volatility: Market volatility (0.0-1.0)
                - urgency: Trade urgency (0-5 scale)

        Returns:
            MEV risk score between 0.0 and 100.0, where:
            - 0-40: Low risk (minimal protection needed)
            - 40-70: Medium risk (moderate protection)
            - 70-100: High risk (aggressive protection needed)
        """
        trade_size = abs(trade_data.get("amount", 0) * trade_data.get("price", 0))
        price_impact = trade_data.get("price_impact", 0)
        volatility = trade_data.get("volatility", 0)
        urgency = trade_data.get("urgency", 0)

        # Normalize factors to 0-100 scale
        size_score = min(100, trade_size / MAX_TRADE_SIZE_FOR_MEV_SCORE)
        impact_score = min(100, price_impact / MAX_PRICE_IMPACT_FOR_MEV_SCORE * 100)
        volatility_score = min(100, volatility / MAX_VOLATILITY_FOR_MEV_SCORE * 100)
        urgency_score = (urgency / MAX_URGENCY_FOR_MEV_SCORE) * 100

        # Weighted combination
        risk_score = (
            size_score * MEV_RISK_WEIGHT_SIZE
            + impact_score * MEV_RISK_WEIGHT_IMPACT
            + volatility_score * MEV_RISK_WEIGHT_VOLATILITY
            + urgency_score * MEV_RISK_WEIGHT_URGENCY
        )

        return min(100, max(0, risk_score))

    def get_mev_protection_strategy(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get recommended MEV protection strategy for a trade.

        Analyzes trade characteristics and returns a protection strategy
        with specific recommendations for reducing MEV vulnerability.

        Args:
            trade_data: Dictionary containing trade information including
                amount, price, price_impact, volatility, and urgency.

        Returns:
            Dictionary containing:
            - risk_score: Calculated MEV risk score (0-100)
            - recommendations: List of protection recommendations
            - gas_adjustment: Recommended gas price multiplier
            - delay_seconds: Recommended delay before execution
            - batch_with_others: Whether to batch with other trades
        """
        risk_score = self.calculate_mev_risk_score(trade_data)

        strategy = {
            "risk_score": risk_score,
            "recommendations": [],
            "gas_adjustment": 1.0,
            "delay_seconds": 0,
            "batch_with_others": False,
        }

        if risk_score > HIGH_MEV_RISK_THRESHOLD:
            # High risk - aggressive protection
            strategy["recommendations"].append("Use private mempool if available")
            strategy["recommendations"].append(
                f"Add random delay ({HIGH_RISK_DELAY_MIN}-{HIGH_RISK_DELAY_MAX} seconds)"
            )
            strategy["recommendations"].append("Batch with other trades")
            strategy["gas_adjustment"] = HIGH_RISK_GAS_ADJUSTMENT
            strategy["delay_seconds"] = np.random.uniform(
                HIGH_RISK_DELAY_MIN, HIGH_RISK_DELAY_MAX
            )
            strategy["batch_with_others"] = True

        elif risk_score > MEDIUM_MEV_RISK_THRESHOLD:
            # Medium risk - moderate protection
            strategy["recommendations"].append("Add small random delay")
            strategy["recommendations"].append("Consider batching")
            strategy["gas_adjustment"] = MEDIUM_RISK_GAS_ADJUSTMENT
            strategy["delay_seconds"] = np.random.uniform(
                MEDIUM_RISK_DELAY_MIN, MEDIUM_RISK_DELAY_MAX
            )
            strategy["batch_with_others"] = len(self.pending_transactions) > 1

        else:
            # Low risk - minimal protection
            strategy["recommendations"].append("Standard execution")
            strategy["gas_adjustment"] = 1.0
            strategy["delay_seconds"] = 0

        return strategy


class GasOptimizer:
    """
    Advanced gas price optimizer with MEV protection and cost-benefit analysis.

    Features:
    - Historical gas price prediction
    - MEV-resistant transaction ordering
    - Dynamic gas multiplier based on volatility
    - Fallback strategies during gas spikes
    - Cost-benefit analysis for execution timing
    """

    def __init__(
        self,
        web3: Web3,
        mode: GasOptimizationMode = GasOptimizationMode.BALANCED,
        update_interval_seconds: int = 30,
    ) -> None:
        """
        Initialize gas optimizer.

        Args:
            web3: Web3 instance for gas price queries
            mode: Optimization mode (conservative/balanced/aggressive)
            update_interval_seconds: How often to update gas price history
        """
        self.web3 = web3
        self.mode = mode
        self.update_interval = update_interval_seconds

        # Components
        self.predictor = GasPricePredictor()
        self.mev_protection = MEVProtection()

        # Gas price cache
        self.current_gas_price: Optional[float] = None
        self.last_update_time: Optional[float] = None

        # Mode-specific parameters
        self.mode_params = self._get_mode_parameters()

        # Performance tracking
        self.metrics = {
            "total_optimizations": 0,
            "gas_savings_usd": 0.0,
            "spike_detections": 0,
            "deferred_trades": 0,
            "batched_trades": 0,
        }

        logger.info(f"Gas optimizer initialized in {mode.value} mode")

    def _get_mode_parameters(self) -> Dict[str, Any]:
        """Get parameters for current optimization mode.

        Returns:
            Dictionary containing mode-specific parameters:
            - base_multiplier: Base gas price multiplier
            - volatility_multiplier_range: (min, max) volatility multipliers
            - spike_threshold: Threshold multiplier for gas spike detection
            - max_wait_minutes: Maximum minutes to wait for gas to decrease
            - cost_priority: Priority weight for cost optimization (0.0-1.0)
            - speed_priority: Priority weight for speed optimization (0.0-1.0)
        """
        if self.mode == GasOptimizationMode.CONSERVATIVE:
            return {
                "base_multiplier": CONSERVATIVE_BASE_MULTIPLIER,
                "volatility_multiplier_range": (
                    CONSERVATIVE_VOLATILITY_MIN,
                    CONSERVATIVE_VOLATILITY_MAX,
                ),
                "spike_threshold": CONSERVATIVE_SPIKE_THRESHOLD,
                "max_wait_minutes": CONSERVATIVE_MAX_WAIT_MINUTES,
                "cost_priority": CONSERVATIVE_COST_PRIORITY,
                "speed_priority": CONSERVATIVE_SPEED_PRIORITY,
            }
        elif self.mode == GasOptimizationMode.AGGRESSIVE:
            return {
                "base_multiplier": AGGRESSIVE_BASE_MULTIPLIER,
                "volatility_multiplier_range": (
                    AGGRESSIVE_VOLATILITY_MIN,
                    AGGRESSIVE_VOLATILITY_MAX,
                ),
                "spike_threshold": AGGRESSIVE_SPIKE_THRESHOLD,
                "max_wait_minutes": AGGRESSIVE_MAX_WAIT_MINUTES,
                "cost_priority": AGGRESSIVE_COST_PRIORITY,
                "speed_priority": AGGRESSIVE_SPEED_PRIORITY,
            }
        else:  # BALANCED
            return {
                "base_multiplier": BALANCED_BASE_MULTIPLIER,
                "volatility_multiplier_range": (
                    BALANCED_VOLATILITY_MIN,
                    BALANCED_VOLATILITY_MAX,
                ),
                "spike_threshold": BALANCED_SPIKE_THRESHOLD,
                "max_wait_minutes": BALANCED_MAX_WAIT_MINUTES,
                "cost_priority": BALANCED_COST_PRIORITY,
                "speed_priority": BALANCED_SPEED_PRIORITY,
            }

    async def update_gas_price(self) -> float:
        """Update current gas price from network.

        Fetches the current gas price from the Web3 provider and adds
        it to the predictor's history for future predictions.

        Returns:
            Current gas price in gwei. Returns DEFAULT_GAS_PRICE_GWEI
            if update fails and no previous price is available.

        Raises:
            Exception: If Web3 provider call fails (logged but not raised).
        """
        try:
            gas_price = self.web3.eth.gas_price
            gas_price_gwei = self.web3.from_wei(gas_price, "gwei")

            self.current_gas_price = float(gas_price_gwei)
            self.last_update_time = time.time()

            # Add to predictor history
            self.predictor.add_gas_price(self.current_gas_price)

            logger.debug(f"⛽ Updated gas price: {self.current_gas_price:.2f} gwei")

            return self.current_gas_price

        except Exception as e:
            logger.error(f"❌ Error updating gas price: {e}")
            # Return last known price or default
            return self.current_gas_price or DEFAULT_GAS_PRICE_GWEI

    async def get_optimal_gas_price(
        self,
        trade_data: Optional[Dict[str, Any]] = None,
        urgency: float = 0.5,
    ) -> Dict[str, Any]:
        """Get optimal gas price for trade execution.

        Calculates optimal gas price based on current market conditions,
        predicted future prices, volatility, MEV risk, and trade urgency.
        Considers optimization mode (conservative/balanced/aggressive).

        Args:
            trade_data: Optional trade data for MEV risk assessment.
                If provided, includes MEV protection recommendations.
            urgency: Trade urgency factor (0.0-1.0, where 1.0 = most urgent).
                Higher urgency increases recommended gas price.
                Defaults to 0.5 (moderate urgency).

        Returns:
            Dictionary containing:
            - optimal_gas_price_gwei: Recommended gas price in gwei
            - current_gas_price_gwei: Current market gas price
            - predicted_gas_price_gwei: Predicted future gas price
            - confidence: Prediction confidence (0.0-1.0)
            - multiplier: Applied gas price multiplier
            - volatility: Current market volatility
            - is_spike: Whether gas spike is detected
            - spike_strategy: Strategy for handling spike (if applicable)
            - mev_strategy: MEV protection strategy (if trade_data provided)
            - recommendation: Human-readable recommendation string
        """
        # Update gas price if needed
        if (
            self.last_update_time is None
            or time.time() - self.last_update_time > self.update_interval
        ):
            await self.update_gas_price()

        current_gas = self.current_gas_price or DEFAULT_GAS_PRICE_GWEI

        # Get prediction
        prediction = self.predictor.predict_gas_price(
            prediction_horizon_minutes=DEFAULT_PREDICTION_HORIZON_MINUTES
        )

        # Calculate volatility-based multiplier
        volatility = self.predictor.get_volatility()
        volatility_multiplier = self._calculate_volatility_multiplier(
            volatility, current_gas
        )

        # Check for gas spike
        is_spike = self.predictor.detect_gas_spike(
            current_gas, threshold_multiplier=self.mode_params["spike_threshold"]
        )

        if is_spike:
            self.metrics["spike_detections"] += 1

        # Get MEV protection strategy if trade data provided
        mev_strategy = None
        if trade_data:
            mev_strategy = self.mev_protection.get_mev_protection_strategy(trade_data)

        # Calculate optimal gas price
        base_multiplier = self.mode_params["base_multiplier"]
        mev_adjustment = mev_strategy["gas_adjustment"] if mev_strategy else 1.0

        # Combine multipliers
        optimal_multiplier = base_multiplier * volatility_multiplier * mev_adjustment

        # Apply urgency adjustment
        urgency_adjustment = 1.0 + (urgency * MAX_URGENCY_ADJUSTMENT)
        optimal_multiplier *= urgency_adjustment

        optimal_gas_price = current_gas * optimal_multiplier

        # Get spike strategy if applicable
        spike_strategy = None
        if is_spike:
            spike_strategy = self._get_spike_strategy(current_gas, prediction)

        result = {
            "optimal_gas_price_gwei": float(optimal_gas_price),
            "current_gas_price_gwei": float(current_gas),
            "predicted_gas_price_gwei": prediction["predicted_price_gwei"],
            "confidence": prediction["confidence"],
            "multiplier": float(optimal_multiplier),
            "volatility": float(volatility),
            "is_spike": is_spike,
            "spike_strategy": spike_strategy,
            "mev_strategy": mev_strategy,
            "recommendation": self._generate_recommendation(
                current_gas, optimal_gas_price, is_spike, spike_strategy
            ),
        }

        self.metrics["total_optimizations"] += 1

        return result

    def _calculate_volatility_multiplier(
        self, volatility: float, current_gas: float
    ) -> float:
        """Calculate gas multiplier based on volatility.

        Adjusts gas price multiplier based on market volatility. Higher
        volatility results in higher multipliers to ensure execution,
        while lower volatility allows for cost savings.

        Args:
            volatility: Gas price volatility (standard deviation).
            current_gas: Current gas price in gwei.

        Returns:
            Volatility-based multiplier within the range specified by
            the current optimization mode's volatility_multiplier_range.
        """
        if current_gas == 0:
            return 1.0

        volatility_ratio = volatility / current_gas
        min_mult, max_mult = self.mode_params["volatility_multiplier_range"]

        # Higher volatility = higher multiplier
        multiplier = min_mult + (volatility_ratio * (max_mult - min_mult) * 2)
        multiplier = max(min_mult, min(max_mult, multiplier))

        return multiplier

    def _get_spike_strategy(
        self, current_gas: float, prediction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get strategy for handling gas spike.

        Determines the best strategy when a gas spike is detected based
        on predicted future prices and optimization mode.

        Args:
            current_gas: Current gas price in gwei.
            prediction: Gas price prediction dictionary containing:
                - predicted_price_gwei: Predicted future price
                - lower_bound: Lower confidence bound

        Returns:
            Dictionary containing:
            - strategy: One of WAIT, EXECUTE, DEFER, or BATCH
            - wait_minutes: Minutes to wait (if strategy is WAIT)
            - expected_savings_pct: Expected savings percentage
            - reason: Human-readable explanation
        """
        predicted_price = prediction["predicted_price_gwei"]
        predicted_lower = prediction["lower_bound"]

        # If predicted to decrease significantly, wait
        if predicted_lower < current_gas * 0.8:
            wait_minutes = self.mode_params["max_wait_minutes"]
            return {
                "strategy": GasSpikeStrategy.WAIT.value,
                "wait_minutes": wait_minutes,
                "expected_savings_pct": (current_gas - predicted_lower)
                / current_gas
                * 100,
                "reason": f"Gas predicted to drop to {predicted_lower:.2f} gwei",
            }

        # If predicted to stay high, execute now or defer
        if predicted_price > current_gas * 0.95:
            if self.mode == GasOptimizationMode.AGGRESSIVE:
                return {
                    "strategy": GasSpikeStrategy.EXECUTE.value,
                    "reason": "Gas predicted to stay high - execute now",
                }
            else:
                return {
                    "strategy": GasSpikeStrategy.DEFER.value,
                    "reason": "Gas spike detected - defer to next window",
                }

        # Default: batch with other trades
        return {
            "strategy": GasSpikeStrategy.BATCH.value,
            "reason": "Batch trades to optimize gas costs",
        }

    def _generate_recommendation(
        self,
        current_gas: float,
        optimal_gas: float,
        is_spike: bool,
        spike_strategy: Optional[Dict[str, Any]],
    ) -> str:
        """Generate human-readable recommendation.

        Creates a user-friendly recommendation string explaining the
        optimal gas price and any special considerations.

        Args:
            current_gas: Current market gas price in gwei.
            optimal_gas: Calculated optimal gas price in gwei.
            is_spike: Whether a gas spike was detected.
            spike_strategy: Optional spike handling strategy dictionary.

        Returns:
            Human-readable recommendation string.
        """
        if is_spike and spike_strategy:
            strategy = spike_strategy["strategy"]
            if strategy == GasSpikeStrategy.WAIT.value:
                return (
                    f"Gas spike detected ({current_gas:.2f} gwei). "
                    f"Wait {spike_strategy.get('wait_minutes', 5)} minutes for predicted drop. "
                    f"Expected savings: {spike_strategy.get('expected_savings_pct', 0):.1f}%"
                )
            elif strategy == GasSpikeStrategy.DEFER.value:
                return (
                    f"Gas spike detected ({current_gas:.2f} gwei). "
                    "Defer execution to next optimal window."
                )
            elif strategy == GasSpikeStrategy.BATCH.value:
                return (
                    f"Gas spike detected ({current_gas:.2f} gwei). "
                    "Batch with other pending trades to optimize costs."
                )

        return (
            f"Optimal gas price: {optimal_gas:.2f} gwei "
            f"(current: {current_gas:.2f} gwei, multiplier: {optimal_gas / current_gas:.2f}x)"
        )

    async def analyze_execution_timing(
        self,
        trade_data: Dict[str, Any],
        max_wait_minutes: int = BALANCED_MAX_WAIT_MINUTES,
    ) -> Dict[str, Any]:
        """Analyze cost-benefit of executing trade now vs waiting.

        Compares gas costs at different time horizons to determine if
        waiting would result in significant cost savings. Considers
        prediction confidence and minimum savings thresholds.

        Args:
            trade_data: Dictionary containing:
                - amount: Trade amount
                - price: Trade price
                - gas_limit: Gas limit for transaction
                - eth_price_usd: Current ETH price in USD
            max_wait_minutes: Maximum minutes to consider waiting.
                Defaults to BALANCED_MAX_WAIT_MINUTES.

        Returns:
            Dictionary containing:
            - current_cost_usd: Gas cost if executed now
            - optimal_cost_usd: Gas cost at optimal timing
            - optimal_wait_minutes: Minutes to wait for optimal cost
            - savings_usd: Potential savings in USD
            - savings_pct: Potential savings percentage
            - should_wait: Whether waiting is recommended
            - timing_analysis: Detailed analysis for each time horizon
            - recommendation: Human-readable recommendation
        """
        current_gas = self.current_gas_price or 50.0

        # Get predictions for different time horizons
        predictions = []
        for minutes in [0, 5, 10, 15, max_wait_minutes]:
            pred = self.predictor.predict_gas_price(prediction_horizon_minutes=minutes)
            predictions.append(
                {
                    "minutes": minutes,
                    "predicted_gas": pred["predicted_price_gwei"],
                    "confidence": pred["confidence"],
                }
            )

        # Calculate costs for each timing
        trade_value = abs(trade_data.get("amount", 0) * trade_data.get("price", 0))
        gas_limit = trade_data.get("gas_limit", DEFAULT_GAS_LIMIT)
        eth_price_usd = trade_data.get("eth_price_usd", DEFAULT_ETH_PRICE_USD)

        timing_analysis = []
        for pred in predictions:
            # Convert gwei to wei, then to ETH
            gas_cost_eth = pred["predicted_gas"] * gas_limit / GWEI_TO_WEI_FACTOR
            gas_cost_usd = gas_cost_eth * eth_price_usd
            gas_cost_pct = (gas_cost_usd / trade_value * 100) if trade_value > 0 else 0

            timing_analysis.append(
                {
                    "minutes": pred["minutes"],
                    "gas_price_gwei": pred["predicted_gas"],
                    "gas_cost_usd": gas_cost_usd,
                    "gas_cost_pct": gas_cost_pct,
                    "confidence": pred["confidence"],
                }
            )

        # Find optimal timing
        optimal_timing = min(timing_analysis, key=lambda x: x["gas_cost_usd"])
        current_timing = timing_analysis[0]

        savings_usd = current_timing["gas_cost_usd"] - optimal_timing["gas_cost_usd"]
        savings_pct = (
            (savings_usd / current_timing["gas_cost_usd"] * 100)
            if current_timing["gas_cost_usd"] > 0
            else 0
        )

        # Determine if waiting is worth it
        should_wait = (
            optimal_timing["minutes"] > 0
            and savings_usd > MIN_SAVINGS_THRESHOLD_USD
            and savings_pct > MIN_SAVINGS_THRESHOLD_PCT
            and optimal_timing["confidence"] > MIN_CONFIDENCE_FOR_WAIT
        )

        return {
            "current_cost_usd": current_timing["gas_cost_usd"],
            "optimal_cost_usd": optimal_timing["gas_cost_usd"],
            "optimal_wait_minutes": optimal_timing["minutes"],
            "savings_usd": savings_usd,
            "savings_pct": savings_pct,
            "should_wait": should_wait,
            "timing_analysis": timing_analysis,
            "recommendation": (
                f"Wait {optimal_timing['minutes']} minutes to save ${savings_usd:.2f} ({savings_pct:.1f}%)"
                if should_wait
                else f"Execute now - savings not significant (${savings_usd:.2f})"
            ),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get optimizer performance metrics.

        Returns comprehensive metrics about the optimizer's performance
        including total optimizations, gas savings, spike detections,
        and deferred/batched trades.

        Returns:
            Dictionary containing:
            - total_optimizations: Total number of optimizations performed
            - gas_savings_usd: Total gas savings in USD
            - spike_detections: Number of gas spikes detected
            - deferred_trades: Number of trades deferred
            - batched_trades: Number of trades batched
            - mode: Current optimization mode
            - current_gas_price_gwei: Current gas price
            - history_size: Number of historical prices tracked
            - volatility: Current gas price volatility
        """
        return {
            **self.metrics,
            "mode": self.mode.value,
            "current_gas_price_gwei": self.current_gas_price,
            "history_size": len(self.predictor.gas_history),
            "volatility": self.predictor.get_volatility(),
        }
