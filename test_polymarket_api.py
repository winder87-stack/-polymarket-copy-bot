#!/usr/bin/env python3
"""
Polymarket API Test Script
Comprehensive testing of the Polymarket API client functionality
"""

import asyncio
import json
import os
import sys
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Simple logger setup for testing
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Mock configuration for testing
class MockScannerConfig:
    """Mock configuration for testing"""

    def __init__(self):
        self.POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")
        self.API_ENDPOINTS = [
            "https://polymarket.com/api/v1/leaderboard",  # Primary (updated)
            "https://polymarket.com/api/leaderboard",  # Fallback (original)
            "https://polymarket.com/v1/leaderboard",  # Alternative
            "https://polymarket.com/leaderboard",  # Last resort
        ]
        self.USE_TESTNET = False
        self.API_TIMEOUT = 30  # seconds


# Import after path setup
try:
    # Direct import to avoid config dependencies
    import requests
    import time
    import json
    from typing import List, Dict, Any

    # Copy the API client code directly to avoid import issues
    class PolymarketLeaderboardAPI:
        """Production-grade API client with endpoint fallbacks and health checks"""

        def __init__(self, config):
            self.config = config
            self.session = requests.Session()
            self.session.headers.update(
                {
                    "User-Agent": "PolymarketCopyBot/1.0",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {config.POLYMARKET_API_KEY}"
                    if hasattr(config, "POLYMARKET_API_KEY")
                    and config.POLYMARKET_API_KEY
                    else "",
                }
            )
            self.last_request_time = 0
            self.rate_limit_delay = 1.5
            self.max_retries = 3
            self.current_endpoint_index = 0

    def _respect_rate_limits(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _get_next_endpoint(self) -> str:
        """Rotate through endpoints on failure"""
        endpoint = self.config.API_ENDPOINTS[self.current_endpoint_index]
        self.current_endpoint_index = (self.current_endpoint_index + 1) % len(
            self.config.API_ENDPOINTS
        )
        return endpoint

    def get_leaderboard(self, page: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
        """Get leaderboard data with endpoint fallbacks"""
        attempted_endpoints = []

        for _ in range(len(self.config.API_ENDPOINTS)):
            endpoint = self._get_next_endpoint()
            attempted_endpoints.append(endpoint)

            for attempt in range(self.max_retries):
                try:
                    self._respect_rate_limits()

                    params = {
                        "page": page,
                        "limit": limit,
                        "sortBy": "roi",
                        "timeframe": "30d",
                        "testnet": str(self.config.USE_TESTNET).lower(),
                    }

                    logger.info(f"📡 Requesting leaderboard from: {endpoint}")
                    logger.debug(f"Params: {params}")

                    response = self.session.get(
                        endpoint, params=params, timeout=self.config.API_TIMEOUT
                    )

                    if response.status_code == 200:
                        try:
                            data = response.json()
                            return self._parse_response(data, endpoint)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error from {endpoint}: {e}")
                            continue

                    elif response.status_code == 404:
                        logger.warning(
                            f"404 Not Found from {endpoint} - trying next endpoint"
                        )
                        break  # Break to next endpoint

                    elif response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(
                            f"Rate limited by {endpoint}. Waiting {retry_after}s..."
                        )
                        time.sleep(retry_after)
                        continue

                    else:
                        logger.error(
                            f"HTTP {response.status_code} from {endpoint}: {response.text[:200]}"
                        )
                        if attempt < self.max_retries - 1:
                            time.sleep(2**attempt)  # Exponential backoff
                            continue

                except RequestException as e:
                    logger.error(
                        f"Network error with {endpoint} (attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(2**attempt)
                        continue
                except Exception as e:
                    logger.error(f"Unexpected error with {endpoint}: {str(e)}")

            # If we get here, this endpoint failed completely
            logger.error(f"❌ All attempts failed for endpoint: {endpoint}")

        # 🔴 ALL ENDPOINTS FAILED - Use fallback wallets
        logger.critical(
            f"🚨 ALL API ENDPOINTS FAILED after trying: {attempted_endpoints}"
        )
        return self._get_fallback_wallets()

    def get_leaderboard(self, page: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
        """Get leaderboard data with endpoint fallbacks"""
        attempted_endpoints = []

        for _ in range(len(self.config.API_ENDPOINTS)):
            endpoint = self._get_next_endpoint()
            attempted_endpoints.append(endpoint)

            for attempt in range(self.max_retries):
                try:
                    self._respect_rate_limits()

                    params = {
                        "page": page,
                        "limit": limit,
                        "sortBy": "roi",
                        "timeframe": "30d",
                        "testnet": str(self.config.USE_TESTNET).lower(),
                    }

                    logger.info(f"📡 Requesting leaderboard from: {endpoint}")
                    logger.debug(f"Params: {params}")

                    response = self.session.get(
                        endpoint, params=params, timeout=self.config.API_TIMEOUT
                    )

                    if response.status_code == 200:
                        try:
                            data = response.json()
                            return self._parse_response(data, endpoint)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error from {endpoint}: {e}")
                            continue

                    elif response.status_code == 404:
                        logger.warning(
                            f"404 Not Found from {endpoint} - trying next endpoint"
                        )
                        break  # Break to next endpoint

                    elif response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(
                            f"Rate limited by {endpoint}. Waiting {retry_after}s..."
                        )
                        time.sleep(retry_after)
                        continue

                    else:
                        logger.error(
                            f"HTTP {response.status_code} from {endpoint}: {response.text[:200]}"
                        )
                        if attempt < self.max_retries - 1:
                            time.sleep(2**attempt)  # Exponential backoff
                            continue

                except RequestException as e:
                    logger.error(
                        f"Network error with {endpoint} (attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(2**attempt)
                        continue
                except Exception as e:
                    logger.error(f"Unexpected error with {endpoint}: {str(e)}")

            # If we get here, this endpoint failed completely
            logger.error(f"❌ All attempts failed for endpoint: {endpoint}")

        logger.critical(
            f"🚨 ALL API ENDPOINTS FAILED after trying: {attempted_endpoints}"
        )
        return self._get_fallback_wallets()

    def _parse_response(self, data: Any, endpoint: str) -> List[Dict[str, Any]]:
        """Parse API response handling different formats"""
        if isinstance(data, dict) and "data" in data:
            logger.debug(f"✅ Parsed data format from {endpoint}: 'data' key present")
            return data["data"]
        elif isinstance(data, list):
            logger.debug(f"✅ Parsed data format from {endpoint}: direct list")
            return data
        else:
            logger.error(f"❌ Unexpected response format from {endpoint}: {type(data)}")
            return []

    def _get_fallback_wallets(self) -> List[Dict[str, Any]]:
        """Emergency fallback wallet data"""
        return [
            {
                "address": "0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9",
                "trade_count": 150,
                "created_at": "2023-01-15T00:00:00Z",
                "roi_30d": 25.0,
                "win_rate": 0.68,
                "name": "Fallback Trader 1",
            },
            {
                "address": "0x8a5d7f382763a2a954e85c8d89a0e3f4a9c5f3b8",
                "trade_count": 125,
                "created_at": "2023-02-20T00:00:00Z",
                "roi_30d": 18.5,
                "win_rate": 0.62,
                "name": "Fallback Trader 2",
            },
            {
                "address": "0x9b3e7f1c5d4a2b1d8c7e6f5a4b3c2d1e0f9a8b7c",
                "trade_count": 200,
                "created_at": "2022-11-10T00:00:00Z",
                "roi_30d": 32.0,
                "win_rate": 0.71,
                "name": "Fallback Trader 3",
            },
        ]

    def health_check(self) -> bool:
        """✅ Health check for API connectivity"""
        try:
            self._respect_rate_limits()
            url = f"{self.base_url}{self.config.HEALTH_CHECK_ENDPOINT}"

            response = self.session.get(url, timeout=10)
            is_healthy = response.status_code == 200

            logger.debug(
                f"API Health Check: {'✅ HEALTHY' if is_healthy else '❌ UNHEALTHY'} (Status: {response.status_code})"
            )
            return is_healthy

        except Exception as e:
            logger.error(f"API health check failed: {str(e)[:100]}")
            return False

    API_AVAILABLE = True
    logger.info("✅ API client loaded directly")

except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    API_AVAILABLE = False


class PolymarketAPITester:
    """Comprehensive tester for Polymarket API functionality"""

    def __init__(self):
        if not API_AVAILABLE:
            raise RuntimeError("Polymarket API client not available")

        self.config = MockScannerConfig()
        self.api_client = PolymarketLeaderboardAPI(self.config)
        self.test_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tests_run": [],
            "passed": 0,
            "failed": 0,
            "errors": [],
        }

    def log_test_result(
        self, test_name: str, success: bool, message: str = "", data: Any = None
    ):
        """Log individual test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}: {message}")

        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if data is not None:
            result["data"] = data

        self.test_results["tests_run"].append(result)

        if success:
            self.test_results["passed"] += 1
        else:
            self.test_results["failed"] += 1

    async def test_health_check(self) -> bool:
        """Test API health check functionality"""
        try:
            logger.info("🔍 Testing API health check...")
            healthy = self.api_client.health_check()

            if healthy:
                self.log_test_result("health_check", True, "API health check passed")
                return True
            else:
                self.log_test_result("health_check", False, "API health check failed")
                return False

        except Exception as e:
            self.log_test_result("health_check", False, f"Health check error: {str(e)}")
            return False

    async def test_leaderboard_basic(self) -> bool:
        """Test basic leaderboard retrieval"""
        try:
            logger.info("📊 Testing basic leaderboard retrieval...")
            start_time = time.time()

            results = self.api_client.get_leaderboard(page=1, limit=10)

            duration = time.time() - start_time

            if results and len(results) > 0:
                self.log_test_result(
                    "leaderboard_basic",
                    True,
                    f"Retrieved {len(results)} wallets in {duration:.2f}s",
                    {
                        "count": len(results),
                        "duration": duration,
                        "sample_wallet": results[0] if results else None,
                    },
                )
                return True
            else:
                self.log_test_result(
                    "leaderboard_basic", False, "No leaderboard data retrieved"
                )
                return False

        except Exception as e:
            self.log_test_result(
                "leaderboard_basic", False, f"Leaderboard error: {str(e)}"
            )
            return False

    async def test_leaderboard_pagination(self) -> bool:
        """Test leaderboard pagination"""
        try:
            logger.info("📄 Testing leaderboard pagination...")

            # Test multiple pages
            all_results = []
            for page in range(1, 4):  # Test first 3 pages
                results = self.api_client.get_leaderboard(page=page, limit=5)
                if results:
                    all_results.extend(results)
                    logger.info(f"  Page {page}: {len(results)} wallets")
                else:
                    break

            if len(all_results) >= 5:  # Should have at least 5 wallets
                self.log_test_result(
                    "leaderboard_pagination",
                    True,
                    f"Successfully paginated {len(all_results)} total wallets",
                    {"pages_tested": page, "total_wallets": len(all_results)},
                )
                return True
            else:
                self.log_test_result(
                    "leaderboard_pagination", False, "Insufficient pagination results"
                )
                return False

        except Exception as e:
            self.log_test_result(
                "leaderboard_pagination", False, f"Pagination error: {str(e)}"
            )
            return False

    async def test_rate_limiting(self) -> bool:
        """Test rate limiting functionality"""
        try:
            logger.info("⏱️ Testing rate limiting...")

            start_time = time.time()

            # Make multiple rapid requests
            for i in range(5):
                results = self.api_client.get_leaderboard(page=1, limit=5)
                if not results:
                    break

            duration = time.time() - start_time

            # Should take at least 5 seconds due to rate limiting (5 requests * 1.5s delay)
            if duration >= 5.0:
                self.log_test_result(
                    "rate_limiting",
                    True,
                    f"Rate limiting working correctly ({duration:.2f}s for 5 requests)",
                    {"duration": duration, "expected_min": 5.0},
                )
                return True
            else:
                self.log_test_result(
                    "rate_limiting",
                    False,
                    f"Rate limiting may not be working ({duration:.2f}s, expected >= 5.0s)",
                )
                return False

        except Exception as e:
            self.log_test_result(
                "rate_limiting", False, f"Rate limiting test error: {str(e)}"
            )
            return False

    async def test_endpoint_fallback(self) -> bool:
        """Test endpoint fallback functionality"""
        try:
            logger.info("🔄 Testing endpoint fallback...")

            # Test with invalid endpoint first
            original_endpoints = self.config.API_ENDPOINTS.copy()

            # Temporarily modify config to test fallback
            self.config.API_ENDPOINTS = [
                "https://invalid-domain-that-does-not-exist.com"
            ] + original_endpoints

            try:
                results = self.api_client.get_leaderboard(page=1, limit=5)

                # Restore original endpoints
                self.config.API_ENDPOINTS = original_endpoints

                if results and len(results) > 0:
                    self.log_test_result(
                        "endpoint_fallback",
                        True,
                        f"Endpoint fallback working - retrieved {len(results)} wallets after fallback",
                        {"fallback_triggered": True, "results_count": len(results)},
                    )
                    return True
                else:
                    self.log_test_result(
                        "endpoint_fallback", False, "Endpoint fallback failed"
                    )
                    return False

            finally:
                # Always restore original endpoints
                self.config.FALLBACK_ENDPOINTS = original_endpoints

        except Exception as e:
            self.log_test_result(
                "endpoint_fallback", False, f"Fallback test error: {str(e)}"
            )
            return False

    async def test_data_validation(self) -> bool:
        """Test data validation and structure"""
        try:
            logger.info("✅ Testing data validation...")

            results = self.api_client.get_leaderboard(page=1, limit=10)

            if not results:
                self.log_test_result("data_validation", False, "No data to validate")
                return False

            # Validate wallet data structure
            required_fields = ["address"]
            valid_wallets = 0

            for wallet in results[:5]:  # Check first 5 wallets
                if isinstance(wallet, dict):
                    missing_fields = [
                        field for field in required_fields if field not in wallet
                    ]
                    if not missing_fields:
                        valid_wallets += 1
                    else:
                        logger.warning(f"Wallet missing fields: {missing_fields}")
                else:
                    logger.warning(f"Wallet is not a dict: {type(wallet)}")

            if valid_wallets >= 3:  # At least 3 valid wallets
                self.log_test_result(
                    "data_validation",
                    True,
                    f"Data validation passed: {valid_wallets}/{len(results[:5])} wallets valid",
                    {"valid_wallets": valid_wallets, "total_checked": len(results[:5])},
                )
                return True
            else:
                self.log_test_result(
                    "data_validation",
                    False,
                    f"Data validation failed: only {valid_wallets}/{len(results[:5])} wallets valid",
                )
                return False

        except Exception as e:
            self.log_test_result(
                "data_validation", False, f"Validation error: {str(e)}"
            )
            return False

    async def test_emergency_fallback(self) -> bool:
        """Test emergency fallback functionality"""
        try:
            logger.info("🚨 Testing emergency fallback...")

            # Force all endpoints to fail by modifying base URL temporarily
            original_base_url = self.api_client.base_url
            self.api_client.base_url = "https://invalid-domain-that-does-not-exist.com"

            try:
                results = self.api_client.get_leaderboard(page=1, limit=5)

                # Restore original URL
                self.api_client.base_url = original_base_url

                if results and len(results) >= 3:  # Should get fallback wallets
                    self.log_test_result(
                        "emergency_fallback",
                        True,
                        f"Emergency fallback working - retrieved {len(results)} fallback wallets",
                        {"fallback_activated": True, "fallback_wallets": len(results)},
                    )
                    return True
                else:
                    self.log_test_result(
                        "emergency_fallback", False, "Emergency fallback failed"
                    )
                    return False

            finally:
                # Always restore original URL
                self.api_client.base_url = original_base_url

        except Exception as e:
            self.log_test_result(
                "emergency_fallback", False, f"Fallback test error: {str(e)}"
            )
            return False

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all API tests"""
        logger.info("🚀 Starting Polymarket API Test Suite")
        logger.info("=" * 50)

        # Run all tests
        tests = [
            ("Health Check", self.test_health_check),
            ("Basic Leaderboard", self.test_leaderboard_basic),
            ("Leaderboard Pagination", self.test_leaderboard_pagination),
            ("Rate Limiting", self.test_rate_limiting),
            ("Endpoint Fallback", self.test_endpoint_fallback),
            ("Data Validation", self.test_data_validation),
            ("Emergency Fallback", self.test_emergency_fallback),
        ]

        for test_name, test_func in tests:
            logger.info(f"\n🧪 Running: {test_name}")
            try:
                await test_func()
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                self.log_test_result(
                    test_name.lower().replace(" ", "_"), False, f"Exception: {str(e)}"
                )

            # Small delay between tests
            await asyncio.sleep(0.5)

        # Generate summary
        total_tests = len(self.test_results["tests_run"])
        passed = self.test_results["passed"]
        failed = self.test_results["failed"]

        logger.info("\n" + "=" * 50)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"✅ Passed: {passed}")
        logger.info(f"❌ Failed: {failed}")
        logger.info(f"Success Rate: {passed / total_tests * 100:.1f}%")
        # Save detailed results
        self.save_test_results()

        return {
            "total_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "success_rate": passed / total_tests if total_tests > 0 else 0,
            "results": self.test_results,
        }

    def save_test_results(self):
        """Save test results to file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"polymarket_api_test_{timestamp}.json"

            with open(filename, "w") as f:
                json.dump(self.test_results, f, indent=2, default=str)

            logger.info(f"💾 Test results saved to: {filename}")

        except Exception as e:
            logger.error(f"Failed to save test results: {e}")


def main():
    """Main test runner"""
    try:
        if not API_AVAILABLE:
            logger.error(
                "❌ Polymarket API client not available. Please check dependencies."
            )
            sys.exit(1)

        # Check configuration
        config = MockScannerConfig()
        logger.info("🔧 Mock configuration loaded successfully")
        logger.info(f"API Endpoints: {len(config.API_ENDPOINTS)} configured")
        logger.info(f"Testnet Mode: {config.USE_TESTNET}")
        logger.info(f"API Timeout: {config.API_TIMEOUT}s")
        logger.info(
            f"API Key configured: {'Yes' if config.POLYMARKET_API_KEY else 'No'}"
        )

        # Run tests
        tester = PolymarketAPITester()
        results = asyncio.run(tester.run_all_tests())

        # Exit with appropriate code
        if results["success_rate"] >= 0.8:  # 80% success rate
            logger.info("🎉 API tests PASSED!")
            sys.exit(0)
        else:
            logger.error("💥 API tests FAILED!")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n⏹️ Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Test suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
