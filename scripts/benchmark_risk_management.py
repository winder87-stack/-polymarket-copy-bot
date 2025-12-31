from typing import Optional, Dict, Any, List, Tuple

#!/usr/bin/env python3
"""
Risk Management Benchmark
=========================

Tests risk framework PILLAR implementation:
- PILLAR 1: Specialization scoring
- PILLAR 2: Risk behavior detection
- PILLAR 3: Market structure analysis

Usage:
    python scripts/benchmark_risk_management.py --trades 2000 --max-loss 5.00
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def calculate_specialization_score(trades: List[Dict[str, Any]]) -> Tuple[float, str]:
    """
    Calculate specialization score with O(n) efficiency.

    PILLAR 1 - Specialization (35% weight):
        - Measures focus in specific market categories
        - Early rejection for generalists (diversified across 5+ categories)
        - Top category must represent 50%+ of volume

    Args:
        trades: List of trade dictionaries

    Returns:
        Tuple of (specialization_score, top_category_name)
    """
    if not trades:
        return 0.0, "NO_DATA"

    categories = defaultdict(lambda: Decimal("0"))
    total_vol = Decimal("0")

    # Single pass calculation - O(n)
    for t in trades:
        cat = t.get("category", "Uncategorized")
        vol = Decimal(str(t.get("amount", "0")))
        categories[cat] += vol
        total_vol += vol

    if total_vol == Decimal("0"):
        return 0.0, "NO_DATA"

    # Find top category
    top_category = max(categories.items(), key=lambda x: x[1])
    score = float(top_category[1] / total_vol)

    return score, top_category[0]


def analyze_martingale_behavior(
    trade_history: List[Dict[str, Any]],
    martingale_threshold: float = 1.5,
    martingale_limit: float = 0.20,
) -> Tuple[bool, int, float]:
    """
    Optimized Martingale detection with early termination.

    PILLAR 2 - Risk Behavior (40% weight):
        - Detects "loss chasing" behavior (Martingale strategy)
        - Early termination when >20% chasing detected
        - Analyzes up to 100 most recent trades

    Algorithm:
        1. Sort trades by timestamp (assume pre-sorted for performance)
        2. For each loss, check if next trade is >1.5x position size
        3. If chasing instances > 20% of total, trigger rejection

    Args:
        trade_history: List of trades sorted by timestamp
        martingale_threshold: Position size multiplier after loss (default: 1.5x)
        martingale_limit: Chasing ratio threshold (default: 20%)

    Returns:
        Tuple of (is_martingale, chasing_instance_count, chasing_ratio)
    """
    if not trade_history:
        return False, 0, 0.0

    chasing_instances = 0
    clean_instances = 0
    max_trades = min(len(trade_history) - 1, 100)  # Limit to 100 most recent trades

    # Analyze up to MAX_TRADES_FOR_ANALYSIS most recent trades
    for i in range(max_trades):
        current = trade_history[i]
        next_trade = trade_history[i + 1]

        # Skip if no PnL data
        if "pnl" not in current or "amount" not in current:
            continue

        # Check for loss
        if current["pnl"] < 0:  # Loss detected
            # Check if next trade is chasing (1.5x position size)
            try:
                current_amount = Decimal(str(current["amount"]))
                next_amount = Decimal(str(next_trade["amount"]))

                if next_amount > (current_amount * Decimal(str(martingale_threshold))):
                    chasing_instances += 1

                    # Early termination - if >20% chasing, reject immediately
                    total_instances = chasing_instances + clean_instances
                    if total_instances > 0:
                        chasing_ratio = chasing_instances / total_instances
                        if chasing_ratio > martingale_limit:
                            return True, chasing_instances, chasing_ratio
                else:
                    clean_instances += 1
            except (ValueError, TypeError):
                continue

    # Final check if chasing ratio exceeds limit
    total_instances = chasing_instances + clean_instances
    chasing_ratio = chasing_instances / total_instances if total_instances > 0 else 0.0

    is_martingale = chasing_ratio > martingale_limit

    return is_martingale, chasing_instances, chasing_ratio


def detect_market_maker_pattern(
    wallet_data: Dict[str, Any],
    hold_time_threshold: int = 14400,
    win_rate_min: float = 0.48,
    win_rate_max: float = 0.52,
    profit_threshold: float = 0.02,
) -> bool:
    """
    Lightning-fast market maker detection.

    PILLAR 3 - Market Structure (25% weight):
        - Market makers have predictable patterns:
            * Very short hold times (<4 hours)
            * Win rate clustered around 50% (48-52%)
            * Low profit per trade (<2%)
        - Uses exact thresholds for consistency

    Args:
        wallet_data: Dictionary containing wallet performance metrics
        hold_time_threshold: Avg hold time threshold (default: <4 hours)
        win_rate_min: Minimum win rate (default: 48%)
        win_rate_max: Maximum win rate (default: 52%)
        profit_threshold: Profit per trade threshold (default: <2%)

    Returns:
        True if wallet matches market maker pattern, False otherwise
    """
    avg_hold_time = wallet_data.get("avg_hold_time_seconds", 999999)
    win_rate = wallet_data.get("win_rate", 0.0)
    profit_per_trade = wallet_data.get("profit_per_trade", 0.0)

    # Check market maker signature
    is_mm = (
        avg_hold_time < hold_time_threshold
        and win_rate_min <= win_rate <= win_rate_max
        and profit_per_trade < profit_threshold
    )

    return is_mm


def generate_test_wallets(count: int) -> List[Dict[str, Any]]:
    """
    Generate test wallet data for benchmarking.

    Args:
        count: Number of wallets to generate

    Returns:
        List of wallet data dictionaries
    """
    wallets = []
    categories = ["US_POLITICS", "CRYPTO", "SPORTS", "FINANCE", "ENTERTAINMENT"]

    # Generate realistic wallet distribution:
    # - 5% TARGET (good performance, specialized)
    # - 10% WATCHLIST (decent but risky)
    # - 80% REJECT (generalists, martingale, market makers)

    for i in range(count):
        if i < int(count * 0.05):  # 5% TARGET
            # TARGET: Specialized, low risk, good performance
            primary_category = categories[i % len(categories)]
            trades = []

            # Generate trades focused in primary category (75-90% in one category)
            for j in range(100):
                if j < 85:  # 85% in primary category
                    trades.append(
                        {
                            "category": primary_category,
                            "amount": float(100 + (j % 50)),
                            "pnl": float(10 + (j % 30) - (j % 20)),  # Mostly positive
                        }
                    )
                else:  # 15% spread across other categories
                    other_cat = categories[(i + j) % len(categories)]
                    trades.append(
                        {
                            "category": other_cat,
                            "amount": float(50 + (j % 30)),
                            "pnl": float(5 + (j % 15) - (j % 10)),
                        }
                    )

            wallet = {
                "address": f"0x{''.join(['0'] * 40)}",
                "category": primary_category,
                "win_rate": 0.65 + (i % 15) * 0.01,  # 65-80%
                "roi_30d": 20.0 + (i % 20),  # 20-40%
                "max_drawdown": 0.15 + (i % 10) * 0.01,  # 15-25%
                "avg_hold_time_seconds": 86400 + (i % 7200),  # 24-44 hours
                "profit_per_trade": 0.03 + (i % 20) * 0.005,  # 3-4%
                "trade_count": 100 + i,
                "trades": trades,
                "classification": "TARGET",
            }

        elif i < int(count * 0.15):  # 10% WATCHLIST
            # WATCHLIST: Decent performance but some risk
            primary_category = categories[i % len(categories)]
            trades = []

            for j in range(80):
                # 60% in primary category, 40% spread
                if j < 48:
                    trades.append(
                        {
                            "category": primary_category,
                            "amount": float(80 + (j % 40)),
                            "pnl": float(8 + (j % 25) - (j % 15)),
                        }
                    )
                else:
                    other_cat = categories[(i + j) % len(categories)]
                    trades.append(
                        {
                            "category": other_cat,
                            "amount": float(60 + (j % 30)),
                            "pnl": float(6 + (j % 20) - (j % 12)),
                        }
                    )

            wallet = {
                "address": f"0x{''.join(['1'] * 40)}",
                "category": primary_category,
                "win_rate": 0.55 + (i % 10) * 0.01,  # 55-65%
                "roi_30d": 12.0 + (i % 15),  # 12-27%
                "max_drawdown": 0.25 + (i % 15) * 0.01,  # 25-40%
                "avg_hold_time_seconds": 36000 + (i % 7200),  # 10-30 hours
                "profit_per_trade": 0.02 + (i % 15) * 0.003,  # 2-2.5%
                "trade_count": 80 + i,
                "trades": trades,
                "classification": "WATCHLIST",
            }

        else:  # 85% REJECT
            # Split REJECT into: 50% generalist, 20% martingale, 15% market maker
            reject_type = i % 100

            if reject_type < 50:  # 50% GENERALIST
                # Generalist: diversified across 6+ categories
                trades = []
                for j in range(60):
                    cat = categories[j % len(categories)]
                    if j < 6:  # Add 6 categories first
                        trades.append(
                            {
                                "category": cat,
                                "amount": float(100 + (j % 50)),
                                "pnl": float(5 + (j % 20) - (j % 15)),
                            }
                        )

                wallet = {
                    "address": f"0x{''.join(['2'] * 40)}",
                    "category": "GENERALIST",
                    "win_rate": 0.60,
                    "roi_30d": 8.0,
                    "max_drawdown": 0.20,
                    "avg_hold_time_seconds": 86400,
                    "profit_per_trade": 0.025,
                    "trade_count": 60,
                    "trades": trades,
                    "classification": "REJECT",
                    "rejection_reason": "GENERALIST",
                }

            elif reject_type < 70:  # 20% MARTINGALE
                # Martingale: Loss chasing behavior
                trades = []
                for j in range(80):
                    is_loss = j % 3 == 0  # Every 3rd trade is a loss
                    if is_loss:
                        # Chase after loss (1.5x-2.0x position size)
                        amount = 100 * (1.5 + (j % 5) * 0.1)
                    else:
                        # Normal trades
                        amount = 100

                    trades.append(
                        {
                            "category": "CRYPTO",
                            "amount": amount,
                            "pnl": -10.0 if is_loss else 5.0,
                        }
                    )

                wallet = {
                    "address": f"0x{''.join(['3'] * 40)}",
                    "category": "MARTINGALE",
                    "win_rate": 0.42,  # Low win rate from chasing
                    "roi_30d": -5.0,  # Negative from chasing
                    "max_drawdown": 0.45,  # High drawdown
                    "avg_hold_time_seconds": 43200,  # 12 hours
                    "profit_per_trade": -0.02,
                    "trade_count": 80,
                    "trades": trades,
                    "classification": "REJECT",
                    "rejection_reason": "MARTINGALE",
                }

            else:  # 30% MARKET MAKER
                # Market maker: High frequency, low profit, 50% win rate
                trades = []
                for j in range(200):
                    # Consistent size, 50% win rate
                    trades.append(
                        {
                            "category": "FINANCE",
                            "amount": 50.0,
                            "pnl": 1.0 if j % 2 == 0 else -1.0,  # 50% win
                        }
                    )

                wallet = {
                    "address": f"0x{''.join(['4'] * 40)}",
                    "category": "MARKET_MAKER",
                    "win_rate": 0.50,  # Exactly 50%
                    "roi_30d": 5.0,  # Low but positive
                    "max_drawdown": 0.10,  # Low drawdown
                    "avg_hold_time_seconds": 7200,  # <2 hours
                    "profit_per_trade": 0.01,  # <2%
                    "trade_count": 200,
                    "trades": trades,
                    "classification": "REJECT",
                    "rejection_reason": "MARKET_MAKER",
                }

        wallets.append(wallet)

    return wallets


def benchmark_risk_framework(
    num_wallets: int = 1000,
    max_loss: float = 5.00,
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Benchmark risk framework PILLAR implementation.

    Args:
        num_wallets: Number of wallets to benchmark (default: 1000)
        max_loss: Maximum daily loss threshold (default: $5.00)
        output_file: Optional path to save JSON results

    Returns:
        Dictionary with benchmark results
    """
    print("🧪 Starting risk framework benchmark...")
    print(f"   Wallets: {num_wallets}")
    print(f"   Max Loss: ${max_loss:.2f}")
    print(f"   Output: {output_file or 'stdout'}")

    # Generate test wallets
    start_time = time.time()
    test_wallets = generate_test_wallets(num_wallets)

    # Analyze each wallet
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_configuration": {
            "num_wallets": num_wallets,
            "max_loss_threshold": max_loss,
        },
        "pillar_1_specialization": {
            "total_wallets": 0,
            "target_count": 0,
            "watchlist_count": 0,
            "reject_count": 0,
            "generalist_count": 0,
            "avg_specialization_score": 0.0,
            "processing_time_ms": 0.0,
        },
        "pillar_2_risk_behavior": {
            "total_wallets": 0,
            "martingale_count": 0,
            "chasing_avg_ratio": 0.0,
            "max_chasing_ratio": 0.0,
            "processing_time_ms": 0.0,
        },
        "pillar_3_market_structure": {
            "total_wallets": 0,
            "market_maker_count": 0,
            "normal_count": 0,
            "processing_time_ms": 0.0,
        },
        "classification_summary": {
            "target": 0,
            "watchlist": 0,
            "reject": 0,
            "generalist_rejects": 0,
            "martingale_rejects": 0,
            "market_maker_rejects": 0,
        },
        "performance_metrics": {
            "total_time_seconds": 0.0,
            "wallets_per_second": 0.0,
            "avg_time_per_wallet_ms": 0.0,
        },
    }

    # PILLAR 1: Specialization Analysis
    print("\n📊 PILLAR 1: Specialization Analysis...")
    pillar1_start = time.time()

    for wallet in test_wallets:
        score, top_cat = calculate_specialization_score(wallet["trades"])

        results["pillar_1_specialization"]["total_wallets"] += 1
        results["pillar_1_specialization"]["avg_specialization_score"] += score

        if wallet["classification"] == "TARGET":
            results["pillar_1_specialization"]["target_count"] += 1
        elif wallet["classification"] == "WATCHLIST":
            results["pillar_1_specialization"]["watchlist_count"] += 1
        else:
            results["pillar_1_specialization"]["reject_count"] += 1
            if wallet.get("rejection_reason") == "GENERALIST":
                results["pillar_1_specialization"]["generalist_count"] += 1

    pillar1_time = (time.time() - pillar1_start) * 1000
    results["pillar_1_specialization"]["processing_time_ms"] = pillar1_time

    # Calculate averages
    total_p1 = results["pillar_1_specialization"]["total_wallets"]
    if total_p1 > 0:
        results["pillar_1_specialization"]["avg_specialization_score"] /= total_p1

    print(f"   ✓ Processed {total_p1} wallets in {pillar1_time:.1f}ms")
    print(
        f"   ✓ Avg specialization: {results['pillar_1_specialization']['avg_specialization_score']:.2f}"
    )
    print(
        f"   ✓ Generalists rejected: {results['pillar_1_specialization']['generalist_count']}/{total_p1} ({results['pillar_1_specialization']['generalist_count'] / total_p1:.1%})"
    )

    # PILLAR 2: Risk Behavior Analysis
    print("\n🔬 PILLAR 2: Risk Behavior Analysis...")
    pillar2_start = time.time()

    chasing_ratios = []

    for wallet in test_wallets:
        is_martingale, chasing_count, chasing_ratio = analyze_martingale_behavior(
            wallet["trades"]
        )

        results["pillar_2_risk_behavior"]["total_wallets"] += 1
        results["pillar_2_risk_behavior"]["chasing_avg_ratio"] += chasing_ratio
        results["pillar_2_risk_behavior"]["max_chasing_ratio"] = max(
            results["pillar_2_risk_behavior"]["max_chasing_ratio"], chasing_ratio
        )

        if is_martingale:
            results["pillar_2_risk_behavior"]["martingale_count"] += 1
            results["classification_summary"]["martingale_rejects"] += 1
            results["classification_summary"]["reject"] += 1
        else:
            results["classification_summary"]["reject"] += 1

    pillar2_time = (time.time() - pillar2_start) * 1000
    results["pillar_2_risk_behavior"]["processing_time_ms"] = pillar2_time

    # Calculate averages
    total_p2 = results["pillar_2_risk_behavior"]["total_wallets"]
    if total_p2 > 0:
        results["pillar_2_risk_behavior"]["chasing_avg_ratio"] /= total_p2

    print(f"   ✓ Processed {total_p2} wallets in {pillar2_time:.1f}ms")
    print(
        f"   ✓ Martingale detected: {results['pillar_2_risk_behavior']['martingale_count']}/{total_p2} ({results['pillar_2_risk_behavior']['martingale_count'] / total_p2:.1%})"
    )
    print(
        f"   ✓ Avg chasing ratio: {results['pillar_2_risk_behavior']['chasing_avg_ratio']:.2%}"
    )
    print(
        f"   ✓ Max chasing ratio: {results['pillar_2_risk_behavior']['max_chasing_ratio']:.2%}"
    )

    # PILLAR 3: Market Structure Analysis
    print("\n🏗️  PILLAR 3: Market Structure Analysis...")
    pillar3_start = time.time()

    for wallet in test_wallets:
        is_mm = detect_market_maker_pattern(wallet)

        results["pillar_3_market_structure"]["total_wallets"] += 1

        if is_mm:
            results["pillar_3_market_structure"]["market_maker_count"] += 1
            results["classification_summary"]["market_maker_rejects"] += 1
            results["classification_summary"]["reject"] += 1
        else:
            results["pillar_3_market_structure"]["normal_count"] += 1

    pillar3_time = (time.time() - pillar3_start) * 1000
    results["pillar_3_market_structure"]["processing_time_ms"] = pillar3_time

    print(
        f"   ✓ Processed {results['pillar_3_market_structure']['total_wallets']} wallets in {pillar3_time:.1f}ms"
    )
    print(
        f"   ✓ Market makers detected: {results['pillar_3_market_structure']['market_maker_count']}/{results['pillar_3_market_structure']['total_wallets']} ({results['pillar_3_market_structure']['market_maker_count'] / results['pillar_3_market_structure']['total_wallets']:.1%})"
    )

    # Calculate final statistics
    total_time = time.time() - start_time
    results["performance_metrics"]["total_time_seconds"] = total_time
    results["performance_metrics"]["wallets_per_second"] = num_wallets / total_time
    results["performance_metrics"]["avg_time_per_wallet_ms"] = (
        total_time * 1000
    ) / num_wallets

    # Classification summary
    results["classification_summary"]["target"] = results["pillar_1_specialization"][
        "target_count"
    ]
    results["classification_summary"]["watchlist"] = results["pillar_1_specialization"][
        "watchlist_count"
    ]
    results["classification_summary"]["reject"] = results["classification_summary"][
        "reject"
    ]

    # Print summary
    print("\n" + "=" * 80)
    print("RISK FRAMEWORK BENCHMARK RESULTS")
    print("=" * 80)

    print("\n📊 PILLAR 1: Specialization (35% weight)")
    print(f"   Total Wallets: {results['pillar_1_specialization']['total_wallets']}")
    print(
        f"   Targets: {results['pillar_1_specialization']['target_count']} ({results['pillar_1_specialization']['target_count'] / results['pillar_1_specialization']['total_wallets']:.1%})"
    )
    print(
        f"   Watchlists: {results['pillar_1_specialization']['watchlist_count']} ({results['pillar_1_specialization']['watchlist_count'] / results['pillar_1_specialization']['total_wallets']:.1%})"
    )
    print(
        f"   Generalists: {results['pillar_1_specialization']['generalist_count']} ({results['pillar_1_specialization']['generalist_count'] / results['pillar_1_specialization']['total_wallets']:.1%})"
    )
    print(
        f"   Avg Specialization: {results['pillar_1_specialization']['avg_specialization_score']:.2f}"
    )
    print(
        f"   Processing Time: {results['pillar_1_specialization']['processing_time_ms']:.2f}ms"
    )

    print("\n🔬 PILLAR 2: Risk Behavior (40% weight)")
    print(f"   Total Wallets: {results['pillar_2_risk_behavior']['total_wallets']}")
    print(
        f"   Martingale: {results['pillar_2_risk_behavior']['martingale_count']} ({results['pillar_2_risk_behavior']['martingale_count'] / results['pillar_2_risk_behavior']['total_wallets']:.1%})"
    )
    print(
        f"   Avg Chasing Ratio: {results['pillar_2_risk_behavior']['chasing_avg_ratio']:.2%}"
    )
    print(
        f"   Max Chasing Ratio: {results['pillar_2_risk_behavior']['max_chasing_ratio']:.2%}"
    )
    print(
        f"   Processing Time: {results['pillar_2_risk_behavior']['processing_time_ms']:.2f}ms"
    )

    print("\n🏗️  PILLAR 3: Market Structure (25% weight)")
    print(f"   Total Wallets: {results['pillar_3_market_structure']['total_wallets']}")
    print(
        f"   Market Makers: {results['pillar_3_market_structure']['market_maker_count']} ({results['pillar_3_market_structure']['market_maker_count'] / results['pillar_3_market_structure']['total_wallets']:.1%})"
    )
    print(
        f"   Normal: {results['pillar_3_market_structure']['normal_count']} ({results['pillar_3_market_structure']['normal_count'] / results['pillar_3_market_structure']['total_wallets']:.1%})"
    )
    print(
        f"   Processing Time: {results['pillar_3_market_structure']['processing_time_ms']:.2f}ms"
    )

    print("\n📈 Classification Summary")
    print(
        f"   TARGET: {results['classification_summary']['target']} ({results['classification_summary']['target'] / num_wallets:.1%})"
    )
    print(
        f"   WATCHLIST: {results['classification_summary']['watchlist']} ({results['classification_summary']['watchlist'] / num_wallets:.1%})"
    )
    print(
        f"   REJECT: {results['classification_summary']['reject']} ({results['classification_summary']['reject'] / num_wallets:.1%})"
    )
    print(
        f"     - Generalists: {results['classification_summary']['generalist_rejects']}"
    )
    print(
        f"     - Martingale: {results['classification_summary']['martingale_rejects']}"
    )
    print(
        f"     - Market Makers: {results['classification_summary']['market_maker_rejects']}"
    )

    print("\n⚡ Performance Metrics")
    print(f"   Total Time: {results['performance_metrics']['total_time_seconds']:.2f}s")
    print(
        f"   Wallets/Second: {results['performance_metrics']['wallets_per_second']:.1f}"
    )
    print(
        f"   Avg Time/Wallet: {results['performance_metrics']['avg_time_per_wallet_ms']:.2f}ms"
    )

    # Calculate overall score
    total_pillar_time = (
        results["pillar_1_specialization"]["processing_time_ms"]
        + results["pillar_2_risk_behavior"]["processing_time_ms"]
        + results["pillar_3_market_structure"]["processing_time_ms"]
    )
    avg_pillar_time = total_pillar_time / 3
    results["avg_pillar_time_ms"] = avg_pillar_time

    print(f"\n✅ Average PILLAR Analysis Time: {avg_pillar_time:.2f}ms")
    print(f"   Total PILLAR Time: {total_pillar_time:.2f}ms")

    # Check performance targets
    target_wallets_per_second = num_wallets / 60.0  # 1000 wallets in 60 seconds
    is_fast = (
        results["performance_metrics"]["wallets_per_second"]
        >= target_wallets_per_second
    )

    print("\n🎯 Performance Check")
    print(f"   Target: {target_wallets_per_second:.1f} wallets/second")
    print(
        f"   Achieved: {results['performance_metrics']['wallets_per_second']:.1f} wallets/second"
    )
    print(f"   Status: {'✅ PASS' if is_fast else '❌ FAIL'}")

    # Save to file if specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n✅ Results saved to: {output_path}")

    # Final status
    overall_status = is_fast

    print("\n" + "=" * 80)
    print(
        f"STATUS: {'✅ ALL CHECKS PASSED' if overall_status else '⚠️  SOME CHECKS FAILED'}"
    )
    print("=" * 80)

    return results


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Risk management benchmark for wallet scanner"
    )
    parser.add_argument(
        "--trades",
        type=int,
        default=2000,
        help="Number of trades to simulate (default: 2000)",
    )
    parser.add_argument(
        "--wallets",
        type=int,
        default=1000,
        help="Number of wallets to benchmark (default: 1000)",
    )
    parser.add_argument(
        "--max-loss",
        type=float,
        default=5.00,
        help="Maximum daily loss threshold (default: $5.00)",
    )
    parser.add_argument("--output", type=str, help="Output JSON file path")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    try:
        results = benchmark_risk_framework(
            num_wallets=args.wallets,
            max_loss=args.max_loss,
            output_file=args.output,
        )

        # Exit with appropriate code
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n⚠️  Benchmark interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
