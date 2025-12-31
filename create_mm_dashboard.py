#!/usr/bin/env python3
"""
Market Maker Detection Dashboard Generator
========================================

Creates visual charts and analysis dashboard from market maker detection results.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt


def create_market_maker_dashboard():
    """Create visual dashboard from market maker detection results"""

    # Load results
    results_file = Path("market_maker_detection_results.json")
    with open(results_file, "r") as f:
        data = json.load(f)

    summary = data["summary"]
    detailed_results = data["detailed_results"]

    # Create dashboard directory
    dashboard_dir = Path("market_maker_dashboard")
    dashboard_dir.mkdir(exist_ok=True)

    # Extract data for plotting
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

    # Create charts
    create_classification_pie_chart(classifications, dashboard_dir)
    create_probability_distribution_chart(wallet_data, dashboard_dir)
    create_trading_patterns_scatter(wallet_data, dashboard_dir)
    create_top_performers_table(wallet_data, dashboard_dir)
    create_summary_report(summary, wallet_data, dashboard_dir)

    print("✅ Market maker dashboard created successfully!")
    print(f"📁 Dashboard saved to: {dashboard_dir}/")


def create_classification_pie_chart(classifications, output_dir):
    """Create pie chart of wallet classifications"""

    labels = []
    sizes = []
    colors = {
        "market_maker": "#e74c3c",
        "directional_trader": "#27ae60",
        "high_frequency_trader": "#f39c12",
        "arbitrage_trader": "#9b59b6",
        "mixed_trader": "#3498db",
        "low_activity": "#95a5a6",
    }

    for classification, count in classifications.items():
        labels.append(f"{classification.replace('_', ' ').title()}\n({count})")
        sizes.append(count)

    fig, ax = plt.subplots(figsize=(10, 8))
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        colors=[
            colors.get(cls.split("\n")[0].lower().replace(" ", "_"), "#95a5a6")
            for cls in classifications.keys()
        ],
    )

    ax.set_title("Wallet Classification Distribution", fontsize=16, fontweight="bold")
    plt.setp(autotexts, size=10, weight="bold")
    plt.setp(texts, size=10)

    plt.tight_layout()
    plt.savefig(
        output_dir / "classification_distribution.png", dpi=300, bbox_inches="tight"
    )
    plt.close()


def create_probability_distribution_chart(wallet_data, output_dir):
    """Create histogram of market maker probabilities"""

    probabilities = [w["mm_probability"] for w in wallet_data]

    fig, ax = plt.subplots(figsize=(12, 6))

    n, bins, patches = ax.hist(
        probabilities, bins=20, alpha=0.7, color="#3498db", edgecolor="black"
    )

    # Color bars based on probability ranges
    for i, patch in enumerate(patches):
        if bins[i] >= 0.7:  # Market maker threshold
            patch.set_facecolor("#e74c3c")  # Red for market makers
        elif bins[i] >= 0.4:  # Mixed trader range
            patch.set_facecolor("#f39c12")  # Orange for mixed
        else:
            patch.set_facecolor("#95a5a6")  # Gray for others

    ax.axvline(
        x=0.7,
        color="red",
        linestyle="--",
        linewidth=2,
        label="Market Maker Threshold (0.7)",
    )
    ax.axvline(
        x=0.4,
        color="orange",
        linestyle=":",
        linewidth=2,
        label="Mixed Trader Threshold (0.4)",
    )

    ax.set_title(
        "Market Maker Probability Distribution", fontsize=16, fontweight="bold"
    )
    ax.set_xlabel("Market Maker Probability", fontsize=12)
    ax.set_ylabel("Number of Wallets", fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(
        output_dir / "probability_distribution.png", dpi=300, bbox_inches="tight"
    )
    plt.close()


def create_trading_patterns_scatter(wallet_data, output_dir):
    """Create scatter plot of trading patterns"""

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Trading frequency vs balance score
    freq = [w["trades_per_hour"] for w in wallet_data]
    balance = [w["balance_score"] for w in wallet_data]
    classifications = [w["classification"] for w in wallet_data]

    colors = {
        "market_maker": "#e74c3c",
        "directional_trader": "#27ae60",
        "high_frequency_trader": "#f39c12",
        "arbitrage_trader": "#9b59b6",
        "mixed_trader": "#3498db",
        "low_activity": "#95a5a6",
    }

    for i, (f, b, cls) in enumerate(zip(freq, balance, classifications)):
        ax1.scatter(
            f,
            b,
            color=colors.get(cls, "#95a5a6"),
            alpha=0.7,
            s=60,
            label=cls.replace("_", " ").title()
            if i == classifications.index(cls)
            else "",
        )

    ax1.set_title("Trading Frequency vs Balance Score", fontsize=14, fontweight="bold")
    ax1.set_xlabel("Trades per Hour", fontsize=12)
    ax1.set_ylabel("Buy/Sell Balance Score", fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

    # Markets traded vs trade count
    markets = [w["markets_traded"] for w in wallet_data]
    trades = [w["trade_count"] for w in wallet_data]

    for i, (m, t, cls) in enumerate(zip(markets, trades, classifications)):
        ax2.scatter(m, t, color=colors.get(cls, "#95a5a6"), alpha=0.7, s=60)

    ax2.set_title("Markets Traded vs Trade Count", fontsize=14, fontweight="bold")
    ax2.set_xlabel("Number of Markets Traded", fontsize=12)
    ax2.set_ylabel("Total Trade Count", fontsize=12)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "trading_patterns.png", dpi=300, bbox_inches="tight")
    plt.close()


def create_top_performers_table(wallet_data, output_dir):
    """Create table of top performing wallets"""

    # Sort by market maker probability
    sorted_wallets = sorted(
        wallet_data, key=lambda x: x["mm_probability"], reverse=True
    )
    top_10 = sorted_wallets[:10]

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.axis("tight")
    ax.axis("off")

    # Prepare table data
    headers = [
        "Rank",
        "Wallet Address",
        "Classification",
        "MM Probability",
        "Confidence",
        "Trades/Day",
        "Markets",
    ]
    table_data = []

    for i, wallet in enumerate(top_10, 1):
        table_data.append(
            [
                str(i),
                wallet["address"][:12] + "...",
                wallet["classification"].replace("_", " ").title(),
                f"{wallet['mm_probability']:.3f}",
                f"{wallet['confidence']:.3f}",
                f"{wallet['trades_per_hour'] * 24:.1f}",
                str(wallet["markets_traded"]),
            ]
        )

    table = ax.table(
        cellText=table_data,
        colLabels=headers,
        loc="center",
        cellLoc="center",
        colColours=["#f8f9fa"] * len(headers),
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.5)

    # Color cells based on classification
    colors = {
        "market_maker": "#ffe6e6",
        "directional_trader": "#e6ffe6",
        "high_frequency_trader": "#fff3cd",
        "arbitrage_trader": "#f3e5f5",
        "mixed_trader": "#e3f2fd",
        "low_activity": "#f8f9fa",
    }

    for i, wallet in enumerate(top_10):
        row_idx = i + 1
        classification = wallet["classification"]
        color = colors.get(classification, "#f8f9fa")

        for col_idx in range(len(headers)):
            table[row_idx, col_idx].set_facecolor(color)

    ax.set_title(
        "Top 10 Wallets by Market Maker Probability",
        fontsize=16,
        fontweight="bold",
        pad=20,
    )

    plt.tight_layout()
    plt.savefig(output_dir / "top_performers.png", dpi=300, bbox_inches="tight")
    plt.close()


def create_summary_report(summary, wallet_data, output_dir):
    """Create summary report"""

    report_content = f"""
# 🎯 Market Maker Detection Analysis Report

**Generated:** {summary["analysis_timestamp"][:19].replace("T", " ")}

## 📊 Executive Summary

- **Total Wallets Analyzed:** {summary["total_wallets"]}
- **Analysis Window:** 7 days
- **Market Maker Identification Rate:** {summary["results_summary"]["market_maker_percentage"]:.1f}%

## 🎯 Classification Results

| Classification | Count | Percentage |
|----------------|-------|------------|
"""

    classifications = summary["results_summary"]["classification_distribution"]
    total = sum(classifications.values())

    for cls, count in classifications.items():
        percentage = (count / total) * 100
        report_content += (
            f"| {cls.replace('_', ' ').title()} | {count} | {percentage:.1f}% |\n"
        )

    report_content += f"- **Average Confidence:** {summary['results_summary']['average_confidence']:.3f}\n"
    report_content += f"- **High Confidence Classifications:** {summary['results_summary']['high_confidence_classifications']}\n"
    report_content += "\n"
    report_content += "## 🔍 Top Market Maker Candidates\n\n"
    report_content += (
        "The following wallets show the highest market maker probabilities:\n\n"
    )

    # Sort wallets by MM probability
    sorted_wallets = sorted(
        wallet_data, key=lambda x: x["mm_probability"], reverse=True
    )

    for i, wallet in enumerate(sorted_wallets[:5], 1):
        report_content += f"""
### {i}. {wallet["address"][:12]}...
- **Classification:** {wallet["classification"].replace("_", " ").title()}
- **Market Maker Probability:** {wallet["mm_probability"]:.3f}
- **Confidence Score:** {wallet["confidence"]:.3f}
- **Trading Activity:** {wallet["trades_per_hour"] * 24:.1f} trades/day
- **Markets Traded:** {wallet["markets_traded"]}
"""

    report_content += "\n"
    report_content += "## 💡 Recommendations\n\n"
    report_content += "1. **Prioritize** wallets with MM probability > 0.7 for market making opportunities\n"
    report_content += (
        "2. **Monitor** arbitrage traders (MM probability 0.6-0.7) for spread trading\n"
    )
    report_content += "3. **Consider** mixed traders for balanced portfolio exposure\n"
    report_content += "4. **Avoid** low activity wallets until they demonstrate consistent patterns\n\n"
    report_content += "---\n"
    report_content += (
        "*Analysis completed using advanced behavioral pattern recognition*\n"
    )

    with open(output_dir / "analysis_report.md", "w") as f:
        f.write(report_content)


if __name__ == "__main__":
    create_market_maker_dashboard()
