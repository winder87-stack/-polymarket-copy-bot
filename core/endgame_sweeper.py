"""
Endgame Sweeper - Automated High-Probability Trade Scanner

This module implements an automated trading strategy that scans for markets:
- Resolving within 7 days with probability > 95%
- Calculates annualized returns based on edge and time to resolution
- Implements automatic exit at 99.8% probability to minimize black swan risk
- Filters markets with minimum $10K daily liquidity

Risk Controls:
- Max 3% position size per trade
- Daily loss limit of 15% of portfolio
- Auto-exit if position moves >10% against entry
- Correlation check to avoid overexposure to similar markets

WARNING: This strategy carries black swan risk. Markets can be cancelled or outcomes
can change unexpectedly. Always use proper position sizing and risk management.

Author: Polymarket Bot Team
Version: 1.0.0
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from config import get_settings
from core.circuit_breaker import CircuitBreaker
from core.clob_client import PolymarketClient
from core.exceptions import ValidationError
from utils.financial_calculations import FinancialCalculator
from utils.helpers import BoundedCache
from utils.logger import get_logger
from utils.validation import InputValidator

logger = get_logger(__name__)


class EndgameTrade:
    """Data class for endgame trade opportunities."""

    def __init__(
        self,
        condition_id: str,
        market_question: str,
        probability: Decimal,
        edge: Decimal,
        annualized_return: Decimal,
        days_to_resolution: int,
        liquidity_usdc: Decimal,
        token_id: str,
        entry_price: Decimal,
    ):
        self.condition_id = condition_id
        self.market_question = market_question
        self.probability = probability
        self.edge = edge
        self.annualized_return = annualized_return
        self.days_to_resolution = days_to_resolution
        self.liquidity_usdc = liquidity_usdc
        self.token_id = token_id
        self.entry_price = entry_price
        self.timestamp = time.time()


class EndgamePosition:
    """Data class for active endgame positions."""

    def __init__(
        self,
        condition_id: str,
        token_id: str,
        side: str,
        entry_price: Decimal,
        position_size: Decimal,
        entry_time: float,
    ):
        self.condition_id = condition_id
        self.token_id = token_id
        self.side = side.upper()
        self.entry_price = entry_price
        self.position_size = position_size
        self.entry_time = entry_time
        self.exit_reason: Optional[str] = None


class EndgameSweeper:
    """
    Automated high-probability trade scanner and executor.

    This class implements a sophisticated endgame trading strategy:
    1. Scans markets for high-probability opportunities (>95%)
    2. Calculates annualized returns using edge and time-to-resolution
    3. Filters by liquidity and correlation
    4. Executes trades with proper risk management
    5. Monitors positions for auto-exit conditions

    Risk Management:
    - Circuit breaker integration for daily loss limits
    - Position size limits (max 3% per trade)
    - Automatic exit at 99.8% probability (black swan protection)
    - Stop loss at 10% move against entry
    - Correlation analysis to avoid concentration risk

    Thread Safety:
        Uses asyncio locks for all state modifications to prevent race conditions.
    """

    # Configuration constants
    MIN_PROBABILITY = Decimal("0.95")  # 95% minimum probability
    MAX_PROBABILITY_EXIT = Decimal("0.998")  # 99.8% auto-exit
    MIN_LIQUIDITY_USDC = Decimal("10000.0")  # $10K minimum liquidity
    MAX_DAYS_TO_RESOLUTION = 7  # Maximum days until resolution
    MAX_POSITION_PERCENTAGE = Decimal("0.03")  # 3% max position size
    MAX_DAILY_LOSS_PERCENTAGE = Decimal("0.15")  # 15% daily loss limit
    STOP_LOSS_PERCENTAGE = Decimal("0.10")  # 10% stop loss

    # Blacklist for obvious public information markets
    MARKET_BLACKLIST_PATTERNS = [
        "election",
        "president",
        "vote",
        "congress",
        "senate",
        "referendum",
    ]

    def __init__(
        self,
        clob_client: PolymarketClient,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        """
        Initialize endgame sweeper.

        Args:
            clob_client: Polymarket CLOB API client
            circuit_breaker: Circuit breaker for risk management
        """
        self.settings = get_settings()
        self.clob_client = clob_client
        self.circuit_breaker = circuit_breaker

        # Thread safety
        self._state_lock: asyncio.Lock = asyncio.Lock()
        self._scan_lock: asyncio.Lock = asyncio.Lock()

        # Market cache (bounded to prevent memory leaks)
        self.market_cache: BoundedCache = BoundedCache(
            max_size=500,
            ttl_seconds=300,  # 5 minutes
            memory_threshold_mb=20.0,
            cleanup_interval_seconds=60,
        )

        # Position tracking
        self.open_positions: BoundedCache = BoundedCache(
            max_size=100,
            ttl_seconds=86400,  # 24 hours
            memory_threshold_mb=10.0,
            cleanup_interval_seconds=300,
        )

        # Market correlation tracking (to avoid concentration)
        self.market_keywords: BoundedCache = BoundedCache(
            max_size=1000,
            ttl_seconds=1800,  # 30 minutes
        )

        # Performance tracking
        self.total_scans = 0
        self.opportunities_found = 0
        self.trades_executed = 0
        self.successful_exits = 0
        self.unsuccessful_exits = 0
        self.start_time = time.time()

        # State
        self.running = False
        self.last_scan_time: Optional[float] = None

        logger.info("✅ Endgame Sweeper initialized")
        logger.info(
            f"   Min Probability: {self.MIN_PROBABILITY:.1%}, "
            f"Min Liquidity: ${self.MIN_LIQUIDITY_USDC:,.0f}"
        )
        logger.info(
            f"   Max Position: {self.MAX_POSITION_PERCENTAGE:.1%}, "
            f"Stop Loss: {self.STOP_LOSS_PERCENTAGE:.1%}"
        )

    async def start(self) -> None:
        """Start endgame sweeper background task."""
        if self.running:
            logger.warning("⚠️ Endgame Sweeper already running")
            return

        self.running = True
        logger.info("🚀 Starting Endgame Sweeper")

        # Start background scan task
        asyncio.create_task(self._scan_loop())

    async def stop(self) -> None:
        """Stop endgame sweeper background task."""
        logger.info("🛑 Stopping Endgame Sweeper")
        self.running = False

    async def _scan_loop(self) -> None:
        """Main scan loop - runs continuously."""
        scan_interval = self.settings.monitoring.monitor_interval

        while self.running:
            try:
                # Perform scan
                await self.scan_and_execute()

                # Wait for next scan
                await asyncio.sleep(scan_interval)

            except asyncio.CancelledError:
                logger.info("🛑 Endgame Sweeper scan loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in endgame scan loop: {e}", exc_info=True)
                await asyncio.sleep(10)  # Wait before retrying

    async def scan_and_execute(self) -> Dict[str, Any]:
        """
        Scan for opportunities and execute trades.

        Returns:
            Dictionary with scan results (opportunities, trades, etc.)
        """
        async with self._scan_lock:
            scan_start = time.time()
            self.total_scans += 1

            try:
                logger.info("🔍 Scanning for endgame opportunities...")

                # Get markets and scan for opportunities
                opportunities = await self._find_opportunities()

                # Filter by risk management rules
                filtered_opps = await self._filter_opportunities(opportunities)

                # Check correlations
                safe_opps = await self._check_correlations(filtered_opps)

                # Execute trades
                trades_executed = await self._execute_opportunities(safe_opps)

                # Monitor existing positions
                await self._monitor_positions()

                scan_time = time.time() - scan_start
                self.last_scan_time = time.time()

                results = {
                    "scan_time": scan_time,
                    "total_opportunities": len(opportunities),
                    "filtered_opportunities": len(filtered_opps),
                    "safe_opportunities": len(safe_opps),
                    "trades_executed": trades_executed,
                    "open_positions": len(self.open_positions),
                }

                logger.info(
                    f"✅ Scan complete in {scan_time:.2f}s: "
                    f"{len(opportunities)} opps, {len(safe_opps)} filtered, "
                    f"{trades_executed} trades, {len(self.open_positions)} positions"
                )

                return results

            except Exception as e:
                logger.error(f"❌ Error during endgame scan: {e}", exc_info=True)
                return {
                    "error": str(e),
                    "scan_time": time.time() - scan_start,
                }

    async def _find_opportunities(self) -> List[EndgameTrade]:
        """
        Find high-probability trading opportunities.

        Returns:
            List of EndgameTrade objects
        """
        opportunities = []

        try:
            # Get all markets from CLOB
            markets = await self._get_all_markets()

            if not markets:
                logger.warning("⚠️ No markets available for scanning")
                return []

            # Analyze each market
            for market in markets:
                try:
                    opportunity = await self._analyze_market(market)
                    if opportunity:
                        opportunities.append(opportunity)
                except Exception as e:
                    logger.debug(f"Error analyzing market: {e}")
                    continue

            # Sort by annualized return (highest first)
            opportunities.sort(key=lambda x: x.annualized_return, reverse=True)

            self.opportunities_found += len(opportunities)

            return opportunities

        except Exception as e:
            logger.error(f"❌ Error finding opportunities: {e}", exc_info=True)
            return []

    async def _get_all_markets(self) -> List[Dict[str, Any]]:
        """
        Get all markets from CLOB client.

        Returns:
            List of market dictionaries
        """
        try:
            # Cache markets to reduce API calls
            cache_key = "all_markets"
            cached_markets = self.market_cache.get(cache_key)

            if cached_markets:
                return cached_markets

            # Fetch from API
            markets = await self.clob_client.get_markets()

            if markets:
                # Cache for 5 minutes
                self.market_cache.set(cache_key, markets)

            return markets or []

        except Exception as e:
            logger.error(f"❌ Error fetching markets: {e}")
            return []

    async def _analyze_market(self, market: Dict[str, Any]) -> Optional[EndgameTrade]:
        """
        Analyze a single market for endgame opportunity.

        Args:
            market: Market data dictionary

        Returns:
            EndgameTrade if market qualifies, None otherwise
        """
        try:
            # Extract required fields
            condition_id = market.get("condition_id")
            if not condition_id:
                return None

            # Check blacklist
            question = market.get("question", "").lower()
            if self._is_blacklisted_market(question):
                return None

            # Get probability (price represents probability in YES markets)
            price = market.get("price", market.get("bestAsk", 0))
            probability = Decimal(str(price))

            # Filter by minimum probability
            if probability < self.MIN_PROBABILITY:
                return None

            # Get time to resolution
            end_time = market.get("endTime")
            if not end_time:
                return None

            days_to_resolution = self._calculate_days_to_resolution(end_time)

            # Filter by maximum days
            if days_to_resolution > self.MAX_DAYS_TO_RESOLUTION:
                return None

            # Get liquidity
            liquidity_usdc = Decimal(str(market.get("liquidity", 0)))

            # Filter by minimum liquidity
            if liquidity_usdc < self.MIN_LIQUIDITY_USDC:
                return None

            # Calculate edge and annualized return
            edge = FinancialCalculator.calculate_edge(probability)
            annualized_return = FinancialCalculator.calculate_annualized_return(
                edge, days_to_resolution
            )

            # Filter by minimum annualized return
            if annualized_return < Decimal("20.0"):  # 20% minimum
                return None

            # Get token ID
            token_id = market.get("token_id", "")
            if not token_id:
                return None

            # Validate inputs
            InputValidator.validate_condition_id(condition_id)
            InputValidator.validate_price(float(probability))

            # Create opportunity
            opportunity = EndgameTrade(
                condition_id=condition_id,
                market_question=market.get("question", "Unknown"),
                probability=probability,
                edge=edge,
                annualized_return=annualized_return,
                days_to_resolution=days_to_resolution,
                liquidity_usdc=liquidity_usdc,
                token_id=token_id,
                entry_price=probability,
            )

            logger.debug(
                f"Found opportunity: {condition_id[-8:]} | "
                f"Prob: {probability:.1%} | Edge: {edge:.2f}% | "
                f"Ann. Return: {annualized_return:.1f}% | Days: {days_to_resolution}"
            )

            return opportunity

        except (ValidationError, ValueError, TypeError) as e:
            logger.debug(f"Validation error analyzing market: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error analyzing market: {e}", exc_info=True)
            return None

    def _is_blacklisted_market(self, question: str) -> bool:
        """
        Check if market is blacklisted (obvious public information).

        Args:
            question: Market question text

        Returns:
            True if market is blacklisted, False otherwise
        """
        question_lower = question.lower()
        for pattern in self.MARKET_BLACKLIST_PATTERNS:
            if pattern in question_lower:
                logger.debug(f"Market blacklisted: '{question}' matches '{pattern}'")
                return True
        return False

    def _calculate_days_to_resolution(self, end_time: Any) -> int:
        """
        Calculate days until market resolution.

        Args:
            end_time: End time (ISO string or datetime)

        Returns:
            Days until resolution (integer)
        """
        try:
            # Parse end time
            if isinstance(end_time, str):
                # Try ISO format
                try:
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                except ValueError:
                    # Try epoch timestamp
                    try:
                        timestamp = int(end_time)
                        end_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    except (ValueError, TypeError):
                        return 999  # Invalid, skip
            elif isinstance(end_time, (int, float)):
                end_dt = datetime.fromtimestamp(end_time, tz=timezone.utc)
            else:
                return 999  # Invalid, skip

            # Ensure timezone-aware
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)

            # Calculate days difference
            now = datetime.now(timezone.utc)
            time_delta = end_dt - now
            days = int(time_delta.total_seconds() / 86400)

            return max(0, days)

        except Exception as e:
            logger.warning(f"Error calculating days to resolution: {e}")
            return 999  # Skip if error

    async def _filter_opportunities(
        self, opportunities: List[EndgameTrade]
    ) -> List[EndgameTrade]:
        """
        Filter opportunities by risk management rules.

        Args:
            opportunities: List of endgame trades

        Returns:
            Filtered list of opportunities
        """
        filtered = []

        for opp in opportunities:
            try:
                # Check circuit breaker
                cb_state = self.circuit_breaker.get_state()
                if cb_state["active"]:
                    logger.debug("Circuit breaker active, skipping opportunity")
                    continue

                # Check daily loss limit
                daily_loss = cb_state["daily_loss"]
                max_daily_loss = self.circuit_breaker.max_daily_loss
                if daily_loss >= max_daily_loss:
                    logger.debug("Daily loss limit reached, skipping opportunity")
                    continue

                # Check max concurrent positions
                position_count = self.open_positions.get_stats()["size"]
                if position_count >= self.settings.risk.max_concurrent_positions:
                    logger.debug("Max concurrent positions reached")
                    continue

                # Check if we already have position in this market
                if self.open_positions.get(opp.condition_id):
                    logger.debug(f"Already have position in {opp.condition_id[-8:]}")
                    continue

                filtered.append(opp)

            except Exception as e:
                logger.error(f"Error filtering opportunity: {e}")
                continue

        return filtered

    async def _check_correlations(
        self, opportunities: List[EndgameTrade]
    ) -> List[EndgameTrade]:
        """
        Check for market correlations to avoid overexposure.

        Args:
            opportunities: List of endgame trades

        Returns:
            List of opportunities with no correlation issues
        """
        safe_opps = []

        # Extract keywords from current positions
        position_keywords = set()
        for position_key in self.open_positions._cache.keys():
            keywords = self.market_keywords.get(position_key, [])
            position_keywords.update(keywords)

        for opp in opportunities:
            try:
                # Extract keywords from market question
                keywords = self._extract_keywords(opp.market_question)

                # Check for overlap with existing positions
                if position_keywords & keywords:  # Intersection
                    logger.debug(
                        f"Market {opp.condition_id[-8:]} has correlated keywords"
                    )
                    continue

                safe_opps.append(opp)

            except Exception as e:
                logger.error(f"Error checking correlation: {e}")
                continue

        return safe_opps

    def _extract_keywords(self, text: str) -> Set[str]:
        """
        Extract keywords from market question for correlation checking.

        Args:
            text: Market question text

        Returns:
            Set of keywords
        """
        # Simple keyword extraction
        words = text.lower().split()
        # Remove common words
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "will",
            "be",
            "to",
            "for",
            "in",
            "on",
            "at",
            "by",
        }
        keywords = {
            word.strip(".,!?")
            for word in words
            if len(word) > 3 and word not in stop_words
        }
        return keywords

    async def _execute_opportunities(self, opportunities: List[EndgameTrade]) -> int:
        """
        Execute trading opportunities.

        Args:
            opportunities: List of endgame trades to execute

        Returns:
            Number of trades executed
        """
        if not opportunities:
            return 0

        trades_executed = 0

        # Execute top N opportunities (limit to prevent overtrading)
        max_trades = min(len(opportunities), 3)  # Max 3 trades per scan
        for opp in opportunities[:max_trades]:
            try:
                success = await self._execute_single_opportunity(opp)
                if success:
                    trades_executed += 1
                    self.trades_executed += 1
            except Exception as e:
                logger.error(f"❌ Error executing opportunity: {e}")
                continue

        return trades_executed

    async def _execute_single_opportunity(self, opportunity: EndgameTrade) -> bool:
        """
        Execute a single trading opportunity.

        Args:
            opportunity: EndgameTrade to execute

        Returns:
            True if trade executed successfully, False otherwise
        """
        try:
            # Get account balance
            balance = await self.clob_client.get_balance()
            if not balance:
                logger.error("❌ Could not get account balance")
                return False

            account_balance = Decimal(str(balance.get("usdc", 0)))

            # Calculate position size (max 3% of portfolio)
            position_size = FinancialCalculator.calculate_position_size(
                account_balance=account_balance,
                risk_percentage=self.MAX_POSITION_PERCENTAGE,
                max_position_size=self.settings.risk.max_position_size,
                edge=opportunity.edge,
            )

            # Validate position size
            InputValidator.validate_trade_amount(float(position_size))

            # Create trade
            trade = {
                "condition_id": opportunity.condition_id,
                "token_id": opportunity.token_id,
                "side": "BUY",  # Always BUY for high-probability markets
                "amount": position_size,
                "price": float(opportunity.entry_price),
                "confidence_score": 0.99,  # High confidence
                "is_endgame": True,  # Flag for endgame strategy
            }

            logger.info(
                f"🎯 Executing endgame trade: {opportunity.condition_id[-8:]}\n"
                f"   Question: {opportunity.market_question[:60]}...\n"
                f"   Probability: {opportunity.probability:.1%}\n"
                f"   Edge: {opportunity.edge:.2f}%\n"
                f"   Annualized Return: {opportunity.annualized_return:.1f}%\n"
                f"   Days to Resolution: {opportunity.days_to_resolution}\n"
                f"   Position Size: ${position_size:.2f}"
            )

            # Execute trade
            result = await self.clob_client.place_order(
                condition_id=trade["condition_id"],
                side=trade["side"],
                amount=position_size,
                price=trade["price"],
                token_id=trade["token_id"],
            )

            if not result or "orderID" not in result:
                logger.error(f"❌ Trade execution failed: {result}")
                return False

            # Record position
            position = EndgamePosition(
                condition_id=opportunity.condition_id,
                token_id=opportunity.token_id,
                side=trade["side"],
                entry_price=opportunity.entry_price,
                position_size=position_size,
                entry_time=time.time(),
            )

            position_key = f"{opportunity.condition_id}_{trade['side']}"
            self.open_positions.set(position_key, position)

            # Cache keywords for correlation checking
            keywords = self._extract_keywords(opportunity.market_question)
            self.market_keywords.set(opportunity.condition_id, keywords)

            logger.info(
                f"✅ Endgame trade executed: {result['orderID']} "
                f"({opportunity.condition_id[-8:]})"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Error executing endgame trade: {e}", exc_info=True)
            return False

    async def _monitor_positions(self) -> None:
        """Monitor and manage open positions."""
        positions_to_close = []

        # Get current prices for all positions
        position_keys = list(self.open_positions._cache.keys())

        for position_key in position_keys:
            position = self.open_positions.get(position_key)
            if position is None:
                continue

            try:
                exit_reason = await self._check_exit_conditions(position, position_key)
                if exit_reason:
                    positions_to_close.append((position, exit_reason))
            except Exception as e:
                logger.error(f"Error checking position {position_key}: {e}")
                continue

        # Close positions that meet exit conditions
        for position, reason in positions_to_close:
            await self._close_position(position, reason)

    async def _check_exit_conditions(
        self, position: EndgamePosition, position_key: str
    ) -> Optional[str]:
        """
        Check if position should be closed.

        Args:
            position: EndgamePosition to check
            position_key: Position cache key

        Returns:
            Exit reason if should close, None otherwise
        """
        try:
            # Get current market data
            market = await self.clob_client.get_market(position.condition_id)
            if not market:
                logger.debug(f"Could not get market for {position.condition_id[-8:]}")
                return None

            # Get current probability/price
            current_price = market.get(
                "price", market.get("bestAsk", position.entry_price)
            )
            current_probability = Decimal(str(current_price))

            # Condition 1: Auto-exit at 99.8% probability (black swan protection)
            if current_probability >= self.MAX_PROBABILITY_EXIT:
                logger.info(
                    f"🛑 Auto-exit at {current_probability:.2%} probability "
                    f"(threshold: {self.MAX_PROBABILITY_EXIT:.1%})"
                )
                return "PROBABILITY_EXIT"

            # Condition 2: Stop loss at 10% move against entry
            price_change = (
                current_probability - position.entry_price
            ) / position.entry_price

            if abs(price_change) >= self.STOP_LOSS_PERCENTAGE:
                if price_change < 0:
                    logger.warning(
                        f"🛑 Stop loss triggered: {price_change:.1%} move against entry"
                    )
                    return "STOP_LOSS"
                else:
                    # Take profit if moved in favor
                    logger.info(f"🎉 Take profit: {price_change:.1%} move in favor")
                    return "TAKE_PROFIT"

            # Condition 3: Time-based exit (market resolved)
            end_time = market.get("endTime")
            if end_time:
                days_to_resolution = self._calculate_days_to_resolution(end_time)
                if days_to_resolution == 0:
                    logger.info("⏰ Market resolved, closing position")
                    return "MARKET_RESOLVED"

            return None

        except Exception as e:
            logger.error(f"Error checking exit conditions: {e}")
            return None

    async def _close_position(self, position: EndgamePosition, reason: str) -> None:
        """
        Close an endgame position.

        Args:
            position: EndgamePosition to close
            reason: Reason for closing
        """
        try:
            # Get current price
            market = await self.clob_client.get_market(position.condition_id)
            if not market:
                logger.error("Could not get market to close position")
                return

            current_price = market.get(
                "price", market.get("bestAsk", position.entry_price)
            )

            # Create opposite trade to close position
            close_side = "SELL" if position.side == "BUY" else "BUY"

            logger.info(
                f"Closing endgame position: {position.condition_id[-8:]}\n"
                f"   Side: {close_side}\n"
                f"   Size: ${position.position_size:.2f}\n"
                f"   Entry: {position.entry_price:.4f}\n"
                f"   Current: {current_price:.4f}\n"
                f"   Reason: {reason}"
            )

            result = await self.clob_client.place_order(
                condition_id=position.condition_id,
                side=close_side,
                amount=position.position_size,
                price=float(current_price),
                token_id=position.token_id,
            )

            if result and "orderID" in result:
                # Remove from open positions
                position_key = f"{position.condition_id}_{position.side}"
                self.open_positions.delete(position_key)

                # Track statistics
                if reason in ["TAKE_PROFIT", "PROBABILITY_EXIT", "MARKET_RESOLVED"]:
                    self.successful_exits += 1
                else:
                    self.unsuccessful_exits += 1

                # Calculate P&L
                pnl = FinancialCalculator.calculate_profit_loss(
                    entry_price=position.entry_price,
                    exit_price=Decimal(str(current_price)),
                    position_size=position.position_size,
                    is_long=(position.side == "BUY"),
                )

                logger.info(
                    f"✅ Position closed: {result['orderID']} | "
                    f"P&L: ${pnl[0]:.2f} ({pnl[1]:.2f}%) | "
                    f"Reason: {reason}"
                )

                # Record loss in circuit breaker if applicable
                if pnl[0] < Decimal("0"):
                    await self.circuit_breaker.record_loss(abs(float(pnl[0])))
                elif pnl[0] > Decimal("0"):
                    await self.circuit_breaker.record_profit(float(pnl[0]))

            else:
                logger.error(f"❌ Failed to close position: {result}")

        except Exception as e:
            logger.error(f"❌ Error closing position: {e}", exc_info=True)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get endgame sweeper statistics.

        Returns:
            Dictionary with performance metrics
        """
        runtime = time.time() - self.start_time if self.start_time else 0
        position_count = self.open_positions.get_stats()["size"]

        return {
            "running": self.running,
            "total_scans": self.total_scans,
            "opportunities_found": self.opportunities_found,
            "trades_executed": self.trades_executed,
            "successful_exits": self.successful_exits,
            "unsuccessful_exits": self.unsuccessful_exits,
            "open_positions": position_count,
            "last_scan_time": self.last_scan_time,
            "uptime_seconds": runtime,
            "uptime_hours": runtime / 3600,
        }

    async def health_check(self) -> bool:
        """
        Perform health check on endgame sweeper.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check circuit breaker
            cb_state = self.circuit_breaker.get_state()
            if cb_state["active"]:
                logger.warning(f"⚠️ Circuit breaker active: {cb_state['reason']}")

            # Check cache stats
            cache_stats = self.market_cache.get_stats()
            position_stats = self.open_positions.get_stats()

            logger.info(
                f"✅ Endgame Sweeper health check passed\n"
                f"   Scans: {self.total_scans}\n"
                f"   Positions: {position_stats['size']}\n"
                f"   Cache hit rate: {cache_stats['hit_ratio']:.1%}"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Endgame sweeper health check failed: {e}")
            return False
