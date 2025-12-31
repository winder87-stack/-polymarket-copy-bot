"""
Integration Tests for Production-Ready Copy Trading Strategy

This module contains comprehensive integration tests for the new
copy trading strategy components.

Tests:
- WalletQualityScorer integration
- RedFlagDetector integration
- DynamicPositionSizer integration
- WalletBehaviorMonitor integration
- End-to-end strategy workflow

Author: Polymarket Copy Bot Team
Date: 2025-12-27
"""

import pytest
from decimal import Decimal

from core.wallet_quality_scorer import (
    WalletQualityScorer,
    WalletQualityScore,
    WalletDomainExpertise,
    WalletRiskMetrics,
)
from core.red_flag_detector import RedFlagDetector
from core.dynamic_position_sizer import (
    DynamicPositionSizer,
)
from core.wallet_behavior_monitor import (
    WalletBehaviorMonitor,
)


@pytest.fixture
def sample_wallet_data():
    """Sample wallet data for testing"""
    return {
        "address": "0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
        "trade_count": 150,
        "win_rate": 0.68,
        "roi_7d": 8.5,
        "roi_30d": 22.0,
        "profit_factor": 1.8,
        "max_drawdown": 0.18,
        "volatility": 0.15,
        "sharpe_ratio": 1.2,
        "downside_volatility": 0.10,
        "avg_position_hold_time": 7200,  # 2 hours
        "trade_categories": [
            "politics",
            "politics",
            "politics",
            "politics",
            "economics",
        ],
        "politics_win_rate": 0.72,
        "politics_roi": 28.0,
        "created_at": "2023-01-01T00:00:00Z",
        "avg_position_size": 150,
    }


@pytest.fixture
def market_maker_wallet_data():
    """Sample market maker wallet data for testing"""
    return {
        "address": "0x0000000000000000000000000000000000000000001",
        "trade_count": 600,
        "win_rate": 0.52,
        "roi_30d": 0.5,
        "profit_factor": 1.01,
        "max_drawdown": 0.05,
        "volatility": 0.08,
        "sharpe_ratio": 0.1,
        "avg_position_hold_time": 1800,  # 30 minutes
        "trade_categories": [
            "crypto",
            "politics",
            "sports",
            "economics",
            "entertainment",
            "crypto",
        ],
        "created_at": "2023-01-01T00:00:00Z",
        "avg_position_size": 50,
    }


@pytest.fixture
def red_flag_wallet_data():
    """Sample wallet with red flags for testing"""
    return {
        "address": "0x0000000000000000000000000000000000000000002",
        "trade_count": 10,
        "win_rate": 0.95,
        "roi_30d": 5.0,
        "profit_factor": 0.8,
        "max_drawdown": 0.10,
        "volatility": 0.20,
        "sharpe_ratio": 0.5,
        "avg_position_hold_time": 3600,
        "trade_categories": [
            "politics",
            "economics",
            "crypto",
            "sports",
            "entertainment",
            "crypto",
        ],
        "created_at": "2025-12-20T00:00:00Z",  # Very recent (7 days ago)
        "max_single_trade": 1500,  # Large bet
        "avg_position_size": 100,
    }


class TestWalletQualityScorer:
    """Test suite for WalletQualityScorer"""

    @pytest.mark.asyncio
    async def test_score_good_wallet(self, sample_wallet_data):
        """Test scoring a good quality wallet"""
        scorer = WalletQualityScorer()

        score = await scorer.score_wallet(sample_wallet_data)

        assert score is not None
        assert score.is_market_maker is False
        assert len(score.red_flags) == 0
        assert score.total_score >= 7.0  # Expert or better
        assert score.quality_tier in ["Elite", "Expert", "Good"]
        assert score.domain_expertise.specialization_score >= 0.70

    @pytest.mark.asyncio
    async def test_detect_market_maker(self, market_maker_wallet_data):
        """Test market maker detection"""
        scorer = WalletQualityScorer()

        score = await scorer.score_wallet(market_maker_wallet_data)

        assert score is not None
        assert score.is_market_maker is True
        assert len(score.red_flags) == 1
        assert score.red_flags[0] == "MARKET_MAKER"
        assert score.total_score < 1.0  # Poor score

    @pytest.mark.asyncio
    async def test_domain_expertise_calculation(self, sample_wallet_data):
        """Test domain expertise calculation"""
        scorer = WalletQualityScorer()

        score = await scorer.score_wallet(sample_wallet_data)

        assert score.domain_expertise.primary_domain in ["politics", "economics"]
        assert score.domain_expertise.specialization_score >= 0.70
        assert score.domain_expertise.total_trades_in_domain >= 128  # 5/6 of trades

    @pytest.mark.asyncio
    async def test_risk_metrics_calculation(self, sample_wallet_data):
        """Test risk metrics calculation"""
        scorer = WalletQualityScorer()

        score = await scorer.score_wallet(sample_wallet_data)

        assert score.risk_metrics.max_drawdown < 0.35
        assert score.risk_metrics.volatility < 0.30
        assert score.risk_metrics.sharpe_ratio > 0.5
        assert score.risk_metrics.calmar_ratio > 0.5

    @pytest.mark.asyncio
    async def test_score_caching(self, sample_wallet_data):
        """Test that scoring is cached correctly"""
        scorer = WalletQualityScorer()

        # First call
        score1 = await scorer.score_wallet(sample_wallet_data)

        # Second call (should use cache)
        score2 = await scorer.score_wallet(sample_wallet_data)

        assert score1.wallet_address == score2.wallet_address
        assert score1.total_score == score2.total_score

    @pytest.mark.asyncio
    async def test_cleanup(self, sample_wallet_data):
        """Test cleanup functionality"""
        scorer = WalletQualityScorer()

        # Score a wallet
        await scorer.score_wallet(sample_wallet_data)

        # Cleanup
        await scorer.cleanup()

        # Check cache stats
        summary = scorer.get_score_summary()
        assert summary["total_cached_scores"] == 0


class TestRedFlagDetector:
    """Test suite for RedFlagDetector"""

    @pytest.mark.asyncio
    async def test_no_red_flags(self, sample_wallet_data):
        """Test that good wallet has no red flags"""
        detector = RedFlagDetector()

        result = await detector.check_wallet_exclusion(sample_wallet_data)

        assert result.is_excluded is False
        assert len(result.red_flags) == 0
        assert result.can_reconsider is True

    @pytest.mark.asyncio
    async def test_new_wallet_large_bet(self, red_flag_wallet_data):
        """Test detection of new wallet with large bet"""
        detector = RedFlagDetector()

        result = await detector.check_wallet_exclusion(red_flag_wallet_data)

        assert result.is_excluded is True
        assert any(
            flag.flag_type == "NEW_WALLET_LARGE_BET" for flag in result.red_flags
        )
        assert result.can_reconsider is True

    @pytest.mark.asyncio
    async def test_luck_not_skill(self, red_flag_wallet_data):
        """Test detection of luck vs skill"""
        detector = RedFlagDetector()

        result = await detector.check_wallet_exclusion(red_flag_wallet_data)

        assert any(flag.flag_type == "LUCK_NOT_SKILL" for flag in result.red_flags)
        assert any(flag.severity in ["MEDIUM", "HIGH"] for flag in result.red_flags)

    @pytest.mark.asyncio
    async def test_no_specialization(self, red_flag_wallet_data):
        """Test detection of no specialization"""
        detector = RedFlagDetector()

        result = await detector.check_wallet_exclusion(red_flag_wallet_data)

        assert any(flag.flag_type == "NO_SPECIALIZATION" for flag in result.red_flags)

    @pytest.mark.asyncio
    async def test_exclusion_caching(self, sample_wallet_data):
        """Test that exclusion results are cached"""
        detector = RedFlagDetector()

        # First call
        result1 = await detector.check_wallet_exclusion(sample_wallet_data)

        # Second call (should use cache)
        result2 = await detector.check_wallet_exclusion(sample_wallet_data)

        assert result1.is_excluded == result2.is_excluded
        assert len(result1.red_flags) == len(result2.red_flags)

    @pytest.mark.asyncio
    async def test_get_wallet_flags(self, red_flag_wallet_data):
        """Test getting wallet flags"""
        detector = RedFlagDetector()

        await detector.check_wallet_exclusion(red_flag_wallet_data)

        flags = await detector.get_wallet_flags(red_flag_wallet_data["address"])

        assert len(flags) > 0
        assert all(
            flag.wallet_address == red_flag_wallet_data["address"] for flag in flags
        )


class TestDynamicPositionSizer:
    """Test suite for DynamicPositionSizer"""

    @pytest.mark.asyncio
    async def test_elite_wallet_position_size(self):
        """Test position sizing for elite wallet"""
        sizer = DynamicPositionSizer(portfolio_value=Decimal("10000.00"))

        # Create elite wallet score
        wallet_score = WalletQualityScore(
            wallet_address="0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
            total_score=9.5,
            performance_score=9.0,
            risk_score=9.5,
            consistency_score=9.2,
            domain_expertise=WalletDomainExpertise(
                primary_domain="politics",
                specialization_score=0.90,
                domain_win_rate=0.75,
                total_trades_in_domain=180,
                domain_roi=35.0,
            ),
            risk_metrics=WalletRiskMetrics(
                volatility=0.10,
                max_drawdown=0.12,
                sharpe_ratio=1.8,
                sortino_ratio=2.0,
                calmar_ratio=2.5,
                tail_risk=0.08,
            ),
            is_market_maker=False,
            red_flags=[],
            quality_tier="Elite",
        )

        result = await sizer.calculate_position_size(
            wallet_score=wallet_score,
            original_trade_amount=Decimal("200.00"),
            current_volatility=0.15,
        )

        assert result.position_size_usdc > Decimal("100.00")  # Should be larger
        assert result.quality_multiplier >= 1.5
        assert result.max_size_hit is False
        assert result.reason == "Position sized successfully"

    @pytest.mark.asyncio
    async def test_expert_wallet_position_size(self):
        """Test position sizing for expert wallet"""
        sizer = DynamicPositionSizer(portfolio_value=Decimal("10000.00"))

        # Create expert wallet score
        wallet_score = WalletQualityScore(
            wallet_address="0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
            total_score=8.0,
            performance_score=7.5,
            risk_score=8.5,
            consistency_score=8.0,
            domain_expertise=WalletDomainExpertise(
                primary_domain="politics",
                specialization_score=0.80,
                domain_win_rate=0.70,
                total_trades_in_domain=120,
                domain_roi=25.0,
            ),
            risk_metrics=WalletRiskMetrics(
                volatility=0.15,
                max_drawdown=0.18,
                sharpe_ratio=1.2,
                sortino_ratio=1.5,
                calmar_ratio=1.8,
                tail_risk=0.12,
            ),
            is_market_maker=False,
            red_flags=[],
            quality_tier="Expert",
        )

        result = await sizer.calculate_position_size(
            wallet_score=wallet_score,
            original_trade_amount=Decimal("200.00"),
            current_volatility=0.15,
        )

        assert result.position_size_usdc > Decimal("50.00")
        assert 1.2 <= result.quality_multiplier <= 1.5
        assert result.max_size_hit is False

    @pytest.mark.asyncio
    async def test_poor_wallet_exclusion(self):
        """Test that poor wallets are excluded"""
        sizer = DynamicPositionSizer(portfolio_value=Decimal("10000.00"))

        # Create poor wallet score
        wallet_score = WalletQualityScore(
            wallet_address="0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
            total_score=3.0,
            performance_score=3.0,
            risk_score=3.0,
            consistency_score=3.0,
            domain_expertise=WalletDomainExpertise(
                primary_domain="general",
                specialization_score=0.30,
                domain_win_rate=0.50,
                total_trades_in_domain=45,
                domain_roi=5.0,
            ),
            risk_metrics=WalletRiskMetrics(
                volatility=0.40,
                max_drawdown=0.50,
                sharpe_ratio=0.2,
                sortino_ratio=0.3,
                calmar_ratio=0.1,
                tail_risk=0.50,
            ),
            is_market_maker=False,
            red_flags=[],
            quality_tier="Poor",
        )

        result = await sizer.calculate_position_size(
            wallet_score=wallet_score,
            original_trade_amount=Decimal("200.00"),
            current_volatility=0.15,
        )

        assert result.position_size_usdc == Decimal("0.00")
        assert result.quality_multiplier == 0.0
        assert "Poor quality" in result.reason

    @pytest.mark.asyncio
    async def test_volatility_adjustment(self):
        """Test position size adjustment during high volatility"""
        sizer = DynamicPositionSizer(portfolio_value=Decimal("10000.00"))

        # Create expert wallet score
        wallet_score = WalletQualityScore(
            wallet_address="0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
            total_score=8.0,
            performance_score=7.5,
            risk_score=8.5,
            consistency_score=8.0,
            domain_expertise=WalletDomainExpertise(
                primary_domain="politics",
                specialization_score=0.80,
                domain_win_rate=0.70,
                total_trades_in_domain=120,
                domain_roi=25.0,
            ),
            risk_metrics=WalletRiskMetrics(
                volatility=0.15,
                max_drawdown=0.18,
                sharpe_ratio=1.2,
                sortino_ratio=1.5,
                calmar_ratio=1.8,
                tail_risk=0.12,
            ),
            is_market_maker=False,
            red_flags=[],
            quality_tier="Expert",
        )

        # Normal volatility
        result_normal = await sizer.calculate_position_size(
            wallet_score=wallet_score,
            original_trade_amount=Decimal("200.00"),
            current_volatility=0.15,
        )

        # High volatility
        result_high = await sizer.calculate_position_size(
            wallet_score=wallet_score,
            original_trade_amount=Decimal("200.00"),
            current_volatility=0.35,  # High volatility
        )

        assert result_high.risk_adjustment < result_normal.risk_adjustment
        assert result_high.position_size_usdc < result_normal.position_size_usdc

    @pytest.mark.asyncio
    async def test_wallet_exposure_limits(self):
        """Test per-wallet exposure limits"""
        sizer = DynamicPositionSizer(portfolio_value=Decimal("10000.00"))

        # Create elite wallet score
        wallet_score = WalletQualityScore(
            wallet_address="0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
            total_score=9.5,
            performance_score=9.0,
            risk_score=9.5,
            consistency_score=9.2,
            domain_expertise=WalletDomainExpertise(
                primary_domain="politics",
                specialization_score=0.90,
                domain_win_rate=0.75,
                total_trades_in_domain=180,
                domain_roi=35.0,
            ),
            risk_metrics=WalletRiskMetrics(
                volatility=0.10,
                max_drawdown=0.12,
                sharpe_ratio=1.8,
                sortino_ratio=2.0,
                calmar_ratio=2.5,
                tail_risk=0.08,
            ),
            is_market_maker=False,
            red_flags=[],
            quality_tier="Elite",
        )

        # Elite wallets can have up to 15% exposure ($1500)
        max_exposure = Decimal("1500.00")

        # Record multiple trades approaching limit
        await sizer.record_trade(wallet_score.wallet_address, Decimal("1000.00"))
        await sizer.record_trade(wallet_score.wallet_address, Decimal("400.00"))

        # Next trade should be limited
        result = await sizer.calculate_position_size(
            wallet_score=wallet_score,
            original_trade_amount=Decimal("200.00"),
            current_volatility=0.15,
        )

        # Remaining exposure should be less than requested
        remaining_exposure = max_exposure - Decimal("1400.00")
        assert result.position_size_usdc <= remaining_exposure


class TestWalletBehaviorMonitor:
    """Test suite for WalletBehaviorMonitor"""

    @pytest.mark.asyncio
    async def test_win_rate_change_detection(self):
        """Test detection of win rate changes"""
        monitor = WalletBehaviorMonitor()

        wallet_address = "0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9"

        # Baseline metrics
        baseline_metrics = {
            "win_rate": 0.70,
            "avg_position_size": 150,
            "trade_categories": ["politics", "economics"],
            "volatility": 0.15,
        }

        # Monitor baseline
        changes = await monitor.monitor_wallet(wallet_address, baseline_metrics)
        assert len(changes) == 0  # No changes on first run

        # Degraded metrics (20% win rate drop)
        degraded_metrics = {
            "win_rate": 0.50,
            "avg_position_size": 150,
            "trade_categories": ["politics", "economics"],
            "volatility": 0.15,
            "new_trades": 10,
            "new_profit": 50,
            "new_loss": 100,
            "previous_score": 8.0,
            "total_score": 6.0,
        }

        # Monitor degradation
        changes = await monitor.monitor_wallet(wallet_address, degraded_metrics)

        assert len(changes) >= 1
        assert any(change.change_type == "WIN_RATE_DROP" for change in changes)
        assert any(change.severity in ["HIGH", "CRITICAL"] for change in changes)

    @pytest.mark.asyncio
    async def test_position_size_increase_detection(self):
        """Test detection of position size increases"""
        monitor = WalletBehaviorMonitor()

        wallet_address = "0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9"

        # Baseline metrics
        baseline_metrics = {
            "win_rate": 0.70,
            "avg_position_size": 150,
            "trade_categories": ["politics", "economics"],
            "volatility": 0.15,
        }

        await monitor.monitor_wallet(wallet_address, baseline_metrics)

        # Increased position size (2.5x)
        increased_metrics = {
            "win_rate": 0.70,
            "avg_position_size": 375,  # 2.5x increase
            "trade_categories": ["politics", "economics"],
            "volatility": 0.15,
            "new_trades": 5,
            "new_profit": 100,
            "new_loss": 50,
            "previous_score": 8.0,
            "total_score": 8.0,
        }

        changes = await monitor.monitor_wallet(wallet_address, increased_metrics)

        assert any(change.change_type == "RISK_INCREASE" for change in changes)
        assert any(change.severity in ["HIGH", "CRITICAL"] for change in changes)

    @pytest.mark.asyncio
    async def test_category_shift_detection(self):
        """Test detection of category shifts"""
        monitor = WalletBehaviorMonitor()

        wallet_address = "0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9"

        # Baseline metrics (politics and economics only)
        baseline_metrics = {
            "win_rate": 0.70,
            "avg_position_size": 150,
            "trade_categories": [
                "politics",
                "politics",
                "economics",
                "politics",
                "economics",
            ],
            "volatility": 0.15,
        }

        await monitor.monitor_wallet(wallet_address, baseline_metrics)

        # New categories added
        shifted_metrics = {
            "win_rate": 0.70,
            "avg_position_size": 150,
            "trade_categories": [
                "politics",
                "politics",
                "economics",
                "politics",
                "economics",
                "crypto",
                "sports",
            ],
            "volatility": 0.15,
            "new_trades": 5,
            "new_profit": 80,
            "new_loss": 40,
            "previous_score": 8.0,
            "total_score": 8.0,
        }

        changes = await monitor.monitor_wallet(wallet_address, shifted_metrics)

        assert any(change.change_type == "CATEGORY_SHIFT" for change in changes)

    @pytest.mark.asyncio
    async def test_get_wallet_summary(self):
        """Test getting wallet summary"""
        monitor = WalletBehaviorMonitor()

        wallet_address = "0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9"

        # Monitor wallet with some trades
        metrics = {
            "win_rate": 0.70,
            "avg_position_size": 150,
            "trade_categories": ["politics", "economics"],
            "volatility": 0.15,
            "trade_count": 20,
            "total_profit": 500,
            "total_loss": 200,
            "sharpe_ratio": 1.2,
            "new_trades": 10,
            "new_profit": 250,
            "new_loss": 100,
            "previous_score": 8.0,
            "total_score": 8.0,
        }

        await monitor.monitor_wallet(wallet_address, metrics)

        # Get summary
        summary = await monitor.get_wallet_summary(wallet_address)

        assert summary is not None
        assert summary["wallet_address"] == wallet_address
        assert summary["trade_count"] >= 20
        assert summary["win_rate"] == 0.70
        assert summary["categories_traded"] == ["politics", "economics"]

    @pytest.mark.asyncio
    async def test_monitor_summary(self):
        """Test getting monitor summary"""
        monitor = WalletBehaviorMonitor()

        # Monitor multiple wallets
        wallet_addresses = [
            "0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
            "0x8a5d7f382763a2a954e85c8d89a0e3f4a9c5f3b8",
            "0x9b6c4e2f8a7d1b5c3e9f2a8d7c6b4e1f3a9d2c7",
        ]

        for address in wallet_addresses:
            metrics = {
                "win_rate": 0.70,
                "avg_position_size": 150,
                "trade_categories": ["politics", "economics"],
                "volatility": 0.15,
                "trade_count": 20,
                "total_profit": 500,
                "total_loss": 200,
                "sharpe_ratio": 1.2,
                "new_trades": 10,
                "new_profit": 250,
                "new_loss": 100,
                "previous_score": 8.0,
                "total_score": 8.0,
            }
            await monitor.monitor_wallet(address, metrics)

        # Get monitor summary
        summary = await monitor.get_monitor_summary()

        assert summary["total_monitored_wallets"] == len(wallet_addresses)
        assert summary["total_trades"] >= len(wallet_addresses) * 10


class TestEndToEndWorkflow:
    """End-to-end tests for the complete workflow"""

    @pytest.mark.asyncio
    async def test_complete_workflow(self, sample_wallet_data):
        """Test complete workflow from data to position sizing"""
        # Initialize components
        scorer = WalletQualityScorer()
        detector = RedFlagDetector()
        sizer = DynamicPositionSizer(portfolio_value=Decimal("10000.00"))
        monitor = WalletBehaviorMonitor()

        # Step 1: Score wallet
        quality_score = await scorer.score_wallet(sample_wallet_data)

        assert quality_score is not None
        assert quality_score.quality_tier in ["Elite", "Expert", "Good"]

        # Step 2: Check for red flags
        exclusion_result = await detector.check_wallet_exclusion(sample_wallet_data)

        assert exclusion_result.is_excluded is False

        # Step 3: Calculate position size
        position_result = await sizer.calculate_position_size(
            wallet_score=quality_score,
            original_trade_amount=Decimal("200.00"),
            current_volatility=0.15,
        )

        assert position_result.position_size_usdc > Decimal("0.00")
        assert position_result.shares > 0

        # Step 4: Record trade in sizer
        recorded = await sizer.record_trade(
            quality_score.wallet_address,
            position_result.position_size_usdc,
        )

        assert recorded is True

        # Step 5: Monitor behavior
        metrics = {
            "win_rate": 0.70,
            "avg_position_size": float(position_result.position_size_usdc),
            "trade_categories": sample_wallet_data["trade_categories"],
            "volatility": 0.15,
            "new_trades": 1,
            "new_profit": 50,
            "new_loss": 20,
            "previous_score": quality_score.total_score,
            "total_score": quality_score.total_score,
        }

        behavior_changes = await monitor.monitor_wallet(
            quality_score.wallet_address, metrics
        )

        # Should not trigger alerts on first monitoring
        assert len(behavior_changes) == 0

        # Cleanup
        await scorer.cleanup()
        await detector.cleanup()
        await sizer.cleanup()
        await monitor.cleanup()

    @pytest.mark.asyncio
    async def test_market_maker_workflow(self, market_maker_wallet_data):
        """Test workflow with market maker (should be excluded)"""
        scorer = WalletQualityScorer()
        detector = RedFlagDetector()
        sizer = DynamicPositionSizer(portfolio_value=Decimal("10000.00"))

        # Score wallet
        quality_score = await scorer.score_wallet(market_maker_wallet_data)

        assert quality_score.is_market_maker is True

        # Check exclusion
        exclusion_result = await detector.check_wallet_exclusion(
            market_maker_wallet_data
        )

        assert exclusion_result.is_excluded is True

        # Calculate position (should be zero)
        position_result = await sizer.calculate_position_size(
            wallet_score=quality_score,
            original_trade_amount=Decimal("200.00"),
            current_volatility=0.15,
        )

        assert position_result.position_size_usdc == Decimal("0.00")
        assert "Poor quality" in position_result.reason

        # Cleanup
        await scorer.cleanup()
        await detector.cleanup()
        await sizer.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
