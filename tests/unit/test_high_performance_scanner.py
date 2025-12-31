"""
Unit Tests for High-Performance Wallet Scanner
===============================================

Comprehensive test suite for HighPerformanceWalletScanner covering:
- Three-stage filtering pipeline performance
- Risk framework PILLAR implementation
- Memory management and bounded cache behavior
- Edge cases and error handling
- Performance benchmarks and regression prevention

Run with:
    pytest tests/unit/test_high_performance_scanner.py -v
    pytest tests/unit/test_high_performance_scanner.py -v --benchmark-only
"""

import asyncio
import time
from typing import Dict
from unittest.mock import AsyncMock, patch

import pytest

# Note: Tests require full environment setup with all dependencies
# Run with: pytest tests/unit/test_high_performance_scanner.py -v

try:
    from config.scanner_config import ScannerConfig
    from scanners.high_performance_wallet_scanner import (
        HighPerformanceWalletScanner,
        RiskFrameworkConfig,
        create_high_performance_scanner,
    )

    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    print(f"⚠️  Test dependencies not available: {e}")
    print(
        "   Run tests with full environment: pytest tests/unit/test_high_performance_scanner.py -v"
    )


# ============================================================================
# Fixtures
# ============================================================================

# Skip all tests if dependencies aren't available
pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason="Test dependencies not available - requires full environment setup",
)


@pytest.fixture
def scanner_config() -> ScannerConfig:
    """Get scanner configuration"""
    return ScannerConfig.from_env()


@pytest.fixture
def risk_config() -> RiskFrameworkConfig:
    """Get risk framework configuration"""
    return RiskFrameworkConfig()


@pytest.fixture
def mock_wallet_data() -> Dict:
    """Mock wallet data for testing"""
    return {
        "address": "0x1234567890abcdef1234567890abcdef12345678",
        "trade_count": 150,
        "wallet_age_days": 60,
        "trades": [
            {
                "category": "Politics",
                "amount": 100.0,
                "pnl": 10.0,
                "timestamp": 1234567890,
            },
            {
                "category": "Politics",
                "amount": 150.0,
                "pnl": 15.0,
                "timestamp": 1234567900,
            },
            {
                "category": "Politics",
                "amount": 200.0,
                "pnl": -10.0,
                "timestamp": 1234567910,
            },
            {
                "category": "Politics",
                "amount": 120.0,  # Not chasing after loss (1.2x vs 1.5x)
                "pnl": 5.0,
                "timestamp": 1234567920,
            },
        ],
        "avg_hold_time_seconds": 3600,
        "win_rate": 0.65,
        "max_drawdown": 0.15,
        "roi_30d": 25.0,
        "roi_7d": 8.0,
        "profit_factor": 1.8,
    }


@pytest.fixture
def mock_martingale_wallet_data() -> Dict:
    """Mock wallet with Martingale (loss chasing) behavior"""
    return {
        "address": "0x9876543210fedcba9876543210fedcba98765432",
        "trade_count": 50,
        "wallet_age_days": 30,
        "trades": [
            {
                "category": "Sports",
                "amount": 100.0,
                "pnl": 10.0,
                "timestamp": 1234567890,
            },
            {
                "category": "Sports",
                "amount": 110.0,
                "pnl": -15.0,  # Loss
                "timestamp": 1234567900,
            },
            {
                "category": "Sports",
                "amount": 200.0,  # Chasing: 1.8x position after loss
                "pnl": -30.0,  # Another loss
                "timestamp": 1234567910,
            },
            {
                "category": "Sports",
                "amount": 400.0,  # Chasing again: 2x position after loss
                "pnl": -50.0,  # Another loss
                "timestamp": 1234567920,
            },
            {
                "category": "Sports",
                "amount": 800.0,  # Chasing again: 2x position after loss
                "pnl": 100.0,
                "timestamp": 1234567930,
            },
        ],
        "avg_hold_time_seconds": 3600,
        "win_rate": 0.40,  # Low win rate from Martingale
        "max_drawdown": 0.45,  # High drawdown
    }


@pytest.fixture
def mock_market_maker_data() -> Dict:
    """Mock market maker wallet"""
    return {
        "address": "0xaabbccddeeff00112233445566778899001122334",
        "trade_count": 800,  # High trade count
        "wallet_age_days": 90,
        "trades": [
            {
                "category": "Finance",
                "amount": 50.0,
                "pnl": 1.0,
                "timestamp": 1234567890,
            },
            {
                "category": "Finance",
                "amount": 50.0,
                "pnl": -1.0,
                "timestamp": 1234567900,
            },
            {
                "category": "Finance",
                "amount": 50.0,
                "pnl": 1.0,
                "timestamp": 1234567910,
            },
            {
                "category": "Finance",
                "amount": 50.0,
                "pnl": -1.0,
                "timestamp": 1234567920,
            },
        ],
        "avg_hold_time_seconds": 7200,  # <4 hours
        "win_rate": 0.50,  # 50% +/- 2%
        "profit_per_trade": 0.01,  # <2%
    }


@pytest.fixture
def mock_generalist_wallet_data() -> Dict:
    """Mock generalist wallet (diversified across categories)"""
    return {
        "address": "0xfedcba0987654321fedcba0987654321fedcba098",
        "trade_count": 100,
        "wallet_age_days": 45,
        "trades": [
            {
                "category": "Politics",
                "amount": 100.0,
                "pnl": 10.0,
                "timestamp": 1234567890,
            },
            {
                "category": "Sports",
                "amount": 100.0,
                "pnl": 10.0,
                "timestamp": 1234567900,
            },
            {
                "category": "Finance",
                "amount": 100.0,
                "pnl": 10.0,
                "timestamp": 1234567910,
            },
            {
                "category": "Crypto",
                "amount": 100.0,
                "pnl": 10.0,
                "timestamp": 1234567920,
            },
            {
                "category": "Entertainment",
                "amount": 100.0,
                "pnl": 10.0,
                "timestamp": 1234567930,
            },
            {
                "category": "Technology",
                "amount": 100.0,
                "pnl": 10.0,
                "timestamp": 1234567940,
            },
        ],
        "avg_hold_time_seconds": 3600,
        "win_rate": 0.60,
    }


@pytest.fixture
async def scanner(scanner_config, risk_config) -> HighPerformanceWalletScanner:
    """Create scanner instance for testing"""
    scanner = create_high_performance_scanner(
        config=scanner_config,
        risk_config=risk_config,
    )
    async with scanner:
        yield scanner


# ============================================================================
# Stage 1 Tests: Basic Validation (10ms target)
# ============================================================================


class TestStage1BasicValidation:
    """Test Stage 1: Basic validation and generalist rejection"""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Dependencies not available")
    async def test_stage1_passes_valid_wallet(self, scanner, mock_wallet_data):
        """Test that Stage 1 passes a valid wallet"""
        address = mock_wallet_data["address"]

        result = await scanner._stage1_basic_validation(address, mock_wallet_data)

        assert result["pass"] is True
        assert len(result["reasons"]) == 0

    @pytest.mark.asyncio
    async def test_stage1_rejects_generalist(
        self, scanner, mock_generalist_wallet_data
    ):
        """Test that Stage 1 rejects generalist wallets"""
        address = mock_generalist_wallet_data["address"]

        result = await scanner._stage1_basic_validation(
            address, mock_generalist_wallet_data
        )

        assert result["pass"] is False
        assert any("Generalist" in reason for reason in result["reasons"])

    @pytest.mark.asyncio
    async def test_stage1_rejects_insufficient_trades(self, scanner):
        """Test that Stage 1 rejects wallets with insufficient trades"""
        wallet_data = {
            "address": "0x1111111111111111111111111111111111111111",
            "trade_count": 10,  # Below minimum
            "wallet_age_days": 60,
            "trades": [],
        }

        result = await scanner._stage1_basic_validation(
            wallet_data["address"], wallet_data
        )

        assert result["pass"] is False
        assert any("Insufficient trades" in reason for reason in result["reasons"])

    @pytest.mark.asyncio
    async def test_stage1_rejects_new_wallet(self, scanner):
        """Test that Stage 1 rejects new wallets"""
        wallet_data = {
            "address": "0x2222222222222222222222222222222222222222",
            "trade_count": 100,
            "wallet_age_days": 5,  # Too new
            "trades": [],
        }

        result = await scanner._stage1_basic_validation(
            wallet_data["address"], wallet_data
        )

        assert result["pass"] is False
        assert any("too new" in reason for reason in result["reasons"])

    @pytest.mark.asyncio
    async def test_specialization_score_calculation(self, scanner, mock_wallet_data):
        """Test specialization score calculation with O(n) efficiency"""
        start_time = time.time()

        score, top_category = scanner._calculate_specialization_score_fast(
            mock_wallet_data["trades"]
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Should be highly specialized in "Politics"
        assert score >= 0.5
        assert top_category == "Politics"

        # Should be fast (<1ms for 4 trades)
        assert elapsed_ms < 10.0, (
            f"Specialization calculation took {elapsed_ms:.2f}ms (expected <10ms)"
        )

    @pytest.mark.asyncio
    async def test_generalist_detection(self, scanner, mock_generalist_wallet_data):
        """Test generalist wallet detection"""
        score, top_category = scanner._calculate_specialization_score_fast(
            mock_generalist_wallet_data["trades"]
        )

        # Generalist should have low specialization score
        assert score < 0.3
        assert len(mock_generalist_wallet_data["trades"]) >= 5


# ============================================================================
# Stage 2 Tests: Risk Behavior Analysis (50ms target)
# ============================================================================


class TestStage2RiskAnalysis:
    """Test Stage 2: Risk behavior analysis and market maker detection"""

    @pytest.mark.asyncio
    async def test_stage2_passes_valid_wallet(self, scanner, mock_wallet_data):
        """Test that Stage 2 passes a valid wallet"""
        address = mock_wallet_data["address"]

        result = await scanner._stage2_risk_analysis(address, mock_wallet_data)

        assert result["pass"] is True
        assert result["risk_score"] >= 0.5
        assert result["confidence_score"] >= 0.5

    @pytest.mark.asyncio
    async def test_stage2_rejects_martingale(
        self, scanner, mock_martingale_wallet_data
    ):
        """Test that Stage 2 detects Martingale behavior"""
        address = mock_martingale_wallet_data["address"]

        result = await scanner._stage2_risk_analysis(
            address, mock_martingale_wallet_data
        )

        assert result["pass"] is False
        assert any("Martingale" in reason for reason in result["reasons"])

    @pytest.mark.asyncio
    async def test_stage2_rejects_market_maker(self, scanner, mock_market_maker_data):
        """Test that Stage 2 detects market makers"""
        address = mock_market_maker_data["address"]

        result = await scanner._stage2_risk_analysis(address, mock_market_maker_data)

        assert result["pass"] is False
        assert any("Market maker" in reason for reason in result["reasons"])

    @pytest.mark.asyncio
    async def test_martingale_detection(self, scanner, mock_martingale_wallet_data):
        """Test Martingale (loss chasing) detection"""
        is_martingale, chasing_count = scanner._analyze_post_loss_behavior_fast(
            mock_martingale_wallet_data["trades"]
        )

        # Should detect Martingale behavior
        assert is_martingale is True
        assert chasing_count >= 2  # At least 2 instances of chasing

    @pytest.mark.asyncio
    async def test_martingale_not_detected_in_safe_wallet(
        self, scanner, mock_wallet_data
    ):
        """Test that safe wallet is not flagged as Martingale"""
        is_martingale, chasing_count = scanner._analyze_post_loss_behavior_fast(
            mock_wallet_data["trades"]
        )

        # Should NOT detect Martingale behavior
        assert is_martingale is False
        assert chasing_count == 0

    @pytest.mark.asyncio
    async def test_market_maker_detection(self, scanner, mock_market_maker_data):
        """Test market maker detection"""
        is_mm = scanner._detect_market_maker_fast(mock_market_maker_data)

        # Should detect market maker pattern
        assert is_mm is True

    @pytest.mark.asyncio
    async def test_market_maker_not_detected_in_normal_wallet(
        self, scanner, mock_wallet_data
    ):
        """Test that normal wallet is not flagged as market maker"""
        is_mm = scanner._detect_market_maker_fast(mock_wallet_data)

        # Should NOT detect market maker pattern
        assert is_mm is False


# ============================================================================
# Stage 3 Tests: Full Analysis (200ms target)
# ============================================================================


class TestStage3FullAnalysis:
    """Test Stage 3: Full analysis and scoring"""

    @pytest.mark.asyncio
    async def test_stage3_target_wallet(self, scanner, mock_wallet_data):
        """Test that Stage 3 classifies TARGET wallet correctly"""
        address = mock_wallet_data["address"]
        stage2_result = {
            "pass": True,
            "partial_score": 0.8,
            "specialization_score": 0.8,
            "risk_score": 0.9,
            "confidence_score": 0.7,
        }

        with patch.object(
            scanner, "_fetch_performance_data", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_wallet_data

            result = await scanner._stage3_full_analysis(
                address, mock_wallet_data, stage2_result
            )

        assert result["pass"] is True
        assert result["classification"] == "TARGET"
        assert result["score"] >= scanner.risk_config.TARGET_WALLET_SCORE

    @pytest.mark.asyncio
    async def test_confidence_score_calculation(self, scanner, mock_wallet_data):
        """Test confidence score calculation"""
        score = scanner._calculate_confidence_score(mock_wallet_data, mock_wallet_data)

        # Should have reasonable confidence (60+ trades, 60+ days old)
        assert 0.5 <= score <= 1.0


# ============================================================================
# Integration Tests: Full Pipeline
# ============================================================================


class TestFullPipeline:
    """Test full three-stage filtering pipeline"""

    @pytest.mark.asyncio
    async def test_target_wallet_passes_all_stages(self, scanner, mock_wallet_data):
        """Test that target wallet passes all three stages"""
        address = mock_wallet_data["address"]

        with patch.object(
            scanner, "_fetch_wallet_data", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_wallet_data

            with patch.object(
                scanner, "_fetch_performance_data", new_callable=AsyncMock
            ) as mock_perf:
                mock_perf.return_value = mock_wallet_data

                result = await scanner._analyze_wallet_pipeline(address)

        assert result is not None
        assert result.classification == "TARGET"
        assert result.scan_stage_completed == 3
        assert result.total_score >= scanner.risk_config.TARGET_WALLET_SCORE

    @pytest.mark.asyncio
    async def test_generalist_rejected_stage1(
        self, scanner, mock_generalist_wallet_data
    ):
        """Test that generalist wallet is rejected in Stage 1"""
        address = mock_generalist_wallet_data["address"]

        with patch.object(
            scanner, "_fetch_wallet_data", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_generalist_wallet_data

            result = await scanner._analyze_wallet_pipeline(address)

        assert result is not None
        assert result.classification == "REJECT"
        assert result.scan_stage_completed == 1
        assert "Generalist" in " ".join(result.rejection_reasons)

    @pytest.mark.asyncio
    async def test_martingale_rejected_stage2(
        self, scanner, mock_martingale_wallet_data
    ):
        """Test that Martingale wallet is rejected in Stage 2"""
        address = mock_martingale_wallet_data["address"]

        with patch.object(
            scanner, "_fetch_wallet_data", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_martingale_wallet_data

            result = await scanner._analyze_wallet_pipeline(address)

        assert result is not None
        assert result.classification == "REJECT"
        assert result.scan_stage_completed == 2
        assert "Martingale" in " ".join(result.rejection_reasons)


# ============================================================================
# Performance Benchmark Tests
# ============================================================================


class TestPerformanceBenchmarks:
    """Test performance benchmarks and regression prevention"""

    @pytest.mark.asyncio
    async def test_stage1_performance_under_10ms(self, scanner, mock_wallet_data):
        """Test that Stage 1 processes wallet in <10ms"""
        address = mock_wallet_data["address"]

        start_time = time.time()
        await scanner._stage1_basic_validation(address, mock_wallet_data)
        elapsed_ms = (time.time() - start_time) * 1000

        assert elapsed_ms < 10.0, f"Stage 1 took {elapsed_ms:.2f}ms (expected <10ms)"

    @pytest.mark.asyncio
    async def test_stage2_performance_under_50ms(self, scanner, mock_wallet_data):
        """Test that Stage 2 processes wallet in <50ms"""
        address = mock_wallet_data["address"]

        start_time = time.time()
        await scanner._stage2_risk_analysis(address, mock_wallet_data)
        elapsed_ms = (time.time() - start_time) * 1000

        assert elapsed_ms < 50.0, f"Stage 2 took {elapsed_ms:.2f}ms (expected <50ms)"

    @pytest.mark.asyncio
    async def test_stage3_performance_under_200ms(self, scanner, mock_wallet_data):
        """Test that Stage 3 processes wallet in <200ms"""
        address = mock_wallet_data["address"]
        stage2_result = {
            "pass": True,
            "partial_score": 0.8,
            "specialization_score": 0.8,
            "risk_score": 0.9,
            "confidence_score": 0.7,
        }

        with patch.object(
            scanner, "_fetch_performance_data", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_wallet_data

            start_time = time.time()
            await scanner._stage3_full_analysis(
                address, mock_wallet_data, stage2_result
            )
            elapsed_ms = (time.time() - start_time) * 1000

        assert elapsed_ms < 200.0, f"Stage 3 took {elapsed_ms:.2f}ms (expected <200ms)"

    @pytest.mark.asyncio
    async def test_batch_processing_performance(self, scanner):
        """Test batch processing performance (100 wallets <2.5s)"""
        # Create 100 test wallets
        wallets = [
            {
                "address": f"0x{''.join(['0'] * 40)}",
                "trade_count": 100 + i,
                "wallet_age_days": 60,
                "trades": [
                    {"category": "Politics", "amount": 100.0, "pnl": 10.0}
                    for _ in range(10)
                ],
            }
            for i in range(100)
        ]

        # Mock data fetching to return same data for all wallets
        with patch.object(
            scanner, "_fetch_wallet_data", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = wallets[0]

            with patch.object(
                scanner, "_fetch_performance_data", new_callable=AsyncMock
            ) as mock_perf:
                mock_perf.return_value = wallets[0]

                start_time = time.time()
                batch_results = await scanner._process_wallet_batch(
                    [w["address"] for w in wallets]
                )
                elapsed_seconds = time.time() - start_time

        # Should process 100 wallets in <2.5 seconds (25ms average)
        assert elapsed_seconds < 2.5, (
            f"Batch processing took {elapsed_seconds:.2f}s (expected <2.5s)"
        )
        assert len(batch_results) == 100

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self, scanner, mock_wallet_data):
        """Test that cache hits significantly improve performance"""
        address = mock_wallet_data["address"]

        # First call - cache miss
        with patch.object(
            scanner, "_fetch_wallet_data", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_wallet_data

            start_time = time.time()
            result1 = await scanner.scan_single_wallet(address)
            time_miss = (time.time() - start_time) * 1000

        # Second call - cache hit
        start_time = time.time()
        result2 = await scanner.scan_single_wallet(address, force_refresh=False)
        time_hit = (time.time() - start_time) * 1000

        # Cache hit should be significantly faster (no API calls)
        assert time_hit < time_miss * 0.5, (
            f"Cache hit took {time_hit:.2f}ms vs {time_miss:.2f}ms miss"
        )


# ============================================================================
# Memory Management Tests
# ============================================================================


class TestMemoryManagement:
    """Test memory management and bounded cache behavior"""

    @pytest.mark.asyncio
    async def test_cache_size_limit(self, scanner):
        """Test that cache respects max size limit"""
        cache = scanner.api_cache

        # Add more entries than max_size
        max_size = cache.max_size
        for i in range(max_size * 2):
            cache.set(f"key_{i}", f"value_{i}")

        # Cache should not exceed max_size
        assert len(cache._cache) <= max_size

    @pytest.mark.asyncio
    async def test_cache_ttl_cleanup(self, scanner):
        """Test that cache respects TTL and expires entries"""
        cache = scanner.analysis_cache

        # Add entry
        cache.set("test_key", "test_value")

        # Verify entry exists
        assert cache.get("test_key") == "test_value"

        # Modify TTL to 1 second for testing
        cache.ttl_seconds = 1

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Entry should be expired
        assert cache.get("test_key") is None

    @pytest.mark.asyncio
    async def test_memory_cleanup_between_batches(self, scanner):
        """Test that memory cleanup runs between batches"""
        # This test verifies cleanup doesn't crash
        await scanner._cleanup_memory()

        # Cache stats should be accessible
        stats = scanner.get_cache_stats()
        assert "api_cache" in stats
        assert "analysis_cache" in stats


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_empty_trade_list(self, scanner):
        """Test handling of empty trade list"""
        score, top_category = scanner._calculate_specialization_score_fast([])

        assert score == 0.0
        assert top_category == "NO_DATA"

    @pytest.mark.asyncio
    async def test_zero_total_volume(self, scanner):
        """Test handling of zero total volume"""
        trades = [{"category": "Politics", "amount": 0.0, "pnl": 0.0}]
        score, top_category = scanner._calculate_specialization_score_fast(trades)

        assert score == 0.0
        assert top_category == "NO_DATA"

    @pytest.mark.asyncio
    async def test_invalid_wallet_address(self, scanner):
        """Test handling of invalid wallet address"""
        wallet_data = {
            "address": "invalid",
            "trade_count": 100,
            "wallet_age_days": 60,
            "trades": [],
        }

        result = await scanner._stage1_basic_validation(
            wallet_data["address"], wallet_data
        )

        assert result["pass"] is False
        assert any("Invalid" in reason for reason in result["reasons"])

    @pytest.mark.asyncio
    async def test_missing_pnl_data(self, scanner):
        """Test handling of missing PnL data in trades"""
        trades = [
            {"category": "Politics", "amount": 100.0},  # Missing pnl
            {"category": "Politics", "amount": 150.0},
        ]

        is_martingale, count = scanner._analyze_post_loss_behavior_fast(trades)

        # Should handle gracefully without crashing
        assert is_martingale is False
        assert count == 0

    @pytest.mark.asyncio
    async def test_api_failure_handling(self, scanner):
        """Test graceful handling of API failures"""
        with patch.object(
            scanner, "_fetch_wallet_data", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = None

            result = await scanner.scan_single_wallet("0x1234...5678")

        # Should return None on API failure
        assert result is None

    @pytest.mark.asyncio
    async def test_api_exception_handling(self, scanner):
        """Test graceful handling of API exceptions"""
        with patch.object(
            scanner, "_fetch_wallet_data", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("API error")

            result = await scanner.scan_single_wallet("0x1234...5678")

        # Should return None on exception
        assert result is None
        # Error counter should be incremented
        assert scanner.metrics.errors > 0


# ============================================================================
# Statistics and Reporting Tests
# ============================================================================


class TestStatisticsAndReporting:
    """Test statistics tracking and reporting"""

    @pytest.mark.asyncio
    async def test_scan_statistics_tracking(self, scanner):
        """Test that scan statistics are tracked correctly"""
        wallets = [f"0x{''.join(['0'] * 40)}" for _ in range(50)]

        mock_data = {
            "address": wallets[0],
            "trade_count": 100,
            "wallet_age_days": 60,
            "trades": [{"category": "Politics", "amount": 100.0, "pnl": 10.0}],
        }

        with patch.object(
            scanner, "_fetch_wallet_data", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_data

            with patch.object(
                scanner, "_fetch_performance_data", new_callable=AsyncMock
            ) as mock_perf:
                mock_perf.return_value = mock_data

                results, stats = await scanner.scan_wallet_batch(wallets, batch_size=10)

        # Verify statistics
        assert stats.total_wallets == 50
        assert stats.avg_time_per_wallet_ms > 0
        assert stats.total_time_seconds > 0

    @pytest.mark.asyncio
    async def test_performance_summary(self, scanner):
        """Test performance summary generation"""
        summary = scanner.get_performance_summary()

        # Should contain all expected sections
        assert "Scan Statistics" in summary
        assert "Processing Times" in summary
        assert "API Calls" in summary
        assert "Memory" in summary

    @pytest.mark.asyncio
    async def test_cache_stats(self, scanner):
        """Test cache statistics"""
        stats = scanner.get_cache_stats()

        # Should have both cache stats
        assert "api_cache" in stats
        assert "analysis_cache" in stats

        # Each cache should have expected keys
        for cache_name in ["api_cache", "analysis_cache"]:
            cache_stats = stats[cache_name]
            assert "size" in cache_stats
            assert "hit_ratio" in cache_stats
            assert "estimated_memory_mb" in cache_stats


# ============================================================================
# Risk Framework Configuration Tests
# ============================================================================


class TestRiskFrameworkConfig:
    """Test risk framework configuration"""

    def test_default_config_values(self):
        """Test that default risk configuration values are correct"""
        config = RiskFrameworkConfig()

        # Verify all default values
        assert config.MIN_SPECIALIZATION_SCORE == 0.50
        assert config.MAX_CATEGORIES == 5
        assert config.CATEGORY_WEIGHT == 0.35
        assert config.MARTINGALE_THRESHOLD == 1.5
        assert config.MARTINGALE_LIMIT == 0.20
        assert config.BEHAVIOR_WEIGHT == 0.40
        assert config.STRUCTURE_WEIGHT == 0.25
        assert config.TARGET_WALLET_SCORE == 0.70
        assert config.WATCHLIST_SCORE == 0.50

    def test_weight_sum_is_one(self):
        """Test that risk pillar weights sum to 1.0"""
        config = RiskFrameworkConfig()

        total_weight = (
            config.CATEGORY_WEIGHT + config.BEHAVIOR_WEIGHT + config.STRUCTURE_WEIGHT
        )

        assert abs(total_weight - 1.0) < 0.01, (
            f"Weights sum to {total_weight} (expected 1.0)"
        )


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestFactoryFunctions:
    """Test factory functions"""

    def test_create_high_performance_scanner(self):
        """Test factory function creates scanner correctly"""
        scanner = create_high_performance_scanner()

        assert isinstance(scanner, HighPerformanceWalletScanner)
        assert scanner.config is not None
        assert scanner.risk_config is not None


# ============================================================================
# Integration with Existing System
# ============================================================================


class TestSystemIntegration:
    """Test integration with existing system components"""

    @pytest.mark.asyncio
    async def test_context_manager(self, scanner_config, risk_config):
        """Test async context manager lifecycle"""
        scanner = create_high_performance_scanner(scanner_config, risk_config)

        # Enter context
        async with scanner:
            # Background tasks should be running
            assert scanner.api_cache._cleanup_task is not None
            assert scanner.analysis_cache._cleanup_task is not None

        # Exit context - background tasks should be stopped
        assert scanner.api_cache._cleanup_task is None
        assert scanner.analysis_cache._cleanup_task is None


# ============================================================================
# Main Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
