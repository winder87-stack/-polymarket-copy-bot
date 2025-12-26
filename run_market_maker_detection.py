#!/usr/bin/env python3
"""
Market Maker Detection Runner
=============================

Runs comprehensive market maker detection analysis on all configured wallets.
Generates behavioral classifications and creates interactive dashboard.

Usage:
    python run_market_maker_detection.py [--mock-data] [--dashboard-only]

Options:
    --mock-data     Generate mock trade data for analysis
    --dashboard-only Generate dashboard from existing data only
"""

import asyncio
import json
import logging
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from core.market_maker_detector import MarketMakerDetector
from monitoring.market_maker_dashboard import MarketMakerDashboard
from utils.helpers import normalize_address

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarketMakerDetectionRunner:
    """
    Runner for comprehensive market maker detection analysis.

    Analyzes all configured wallets and generates classification reports
    and interactive dashboards.
    """

    def __init__(self):
        self.detector = MarketMakerDetector(settings)
        self.wallets = self._load_target_wallets()
        self.analysis_results = {}

        logger.info(f"🎯 Initialized detection runner for {len(self.wallets)} wallets")

    def _load_target_wallets(self) -> List[str]:
        """Load target wallets from configuration"""
        try:
            wallets_file = Path("config/wallets.json")
            if wallets_file.exists():
                with open(wallets_file, 'r') as f:
                    data = json.load(f)
                    return [normalize_address(wallet) for wallet in data.get("target_wallets", [])]
            else:
                logger.warning("Wallets config file not found, using empty list")
                return []
        except Exception as e:
            logger.error(f"Error loading wallets: {e}")
            return []

    def generate_mock_trade_data(self, wallet_address: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Generate realistic mock trade data for analysis demonstration.

        Creates varied trading patterns based on different wallet types:
        - Market Makers: High frequency, balanced buy/sell, multiple markets
        - Directional Traders: Lower frequency, directional bias
        - High Frequency Traders: Very high frequency, some directional bias
        """
        trades = []

        # Determine wallet type based on address hash for consistency
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

        # Generate trades over the analysis period
        start_time = datetime.now() - timedelta(days=days)
        markets = [
            "0x1234567890123456789012345678901234567890",  # BTC market
            "0x2345678901234567890123456789012345678901",  # ETH market
            "0x3456789012345678901234567890123456789012",  # Political market
            "0x4567890123456789012345678901234567890123",  # Sports market
            "0x5678901234567890123456789012345678901234",  # Crypto market
        ]

        # Type-specific parameters
        if wallet_type == "market_maker":
            trades_per_day = random.randint(50, 200)  # High frequency
            balance_ratio = random.uniform(0.45, 0.55)  # Very balanced
            markets_used = random.randint(3, 5)  # Multi-market
            holding_time_hours = random.uniform(0.5, 4)  # Short holding
        elif wallet_type == "directional_trader":
            trades_per_day = random.randint(5, 20)  # Low frequency
            balance_ratio = random.uniform(0.2, 0.4)  # Directional bias
            markets_used = random.randint(1, 2)  # Single market focus
            holding_time_hours = random.uniform(12, 48)  # Longer holding
        elif wallet_type == "high_frequency_trader":
            trades_per_day = random.randint(30, 100)  # Very high frequency
            balance_ratio = random.uniform(0.3, 0.6)  # Some directional bias
            markets_used = random.randint(2, 4)  # Multi-market
            holding_time_hours = random.uniform(0.1, 2)  # Very short holding
        else:  # mixed_trader
            trades_per_day = random.randint(10, 40)  # Moderate frequency
            balance_ratio = random.uniform(0.4, 0.6)  # Somewhat balanced
            markets_used = random.randint(2, 3)  # Moderate markets
            holding_time_hours = random.uniform(2, 12)  # Medium holding

        # Generate trades
        total_trades = trades_per_day * days
        buy_count = int(total_trades * balance_ratio)
        sell_count = total_trades - buy_count

        # Generate timestamps with realistic distribution
        current_time = start_time
        for i in range(total_trades):
            # Add some time jitter
            if i > 0:
                # Market makers trade more evenly, others have bursts
                if wallet_type == "market_maker":
                    interval_minutes = random.expovariate(1 / (24 * 60 / trades_per_day))
                else:
                    interval_minutes = random.expovariate(1 / (24 * 60 / trades_per_day)) * random.uniform(0.5, 3)

                current_time += timedelta(minutes=interval_minutes)

                # Skip if beyond our analysis window
                if current_time > datetime.now():
                    break

            # Determine trade side
            if i < buy_count:
                side = "BUY"
            else:
                side = "SELL"

            # Select market
            market_idx = random.randint(0, min(markets_used, len(markets)) - 1)
            market_id = markets[market_idx]

            # Generate trade amount (varies by wallet type)
            if wallet_type == "market_maker":
                amount = random.uniform(0.1, 2.0)  # Smaller, consistent amounts
            elif wallet_type == "directional_trader":
                amount = random.uniform(0.5, 5.0)  # Larger directional bets
            else:
                amount = random.uniform(0.2, 3.0)  # Medium amounts

            # Create trade record
            trade = {
                "timestamp": current_time.isoformat(),
                "side": side,
                "amount": amount,
                "market_id": market_id,
                "contract_address": market_id,
                "price": random.uniform(0.1, 0.9),  # Mock price
                "fee": amount * 0.001,  # 0.1% fee
                "wallet_address": wallet_address
            }

            trades.append(trade)

        # Sort trades by timestamp
        trades.sort(key=lambda x: x['timestamp'])

        logger.info(f"📊 Generated {len(trades)} trades for {wallet_type} wallet")
        return trades

    async def run_detection_on_wallet(
        self,
        wallet_address: str,
        use_mock_data: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Run market maker detection analysis on a single wallet"""

        try:
            if use_mock_data:
                # Generate mock trade data
                trades = self.generate_mock_trade_data(wallet_address)
            else:
                # In production, this would fetch real trade data
                # For now, we'll use mock data as fallback
                trades = self.generate_mock_trade_data(wallet_address)

            if not trades:
                logger.warning(f"No trade data available for {wallet_address}")
                return None

            # Run analysis
            analysis = await self.detector.analyze_wallet_behavior(
                wallet_address=wallet_address,
                trades=trades
            )

            self.analysis_results[wallet_address] = analysis

            logger.info(
                f"✅ Analyzed {wallet_address[:10]}...: {analysis['classification']} "
                f"(MM: {analysis['market_maker_probability']:.2f})"
            )

            return analysis

        except Exception as e:
            logger.error(f"❌ Error analyzing wallet {wallet_address}: {e}")
            return None

    async def run_detection_on_all_wallets(self, use_mock_data: bool = True) -> Dict[str, Any]:
        """Run detection analysis on all configured wallets"""

        logger.info(f"🚀 Starting market maker detection for {len(self.wallets)} wallets...")

        successful_analyses = 0
        failed_analyses = 0

        for i, wallet_address in enumerate(self.wallets, 1):
            logger.info(f"🔍 Analyzing wallet {i}/{len(self.wallets)}: {wallet_address[:10]}...")

            analysis = await self.run_detection_on_wallet(wallet_address, use_mock_data)

            if analysis:
                successful_analyses += 1
            else:
                failed_analyses += 1

            # Small delay to prevent overwhelming the system
            if i % 5 == 0:
                await asyncio.sleep(0.1)

        # Save classifications
        self.detector.save_data()

        # Generate summary
        summary = {
            "total_wallets": len(self.wallets),
            "successful_analyses": successful_analyses,
            "failed_analyses": failed_analyses,
            "analysis_timestamp": datetime.now().isoformat(),
            "mock_data_used": use_mock_data,
            "results_summary": self._generate_results_summary()
        }

        logger.info(f"🎯 Detection completed: {successful_analyses}/{len(self.wallets)} wallets analyzed successfully")

        return summary

    def _generate_results_summary(self) -> Dict[str, Any]:
        """Generate summary statistics from analysis results"""

        if not self.analysis_results:
            return {}

        classifications = {}
        probabilities = []
        confidences = []

        for analysis in self.analysis_results.values():
            classification = analysis.get('classification', 'unknown')
            classifications[classification] = classifications.get(classification, 0) + 1

            probabilities.append(analysis.get('market_maker_probability', 0))
            confidences.append(analysis.get('confidence_score', 0))

        return {
            "classification_distribution": classifications,
            "average_mm_probability": sum(probabilities) / len(probabilities) if probabilities else 0,
            "average_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "market_maker_percentage": classifications.get('market_maker', 0) / len(self.analysis_results) * 100,
            "high_confidence_classifications": sum(1 for c in confidences if c >= 0.8)
        }

    async def generate_dashboard(self) -> Dict[str, Any]:
        """Generate comprehensive market maker dashboard"""

        logger.info("📊 Generating market maker dashboard...")

        try:
            dashboard = MarketMakerDashboard(self.detector)
            dashboard_data = await dashboard.generate_comprehensive_dashboard()

            logger.info("✅ Dashboard generated successfully")
            return dashboard_data

        except Exception as e:
            logger.error(f"❌ Error generating dashboard: {e}")
            return {"error": str(e)}

    def print_analysis_summary(self, summary: Dict[str, Any]):
        """Print a formatted summary of the analysis results"""

        print("\n" + "="*60)
        print("🎯 MARKET MAKER DETECTION ANALYSIS COMPLETE")
        print("="*60)

        print(f"\n📊 Analysis Summary:")
        print(f"   Total Wallets: {summary['total_wallets']}")
        print(f"   Successful Analyses: {summary['successful_analyses']}")
        print(f"   Failed Analyses: {summary['failed_analyses']}")
        print(f"   Mock Data Used: {summary['mock_data_used']}")

        results = summary.get('results_summary', {})
        if results:
            print(f"\n🎯 Results Summary:")
            print(f"   Average MM Probability: {results.get('average_mm_probability', 0):.3f}")
            print(f"   Average Confidence: {results.get('average_confidence', 0):.3f}")
            print(f"   Market Maker Percentage: {results.get('market_maker_percentage', 0):.1f}%")
            print(f"   High Confidence Classifications: {results.get('high_confidence_classifications', 0)}")

            print(f"\n📈 Classification Distribution:")
            for classification, count in results.get('classification_distribution', {}).items():
                percentage = count / sum(results['classification_distribution'].values()) * 100
                print(f"   {classification.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")

        print(f"\n📁 Dashboard generated at: monitoring/dashboard/market_maker/market_maker_dashboard.html")
        print(f"📄 Results saved to: data/wallet_behavior/classifications.json.gz")

        print("\n" + "="*60)


async def main():
    """Main entry point"""

    import argparse

    parser = argparse.ArgumentParser(description="Run market maker detection on configured wallets")
    parser.add_argument(
        "--mock-data",
        action="store_true",
        default=True,
        help="Generate mock trade data for analysis (default: True)"
    )
    parser.add_argument(
        "--dashboard-only",
        action="store_true",
        help="Generate dashboard from existing data only (skip analysis)"
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Skip dashboard generation"
    )

    args = parser.parse_args()

    try:
        runner = MarketMakerDetectionRunner()

        if not runner.wallets:
            logger.error("❌ No wallets configured for analysis")
            return 1

        if args.dashboard_only:
            # Generate dashboard from existing data only
            logger.info("📊 Generating dashboard from existing data...")
            dashboard_data = await runner.generate_dashboard()
        else:
            # Run full analysis
            summary = await runner.run_detection_on_all_wallets(use_mock_data=args.mock_data)

            # Print summary
            runner.print_analysis_summary(summary)

            # Generate dashboard unless disabled
            if not args.no_dashboard:
                dashboard_data = await runner.generate_dashboard()
            else:
                logger.info("📊 Dashboard generation skipped (--no-dashboard)")

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
    sys.exit(exit_code)
