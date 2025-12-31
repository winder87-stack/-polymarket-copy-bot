from typing import Dict, Any, List

#!/usr/bin/env python3
"""
High-Performance Wallet Scanner Benchmark
========================================

Validates performance targets:
- Process 1000+ wallets/minute on standard cloud instance (4 CPU, 8GB RAM)
- Memory footprint <500MB even during full scans
- 95% rejection rate in early stages
- Stage 1: <10ms average
- Stage 2: <50ms average
- Stage 3: <200ms average
- Overall: <25ms average per wallet

Usage:
    python scripts/benchmark_high_performance_scanner.py
    python scripts/benchmark_high_performance_scanner.py --wallets 1000 --verbose
"""

import argparse
import asyncio
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.scanner_config import ScannerConfig
from scanners.high_performance_wallet_scanner import (
    HighPerformanceWalletScanner,
    RiskFrameworkConfig,
    create_high_performance_scanner,
)
from utils.logger import setup_logging, get_logger

logger = get_logger(__name__)


# ============================================================================
# Mock Data Generators
# ============================================================================


def generate_mock_wallet_data(
    address: str,
    wallet_type: str = "normal",
) -> Dict:
    """
    Generate mock wallet data for benchmarking.

    Args:
        address: Wallet address
        wallet_type: Type of wallet ("normal", "generalist", "martingale", "market_maker")

    Returns:
        Dictionary with mock wallet data
    """
    if wallet_type == "generalist":
        # Generalist: diverse across 6+ categories
        categories = [
            "Politics",
            "Sports",
            "Finance",
            "Crypto",
            "Entertainment",
            "Technology",
        ]
        trades = []
        for i, category in enumerate(categories):
            trades.append(
                {
                    "category": category,
                    "amount": random.uniform(50, 150),
                    "pnl": random.uniform(-20, 30),
                    "timestamp": time.time() - (len(categories) - i) * 1000,
                }
            )

        return {
            "address": address,
            "trade_count": random.randint(80, 120),
            "wallet_age_days": random.randint(30, 90),
            "trades": trades,
            "avg_hold_time_seconds": random.randint(1800, 7200),
            "win_rate": random.uniform(0.55, 0.65),
            "max_drawdown": random.uniform(0.10, 0.20),
            "roi_30d": random.uniform(10.0, 20.0),
            "roi_7d": random.uniform(3.0, 10.0),
            "profit_factor": random.uniform(1.2, 1.8),
        }

    elif wallet_type == "martingale":
        # Martingale: loss chasing behavior
        trades = []
        current_amount = 100.0
        for i in range(20):
            pnl = random.uniform(-30, 20)  # More losses
            trades.append(
                {
                    "category": "Sports",
                    "amount": current_amount,
                    "pnl": pnl,
                    "timestamp": time.time() - (20 - i) * 1000,
                }
            )

            # Chase after losses
            if pnl < 0:
                current_amount *= random.uniform(1.4, 1.8)  # 1.4x - 1.8x after loss
            else:
                current_amount = max(50.0, current_amount * 0.9)

        return {
            "address": address,
            "trade_count": len(trades),
            "wallet_age_days": random.randint(20, 60),
            "trades": trades,
            "avg_hold_time_seconds": random.randint(1800, 7200),
            "win_rate": random.uniform(0.40, 0.50),  # Lower win rate from chasing
            "max_drawdown": random.uniform(0.30, 0.50),  # Higher drawdown
            "roi_30d": random.uniform(-10.0, 5.0),
        }

    elif wallet_type == "market_maker":
        # Market maker: high frequency, low profit per trade
        trades = []
        for i in range(200):
            trades.append(
                {
                    "category": "Finance",
                    "amount": random.uniform(45, 55),  # Consistent size
                    "pnl": random.uniform(-2, 2),  # Low PnL per trade
                    "timestamp": time.time() - (200 - i) * 100,
                }
            )

        return {
            "address": address,
            "trade_count": random.randint(500, 1000),
            "wallet_age_days": random.randint(60, 120),
            "trades": trades[:20],  # Only return recent trades
            "avg_hold_time_seconds": random.randint(3600, 10800),  # <3 hours
            "win_rate": random.uniform(0.48, 0.52),  # 50% +/- 2%
            "profit_per_trade": random.uniform(0.005, 0.015),  # <2%
            "roi_30d": random.uniform(5.0, 15.0),
        }

    else:
        # Normal: specialized, good performance
        categories = ["Politics", "Sports", "Finance", "Crypto", "Entertainment"]
        primary_category = random.choice(categories)

        trades = []
        for i in range(random.randint(20, 50)):
            # 80% in primary category, 20% spread across others
            if random.random() < 0.8:
                category = primary_category
                amount = random.uniform(100, 200)
            else:
                category = random.choice(
                    [c for c in categories if c != primary_category]
                )
                amount = random.uniform(50, 100)

            trades.append(
                {
                    "category": category,
                    "amount": amount,
                    "pnl": random.uniform(-10, 20),
                    "timestamp": time.time() - (len(trades) - i) * 1000,
                }
            )

        return {
            "address": address,
            "trade_count": len(trades),
            "wallet_age_days": random.randint(60, 180),
            "trades": trades,
            "avg_hold_time_seconds": random.randint(3600, 14400),
            "win_rate": random.uniform(0.60, 0.75),
            "max_drawdown": random.uniform(0.10, 0.25),
            "roi_30d": random.uniform(15.0, 40.0),
            "roi_7d": random.uniform(5.0, 15.0),
            "profit_factor": random.uniform(1.5, 2.5),
            "sharpe_ratio": random.uniform(0.8, 2.0),
            "volatility": random.uniform(0.15, 0.30),
        }


def generate_test_wallets(
    count: int,
    target_percentage: float = 0.05,
) -> List[str]:
    """
    Generate test wallet list with realistic distribution.

    Args:
        count: Total number of wallets to generate
        target_percentage: Percentage of TARGET wallets (default 5%)

    Returns:
        List of wallet addresses
    """
    wallets = []

    # Distribution:
    # - 5% TARGET (good performance)
    # - 10% WATCHLIST (decent but risky)
    # - 80% REJECT Stage 1 (generalists, insufficient data)
    # - 3% REJECT Stage 2 (Martingale, market makers)
    # - 2% REJECT Stage 3 (risk score too low)

    target_count = int(count * target_percentage)
    watchlist_count = int(count * 0.10)
    stage1_reject_count = int(count * 0.80)
    stage2_reject_count = int(count * 0.03)
    stage3_reject_count = int(count * 0.02)

    # Generate addresses
    for i in range(count):
        address = f"0x{''.join(random.choices('0123456789abcdef', k=40))}"
        wallets.append(address)

    return wallets


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB"""
    process = psutil.Process()
    memory_info = process.memory_info()
    return memory_info.rss / (1024 * 1024)


# ============================================================================
# Benchmark Functions
# ============================================================================


async def benchmark_stage_performance(
    scanner: HighPerformanceWalletScanner,
    wallet_data: Dict,
) -> Dict[str, float]:
    """
    Benchmark individual stage performance.

    Args:
        scanner: Scanner instance
        wallet_data: Mock wallet data

    Returns:
        Dictionary with timing for each stage
    """
    results = {}

    # Stage 1
    start = time.time()
    await scanner._stage1_basic_validation(wallet_data["address"], wallet_data)
    results["stage1_ms"] = (time.time() - start) * 1000

    # Stage 2
    start = time.time()
    await scanner._stage2_risk_analysis(wallet_data["address"], wallet_data)
    results["stage2_ms"] = (time.time() - start) * 1000

    # Stage 3
    stage2_result = {
        "pass": True,
        "partial_score": 0.8,
        "specialization_score": 0.8,
        "risk_score": 0.9,
        "confidence_score": 0.7,
    }

    start = time.time()
    await scanner._stage3_full_analysis(
        wallet_data["address"],
        wallet_data,
        stage2_result,
    )
    results["stage3_ms"] = (time.time() - start) * 1000

    results["total_ms"] = sum(
        [results["stage1_ms"], results["stage2_ms"], results["stage3_ms"]]
    )

    return results


async def run_benchmark(
    num_wallets: int,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Run comprehensive benchmark.

    Args:
        num_wallets: Number of wallets to benchmark
        verbose: Enable verbose output

    Returns:
        Dictionary with benchmark results
    """
    logger.info(f"🚀 Starting benchmark with {num_wallets} wallets")

    # Initialize scanner
    config = ScannerConfig.from_env()
    risk_config = RiskFrameworkConfig()
    scanner = create_high_performance_scanner(config, risk_config)

    # Generate test wallets
    wallet_addresses = generate_test_wallets(num_wallets)

    # Generate mock data for each wallet
    wallet_data_map = {}
    for i, address in enumerate(wallet_addresses):
        # Determine wallet type
        if i < int(num_wallets * 0.05):
            wallet_type = "normal"  # TARGET
        elif i < int(num_wallets * 0.15):
            wallet_type = "normal"  # WATCHLIST
        elif i < int(num_wallets * 0.95):
            wallet_type = "generalist"  # REJECT Stage 1
        elif i < int(num_wallets * 0.98):
            wallet_type = random.choice(
                ["martingale", "market_maker"]
            )  # REJECT Stage 2
        else:
            wallet_type = "normal"  # REJECT Stage 3 (low score)

        wallet_data_map[address] = generate_mock_wallet_data(address, wallet_type)

    # Mock data fetching
    async def mock_fetch_wallet(address: str) -> Dict:
        return wallet_data_map.get(address, {})

    async def mock_fetch_performance(address: str) -> Dict:
        return wallet_data_map.get(address, {})

    # Patch scanner methods
    scanner._fetch_wallet_data = mock_fetch_wallet
    scanner._fetch_performance_data = mock_fetch_performance

    # ============================================================
    # Benchmark 1: Individual Stage Performance
    # ============================================================
    logger.info("📊 Benchmark 1: Individual Stage Performance")

    stage_times = {
        "stage1_ms": [],
        "stage2_ms": [],
        "stage3_ms": [],
        "total_ms": [],
    }

    # Sample 50 wallets for stage timing
    sample_addresses = wallet_addresses[:50]
    for address in sample_addresses:
        times = await benchmark_stage_performance(scanner, wallet_data_map[address])
        stage_times["stage1_ms"].append(times["stage1_ms"])
        stage_times["stage2_ms"].append(times["stage2_ms"])
        stage_times["stage3_ms"].append(times["stage3_ms"])
        stage_times["total_ms"].append(times["total_ms"])

    stage_averages = {
        "stage1_avg_ms": sum(stage_times["stage1_ms"]) / len(stage_times["stage1_ms"]),
        "stage2_avg_ms": sum(stage_times["stage2_ms"]) / len(stage_times["stage2_ms"]),
        "stage3_avg_ms": sum(stage_times["stage3_ms"]) / len(stage_times["stage3_ms"]),
        "total_avg_ms": sum(stage_times["total_ms"]) / len(stage_times["total_ms"]),
    }

    if verbose:
        logger.info(
            f"   Stage 1 avg: {stage_averages['stage1_avg_ms']:.2f}ms (target: <10ms)"
        )
        logger.info(
            f"   Stage 2 avg: {stage_averages['stage2_avg_ms']:.2f}ms (target: <50ms)"
        )
        logger.info(
            f"   Stage 3 avg: {stage_averages['stage3_avg_ms']:.2f}ms (target: <200ms)"
        )
        logger.info(
            f"   Total avg: {stage_averages['total_avg_ms']:.2f}ms (target: <25ms)"
        )

    # ============================================================
    # Benchmark 2: Batch Processing Performance
    # ============================================================
    logger.info("📊 Benchmark 2: Batch Processing Performance")

    # Measure initial memory
    initial_memory_mb = get_memory_usage_mb()

    # Process all wallets
    start_time = time.time()

    async with scanner as s:
        results, stats = await s.scan_wallet_batch(
            wallet_addresses,
            batch_size=50,
        )

    total_time = time.time() - start_time
    final_memory_mb = get_memory_usage_mb()
    memory_peak_mb = final_memory_mb - initial_memory_mb

    # Calculate metrics
    wallets_per_minute = (num_wallets / total_time) * 60
    avg_time_per_wallet_ms = (total_time * 1000) / num_wallets

    if verbose:
        logger.info(f"   Total time: {total_time:.2f}s")
        logger.info(f"   Wallets/minute: {wallets_per_minute:.1f} (target: 1000+)")
        logger.info(
            f"   Avg time/wallet: {avg_time_per_wallet_ms:.2f}ms (target: <25ms)"
        )
        logger.info(f"   Memory peak: {memory_peak_mb:.1f}MB (target: <500MB)")

    # ============================================================
    # Benchmark 3: Cache Performance
    # ============================================================
    logger.info("📊 Benchmark 3: Cache Performance")

    # First pass - cache misses
    cache_misses_before = scanner.metrics.cache_misses
    start = time.time()
    await scanner.scan_single_wallet(wallet_addresses[0], force_refresh=True)
    miss_time = (time.time() - start) * 1000
    cache_misses_after = scanner.metrics.cache_misses

    # Second pass - cache hits
    cache_hits_before = scanner.metrics.cache_hits
    start = time.time()
    await scanner.scan_single_wallet(wallet_addresses[0], force_refresh=False)
    hit_time = (time.time() - start) * 1000
    cache_hits_after = scanner.metrics.cache_hits

    speedup = miss_time / hit_time if hit_time > 0 else 0

    if verbose:
        logger.info(f"   Cache miss time: {miss_time:.2f}ms")
        logger.info(f"   Cache hit time: {hit_time:.2f}ms")
        logger.info(f"   Speedup: {speedup:.2f}x")

    # ============================================================
    # Compile Results
    # ============================================================
    benchmark_results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_configuration": {
            "num_wallets": num_wallets,
            "target_percentage": 0.05,
            "batch_size": 50,
            "concurrency": 50,
        },
        "stage_performance": {
            "stage1_avg_ms": stage_averages["stage1_avg_ms"],
            "stage1_target_ms": 10.0,
            "stage1_passed": stage_averages["stage1_avg_ms"] < 10.0,
            "stage2_avg_ms": stage_averages["stage2_avg_ms"],
            "stage2_target_ms": 50.0,
            "stage2_passed": stage_averages["stage2_avg_ms"] < 50.0,
            "stage3_avg_ms": stage_averages["stage3_avg_ms"],
            "stage3_target_ms": 200.0,
            "stage3_passed": stage_averages["stage3_avg_ms"] < 200.0,
            "total_avg_ms": stage_averages["total_avg_ms"],
            "total_target_ms": 25.0,
            "total_passed": stage_averages["total_avg_ms"] < 25.0,
        },
        "batch_performance": {
            "total_time_seconds": total_time,
            "wallets_per_minute": wallets_per_minute,
            "wallets_per_minute_target": 1000.0,
            "wallets_per_minute_passed": wallets_per_minute >= 1000.0,
            "avg_time_per_wallet_ms": avg_time_per_wallet_ms,
            "avg_time_per_wallet_target_ms": 25.0,
            "avg_time_per_wallet_passed": avg_time_per_wallet_ms < 25.0,
            "memory_peak_mb": memory_peak_mb,
            "memory_target_mb": 500.0,
            "memory_passed": memory_peak_mb < 500.0,
        },
        "cache_performance": {
            "cache_miss_time_ms": miss_time,
            "cache_hit_time_ms": hit_time,
            "speedup_factor": speedup,
        },
        "scan_statistics": {
            "total_wallets": stats.total_wallets,
            "stage1_rejected": stats.stage1_rejected,
            "stage1_rejection_rate": stats.stage1_rejected
            / max(stats.total_wallets, 1),
            "stage2_rejected": stats.stage2_rejected,
            "stage2_rejection_rate": stats.stage2_rejected
            / max(stats.total_wallets, 1),
            "stage3_rejected": stats.stage3_rejected,
            "targets_found": stats.targets_found,
            "target_rate": stats.targets_found / max(stats.total_wallets, 1),
            "watchlist_found": stats.watchlist_found,
        },
        "overall_passed": (
            stage_averages["total_avg_ms"] < 25.0
            and wallets_per_minute >= 1000.0
            and memory_peak_mb < 500.0
        ),
    }

    return benchmark_results


def print_benchmark_results(results: Dict[str, Any]) -> None:
    """Print formatted benchmark results"""
    print("\n" + "=" * 80)
    print("HIGH-PERFORMANCE WALLET SCANNER BENCHMARK RESULTS")
    print("=" * 80)
    print(f"\nTimestamp: {results['timestamp']}")
    print(f"Test Configuration: {results['test_configuration']['num_wallets']} wallets")

    # Stage Performance
    print("\n📊 STAGE PERFORMANCE")
    print("-" * 80)
    stage_perf = results["stage_performance"]

    stage1_status = "✅ PASS" if stage_perf["stage1_passed"] else "❌ FAIL"
    stage2_status = "✅ PASS" if stage_perf["stage2_passed"] else "❌ FAIL"
    stage3_status = "✅ PASS" if stage_perf["stage3_passed"] else "❌ FAIL"
    total_status = "✅ PASS" if stage_perf["total_passed"] else "❌ FAIL"

    print(
        f"Stage 1: {stage_perf['stage1_avg_ms']:.2f}ms (target: <{stage_perf['stage1_target_ms']}ms) {stage1_status}"
    )
    print(
        f"Stage 2: {stage_perf['stage2_avg_ms']:.2f}ms (target: <{stage_perf['stage2_target_ms']}ms) {stage2_status}"
    )
    print(
        f"Stage 3: {stage_perf['stage3_avg_ms']:.2f}ms (target: <{stage_perf['stage3_target_ms']}ms) {stage3_status}"
    )
    print(
        f"Total:    {stage_perf['total_avg_ms']:.2f}ms (target: <{stage_perf['total_target_ms']}ms) {total_status}"
    )

    # Batch Performance
    print("\n🚀 BATCH PROCESSING PERFORMANCE")
    print("-" * 80)
    batch_perf = results["batch_performance"]

    wpm_status = "✅ PASS" if batch_perf["wallets_per_minute_passed"] else "❌ FAIL"
    time_status = "✅ PASS" if batch_perf["avg_time_per_wallet_passed"] else "❌ FAIL"
    memory_status = "✅ PASS" if batch_perf["memory_passed"] else "❌ FAIL"

    print(
        f"Wallets/Minute: {batch_perf['wallets_per_minute']:.1f} (target: {batch_perf['wallets_per_minute_target']:.0f}+) {wpm_status}"
    )
    print(
        f"Avg Time/Wallet: {batch_perf['avg_time_per_wallet_ms']:.2f}ms (target: <{batch_perf['avg_time_per_wallet_target_ms']}ms) {time_status}"
    )
    print(
        f"Memory Peak:    {batch_perf['memory_peak_mb']:.1f}MB (target: <{batch_perf['memory_target_mb']}MB) {memory_status}"
    )

    # Cache Performance
    print("\n💾 CACHE PERFORMANCE")
    print("-" * 80)
    cache_perf = results["cache_performance"]
    print(f"Cache Miss Time: {cache_perf['cache_miss_time_ms']:.2f}ms")
    print(f"Cache Hit Time:  {cache_perf['cache_hit_time_ms']:.2f}ms")
    print(f"Speedup:        {cache_perf['speedup_factor']:.2f}x")

    # Scan Statistics
    print("\n📈 SCAN STATISTICS")
    print("-" * 80)
    scan_stats = results["scan_statistics"]
    print(f"Total Wallets:      {scan_stats['total_wallets']}")
    print(
        f"Stage 1 Rejected:   {scan_stats['stage1_rejected']} ({scan_stats['stage1_rejection_rate']:.1%})"
    )
    print(
        f"Stage 2 Rejected:   {scan_stats['stage2_rejected']} ({scan_stats['stage2_rejection_rate']:.1%})"
    )
    print(f"Stage 3 Rejected:   {scan_stats['stage3_rejected']}")
    print(
        f"Targets Found:      {scan_stats['targets_found']} ({scan_stats['target_rate']:.1%})"
    )
    print(f"Watchlist Found:    {scan_stats['watchlist_found']}")

    # Overall Result
    print("\n" + "=" * 80)
    overall_status = (
        "✅ ALL TESTS PASSED" if results["overall_passed"] else "❌ SOME TESTS FAILED"
    )
    print(f"OVERALL: {overall_status}")
    print("=" * 80 + "\n")


def save_benchmark_results(results: Dict[str, Any]) -> None:
    """Save benchmark results to file"""
    results_dir = Path("monitoring/benchmarks")
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"scanner_benchmark_{timestamp}.json"
    filepath = results_dir / filename

    with open(filepath, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"✅ Benchmark results saved to: {filepath}")


# ============================================================================
# Main Entry Point
# ============================================================================


async def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="High-Performance Wallet Scanner Benchmark"
    )
    parser.add_argument(
        "--wallets",
        type=int,
        default=1000,
        help="Number of wallets to benchmark (default: 1000)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--save", action="store_true", help="Save benchmark results to file"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    try:
        # Run benchmark
        results = await run_benchmark(
            num_wallets=args.wallets,
            verbose=args.verbose,
        )

        # Print results
        print_benchmark_results(results)

        # Save results if requested
        if args.save:
            save_benchmark_results(results)

        # Exit with appropriate code
        sys.exit(0 if results["overall_passed"] else 1)

    except Exception as e:
        logger.exception(f"Benchmark failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
