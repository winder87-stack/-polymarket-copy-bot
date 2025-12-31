#!/usr/bin/env python3
"""
Simple Market Maker Dashboard Generator
======================================

Creates a text-based dashboard with ASCII charts and analysis.
"""

import json
from pathlib import Path


def create_simple_dashboard():
    """Create a simple text-based dashboard"""

    # Load results
    results_file = Path("market_maker_detection_results.json")
    with open(results_file, "r") as f:
        data = json.load(f)

    summary = data["summary"]
    detailed_results = data["detailed_results"]

    # Create dashboard directory
    dashboard_dir = Path("market_maker_dashboard")
    dashboard_dir.mkdir(exist_ok=True)

    # Extract data
    classifications = summary["results_summary"]["classification_distribution"]
    wallet_data = []

    for wallet_addr, analysis in detailed_results.items():
        wallet_data.append(
            {
                "address": wallet_addr,
                "classification": analysis["classification"],
                "mm_probability": analysis["market_maker_probability"],
                "confidence": analysis["confidence_score"],
                "trade_count": analysis["trade_count"],
                "trades_per_hour": analysis["metrics"]["temporal_metrics"][
                    "trades_per_hour"
                ],
                "balance_score": analysis["metrics"]["directional_metrics"][
                    "balance_score"
                ],
                "markets_traded": analysis["metrics"]["market_metrics"][
                    "markets_traded_count"
                ],
            }
        )

    # Generate dashboard content
    dashboard_content = generate_dashboard_content(
        summary, classifications, wallet_data
    )

    # Save dashboard
    dashboard_file = dashboard_dir / "market_maker_dashboard.txt"
    with open(dashboard_file, "w") as f:
        f.write(dashboard_content)

    print("✅ Market maker dashboard created successfully!")
    print(f"📁 Dashboard saved to: {dashboard_file}")
    print("\n" + "=" * 80)
    print(dashboard_content)


def generate_dashboard_content(summary, classifications, wallet_data):
    """Generate dashboard content"""

    content = "=" * 80 + "\n"
    content += "🎯 MARKET MAKER DETECTION DASHBOARD\n"
    content += "=" * 80 + "\n\n"

    # Executive Summary
    content += "📊 EXECUTIVE SUMMARY\n"
    content += "-" * 30 + "\n"
    content += f"Total Wallets Analyzed: {summary['total_wallets']}\n"
    content += (
        f"Analysis Timestamp: {summary['analysis_timestamp'][:19].replace('T', ' ')}\n"
    )
    content += f"Market Maker Percentage: {summary['results_summary']['market_maker_percentage']:.1f}%\n"
    content += f"Average Confidence Score: {summary['results_summary']['average_confidence']:.3f}\n"
    content += f"High Confidence Classifications: {summary['results_summary']['high_confidence_classifications']}\n"

    # Classification Distribution
    content += "\n🎯 CLASSIFICATION DISTRIBUTION\n"
    content += "-" * 35 + "\n"

    total = sum(classifications.values())
    sorted_classifications = sorted(
        classifications.items(), key=lambda x: x[1], reverse=True
    )

    for classification, count in sorted_classifications:
        (count / total) * 100
        bar_length = int((count / max(classifications.values())) * 30)
        "█" * bar_length
        content += "25"

    # Top Performers Table
    content += "\n🏆 TOP MARKET MAKER CANDIDATES\n"
    content += "-" * 35 + "\n"

    sorted_wallets = sorted(
        wallet_data, key=lambda x: x["mm_probability"], reverse=True
    )
    top_10 = sorted_wallets[:10]

    content += f"{'Rank':<5} {'Wallet':<15} {'Classification':<18} {'MM Prob':<8} {'Conf':<6} {'Trades/Day':<11} {'Markets':<8}\n"
    content += "-" * 85 + "\n"

    for i, wallet in enumerate(top_10, 1):
        content += f"{i:<5} {wallet['address'][:14]:<15} {wallet['classification'].replace('_', ' ')[:17]:<18} {wallet['mm_probability']:<8.3f} {wallet['confidence']:<6.3f} {wallet['trades_per_hour'] * 24:<11.1f} {wallet['markets_traded']:<8}\n"

    # Market Maker Details
    market_makers = [w for w in wallet_data if w["classification"] == "market_maker"]
    if market_makers:
        content += "\n🎯 IDENTIFIED MARKET MAKERS\n"
        content += "-" * 30 + "\n"

        for mm in market_makers:
            content += f"\n🏆 WALLET: {mm['address'][:16]}...\n"
            content += f"   • Market Maker Probability: {mm['mm_probability']:.3f}\n"
            content += f"   • Confidence Score: {mm['confidence']:.3f}\n"
            content += f"   • Daily Trades: {mm['trades_per_hour'] * 24:.1f}\n"
            content += f"   • Markets Traded: {mm['markets_traded']}\n"
            content += f"   • Balance Score: {mm['balance_score']:.3f}\n"

    # Arbitrage Traders
    arbitrage = [w for w in wallet_data if w["classification"] == "arbitrage_trader"]
    if arbitrage:
        content += "\n⚡ ARBITRAGE TRADERS\n"
        content += "-" * 20 + "\n"

        for arb in arbitrage[:3]:  # Top 3
            content += f"• {arb['address'][:16]}... (MM: {arb['mm_probability']:.3f})\n"

    # Trading Pattern Insights
    content += "\n💡 TRADING PATTERN INSIGHTS\n"
    content += "-" * 30 + "\n"

    high_freq = len([w for w in wallet_data if w["trades_per_hour"] >= 5])
    balanced = len([w for w in wallet_data if w["balance_score"] >= 0.8])
    multi_market = len([w for w in wallet_data if w["markets_traded"] >= 3])

    content += f"• High Frequency Traders (≥5 trades/hour): {high_freq}\n"
    content += f"• Highly Balanced Traders (≥80% balance): {balanced}\n"
    content += f"• Multi-Market Traders (≥3 markets): {multi_market}\n"

    # Recommendations
    content += "\n💡 RECOMMENDATIONS\n"
    content += "-" * 18 + "\n"
    content += "1. 🎯 Prioritize wallets with MM probability > 0.7 for market making opportunities\n"
    content += (
        "2. ⚡ Monitor arbitrage traders (MM probability 0.6-0.7) for spread trading\n"
    )
    content += "3. 📊 Consider mixed traders for balanced portfolio exposure\n"
    content += "4. 📈 Track low activity wallets for pattern development\n"
    content += "5. 🔄 Re-run analysis periodically to identify emerging market makers\n"

    content += "\n" + "=" * 80 + "\n"
    content += "Analysis completed using advanced behavioral pattern recognition\n"
    content += "Generated by Polymarket Copy Bot Market Maker Detection System\n"
    content += "=" * 80 + "\n"

    return content


if __name__ == "__main__":
    create_simple_dashboard()
