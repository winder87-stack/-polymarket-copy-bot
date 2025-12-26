#!/usr/bin/env python3
"""
Wallet Quality Ranking System
============================

Advanced quality scoring and ranking system for identifying the best performers
within each market maker detection category. Uses multi-dimensional scoring
to evaluate wallets based on their behavioral patterns and trading characteristics.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class WalletQualityRanker:
    """
    Advanced wallet quality ranking system for categorized performance analysis.

    Applies sophisticated scoring algorithms to rank wallets within each behavioral
    category identified by the market maker detection system.
    """

    def __init__(self):
        # Quality scoring weights by category
        self.category_weights = {
            "market_maker": self._get_market_maker_weights(),
            "arbitrage_trader": self._get_arbitrage_trader_weights(),
            "mixed_trader": self._get_mixed_trader_weights(),
            "directional_trader": self._get_directional_trader_weights(),
            "high_frequency_trader": self._get_high_frequency_weights(),
            "low_activity": self._get_low_activity_weights(),
        }

        # Quality metrics definitions
        self.quality_metrics = {
            "trading_activity": {
                "weight": 0.15,
                "description": "Volume and frequency of trading activity",
            },
            "balance_efficiency": {"weight": 0.20, "description": "Buy/sell balance optimization"},
            "market_diversity": {"weight": 0.15, "description": "Cross-market trading diversity"},
            "consistency_score": {"weight": 0.20, "description": "Trading pattern consistency"},
            "behavioral_stability": {"weight": 0.15, "description": "Behavioral pattern stability"},
            "market_maker_potential": {
                "weight": 0.15,
                "description": "Market maker probability score",
            },
        }

        logger.info("🏆 Wallet quality ranking system initialized")

    def _get_market_maker_weights(self) -> Dict[str, float]:
        """Weights optimized for market maker evaluation"""
        return {
            "trading_activity": 0.25,  # High frequency critical
            "balance_efficiency": 0.30,  # Perfect balance essential
            "market_diversity": 0.20,  # Multi-market presence
            "consistency_score": 0.15,  # Pattern consistency
            "behavioral_stability": 0.05,  # Less critical for MMs
            "market_maker_potential": 0.05,  # Already high by definition
        }

    def _get_arbitrage_trader_weights(self) -> Dict[str, float]:
        """Weights optimized for arbitrage trader evaluation"""
        return {
            "trading_activity": 0.20,
            "balance_efficiency": 0.20,  # Some balance needed
            "market_diversity": 0.25,  # Cross-market arbitrage
            "consistency_score": 0.20,
            "behavioral_stability": 0.10,
            "market_maker_potential": 0.05,
        }

    def _get_mixed_trader_weights(self) -> Dict[str, float]:
        """Weights optimized for mixed strategy evaluation"""
        return {
            "trading_activity": 0.20,
            "balance_efficiency": 0.25,  # Balance important
            "market_diversity": 0.15,
            "consistency_score": 0.20,
            "behavioral_stability": 0.15,
            "market_maker_potential": 0.05,
        }

    def _get_directional_trader_weights(self) -> Dict[str, float]:
        """Weights optimized for directional trader evaluation"""
        return {
            "trading_activity": 0.15,
            "balance_efficiency": 0.10,  # Less balance needed
            "market_diversity": 0.20,  # May trade multiple markets
            "consistency_score": 0.25,  # Directional consistency
            "behavioral_stability": 0.20,
            "market_maker_potential": 0.10,
        }

    def _get_high_frequency_weights(self) -> Dict[str, float]:
        """Weights optimized for high frequency trader evaluation"""
        return {
            "trading_activity": 0.30,  # Speed critical
            "balance_efficiency": 0.15,
            "market_diversity": 0.20,
            "consistency_score": 0.20,
            "behavioral_stability": 0.10,
            "market_maker_potential": 0.05,
        }

    def _get_low_activity_weights(self) -> Dict[str, float]:
        """Weights for low activity wallet evaluation"""
        return {
            "trading_activity": 0.05,  # Low weight due to low activity
            "balance_efficiency": 0.20,
            "market_diversity": 0.15,
            "consistency_score": 0.30,  # Consistency more important with less data
            "behavioral_stability": 0.20,
            "market_maker_potential": 0.10,
        }

    def calculate_wallet_quality_score(
        self, wallet_data: Dict[str, Any], category: str
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive quality score for a wallet within its category.

        Args:
            wallet_data: Wallet analysis data from market maker detection
            category: Wallet classification category

        Returns:
            Comprehensive quality scoring analysis
        """

        metrics = wallet_data.get("metrics", {})
        temporal = metrics.get("temporal_metrics", {})
        directional = metrics.get("directional_metrics", {})
        market = metrics.get("market_metrics", {})
        consistency = metrics.get("consistency_metrics", {})

        # Extract raw metrics
        trades_per_hour = temporal.get("trades_per_hour", 0)
        balance_score = directional.get("balance_score", 0)
        markets_traded = market.get("markets_traded_count", 0)
        volume_consistency = consistency.get("volume_consistency", 0)
        activity_consistency = consistency.get("activity_consistency", 0)
        mm_probability = wallet_data.get("market_maker_probability", 0)

        # Calculate individual quality metrics (0-100 scale)
        quality_scores = {}

        # 1. Trading Activity Score
        activity_score = self._calculate_trading_activity_score(trades_per_hour, category)
        quality_scores["trading_activity"] = activity_score

        # 2. Balance Efficiency Score
        balance_efficiency = self._calculate_balance_efficiency_score(balance_score, category)
        quality_scores["balance_efficiency"] = balance_efficiency

        # 3. Market Diversity Score
        diversity_score = self._calculate_market_diversity_score(markets_traded, category)
        quality_scores["market_diversity"] = diversity_score

        # 4. Consistency Score
        consistency_score = self._calculate_consistency_score(
            volume_consistency, activity_consistency
        )
        quality_scores["consistency_score"] = consistency_score

        # 5. Behavioral Stability Score
        stability_score = self._calculate_behavioral_stability_score(metrics, category)
        quality_scores["behavioral_stability"] = stability_score

        # 6. Market Maker Potential Score
        potential_score = mm_probability * 100  # Convert to 0-100 scale
        quality_scores["market_maker_potential"] = potential_score

        # Calculate weighted overall score
        weights = self.category_weights.get(category, self.category_weights["mixed_trader"])
        overall_score = 0.0

        for metric, score in quality_scores.items():
            weight = weights.get(metric, 0.0)
            overall_score += score * weight

        # Calculate confidence score based on data quality
        confidence_score = self._calculate_confidence_score(wallet_data, metrics)

        # Determine quality tier
        quality_tier = self._determine_quality_tier(overall_score, confidence_score)

        return {
            "wallet_address": wallet_data["wallet_address"],
            "category": category,
            "overall_quality_score": round(overall_score, 2),
            "confidence_score": round(confidence_score, 2),
            "quality_tier": quality_tier,
            "individual_scores": {k: round(v, 2) for k, v in quality_scores.items()},
            "weights_used": weights,
            "trade_count": wallet_data.get("trade_count", 0),
            "analysis_timestamp": datetime.now().isoformat(),
        }

    def _calculate_trading_activity_score(self, trades_per_hour: float, category: str) -> float:
        """Calculate trading activity quality score"""

        if category == "market_maker":
            # Market makers need very high activity
            if trades_per_hour >= 10:
                return 100.0
            elif trades_per_hour >= 5:
                return 80.0 + (trades_per_hour - 5) * 4
            elif trades_per_hour >= 1:
                return 40.0 + (trades_per_hour - 1) * 20
            else:
                return max(0, trades_per_hour * 40)

        elif category in ["arbitrage_trader", "high_frequency_trader"]:
            # High frequency traders need substantial activity
            if trades_per_hour >= 5:
                return 100.0
            elif trades_per_hour >= 2:
                return 60.0 + (trades_per_hour - 2) * 20
            elif trades_per_hour >= 0.5:
                return 20.0 + (trades_per_hour - 0.5) * 80
            else:
                return max(0, trades_per_hour * 40)

        elif category == "mixed_trader":
            # Moderate activity expected
            if trades_per_hour >= 2:
                return 100.0
            elif trades_per_hour >= 1:
                return 75.0 + (trades_per_hour - 1) * 50
            elif trades_per_hour >= 0.2:
                return 25.0 + (trades_per_hour - 0.2) * 125
            else:
                return max(0, trades_per_hour * 125)

        else:  # directional_trader, low_activity
            # Lower activity acceptable
            if trades_per_hour >= 1:
                return 100.0
            elif trades_per_hour >= 0.5:
                return 70.0 + (trades_per_hour - 0.5) * 60
            elif trades_per_hour >= 0.1:
                return 20.0 + (trades_per_hour - 0.1) * 250
            else:
                return max(0, trades_per_hour * 200)

    def _calculate_balance_efficiency_score(self, balance_score: float, category: str) -> float:
        """Calculate balance efficiency quality score"""

        if category == "market_maker":
            # Market makers need near-perfect balance
            if balance_score >= 0.95:
                return 100.0
            elif balance_score >= 0.90:
                return 80.0 + (balance_score - 0.90) * 200
            elif balance_score >= 0.80:
                return 60.0 + (balance_score - 0.80) * 100
            elif balance_score >= 0.70:
                return 40.0 + (balance_score - 0.70) * 200
            else:
                return max(0, balance_score * 57.14)  # 40/0.7

        elif category in ["arbitrage_trader", "mixed_trader"]:
            # Some balance preferred but not critical
            if balance_score >= 0.80:
                return 100.0
            elif balance_score >= 0.70:
                return 75.0 + (balance_score - 0.70) * 250
            elif balance_score >= 0.60:
                return 50.0 + (balance_score - 0.60) * 250
            elif balance_score >= 0.50:
                return 25.0 + (balance_score - 0.50) * 500
            else:
                return max(0, balance_score * 50)

        else:  # directional_trader, high_frequency_trader, low_activity
            # Balance less important for directional strategies
            return balance_score * 100  # Direct mapping

    def _calculate_market_diversity_score(self, markets_traded: int, category: str) -> float:
        """Calculate market diversity quality score"""

        if category == "market_maker":
            # Market makers should trade many markets
            if markets_traded >= 10:
                return 100.0
            elif markets_traded >= 5:
                return 70.0 + (markets_traded - 5) * 6
            elif markets_traded >= 3:
                return 50.0 + (markets_traded - 3) * 10
            elif markets_traded >= 1:
                return 20.0 + (markets_traded - 1) * 15
            else:
                return 20.0

        elif category in ["arbitrage_trader", "high_frequency_trader"]:
            # Cross-market activity important for arbitrage
            if markets_traded >= 5:
                return 100.0
            elif markets_traded >= 3:
                return 70.0 + (markets_traded - 3) * 15
            elif markets_traded >= 2:
                return 55.0 + (markets_traded - 2) * 15
            elif markets_traded >= 1:
                return 25.0
            else:
                return 10.0

        elif category == "mixed_trader":
            # Moderate diversity expected
            if markets_traded >= 3:
                return 100.0
            elif markets_traded >= 2:
                return 75.0 + (markets_traded - 2) * 25
            elif markets_traded >= 1:
                return 50.0
            else:
                return 25.0

        else:  # directional_trader, low_activity
            # Diversity less critical for focused strategies
            if markets_traded >= 2:
                return 100.0
            elif markets_traded >= 1:
                return 60.0
            else:
                return 30.0

    def _calculate_consistency_score(
        self, volume_consistency: float, activity_consistency: float
    ) -> float:
        """Calculate overall consistency quality score"""
        # Combine volume and activity consistency
        combined_consistency = (volume_consistency + activity_consistency) / 2

        # Scale to 0-100 and add some premium for high consistency
        if combined_consistency >= 0.9:
            return 100.0
        elif combined_consistency >= 0.8:
            return 85.0 + (combined_consistency - 0.8) * 150
        elif combined_consistency >= 0.7:
            return 70.0 + (combined_consistency - 0.7) * 150
        elif combined_consistency >= 0.6:
            return 50.0 + (combined_consistency - 0.6) * 200
        elif combined_consistency >= 0.5:
            return 30.0 + (combined_consistency - 0.5) * 200
        else:
            return combined_consistency * 60

    def _calculate_behavioral_stability_score(
        self, metrics: Dict[str, Any], category: str
    ) -> float:
        """Calculate behavioral stability quality score"""

        temporal = metrics.get("temporal_metrics", {})
        directional = metrics.get("directional_metrics", {})

        # Factors indicating stability
        uniformity_score = temporal.get("trading_hours_uniformity", 0.8)
        balance_score = directional.get("balance_score", 0.5)
        avg_streak = directional.get("avg_direction_streak", 1.0)

        # Normalize streak (lower streak = more stability for balanced traders)
        if category == "market_maker":
            streak_penalty = min(avg_streak / 2, 1.0)  # Penalize long directional streaks
        else:
            streak_penalty = min(avg_streak / 5, 1.0)  # Less penalty for directional traders

        # Combine factors
        stability_factors = [uniformity_score, balance_score, 1 - streak_penalty]
        avg_stability = np.mean(stability_factors)

        return avg_stability * 100

    def _calculate_confidence_score(
        self, wallet_data: Dict[str, Any], metrics: Dict[str, Any]
    ) -> float:
        """Calculate confidence score based on data quality and sample size"""

        trade_count = wallet_data.get("trade_count", 0)
        confidence = wallet_data.get("confidence_score", 0.5)

        # Sample size confidence
        if trade_count >= 1000:
            sample_confidence = 1.0
        elif trade_count >= 500:
            sample_confidence = 0.9
        elif trade_count >= 200:
            sample_confidence = 0.8
        elif trade_count >= 100:
            sample_confidence = 0.7
        elif trade_count >= 50:
            sample_confidence = 0.6
        elif trade_count >= 20:
            sample_confidence = 0.5
        elif trade_count >= 10:
            sample_confidence = 0.4
        else:
            sample_confidence = 0.3

        # Metric completeness confidence
        metrics_complete = 0
        if metrics.get("temporal_metrics"):
            metrics_complete += 0.2
        if metrics.get("directional_metrics"):
            metrics_complete += 0.2
        if metrics.get("position_metrics"):
            metrics_complete += 0.2
        if metrics.get("market_metrics"):
            metrics_complete += 0.2
        if metrics.get("consistency_metrics"):
            metrics_complete += 0.2

        # Combine confidences
        overall_confidence = sample_confidence * 0.6 + confidence * 0.3 + metrics_complete * 0.1

        return overall_confidence * 100

    def _determine_quality_tier(self, overall_score: float, confidence_score: float) -> str:
        """Determine quality tier based on score and confidence"""

        combined_score = overall_score * 0.7 + confidence_score * 0.3

        if combined_score >= 85:
            return "Elite"
        elif combined_score >= 75:
            return "Premium"
        elif combined_score >= 65:
            return "High"
        elif combined_score >= 55:
            return "Medium"
        elif combined_score >= 45:
            return "Low"
        else:
            return "Poor"

    def rank_wallets_by_category(self, market_maker_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rank all wallets by quality within each category.

        Args:
            market_maker_results: Results from market maker detection analysis

        Returns:
            Comprehensive ranking analysis by category
        """

        logger.info("🏆 Starting wallet quality ranking analysis...")

        # Extract wallet data
        detailed_results = market_maker_results.get("detailed_results", {})

        # Group wallets by category
        category_wallets = defaultdict(list)

        for wallet_addr, analysis in detailed_results.items():
            category = analysis.get("classification", "unknown")
            category_wallets[category].append(analysis)

        # Rank wallets within each category
        category_rankings = {}

        for category, wallets in category_wallets.items():
            logger.info(f"📊 Ranking {len(wallets)} wallets in {category} category")

            ranked_wallets = []

            for wallet in wallets:
                quality_analysis = self.calculate_wallet_quality_score(wallet, category)
                ranked_wallets.append(quality_analysis)

            # Sort by overall quality score (descending)
            ranked_wallets.sort(key=lambda x: x["overall_quality_score"], reverse=True)

            # Add ranking positions
            for i, wallet in enumerate(ranked_wallets, 1):
                wallet["category_rank"] = i
                wallet["category_total"] = len(ranked_wallets)

            category_rankings[category] = {
                "wallet_count": len(wallets),
                "ranked_wallets": ranked_wallets,
                "top_performer": ranked_wallets[0] if ranked_wallets else None,
                "average_score": (
                    np.mean([w["overall_quality_score"] for w in ranked_wallets])
                    if ranked_wallets
                    else 0
                ),
                "quality_distribution": self._analyze_quality_distribution(ranked_wallets),
            }

        # Generate summary statistics
        summary = self._generate_ranking_summary(category_rankings, market_maker_results)

        return {
            "ranking_timestamp": datetime.now().isoformat(),
            "category_rankings": category_rankings,
            "summary_statistics": summary,
            "total_wallets_ranked": sum(
                len(cat["ranked_wallets"]) for cat in category_rankings.values()
            ),
        }

    def _analyze_quality_distribution(self, ranked_wallets: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze quality tier distribution within a category"""

        distribution = defaultdict(int)

        for wallet in ranked_wallets:
            tier = wallet.get("quality_tier", "Unknown")
            distribution[tier] += 1

        return dict(distribution)

    def _generate_ranking_summary(
        self, category_rankings: Dict[str, Any], mm_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive ranking summary"""

        summary = {
            "total_categories": len(category_rankings),
            "elite_performers": [],
            "category_leaders": {},
            "quality_tier_distribution": defaultdict(int),
            "average_scores_by_category": {},
            "recommendations": [],
        }

        # Collect elite performers (top 3 overall)
        all_elite = []
        for category_data in category_rankings.values():
            for wallet in category_data["ranked_wallets"][:3]:  # Top 3 from each category
                if wallet["quality_tier"] in ["Elite", "Premium"]:
                    all_elite.append(wallet)

        # Sort elite performers by overall score
        all_elite.sort(key=lambda x: x["overall_quality_score"], reverse=True)
        summary["elite_performers"] = all_elite[:5]  # Top 5 overall

        # Category leaders
        for category, data in category_rankings.items():
            if data["ranked_wallets"]:
                leader = data["ranked_wallets"][0]
                summary["category_leaders"][category] = leader

        # Quality tier distribution across all wallets
        for category_data in category_rankings.values():
            for tier, count in category_data.get("quality_distribution", {}).items():
                summary["quality_tier_distribution"][tier] += count

        # Average scores by category
        for category, data in category_rankings.items():
            summary["average_scores_by_category"][category] = round(data["average_score"], 2)

        # Generate recommendations
        summary["recommendations"] = self._generate_investment_recommendations(
            summary, category_rankings
        )

        return summary

    def _generate_investment_recommendations(
        self, summary: Dict[str, Any], category_rankings: Dict[str, Any]
    ) -> List[str]:
        """Generate investment recommendations based on ranking analysis"""

        recommendations = []

        # Elite performer recommendations
        elite_count = len([p for p in summary["elite_performers"] if p["quality_tier"] == "Elite"])
        if elite_count > 0:
            recommendations.append(
                f"🎯 PRIORITY: {elite_count} Elite-quality wallets identified for immediate copy trading"
            )

        # Category-specific recommendations
        for category, leader in summary["category_leaders"].items():
            if leader and leader["overall_quality_score"] >= 75:
                category_name = category.replace("_", " ").title()
                recommendations.append(
                    f"🏆 Top {category_name}: {leader['wallet_address'][:12]}... (Score: {leader['overall_quality_score']:.1f})"
                )

        # Risk diversification recommendations
        category_count = len(
            [c for c in category_rankings.keys() if category_rankings[c]["wallet_count"] >= 3]
        )
        if category_count >= 3:
            recommendations.append(
                f"📊 DIVERSIFICATION: Strong performers available across {category_count} categories for balanced portfolio"
            )

        # Low quality warnings
        poor_performers = summary["quality_tier_distribution"].get("Poor", 0) + summary[
            "quality_tier_distribution"
        ].get("Low", 0)
        if poor_performers > 0:
            recommendations.append(
                f"⚠️ CAUTION: {poor_performers} low-quality wallets identified - avoid for primary trading"
            )

        return recommendations


def generate_wallet_quality_report(ranking_results: Dict[str, Any]) -> str:
    """Generate comprehensive quality ranking report"""

    content = "=" * 80 + "\n"
    content += "🏆 WALLET QUALITY RANKING REPORT\n"
    content += "=" * 80 + "\n\n"

    content += "📊 EXECUTIVE SUMMARY\n"
    content += "-" * 30 + "\n"
    content += (
        f"Analysis Timestamp: {ranking_results['ranking_timestamp'][:19].replace('T', ' ')}\n"
    )
    content += f"Total Wallets Ranked: {ranking_results['total_wallets_ranked']}\n"
    content += f"Categories Analyzed: {len(ranking_results['category_rankings'])}\n\n"

    # Elite Performers
    elite = ranking_results["summary_statistics"]["elite_performers"]
    if elite:
        content += "👑 ELITE PERFORMERS (Top 5 Overall)\n"
        content += "-" * 35 + "\n"

        for i, wallet in enumerate(elite, 1):
            content += f"{i}. {wallet['wallet_address'][:16]}...\n"
            content += f"   Category: {wallet['category'].replace('_', ' ').title()}\n"
            content += f"   Quality Score: {wallet['overall_quality_score']:.1f}/100\n"
            content += f"   Quality Tier: {wallet['quality_tier']}\n"
            content += f"   Confidence: {wallet['confidence_score']:.1f}%\n\n"

    # Category Leaders
    content += "🏆 CATEGORY LEADERS\n"
    content += "-" * 20 + "\n"

    leaders = ranking_results["summary_statistics"]["category_leaders"]
    for category, leader in leaders.items():
        if leader:
            content += f"{category.replace('_', ' ').title()}: {leader['wallet_address'][:16]}... "
            content += f"(Score: {leader['overall_quality_score']:.1f})\n"

    content += "\n"

    # Category Details
    content += "📈 CATEGORY ANALYSIS\n"
    content += "-" * 25 + "\n"

    for category, data in ranking_results["category_rankings"].items():
        content += f"\n{category.replace('_', ' ').upper()}\n"
        content += f"Wallets: {data['wallet_count']} | Avg Score: {data['average_score']:.1f}\n"

        # Quality distribution
        distribution = data.get("quality_distribution", {})
        if distribution:
            dist_str = ", ".join([f"{tier}: {count}" for tier, count in distribution.items()])
            content += f"Quality Distribution: {dist_str}\n"

        # Top 3 performers
        top_3 = data["ranked_wallets"][:3]
        for i, wallet in enumerate(top_3, 1):
            content += f"  {i}. {wallet['wallet_address'][:12]}... (Score: {wallet['overall_quality_score']:.1f})\n"

    # Recommendations
    recommendations = ranking_results["summary_statistics"]["recommendations"]
    if recommendations:
        content += "\n💡 INVESTMENT RECOMMENDATIONS\n"
        content += "-" * 35 + "\n"

        for rec in recommendations:
            content += f"• {rec}\n"

    content += "\n" + "=" * 80 + "\n"
    content += "Report generated by Wallet Quality Ranking System\n"
    content += "=" * 80 + "\n"

    return content


def main():
    """Main execution function"""

    logger.info("🚀 Starting wallet quality ranking analysis...")

    # Load market maker detection results
    results_file = Path("market_maker_detection_results.json")

    if not results_file.exists():
        logger.error(
            "❌ Market maker detection results not found. Run market maker detection first."
        )
        return 1

    with open(results_file, "r") as f:
        mm_results = json.load(f)

    # Initialize ranker and perform analysis
    ranker = WalletQualityRanker()
    ranking_results = ranker.rank_wallets_by_category(mm_results)

    # Generate report
    report_content = generate_wallet_quality_report(ranking_results)

    # Save results
    output_dir = Path("wallet_quality_analysis")
    output_dir.mkdir(exist_ok=True)

    # Save detailed results
    with open(output_dir / "quality_ranking_results.json", "w") as f:
        json.dump(ranking_results, f, indent=2, default=str)

    # Save report
    with open(output_dir / "quality_ranking_report.txt", "w") as f:
        f.write(report_content)

    # Print summary to console
    print("\n" + "=" * 80)
    print("🏆 WALLET QUALITY RANKING ANALYSIS COMPLETE")
    print("=" * 80)

    print("\n📊 Analysis Summary:")
    print(f"   Total Wallets Ranked: {ranking_results['total_wallets_ranked']}")
    print(f"   Categories Analyzed: {len(ranking_results['category_rankings'])}")

    elite_count = len(ranking_results["summary_statistics"]["elite_performers"])
    print(f"   Elite Performers Identified: {elite_count}")

    # Show top performers
    print("\n🏆 Top Performers by Category:")
    for category, leader in ranking_results["summary_statistics"]["category_leaders"].items():
        if leader:
            print(
                f"   {category.replace('_', ' ').title()}: {leader['wallet_address'][:12]}... ({leader['overall_quality_score']:.1f})"
            )

    print(f"\n📁 Detailed results saved to: {output_dir}/")
    print(f"📄 Report saved to: {output_dir}/quality_ranking_report.txt")

    print("\n" + "=" * 80)

    logger.info("✅ Wallet quality ranking analysis completed successfully")
    return 0


if __name__ == "__main__":
    exit(main())
