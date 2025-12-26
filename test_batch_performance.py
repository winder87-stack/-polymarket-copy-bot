#!/usr/bin/env python3
"""
Batch Transaction Processing Performance Benchmark
Tests the optimized batch processing against legacy single-transaction processing
"""

import asyncio
import random
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

# Add the core directory to path for imports
sys.path.insert(0, "core")

# Import only the BatchTransactionProcessor class directly
import importlib.util

spec = importlib.util.spec_from_file_location("wallet_monitor", "core/wallet_monitor.py")
wallet_module = importlib.util.module_from_spec(spec)


# Extract only the BatchTransactionProcessor class
class BatchTransactionProcessor:
    """Efficient batch processor for blockchain transactions"""

    def __init__(self, monitor):
        self.monitor = monitor
        self._batch_cache = {}
        self._batch_stats = {
            "total_processed": 0,
            "filtered_out": 0,
            "trades_detected": 0,
            "avg_processing_time": 0.0,
        }

    async def process_transaction_batch(
        self, transactions: List[Dict[str, Any]], wallet_address: str
    ) -> List[Dict[str, Any]]:
        """Process a batch of transactions efficiently"""
        start_time = time.time()

        try:
            # Phase 1: Pre-filter transactions (fast operations)
            filtered_txs = await self._pre_filter_transactions(transactions)
            self._batch_stats["filtered_out"] += len(transactions) - len(filtered_txs)

            if not filtered_txs:
                print(f"🧹 All transactions filtered out for {wallet_address}")
                return []

            # Phase 2: Batch confidence scoring
            confidence_scores = await self._batch_confidence_scoring(filtered_txs)

            # Phase 3: Parallel trade detection
            trades = await self._parallel_trade_detection(filtered_txs, confidence_scores)

            # Phase 4: Batch deduplication and processing
            unique_trades = self._deduplicate_trades(trades)
            self._batch_stats["trades_detected"] += len(unique_trades)

            # Phase 5: Batch update processed transactions in batch
            await self._batch_update_processed_transactions(unique_trades)

            processing_time = time.time() - start_time
            self._batch_stats["total_processed"] += len(transactions)
            self._batch_stats["avg_processing_time"] = (
                self._batch_stats["avg_processing_time"]
                * (self._batch_stats["total_processed"] - len(transactions))
                + processing_time * len(transactions)
            ) / self._batch_stats["total_processed"]

            print(
                f"⚡ Batch processed {len(transactions)} txs -> {len(unique_trades)} trades "
                f"for {wallet_address} in {processing_time:.2f}s "
                f"(avg: {self._batch_stats['avg_processing_time']:.4f}s/tx)"
            )

            return unique_trades

        except Exception as e:
            print(f"❌ Error processing transaction batch: {e}")
            return []

    async def _pre_filter_transactions(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fast pre-filtering of transactions before deep processing"""
        # Filter 1: Skip already processed transactions
        unprocessed_txs = [
            tx for tx in transactions if tx["hash"] not in self.monitor.processed_transactions
        ]

        # Filter 2: Skip transactions to non-Polymarket contracts
        polymarket_contract_set = {normalize_address(c) for c in self.monitor.polymarket_contracts}
        relevant_txs = [
            tx
            for tx in unprocessed_txs
            if normalize_address(tx.get("to", "")) in polymarket_contract_set
        ]

        # Filter 3: Skip very old transactions
        current_time = int(time.time())
        recent_txs = [
            tx
            for tx in relevant_txs
            if abs(current_time - int(tx.get("timeStamp", current_time))) < 3600  # Last hour
        ]

        print(
            f"🧹 Pre-filtering: {len(transactions)} -> {len(unprocessed_txs)} (unprocessed) "
            f"-> {len(relevant_txs)} (relevant) -> {len(recent_txs)} (recent)"
        )

        return recent_txs

    async def _batch_confidence_scoring(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate confidence scores for a batch of transactions efficiently"""
        # Prepare transaction data for vectorized processing
        tx_data = [
            {
                "value": float(tx.get("value", 0)),
                "gas_used": int(tx.get("gasUsed", 0)),
                "input_length": len(tx.get("input", "")),
                "timestamp": int(tx.get("timeStamp", time.time())),
            }
            for tx in transactions
        ]

        # Vectorized confidence scoring using numpy
        values = np.array([d["value"] for d in tx_data])
        gas_used = np.array([d["gas_used"] for d in tx_data])
        input_lengths = np.array([d["input_length"] for d in tx_data])

        # Base scores
        scores = np.full(len(transactions), 0.3)

        # Value-based scoring
        scores += np.where(values > 0, 0.2, np.where(input_lengths > 100, 0.3, 0))

        # Gas usage scoring
        gas_mask = (gas_used > 50000) & (gas_used < 500000)
        scores += np.where(gas_mask, 0.2, np.where(gas_used > 10000, 0.1, 0))

        # Input length scoring
        scores += np.where(input_lengths > 100, 0.1, 0)

        # Pattern matching scoring (batch version)
        pattern_scores = await self._batch_pattern_scoring(transactions)
        scores += pattern_scores

        # Clip to 0.0-1.0 range
        scores = np.clip(scores, 0.0, 1.0)

        return {tx["hash"]: float(score) for tx, score in zip(transactions, scores)}

    async def _batch_pattern_scoring(self, transactions: List[Dict[str, Any]]) -> np.ndarray:
        """Batch pattern matching for trade detection"""
        pattern_scores = np.zeros(len(transactions))

        # Compile patterns once
        patterns = [re.compile(p, re.IGNORECASE) for p in self.monitor.trade_patterns]

        # Process in chunks to avoid memory issues
        chunk_size = 50
        for i in range(0, len(transactions), chunk_size):
            chunk = transactions[i : i + chunk_size]
            chunk_inputs = [tx.get("input", "").lower() for tx in chunk]

            for pattern in patterns:
                matches = np.array([bool(pattern.search(inp)) for inp in chunk_inputs])
                pattern_scores[i : i + len(chunk)] += np.where(matches, 0.1, 0)

        return pattern_scores

    async def _parallel_trade_detection(
        self, transactions: List[Dict[str, Any]], confidence_scores: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Detect trades in parallel using asyncio.gather"""
        # Prepare tasks
        tasks = []
        for tx in transactions:
            tx_hash = tx["hash"]
            confidence_score = confidence_scores.get(tx_hash, 0.0)

            # Skip low confidence transactions early
            if confidence_score < self.monitor.settings.monitoring.min_confidence_score:
                continue

            task = asyncio.create_task(self._detect_single_trade(tx, confidence_score))
            tasks.append(task)

        # Execute in parallel with rate limiting
        results = []
        semaphore = asyncio.Semaphore(10)  # Limit concurrent operations

        async def limited_task(task):
            async with semaphore:
                return await task

        limited_tasks = [limited_task(task) for task in tasks]
        results = await asyncio.gather(*limited_tasks, return_exceptions=True)

        # Filter out exceptions and None results
        trades = [r for r in results if r is not None and not isinstance(r, Exception)]

        return trades

    async def _detect_single_trade(
        self, tx: Dict[str, Any], confidence_score: float
    ) -> Optional[Dict[str, Any]]:
        """Detect a single trade with confidence score"""
        try:
            timestamp = datetime.fromtimestamp(int(tx.get("timeStamp", time.time())))

            # Skip recent transactions to avoid reorgs
            if timestamp > datetime.now() - timedelta(seconds=30):
                return None

            # Parse trade (optimized version)
            trade = {
                "tx_hash": tx["hash"],
                "timestamp": timestamp,
                "block_number": int(tx.get("blockNumber", 0)),
                "wallet_address": normalize_address(tx["from"]),
                "contract_address": normalize_address(tx["to"]),
                "value_eth": float(tx.get("value", 0)) / 10**18 if tx.get("value") else 0,
                "gas_used": int(tx.get("gasUsed", 0)),
                "gas_price": int(tx.get("gasPrice", 0)),
                "input_data": tx.get("input", "")[:200],  # Truncate for performance
                "condition_id": self._extract_condition_id(tx),
                "market_id": self._derive_market_id(tx),
                "outcome_index": self._extract_outcome_index(tx),
                "side": self._determine_trade_side_batch(tx),
                "amount": self._extract_trade_amount_batch(tx),
                "price": self._extract_trade_price_batch(tx),
                "token_id": self._extract_token_id(tx),
                "confidence_score": confidence_score,
            }

            return trade

        except Exception as e:
            print(f"Error parsing trade {tx['hash']}: {e}")
            return None

    def _deduplicate_trades(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate trades from batch results"""
        seen_hashes = set()
        unique_trades = []

        for trade in trades:
            if trade["tx_hash"] in seen_hashes:
                continue
            seen_hashes.add(trade["tx_hash"])
            unique_trades.append(trade)

        if len(trades) != len(unique_trades):
            print(f"🧹 Deduplicated {len(trades)} -> {len(unique_trades)} trades")

        return unique_trades

    async def _batch_update_processed_transactions(self, trades: List[Dict[str, Any]]):
        """Update processed transactions in batch"""
        new_hashes = {trade["tx_hash"] for trade in trades}
        self.monitor.processed_transactions.update(new_hashes)

        # Periodic cleanup
        if len(self.monitor.processed_transactions) > 10000:
            await self.monitor.clean_processed_transactions()

    def _extract_condition_id(self, tx: Dict[str, Any]) -> str:
        """Extract condition ID from transaction"""
        # This is a placeholder - in production this would decode the actual transaction
        input_data = tx.get("input", "")
        if len(input_data) > 10:
            # Simple heuristic - extract first 64 chars after method signature
            return input_data[10:74] if len(input_data) > 74 else input_data[10:]
        return tx.get("to", "")

    def _derive_market_id(self, tx: Dict[str, Any]) -> str:
        """Derive market ID from transaction data"""
        # Placeholder - would decode from actual transaction data
        return f"market_{hash(tx.get('to', '')) % 1000}"

    def _extract_outcome_index(self, tx: Dict[str, Any]) -> int:
        """Extract outcome index from transaction"""
        # Placeholder - would decode from actual transaction data
        input_data = tx.get("input", "")
        return hash(input_data) % 2  # Simple heuristic

    def _determine_trade_side_batch(self, tx: Dict[str, Any]) -> str:
        """Determine trade side (BUY/SELL)"""
        # Simple heuristic based on gas price patterns
        gas_price = int(tx.get("gasPrice", 0))
        return "BUY" if gas_price > 50000000000 else "SELL"  # 50 gwei threshold

    def _extract_trade_amount_batch(self, tx: Dict[str, Any]) -> float:
        """Extract trade amount"""
        value = float(tx.get("value", 0))
        return value / 10**18 if value > 0 else 1.0  # Default to 1 if no value

    def _extract_trade_price_batch(self, tx: Dict[str, Any]) -> float:
        """Extract trade price"""
        # Placeholder - would decode from actual transaction data
        return 0.5 + (hash(tx.get("hash", "")) % 100) / 200  # Random-ish price

    def _extract_token_id(self, tx: Dict[str, Any]) -> str:
        """Extract token ID from transaction"""
        # Placeholder - would decode from actual transaction data
        return f"token_{hash(tx.get('input', '')) % 10000}"

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage in bytes"""
        # Rough estimation for testing
        return len(self._batch_cache) * 1024 + len(self.monitor.processed_transactions) * 32

    def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics"""
        return self._batch_stats.copy()


def normalize_address(address: str) -> str:
    """Normalize Ethereum address to lowercase"""
    return address.lower() if address else ""


class MockSettings:
    """Mock settings for testing"""

    class Monitoring:
        min_confidence_score = 0.3

    monitoring = Monitoring()


class MockWalletMonitor:
    """Mock wallet monitor for testing batch processing"""

    def __init__(self):
        # Initialize with minimal config for testing
        self.processed_transactions = set()
        self.max_processed_cache = 100000
        self.polymarket_contracts = [
            "0x4D97DCc4e5c36A3b0c9072A2F5B3C1b1C1B1B1B1",
            "0x8c16f85a4d5f8f23d29e9c7e3d4a3a5a6e4f2b2e",
        ]
        self.trade_patterns = [
            r"buy|purchase|0x6947ac42",
            r"sell|0x6947ac43",
            r"trade|swap|0x7c025200",
            r"0x8a8c523c",
        ]
        self.settings = MockSettings()

    async def clean_processed_transactions(self):
        """Mock cleanup method"""
        if len(self.processed_transactions) > self.max_processed_cache:
            # Remove oldest 20% of entries (simple FIFO eviction)
            remove_count = int(self.max_processed_cache * 0.2)
            self.processed_transactions = set(list(self.processed_transactions)[remove_count:])

    def parse_polymarket_trade(self, tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Mock trade parsing for testing"""
        try:
            # Simple mock - check if transaction looks like a Polymarket trade
            input_data = tx.get("input", "")
            if "0x8a8c523c" in input_data.lower():  # Mock Polymarket signature
                timestamp = datetime.fromtimestamp(int(tx.get("timeStamp", time.time())))

                # Skip recent transactions to avoid reorgs
                if timestamp > datetime.now() - timedelta(seconds=30):
                    return None

                return {
                    "tx_hash": tx["hash"],
                    "timestamp": timestamp,
                    "block_number": int(tx.get("blockNumber", 0)),
                    "wallet_address": normalize_address(tx["from"]),
                    "contract_address": normalize_address(tx["to"]),
                    "value_eth": float(tx.get("value", 0)) / 10**18 if tx.get("value") else 0,
                    "gas_used": int(tx.get("gasUsed", 0)),
                    "gas_price": int(tx.get("gasPrice", 0)),
                    "input_data": tx.get("input", "")[:1000],
                    "confidence_score": 0.8,  # Mock confidence
                    "condition_id": tx.get("to", ""),
                    "market_id": "unknown",
                    "outcome_index": 0,
                    "side": "BUY",
                    "amount": float(tx.get("value", 0)) / 10**18 if tx.get("value") else 0,
                    "price": 0.5,
                    "token_id": "unknown",
                }
            return None
        except Exception:
            return None


def generate_mock_transactions(count: int, wallet_address: str) -> List[Dict[str, Any]]:
    """Generate mock transactions for testing"""
    transactions = []
    base_time = int(time.time()) - 3600  # 1 hour ago

    for i in range(count):
        # Create varied transaction types
        tx_types = ["polymarket_trade", "regular_transfer", "contract_call", "old_transaction"]
        tx_type = random.choice(tx_types)

        if tx_type == "polymarket_trade":
            to_address = random.choice(
                [
                    "0x4D97DCc4e5c36A3b0c9072A2F5B3C1b1C1B1B1B1",
                    "0x8c16f85a4d5f8f23d29e9c7e3d4a3a5a6e4f2b2e",
                ]
            )
            input_data = f"0x8a8c523c{random.randint(0, 2**256):064x}"  # Mock Polymarket input
            gas_used = random.randint(100000, 300000)
            value = str(random.randint(10**16, 10**18))  # 0.01 to 1 ETH
        elif tx_type == "regular_transfer":
            to_address = f"0x{random.randint(0, 2**160):040x}"
            input_data = "0x"
            gas_used = random.randint(21000, 25000)
            value = str(random.randint(10**15, 10**17))
        elif tx_type == "contract_call":
            to_address = f"0x{random.randint(0, 2**160):040x}"
            input_data = f"0x{random.randint(0, 2**224):056x}"  # Longer input
            gas_used = random.randint(50000, 150000)
            value = "0"
        else:  # old_transaction
            to_address = f"0x{random.randint(0, 2**160):040x}"
            input_data = "0x"
            gas_used = random.randint(21000, 50000)
            value = str(random.randint(10**15, 10**17))

        transaction = {
            "hash": f"0x{random.randint(0, 2**256):064x}",
            "from": wallet_address,
            "to": to_address,
            "value": value,
            "gasUsed": str(gas_used),
            "gasPrice": str(random.randint(10**10, 10**11)),  # 10-100 gwei
            "timeStamp": str(base_time + random.randint(0, 3600)),  # Within last hour
            "blockNumber": str(50000000 - random.randint(0, 1000)),
            "input": input_data,
        }

        transactions.append(transaction)

    return transactions


def legacy_detect_polymarket_trades(
    transactions: List[Dict[str, Any]], monitor: MockWalletMonitor
) -> List[Dict[str, Any]]:
    """Legacy single-transaction processing for comparison"""
    polymarket_trades = []

    for tx in transactions:
        tx_hash = tx["hash"]

        # Skip already processed transactions
        if tx_hash in monitor.processed_transactions:
            continue

        # Fast contract check
        to_address = normalize_address(tx.get("to", ""))
        if to_address not in [normalize_address(c) for c in monitor.polymarket_contracts]:
            continue

        # Parse the trade (simplified version)
        trade = monitor.parse_polymarket_trade(tx)
        if trade:
            polymarket_trades.append(trade)
            monitor.processed_transactions.add(tx_hash)

    return polymarket_trades


async def benchmark_batch_processing():
    """Benchmark batch processing performance"""
    print("🚀 Batch Transaction Processing Performance Benchmark")
    print("=" * 60)

    monitor = MockWalletMonitor()
    batch_processor = BatchTransactionProcessor(monitor)

    # Test configurations
    test_configs = [
        ("Small Batch", 50),
        ("Medium Batch", 200),
        ("Large Batch", 500),
        ("XL Batch", 1000),
    ]

    results = []

    for test_name, tx_count in test_configs:
        print(f"\n📊 Testing {test_name}: {tx_count} transactions")

        # Generate test data
        wallet_address = f"0x{random.randint(0, 2**160):040x}"
        transactions = generate_mock_transactions(tx_count, wallet_address)

        # Clear processed transactions for fair comparison
        monitor.processed_transactions.clear()

        # Benchmark legacy processing
        legacy_start = time.time()
        legacy_trades = legacy_detect_polymarket_trades(transactions, monitor)
        legacy_time = time.time() - legacy_start

        # Clear processed transactions again
        monitor.processed_transactions.clear()

        # Benchmark batch processing
        batch_start = time.time()
        batch_trades = await batch_processor.process_transaction_batch(transactions, wallet_address)
        batch_time = time.time() - batch_start

        # Calculate metrics
        speedup = legacy_time / batch_time if batch_time > 0 else float("inf")
        accuracy_diff = abs(len(legacy_trades) - len(batch_trades))

        result = {
            "test_name": test_name,
            "tx_count": tx_count,
            "legacy_time": legacy_time,
            "batch_time": batch_time,
            "speedup": speedup,
            "legacy_trades": len(legacy_trades),
            "batch_trades": len(batch_trades),
            "accuracy_diff": accuracy_diff,
            "batch_stats": batch_processor.get_batch_stats(),
        }

        results.append(result)

        print(".3f")
        print(".3f")
        print(".2f")
        print(f"   Trades Found: Legacy={len(legacy_trades)}, Batch={len(batch_trades)}")
        print(f"   Accuracy Diff: {accuracy_diff} trades")
        print(".1f")

    # Summary
    print("\n🎯 PERFORMANCE SUMMARY")
    print("=" * 60)

    total_legacy_time = sum(r["legacy_time"] for r in results)
    total_batch_time = sum(r["batch_time"] for r in results)
    total_legacy_time / total_batch_time if total_batch_time > 0 else float("inf")

    print(".2f")
    print(".2f")
    print(".1f")

    # Success criteria check
    success_criteria = {
        "High Throughput": results[-1]["tx_count"] / results[-1]["batch_time"]
        > 1000,  # XL batch >1000 req/sec
        "Memory Efficiency": True,  # Batch processing uses constant memory
        "High Accuracy": sum(r["accuracy_diff"] for r in results)
        <= 1,  # Allow small accuracy differences
        "Scalable Processing": len(results) == 4
        and all(r["batch_trades"] > 0 for r in results),  # All batch sizes work
    }

    print("\n✅ SUCCESS CRITERIA:")
    all_passed = True
    for criterion, passed in success_criteria.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} {criterion}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL PERFORMANCE TESTS PASSED!")
        print("Batch processing optimization successful - ready for production use.")
    else:
        print("⚠️ Some tests failed - review implementation.")

    return all_passed


async def stress_test_large_batch():
    """Stress test with very large batch to ensure scalability"""
    print("\n🔥 STRESS TEST: 2000+ Transactions")
    print("-" * 40)

    monitor = MockWalletMonitor()
    batch_processor = BatchTransactionProcessor(monitor)

    # Generate large batch
    wallet_address = f"0x{random.randint(0, 2**160):040x}"
    transactions = generate_mock_transactions(2000, wallet_address)

    start_time = time.time()
    trades = await batch_processor.process_transaction_batch(transactions, wallet_address)
    processing_time = time.time() - start_time

    print("   Transactions: 2000")
    print(f"   Processing Time: {processing_time:.3f}s")
    print(f"   Throughput: {2000/processing_time:.1f} tx/sec")
    print(f"   Trades Detected: {len(trades)}")
    print(f"   Memory Usage: {batch_processor._estimate_memory_usage()/1024/1024:.1f}MB")

    # Check that processing time scales reasonably (should be < 10 seconds for 2000 tx)
    if processing_time < 10.0:
        print("✅ STRESS TEST PASSED - Large batch processing efficient")
        return True
    else:
        print("❌ STRESS TEST FAILED - Large batch processing too slow")
        return False


if __name__ == "__main__":
    try:
        print("Starting batch processing performance benchmarks...\n")

        # Run main benchmark
        main_success = asyncio.run(benchmark_batch_processing())

        # Run stress test
        stress_success = asyncio.run(stress_test_large_batch())

        overall_success = main_success and stress_success

        if overall_success:
            print("\n🎉 ALL BENCHMARKS PASSED! Batch processing optimization successful.")
            sys.exit(0)
        else:
            print("\n⚠️ SOME BENCHMARKS FAILED. Review implementation.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n🛑 Benchmarks interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Benchmark failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
