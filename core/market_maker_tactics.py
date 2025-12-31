"""
Market Maker Specific Tactics
============================

Specialized trading algorithms and tactics optimized for copying
professional market maker behavior patterns.

Features:
- Spread capture algorithms
- Latency arbitrage detection
- Inventory management simulation
- Cross-market arbitrage
- Gas-optimized high-frequency trading
- Time-based position management
- Profitability threshold enforcement
"""

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class MarketMakerTactics:
    """
    Specialized tactics for copying market maker trading patterns.

    Implements algorithms that replicate professional market making behavior:
    - Spread capture through bid-ask trading
    - Inventory management and hedging
    - Latency arbitrage detection
    - Cross-market price discrepancies
    - Gas-efficient execution strategies
    """

    def __init__(self):
        # Spread capture parameters
        self.spread_capture_params = {
            "min_spread_capture_pct": 0.05,  # Minimum 0.05% spread to capture
            "max_spread_capture_pct": 0.50,  # Maximum 0.50% spread to target
            "spread_convergence_time": 300,  # 5 minutes expected convergence
            "inventory_skew_threshold": 0.3,  # Inventory imbalance threshold
            "max_inventory_position": 0.2,  # Max position as % of typical volume
        }

        # Latency arbitrage parameters
        self.latency_params = {
            "min_latency_edge_ms": 50,  # Minimum 50ms latency advantage
            "max_holding_time_latency": 30,  # Max 30 seconds for latency arb
            "latency_decay_factor": 0.95,  # Latency edge decay per second
            "min_profit_latency_pct": 0.02,  # Minimum 0.02% profit for latency arb
        }

        # Inventory management parameters
        self.inventory_params = {
            "target_inventory_ratio": 0.0,  # Target neutral inventory
            "inventory_rebalance_threshold": 0.2,  # Rebalance when 20% off target
            "max_inventory_holding_time": 1800,  # 30 minutes max inventory hold
            "inventory_cost_pct": 0.001,  # 0.001% per minute inventory cost
        }

        # Gas optimization parameters
        self.gas_params = {
            "gas_efficiency_threshold": 0.7,  # Minimum gas efficiency score
            "gas_price_elasticity": 1.5,  # Gas price sensitivity
            "min_gas_profit_ratio": 3.0,  # Min profit/gas cost ratio
            "gas_batch_window_seconds": 60,  # Batch trades within 60 seconds
        }

        # Cross-market arbitrage parameters
        self.arbitrage_params = {
            "min_price_discrepancy_pct": 0.1,  # Minimum 0.1% price difference
            "max_arbitrage_holding_time": 120,  # 2 minutes max hold
            "arbitrage_confidence_threshold": 0.8,  # Min confidence score
            "max_concurrent_arbitrages": 3,  # Max simultaneous arb positions
        }

        # Time-based management parameters
        self.time_params = {
            "market_open_buffer_minutes": 15,  # Buffer after market open
            "market_close_buffer_minutes": 30,  # Buffer before market close
            "optimal_trading_hours_start": 9,  # 9 AM UTC
            "optimal_trading_hours_end": 17,  # 5 PM UTC
            "weekend_trading_penalty": 0.5,  # 50% penalty on weekends
        }

        # Performance tracking
        self.tactic_performance: Dict[str, Dict[str, Any]] = {}
        self.inventory_positions: Dict[str, Dict[str, Any]] = {}

        # Batch processing
        self.pending_trades: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.last_batch_execution: Dict[str, datetime] = {}

        logger.info("🎯 Market maker tactics initialized")

    async def evaluate_spread_capture_opportunity(
        self,
        wallet_address: str,
        trade_data: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate spread capture opportunity for market maker copying.

        Market makers profit from buying at bid and selling at ask prices,
        capturing the spread. This tactic identifies when a market maker
        is likely engaging in spread capture behavior.
        """

        evaluation = {
            "opportunity_detected": False,
            "capture_probability": 0.0,
            "expected_spread_capture": 0.0,
            "recommended_action": "hold",
            "risk_assessment": "low",
            "time_to_convergence": 0,
            "inventory_impact": 0.0,
        }

        try:
            # Extract market data
            bid_price = market_data.get("bid_price", trade_data.get("price", 0))
            ask_price = market_data.get(
                "ask_price", bid_price * 1.001
            )  # Default 0.1% spread
            spread_pct = (ask_price - bid_price) / bid_price * 100

            # Check minimum spread requirements
            min_spread = self.spread_capture_params["min_spread_capture_pct"]
            if spread_pct < min_spread:
                evaluation["reason"] = ".3f"
                return evaluation

            # Analyze trade direction and position
            trade_side = trade_data.get("side", "BUY")
            trade_amount = abs(float(trade_data.get("amount", 0)))

            # Check for spread capture pattern
            # Market makers often alternate between buy and sell in quick succession
            recent_trades = await self._get_recent_wallet_trades(
                wallet_address, minutes_back=10
            )

            if len(recent_trades) >= 2:
                # Look for buy-sell alternation pattern
                sides = [
                    t.get("side", "BUY") for t in recent_trades[-3:]
                ]  # Last 3 trades

                # Check for market making pattern (alternating buys/sells)
                alternation_score = self._calculate_alternation_score(sides)

                if alternation_score >= 0.6:  # 60% alternation indicates market making
                    evaluation["opportunity_detected"] = True
                    evaluation["capture_probability"] = alternation_score

                    # Estimate spread capture potential
                    expected_spread = min(
                        spread_pct, self.spread_capture_params["max_spread_capture_pct"]
                    )
                    evaluation["expected_spread_capture"] = expected_spread

                    # Calculate convergence time (how long until spread normalizes)
                    convergence_time = self._estimate_spread_convergence_time(
                        spread_pct, market_data
                    )
                    evaluation["time_to_convergence"] = convergence_time

                    # Assess inventory impact
                    inventory_impact = self._calculate_inventory_impact(
                        wallet_address, trade_side, trade_amount
                    )
                    evaluation["inventory_impact"] = inventory_impact

                    # Determine recommended action
                    if inventory_impact < 0.3:  # Low inventory impact
                        evaluation["recommended_action"] = "capture_spread"
                        evaluation["risk_assessment"] = "low"
                    elif inventory_impact < 0.6:  # Moderate impact
                        evaluation["recommended_action"] = "partial_capture"
                        evaluation["risk_assessment"] = "medium"
                    else:  # High impact
                        evaluation["recommended_action"] = "avoid_capture"
                        evaluation["risk_assessment"] = "high"

                    # Position sizing recommendation for spread capture
                    position_size = self._calculate_spread_capture_size(
                        expected_spread, inventory_impact, convergence_time
                    )
                    evaluation["recommended_position_size"] = position_size

        except Exception as e:
            logger.error(f"Error evaluating spread capture for {wallet_address}: {e}")
            evaluation["error"] = str(e)

        return evaluation

    def _calculate_alternation_score(self, trade_sides: List[str]) -> float:
        """Calculate how alternating buy/sell trades are (0-1, higher = more alternating)."""

        if len(trade_sides) < 2:
            return 0.0

        alternations = 0
        for i in range(1, len(trade_sides)):
            if trade_sides[i] != trade_sides[i - 1]:
                alternations += 1

        max_possible_alternations = len(trade_sides) - 1
        alternation_score = (
            alternations / max_possible_alternations
            if max_possible_alternations > 0
            else 0
        )

        return alternation_score

    def _estimate_spread_convergence_time(
        self, current_spread_pct: float, market_data: Dict[str, Any]
    ) -> int:
        """Estimate time for spread to converge to normal levels (in seconds)."""

        # Base convergence time
        base_time = self.spread_capture_params["spread_convergence_time"]

        # Adjust for spread size (larger spreads take longer to converge)
        spread_multiplier = 1 + (current_spread_pct / 0.5)  # 0.5% = 2x time

        # Adjust for market liquidity (more liquid = faster convergence)
        liquidity_score = market_data.get("liquidity_score", 0.5)
        liquidity_multiplier = (
            2 - liquidity_score
        )  # Higher liquidity = faster convergence

        # Adjust for volatility (higher volatility = slower convergence)
        volatility = market_data.get("volatility_index", 0.2)
        volatility_multiplier = 1 + volatility * 2

        convergence_time = (
            base_time * spread_multiplier * liquidity_multiplier * volatility_multiplier
        )

        return min(int(convergence_time), 1800)  # Cap at 30 minutes

    def _calculate_inventory_impact(
        self, wallet_address: str, trade_side: str, trade_amount: float
    ) -> float:
        """Calculate inventory impact of the trade (0-1, higher = more impact)."""

        # Get current inventory position
        inventory = self.inventory_positions.get(wallet_address, {}).get(
            "net_position", 0
        )

        # Calculate new inventory after trade
        trade_direction = 1 if trade_side == "BUY" else -1
        new_inventory = inventory + (trade_direction * trade_amount)

        # Get typical position size for this wallet
        typical_position = self.inventory_positions.get(wallet_address, {}).get(
            "typical_position", trade_amount
        )

        if typical_position == 0:
            return 0.0

        # Calculate inventory ratio (as % of typical position)
        inventory_ratio = abs(new_inventory) / typical_position

        # Normalize to 0-1 scale with sigmoid function for smooth transition
        inventory_impact = 1 / (1 + math.exp(-5 * (inventory_ratio - 0.5)))

        return min(inventory_impact, 1.0)

    def _calculate_spread_capture_size(
        self,
        expected_spread_pct: float,
        inventory_impact: float,
        convergence_time_seconds: int,
    ) -> float:
        """Calculate optimal position size for spread capture."""

        # Base size on expected profit and risk
        base_profit_pct = expected_spread_pct * 0.8  # 80% of spread as profit estimate
        risk_pct = expected_spread_pct * 0.3  # 30% risk estimate

        # Kelly criterion for position sizing
        if risk_pct > 0:
            kelly_fraction = base_profit_pct / risk_pct
            kelly_fraction = min(kelly_fraction * 0.5, 0.25)  # Half-Kelly, max 25%
        else:
            kelly_fraction = 0.05  # Default 5%

        # Adjust for inventory impact (higher impact = smaller size)
        inventory_adjustment = 1 - inventory_impact * 0.5

        # Adjust for convergence time (longer time = smaller size due to opportunity cost)
        time_adjustment = min(
            1.0, 300 / max(convergence_time_seconds, 60)
        )  # 5 min baseline

        position_size_pct = kelly_fraction * inventory_adjustment * time_adjustment
        position_size_pct = max(0.01, min(position_size_pct, 0.20))  # 1% to 20%

        return position_size_pct

    async def detect_latency_arbitrage_opportunity(
        self,
        wallet_address: str,
        trade_data: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Detect potential latency arbitrage opportunities.

        Latency arbitrage exploits small price discrepancies that exist
        for brief moments due to differences in trade execution speed.
        """

        evaluation = {
            "opportunity_detected": False,
            "latency_edge_ms": 0,
            "expected_profit_pct": 0.0,
            "holding_time_seconds": 0,
            "risk_assessment": "high",
            "recommended_action": "avoid",
        }

        try:
            # Check for latency patterns in recent trades
            recent_trades = await self._get_recent_wallet_trades(
                wallet_address, minutes_back=5
            )

            if len(recent_trades) < 3:
                evaluation["reason"] = "Insufficient trade data for latency analysis"
                return evaluation

            # Analyze trade timing patterns
            timestamps = [datetime.fromisoformat(t["timestamp"]) for t in recent_trades]
            intervals_ms = []

            for i in range(1, len(timestamps)):
                interval = (timestamps[i] - timestamps[i - 1]).total_seconds() * 1000
                intervals_ms.append(interval)

            # Look for very short intervals (< 1000ms) indicating high-frequency trading
            short_intervals = [i for i in intervals_ms if i < 1000]

            if len(short_intervals) >= 2:
                avg_short_interval = np.mean(short_intervals)

                # Estimate latency edge (shorter intervals = larger edge)
                latency_edge_ms = max(10, 1000 - avg_short_interval)

                if latency_edge_ms >= self.latency_params["min_latency_edge_ms"]:
                    evaluation["opportunity_detected"] = True
                    evaluation["latency_edge_ms"] = latency_edge_ms

                    # Estimate profit potential based on latency edge
                    # This is highly simplified - real latency arb requires sophisticated modeling
                    profit_estimate_pct = (
                        latency_edge_ms / 1000
                    ) * 0.05  # Rough estimate
                    profit_estimate_pct = min(profit_estimate_pct, 0.2)  # Cap at 0.2%

                    evaluation["expected_profit_pct"] = profit_estimate_pct
                    evaluation["holding_time_seconds"] = min(
                        self.latency_params["max_holding_time_latency"],
                        latency_edge_ms / 100,  # Shorter latency = shorter hold
                    )

                    # Assess risk (latency arb is very high risk)
                    if (
                        profit_estimate_pct
                        >= self.latency_params["min_profit_latency_pct"]
                    ):
                        evaluation["risk_assessment"] = "very_high"
                        evaluation["recommended_action"] = "consider_latency_arb"
                        evaluation["warning"] = (
                            "Extreme risk - latency arbitrage requires sophisticated infrastructure"
                        )
                    else:
                        evaluation["recommended_action"] = "avoid_insufficient_edge"

        except Exception as e:
            logger.error(f"Error detecting latency arbitrage for {wallet_address}: {e}")
            evaluation["error"] = str(e)

        return evaluation

    async def simulate_inventory_management(
        self,
        wallet_address: str,
        current_position: float,
        market_conditions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Simulate market maker inventory management decisions.

        Market makers constantly adjust their inventory to maintain
        market neutrality and avoid directional risk.
        """

        simulation = {
            "inventory_adjustment_needed": False,
            "recommended_action": "hold",
            "target_position": 0.0,
            "urgency_level": "low",
            "expected_cost": 0.0,
            "time_horizon": 0,
        }

        try:
            # Get inventory parameters
            target_ratio = self.inventory_params["target_inventory_ratio"]
            rebalance_threshold = self.inventory_params["inventory_rebalance_threshold"]

            # Calculate current inventory ratio
            typical_position = self._get_wallet_typical_position(wallet_address)
            if typical_position == 0:
                return simulation

            current_ratio = current_position / typical_position

            # Check if rebalancing is needed
            deviation = abs(current_ratio - target_ratio)
            simulation["inventory_adjustment_needed"] = deviation >= rebalance_threshold

            if not simulation["inventory_adjustment_needed"]:
                simulation["reason"] = ".2f"
                return simulation

            # Determine rebalancing direction and urgency
            if current_ratio > target_ratio:
                # Overbought - need to sell
                adjustment_size = (current_ratio - target_ratio) * typical_position
                simulation["recommended_action"] = "reduce_inventory"
                simulation["target_position"] = target_ratio * typical_position
            else:
                # Oversold - need to buy
                adjustment_size = (target_ratio - current_ratio) * typical_position
                simulation["recommended_action"] = "increase_inventory"
                simulation["target_position"] = target_ratio * typical_position

            # Calculate urgency based on deviation size
            if deviation >= rebalance_threshold * 2:
                simulation["urgency_level"] = "high"
                simulation["time_horizon"] = 300  # 5 minutes
            elif deviation >= rebalance_threshold * 1.5:
                simulation["urgency_level"] = "medium"
                simulation["time_horizon"] = 900  # 15 minutes
            else:
                simulation["urgency_level"] = "low"
                simulation["time_horizon"] = 1800  # 30 minutes

            # Estimate rebalancing cost
            volatility = market_conditions.get("volatility_index", 0.2)
            gas_multiplier = market_conditions.get("gas_price_multiplier", 1.0)

            # Cost includes slippage, gas, and market impact
            slippage_cost = (
                adjustment_size * volatility * 0.001
            )  # 0.1% slippage estimate
            gas_cost = adjustment_size * gas_multiplier * 0.0001  # Gas cost estimate
            time_cost = (
                adjustment_size
                * (simulation["time_horizon"] / 3600)
                * self.inventory_params["inventory_cost_pct"]
            )

            simulation["expected_cost"] = slippage_cost + gas_cost + time_cost

            # Risk assessment
            simulation["risk_assessment"] = (
                "medium" if deviation < rebalance_threshold * 2 else "high"
            )

        except Exception as e:
            logger.error(
                f"Error simulating inventory management for {wallet_address}: {e}"
            )
            simulation["error"] = str(e)

        return simulation

    async def detect_cross_market_arbitrage(
        self,
        wallet_address: str,
        trade_data: Dict[str, Any],
        related_markets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Detect cross-market arbitrage opportunities.

        Market makers often arbitrage price discrepancies between
        related markets or different market venues.
        """

        arbitrage = {
            "opportunity_detected": False,
            "price_discrepancy_pct": 0.0,
            "arbitrage_direction": None,
            "expected_profit_pct": 0.0,
            "holding_time_seconds": 0,
            "confidence_score": 0.0,
            "risk_assessment": "high",
        }

        try:
            if not related_markets or len(related_markets) < 2:
                arbitrage["reason"] = "Insufficient related market data"
                return arbitrage

            # Extract prices from related markets
            current_market = trade_data.get("market_id", trade_data.get("condition_id"))
            current_price = trade_data.get("price", 0)

            related_prices = []
            for market in related_markets:
                if market.get("market_id") != current_market:
                    price = market.get("price", 0)
                    if price > 0:
                        related_prices.append(
                            {
                                "market_id": market["market_id"],
                                "price": price,
                                "liquidity": market.get("liquidity_score", 0.5),
                            }
                        )

            if not related_prices:
                arbitrage["reason"] = "No valid related market prices"
                return arbitrage

            # Find best arbitrage opportunity
            best_opportunity = None
            max_discrepancy = 0

            for related in related_prices:
                discrepancy_pct = (
                    abs(current_price - related["price"]) / current_price * 100
                )

                if discrepancy_pct > max_discrepancy:
                    max_discrepancy = discrepancy_pct
                    direction = (
                        "buy_related_sell_current"
                        if related["price"] > current_price
                        else "buy_current_sell_related"
                    )
                    best_opportunity = {
                        "discrepancy_pct": discrepancy_pct,
                        "direction": direction,
                        "related_market": related["market_id"],
                        "price_ratio": related["price"] / current_price,
                        "liquidity_score": related["liquidity"],
                    }

            # Check if opportunity meets thresholds
            min_discrepancy = self.arbitrage_params["min_price_discrepancy_pct"]

            if max_discrepancy >= min_discrepancy:
                arbitrage["opportunity_detected"] = True
                arbitrage["price_discrepancy_pct"] = max_discrepancy
                arbitrage["arbitrage_direction"] = best_opportunity["direction"]

                # Estimate profit potential (accounting for fees and slippage)
                gross_profit_pct = (
                    max_discrepancy * 0.8
                )  # 80% of discrepancy after costs
                arbitrage["expected_profit_pct"] = gross_profit_pct

                # Estimate holding time based on market liquidity
                liquidity_score = best_opportunity["liquidity_score"]
                holding_time = int(
                    self.arbitrage_params["max_arbitrage_holding_time"]
                    * (2 - liquidity_score)
                )
                arbitrage["holding_time_seconds"] = holding_time

                # Calculate confidence score
                confidence = min(
                    1.0, max_discrepancy / (min_discrepancy * 3)
                )  # Scale with discrepancy size
                confidence *= liquidity_score  # Reduce confidence in illiquid markets
                arbitrage["confidence_score"] = confidence

                # Risk assessment
                if (
                    confidence
                    >= self.arbitrage_params["arbitrage_confidence_threshold"]
                ):
                    arbitrage["risk_assessment"] = "medium"
                    arbitrage["recommended_action"] = "execute_arbitrage"
                else:
                    arbitrage["risk_assessment"] = "high"
                    arbitrage["recommended_action"] = "monitor_only"

        except Exception as e:
            logger.error(
                f"Error detecting cross-market arbitrage for {wallet_address}: {e}"
            )
            arbitrage["error"] = str(e)

        return arbitrage

    async def optimize_gas_efficiency(
        self,
        wallet_address: str,
        pending_trades: List[Dict[str, Any]],
        gas_conditions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Optimize trade execution for gas efficiency.

        High-frequency market maker strategies require careful gas management
        to maintain profitability.
        """

        optimization = {
            "optimization_applied": False,
            "gas_efficiency_score": 0.0,
            "recommended_batch_size": len(pending_trades),
            "estimated_gas_savings_pct": 0.0,
            "optimal_execution_time": None,
            "alternative_strategies": [],
        }

        try:
            if not pending_trades:
                return optimization

            current_gas_multiplier = gas_conditions.get("gas_price_multiplier", 1.0)
            gas_efficiency_threshold = self.gas_params["gas_efficiency_threshold"]

            # Calculate base gas cost
            avg_trade_size = np.mean([abs(t.get("amount", 0)) for t in pending_trades])
            avg_trade_size * current_gas_multiplier * 0.00005  # Base gas estimate

            # Strategy 1: Trade Batching
            batch_window = self.gas_params["gas_batch_window_seconds"]
            batch_efficiency = self._calculate_batch_efficiency(
                pending_trades, batch_window
            )
            optimization["batch_efficiency"] = batch_efficiency

            # Strategy 2: Time-based execution (avoid peak gas times)
            time_efficiency = self._calculate_time_based_efficiency(gas_conditions)
            optimization["time_efficiency"] = time_efficiency

            # Strategy 3: Size optimization (larger trades may have better gas ratios)
            size_efficiency = self._calculate_size_efficiency(pending_trades)
            optimization["size_efficiency"] = size_efficiency

            # Overall gas efficiency score
            overall_efficiency = (
                batch_efficiency + time_efficiency + size_efficiency
            ) / 3
            optimization["gas_efficiency_score"] = overall_efficiency

            if overall_efficiency >= gas_efficiency_threshold:
                optimization["optimization_applied"] = True

                # Recommend optimal batch size
                if (
                    batch_efficiency > time_efficiency
                    and batch_efficiency > size_efficiency
                ):
                    # Batch strategy is best
                    optimal_batch = min(
                        len(pending_trades), 5
                    )  # Max 5 trades per batch
                    optimization["recommended_batch_size"] = optimal_batch
                    optimization["primary_strategy"] = "batching"
                    optimization["estimated_gas_savings_pct"] = (
                        batch_efficiency - 0.5
                    ) * 20

                elif (
                    time_efficiency > batch_efficiency
                    and time_efficiency > size_efficiency
                ):
                    # Time-based strategy is best
                    optimal_time = self._find_optimal_execution_time(gas_conditions)
                    optimization["optimal_execution_time"] = optimal_time
                    optimization["primary_strategy"] = "time_based"
                    optimization["estimated_gas_savings_pct"] = (
                        time_efficiency - 0.5
                    ) * 15

                else:
                    # Size optimization strategy
                    optimization["primary_strategy"] = "size_optimization"
                    optimization["estimated_gas_savings_pct"] = (
                        size_efficiency - 0.5
                    ) * 10

                # Alternative strategies
                optimization["alternative_strategies"] = [
                    strategy
                    for strategy in ["batching", "time_based", "size_optimization"]
                    if strategy != optimization["primary_strategy"]
                ]

        except Exception as e:
            logger.error(f"Error optimizing gas efficiency for {wallet_address}: {e}")
            optimization["error"] = str(e)

        return optimization

    def _calculate_batch_efficiency(
        self, trades: List[Dict[str, Any]], batch_window: int
    ) -> float:
        """Calculate gas efficiency of batching trades."""

        if len(trades) <= 1:
            return 0.5  # Neutral score for single trades

        # Sort trades by timestamp
        sorted_trades = sorted(trades, key=lambda x: x.get("timestamp", ""))

        # Count trades within batch windows
        batchable_trades = 0
        for i in range(len(sorted_trades)):
            window_start = datetime.fromisoformat(sorted_trades[i]["timestamp"])
            window_end = window_start + timedelta(seconds=batch_window)

            # Count trades in this window
            in_window = sum(
                1
                for t in sorted_trades[i:]
                if datetime.fromisoformat(t["timestamp"]) <= window_end
            )

            batchable_trades = max(batchable_trades, in_window)

        # Efficiency score based on batching potential
        batch_efficiency = min(1.0, batchable_trades / len(trades))
        return batch_efficiency

    def _calculate_time_based_efficiency(self, gas_conditions: Dict[str, Any]) -> float:
        """Calculate gas efficiency based on execution timing."""

        current_hour = datetime.now().hour
        gas_multiplier = gas_conditions.get("gas_price_multiplier", 1.0)

        # Gas prices typically higher during business hours
        if 9 <= current_hour <= 17:  # Business hours
            time_penalty = 1.2
        elif 6 <= current_hour <= 21:  # Extended hours
            time_penalty = 1.1
        else:  # Off-hours
            time_penalty = 0.9

        # Calculate efficiency (lower gas = higher efficiency)
        time_efficiency = 1.0 / (gas_multiplier * time_penalty)
        return min(time_efficiency, 1.0)

    def _calculate_size_efficiency(self, trades: List[Dict[str, Any]]) -> float:
        """Calculate gas efficiency based on trade sizes."""

        sizes = [abs(t.get("amount", 0)) for t in trades]
        if not sizes:
            return 0.5

        avg_size = np.mean(sizes)
        size_variation = np.std(sizes) / avg_size if avg_size > 0 else 0

        # Larger, more consistent trade sizes tend to have better gas efficiency
        size_efficiency = 1.0 / (1.0 + size_variation)
        return size_efficiency

    def _find_optimal_execution_time(self, gas_conditions: Dict[str, Any]) -> datetime:
        """Find optimal execution time for gas efficiency."""

        # Simple heuristic: execute 2 hours from now (assuming gas patterns)
        # In practice, this would use gas price forecasting
        return datetime.now() + timedelta(hours=2)

    async def apply_time_based_position_management(
        self, position_data: Dict[str, Any], market_conditions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply time-based position management rules.

        Market makers often have strict time limits on positions
        to manage inventory and avoid overnight risk.
        """

        management = {
            "action_required": False,
            "recommended_action": "hold",
            "urgency_level": "low",
            "reason": "",
            "time_to_expiry": 0,
        }

        try:
            entry_time = position_data.get("entry_time")
            if not entry_time:
                return management

            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time)

            position_age_seconds = (datetime.now() - entry_time).total_seconds()
            position_age_hours = position_age_seconds / 3600

            # Get position management rules based on strategy
            wallet_type = position_data.get("wallet_type", "market_maker")
            max_holding_time = self._get_max_holding_time(
                wallet_type, market_conditions
            )

            # Check if position is approaching expiry
            time_to_expiry = max_holding_time - position_age_hours

            if time_to_expiry <= 0:
                # Position has expired
                management["action_required"] = True
                management["recommended_action"] = "close_position"
                management["urgency_level"] = "critical"
                management["reason"] = ".1f"
                management["time_to_expiry"] = 0

            elif time_to_expiry <= 0.5:  # Less than 30 minutes
                management["action_required"] = True
                management["recommended_action"] = "reduce_position"
                management["urgency_level"] = "high"
                management["reason"] = ".1f"
                management["time_to_expiry"] = time_to_expiry

            elif time_to_expiry <= 2.0:  # Less than 2 hours
                management["action_required"] = True
                management["recommended_action"] = "monitor_closely"
                management["urgency_level"] = "medium"
                management["reason"] = ".1f"
                management["time_to_expiry"] = time_to_expiry

            # Apply market close buffer
            current_hour = datetime.now().hour
            market_close_buffer = self.time_params["market_close_buffer_minutes"] / 60

            if current_hour >= (
                self.time_params["optimal_trading_hours_end"] - market_close_buffer
            ):
                if position_age_hours >= 1.0:  # Hold at least 1 hour
                    management["action_required"] = True
                    management["recommended_action"] = "close_before_market_close"
                    management["urgency_level"] = "medium"
                    management["reason"] = (
                        "Approaching market close - reduce overnight risk"
                    )

            # Weekend penalty
            current_day = datetime.now().weekday()
            if current_day >= 5:  # Saturday/Sunday
                self.time_params["weekend_trading_penalty"]
                if position_age_hours >= 1.0:
                    management["action_required"] = True
                    management["recommended_action"] = "reduce_weekend_exposure"
                    management["urgency_level"] = "low"
                    management["reason"] = ".1f"

        except Exception as e:
            logger.error(f"Error applying time-based management: {e}")
            management["error"] = str(e)

        return management

    def _get_max_holding_time(
        self, wallet_type: str, market_conditions: Dict[str, Any]
    ) -> float:
        """Get maximum holding time for wallet type under current conditions."""

        base_times = {
            "market_maker": 2.0,  # 2 hours
            "arbitrage_trader": 1.0,  # 1 hour
            "high_frequency_trader": 0.5,  # 30 minutes
            "directional_trader": 24.0,  # 24 hours
            "mixed_trader": 6.0,  # 6 hours
            "low_activity": 12.0,  # 12 hours
        }

        base_time = base_times.get(wallet_type, 2.0)

        # Adjust for market conditions
        volatility = market_conditions.get("volatility_index", 0.2)
        liquidity = market_conditions.get("liquidity_score", 0.6)

        # Higher volatility = shorter holding times
        volatility_adjustment = 1.0 / (1.0 + volatility * 2)

        # Lower liquidity = shorter holding times
        liquidity_adjustment = liquidity

        adjusted_time = base_time * volatility_adjustment * liquidity_adjustment

        return max(adjusted_time, 0.25)  # Minimum 15 minutes

    async def enforce_profitability_thresholds(
        self,
        trade_data: Dict[str, Any],
        wallet_info: Dict[str, Any],
        market_conditions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Enforce minimum profitability thresholds for market maker trades.

        Ensures trades meet profitability requirements before execution.
        """

        enforcement = {
            "threshold_met": False,
            "required_profit_pct": 0.0,
            "estimated_profit_pct": 0.0,
            "gas_cost_pct": 0.0,
            "net_profit_pct": 0.0,
            "reason": "",
        }

        try:
            # Get minimum profitability threshold
            wallet_type = wallet_info.get("classification", "market_maker")
            min_threshold_pct = self._get_min_profit_threshold(
                wallet_type, market_conditions
            )

            enforcement["required_profit_pct"] = min_threshold_pct

            # Estimate trade profitability
            estimated_profit_pct = self._estimate_trade_profitability(
                trade_data, wallet_info, market_conditions
            )

            enforcement["estimated_profit_pct"] = estimated_profit_pct

            # Estimate gas costs
            gas_cost_pct = self._estimate_gas_cost_pct(trade_data, market_conditions)
            enforcement["gas_cost_pct"] = gas_cost_pct

            # Calculate net profitability
            net_profit_pct = estimated_profit_pct - gas_cost_pct
            enforcement["net_profit_pct"] = net_profit_pct

            # Check threshold
            if net_profit_pct >= min_threshold_pct:
                enforcement["threshold_met"] = True
                enforcement["reason"] = ".3f"
            else:
                enforcement["threshold_met"] = False
                enforcement["reason"] = ".3f"

        except Exception as e:
            logger.error(f"Error enforcing profitability thresholds: {e}")
            enforcement["error"] = str(e)

        return enforcement

    def _get_min_profit_threshold(
        self, wallet_type: str, market_conditions: Dict[str, Any]
    ) -> float:
        """Get minimum profit threshold for wallet type."""

        base_thresholds = {
            "market_maker": 0.003,  # 0.3%
            "arbitrage_trader": 0.005,  # 0.5%
            "high_frequency_trader": 0.002,  # 0.2%
            "directional_trader": 0.02,  # 2.0%
            "mixed_trader": 0.01,  # 1.0%
            "low_activity": 0.015,  # 1.5%
        }

        base_threshold = base_thresholds.get(wallet_type, 0.003)

        # Adjust for market conditions
        volatility = market_conditions.get("volatility_index", 0.2)
        gas_multiplier = market_conditions.get("gas_price_multiplier", 1.0)

        # Higher volatility = higher threshold
        volatility_adjustment = 1.0 + volatility

        # Higher gas costs = higher threshold
        gas_adjustment = gas_multiplier

        adjusted_threshold = base_threshold * volatility_adjustment * gas_adjustment

        return adjusted_threshold

    def _estimate_trade_profitability(
        self,
        trade_data: Dict[str, Any],
        wallet_info: Dict[str, Any],
        market_conditions: Dict[str, Any],
    ) -> float:
        """Estimate profitability of a potential trade."""

        # This is a simplified estimation - in practice, this would use
        # more sophisticated modeling based on historical performance

        wallet_type = wallet_info.get("classification", "market_maker")

        # Base profitability estimates by wallet type
        base_estimates = {
            "market_maker": 0.008,  # 0.8%
            "arbitrage_trader": 0.012,  # 1.2%
            "high_frequency_trader": 0.005,  # 0.5%
            "directional_trader": 0.035,  # 3.5%
            "mixed_trader": 0.015,  # 1.5%
            "low_activity": 0.025,  # 2.5%
        }

        base_profit = base_estimates.get(wallet_type, 0.008)

        # Adjust for market conditions
        volatility = market_conditions.get("volatility_index", 0.2)
        liquidity = market_conditions.get("liquidity_score", 0.6)

        # Higher volatility typically increases profit potential
        volatility_adjustment = 1.0 + volatility * 0.5

        # Higher liquidity typically decreases profit potential (more competition)
        liquidity_adjustment = 2.0 - liquidity

        estimated_profit = base_profit * volatility_adjustment * liquidity_adjustment

        return estimated_profit

    def _estimate_gas_cost_pct(
        self, trade_data: Dict[str, Any], market_conditions: Dict[str, Any]
    ) -> float:
        """Estimate gas cost as percentage of trade value."""

        trade_amount = abs(float(trade_data.get("amount", 0)))
        gas_multiplier = market_conditions.get("gas_price_multiplier", 1.0)

        # Simplified gas cost estimation
        # In practice, this would use actual gas price data
        gas_cost_usd = trade_amount * gas_multiplier * 0.00005  # 0.005% of trade size
        gas_cost_pct = gas_cost_usd / trade_amount if trade_amount > 0 else 0

        return gas_cost_pct

    async def _get_recent_wallet_trades(
        self, wallet_address: str, minutes_back: int
    ) -> List[Dict[str, Any]]:
        """Get recent trades for wallet (placeholder - integrate with actual trade data)."""

        # This would integrate with the actual trade data storage
        # For now, return empty list
        return []

    def _get_wallet_typical_position(self, wallet_address: str) -> float:
        """Get typical position size for wallet (placeholder)."""

        # This would be calculated from historical trade data
        return 1000.0  # Default placeholder

    def update_tactic_performance(
        self, tactic_name: str, performance_data: Dict[str, Any]
    ):
        """Update performance tracking for tactics."""

        if tactic_name not in self.tactic_performance:
            self.tactic_performance[tactic_name] = {
                "total_executions": 0,
                "successful_executions": 0,
                "total_profit": 0.0,
                "avg_profit": 0.0,
                "win_rate": 0.0,
                "last_update": datetime.now().isoformat(),
            }

        perf = self.tactic_performance[tactic_name]
        perf["total_executions"] += 1

        if performance_data.get("successful", False):
            perf["successful_executions"] += 1

        profit = performance_data.get("profit", 0.0)
        perf["total_profit"] += profit

        # Recalculate averages
        perf["avg_profit"] = perf["total_profit"] / perf["total_executions"]
        perf["win_rate"] = perf["successful_executions"] / perf["total_executions"]
        perf["last_update"] = datetime.now().isoformat()

    def get_tactic_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all tactics."""

        summary = {
            "tactic_count": len(self.tactic_performance),
            "best_performing_tactic": None,
            "worst_performing_tactic": None,
            "overall_win_rate": 0.0,
            "total_profit_generated": 0.0,
        }

        if not self.tactic_performance:
            return summary

        total_executions = sum(
            perf["total_executions"] for perf in self.tactic_performance.values()
        )
        total_profit = sum(
            perf["total_profit"] for perf in self.tactic_performance.values()
        )

        if total_executions > 0:
            summary["overall_win_rate"] = (
                sum(
                    perf["successful_executions"]
                    for perf in self.tactic_performance.values()
                )
                / total_executions
            )

        summary["total_profit_generated"] = total_profit

        # Find best and worst performing tactics
        if self.tactic_performance:
            best_tactic = max(
                self.tactic_performance.keys(),
                key=lambda x: self.tactic_performance[x]["avg_profit"],
            )
            worst_tactic = min(
                self.tactic_performance.keys(),
                key=lambda x: self.tactic_performance[x]["avg_profit"],
            )

            summary["best_performing_tactic"] = best_tactic
            summary["worst_performing_tactic"] = worst_tactic

        return summary
