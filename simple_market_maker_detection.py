#!/usr/bin/env python3
"""
Simple Market Maker Detection Runner
===================================

Runs market maker detection analysis on configured wallets without complex dependencies.
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleMarketMakerDetector:
    """
    Simplified market maker detection system.
    """

    def __init__(self):
        self.analysis_window_days = 7
        self.min_trades_for_analysis = 10
        self.classification_threshold = 0.7

        # Classification thresholds
        self.thresholds = {
            "high_frequency_threshold": 5.0,
            "balance_ratio_threshold": 0.3,
            "holding_time_threshold": 3600,
            "spread_tightness_threshold": 0.02,
            "multi_market_threshold": 3,
            "consistency_threshold": 0.8,
        }

    def analyze_wallet_behavior(
        self, wallet_address: str, trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze wallet behavior and calculate market maker probability score.
        """

        # Filter trades for analysis window
        analysis_cutoff = datetime.now() - timedelta(days=self.analysis_window_days)
        recent_trades = [
            trade
            for trade in trades
            if datetime.fromisoformat(trade.get("timestamp", datetime.now().isoformat()))
            > analysis_cutoff
        ]

        if len(recent_trades) < self.min_trades_for_analysis:
            return {
                "wallet_address": wallet_address,
                "analysis_timestamp": datetime.now().isoformat(),
                "classification": "insufficient_data",
                "market_maker_probability": 0.0,
                "confidence_score": 0.0,
                "trade_count": len(recent_trades),
                "analysis_window_days": self.analysis_window_days,
                "min_trades_required": self.min_trades_for_analysis,
            }

        # Calculate behavioral metrics
        metrics = self._calculate_behavioral_metrics(recent_trades)

        # Calculate market maker probability
        mm_probability = self._calculate_market_maker_probability(metrics)

        # Determine classification
        classification = self._classify_wallet(mm_probability, metrics)

        # Calculate confidence score
        confidence = self._calculate_confidence_score(metrics, recent_trades)

        return {
            "wallet_address": wallet_address,
            "analysis_timestamp": datetime.now().isoformat(),
            "classification": classification,
            "market_maker_probability": round(mm_probability, 4),
            "confidence_score": round(confidence, 4),
            "trade_count": len(recent_trades),
            "analysis_window_days": self.analysis_window_days,
            "metrics": metrics,
        }

    def _calculate_behavioral_metrics(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate behavioral metrics"""

        metrics = {
            "temporal_metrics": {},
            "directional_metrics": {},
            "position_metrics": {},
            "market_metrics": {},
            "consistency_metrics": {},
        }

        # Sort trades by timestamp
        sorted_trades = sorted(trades, key=lambda x: x.get("timestamp", ""))

        # Temporal Analysis
        metrics["temporal_metrics"] = self._analyze_temporal_patterns(sorted_trades)

        # Directional Analysis
        metrics["directional_metrics"] = self._analyze_directional_patterns(sorted_trades)

        # Position Analysis
        metrics["position_metrics"] = self._analyze_position_patterns(sorted_trades)

        # Market Analysis
        metrics["market_metrics"] = self._analyze_market_patterns(sorted_trades)

        # Consistency Analysis
        metrics["consistency_metrics"] = self._analyze_consistency_patterns(sorted_trades)

        return metrics

    def _analyze_temporal_patterns(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze temporal trading patterns"""

        if not trades:
            return {}

        timestamps = [
            datetime.fromisoformat(trade.get("timestamp", datetime.now().isoformat()))
            for trade in trades
        ]

        # Trading frequency metrics
        total_duration = (timestamps[-1] - timestamps[0]).total_seconds()
        trades_per_hour = len(trades) / max(total_duration / 3600, 1)

        return {
            "trades_per_hour": trades_per_hour,
            "trading_span_hours": total_duration / 3600,
            "trading_hours_uniformity": 0.8,  # Simplified
        }

    def _analyze_directional_patterns(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze buy/sell directional patterns"""

        buy_count = sum(1 for trade in trades if trade.get("side", "").upper() == "BUY")
        sell_count = sum(1 for trade in trades if trade.get("side", "").upper() == "SELL")

        total_trades = len(trades)
        buy_ratio = buy_count / total_trades if total_trades > 0 else 0

        # Balance score (how close buy/sell ratio is to 50/50)
        balance_score = 1 - abs(buy_ratio - 0.5) * 2

        return {
            "buy_count": buy_count,
            "sell_count": sell_count,
            "buy_ratio": buy_ratio,
            "balance_score": balance_score,
        }

    def _analyze_position_patterns(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze position sizing patterns"""

        amounts = [abs(float(trade.get("amount", 0))) for trade in trades if trade.get("amount")]

        # Position size analysis
        if amounts:
            avg_position_size = sum(amounts) / len(amounts)
            position_size_consistency = 1 / (
                1 + (max(amounts) - min(amounts)) / max(avg_position_size, 1)
            )
        else:
            avg_position_size = 0
            position_size_consistency = 0

        # Simplified holding time
        avg_holding_time = 1800  # 30 minutes default

        return {
            "avg_position_size": avg_position_size,
            "position_size_consistency": position_size_consistency,
            "avg_holding_time_seconds": avg_holding_time,
        }

    def _analyze_market_patterns(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze cross-market trading patterns"""

        markets_traded = set()
        for trade in trades:
            market_id = (
                trade.get("market_id")
                or trade.get("condition_id")
                or trade.get("contract_address", "unknown")
            )
            markets_traded.add(market_id)

        num_markets = len(markets_traded)

        return {
            "markets_traded_count": num_markets,
            "market_list": list(markets_traded),
            "market_diversity": min(num_markets / 5, 1.0),  # Scale to 0-1
        }

    def _analyze_consistency_patterns(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trading consistency"""

        # Simplified consistency analysis
        volume_consistency = 0.7  # Default good consistency
        activity_consistency = 0.8  # Default good activity pattern

        return {
            "volume_consistency": volume_consistency,
            "activity_consistency": activity_consistency,
            "trading_frequency": 0.6,  # Days per week
        }

    def _calculate_market_maker_probability(self, metrics: Dict[str, Any]) -> float:
        """Calculate market maker probability score"""

        score = 0.0
        total_weight = 0.0

        # High-frequency trading (weight: 0.25)
        trades_per_hour = metrics.get("temporal_metrics", {}).get("trades_per_hour", 0)
        freq_score = min(trades_per_hour / self.thresholds["high_frequency_threshold"], 1.0)
        score += freq_score * 0.25
        total_weight += 0.25

        # Buy/sell balance (weight: 0.20)
        balance_score = metrics.get("directional_metrics", {}).get("balance_score", 0)
        balance_threshold = 1 - self.thresholds["balance_ratio_threshold"]
        balance_contribution = max(0, (balance_score - balance_threshold) / (1 - balance_threshold))
        score += balance_contribution * 0.20
        total_weight += 0.20

        # Multi-market trading (weight: 0.15)
        markets_count = metrics.get("market_metrics", {}).get("markets_traded_count", 0)
        market_score = min(markets_count / self.thresholds["multi_market_threshold"], 1.0)
        score += market_score * 0.15
        total_weight += 0.15

        # Volume consistency (weight: 0.10)
        volume_consistency = metrics.get("consistency_metrics", {}).get("volume_consistency", 0)
        consistency_threshold = self.thresholds["consistency_threshold"]
        consistency_contribution = max(
            0, (volume_consistency - consistency_threshold) / (1 - consistency_threshold)
        )
        score += consistency_contribution * 0.10
        total_weight += 0.10

        # Normalize score
        final_score = score / total_weight if total_weight > 0 else 0.0

        return min(final_score, 1.0)

    def _classify_wallet(self, mm_probability: float, metrics: Dict[str, Any]) -> str:
        """Classify wallet based on market maker probability"""

        if mm_probability >= self.classification_threshold:
            return "market_maker"

        # Check for other patterns
        trades_per_hour = metrics.get("temporal_metrics", {}).get("trades_per_hour", 0)
        balance_score = metrics.get("directional_metrics", {}).get("balance_score", 0)
        markets_count = metrics.get("market_metrics", {}).get("markets_traded_count", 0)

        # High frequency but unbalanced = potential scalper/arbitrageur
        if trades_per_hour >= self.thresholds["high_frequency_threshold"] * 0.5:
            if balance_score < 0.6:  # Unbalanced
                return "high_frequency_trader"
            elif markets_count >= self.thresholds["multi_market_threshold"]:
                return "arbitrage_trader"

        # Low frequency, directional trading
        if trades_per_hour < 1.0 and balance_score < 0.6:
            return "directional_trader"

        # Moderate activity, somewhat balanced
        if 0.4 <= mm_probability < self.classification_threshold:
            return "mixed_trader"

        # Very low activity or insufficient data
        return "low_activity"

    def _calculate_confidence_score(
        self, metrics: Dict[str, Any], trades: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score for the classification"""

        confidence_factors = []

        # Sample size confidence
        trade_count = len(trades)
        sample_confidence = min(trade_count / 50, 1.0)
        confidence_factors.append(sample_confidence)

        # Time span confidence (simplified)
        time_confidence = 0.8  # Assume good time coverage
        confidence_factors.append(time_confidence)

        # Metric consistency confidence
        consistency = metrics.get("consistency_metrics", {})
        volume_consistency = consistency.get("volume_consistency", 0)
        activity_consistency = consistency.get("activity_consistency", 0)
        consistency_confidence = (volume_consistency + activity_consistency) / 2
        confidence_factors.append(consistency_confidence)

        # Overall confidence
        weights = [0.3, 0.3, 0.4]
        confidence = sum(f * w for f, w in zip(confidence_factors, weights))

        return min(confidence, 1.0)


class MarketMakerDetectionRunner:
    """
    Runner for market maker detection analysis.
    """

    def __init__(self):
        self.detector = SimpleMarketMakerDetector()
        self.wallets = self._load_target_wallets()
        self.analysis_results = {}

        logger.info(f"🎯 Initialized detection runner for {len(self.wallets)} wallets")

    def _load_target_wallets(self) -> List[str]:
        """Load target wallets from configuration"""
        try:
            wallets_file = Path("config/wallets.json")
            if wallets_file.exists():
                with open(wallets_file, "r") as f:
                    data = json.load(f)
                    return data.get("target_wallets", [])
            else:
                logger.warning("Wallets config file not found")
                return []
        except Exception as e:
            logger.error(f"Error loading wallets: {e}")
            return []

    def generate_mock_trade_data(self, wallet_address: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Generate realistic mock trade data for analysis demonstration.
        """

        # Determine wallet type based on address hash
        wallet_hash = hash(wallet_address) % 100
        if wallet_hash < 25:  # 25% market makers
            wallet_type = "market_maker"
        elif wallet_hash < 50:  # 25% directional traders
            wallet_type = "directional_trader"
        elif wallet_hash < 75:  # 25% high frequency traders
            wallet_type = "high_frequency_trader"
        else:  # 25% mixed traders
            wallet_type = "mixed_trader"

        logger.info(f"🎭 Generating {wallet_type} pattern for {wallet_address[:10]}...")

        # Type-specific parameters
        if wallet_type == "market_maker":
            trades_per_day = random.randint(50, 200)
            balance_ratio = random.uniform(0.45, 0.55)
            random.randint(3, 5)
        elif wallet_type == "directional_trader":
            trades_per_day = random.randint(5, 20)
            balance_ratio = random.uniform(0.2, 0.4)
            random.randint(1, 2)
        elif wallet_type == "high_frequency_trader":
            trades_per_day = random.randint(30, 100)
            balance_ratio = random.uniform(0.3, 0.6)
            random.randint(2, 4)
        else:  # mixed_trader
            trades_per_day = random.randint(10, 40)
            balance_ratio = random.uniform(0.4, 0.6)
            random.randint(2, 3)

        # Generate trades
        total_trades = trades_per_day * days
        buy_count = int(total_trades * balance_ratio)
        total_trades - buy_count

        trades = []
        current_time = datetime.now() - timedelta(days=days)

        for i in range(total_trades):
            # Add time jitter
            if i > 0:
                interval_minutes = random.expovariate(1 / (24 * 60 / trades_per_day))
                current_time += timedelta(minutes=interval_minutes)

            # Determine trade side
            side = "BUY" if i < buy_count else "SELL"

            # Select market
            market_id = f"0x{random.randint(1000, 9999):04x}" * 8

            # Generate trade amount
            if wallet_type == "market_maker":
                amount = random.uniform(0.1, 2.0)
            elif wallet_type == "directional_trader":
                amount = random.uniform(0.5, 5.0)
            else:
                amount = random.uniform(0.2, 3.0)

            # Create trade record
            trade = {
                "timestamp": current_time.isoformat(),
                "side": side,
                "amount": amount,
                "market_id": market_id,
                "contract_address": market_id,
                "price": random.uniform(0.1, 0.9),
                "fee": amount * 0.001,
                "wallet_address": wallet_address,
            }

            trades.append(trade)

        # Sort trades by timestamp
        trades.sort(key=lambda x: x["timestamp"])

        logger.info(f"📊 Generated {len(trades)} trades for {wallet_type} wallet")
        return trades

    async def run_detection_on_wallet(self, wallet_address: str) -> Dict[str, Any]:
        """Run market maker detection analysis on a single wallet"""

        try:
            # Generate mock trade data
            trades = self.generate_mock_trade_data(wallet_address)

            if not trades:
                logger.warning(f"No trade data available for {wallet_address}")
                return None

            # Run analysis
            analysis = self.detector.analyze_wallet_behavior(wallet_address, trades)

            self.analysis_results[wallet_address] = analysis

            logger.info(
                f"✅ Analyzed {wallet_address[:10]}...: {analysis['classification']} "
                f"(MM: {analysis['market_maker_probability']:.2f})"
            )

            return analysis

        except Exception as e:
            logger.error(f"❌ Error analyzing wallet {wallet_address}: {e}")
            return None

    async def run_detection_on_all_wallets(self) -> Dict[str, Any]:
        """Run detection analysis on all configured wallets"""

        logger.info(f"🚀 Starting market maker detection for {len(self.wallets)} wallets...")

        successful_analyses = 0
        failed_analyses = 0

        for i, wallet_address in enumerate(self.wallets, 1):
            logger.info(f"🔍 Analyzing wallet {i}/{len(self.wallets)}: {wallet_address[:10]}...")

            analysis = await self.run_detection_on_wallet(wallet_address)

            if analysis:
                successful_analyses += 1
            else:
                failed_analyses += 1

        # Generate summary
        summary = {
            "total_wallets": len(self.wallets),
            "successful_analyses": successful_analyses,
            "failed_analyses": failed_analyses,
            "analysis_timestamp": datetime.now().isoformat(),
            "results_summary": self._generate_results_summary(),
        }

        logger.info(
            f"🎯 Detection completed: {successful_analyses}/{len(self.wallets)} wallets analyzed successfully"
        )

        return summary

    def _generate_results_summary(self) -> Dict[str, Any]:
        """Generate summary statistics from analysis results"""

        if not self.analysis_results:
            return {}

        classifications = {}
        probabilities = []
        confidences = []

        for analysis in self.analysis_results.values():
            classification = analysis.get("classification", "unknown")
            classifications[classification] = classifications.get(classification, 0) + 1

            probabilities.append(analysis.get("market_maker_probability", 0))
            confidences.append(analysis.get("confidence_score", 0))

        return {
            "classification_distribution": classifications,
            "average_mm_probability": (
                sum(probabilities) / len(probabilities) if probabilities else 0
            ),
            "average_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "market_maker_percentage": classifications.get("market_maker", 0)
            / len(self.analysis_results)
            * 100,
            "high_confidence_classifications": sum(1 for c in confidences if c >= 0.8),
        }

    def print_analysis_summary(self, summary: Dict[str, Any]):
        """Print a formatted summary of the analysis results"""

        print("\n" + "=" * 60)
        print("🎯 MARKET MAKER DETECTION ANALYSIS COMPLETE")
        print("=" * 60)

        print("\n📊 Analysis Summary:")
        print(f"   Total Wallets: {summary['total_wallets']}")
        print(f"   Successful Analyses: {summary['successful_analyses']}")
        print(f"   Failed Analyses: {summary['failed_analyses']}")

        results = summary.get("results_summary", {})
        if results:
            print("\n🎯 Results Summary:")
            print(f"   Average MM Probability: {results.get('average_mm_probability', 0):.3f}")
            print(f"   Average Confidence: {results.get('average_confidence', 0):.3f}")
            print(f"   Market Maker Percentage: {results.get('market_maker_percentage', 0):.1f}%")
            print(
                f"   High Confidence Classifications: {results.get('high_confidence_classifications', 0)}"
            )

            print("\n📈 Classification Distribution:")
            for classification, count in results.get("classification_distribution", {}).items():
                percentage = count / sum(results["classification_distribution"].values()) * 100
                print(f"   {classification.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")

        print("\n" + "=" * 60)


async def main():
    """Main entry point"""

    try:
        runner = MarketMakerDetectionRunner()

        if not runner.wallets:
            logger.error("❌ No wallets configured for analysis")
            return 1

        # Run full analysis
        summary = await runner.run_detection_on_all_wallets()

        # Print summary
        runner.print_analysis_summary(summary)

        # Save results to JSON
        results_file = Path("market_maker_detection_results.json")
        with open(results_file, "w") as f:
            json.dump(
                {"summary": summary, "detailed_results": runner.analysis_results},
                f,
                indent=2,
                default=str,
            )

        print(f"\n💾 Results saved to: {results_file}")

        logger.info("✅ Market maker detection process completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.info("🛑 Process interrupted by user")
        return 1
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
