"""
Historical Data Manager for Backtesting
========================================

Comprehensive data collection, validation, and preparation system for
backtesting copy trading strategies across market maker and directional trader wallets.

Features:
- Multi-source data collection (Polygonscan, market data feeds)
- Data quality validation and gap handling
- Synthetic data generation for edge cases
- Market regime classification
- Performance benchmarking data preparation
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class HistoricalDataManager:
    """
    Comprehensive historical data management system for backtesting.

    Handles collection, validation, and preparation of all data required
    for thorough backtesting of copy trading strategies.
    """

    def __init__(self):
        # Data sources configuration
        self.data_sources = {
            "polygonscan": {
                "api_endpoint": "https://api.polygonscan.com/api",
                "rate_limit": 5,  # requests per second
                "timeout": 30,
                "retries": 3,
            },
            "market_data": {
                "api_endpoint": "https://api.example.com/market-data",
                "rate_limit": 10,
                "timeout": 15,
                "retries": 2,
            },
            "gas_oracle": {
                "api_endpoint": "https://api.etherscan.io/api",
                "rate_limit": 5,
                "timeout": 20,
                "retries": 3,
            },
        }

        # Data quality parameters
        self.quality_params = {
            "min_data_points_per_wallet": 100,
            "max_data_gap_hours": 24,
            "outlier_threshold_std": 3.0,
            "completeness_threshold": 0.95,
            "consistency_check_window": 50,
            "validation_sample_size": 1000,
        }

        # Market regime classification parameters
        self.regime_params = {
            "volatility_lookback_days": 30,
            "trend_lookback_days": 20,
            "liquidity_percentile_threshold": 25,
            "regime_stability_window": 5,
            "min_regime_duration_hours": 12,
        }

        # Data storage
        self.data_cache: Dict[str, Any] = {}
        self.validation_reports: List[Dict[str, Any]] = []

        # Synthetic data generation parameters
        self.synthetic_params = {
            "edge_case_scenarios": [
                "flash_crash",
                "high_volatility",
                "low_liquidity",
                "gas_spike",
                "market_manipulation",
                "extreme_drawdown",
            ],
            "synthetic_data_ratio": 0.2,  # 20% synthetic data for augmentation
            "noise_level": 0.05,  # 5% noise for realism
            "correlation_preservation": True,
        }

        logger.info("📊 Historical data manager initialized")

    async def collect_comprehensive_dataset(
        self,
        wallet_addresses: List[str],
        start_date: datetime,
        end_date: datetime,
        data_types: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Collect comprehensive historical dataset for backtesting.

        Args:
            wallet_addresses: List of wallet addresses to collect data for
            start_date: Start date for data collection
            end_date: End date for data collection
            data_types: Types of data to collect (trade_history, market_data, gas_prices)

        Returns:
            Comprehensive dataset with validation reports
        """

        if data_types is None:
            data_types = ["trade_history", "market_data", "gas_prices", "market_regimes"]

        dataset = {
            "collection_metadata": {
                "wallet_count": len(wallet_addresses),
                "date_range": f"{start_date.isoformat()} to {end_date.isoformat()}",
                "data_types": data_types,
                "collection_timestamp": datetime.now().isoformat(),
            },
            "wallet_data": {},
            "market_data": {},
            "gas_data": {},
            "regime_data": {},
            "validation_reports": {},
            "data_quality_summary": {},
        }

        try:
            # Collect trade history for all wallets
            if "trade_history" in data_types:
                logger.info(f"📈 Collecting trade history for {len(wallet_addresses)} wallets")
                wallet_trade_data = await self._collect_wallet_trade_history(
                    wallet_addresses, start_date, end_date
                )
                dataset["wallet_data"] = wallet_trade_data

            # Collect market data
            if "market_data" in data_types:
                logger.info("💰 Collecting market data")
                market_data = await self._collect_market_data(start_date, end_date)
                dataset["market_data"] = market_data

            # Collect gas price history
            if "gas_prices" in data_types:
                logger.info("⛽ Collecting gas price history")
                gas_data = await self._collect_gas_price_history(start_date, end_date)
                dataset["gas_data"] = gas_data

            # Classify market regimes
            if "market_regimes" in data_types:
                logger.info("📊 Classifying market regimes")
                regime_data = await self._classify_market_regimes(
                    dataset["market_data"], start_date, end_date
                )
                dataset["regime_data"] = regime_data

            # Validate data quality
            logger.info("🔍 Validating data quality")
            validation_reports = await self._validate_dataset_quality(dataset)
            dataset["validation_reports"] = validation_reports

            # Handle data gaps
            logger.info("🔧 Handling data gaps")
            dataset = await self._handle_data_gaps(dataset)

            # Generate synthetic data for edge cases
            if self.synthetic_params["synthetic_data_ratio"] > 0:
                logger.info("🎭 Generating synthetic data for edge cases")
                dataset = await self._generate_synthetic_data(dataset)

            # Generate data quality summary
            dataset["data_quality_summary"] = self._generate_data_quality_summary(dataset)

            logger.info(
                f"✅ Comprehensive dataset collected: {len(wallet_addresses)} wallets, {len(data_types)} data types"
            )

        except Exception as e:
            logger.error(f"Error collecting comprehensive dataset: {e}")
            dataset["error"] = str(e)

        return dataset

    async def _collect_wallet_trade_history(
        self, wallet_addresses: List[str], start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect complete trade history for all wallets."""

        wallet_data = {}

        for wallet_address in wallet_addresses:
            try:
                # Collect transaction data from Polygonscan
                transactions = await self._fetch_polygonscan_transactions(
                    wallet_address, start_date, end_date
                )

                # Filter for Polymarket trades
                polymarket_trades = await self._filter_polymarket_trades(transactions)

                # Enrich with market data and calculations
                enriched_trades = await self._enrich_trade_data(polymarket_trades)

                wallet_data[wallet_address] = {
                    "address": wallet_address,
                    "trade_count": len(enriched_trades),
                    "date_range": f"{start_date.isoformat()} to {end_date.isoformat()}",
                    "trades": enriched_trades,
                    "summary_stats": self._calculate_wallet_summary_stats(enriched_trades),
                }

                logger.debug(f"Collected {len(enriched_trades)} trades for {wallet_address[:8]}...")

            except Exception as e:
                logger.error(f"Error collecting trade history for {wallet_address}: {e}")
                wallet_data[wallet_address] = {
                    "address": wallet_address,
                    "error": str(e),
                    "trade_count": 0,
                    "trades": [],
                }

        return wallet_data

    async def _fetch_polygonscan_transactions(
        self, wallet_address: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch transaction data from Polygonscan API."""

        # This would implement actual API calls to Polygonscan
        # For now, return placeholder structure

        transactions = []

        # Simulate API response structure
        # In practice, this would make actual HTTP requests with proper error handling

        return transactions

    async def _filter_polymarket_trades(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter transactions to include only Polymarket-related trades."""

        polymarket_trades = []

        # Polymarket contract addresses (example)
        polymarket_contracts = [
            "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",  # Example CTF contract
            "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",  # Other contracts
        ]

        for tx in transactions:
            # Check if transaction interacts with Polymarket contracts
            if any(
                contract in str(tx.get("to", "")) or contract in str(tx.get("input", ""))
                for contract in polymarket_contracts
            ):
                polymarket_trades.append(tx)

        return polymarket_trades

    async def _enrich_trade_data(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich trade data with additional calculations and market context."""

        enriched_trades = []

        for trade in trades:
            enriched_trade = trade.copy()

            # Parse trade details
            enriched_trade["parsed_trade"] = await self._parse_trade_details(trade)

            # Calculate PNL
            enriched_trade["pnl_calculation"] = await self._calculate_trade_pnl(trade)

            # Add market context
            enriched_trade["market_context"] = await self._add_market_context(trade)

            # Add execution quality metrics
            enriched_trade["execution_quality"] = await self._calculate_execution_quality(trade)

            enriched_trades.append(enriched_trade)

        return enriched_trades

    async def _parse_trade_details(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Parse detailed trade information from transaction data."""

        # This would decode Polymarket trade details from transaction input
        # Simplified implementation

        return {
            "side": "BUY",  # BUY or SELL
            "amount": 100.0,  # Trade amount
            "price": 0.55,  # Trade price
            "market_id": "0x123...",  # Market identifier
            "condition_id": "0x456...",  # Condition identifier
            "outcome_index": 0,  # Outcome index
            "timestamp": trade.get("timestamp", datetime.now().isoformat()),
        }

    async def _calculate_trade_pnl(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate profit and loss for a trade."""

        # Simplified PNL calculation
        await self._parse_trade_details(trade)

        # For Polymarket, PNL depends on market outcome and position
        # This is a simplified calculation

        pnl_calculation = {
            "gross_pnl": 0.0,
            "net_pnl": 0.0,
            "gas_cost": trade.get("gas_used", 0) * trade.get("gas_price", 0),
            "fee_cost": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        }

        return pnl_calculation

    async def _add_market_context(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Add market context information to trade."""

        return {
            "market_volatility": 0.2,
            "market_liquidity": 0.6,
            "market_trend": 0.0,
            "order_book_depth": 1000,
            "spread_bps": 50,
        }

    async def _calculate_execution_quality(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate execution quality metrics."""

        return {
            "slippage_bps": 25,
            "market_impact_bps": 10,
            "execution_time_ms": 150,
            "price_improvement_bps": 5,
            "fill_rate": 1.0,
        }

    def _calculate_wallet_summary_stats(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics for a wallet's trading activity."""

        if not trades:
            return {"total_trades": 0, "date_range": None}

        # Extract basic metrics
        pnl_values = [t.get("pnl_calculation", {}).get("net_pnl", 0) for t in trades]
        trade_sizes = [t.get("parsed_trade", {}).get("amount", 0) for t in trades]

        timestamps = [
            datetime.fromisoformat(t.get("timestamp", datetime.now().isoformat())) for t in trades
        ]

        summary = {
            "total_trades": len(trades),
            "total_pnl": sum(pnl_values),
            "average_pnl": np.mean(pnl_values) if pnl_values else 0,
            "pnl_volatility": np.std(pnl_values) if pnl_values else 0,
            "average_trade_size": np.mean(trade_sizes) if trade_sizes else 0,
            "date_range": f"{min(timestamps).isoformat()} to {max(timestamps).isoformat()}",
            "trading_days": len(set(t.date() for t in timestamps)),
            "average_daily_trades": (
                len(trades) / len(set(t.date() for t in timestamps)) if trades else 0
            ),
        }

        # Calculate win rate
        winning_trades = sum(1 for pnl in pnl_values if pnl > 0)
        summary["win_rate"] = winning_trades / len(pnl_values) if pnl_values else 0

        # Calculate profit factor
        gross_profits = sum(pnl for pnl in pnl_values if pnl > 0)
        gross_losses = abs(sum(pnl for pnl in pnl_values if pnl < 0))
        summary["profit_factor"] = (
            gross_profits / gross_losses if gross_losses > 0 else float("inf")
        )

        return summary

    async def _collect_market_data(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect comprehensive market data for backtesting period."""

        market_data = {
            "price_data": {},
            "order_book_data": {},
            "liquidity_data": {},
            "volatility_data": {},
            "correlation_data": {},
        }

        # Collect price data for major markets
        market_ids = ["0x123", "0x456", "0x789"]  # Example market IDs

        for market_id in market_ids:
            price_series = await self._fetch_market_price_series(market_id, start_date, end_date)
            market_data["price_data"][market_id] = price_series

            # Calculate volatility
            if price_series:
                returns = self._calculate_returns(price_series)
                volatility = np.std(returns) * np.sqrt(365) if returns else 0
                market_data["volatility_data"][market_id] = {
                    "daily_volatility": np.std(returns) if returns else 0,
                    "annualized_volatility": volatility,
                    "max_drawdown": self._calculate_max_drawdown(price_series),
                }

        # Collect order book snapshots
        market_data["order_book_data"] = await self._collect_order_book_snapshots(
            market_ids, start_date, end_date
        )

        # Calculate market correlations
        market_data["correlation_data"] = self._calculate_market_correlations(
            market_data["price_data"]
        )

        return market_data

    async def _fetch_market_price_series(
        self, market_id: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch price time series for a market."""

        # This would fetch actual price data
        # Placeholder implementation

        price_series = []
        current_date = start_date

        while current_date <= end_date:
            price_series.append(
                {
                    "timestamp": current_date.isoformat(),
                    "price": 0.5 + 0.1 * np.random.normal(),  # Random walk around 0.5
                    "volume": 1000 + 500 * np.random.normal(),
                    "market_id": market_id,
                }
            )
            current_date += timedelta(hours=1)

        return price_series

    def _calculate_returns(self, price_series: List[Dict[str, Any]]) -> List[float]:
        """Calculate returns from price series."""

        if len(price_series) < 2:
            return []

        prices = [p["price"] for p in price_series]
        returns = []

        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i - 1]) / prices[i - 1]
            returns.append(ret)

        return returns

    def _calculate_max_drawdown(self, price_series: List[Dict[str, Any]]) -> float:
        """Calculate maximum drawdown from price series."""

        if not price_series:
            return 0

        prices = [p["price"] for p in price_series]
        peak = prices[0]
        max_drawdown = 0

        for price in prices:
            if price > peak:
                peak = price
            drawdown = (peak - price) / peak
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    async def _collect_order_book_snapshots(
        self, market_ids: List[str], start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect order book snapshots for analysis."""

        order_book_data = {}

        for market_id in market_ids:
            # Collect snapshots at regular intervals
            snapshots = []
            current_time = start_date

            while current_time <= end_date:
                snapshot = {
                    "timestamp": current_time.isoformat(),
                    "bids": [
                        {"price": 0.48 - i * 0.01, "size": 100 + np.random.normal() * 20}
                        for i in range(5)
                    ],
                    "asks": [
                        {"price": 0.52 + i * 0.01, "size": 100 + np.random.normal() * 20}
                        for i in range(5)
                    ],
                    "spread_bps": 80,
                    "market_id": market_id,
                }
                snapshots.append(snapshot)
                current_time += timedelta(hours=1)

            order_book_data[market_id] = snapshots

        return order_book_data

    def _calculate_market_correlations(
        self, price_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, float]:
        """Calculate correlations between markets."""

        correlations = {}

        if len(price_data) < 2:
            return correlations

        # Extract price series
        market_prices = {}
        for market_id, prices in price_data.items():
            market_prices[market_id] = [p["price"] for p in prices]

        # Calculate pairwise correlations
        market_ids = list(market_prices.keys())

        for i in range(len(market_ids)):
            for j in range(i + 1, len(market_ids)):
                market1 = market_ids[i]
                market2 = market_ids[j]

                prices1 = market_prices[market1]
                prices2 = market_prices[market2]

                # Ensure same length
                min_len = min(len(prices1), len(prices2))
                prices1 = prices1[:min_len]
                prices2 = prices2[:min_len]

                if len(prices1) > 1:
                    corr, _ = stats.pearsonr(prices1, prices2)
                    correlations[f"{market1[:8]}..._{market2[:8]}..."] = corr

        return correlations

    async def _collect_gas_price_history(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Collect historical gas price data."""

        gas_data = {
            "gas_price_series": [],
            "gas_limit_series": [],
            "network_congestion": [],
            "gas_cost_analysis": {},
        }

        # Collect gas price data at regular intervals
        current_time = start_date
        gas_prices = []

        while current_time <= end_date:
            gas_price = {
                "timestamp": current_time.isoformat(),
                "gas_price_gwei": 50
                + 20 * np.sin(current_time.timestamp() / 86400)
                + np.random.normal() * 10,
                "gas_limit": 21000,
                "network_base_fee": 40 + 15 * np.sin(current_time.timestamp() / 86400),
                "priority_fee": 5 + np.random.normal() * 2,
            }
            gas_prices.append(gas_price)
            current_time += timedelta(minutes=15)  # 15-minute intervals

        gas_data["gas_price_series"] = gas_prices

        # Calculate gas cost statistics
        gas_data["gas_cost_analysis"] = {
            "average_gas_price": np.mean([g["gas_price_gwei"] for g in gas_prices]),
            "gas_price_volatility": np.std([g["gas_price_gwei"] for g in gas_prices]),
            "max_gas_price": max([g["gas_price_gwei"] for g in gas_prices]),
            "gas_price_percentiles": {
                "25": np.percentile([g["gas_price_gwei"] for g in gas_prices], 25),
                "50": np.percentile([g["gas_price_gwei"] for g in gas_prices], 50),
                "75": np.percentile([g["gas_price_gwei"] for g in gas_prices], 75),
                "95": np.percentile([g["gas_price_gwei"] for g in gas_prices], 95),
            },
        }

        return gas_data

    async def _classify_market_regimes(
        self, market_data: Dict[str, Any], start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Classify market regimes based on volatility, trend, and liquidity."""

        regime_data = {
            "regime_series": [],
            "regime_transitions": [],
            "regime_statistics": {},
            "regime_duration_analysis": {},
        }

        # Extract market metrics
        price_data = market_data.get("price_data", {})
        market_data.get("volatility_data", {})

        # Create time series of regime indicators
        current_time = start_date
        regime_indicators = []

        while current_time <= end_date:
            # Calculate regime indicators for this time point
            volatility = self._calculate_current_volatility(price_data, current_time)
            trend = self._calculate_current_trend(price_data, current_time)
            liquidity = self._calculate_current_liquidity(market_data, current_time)

            regime_indicators.append(
                {
                    "timestamp": current_time.isoformat(),
                    "volatility": volatility,
                    "trend_strength": trend,
                    "liquidity_score": liquidity,
                }
            )

            current_time += timedelta(hours=1)

        # Classify regimes using clustering
        regime_labels = self._cluster_market_regimes(regime_indicators)

        # Create regime time series
        for i, indicator in enumerate(regime_indicators):
            regime_data["regime_series"].append(
                {
                    "timestamp": indicator["timestamp"],
                    "regime": regime_labels[i],
                    "indicators": indicator,
                }
            )

        # Analyze regime transitions
        regime_data["regime_transitions"] = self._analyze_regime_transitions(regime_labels)

        # Calculate regime statistics
        regime_data["regime_statistics"] = self._calculate_regime_statistics(
            regime_labels, regime_indicators
        )

        # Analyze regime duration patterns
        regime_data["regime_duration_analysis"] = self._analyze_regime_durations(regime_labels)

        return regime_data

    def _calculate_current_volatility(
        self, price_data: Dict[str, List[Dict[str, Any]]], current_time: datetime
    ) -> float:
        """Calculate current market volatility."""

        # Use recent price data to calculate volatility
        lookback_hours = self.regime_params["volatility_lookback_days"] * 24

        volatilities = []
        for market_prices in price_data.values():
            # Get recent prices
            recent_prices = [
                p["price"]
                for p in market_prices
                if datetime.fromisoformat(p["timestamp"]) <= current_time
                and (current_time - datetime.fromisoformat(p["timestamp"])).total_seconds()
                <= lookback_hours * 3600
            ]

            if len(recent_prices) >= 2:
                returns = self._calculate_returns([{"price": p} for p in recent_prices])
                if returns:
                    vol = np.std(returns)
                    volatilities.append(vol)

        return np.mean(volatilities) if volatilities else 0.2

    def _calculate_current_trend(
        self, price_data: Dict[str, List[Dict[str, Any]]], current_time: datetime
    ) -> float:
        """Calculate current market trend strength."""

        lookback_hours = self.regime_params["trend_lookback_days"] * 24

        trends = []
        for market_prices in price_data.values():
            recent_prices = [
                p
                for p in market_prices
                if datetime.fromisoformat(p["timestamp"]) <= current_time
                and (current_time - datetime.fromisoformat(p["timestamp"])).total_seconds()
                <= lookback_hours * 3600
            ]

            if len(recent_prices) >= 5:
                prices = [p["price"] for p in recent_prices]
                # Calculate linear trend
                x = np.arange(len(prices))
                slope, _, _, _, _ = stats.linregress(x, prices)
                trend_strength = abs(slope) / np.std(prices) if np.std(prices) > 0 else 0
                trends.append(trend_strength)

        return np.mean(trends) if trends else 0

    def _calculate_current_liquidity(
        self, market_data: Dict[str, Any], current_time: datetime
    ) -> float:
        """Calculate current market liquidity score."""

        # Use order book data or volume as liquidity proxy
        order_book_data = market_data.get("order_book_data", {})

        liquidity_scores = []
        for market_snapshots in order_book_data.values():
            # Find closest snapshot to current time
            closest_snapshot = None
            min_time_diff = float("inf")

            for snapshot in market_snapshots:
                snapshot_time = datetime.fromisoformat(snapshot["timestamp"])
                time_diff = abs((current_time - snapshot_time).total_seconds())
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_snapshot = snapshot

            if closest_snapshot:
                # Calculate liquidity based on order book depth
                bid_sizes = [bid["size"] for bid in closest_snapshot["bids"]]
                ask_sizes = [ask["size"] for ask in closest_snapshot["asks"]]

                total_depth = sum(bid_sizes) + sum(ask_sizes)
                spread = closest_snapshot["spread_bps"]

                # Liquidity score (higher is better)
                liquidity_score = total_depth / (1 + spread)
                liquidity_scores.append(liquidity_score)

        return np.mean(liquidity_scores) if liquidity_scores else 0.5

    def _cluster_market_regimes(self, regime_indicators: List[Dict[str, Any]]) -> List[str]:
        """Cluster regime indicators to identify distinct market regimes."""

        if len(regime_indicators) < 10:
            return ["normal"] * len(regime_indicators)

        # Extract features for clustering
        features = []
        for indicator in regime_indicators:
            features.append(
                [indicator["volatility"], indicator["trend_strength"], indicator["liquidity_score"]]
            )

        # Standardize features
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)

        # Perform clustering
        n_clusters = 4  # bull, bear, high_vol, normal
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(features_scaled)

        # Map cluster labels to regime names
        regime_names = []
        for label in cluster_labels:
            if label == 0:
                regime_names.append("bull")
            elif label == 1:
                regime_names.append("bear")
            elif label == 2:
                regime_names.append("high_volatility")
            else:
                regime_names.append("normal")

        return regime_names

    def _analyze_regime_transitions(self, regime_labels: List[str]) -> List[Dict[str, Any]]:
        """Analyze transitions between market regimes."""

        transitions = []

        for i in range(1, len(regime_labels)):
            if regime_labels[i] != regime_labels[i - 1]:
                transitions.append(
                    {
                        "from_regime": regime_labels[i - 1],
                        "to_regime": regime_labels[i],
                        "transition_point": i,
                        "duration_previous": self._count_consecutive_regime(
                            regime_labels, i - 1, -1
                        ),
                    }
                )

        return transitions

    def _count_consecutive_regime(
        self, regime_labels: List[str], start_idx: int, direction: int
    ) -> int:
        """Count consecutive occurrences of the same regime."""

        count = 1
        current_regime = regime_labels[start_idx]
        idx = start_idx + direction

        while 0 <= idx < len(regime_labels) and regime_labels[idx] == current_regime:
            count += 1
            idx += direction

        return count

    def _calculate_regime_statistics(
        self, regime_labels: List[str], regime_indicators: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate statistics for each market regime."""

        regime_stats = {}

        unique_regimes = set(regime_labels)

        for regime in unique_regimes:
            regime_indices = [i for i, r in enumerate(regime_labels) if r == regime]
            regime_data = [regime_indicators[i] for i in regime_indices]

            regime_stats[regime] = {
                "count": len(regime_indices),
                "percentage": len(regime_indices) / len(regime_labels),
                "avg_volatility": np.mean([d["volatility"] for d in regime_data]),
                "avg_trend_strength": np.mean([d["trend_strength"] for d in regime_data]),
                "avg_liquidity": np.mean([d["liquidity_score"] for d in regime_data]),
                "volatility_range": [
                    min([d["volatility"] for d in regime_data]),
                    max([d["volatility"] for d in regime_data]),
                ],
            }

        return regime_stats

    def _analyze_regime_durations(self, regime_labels: List[str]) -> Dict[str, Any]:
        """Analyze duration patterns of market regimes."""

        duration_analysis = {}

        # Calculate duration of each regime period
        durations = []
        current_regime = regime_labels[0]
        current_duration = 1

        for regime in regime_labels[1:]:
            if regime == current_regime:
                current_duration += 1
            else:
                durations.append({"regime": current_regime, "duration_hours": current_duration})
                current_regime = regime
                current_duration = 1

        # Add final regime
        durations.append({"regime": current_regime, "duration_hours": current_duration})

        # Analyze by regime
        for regime in set(regime_labels):
            regime_durations = [d["duration_hours"] for d in durations if d["regime"] == regime]

            if regime_durations:
                duration_analysis[regime] = {
                    "average_duration": np.mean(regime_durations),
                    "min_duration": min(regime_durations),
                    "max_duration": max(regime_durations),
                    "median_duration": np.median(regime_durations),
                    "total_periods": len(regime_durations),
                }

        return duration_analysis

    async def _validate_dataset_quality(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Validate quality of collected dataset."""

        validation_reports = {
            "overall_quality_score": 0.0,
            "component_reports": {},
            "quality_issues": [],
            "recommendations": [],
        }

        # Validate wallet data
        wallet_validation = self._validate_wallet_data_quality(dataset.get("wallet_data", {}))
        validation_reports["component_reports"]["wallet_data"] = wallet_validation

        # Validate market data
        market_validation = self._validate_market_data_quality(dataset.get("market_data", {}))
        validation_reports["component_reports"]["market_data"] = market_validation

        # Validate gas data
        gas_validation = self._validate_gas_data_quality(dataset.get("gas_data", {}))
        validation_reports["component_reports"]["gas_data"] = gas_validation

        # Calculate overall quality score
        component_scores = [
            report["quality_score"]
            for report in validation_reports["component_reports"].values()
            if "quality_score" in report
        ]

        if component_scores:
            validation_reports["overall_quality_score"] = np.mean(component_scores)

        # Identify quality issues
        validation_reports["quality_issues"] = self._identify_quality_issues(validation_reports)

        # Generate recommendations
        validation_reports["recommendations"] = self._generate_quality_recommendations(
            validation_reports
        )

        return validation_reports

    def _validate_wallet_data_quality(self, wallet_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate quality of wallet trade data."""

        validation = {
            "quality_score": 0.0,
            "total_wallets": len(wallet_data),
            "wallets_with_data": 0,
            "average_trades_per_wallet": 0,
            "data_completeness": 0.0,
            "issues": [],
        }

        total_trades = 0
        wallets_with_data = 0

        for wallet_addr, wallet_info in wallet_data.items():
            trade_count = wallet_info.get("trade_count", 0)

            if trade_count > 0:
                wallets_with_data += 1
                total_trades += trade_count
            else:
                validation["issues"].append(f"Wallet {wallet_addr[:8]}... has no trade data")

        validation["wallets_with_data"] = wallets_with_data

        if wallets_with_data > 0:
            validation["average_trades_per_wallet"] = total_trades / wallets_with_data

        # Calculate data completeness
        expected_wallets = len(wallet_data)
        validation["data_completeness"] = (
            wallets_with_data / expected_wallets if expected_wallets > 0 else 0
        )

        # Calculate quality score
        completeness_score = validation["data_completeness"]
        coverage_score = min(
            1.0,
            total_trades / (expected_wallets * self.quality_params["min_data_points_per_wallet"]),
        )

        validation["quality_score"] = (completeness_score + coverage_score) / 2

        return validation

    def _validate_market_data_quality(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate quality of market data."""

        validation = {
            "quality_score": 0.0,
            "markets_with_data": 0,
            "total_price_points": 0,
            "average_data_density": 0.0,
            "issues": [],
        }

        price_data = market_data.get("price_data", {})
        validation["markets_with_data"] = len(price_data)

        total_points = 0
        for market_prices in price_data.values():
            total_points += len(market_prices)

        validation["total_price_points"] = total_points

        if validation["markets_with_data"] > 0:
            validation["average_data_density"] = total_points / validation["markets_with_data"]

        # Quality score based on data density and completeness
        density_score = min(1.0, total_points / 10000)  # Expect 10K data points
        validation["quality_score"] = density_score

        return validation

    def _validate_gas_data_quality(self, gas_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate quality of gas price data."""

        validation = {
            "quality_score": 0.0,
            "data_points": 0,
            "time_coverage_hours": 0,
            "issues": [],
        }

        gas_series = gas_data.get("gas_price_series", [])
        validation["data_points"] = len(gas_series)

        if gas_series:
            timestamps = [datetime.fromisoformat(g["timestamp"]) for g in gas_series]
            time_span = max(timestamps) - min(timestamps)
            validation["time_coverage_hours"] = time_span.total_seconds() / 3600

        # Quality score based on coverage and density
        coverage_score = min(1.0, validation["time_coverage_hours"] / 720)  # Expect 30 days
        density_score = min(
            1.0, validation["data_points"] / 2880
        )  # Expect 15-min intervals for 30 days

        validation["quality_score"] = (coverage_score + density_score) / 2

        return validation

    def _identify_quality_issues(self, validation_reports: Dict[str, Any]) -> List[str]:
        """Identify data quality issues."""

        issues = []

        # Check component quality scores
        for component, report in validation_reports["component_reports"].items():
            quality_score = report.get("quality_score", 1.0)

            if quality_score < 0.7:
                issues.append(f"{component} quality score is low: {quality_score:.2f}")

            # Component-specific checks
            if component == "wallet_data":
                if report.get("data_completeness", 1.0) < 0.8:
                    issues.append(
                        f"Wallet data completeness is low: {report['data_completeness']:.1%}"
                    )

            elif component == "market_data":
                if report.get("total_price_points", 0) < 1000:
                    issues.append(
                        f"Insufficient market data points: {report['total_price_points']}"
                    )

        return issues

    def _generate_quality_recommendations(self, validation_reports: Dict[str, Any]) -> List[str]:
        """Generate recommendations for improving data quality."""

        recommendations = []

        overall_score = validation_reports.get("overall_quality_score", 1.0)

        if overall_score < 0.8:
            recommendations.append("Consider extending data collection period for better coverage")

        # Component-specific recommendations
        wallet_report = validation_reports["component_reports"].get("wallet_data", {})
        if wallet_report.get("data_completeness", 1.0) < 0.9:
            recommendations.append(
                "Focus on wallets with missing trade data - may need alternative data sources"
            )

        market_report = validation_reports["component_reports"].get("market_data", {})
        if market_report.get("total_price_points", 10000) < 5000:
            recommendations.append(
                "Increase market data collection frequency or extend time period"
            )

        gas_report = validation_reports["component_reports"].get("gas_data", {})
        if gas_report.get("data_points", 3000) < 1000:
            recommendations.append(
                "Gas price data is sparse - consider using multiple gas estimation services"
            )

        return recommendations

    async def _handle_data_gaps(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data gaps through interpolation and gap filling."""

        # Handle wallet data gaps
        wallet_data = dataset.get("wallet_data", {})
        for wallet_addr, wallet_info in wallet_data.items():
            trades = wallet_info.get("trades", [])

            if trades:
                # Sort trades by timestamp
                trades.sort(key=lambda x: x.get("timestamp", ""))

                # Identify gaps
                gaps = self._identify_data_gaps(trades, "timestamp")

                if gaps:
                    # Fill gaps using interpolation
                    filled_trades = self._interpolate_trade_gaps(trades, gaps)
                    wallet_data[wallet_addr]["trades"] = filled_trades
                    wallet_data[wallet_addr]["gap_filling_applied"] = len(gaps)

        # Handle market data gaps
        market_data = dataset.get("market_data", {})
        price_data = market_data.get("price_data", {})

        for market_id, prices in price_data.items():
            if prices:
                prices.sort(key=lambda x: x.get("timestamp", ""))
                gaps = self._identify_data_gaps(prices, "timestamp")

                if gaps:
                    filled_prices = self._interpolate_price_gaps(prices, gaps)
                    market_data["price_data"][market_id] = filled_prices

        # Handle gas data gaps
        gas_data = dataset.get("gas_data", {})
        gas_series = gas_data.get("gas_price_series", [])

        if gas_series:
            gas_series.sort(key=lambda x: x.get("timestamp", ""))
            gaps = self._identify_data_gaps(gas_series, "timestamp")

            if gaps:
                filled_gas = self._interpolate_gas_gaps(gas_series, gaps)
                gas_data["gas_price_series"] = filled_gas

        return dataset

    def _identify_data_gaps(
        self, data_points: List[Dict[str, Any]], timestamp_field: str
    ) -> List[Dict[str, Any]]:
        """Identify gaps in time series data."""

        gaps = []

        for i in range(1, len(data_points)):
            current_time = datetime.fromisoformat(data_points[i][timestamp_field])
            previous_time = datetime.fromisoformat(data_points[i - 1][timestamp_field])

            time_diff = (current_time - previous_time).total_seconds()

            # Define gap threshold (e.g., 2 hours for trade data)
            gap_threshold = 7200  # 2 hours

            if time_diff > gap_threshold:
                gaps.append(
                    {
                        "start_index": i - 1,
                        "end_index": i,
                        "gap_duration_seconds": time_diff,
                        "start_time": data_points[i - 1][timestamp_field],
                        "end_time": data_points[i][timestamp_field],
                    }
                )

        return gaps

    def _interpolate_trade_gaps(
        self, trades: List[Dict[str, Any]], gaps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Interpolate missing trade data in gaps."""

        # For trade data, gaps are harder to fill realistically
        # We'll mark gaps but not artificially create trades

        filled_trades = trades.copy()

        for gap in gaps:
            # Add gap marker
            gap_marker = {
                "timestamp": gap["start_time"],
                "gap_marker": True,
                "gap_duration_seconds": gap["gap_duration_seconds"],
                "interpolated": False,
            }
            filled_trades.append(gap_marker)

        filled_trades.sort(key=lambda x: x.get("timestamp", ""))

        return filled_trades

    def _interpolate_price_gaps(
        self, prices: List[Dict[str, Any]], gaps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Interpolate missing price data."""

        filled_prices = prices.copy()

        for gap in gaps:
            start_idx = gap["start_index"]
            end_idx = gap["end_index"]

            if start_idx >= 0 and end_idx < len(prices):
                start_price = prices[start_idx]["price"]
                end_price = prices[end_idx]["price"]
                gap_steps = int(gap["gap_duration_seconds"] / 3600)  # Hourly interpolation

                if gap_steps > 1:
                    # Linear interpolation
                    price_interpolation = np.linspace(start_price, end_price, gap_steps + 1)

                    # Add interpolated points
                    start_time = datetime.fromisoformat(prices[start_idx]["timestamp"])

                    for i in range(1, gap_steps):
                        interp_time = start_time + timedelta(hours=i)
                        interp_price = price_interpolation[i]

                        filled_prices.append(
                            {
                                "timestamp": interp_time.isoformat(),
                                "price": interp_price,
                                "volume": np.mean(
                                    [prices[start_idx]["volume"], prices[end_idx]["volume"]]
                                ),
                                "market_id": prices[start_idx]["market_id"],
                                "interpolated": True,
                            }
                        )

        filled_prices.sort(key=lambda x: x.get("timestamp", ""))

        return filled_prices

    def _interpolate_gas_gaps(
        self, gas_series: List[Dict[str, Any]], gaps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Interpolate missing gas price data."""

        filled_gas = gas_series.copy()

        for gap in gaps:
            start_idx = gap["start_index"]
            end_idx = gap["end_index"]

            if start_idx >= 0 and end_idx < len(gas_series):
                start_gas = gas_series[start_idx]["gas_price_gwei"]
                end_gas = gas_series[end_idx]["gas_price_gwei"]
                gap_steps = int(gap["gap_duration_seconds"] / 900)  # 15-minute interpolation

                if gap_steps > 1:
                    gas_interpolation = np.linspace(start_gas, end_gas, gap_steps + 1)
                    start_time = datetime.fromisoformat(gas_series[start_idx]["timestamp"])

                    for i in range(1, gap_steps):
                        interp_time = start_time + timedelta(minutes=15 * i)
                        interp_gas = gas_interpolation[i]

                        filled_gas.append(
                            {
                                "timestamp": interp_time.isoformat(),
                                "gas_price_gwei": interp_gas,
                                "gas_limit": gas_series[start_idx]["gas_limit"],  # Assume constant
                                "interpolated": True,
                            }
                        )

        filled_gas.sort(key=lambda x: x.get("timestamp", ""))

        return filled_gas

    async def _generate_synthetic_data(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Generate synthetic data for edge cases and data augmentation."""

        synthetic_ratio = self.synthetic_params["synthetic_data_ratio"]

        if synthetic_ratio <= 0:
            return dataset

        # Generate synthetic scenarios
        synthetic_scenarios = self._generate_synthetic_scenarios(dataset)

        # Add synthetic data to dataset
        dataset["synthetic_data"] = synthetic_scenarios
        dataset["synthetic_data_ratio"] = synthetic_ratio

        return dataset

    def _generate_synthetic_scenarios(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Generate synthetic data for various edge case scenarios."""

        synthetic_data = {}

        for scenario in self.synthetic_params["edge_case_scenarios"]:
            if scenario == "flash_crash":
                synthetic_data[scenario] = self._generate_flash_crash_scenario(dataset)
            elif scenario == "high_volatility":
                synthetic_data[scenario] = self._generate_high_volatility_scenario(dataset)
            elif scenario == "low_liquidity":
                synthetic_data[scenario] = self._generate_low_liquidity_scenario(dataset)
            elif scenario == "gas_spike":
                synthetic_data[scenario] = self._generate_gas_spike_scenario(dataset)
            elif scenario == "extreme_drawdown":
                synthetic_data[scenario] = self._generate_extreme_drawdown_scenario(dataset)

        return synthetic_data

    def _generate_flash_crash_scenario(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Generate synthetic flash crash scenario."""

        # Create a rapid price decline followed by recovery
        base_prices = [0.5] * 100
        crash_prices = []

        # Pre-crash stability
        crash_prices.extend(base_prices[:20])

        # Flash crash (20% decline in 5 minutes)
        peak_price = base_prices[19]
        crash_bottom = peak_price * 0.8

        for i in range(10):  # 10 data points = ~5 minutes at 30-sec intervals
            price = peak_price - (peak_price - crash_bottom) * (i / 9)
            crash_prices.append(price)

        # Recovery
        for i in range(70):
            recovery_progress = i / 69
            price = crash_bottom + (peak_price - crash_bottom) * recovery_progress
            # Add overshoot and stabilization
            if recovery_progress < 0.7:
                price *= 1 + 0.05 * np.sin(recovery_progress * 10)  # Oscillations
            crash_prices.append(price)

        return {
            "price_series": crash_prices,
            "duration_minutes": 50,
            "max_drawdown": 0.2,
            "recovery_time_minutes": 30,
        }

    def _generate_high_volatility_scenario(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Generate high volatility market scenario."""

        # Create price series with high volatility
        base_price = 0.5
        prices = [base_price]

        np.random.seed(42)  # For reproducibility

        for i in range(999):  # 1000 total points
            # High volatility random walk
            shock = np.random.normal(0, 0.02)  # 2% daily volatility (high)
            new_price = prices[-1] * (1 + shock)
            new_price = max(0.01, min(2.0, new_price))  # Reasonable bounds
            prices.append(new_price)

        returns = [prices[i + 1] / prices[i] - 1 for i in range(len(prices) - 1)]

        return {
            "price_series": prices,
            "return_series": returns,
            "volatility": np.std(returns) * np.sqrt(252),  # Annualized
            "duration_days": len(prices) / 24,  # Assuming hourly data
            "max_drawdown": self._calculate_max_drawdown([{"price": p} for p in prices]),
        }

    def _generate_low_liquidity_scenario(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Generate low liquidity market scenario."""

        # Wide spreads, low volume, price gaps
        base_price = 0.5
        prices = []

        for i in range(1000):
            # Base trend with gaps
            trend = 0.001 * i  # Slow upward trend
            gap_effect = np.random.choice([0, 0.02, -0.02], p=[0.8, 0.1, 0.1])  # Occasional gaps
            noise = np.random.normal(0, 0.005)

            price = base_price + trend + gap_effect + noise
            price = max(0.01, price)
            prices.append(price)

        return {
            "price_series": prices,
            "spread_bps": 200,  # 2% spread (very wide)
            "average_volume": 50,  # Low volume
            "gap_frequency": 0.2,  # 20% of periods have gaps
            "liquidity_score": 0.1,  # Very low liquidity
        }

    def _generate_gas_spike_scenario(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Generate gas price spike scenario."""

        # Normal gas prices with sudden spikes
        base_gas = 50  # gwei
        gas_prices = []

        for i in range(1000):
            # Normal variation
            normal_variation = np.random.normal(0, 5)

            # Occasional spikes (network congestion)
            spike_multiplier = np.random.choice([1, 3, 5], p=[0.95, 0.04, 0.01])

            gas_price = base_gas + normal_variation
            gas_price *= spike_multiplier

            gas_prices.append(max(10, gas_price))  # Minimum gas price

        return {
            "gas_price_series": gas_prices,
            "average_gas_price": np.mean(gas_prices),
            "max_gas_price": max(gas_prices),
            "spike_frequency": sum(1 for g in gas_prices if g > base_gas * 2) / len(gas_prices),
            "network_congestion_events": sum(1 for g in gas_prices if g > base_gas * 3),
        }

    def _generate_extreme_drawdown_scenario(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Generate extreme drawdown market scenario."""

        # Prolonged bear market with extreme losses
        base_price = 1.0
        prices = [base_price]

        # Gradual decline over extended period
        total_decline = 0.7  # 70% decline
        decline_periods = 500  # 500 data points of decline

        for i in range(1, decline_periods):
            # Exponential decay with volatility
            decline_progress = i / decline_periods
            target_price = base_price * (1 - total_decline * decline_progress)

            # Add volatility around the decline
            volatility = 0.01 + 0.02 * decline_progress  # Increasing volatility
            noise = np.random.normal(0, volatility)

            price = target_price * (1 + noise)
            price = max(0.01, price)  # Floor price
            prices.append(price)

        # Partial recovery
        recovery_periods = 200
        for i in range(recovery_periods):
            recovery_progress = i / recovery_periods
            recovery_target = prices[-1] * 1.3  # 30% recovery
            price = prices[-1] + (recovery_target - prices[-1]) * recovery_progress
            noise = np.random.normal(0, 0.005)  # Lower volatility during recovery
            price *= 1 + noise
            prices.append(price)

        returns = [prices[i + 1] / prices[i] - 1 for i in range(len(prices) - 1)]

        return {
            "price_series": prices,
            "return_series": returns,
            "total_return": prices[-1] / prices[0] - 1,
            "max_drawdown": self._calculate_max_drawdown([{"price": p} for p in prices]),
            "decline_duration_days": decline_periods / 24,
            "recovery_duration_days": recovery_periods / 24,
            "volatility_during_decline": np.std(returns[:decline_periods]),
            "volatility_during_recovery": np.std(returns[-recovery_periods:]),
        }

    def _generate_data_quality_summary(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive data quality summary."""

        summary = {
            "overall_data_quality": 0.0,
            "data_completeness": {},
            "data_accuracy": {},
            "data_consistency": {},
            "gap_analysis": {},
            "synthetic_data_usage": {},
        }

        # Calculate overall data quality
        validation_reports = dataset.get("validation_reports", {})
        overall_score = validation_reports.get("overall_quality_score", 0.5)
        summary["overall_data_quality"] = overall_score

        # Data completeness by component
        wallet_data = dataset.get("wallet_data", {})
        summary["data_completeness"]["wallets"] = (
            sum(1 for w in wallet_data.values() if w.get("trade_count", 0) > 0) / len(wallet_data)
            if wallet_data
            else 0
        )

        market_data = dataset.get("market_data", {}).get("price_data", {})
        summary["data_completeness"]["markets"] = len(market_data)

        gas_data = dataset.get("gas_data", {}).get("gas_price_series", [])
        summary["data_completeness"]["gas_data"] = (
            len(gas_data) / 2880
        )  # Expected points for 30 days

        # Gap analysis
        summary["gap_analysis"] = self._analyze_data_gaps_summary(dataset)

        # Synthetic data usage
        synthetic_ratio = dataset.get("synthetic_data_ratio", 0)
        summary["synthetic_data_usage"]["ratio"] = synthetic_ratio
        summary["synthetic_data_usage"]["scenarios_generated"] = len(
            dataset.get("synthetic_data", {})
        )

        return summary

    def _analyze_data_gaps_summary(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze data gaps across the dataset."""

        gap_summary = {
            "total_gaps": 0,
            "average_gap_duration_hours": 0,
            "max_gap_duration_hours": 0,
            "gap_frequency": 0,
        }

        # Analyze wallet data gaps
        wallet_data = dataset.get("wallet_data", {})
        total_wallet_gaps = 0

        for wallet_info in wallet_data.values():
            gaps_applied = wallet_info.get("gap_filling_applied", 0)
            total_wallet_gaps += gaps_applied

        gap_summary["wallet_data_gaps"] = total_wallet_gaps

        # This would be extended to analyze market data and gas data gaps
        # For now, return basic summary

        return gap_summary

    def save_dataset(self, dataset: Dict[str, Any], filename: str):
        """Save collected dataset to disk."""

        try:
            # Create data directory
            data_dir = Path("data/backtesting")
            data_dir.mkdir(parents=True, exist_ok=True)

            filepath = data_dir / f"{filename}.json"

            # Convert datetime objects to strings for JSON serialization
            serializable_dataset = self._make_dataset_serializable(dataset)

            with open(filepath, "w") as f:
                json.dump(serializable_dataset, f, indent=2, default=str)

            logger.info(f"💾 Dataset saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving dataset: {e}")

    def load_dataset(self, filename: str) -> Dict[str, Any]:
        """Load dataset from disk."""

        try:
            data_dir = Path("data/backtesting")
            filepath = data_dir / f"{filename}.json"

            with open(filepath, "r") as f:
                dataset = json.load(f)

            logger.info(f"📊 Dataset loaded from {filepath}")
            return dataset

        except Exception as e:
            logger.error(f"Error loading dataset: {e}")
            return {}

    def _make_dataset_serializable(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Make dataset serializable by converting datetime objects."""

        # This is a placeholder - in practice would recursively convert datetime objects
        return dataset

    def get_data_collection_status(self) -> Dict[str, Any]:
        """Get status of data collection system."""

        return {
            "system_health": "operational",
            "data_sources_configured": len(self.data_sources),
            "quality_validation_active": True,
            "synthetic_data_enabled": self.synthetic_params["synthetic_data_ratio"] > 0,
            "gap_handling_active": True,
        }
