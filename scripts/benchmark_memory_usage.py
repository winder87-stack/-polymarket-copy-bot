from typing import Optional, Dict, Any

#!/usr/bin/env python3
"""
Memory Usage Benchmark
=======================

Monitors memory usage during wallet scanning operations.
Critical for validating <500MB memory target.

Usage:
    python scripts/benchmark_memory_usage.py --duration 300 --interval 5
"""

import argparse
import gc
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Try to import psutil for memory tracking
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️  psutil not available. Install with: pip install psutil")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB"""
    if not PSUTIL_AVAILABLE:
        return 0.0

    process = psutil.Process()
    memory_info = process.memory_info()
    return memory_info.rss / (1024 * 1024)  # Convert to MB


def benchmark_memory_usage(
    duration_seconds: int = 300,
    interval_seconds: int = 5,
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Benchmark memory usage over time.

    Args:
        duration_seconds: Total duration to monitor (default: 300 seconds = 5 minutes)
        interval_seconds: Sampling interval (default: 5 seconds)
        output_file: Optional path to save JSON results

    Returns:
        Dictionary with memory benchmark results
    """
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    print("🧪 Starting memory benchmark...")
    print(f"   Duration: {duration_seconds}s ({duration_seconds / 60:.1f} minutes)")
    print(f"   Interval: {interval_seconds}s")
    print(f"   Output: {output_file or 'stdout'}")

    # Force garbage collection before starting
    gc.collect()

    # Track memory samples
    memory_samples = []
    timestamps = []

    start_time = time.time()
    sample_count = 0

    try:
        while time.time() - start_time < duration_seconds:
            # Record memory usage
            memory_mb = get_memory_usage_mb()
            timestamp = datetime.now(timezone.utc).isoformat()

            memory_samples.append(memory_mb)
            timestamps.append(timestamp)
            sample_count += 1

            # Print sample
            print(f"[{timestamp}] Sample {sample_count}: {memory_mb:.2f}MB")

            # Check for memory threshold breach
            if memory_mb > 500:
                print(
                    f"⚠️  WARNING: Memory exceeded 500MB threshold ({memory_mb:.2f}MB)"
                )

            # Wait for next sample
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n⚠️  Benchmark interrupted by user")

    # Final garbage collection
    gc.collect()
    final_memory_mb = get_memory_usage_mb()

    # Calculate statistics
    import statistics

    memory_stats = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": time.time() - start_time,
        "samples_collected": sample_count,
        "memory_usage_mb": {
            "current": final_memory_mb,
            "min": min(memory_samples) if memory_samples else 0,
            "max": max(memory_samples) if memory_samples else 0,
            "avg": statistics.mean(memory_samples) if memory_samples else 0,
            "median": statistics.median(memory_samples) if memory_samples else 0,
            "std_dev": statistics.stdev(memory_samples) if memory_samples else 0,
            "p95": sorted(memory_samples)[int(len(memory_samples) * 0.95)]
            if len(memory_samples) > 1
            else 0,
        },
        "thresholds": {
            "target_mb": 500,
            "warning_threshold_mb": 400,
            "critical_threshold_mb": 500,
            "breached": max(memory_samples) > 500 if memory_samples else False,
        },
        "samples": list(zip(timestamps, memory_samples)),
    }

    # Print summary
    print("\n" + "=" * 80)
    print("MEMORY BENCHMARK RESULTS")
    print("=" * 80)
    print(f"\nSamples Collected: {sample_count}")
    print(
        f"Duration: {memory_stats['duration_seconds']:.2f}s ({memory_stats['duration_seconds'] / 60:.1f} minutes)"
    )
    print("\nMemory Usage (MB):")
    print(f"  Current:  {memory_stats['memory_usage_mb']['current']:.2f}MB")
    print(f"  Average:   {memory_stats['memory_usage_mb']['avg']:.2f}MB")
    print(f"  Median:    {memory_stats['memory_usage_mb']['median']:.2f}MB")
    print(f"  Min:       {memory_stats['memory_usage_mb']['min']:.2f}MB")
    print(f"  Max:       {memory_stats['memory_usage_mb']['max']:.2f}MB")
    print(f"  Std Dev:   {memory_stats['memory_usage_mb']['std_dev']:.2f}MB")
    print(f"  P95:       {memory_stats['memory_usage_mb']['p95']:.2f}MB")

    # Check thresholds
    thresholds = memory_stats["thresholds"]
    print("\nThreshold Checks:")
    print(
        f"  Target (<500MB): {'✅ PASS' if thresholds['breached'] is False else '❌ FAIL'}"
    )
    print(
        f"  Memory Peak: {memory_stats['memory_usage_mb']['max']:.2f}MB (target: {thresholds['target_mb']}MB)"
    )

    if thresholds["breached"]:
        print("\n🚨 CRITICAL: Memory threshold exceeded!")
        print("   Action: Reduce cache sizes or batch sizes")
    elif memory_stats["memory_usage_mb"]["max"] > 400:
        print("\n⚠️  WARNING: Approaching memory limit")
        print("   Action: Monitor closely, consider optimization")
    else:
        print("\n✅ Memory usage well within limits")

    # Save to file if specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(memory_stats, f, indent=2, default=str)

        print(f"\n✅ Results saved to: {output_path}")

    return memory_stats


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Memory usage benchmark for wallet scanner"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Benchmark duration in seconds (default: 300)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Sampling interval in seconds (default: 5)",
    )
    parser.add_argument("--output", type=str, help="Output JSON file path")

    args = parser.parse_args()

    # Generate output filename if not specified
    output_file = args.output
    if not output_file:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_file = f"benchmarks/memory_benchmark_{timestamp}.json"

    # Run benchmark
    try:
        results = benchmark_memory_usage(
            duration_seconds=args.duration,
            interval_seconds=args.interval,
            output_file=output_file,
        )

        # Exit with appropriate code
        sys.exit(0 if not results.get("thresholds", {}).get("breached", False) else 1)

    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
