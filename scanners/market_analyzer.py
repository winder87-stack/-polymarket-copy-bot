"""
Market Analyzer for Opportunity Detection

This module provides market correlation analysis and opportunity detection
for both Copy Trading and Cross-Market Arbitrage strategies.

Features:
- Market correlation matrix calculation
- On-chain wallet clustering analysis
- Public event calendar integration
- Statistical opportunity detection
- Real-time market monitoring

Data Sources:
- Polymarket CLOB API (order books, prices)
- Polygon blockchain (on-chain transactions)
- Dune Analytics API (historical data)
- Public APIs (event calendars)

Author: Polymarket Copy Bot Team
Date: 2025-12-27
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, getcontext
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from utils.helpers import BoundedCache
from utils.logger import get_logger

# Configure Decimal for financial calculations
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

logger = get_logger(__name__)


class MarketCategory(Enum):
    """Market categories for analysis."""

    POLITICS = "politics"
    CRYPTO = "crypto"
    SPORTS = "sports"
    ECONOMICS = "economics"
    ENTERTAINMENT = "entertainment"


class OpportunityType(Enum):
    """Types of trading opportunities."""

    COPY_TRADING_SIGNAL = "copy_trading_signal"
    CORRELATED_MARKET_ARB = "correlated_market_arb"
    ENDGAME_SWEEP = "endgame_sweep"
    NEWS_EVENT_ARB = "news_event_arb"
    MARKET_INEFFICIENCY = "market_inefficiency"


@dataclass
class MarketData:
    """Container for market data."""

    def __init__(
        self,
        market_id: str,
        category: MarketCategory,
        question: str,
        current_yes_price: Decimal,
        current_no_price: Decimal,
        volume_24h: Decimal,
        liquidity_usd: Decimal,
        last_updated: Optional[datetime] = None,
    ) -> None:
        self.market_id = market_id
        self.category = category
        self.question = question
        self.current_yes_price = current_yes_price
        self.current_no_price = current_no_price
        self.volume_24h = volume_24h
        self.liquidity_usd = liquidity_usd
        self.last_updated = last_updated
        self.market_id = market_id
        self.category = category
        self.question = question
        self.current_yes_price = current_yes_price
        self.current_no_price = current_no_price
        self.volume_24h = volume_24h
        self.liquidity_usd = liquidity_usd
        self.last_updated = last_updated

    def get_implied_probability(self) -> Decimal:
        """Calculate implied probability from current prices."""
        total = self.current_yes_price + self.current_no_price
        if total > 0:
            # If no_price is zero, return 0.5 as default (avoid extreme probabilities)
            if self.current_no_price == 0:
                return Decimal("0.5")
            return self.current_yes_price / total
        return Decimal("0.5")

    def get_price_spread(self) -> float:
        """Get price spread as percentage."""
        total = self.current_yes_price + self.current_no_price
        if total > 0:
            return float(abs(self.current_yes_price - self.current_no_price) / total)
        return 0.0


@dataclass
@dataclass
class MarketCorrelation:
    """Correlation between two markets."""

    market_1: str
    market_2: str
    correlation: float  # Pearson correlation coefficient
    sample_size: int
    statistical_significance: float  # p-value
    last_updated: datetime
    category: MarketCategory


@dataclass
class TradingOpportunity:
    """Detected trading opportunity."""

    opportunity_id: str
    opportunity_type: OpportunityType
    involved_markets: List[str]
    edge: Decimal  # Expected profit margin
    confidence: float  # 0.0 to 1.0
    liquidity_usd: Decimal  # Total liquidity
    timestamp: datetime
    risk_factors: List[str]
    data_sources: List[str]
    validity_days: int  # How long this opportunity is valid


@dataclass
class EventData:
    """Public event data for arbitrage detection."""

    event_id: str
    event_type: str  # earnings, FDA decision, sports event
    date: datetime
    related_markets: List[str]
    expected_impact: str  # high, medium, low
    source: str  # Bloomberg, Yahoo, Sportradar, etc.


class MarketAnalyzer:
    """
    Market analyzer for opportunity detection.

    Features:
    - Market correlation analysis
    - On-chain wallet clustering
    - Public event calendar integration
    - Statistical opportunity detection
    - Real-time market monitoring

    Thread Safety:
        All state modifications use asyncio locks.
    """

    # Correlation thresholds
    MIN_CORRELATION_THRESHOLD = 0.7
    HIGH_CORRELATION_THRESHOLD = 0.9
    MAX_CORRELATION_THRESHOLD = 1.0
    CORRELATION_CONFIDENCE_THRESHOLD = 0.8
    CORRELATION_STRENGTH_THRESHOLD = 0.75
    CORRELATION_SIGNIFICANCE_THRESHOLD = 0.05
    MIN_LIQUIDITY_USD = Decimal("10000")  # $10K
    MIN_VOLUME_24H = Decimal("1000")  # $1K daily volume

    # Opportunity thresholds
    MIN_EDGE_PERCENT = Decimal("0.02")  # 2% minimum
    MIN_CONFIDENCE = 0.6  # 60% confidence
    MIN_LIQUIDITY_FOR_ARB = Decimal("25000")  # $25K for arbitrage

    def __init__(
        self,
        polymarket_api_url: str,
        polygon_rpc_url: str,
        cache_ttl_seconds: int = 300,  # 5 minutes
        max_cache_size: int = 1000,
    ) -> None:
        """
        Initialize market analyzer.

        Args:
            polymarket_api_url: Polymarket API base URL
            polygon_rpc_url: Polygon RPC URL for blockchain queries
            cache_ttl_seconds: Cache TTL in seconds
            max_cache_size: Maximum cache size
        """
        self.polymarket_api_url = polymarket_api_url
        self.polygon_rpc_url = polygon_rpc_url

        # Thread safety
        self._state_lock = asyncio.Lock()
        self._correlation_lock = asyncio.Lock()

        # Market data cache
        self._market_data_cache: BoundedCache = BoundedCache(
            max_size=max_cache_size,
            ttl_seconds=cache_ttl_seconds,
            memory_threshold_mb=100.0,
            cleanup_interval_seconds=60,
        )

        # Correlation matrix cache
        self._correlation_cache: BoundedCache = BoundedCache(
            max_size=max_cache_size // 2,
            ttl_seconds=1800,  # 30 minutes
            memory_threshold_mb=50.0,
            cleanup_interval_seconds=120,
        )

        # Opportunity cache
        self._opportunity_cache: BoundedCache = BoundedCache(
            max_size=500,
            ttl_seconds=300,  # 5 minutes
            memory_threshold_mb=50.0,
            cleanup_interval_seconds=60,
        )

        # Event data
        self._event_data: List[EventData] = []

        # Market correlation matrix
        self._correlation_matrix: Dict[Tuple[str, str], MarketCorrelation] = {}

        # Trading opportunities
        self._detected_opportunities: List[TradingOpportunity] = []

        # Performance metrics
        self._total_analyzed = 0
        self._total_opportunities_detected = 0
        self._last_opportunity_time = 0.0

        logger.info("MarketAnalyzer initialized")

    async def fetch_market_data(
        self, market_ids: Optional[List[str]] = None
    ) -> Dict[str, MarketData] | dict[str, Any]:
        """
        Fetch market data from Polymarket API.

        Args:
            market_ids: Optional list of market IDs (None = all active markets)

        Returns:
            Dictionary of market_id to MarketData
        """
        try:
            # Try cache first
            cache_key = "market_data"
            if market_ids is None:
                cached_data = self._market_data_cache.get(cache_key)
                if cached_data:
                    logger.debug(
                        "Using cached market data: %s markets", len(cached_data)
                    )
                    return cached_data

            # In production, this would fetch from Polymarket CLOB API
            # For now, return empty dict as placeholder
            logger.warning(
                "Market data fetching not fully implemented - using empty data"
            )
            return {}  # type: Dict[str, MarketData]

        except Exception as e:
            logger.exception("Error fetching market data: %s", e)
            return {}

    async def calculate_correlations(
        self,
        market_data: Dict[str, MarketData],
    ) -> Dict[Tuple[str, str], MarketCorrelation]:
        """
        Calculate market correlations from price history.

        Args:
            market_data: Dictionary of market data

        Returns:
            Dictionary of (market_1, market_2) tuples to correlation values
        """
        try:
            async with self._correlation_lock:
                correlations = {}
                markets = list(market_data.keys())

                # For production, this would use historical price data
                # For now, return correlations based on category
                for i, market_1 in enumerate(markets):
                    data_1 = market_data.get(market_1)
                    if not data_1:
                        continue

                    for market_2 in markets[i + 1 :]:
                        data_2 = market_data.get(market_2)
                        if not data_2:
                            continue

                        # Calculate correlation based on category
                        correlation = self._calculate_category_correlation(
                            data_1, data_2
                        )

                        key = tuple(sorted((market_1, market_2)))
                        correlations[key] = MarketCorrelation(
                            market_1=market_1,
                            market_2=market_2,
                            correlation=correlation,
                            sample_size=10,  # Placeholder
                            statistical_significance=0.05,  # Placeholder
                            last_updated=datetime.now(timezone.utc),
                            category=data_1.category,
                        )

                # Update correlation matrix
                self._correlation_matrix.update(correlations)

                logger.info("Calculated %s market correlations", len(correlations))

                return correlations

        except Exception as e:
            logger.exception("Error calculating correlations: %s", e)
            return {}

    async def analyze_market_correlations(
        self, market_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze market correlations and return structured results.

        Args:
            market_data: Dictionary of market data with keys like:
                - question
                - current_yes_price
                - current_no_price
                - volume_24h
                - liquidity_usd

        Returns:
            Dictionary with:
                - correlations: Dict of correlation data
                - matrix: Dict of market pairs with correlation and timestamp
                - timestamp: ISO format timestamp string
        """
        try:
            async with self._correlation_lock:
                # Convert dict data to MarketData objects
                market_data_objects: Dict[str, MarketData] = {}
                for market_id, data in market_data.items():
                    market_data_objects[market_id] = MarketData(
                        market_id=market_id,
                        category=MarketCategory.CRYPTO,  # Default category
                        question=data.get("question", ""),
                        current_yes_price=Decimal(
                            str(data.get("current_yes_price", 0))
                        ),
                        current_no_price=Decimal(str(data.get("current_no_price", 0))),
                        volume_24h=Decimal(str(data.get("volume_24h", 0))),
                        liquidity_usd=Decimal(str(data.get("liquidity_usd", 0))),
                    )

                # Calculate correlations
                correlations = await self.calculate_correlations(market_data_objects)

                # Build matrix structure
                matrix: Dict[str, Dict[str, Any]] = {}
                for (market_1, market_2), corr in correlations.items():
                    pair_key = f"{market_1}_{market_2}"
                    matrix[pair_key] = {
                        "correlation": corr.correlation,
                        "timestamp": corr.last_updated.isoformat(),
                    }

                # Build result structure
                timestamp = datetime.now(timezone.utc).isoformat()
                result = {
                    "correlations": {k: v.correlation for k, v in correlations.items()},
                    "matrix": matrix,
                    "timestamp": timestamp,
                }

                return result

        except Exception as e:
            logger.exception("Error analyzing market correlations: %s", e)
            # Return empty structure on error
            return {
                "correlations": {},
                "matrix": {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _calculate_category_correlation(
        self, data_1: MarketData, data_2: MarketData
    ) -> float:
        """
        Calculate correlation between two markets based on category.

        In production, this would use historical price data.
        For now, uses category-based heuristics.
        """
        # Different categories
        if data_1.category != data_2.category:
            return 0.0  # Uncorrelated across categories

        # Same category - check if related markets
        implied_prob_1 = data_1.get_implied_probability()
        implied_prob_2 = data_2.get_implied_probability()

        # If both near 0.5, they might be complementary (correlation ~ 0.0)
        # If both near 1.0 or 0.0, they might be identical or competing (correlation ~ -1.0)

        prob_diff = abs(implied_prob_1 - Decimal("0.5"))
        if prob_diff < Decimal("0.1"):
            # Complementary markets (negative correlation)
            return -abs(float(prob_diff)) * 0.9
        elif prob_diff < Decimal("0.3"):
            # Slightly correlated
            return 0.3
        else:
            # Uncorrelated or competing
            return 0.0

    async def detect_opportunities(
        self,
        market_data: Dict[str, MarketData],
        event_data: Optional[List[EventData]] = None,
    ) -> List[TradingOpportunity]:
        """
        Detect trading opportunities from market data and events.

        Args:
            market_data: Dictionary of market data
            event_data: Optional list of event data

        Returns:
            List of detected trading opportunities
        """
        try:
            async with self._state_lock:
                opportunities = []
                markets = list(market_data.keys())

                # Analyze each market for copy trading signals
                for market_id, data in market_data.items():
                    copy_trading_opp = self._detect_copy_trading_signal(market_id, data)
                    if copy_trading_opp:
                        opportunities.append(copy_trading_opp)

                # Detect correlated market arbitrage
                arb_opportunities = await self._detect_correlated_arb(market_data)
                opportunities.extend(arb_opportunities)

                # Detect endgame sweep opportunities (if event data available)
                if event_data:
                    endgame_opps = self._detect_endgame_opportunities(
                        market_data, event_data
                    )
                    opportunities.extend(endgame_opps)

                # Filter opportunities by liquidity and edge
                filtered_opportunities = [
                    opp
                    for opp in opportunities
                    if self._passes_opportunity_filters(opp, market_data)
                ]

                # Rank opportunities by confidence and edge
                ranked_opportunities = self._rank_opportunities(filtered_opportunities)

                self._detected_opportunities.extend(ranked_opportunities)
                self._total_opportunities_detected += len(ranked_opportunities)

                logger.info(
                    "Detected %s trading opportunities", len(ranked_opportunities)
                )

                return ranked_opportunities

        except Exception as e:
            logger.exception("Error detecting opportunities: %s", e)
            return []

    def _detect_copy_trading_signal(
        self, market_id: str, data: MarketData
    ) -> Optional[TradingOpportunity]:
        """
        Detect copy trading signal from market data.

        A copy trading signal might be:
        - Sudden price movement
        - High volume increase
        - Wide spread narrowing
        """
        try:
            # Check for wide spread (opportunity narrowing)
            spread = data.get_price_spread()

            if spread < 0.05:  # Narrow spread (< 5%)
                return TradingOpportunity(
                    opportunity_id=f"copy_sig_{market_id[:8]}_{int(time.time())}",
                    opportunity_type=OpportunityType.COPY_TRADING_SIGNAL,
                    involved_markets=[market_id],
                    edge=Decimal("0.05") - Decimal(str(spread)),
                    confidence=0.7,
                    liquidity_usd=data.liquidity_usd,
                    timestamp=datetime.now(timezone.utc),
                    risk_factors=["narrowing_spread", "single_market"],
                    data_sources=["polymarket_clob"],
                    validity_days=7,
                )

        except Exception as e:
            logger.error("Error detecting copy trading signal for %s: %s", market_id, e)
            return None

    async def _detect_correlated_arb(
        self, market_data: Dict[str, MarketData]
    ) -> List[TradingOpportunity]:
        """
        Detect correlated market arbitrage opportunities.

        Args:
            market_data: Dictionary of market data

        Returns:
            List of arbitrage opportunities
        """
        try:
            opportunities = []

            # Get correlations
            correlations = self._correlation_matrix

            # Find highly correlated market pairs
            for (market_1, market_2), correlation in correlations.items():
                if correlation.correlation >= self.HIGH_CORRELATION_THRESHOLD:
                    data_1 = market_data.get(market_1)
                    data_2 = market_data.get(market_2)

                    if not data_1 or not data_2:
                        continue

                    # Check for arbitrage: yes prices should sum near 1.0
                    total_cost = data_1.current_yes_price + data_2.current_yes_price

                    if total_cost < Decimal("0.98"):  # Arb opportunity (> 2% edge)
                        edge = (Decimal("1.0") - total_cost) / total_cost
                        liquidity = data_1.liquidity_usd + data_2.liquidity_usd

                        if liquidity >= self.MIN_LIQUIDITY_FOR_ARB:
                            opportunities.append(
                                TradingOpportunity(
                                    opportunity_id=f"arb_{market_1[:8]}_{market_2[:8]}_{int(time.time())}",
                                    opportunity_type=OpportunityType.CORRELATED_MARKET_ARB,
                                    involved_markets=[market_1, market_2],
                                    edge=edge,
                                    confidence=min(0.9, correlation.correlation),
                                    liquidity_usd=liquidity,
                                    timestamp=datetime.now(timezone.utc),
                                    risk_factors=[
                                        f"high_correlation_{correlation.correlation:.2f}",
                                        "bundle_opportunity",
                                        "two_markets",
                                    ],
                                    data_sources=[
                                        "polymarket_clob",
                                        "correlation_matrix",
                                    ],
                                    validity_days=7,
                                )
                            )
                        else:
                            logger.debug(
                                "Arb opportunity filtered out: liquidity %.2f < %.2f",
                                liquidity,
                                float(self.MIN_LIQUIDITY_FOR_ARB),
                            )

            return opportunities

        except Exception as e:
            logger.exception("Error detecting correlated arb: %s", e)
            return []

    def _detect_endgame_opportunities(
        self, market_data: Dict[str, MarketData], event_data: List[EventData]
    ) -> List[TradingOpportunity]:
        """
        Detect endgame sweep opportunities based on event data.

        Args:
            market_data: Dictionary of market data
            event_data: List of event data

        Returns:
            List of endgame opportunities
        """
        try:
            opportunities = []

            for event in event_data:
                # Find markets related to this event
                for market_id in event.related_markets:
                    data = market_data.get(market_id)
                    if not data:
                        continue

                    # Endgame opportunity: market that will resolve with event
                    # High confidence when near event date
                    days_to_event = (event.date - datetime.now(timezone.utc)).days

                    if days_to_event <= 7:  # Within 7 days
                        # Calculate edge based on timing
                        time_edge = Decimal(str(days_to_event / 365))  # Linear decay

                        opportunities.append(
                            TradingOpportunity(
                                opportunity_id=f"endgame_{event.event_id}_{market_id[:8]}_{int(time.time())}",
                                opportunity_type=OpportunityType.ENDGAME_SWEEP,
                                involved_markets=[market_id],
                                edge=time_edge,
                                confidence=0.8 + (0.2 * (7 - days_to_event)),
                                liquidity_usd=data.liquidity_usd,
                                timestamp=datetime.now(timezone.utc),
                                risk_factors=[
                                    "endgame",
                                    f"event_in_{days_to_event}_days",
                                ],
                                data_sources=["event_calendar", "polymarket_clob"],
                                validity_days=days_to_event,
                            )
                        )

            return opportunities

        except Exception as e:
            logger.exception("Error detecting endgame opportunities: %s", e)
            return []

    def _passes_opportunity_filters(
        self, opportunity: TradingOpportunity, market_data: Dict[str, MarketData]
    ) -> bool:
        """
        Check if opportunity passes risk filters.

        Args:
            opportunity: Trading opportunity
            market_data: Dictionary of market data

        Returns:
            True if opportunity passes all filters, False otherwise
        """
        try:
            # Check minimum edge
            if opportunity.opportunity_type != OpportunityType.COPY_TRADING_SIGNAL:
                if opportunity.edge < self.MIN_EDGE_PERCENT:
                    return False

            # Check minimum confidence
            if opportunity.confidence < self.MIN_CONFIDENCE:
                return False

            # Check minimum liquidity
            if opportunity.liquidity_usd < self.MIN_LIQUIDITY_USD:
                return False

            # Check arbitrage-specific liquidity
            if (
                opportunity.opportunity_type == OpportunityType.CORRELATED_MARKET_ARB
                and opportunity.liquidity_usd < self.MIN_LIQUIDITY_FOR_ARB
            ):
                return False

            # Check market data validity
            for market_id in opportunity.involved_markets:
                data = market_data.get(market_id)
                if not data:
                    return False

            # All checks passed
            return True

        except Exception as e:
            logger.error("Error checking opportunity filters: %s", e)
            return False

    def _rank_opportunities(
        self, opportunities: List[TradingOpportunity]
    ) -> List[TradingOpportunity]:
        """
        Rank opportunities by confidence and edge.

        Args:
            opportunities: List of trading opportunities

        Returns:
            Sorted list of opportunities (highest ranked first)
        """
        try:
            # Sort by confidence * edge (prioritize high-confidence, high-edge)
            ranked = sorted(
                opportunities,
                key=lambda x: float(x.confidence) * float(x.edge),
                reverse=True,
            )

            return ranked[:50]  # Top 50 opportunities

        except Exception as e:
            logger.exception("Error ranking opportunities: %s", e)
            return opportunities

    async def update_market_data(
        self, market_updates: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Update market data from external sources.

        Args:
            market_updates: Dictionary of market_id to update data
        """
        try:
            async with self._state_lock:
                updated_count = 0

                for market_id, updates in market_updates.items():
                    current_data = self._market_data_cache.get(f"market_{market_id}")

                    if not current_data:
                        current_data = MarketData(
                            market_id=market_id,
                            category=MarketCategory.POLITICS,  # Default
                            question="Unknown",
                            current_yes_price=Decimal("0.5"),
                            current_no_price=Decimal("0.5"),
                            volume_24h=Decimal("0"),
                            liquidity_usd=Decimal("0"),
                            last_updated=datetime.now(timezone.utc),
                        )

                    # Update fields
                    for field_name, value in updates.items():
                        if field_name == "current_yes_price":
                            current_data.current_yes_price = Decimal(str(value))
                        elif field_name == "current_no_price":
                            current_data.current_no_price = Decimal(str(value))
                        elif field_name == "liquidity_usd":
                            current_data.liquidity_usd = Decimal(str(value))
                        elif field_name == "volume_24h":
                            current_data.volume_24h = Decimal(str(value))

                    current_data.last_updated = datetime.now(timezone.utc)

                    # Update cache
                    self._market_data_cache.set(f"market_{market_id}", current_data)
                    updated_count += 1

                logger.info("Updated %s markets", updated_count)

        except Exception as e:
            logger.exception("Error updating market data: %s", e)

    async def update_event_data(self, event_updates: List[Dict[str, Any]]) -> None:
        """
        Update event data from public sources.

        Args:
            event_updates: List of event updates
        """
        try:
            # In production, this would fetch from event calendar APIs
            # For now, log and return
            logger.info("Would update %s events from public APIs", len(event_updates))

        except Exception as e:
            logger.exception("Error updating event data: %s", e)

    def get_correlation_matrix(self) -> Dict[Tuple[str, str], float]:
        """
        Get current correlation matrix.

        Returns:
            Dictionary of (market_1, market_2) tuples to correlation values
        """
        return {
            key: correlation.correlation
            for key, correlation in self._correlation_matrix.items()
        }

    def get_analytics(self) -> Dict[str, Any]:
        """
        Get market analyzer analytics.

        Returns:
            Dictionary with performance metrics
        """
        try:
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_analyzed": self._total_analyzed,
                "total_opportunities_detected": self._total_opportunities_detected,
                "correlation_matrix_size": len(self._correlation_matrix),
                "active_markets": len(self._market_data_cache.get_stats()),
                "opportunities_detected_last_5min": self._get_recent_opportunities(300),
                "cache_stats": {
                    "market_data": self._market_data_cache.get_stats(),
                    "correlations": self._correlation_cache.get_stats(),
                    "opportunities": self._opportunity_cache.get_stats(),
                },
            }

        except Exception as e:
            logger.exception("Error getting analytics: %s", e)
            return {}

    def _get_recent_opportunities(self, seconds: int) -> int:
        """
        Get number of opportunities detected in recent timeframe.

        Args:
            seconds: Timeframe in seconds

        Returns:
            Number of opportunities detected
        """
        try:
            cutoff_time = time.time() - seconds
            recent_count = sum(
                1
                for opp in self._detected_opportunities
                if opp.timestamp >= datetime.fromtimestamp(cutoff_time, tz=timezone.utc)
            )

            return recent_count

        except Exception as e:
            logger.error("Error getting recent opportunities: %s", e)
            return 0

    async def run_market_analysis(
        self, market_ids: Optional[List[str]] = None
    ) -> List[TradingOpportunity]:
        """
        Run complete market analysis pipeline.

        Args:
            market_ids: Optional list of market IDs to analyze

        Returns:
            List of detected trading opportunities
        """
        try:
            logger.info("Starting market analysis...")

            # Step 1: Fetch market data
            start_time = time.time()
            market_data = await self.fetch_market_data(market_ids)

            # Step 2: Calculate correlations
            await self.calculate_correlations(market_data)

            # Step 3: Detect opportunities
            opportunities = await self.detect_opportunities(market_data)

            elapsed_time = time.time() - start_time

            self._total_analyzed = len(market_data)
            self._last_opportunity_time = time.time()

            logger.info(
                "Market analysis complete in %.2fs: %s markets analyzed, %s opportunities detected",
                elapsed_time,
                len(market_data),
                len(opportunities),
            )

            return opportunities

        except Exception as e:
            logger.exception("Error in market analysis: %s", e)
            return []

    async def shutdown(self) -> None:
        """
        Shutdown market analyzer gracefully.
        """
        try:
            logger.info("Shutting down MarketAnalyzer")

            # Log final analytics
            analytics = self.get_analytics()
            logger.info(
                "Final Analytics:\n"
                "  Total Analyzed: %d\n"
                "  Opportunities Detected: %d\n"
                "  Correlation Matrix Size: %d",
                analytics["total_analyzed"],
                analytics["total_opportunities_detected"],
                analytics["correlation_matrix_size"],
            )

            # Clear caches
            self._market_data_cache.clear()
            self._correlation_cache.clear()
            self._opportunity_cache.clear()

            logger.info("MarketAnalyzer shutdown complete")

        except Exception as e:
            logger.exception("Error during shutdown: %s", e)


# Example usage
async def example_usage():
    """Example of how to use MarketAnalyzer."""
    # Initialize analyzer
    analyzer = MarketAnalyzer(
        polymarket_api_url="https://clob.polymarket.com",
        polygon_rpc_url="https://polygon-rpc.com",
    )

    # Analyze markets
    opportunities = await analyzer.run_market_analysis()

    # Print results
    for i, opp in enumerate(opportunities[:10]):
        print(
            "Opportunity %d:\n"
            "  Type: %s\n"
            "  Edge: %.2f%%\n"
            "  Confidence: %.1f%%\n"
            "  Liquidity: %.2f\n",
            i + 1,
            opp.opportunity_type.value,
            opp.edge * 100,
            opp.confidence * 100,
            opp.liquidity_usd,
        )

    # Get analytics
    analytics = analyzer.get_analytics()
    print("\nAnalytics:\n%s", analytics)

    # Shutdown
    await analyzer.shutdown()


if __name__ == "__main__":
    asyncio.run(example_usage())
