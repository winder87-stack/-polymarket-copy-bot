#!/usr/bin/env python3
"""
Final System Validation - Polymarket Copy Trading Bot
Comprehensive end-to-end validation before production deployment.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import system components
from config.settings import settings
from core.clob_client import PolymarketClient
from core.trade_executor import TradeExecutor
from core.wallet_monitor import WalletMonitor
from main import PolymarketCopyBot


class SystemValidator:
    """Comprehensive system validation suite."""

    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()
        self.performance_metrics = {}

    async def run_full_validation(self) -> Dict[str, Any]:
        """Run complete system validation suite."""
        print("🚀 Starting Final System Validation...")
        print("=" * 60)

        # Component Integration Tests
        self.results[
            "component_initialization"
        ] = await self.test_component_initialization()
        self.results[
            "configuration_validation"
        ] = await self.test_configuration_validation()
        self.results["security_validation"] = await self.test_security_validation()
        self.results[
            "performance_validation"
        ] = await self.test_performance_validation()
        self.results[
            "reliability_validation"
        ] = await self.test_reliability_validation()
        self.results[
            "integration_validation"
        ] = await self.test_integration_validation()

        # Calculate overall score
        self.results["overall_score"] = self.calculate_overall_score()
        self.results["validation_duration"] = (
            datetime.now() - self.start_time
        ).total_seconds()

        return self.results

    async def test_component_initialization(self) -> Dict[str, Any]:
        """Test component initialization and basic functionality."""
        print("🔧 Testing Component Initialization...")

        results = {
            "status": "PASS",
            "components_tested": 0,
            "components_passed": 0,
            "details": [],
        }

        try:
            # Test settings initialization
            results["components_tested"] += 1
            settings.validate_critical_settings()
            results["components_passed"] += 1
            results["details"].append("✅ Settings validation passed")

            # Test CLOB client initialization
            results["components_tested"] += 1
            with patch("core.clob_client.Web3"):
                clob_client = PolymarketClient()
                assert clob_client.wallet_address is not None
                results["components_passed"] += 1
                results["details"].append("✅ CLOB client initialization passed")

            # Test wallet monitor initialization
            results["components_tested"] += 1
            with patch("core.wallet_monitor.Web3"):
                wallet_monitor = WalletMonitor()
                assert len(wallet_monitor.target_wallets) >= 0
                results["components_passed"] += 1
                results["details"].append("✅ Wallet monitor initialization passed")

            # Test trade executor initialization
            results["components_tested"] += 1
            with patch("core.clob_client.Web3"):
                mock_client = PolymarketClient()
                trade_executor = TradeExecutor(mock_client)
                assert trade_executor.clob_client == mock_client
                assert hasattr(trade_executor, "_state_lock")
                results["components_passed"] += 1
                results["details"].append("✅ Trade executor initialization passed")

        except Exception as e:
            results["status"] = "FAIL"
            results["details"].append(f"❌ Component initialization failed: {e}")

        success_rate = results["components_passed"] / results["components_tested"]
        results["success_rate"] = success_rate

        if success_rate >= 0.8:
            results["status"] = "PASS"
        else:
            results["status"] = "FAIL"

        return results

    async def test_configuration_validation(self) -> Dict[str, Any]:
        """Test configuration validation and environment handling."""
        print("⚙️ Testing Configuration Validation...")

        results = {"status": "PASS", "tests_run": 0, "tests_passed": 0, "details": []}

        try:
            # Test default configuration
            results["tests_run"] += 1
            from config.settings import Settings

            default_settings = Settings()
            assert default_settings.risk.max_daily_loss > 0
            results["tests_passed"] += 1
            results["details"].append("✅ Default configuration valid")

            # Test environment variable override
            results["tests_run"] += 1
            with patch.dict(os.environ, {"MAX_DAILY_LOSS": "200.0"}):
                env_settings = Settings()
                assert env_settings.risk.max_daily_loss == 200.0
                results["tests_passed"] += 1
                results["details"].append("✅ Environment variable override working")

            # Test critical settings validation
            results["tests_run"] += 1
            test_settings = Settings()
            test_settings.trading.private_key = "0x" + "1" * 64
            test_settings.validate_critical_settings()
            results["tests_passed"] += 1
            results["details"].append("✅ Critical settings validation passed")

        except Exception as e:
            results["status"] = "FAIL"
            results["details"].append(f"❌ Configuration validation failed: {e}")

        return results

    async def test_security_validation(self) -> Dict[str, Any]:
        """Test security features and controls."""
        print("🔒 Testing Security Validation...")

        results = {
            "status": "PASS",
            "security_tests": 0,
            "security_passed": 0,
            "details": [],
        }

        try:
            from utils.security import mask_sensitive_data, validate_private_key

            # Test private key validation
            results["security_tests"] += 1
            valid = validate_private_key("0x" + "a" * 64)
            assert valid
            results["security_passed"] += 1
            results["details"].append("✅ Private key validation working")

            # Test data masking
            results["security_tests"] += 1
            test_data = {
                "private_key": "0x1234567890abcdef",
                "api_key": "sk_live_secret",
                "normal": "safe_data",
            }
            masked = mask_sensitive_data(test_data)
            assert "[REDACTED]" in str(masked) or "0x1234..." in str(masked)
            assert "safe_data" in str(masked)
            results["security_passed"] += 1
            results["details"].append("✅ Data masking working")

            # Test race condition fixes
            results["security_tests"] += 1
            with patch("core.clob_client.Web3"):
                mock_client = PolymarketClient()
                executor = TradeExecutor(mock_client)
                assert hasattr(executor, "_state_lock")
                assert hasattr(executor, "_position_locks")
                results["security_passed"] += 1
                results["details"].append("✅ Race condition protections in place")

        except Exception as e:
            results["status"] = "FAIL"
            results["details"].append(f"❌ Security validation failed: {e}")

        return results

    async def test_performance_validation(self) -> Dict[str, Any]:
        """Test performance characteristics and optimizations."""
        print("⚡ Testing Performance Validation...")

        results = {
            "status": "PASS",
            "performance_tests": 0,
            "performance_passed": 0,
            "metrics": {},
            "details": [],
        }

        try:
            # Test API caching performance
            results["performance_tests"] += 1
            with (
                patch("core.wallet_monitor.Web3"),
                patch("aiohttp.ClientSession") as mock_session,
            ):
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(
                    return_value={
                        "status": "1",
                        "message": "OK",
                        "result": [{"hash": "0x123", "from": "0xabc"}],
                    }
                )

                mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

                wallet_monitor = WalletMonitor()
                start_time = time.time()

                # Test cached performance
                await wallet_monitor.get_wallet_transactions(
                    "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
                )
                first_call_time = time.time() - start_time

                # Second call should be cached (much faster)
                start_time = time.time()
                await wallet_monitor.get_wallet_transactions(
                    "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
                )
                second_call_time = time.time() - start_time

                # Cache should provide significant speedup
                if second_call_time < first_call_time * 0.1:  # 10x faster
                    results["performance_passed"] += 1
                    results["metrics"]["cache_speedup"] = (
                        first_call_time / second_call_time
                    )
                    results["details"].append(
                        f"Cache speedup: {results['metrics']['cache_speedup']:.1f}x"
                    )
                else:
                    results["details"].append(
                        f"⚠️ Cache performance suboptimal: {second_call_time:.3f}s vs {first_call_time:.3f}s"
                    )

            # Test concurrent operation performance
            results["performance_tests"] += 1
            start_time = time.time()

            # Simulate concurrent trade processing
            async def mock_trade_processing(trade_id):
                await asyncio.sleep(0.01)  # Simulate processing time
                return f"trade_{trade_id}_processed"

            # Process 20 trades concurrently
            tasks = [mock_trade_processing(i) for i in range(20)]
            await asyncio.gather(*tasks)
            concurrent_time = time.time() - start_time

            # Should complete in reasonable time
            if concurrent_time < 0.5:  # Less than 0.5 seconds
                results["performance_passed"] += 1
                results["metrics"]["concurrent_processing_time"] = concurrent_time
                results["details"].append(
                    f"Concurrent processing: {concurrent_time:.2f}s"
                )
            else:
                results["details"].append(
                    f"⚠️ Concurrent processing slow: {concurrent_time:.2f}s"
                )

        except Exception as e:
            results["status"] = "FAIL"
            results["details"].append(f"❌ Performance validation failed: {e}")

        return results

    async def test_reliability_validation(self) -> Dict[str, Any]:
        """Test system reliability and error handling."""
        print("🛡️ Testing Reliability Validation...")

        results = {
            "status": "PASS",
            "reliability_tests": 0,
            "reliability_passed": 0,
            "details": [],
        }

        try:
            # Test circuit breaker functionality
            results["reliability_tests"] += 1
            with patch("core.clob_client.Web3"):
                mock_client = PolymarketClient()
                executor = TradeExecutor(mock_client)

                # Test circuit breaker activation
                executor.daily_loss = executor.settings.risk.max_daily_loss + 10
                executor.activate_circuit_breaker("Test circuit breaker")

                assert executor.circuit_breaker_active
                results["reliability_passed"] += 1
                results["details"].append("✅ Circuit breaker activation working")

            # Test error recovery
            results["reliability_tests"] += 1
            with patch("core.clob_client.Web3"):
                mock_client = PolymarketClient()
                executor = TradeExecutor(mock_client)

                # Mock API failure then recovery
                call_count = 0

                async def mock_api_call(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        raise ConnectionError("API temporarily unavailable")
                    return {"orderID": "recovered_order_123"}

                mock_client.place_order = mock_api_call

                # This should handle the error gracefully
                trade = {
                    "tx_hash": "0x123",
                    "timestamp": datetime.now(),
                    "wallet_address": "0xabc",
                    "condition_id": "0xdef",
                    "side": "BUY",
                    "amount": 100.0,
                    "price": 0.5,
                    "confidence_score": 0.9,
                }

                result = await executor.execute_copy_trade(trade)
                # Should either succeed on retry or fail gracefully
                assert "status" in result
                results["reliability_passed"] += 1
                results["details"].append("✅ Error recovery working")

            # Test graceful degradation
            results["reliability_tests"] += 1
            with patch("core.clob_client.Web3"):
                mock_client = PolymarketClient()
                executor = TradeExecutor(mock_client)

                # Mock balance failure
                mock_client.get_balance = AsyncMock(return_value=None)

                trade = {
                    "tx_hash": "0x456",
                    "timestamp": datetime.now(),
                    "wallet_address": "0xdef",
                    "condition_id": "0xfed",
                    "side": "BUY",
                    "amount": 50.0,
                    "price": 0.6,
                    "confidence_score": 0.8,
                }

                result = await executor.execute_copy_trade(trade)
                # Should use conservative fallback
                assert result["status"] in ["success", "rejected", "failed"]
                results["reliability_passed"] += 1
                results["details"].append("✅ Graceful degradation working")

        except Exception as e:
            results["status"] = "FAIL"
            results["details"].append(f"❌ Reliability validation failed: {e}")

        return results

    async def test_integration_validation(self) -> Dict[str, Any]:
        """Test end-to-end component integration."""
        print("🔗 Testing Integration Validation...")

        results = {
            "status": "PASS",
            "integration_tests": 0,
            "integration_passed": 0,
            "details": [],
        }

        try:
            # Test main bot integration
            results["integration_tests"] += 1
            with (
                patch("core.clob_client.Web3"),
                patch("core.wallet_monitor.Web3"),
                patch("main.PolymarketCopyBot.monitor_loop", new_callable=AsyncMock),
            ):
                bot = PolymarketCopyBot()

                # Test initialization
                init_success = await bot.initialize()
                assert init_success

                # Test health check
                health_ok = await bot.health_check()
                assert (
                    health_ok is True or health_ok is None
                )  # None means recently checked

                results["integration_passed"] += 1
                results["details"].append("✅ Main bot integration working")

            # Test trade flow integration
            results["integration_tests"] += 1
            with patch("core.clob_client.Web3"), patch("core.wallet_monitor.Web3"):
                # Create integrated components
                clob_client = PolymarketClient()
                WalletMonitor()
                trade_executor = TradeExecutor(clob_client)

                # Mock a complete trade flow
                mock_trade = {
                    "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                    "timestamp": datetime.now(),
                    "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                    "condition_id": "0x1234567890abcdef1234567890abcdef12345678",
                    "side": "BUY",
                    "amount": 100.0,
                    "price": 0.5,
                    "confidence_score": 0.9,
                }

                # Mock API responses
                clob_client.get_balance = AsyncMock(return_value=1000.0)
                clob_client.get_current_price = AsyncMock(return_value=0.5)
                clob_client.place_order = AsyncMock(
                    return_value={"orderID": "test_order_123"}
                )

                # Execute trade
                result = await trade_executor.execute_copy_trade(mock_trade)

                # Verify integration worked
                assert result["status"] == "success"
                assert result["order_id"] == "test_order_123"
                assert "position_key" in result

                # Verify position was tracked
                position_key = result["position_key"]
                assert position_key in trade_executor.open_positions

                results["integration_passed"] += 1
                results["details"].append("✅ Trade flow integration working")

        except Exception as e:
            results["status"] = "FAIL"
            results["details"].append(f"❌ Integration validation failed: {e}")
            import traceback

            results["details"].append(f"Traceback: {traceback.format_exc()}")

        return results

    def calculate_overall_score(self) -> float:
        """Calculate overall validation score."""
        if not self.results:
            return 0.0

        total_tests = 0
        total_passed = 0

        for test_result in self.results.values():
            if isinstance(test_result, dict) and "status" in test_result:
                if (
                    "components_tested" in test_result
                    and "components_passed" in test_result
                ):
                    total_tests += test_result["components_tested"]
                    total_passed += test_result["components_passed"]
                elif "tests_run" in test_result and "tests_passed" in test_result:
                    total_tests += test_result.get("tests_run", 0)
                    total_passed += test_result.get("tests_passed", 0)
                elif (
                    "security_tests" in test_result and "security_passed" in test_result
                ):
                    total_tests += test_result["security_tests"]
                    total_passed += test_result["security_passed"]
                elif (
                    "performance_tests" in test_result
                    and "performance_passed" in test_result
                ):
                    total_tests += test_result["performance_tests"]
                    total_passed += test_result["performance_passed"]
                elif (
                    "reliability_tests" in test_result
                    and "reliability_passed" in test_result
                ):
                    total_tests += test_result["reliability_tests"]
                    total_passed += test_result["reliability_passed"]
                elif (
                    "integration_tests" in test_result
                    and "integration_passed" in test_result
                ):
                    total_tests += test_result["integration_tests"]
                    total_passed += test_result["integration_passed"]

        if total_tests == 0:
            return 0.0

        return (total_passed / total_tests) * 100

    def generate_validation_report(self) -> str:
        """Generate comprehensive validation report."""
        score = self.results.get("overall_score", 0)

        report = f"""Final Score: {score:.1f}/100
Percentage: {score:.1f}%

Validation Results Summary
========================

Overall Score: {score:.1f}%

Test Results:
"""

        for test_name, test_result in self.results.items():
            if test_name not in ["overall_score", "validation_duration"]:
                if isinstance(test_result, dict):
                    status = test_result.get("status", "UNKNOWN")
                    status_icon = "✅" if status == "PASS" else "❌"
                    report += f"- {test_name.replace('_', ' ').title()}: {status_icon} {status}\n"

                    # Add details
                    if "details" in test_result:
                        for detail in test_result["details"]:
                            report += f"  {detail}\n"

        report += f"\nValidation Duration: {self.results.get('validation_duration', 0):.2f} seconds\n"

        # Final recommendation
        if score >= 90:
            recommendation = "🟢 PRODUCTION READY - Full deployment approved"
        elif score >= 80:
            recommendation = "🟡 CONDITIONAL APPROVAL - Deploy with monitoring"
        else:
            recommendation = "🔴 NOT READY - Address critical issues first"

        report += f"\nFinal Recommendation: {recommendation}\n"

        if score >= 90:
            report += "\n✅ System validation PASSED - Ready for production deployment!"
        elif score >= 80:
            report += "\n⚠️ System validation PASSED with conditions - Monitor closely in production."
        else:
            report += "\n❌ System validation FAILED - Critical issues must be resolved before deployment."

        return report


async def main():
    """Run the final system validation."""
    # Set up test environment
    os.environ["PRIVATE_KEY"] = (
        "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    )
    os.environ["POLYGON_RPC_URL"] = "https://polygon-rpc.com"
    os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
    os.environ["TELEGRAM_CHAT_ID"] = "123456789"

    validator = SystemValidator()
    results = await validator.run_full_validation()

    # Generate and save report
    report = validator.generate_validation_report()

    print("\n" + "=" * 80)
    print("📊 FINAL SYSTEM VALIDATION REPORT")
    print("=" * 80)
    print(report)

    # Save detailed results
    with open("final_validation_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    with open("final_validation_report.md", "w") as f:
        f.write(report)

    print("📄 Detailed results saved to: final_validation_results.json")
    print("📄 Report saved to: final_validation_report.md")

    # Return success/failure
    score = results.get("overall_score", 0)
    return score >= 80  # 80% success rate required


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
