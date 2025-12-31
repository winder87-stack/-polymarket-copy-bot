#!/usr/bin/env python3
"""
Wallet Quality Analysis Script

This script analyzes wallet quality scores for the top 10 wallets
and provides recommendations for copy trading.

Author: Polymarket Copy Bot Team
Date: 2025-12-27
Version: 1.0
"""

import asyncio
import json
import sys
import time
from decimal import Decimal, getcontext, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta

# Add project to path
sys.path.insert(0, '/home/ink/polymarket-copy-bot')

try:
    from config.scanner_config import ScannerConfig
    from scanners.leaderboard_scanner import LeaderboardScanner
    from core.wallet_quality_scorer import WalletQualityScorer
    from core.red_flag_detector import RedFlagDetector
    from core.dynamic_position_sizer import DynamicPositionSizer
    from core.composite_scoring_engine import CompositeScoringEngine
    from core.wallet_behavior_monitor import WalletBehaviorMonitor
    from core.market_condition_analyzer import MarketConditionAnalyzer

    # Configure Decimal for financial calculations
    getcontext().prec = 28
    getcontext().rounding = ROUND_HALF_UP

    # Colors for terminal output
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

    async def main():
        """Main analysis function"""
        print(f"{GREEN}{'='*80}")
        print(f"{GREEN}🎯 Copy Trading Bot - Wallet Quality Analysis")
        print(f"{GREEN}{'='*80}")

        # Initialize config
        config = ScannerConfig()
        print(f"\n{BLUE}STEP 1: Initializing scanners...{NC}")

        try:
            leaderboard_scanner = LeaderboardScanner(config=config)
            quality_scorer = WalletQualityScorer(config=config)
            red_flag_detector = RedFlagDetector(config=config)
            dynamic_position_sizer = DynamicPositionSizer(config=config)
            composite_scoring_engine = CompositeScoringEngine(
                config=config,
                wallet_quality_scorer=quality_scorer,
                red_flag_detector=red_flag_detector,
            )
            behavior_monitor = WalletBehaviorMonitor(config=config)
            market_condition_analyzer = MarketConditionAnalyzer(
                config=config,
                wallet_quality_scorer=quality_scorer,
            )

            print(f"{GREEN}✅ All components initialized successfully{NC}")

        except Exception as e:
            print(f"{RED}❌ Error initializing components: {e}{NC}")
            print(f"{RED}   This may indicate missing dependencies{NC}")
            print(f"{YELLOW}   Try: pip install -r requirements.txt{NC}")
            return

        # Scan leaderboards
        print(f"\n{BLUE}STEP 2: Scanning leaderboards for wallets...{NC}")
        print(f"{YELLOW}This may take 1-2 minutes...{NC}")

        start_time = time.time()

        try:
            wallet_results = await leaderboard_scanner.scan_leaderboards(
                max_wallets=100,  # Get top 100 wallets
                days_back=30,  # 30 days of history
            )
        except Exception as e:
            print(f"{RED}❌ Error scanning leaderboards: {e}{NC}")
            print(f"{RED}   This may indicate API connectivity issues{NC}")
            return

        scan_time = time.time() - start_time
        print(f"{GREEN}✅ Scan completed in {scan_time:.1f}s{NC}")
        print(f"{GREEN}📊 Found {len(wallet_results)} wallets from leaderboards{NC}")

        if not wallet_results:
            print(f"{RED}❌ No wallets found - check API configuration{NC}")
            return

        # Score wallets (top 20 for this analysis)
        print(f"\n{BLUE}STEP 3: Scoring top 20 wallets...{NC}")
        print(f"{YELLOW}This may take 30-60 seconds...{NC}")

        start_time = time.time()
        scored_wallets = []

        for i, wallet in enumerate(wallet_results[:20], 1):
            # Create wallet data dictionary
            wallet_data = {
                'address': wallet.address,
                'trades': wallet.trades or [],
                'trade_count': len(wallet.trades) if wallet.trades else 0,
                'win_rate': wallet.metrics.get('win_rate', 0.5) if wallet.metrics else 0.5,
                'roi_7d': wallet.metrics.get('roi_7d', 0.0) if wallet.metrics else 0.0,
                'roi_30d': wallet.metrics.get('roi_30d', 0.0) if wallet.metrics else 0.0,
                'profit_factor': wallet.metrics.get('profit_factor', 1.5) if wallet.metrics else 1.5,
                'max_drawdown': wallet.metrics.get('max_drawdown', 0.2) if wallet.metrics else 0.2,
                'volatility': wallet.metrics.get('volatility', 0.15) if wallet.metrics else 0.15,
                'sharpe_ratio': wallet.metrics.get('sharpe_ratio', 0.8) if wallet.metrics else 0.8,
                'downside_volatility': wallet.metrics.get('downside_volatility', 0.1) if wallet.metrics else 0.1,
                'avg_position_hold_time': wallet.metrics.get('avg_position_hold_time', 7200) if wallet.metrics else 7200,
                'trade_categories': wallet.metrics.get('trade_categories', []) if wallet.metrics else [],
                'created_at': wallet.created_at.isoformat() if wallet.created_at else '2023-01-01T00:00:00Z',
                'avg_position_size': wallet.metrics.get('avg_position_size', 100) if wallet.metrics else 100,
                'max_single_trade': 200,
            }

            # Score wallet
            score_result = await quality_scorer.score_wallet(
                wallet_address=wallet.address,
                wallet_data=wallet_data,
                use_cache=True,
            )

            if score_result:
                try:
                    # Detect red flags
                    red_flag_result = await red_flag_detector.detect_red_flags(
                        wallet_address=wallet.address,
                        wallet_data=wallet_data,
                        use_cache=True,
                    )

                    # Calculate position size
                    original_trade = Decimal(str(wallet_data.get('avg_position_size', 100))
                    position_size_result = await dynamic_position_sizer.calculate_position_size(
                        wallet_address=wallet.address,
                        original_trade=original_trade,
                        account_balance=Decimal("1000.00"),  # Test with $1,000
                        use_cache=True,
                    )

                    # Get behavior changes
                    behavior_result = await behavior_monitor.get_wallet_summary(wallet.address)

                    # Calculate composite score
                    composite_score = await composite_scoring_engine.calculate_composite_score(
                        wallet_address=wallet.address,
                        wallet_data=wallet_data,
                        use_cache=True,
                    )

                    # Get market state
                    market_state = await market_condition_analyzer.get_market_state()

                    scored_wallets.append({
                        'rank': i,
                        'address': wallet.address,
                        'quality_score': score_result.total_score,
                        'quality_tier': score_result.quality_tier.value,
                        'is_market_maker': score_result.is_market_maker,
                        'red_flag_count': len(red_flag_result.red_flags),
                        'is_excluded': red_flag_result.is_excluded,
                        'exclusion_reason': red_flag_result.exclusion_reason.value if red_flag_result.exclusion_reason else None,
                        'win_rate': wallet_data['win_rate'],
                        'roi_30d': wallet_data['roi_30d'],
                        'profit_factor': wallet_data['profit_factor'],
                        'max_drawdown': wallet_data['max_drawdown'],
                        'sharpe_ratio': wallet_data['sharpe_ratio'],
                        'composite_score': composite_score.composite_score if composite_score else 0.0,
                        'position_size': float(position_size_result.final_size) if position_size_result else 0.0,
                        'behavior_changes': len(behavior_result.get('behavior_changes', [])),
                    })

                    # Show progress
                    progress = i / len(wallet_results[:20])
                    print(f"{GREEN}  [{progress:.0%}] Scored {wallet.address[-6:]}: "
                          f"{score_result.quality_tier.value} ({score_result.total_score:.2f}/10){NC}")

                except Exception as e:
                    print(f"{RED}⚠️  Error scoring {wallet.address[-6:]}: {e}{NC}")
                    continue

        score_time = time.time() - start_time
        print(f"{GREEN}✅ Wallet scoring completed in {score_time:.1f}s{NC}")

        # Sort by composite score (highest first)
        sorted_wallets = sorted(scored_wallets, key=lambda x: x['composite_score'], reverse=True)

        # Filter out excluded wallets
        qualified_wallets = [w for w in sorted_wallets if not w['is_excluded'] and not w['is_market_maker']]

        # Display results
        print(f"\n{GREEN}{'='*80}")
        print(f"{GREEN}📊 WALLET QUALITY ANALYSIS RESULTS")
        print(f"{GREEN}{'='*80}")

        # Summary statistics
        print(f"\n{BLUE}Summary Statistics:{NC}")
        print(f"  📈 Total wallets scored: {len(sorted_wallets)}")
        print(f"  ✅ Qualified wallets: {len(qualified_wallets)}")
        print(f"  🚫 Excluded wallets: {len(sorted_wallets) - len(qualified_wallets)}")
        print(f"  🏆 Market makers: {sum(1 for w in sorted_wallets if w['is_market_maker'])}")

        # Quality score distribution
        elite_count = sum(1 for w in qualified_wallets if w['quality_tier'] == "Elite")
        expert_count = sum(1 for w in qualified_wallets if w['quality_tier'] == "Expert")
        good_count = sum(1 for w in qualified_wallets if w['quality_tier'] == "Good")
        poor_count = sum(1 for w in qualified_wallets if w['quality_tier'] == "Poor")

        print(f"\n{BLUE}Quality Score Distribution:{NC}")
        print(f"  🏆 Elite (9.0-10.0): {elite_count} wallets")
        print(f"  ⭐ Expert (7.0-8.9): {expert_count} wallets")
        print(f"  ✅ Good (5.0-6.9): {good_count} wallets")
        print(f"  🟡 Poor (<5.0): {poor_count} wallets")

        # Top 10 qualified wallets
        print(f"\n{GREEN}🏆 TOP 10 QUALIFIED WALLETS FOR COPYING")
        print(f"{GREEN}{'='*80}")

        print(f"\n{'Rank':<6} {'Address':<12} {'Quality':<12} {'Score':<10} {'Win Rate':<12} {'ROI 30d':<12} {'Profit Factor':<12} {'Max DD':<12} {'Position'}")
        print(f"{'-':<80}")

        for i, wallet in enumerate(qualified_wallets[:10], 1):
            tier_color = {
                "Elite": CYAN,
                "Expert": GREEN,
                "Good": YELLOW,
                "Poor": RED,
            }.get(wallet['quality_tier'], WHITE)

            print(f"{i:<6} {wallet['address'][-6:]:<12} {tier_color}{wallet['quality_tier']:<8}{NC} "
                  f"{wallet['quality_score']:<10.2f}  {wallet['win_rate']:<10.1%}  "
                  f"{wallet['roi_30d']:<10.1%}  {wallet['profit_factor']:<10.2f}  "
                  f"{wallet['max_drawdown']:<10.1%}  ${wallet['position_size']:>8.2f}{NC}")

        print(f"{'-':<80}")

        # Red flag summary
        print(f"\n{BLUE}Red Flag Analysis:{NC}")
        red_flag_count = sum(w['red_flag_count'] for w in qualified_wallets)
        print(f"  🚫 Total red flags detected: {red_flag_count}")
        print(f"  📈 Average per wallet: {red_flag_count / len(qualified_wallets):.1f}")

        # Recommendations
        print(f"\n{GREEN}💡 RECOMMENDATIONS:{NC}")
        print(f"  ✅ Start with {min(3, len(qualified_wallets))} elite/expert wallets{NC}")
        print(f"  ✅ Use position sizing based on quality scores{NC}")
        print(f"  ✅ Monitor behavior changes for all wallets{NC}")
        print(f"  ✅ Exclude wallets with 3+ red flags{NC}")
        print(f"  ✅ Re-score wallets every 7 days{NC}")
        print(f"  ✅ Use dry-run mode for first 24 hours{NC}")

        # Save results to file
        output_file = "/tmp/wallet_quality_analysis.json"
        results_data = {
            "timestamp": time.time(),
            "total_wallets_scored": len(sorted_wallets),
            "qualified_wallets": len(qualified_wallets),
            "excluded_wallets": len(sorted_wallets) - len(qualified_wallets),
            "top_10_wallets": [
                {
                    "address": w['address'],
                    "quality_score": w['quality_score'],
                    "quality_tier": w['quality_tier'],
                    "win_rate": w['win_rate'],
                    "roi_30d": w['roi_30d'],
                    "composite_score": w['composite_score'],
                    "position_size": w['position_size'],
                    "red_flags": w['red_flag_count'],
                }
                for w in qualified_wallets[:10]
            ],
            "quality_distribution": {
                "Elite": elite_count,
                "Expert": expert_count,
                "Good": good_count,
                "Poor": poor_count,
            },
            "red_flag_summary": {
                "total_red_flags": red_flag_count,
                "average_per_wallet": red_flag_count / len(qualified_wallets) if qualified_wallets else 0,
            },
        }

        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2, default=str)

        print(f"\n{GREEN}💾 Results saved to: {output_file}{NC}")

        print(f"\n{GREEN}{'='*80}")
        print(f"{GREEN}✅ WALLET QUALITY ANALYSIS COMPLETE!")
        print(f"{GREEN}{'='*80}")

        print(f"\n{BLUE}Next Steps:{NC}")
        print(f"  1. Review the top 10 qualified wallets above{NC}")
        print(f"  2. Update .env with wallet addresses to monitor:")
        print(f"     echo 'WALLET_ADDRESSES=0x742d35...,0xabc123...' >> .env{NC}")
        print(f"  3. Run staging deployment: {YELLOW}./scripts/deploy_production_strategy.sh staging --dry-run{NC}")
        print(f"  4. Monitor logs: {YELLOW}journalctl -u polymarket-bot -f{NC}")

        print(f"\n{GREEN}{'='*80}")
        print(f"{GREEN}🚀 Ready for deployment to staging!")
        print(f"{GREEN}{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())

